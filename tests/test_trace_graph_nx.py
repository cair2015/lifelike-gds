import json

import pandas as pd

from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.network.trace_graph_nx import TraceGraphNx


class FakeDatabase:
    def __init__(self):
        self.frames = {
            "nodes": pd.DataFrame({"node_id": [1, 2, 3, 4]}),
            "rels": pd.DataFrame(
                {
                    "source": [1, 2, 3],
                    "target": [2, 3, 4],
                    "type": ["A", "B", "C"],
                }
            ),
        }
        self.node_records = {
            1: {"id": 1, "displayName": "one", "kind": "gene"},
            2: {"id": 2, "displayName": "two", "kind": "protein"},
            3: {"id": 3, "displayName": "three", "kind": "protein"},
            4: {"id": 4, "displayName": "four", "kind": "metabolite"},
        }

    def get_dataframe(self, query, **parameters):
        return self.frames[query].copy()

    def get_nodes_by_node_ids(self, node_ids, node_label=None):
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
        for edge in edges:
            ref = (self.get_node_id(edge["start_node"]), self.get_node_id(edge["end_node"]))
            if edge["key"] is None:
                graph.edges[ref]["description"] = edge["type"]
            else:
                graph.edges[ref + (edge["key"],)]["description"] = edge["type"]

    @classmethod
    def set_edge_description(cls, graph, start_node, end_node, edge_type, key=None):
        ref = (start_node, end_node) if key is None else (start_node, end_node, key)
        graph.edges[ref]["description"] = edge_type

    def initiate_trace_graph(self, tracegraph, **kwargs):
        tracegraph.add_nodes_from_rows(self.database.get_dataframe("nodes"))
        tracegraph.add_relationship_rows(self.database.get_dataframe("rels"))

    def get_node_data_for_excel(self, node_ids, node_label=None):
        return pd.DataFrame(
            [self.database.node_records[node_id] for node_id in node_ids]
        )


def build_trace_graph():
    source = FakeGraphSource(FakeDatabase())
    tracegraph = TraceGraphNx(source, multigraph=False)
    tracegraph.init_default_graph()
    return tracegraph


def test_init_default_graph_and_node_set_helpers_populate_graph():
    tracegraph = build_trace_graph()

    assert set(tracegraph.graph.nodes) == {1, 2, 3, 4}
    assert set(tracegraph.graph.edges) == {(1, 2), (2, 3), (3, 4)}

    tracegraph.set_node_set_from_db_nodes(
        [tracegraph.graphsource.database.node_records[1], tracegraph.graphsource.database.node_records[3]],
        "selected",
        "chosen nodes",
    )
    key = tracegraph.set_node_set_for_node(tracegraph.graphsource.database.node_records[2])

    assert tracegraph.graph.node_set("selected") == {1, 3}
    assert tracegraph.graph.node_set(key) == {2}
    assert tracegraph.graph.get_node_set_name(key) == "two"


def test_load_node_details_and_export_dataframe_include_graph_attributes():
    tracegraph = build_trace_graph()
    tracegraph.load_node_detail_from_db([1, 2])
    tracegraph.graph.set({1}, score=10, default=0)

    df = tracegraph.get_nodes_detail_as_dataframe([1, 2])

    assert tracegraph.graph.nodes[1]["description"] == "one"
    assert tracegraph.graph.nodes[1]["label"] == "one"
    assert set(df["id"]) == {1, 2}
    assert df.set_index("id").loc[1, "score"] == 10


def test_weight_helpers_and_clean_graph_keep_trace_and_nodeset_nodes():
    tracegraph = build_trace_graph()
    tracegraph.graph.set(score={1: 3, 2: 5, 3: 5, 4: 1})
    tracegraph.graph.set_node_set("keep", {4}, name="keep")
    tracegraph.graph.graph["trace_networks"] = [
        {
            "sources": "s",
            "targets": "t",
            "query": "s",
            "traces": [
                {
                    "source": 1,
                    "target": 3,
                    "node_paths": [[1, 2, 3]],
                    "edges": {(1, 2), (2, 3)},
                }
            ]
        }
    ]

    assert set(tracegraph.get_most_weighted_nodes("score", 1)) == {2, 3}
    assert tracegraph.get_least_weighted_nodes("score", 1) == [4]

    tracegraph.clean_graph()

    assert set(tracegraph.graph.nodes) == {1, 2, 3, 4}
    assert "group" in tracegraph.graph.graph["trace_networks"][0]["traces"][0]


def test_sankey_and_cytoscape_exports_write_json_files(tmp_path):
    tracegraph = build_trace_graph()
    tracegraph.graph.graph["trace_networks"] = [
        {
            "sources": "s",
            "targets": "t",
            "query": "s",
            "traces": [{"edges": {(1, 2)}, "node_paths": [[1, 2]], "source": 1, "target": 2}],
        }
    ]

    sankey = tmp_path / "graph.json"
    cyto = tmp_path / "graph_cyto.json"
    tracegraph.write_to_sankey_file(sankey)
    tracegraph.write_to_cytoscape_file(cyto)

    sankey_data = json.loads(sankey.read_text())
    cyto_data = json.loads(cyto.read_text())

    assert sankey.exists()
    assert cyto.exists()
    assert "graph" in sankey_data and "trace_networks" in sankey_data["graph"]
    assert "elements" in cyto_data
