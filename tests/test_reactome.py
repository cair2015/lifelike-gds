import networkx as nx
import pandas as pd

from lifelike_gds.graph_sources.domain_config import REACTOME_TRACE_RELATIONSHIP_TYPES
from lifelike_gds.graph_sources.reactome import Reactome
from lifelike_gds.network.trace_graph_nx import TraceGraphNx


class FakeDatabase:
    def __init__(self):
        self.query_calls = []
        self.excel_calls = []

    def get_query_values(self, query, **kwargs):
        self.query_calls.append({"query": query, "params": kwargs})
        return [
            {"source": "n1", "target": "n2", "relationship_type": "input", "relationship_id": "r1"},
        ]

    def get_summation_data(self, nodes, node_label=None):
        return {node["id"]: f"summary for {node['id']}" for node in nodes}

    def get_gene_names(self, nodes, node_label=None):
        return {node["id"]: [f"gene-{node['id']}"] for node in nodes}

    def get_node_data_for_excel(self, node_ids, node_label=None):
        self.excel_calls.append({"node_ids": node_ids, "node_label": node_label})
        return pd.DataFrame([{"id": node_ids[0], "displayName": "ATP"}])


def test_reactome_display_name_and_entity_helpers():
    assert Reactome.split_display_name("ATP [cytosol]") == ("ATP", "cytosol")
    assert Reactome.split_display_name("ATP") == ("ATP", "")

    node = {"displayName": "ATP [cytosol]", "entityType": "Chemical"}
    assert Reactome.get_node_name(node) == "ATP"
    assert Reactome.get_node_desc(node) == "Chemical ATP [cytosol]"


def test_reactome_loads_projection_into_trace_graph():
    database = FakeDatabase()
    graphsource = Reactome(database)
    tracegraph = TraceGraphNx(graphsource)

    graphsource.initiate_trace_graph(tracegraph, exclude_node_labels=["CurrencyMetabolite"])
    graphsource.load_graph_to_tracegraph(tracegraph, exclude_nodes=["n9"], exclude_node_labels=["Ignore"])

    assert set(tracegraph.graph.nodes) == {"n1", "n2"}
    assert tracegraph.graph.number_of_edges() == 2
    assert len(database.query_calls) == 2
    assert database.query_calls[0]["params"] == {"rel_types": list(REACTOME_TRACE_RELATIONSHIP_TYPES)}
    assert database.query_calls[1]["params"] == {"rel_types": list(REACTOME_TRACE_RELATIONSHIP_TYPES)}
    assert "NOT a:CurrencyMetabolite AND NOT b:CurrencyMetabolite" in database.query_calls[0]["query"]
    assert "NOT a:Ignore AND NOT b:Ignore" in database.query_calls[1]["query"]


def test_reactome_sets_node_and_edge_descriptions():
    database = FakeDatabase()
    graphsource = Reactome(database)
    graph = nx.MultiDiGraph()
    graph.add_node(
        "n1",
        displayName="ATP [cytosol]",
        entityType="Chemical",
    )
    graph.add_node(
        "n2",
        displayName="Reaction A [cytosol]",
        entityType="Reaction",
    )
    graph.add_edge("n1", "n2", key="k1", label="input")

    graphsource.set_nodes_description(
        [
            {
                "id": "n1",
                "entityType": "Chemical",
                "synonyms": ["Adenosine triphosphate"],
            },
            {
                "id": "n2",
                "entityType": "Reaction",
                "synonyms": [],
            },
        ],
        graph,
    )
    assert "NODE: Chemical" in graph.nodes["n1"]["description"]
    assert "Adenosine triphosphate" in graph.nodes["n1"]["description"]
    assert "SUMMATION:" in graph.nodes["n1"]["description"]

    graphsource.set_edges_description(
        [
            {
                "start_node": {"id": "n1", "entityType": "Chemical", "displayName": "ATP [cytosol]"},
                "end_node": {"id": "n2", "entityType": "Reaction", "displayName": "Reaction A [cytosol]"},
                "type": "input",
                "key": "k1",
            }
        ],
        graph,
    )
    assert "RELATIONSHIP: input" in graph.edges[("n1", "n2", "k1")]["description"]
    assert "Chemical(ATP) | input | Reaction(Reaction A)" in graph.edges[("n1", "n2", "k1")]["description"]


def test_reactome_excel_passthrough():
    database = FakeDatabase()
    graphsource = Reactome(database)

    frame = graphsource.get_node_data_for_excel(["n1"])
    assert frame.to_dict(orient="records") == [{"id": "n1", "displayName": "ATP"}]
    assert database.excel_calls == [{"node_ids": ["n1"], "node_label": graphsource.node_label}]
