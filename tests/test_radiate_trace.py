import pandas as pd

from pathway_graphx.network.graph_source import GraphSource
from pathway_graphx.network.radiate_trace import RadiateTrace


class FakeDatabase:
    def __init__(self):
        self.frames = {
            "nodes": pd.DataFrame({"node_id": [1, 2, 3, 4]}),
            "rels": pd.DataFrame(
                {
                    "source": [1, 2, 1, 4],
                    "target": [2, 3, 4, 3],
                    "type": ["A", "B", "C", "D"],
                }
            ),
        }
        self.node_records = {
            1: {"id": 1, "displayName": "Source 1"},
            2: {"id": 2, "displayName": "Mid 2"},
            3: {"id": 3, "displayName": "Target 3"},
            4: {"id": 4, "displayName": "Mid 4"},
        }

    def get_dataframe(self, query, **parameters):
        return self.frames[query].copy()

    def get_nodes_by_node_ids(self, node_ids):
        return [self.node_records[node_id] for node_id in node_ids if node_id in self.node_records]


class FakeGraphSource(GraphSource):
    @classmethod
    def get_node_name(cls, node):
        return node.get("displayName")

    @classmethod
    def get_node_desc(cls, node):
        return node.get("displayName")

    def set_nodes_description(self, nodes, graph):
        for node in nodes:
            graph.nodes[node["id"]]["description"] = node["displayName"]

    def set_edges_description(self, edges, graph):
        return None

    @classmethod
    def set_edge_description(cls, graph, start_node, end_node, edge_type, key=None):
        return None

    def initiate_trace_graph(self, tracegraph, **kwargs):
        tracegraph.add_nodes("nodes")
        tracegraph.add_rels("rels")

    def load_graph_to_tracegraph(self, tracegraph, exclude_nodes=None, exclude_node_labels=None):
        self.initiate_trace_graph(tracegraph)

    def get_node_data_for_excel(self, node_ids):
        return pd.DataFrame(
            [self.database.node_records[node_id] for node_id in node_ids]
        )


def build_tracer():
    tracer = RadiateTrace(FakeGraphSource(FakeDatabase()), multigraph=False)
    tracer.init_default_graph()
    tracer.graph.set_node_set("sources", {1}, name="Sources", description="source set")
    tracer.graph.set_node_set("targets", {3}, name="Targets", description="target set")
    return tracer


def test_set_pagerank_and_numreach_adds_expected_properties():
    tracer = build_tracer()

    has_in, has_out = tracer.set_pagerank_and_numreach("sources", direction="both")

    assert has_in is False
    assert has_out is True
    pagerank = tracer.graph.getd("pagerank")
    assert set(pagerank) == {1, 2, 3, 4}
    assert tracer.graph.getd("nReach")[3] == 1


def test_set_pagerank_and_export_pagerank_data_creates_excel_file(tmp_path):
    tracer = build_tracer()
    tracer.set_datadir(str(tmp_path))

    tracer.set_pagerank("sources", "custom_pr")
    assert set(tracer.graph.getd("custom_pr")) == {1, 2, 3, 4}

    tracer.export_pagerank_data("sources", "pagerank.xlsx", num_nodes=2)

    assert (tmp_path / "pagerank.xlsx").exists()


def test_trace_building_helpers_add_trace_networks_and_descriptions():
    tracer = build_tracer()
    tracer.set_pagerank_and_numreach("sources", direction="forward")
    selected_nodes = [
        tracer.graphsource.database.node_records[3],
        tracer.graphsource.database.node_records[4],
    ]

    tracer.add_traces_from_sources_to_each_selected_nodes(
        selected_nodes,
        "sources",
        selected_nodes_name="selected",
    )
    tracer.add_trace_from_sources_to_all_selected_nodes("targets", "sources")

    assert len(tracer.graph.graph["trace_networks"]) >= 3
    assert "Traces from sources to each of the 2 selected nodes" in tracer.graph.graph["description"]
    assert "Traces from sources to all targets" in tracer.graph.graph["description"]


def test_intersection_pagerank_export_creates_excel_file(tmp_path):
    tracer = build_tracer()
    tracer.set_datadir(str(tmp_path))

    tracer.export_intersection_pageranks(
        "intersection.xlsx",
        "sources",
        "targets",
        num_nodes=2,
    )

    assert (tmp_path / "intersection.xlsx").exists()
