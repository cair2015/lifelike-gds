import networkx as nx
import pandas as pd

from pathway_graphx.graph_sources.biocyc import Biocyc
from pathway_graphx.network.trace_graph_nx import TraceGraphNx


class FakeDatabase:
    def __init__(self):
        self.trace_calls = []
        self.excel_calls = []

    def get_trace_graph_data(self, exclude_nodes=None, exclude_node_labels=None):
        self.trace_calls.append(
            {
                "exclude_nodes": exclude_nodes,
                "exclude_node_labels": exclude_node_labels,
            }
        )
        return (
            pd.DataFrame([{"node_id": "b1"}, {"node_id": "b2"}]),
            pd.DataFrame([{"source": "b1", "target": "b2", "type": "PRODUCES"}]),
        )

    def get_node_data_for_excel(self, node_ids):
        self.excel_calls.append(node_ids)
        return pd.DataFrame([{"id": node_ids[0], "displayName": "ATP"}])


def test_biocyc_node_name_and_description_helpers():
    node = {"displayName": "ATP", "entityType": "Compound"}
    assert Biocyc.get_node_name(node) == "ATP"
    assert Biocyc.get_node_desc(node) == "Compound ATP"
    assert Biocyc.get_node_name({"name": "Adenosine triphosphate"}) == "Adenosine triphosphate"


def test_biocyc_loads_projection_into_trace_graph():
    database = FakeDatabase()
    graphsource = Biocyc(database)
    tracegraph = TraceGraphNx(graphsource)

    graphsource.initiate_trace_graph(tracegraph, exclude_node_labels=["CurrencyMetabolite"])
    graphsource.load_graph_to_tracegraph(tracegraph, exclude_nodes=["b9"], exclude_node_labels=["Ignore"])

    assert set(tracegraph.graph.nodes) == {"b1", "b2"}
    assert tracegraph.graph.number_of_edges() == 2
    assert database.trace_calls == [
        {"exclude_nodes": None, "exclude_node_labels": ["CurrencyMetabolite"]},
        {"exclude_nodes": ["b9"], "exclude_node_labels": ["Ignore"]},
    ]


def test_biocyc_sets_node_and_edge_descriptions():
    database = FakeDatabase()
    graphsource = Biocyc(database)
    graph = nx.MultiDiGraph()
    graph.add_node("b1", displayName="ATP", entityType="Compound")
    graph.add_node("b2", displayName="Reaction A", entityType="Reaction")
    graph.add_edge("b1", "b2", key="k1", label="PRODUCES")

    graphsource.set_nodes_description(
        [
            {
                "id": "b1",
                "entityType": "Compound",
                "synonyms": ["Adenosine triphosphate"],
                "detail": "Energy carrier",
            },
            {
                "id": "b2",
                "entityType": "Reaction",
                "synonyms": [],
            },
        ],
        graph,
    )
    assert "NODE: Compound" in graph.nodes["b1"]["description"]
    assert "Adenosine triphosphate" in graph.nodes["b1"]["description"]
    assert "DETAIL:" in graph.nodes["b1"]["description"]
    assert "Energy carrier" in graph.nodes["b1"]["description"]

    graphsource.set_edges_description(
        [
            {
                "start_node": {"id": "b1", "entityType": "Compound", "displayName": "ATP"},
                "end_node": {"id": "b2", "entityType": "Reaction", "displayName": "Reaction A"},
                "type": "PRODUCES",
                "key": "k1",
            }
        ],
        graph,
    )
    assert "RELATIONSHIP: PRODUCES" in graph.edges[("b1", "b2", "k1")]["description"]
    assert "Compound(ATP) | PRODUCES | Reaction(Reaction A)" in graph.edges[("b1", "b2", "k1")]["description"]


def test_biocyc_excel_passthrough():
    database = FakeDatabase()
    graphsource = Biocyc(database)

    frame = graphsource.get_node_data_for_excel(["b1"])
    assert frame.to_dict(orient="records") == [{"id": "b1", "displayName": "ATP"}]
    assert database.excel_calls == [["b1"]]
