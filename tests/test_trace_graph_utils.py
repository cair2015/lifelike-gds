from copy import deepcopy
import json

import networkx as nx
from networkx.readwrite import json_graph

from pathway_graphx.network.trace_graph_utils import (
    add_pagerank,
    get_node_set_nodes,
    k_shortest_paths,
    link_index,
    pagerank_influence,
    set_intersection_pagerank,
    set_nReach,
    write_cytoscape_file,
)
from pathway_graphx.network.graph_utils import DirectedGraph, MultiDirectedGraph


def build_graph():
    graph = DirectedGraph()
    graph.add_edges_from(
        [
            ("s1", "a"),
            ("s2", "a"),
            ("a", "t"),
            ("s1", "b"),
            ("b", "t"),
            ("s2", "c"),
        ]
    )
    graph.set_node_set("sources", {"s1", "s2"}, name="sources")
    graph.set_node_set("targets", {"t"}, name="targets")
    return graph


def test_link_index_supports_current_node_link_edge_key_for_simple_and_multi_graphs():
    graph = build_graph()
    graph.graph["trace_networks"] = [{"traces": [{"edges": {("s1", "a"), ("a", "t")}}]}]
    data = json_graph.node_link_data(graph)
    expected = {
        i for i, edge in enumerate(data["edges"]) if (edge["source"], edge["target"]) in {("s1", "a"), ("a", "t")}
    }

    link_index(data)

    assert set(data["graph"]["trace_networks"][0]["traces"][0]["edges"]) == expected

    multi = MultiDirectedGraph()
    multi.add_edge("x", "y", key="k1")
    multi.add_edge("x", "y", key="k2")
    multi.graph["trace_networks"] = [{"traces": [{"edges": {("x", "y", "k2")}}]}]
    multi_data = deepcopy(json_graph.node_link_data(multi))

    link_index(multi_data)

    assert multi_data["graph"]["trace_networks"][0]["traces"][0]["edges"] == [1]
    assert all("key" not in edge for edge in multi_data["edges"])


def test_pagerank_helpers_add_expected_node_properties():
    graph = build_graph()

    df = pagerank_influence(graph, "sources")
    assert set(df.columns) == {"node", "pagerank", "nstart"}
    assert set(df["node"]) == set(graph.nodes)

    add_pagerank(graph, "sources", pagerank_prop="pr")
    assert set(graph.getd("pr")) == set(graph.nodes)
    assert graph.getd("start_val") == {"s1": 1, "s2": 1}

    nx.set_node_attributes(graph, {"a": 0.5, "b": 0.2}, "source_pr")
    nx.set_node_attributes(graph, {"a": 0.4, "b": 0.8}, "target_rev_pr")
    set_intersection_pagerank(graph, "source_pr", "target_rev_pr", "inter")
    inter = graph.getd("inter")
    assert set(inter) == {"a", "b"}
    assert inter["a"] > 0 and inter["b"] > 0


def test_set_nreach_and_get_node_set_nodes_cover_named_sets():
    graph = build_graph()

    set_nReach(graph, "sources")
    set_nReach(graph, "targets", reverse=True)

    assert graph.getd("nReach")["a"] == 2
    assert graph.getd("nReach")["t"] == 2
    assert graph.getd("rev_nReach")["a"] == 1
    assert get_node_set_nodes(graph) == {"s1", "s2", "t"}


def test_k_shortest_paths_and_cytoscape_export_work(tmp_path):
    graph = build_graph()

    paths = k_shortest_paths(graph, "s1", "t", k=2)
    assert paths == [["s1", "a", "t"], ["s1", "b", "t"]]

    out = tmp_path / "cyto.json"
    write_cytoscape_file(str(out), graph)
    assert out.exists()
    data = json.loads(out.read_text())
    assert "elements" in data
    assert len(data["elements"]["nodes"]) == len(graph.nodes)
