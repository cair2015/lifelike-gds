import networkx as nx
import pandas as pd

from pathway_graphx.graph_sources.reactome import Reactome
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
            pd.DataFrame([{"node_id": "n1"}, {"node_id": "n2"}]),
            pd.DataFrame([{"source": "n1", "target": "n2", "type": "input"}]),
        )

    def get_summation_data(self, nodes):
        return {node["id"]: f"summary for {node['id']}" for node in nodes}

    def get_gene_names(self, nodes):
        return {node["id"]: [f"gene-{node['id']}"] for node in nodes}

    def get_node_data_for_excel(self, node_ids):
        self.excel_calls.append(node_ids)
        return pd.DataFrame([{"id": node_ids[0], "displayName": "ATP"}])


def test_reactome_display_name_and_entity_helpers():
    assert Reactome.split_display_name("ATP [cytosol]") == ("ATP", "cytosol")
    assert Reactome.split_display_name("ATP") == ("ATP", "")

    node = {"displayName": "ATP [cytosol]", "entityType": "Chemical"}
    assert Reactome.get_node_name(node) == "ATP"
    assert Reactome.get_node_desc(node) == "Chemical ATP [cytosol]"
    assert Reactome.get_node_entity_type(node) == "Chemical"
    assert Reactome.get_node_entity_type({"entityType": "UnsupportedThing"}) == "Entity"


def test_reactome_loads_projection_into_trace_graph():
    database = FakeDatabase()
    graphsource = Reactome(database)
    tracegraph = TraceGraphNx(graphsource)

    graphsource.initiate_trace_graph(tracegraph, exclude_node_labels=["CurrencyMetabolite"])
    graphsource.load_graph_to_tracegraph(tracegraph, exclude_nodes=["n9"], exclude_node_labels=["Ignore"])

    assert set(tracegraph.graph.nodes) == {"n1", "n2"}
    assert tracegraph.graph.number_of_edges() == 2
    assert database.trace_calls == [
        {"exclude_nodes": None, "exclude_node_labels": ["CurrencyMetabolite"]},
        {"exclude_nodes": ["n9"], "exclude_node_labels": ["Ignore"]},
    ]


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
    assert database.excel_calls == [["n1"]]
