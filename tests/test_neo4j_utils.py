import pandas as pd
import pytest

from pathway_graphx.graph_sources.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder


class FakeSession:
    def __init__(self, rows, calls, database):
        self.rows = rows
        self.calls = calls
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def run(self, query, parameters):
        self.calls.append((self.database, query, parameters))
        return self.rows


class FakeDriver:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        self.closed = False
        self.verified = False

    def verify_connectivity(self):
        self.verified = True

    def session(self, database):
        return FakeSession(self.rows, self.calls, database)

    def close(self):
        self.closed = True


def test_neo4j_connection_uses_driver_and_returns_records(monkeypatch):
    rows = [{"value": 1}, {"value": 2}]
    captured = {}

    def fake_driver(uri, auth, **kwargs):
        captured["uri"] = uri
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        driver = FakeDriver(rows)
        captured["driver"] = driver
        return driver

    monkeypatch.setattr("pathway_graphx.graph_sources.neo4j_utils.GraphDatabase.driver", fake_driver)

    connection = Neo4jConnection(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="secret",
        database="testdb",
        encrypted=True,
    )

    records = connection.get_records("RETURN 1 AS value", {"a": 1})
    assert records == rows
    assert captured["uri"] == "bolt://localhost:7687"
    assert captured["auth"] == ("neo4j", "secret")
    assert captured["kwargs"]["encrypted"] is True
    assert "trust" in captured["kwargs"]
    assert captured["driver"].verified is True
    assert captured["driver"].calls == [("testdb", "RETURN 1 AS value", {"a": 1})]

    connection.close()
    assert captured["driver"].closed is True


def test_neo4j_connection_dataframe_and_single_value(monkeypatch):
    rows = [{"value": 7, "name": "alpha"}]
    monkeypatch.setattr(
        "pathway_graphx.graph_sources.neo4j_utils.GraphDatabase.driver",
        lambda *args, **kwargs: FakeDriver(rows),
    )

    connection = Neo4jConnection("bolt://db", "u", "p")

    frame = connection.get_dataframe("RETURN 7 AS value, 'alpha' AS name")
    assert isinstance(frame, pd.DataFrame)
    assert frame.to_dict(orient="records") == rows
    assert connection.get_single_value("RETURN 7 AS value") == 7
    assert connection.get_single_record("RETURN 7 AS value, 'alpha' AS name") == rows[0]


def test_neo4j_connection_single_value_raises_for_empty_results(monkeypatch):
    monkeypatch.setattr(
        "pathway_graphx.graph_sources.neo4j_utils.GraphDatabase.driver",
        lambda *args, **kwargs: FakeDriver([]),
    )
    connection = Neo4jConnection("bolt://db", "u", "p")

    with pytest.raises(ValueError, match="No records returned"):
        connection.get_single_value("RETURN 1")

    with pytest.raises(ValueError, match="No records returned"):
        connection.get_single_record("RETURN 1")


def test_query_builder_generates_expected_cypher_fragments():
    query, params = Neo4jQueryBuilder.get_nodes_by_ids(["1", "2"], "Reactome")
    assert "MATCH (n:Reactome)" in query
    assert "elementId(n) IN $node_ids" in query
    assert params == {"node_ids": ["1", "2"]}

    query, params = Neo4jQueryBuilder.get_nodes_by_property("displayName", ["A"], "BioCyc")
    assert "MATCH (n:BioCyc)" in query
    assert "n.displayName IN $values" in query
    assert params == {"values": ["A"]}

    query, params = Neo4jQueryBuilder.get_relationships_between_nodes(
        ["s1"], ["t1"], ["INPUT", "OUTPUT"]
    )
    assert "MATCH (s)-[r:INPUT|OUTPUT]->(t)" in query
    assert params == {"source_ids": ["s1"], "target_ids": ["t1"]}

    query, _ = Neo4jQueryBuilder.get_shortest_paths(["s1"], ["t1"], ["INPUT"], max_depth=3)
    assert "shortestPath((s)-[:INPUT*1..3]->(t))" in query

    query, _ = Neo4jQueryBuilder.get_all_shortest_paths(["s1"], ["t1"])
    assert "allShortestPaths((s)-[*]->(t))" in query

    query, params = Neo4jQueryBuilder.get_currency_nodes("BioCyc")
    assert "MATCH (n:BioCyc)" in query
    assert "'CurrencyMetabolite' IN labels(n)" in query
    assert params == {}

    assert Neo4jQueryBuilder.extract_nodes_from_paths("path") == (
        "UNWIND nodes(path) as node RETURN DISTINCT node"
    )
    assert "relationships(path)" in Neo4jQueryBuilder.extract_relationships_from_paths("path")
