from copy import deepcopy

from networkx.readwrite import json_graph

from pathway_graphx.network.graph_utils import DirectedGraph, MultiDirectedGraph
from pathway_graphx.network.trace_utils import (
    add_trace_network,
    get_trace_detail_graphs,
    get_traced_edges,
    get_traced_nodes,
    link_index,
)


def build_trace_graph():
    graph = DirectedGraph(name="demo")
    graph.add_nodes_from(
        [
            ("s", {"label": "source"}),
            ("a", {"label": "mid-a"}),
            ("b", {"label": "mid-b"}),
            ("t", {"label": "target"}),
        ]
    )
    graph.add_edges_from([("s", "a"), ("a", "t"), ("s", "b"), ("b", "t")])
    graph.set_node_set("sources", {"s"}, name="Sources", description="input nodes")
    graph.set_node_set("targets", {"t"}, name="Targets", description="output nodes")
    return graph


def test_add_trace_network_registers_trace_metadata_and_paths():
    graph = build_trace_graph()

    trace_index, n_paths = add_trace_network(
        graph,
        "sources",
        "targets",
        name="shortest demo",
        shortest_paths_plus_n=0,
    )

    assert trace_index == 0
    assert n_paths == 2
    trace_network = graph.graph["trace_networks"][0]
    assert trace_network["sources"] == "sources"
    assert trace_network["targets"] == "targets"
    assert trace_network["query"] == "sources"
    assert trace_network["method"] == "min(length)"
    assert trace_network["name"] == "shortest demo"
    assert "Shortest paths starting at input nodes" in trace_network["description"]
    assert len(trace_network["traces"]) == 1
    trace = trace_network["traces"][0]
    assert trace["source"] == "s"
    assert trace["target"] == "t"
    assert {tuple(path) for path in trace["node_paths"]} == {
        ("s", "a", "t"),
        ("s", "b", "t"),
    }
    assert trace["edges"] == {("s", "a"), ("a", "t"), ("s", "b"), ("b", "t")}


def test_traced_nodes_edges_and_detail_graphs_are_collected_from_trace_networks():
    graph = build_trace_graph()
    graph.graph["description"] = "graph description"
    graph.graph["trace_networks"] = [
        {
            "description": "network description",
            "traces": [
                {
                    "source": "s",
                    "target": "t",
                    "description": "trace description",
                    "node_paths": [["s", "a", "t"]],
                    "edges": {("s", "a"), ("a", "t")},
                    "detail_edges": [("s", "a", {"kind": "detail"}), ("a", "t", {"kind": "detail"})],
                }
            ],
        }
    ]

    assert get_traced_edges(graph) == {("s", "a"), ("a", "t")}
    assert get_traced_nodes(graph) == {"s", "a", "t"}

    detail_graphs = get_trace_detail_graphs(graph)
    detail_graph = detail_graphs[("s", "t")]
    assert set(detail_graph.nodes) == {"s", "a", "t"}
    assert set(detail_graph.edges) == {("s", "a"), ("a", "t")}
    assert detail_graph.graph["node_sets"]["source"] == {"s"}
    assert detail_graph.graph["node_sets"]["target"] == {"t"}
    assert "graph description" in detail_graph.graph["description"]


def test_link_index_rewrites_trace_edges_to_link_indexes_for_simple_graphs():
    graph = build_trace_graph()
    graph.graph["trace_networks"] = [
        {"traces": [{"edges": {("s", "a"), ("a", "t")}}]}
    ]

    data = json_graph.node_link_data(graph)
    expected = {
        index
        for index, edge in enumerate(data["edges"])
        if (edge["source"], edge["target"]) in {("s", "a"), ("a", "t")}
    }
    link_index(data)

    assert set(data["graph"]["trace_networks"][0]["traces"][0]["edges"]) == expected


def test_link_index_rewrites_multigraph_edges_and_drops_key_field():
    graph = MultiDirectedGraph()
    graph.add_edge("s", "t", key="k1", weight=1)
    graph.add_edge("s", "t", key="k2", weight=2)
    graph.graph["trace_networks"] = [
        {"traces": [{"edges": {("s", "t", "k2")}}]}
    ]

    data = deepcopy(json_graph.node_link_data(graph))
    link_index(data)

    assert data["graph"]["trace_networks"][0]["traces"][0]["edges"] == [1]
    assert all("key" not in link for link in data["edges"])
