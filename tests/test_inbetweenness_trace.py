import pandas as pd

from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.network.inbetweenness_trace import InBetweennessTrace


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
    tracer = InBetweennessTrace(FakeGraphSource(FakeDatabase()), multigraph=False)
    tracer.init_default_graph()
    tracer.graph.set_node_set("sources", {1}, name="Sources", description="source set")
    tracer.graph.set_node_set("targets", {3}, name="Targets", description="target set")
    return tracer


def test_compute_inbetweenness_sets_raw_and_scaled_properties():
    tracer = build_tracer()

    tracer.compute_inbetweenness("sources", "targets")

    prop = tracer.get_betweenness_prop_name("sources", "targets")
    values = tracer.graph.getd(prop)
    scaled = tracer.graph.getd(prop + "_scaled")
    assert values[2] == 0.5
    assert values[4] == 0.5
    assert scaled[2] == 1 / 6
    assert scaled[4] == 1 / 6


def test_compute_inbetweenness_with_pagerank_weight_uses_updated_helper_signature():
    tracer = build_tracer()
    tracer.graph.set(pagerank={1: 1.0, 2: 10.0, 3: 1.0, 4: 1.0})

    tracer.compute_inbetweenness("sources", "targets", pagerank_prop="pagerank")

    prop = tracer.get_betweenness_prop_name("sources", "targets")
    values = tracer.graph.getd(prop)
    assert values[2] > 0
    assert 4 not in values
    assert all("edge_wt" not in data for _, _, data in tracer.graph.edges(data=True))


def test_export_and_trace_building_helpers_create_outputs_and_trace_networks(tmp_path):
    tracer = build_tracer()
    tracer.set_datadir(str(tmp_path))
    tracer.compute_inbetweenness("sources", "targets")

    tracer.export_inbetweenness_data("sources", "targets", "betweenness.xlsx")
    tracer.add_inbetweenness_trace_networks_with_selected_nodes(
        "targets",
        "sources",
        "targets",
        shortest_paths_plus_n=0,
    )

    assert (tmp_path / "betweenness.xlsx").exists()
    assert len(tracer.graph.graph["trace_networks"]) == 4


def test_add_best_n_inbetweenness_nodes_to_trace_networks_uses_existing_wrapper():
    tracer = build_tracer()

    tracer.add_best_n_inbetweenness_nodes_to_trace_networks(
        "sources",
        "targets",
        num=1,
        do_compute=True,
    )

    assert len(tracer.graph.graph["trace_networks"]) == 4
    assert "Traces from sources to top 1 betweenness nodes;" in tracer.graph.graph["description"]
