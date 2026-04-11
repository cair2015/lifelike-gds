import pandas as pd

from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.network.shortest_paths_trace import (
    InteractionPathTrace,
    ShortestPathTrace,
)


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


def build_tracer(cls=ShortestPathTrace):
    tracer = cls(FakeGraphSource(FakeDatabase()), multigraph=False)
    tracer.init_default_graph()
    tracer.graph.set_node_set("sources", {1}, name="Sources", description="source set")
    tracer.graph.set_node_set("targets", {3}, name="Targets", description="target set")
    return tracer


def test_add_shortest_paths_creates_trace_networks_and_descriptions():
    tracer = build_tracer()

    added = tracer.add_shortest_paths("sources", "targets", shortest_paths_plus_n=1)

    assert added is True
    assert len(tracer.graph.graph["trace_networks"]) == 2
    names = [tn["name"] for tn in tracer.graph.graph["trace_networks"]]
    assert names == [
        "Shortest paths from Sources to Targets",
        "Shortest+1 paths from Sources to Targets",
    ]
    assert tracer.graph.graph["trace_networks"][0]["query"] == "sources"
    assert "Shortest paths from Sources to Targets: 2 paths" in tracer.graph.graph["description"]


def test_add_shortest_paths_can_flip_query_side():
    tracer = build_tracer()

    tracer.add_shortest_paths("sources", "targets", sources_as_query=False)

    assert tracer.graph.graph["trace_networks"][0]["query"] == "targets"


def test_k_all_and_weighted_shortest_path_methods_fall_back_to_shortest_paths():
    tracer = build_tracer()

    assert tracer.add_k_shortest_paths("sources", "targets", k=3) is True
    assert tracer.graph.graph["trace_networks"][0]["name"] == (
        "K-shortest paths (k=3) from Sources to Targets"
    )

    tracer = build_tracer()
    assert tracer.add_all_shortest_paths("sources", "targets", max_length=7) is True
    assert tracer.graph.graph["trace_networks"][0]["name"] == (
        "All shortest paths from Sources to Targets"
    )

    tracer = build_tracer()
    assert tracer.add_weighted_shortest_paths("sources", "targets", "weight") is True
    assert tracer.graph.graph["trace_networks"][0]["name"] == (
        "Weighted shortest paths from Sources to Targets"
    )


def test_interaction_path_trace_is_shortest_path_trace_subclass():
    tracer = build_tracer(InteractionPathTrace)

    assert isinstance(tracer, ShortestPathTrace)
    assert tracer.add_shortest_paths("sources", "targets") is True
