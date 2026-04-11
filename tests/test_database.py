import pandas as pd

from lifelike_gds.graph_sources.database import Database


class FakeNeo4jConnection:
    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.records_calls = []
        self.frame_calls = []
        self.single_calls = []
        self.closed = False
        self.records_result = []
        self.dataframe_result = pd.DataFrame()
        self.single_value_result = None

    def close(self):
        self.closed = True

    def get_records(self, query, parameters):
        self.records_calls.append((query, parameters))
        return self.records_result

    def get_dataframe(self, query, parameters):
        self.frame_calls.append((query, parameters))
        return self.dataframe_result

    def get_single_value(self, query, parameters):
        self.single_calls.append((query, parameters))
        return self.single_value_result


class FakeNode:
    def __init__(self, element_id, labels=None, **props):
        self.element_id = element_id
        self.labels = set(labels or [])
        self._props = props

    def items(self):
        return self._props.items()


def make_database(monkeypatch, config=None, **kwargs):
    holder = {}

    def fake_connection(**connection_kwargs):
        connection = FakeNeo4jConnection(**connection_kwargs)
        holder["connection"] = connection
        return connection

    monkeypatch.setattr("lifelike_gds.graph_sources.database.Neo4jConnection", fake_connection)
    monkeypatch.setattr(
        "lifelike_gds.graph_sources.database.read_config",
        lambda name: config
        or {
            "uri": "bolt://cfg",
            "user": "cfg-user",
            "password": "cfg-pass",
            "database": "cfg-db",
            "encrypted": True,
        },
    )
    db = Database(**kwargs)
    return db, holder["connection"]


def test_database_uses_config_defaults_when_connection_args_missing(monkeypatch):
    db, connection = make_database(monkeypatch, collection_label="Reactome")

    assert db.label_clause == ":Reactome"
    assert connection.init_kwargs == {
        "uri": "bolt://cfg",
        "username": "cfg-user",
        "password": "cfg-pass",
        "database": "cfg-db",
        "encrypted": True,
    }


def test_database_prefers_explicit_connection_arguments(monkeypatch):
    _, connection = make_database(
        monkeypatch,
        collection_label="BioCyc",
        uri="bolt://local",
        username="neo4j",
        password="secret",
        database="neo",
        encrypted=False,
    )

    assert connection.init_kwargs == {
        "uri": "bolt://local",
        "username": "neo4j",
        "password": "secret",
        "database": "neo",
        "encrypted": False,
    }


def test_database_builds_projection_queries_with_filters():
    class DemoDatabase(Database):
        DEFAULT_EXCLUDED_NODE_LABELS = ("CurrencyMetabolite",)
        TRACE_RELATIONSHIP_TYPES = ("INPUT", "OUTPUT")

    node_query, rel_query, params = DemoDatabase.build_trace_graph_projection_queries(
        collection_label="Reactome",
        exclude_nodes=["11", 22],
        exclude_node_labels=None,
    )

    assert "MATCH (n:Reactome)-[r:INPUT|OUTPUT]->(m:Reactome)" in node_query
    assert "NOT elementId(n) IN $exclude_ids" in node_query
    assert "label IN $exclude_node_labels" in rel_query
    assert params == {
        "exclude_ids": ["11", "22"],
        "exclude_node_labels": ["CurrencyMetabolite"],
    }


def test_database_normalizes_nodes_and_wrapper_queries(monkeypatch):
    db, connection = make_database(monkeypatch, collection_label="Reactome")
    connection.records_result = [
        {"n": FakeNode("123", labels=["PhysicalEntity"], displayName="ATP")},
        {"id": "raw-id", "name": "already-normalized"},
    ]

    nodes = db.get_nodes_by_node_ids(["123"])
    assert nodes[0]["id"] == "123"
    assert nodes[0]["_key"] == "123"
    assert nodes[0]["labels"] == ["PhysicalEntity"]
    assert nodes[0]["displayName"] == "ATP"
    assert nodes[1] == {"id": "raw-id", "name": "already-normalized"}

    query, params = connection.records_calls[0]
    assert "MATCH (n:Reactome)" in query
    assert params == {"node_ids": ["123"]}


def test_database_dataframe_single_value_and_trace_graph_helpers(monkeypatch):
    db, connection = make_database(monkeypatch, collection_label="BioCyc")
    connection.dataframe_result = pd.DataFrame([{"node_id": "n1"}])
    connection.single_value_result = 7

    frame = db.get_dataframe("RETURN 1 AS x", x=1)
    assert frame.to_dict(orient="records") == [{"node_id": "n1"}]
    assert connection.frame_calls == [("RETURN 1 AS x", {"x": 1})]

    assert db.get_single_value("RETURN 7 AS n", n=7) == 7
    assert connection.single_calls == [("RETURN 7 AS n", {"n": 7})]

    db.get_trace_graph_data(exclude_nodes=["a"], exclude_node_labels=["Ignore"])
    assert len(connection.frame_calls) == 3
    node_query, node_params = connection.frame_calls[1]
    rel_query, rel_params = connection.frame_calls[2]
    assert "UNWIND [n, m] AS x" in node_query
    assert "RETURN elementId(n) AS source" in rel_query
    assert node_params == {"exclude_ids": ["a"], "exclude_node_labels": ["Ignore"]}
    assert rel_params == {"exclude_ids": ["a"], "exclude_node_labels": ["Ignore"]}

    db.close()
    assert connection.closed is True
