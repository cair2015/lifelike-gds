import math

from pathway_graphx.network.graph_algorithms import (
    all_shortest_paths_through_any,
    get_all_shortest_paths,
    get_shortest_paths_plus_n,
    remove_inf,
    shortest_paths,
    shortest_through,
)
from pathway_graphx.network.graph_utils import DirectedGraph


def build_demo_graph():
    graph = DirectedGraph()
    graph.add_edges_from(
        [
            ("s1", "a"),
            ("a", "t"),
            ("s1", "b"),
            ("b", "t"),
            ("s1", "c"),
            ("c", "d"),
            ("d", "t"),
            ("root", "mid"),
            ("mid", "leaf"),
            ("through1", "x"),
            ("through2", "x"),
        ]
    )
    graph.set_node_set("sources", {"s1"})
    graph.set_node_set("targets", {"t"})
    graph.set_node_set("through", {"a", "b"})
    return graph


def test_shortest_paths_returns_one_path_per_reachable_pair_and_skips_missing_paths():
    graph = DirectedGraph()
    graph.add_edges_from([("s", "a"), ("a", "t"), ("x", "y")])

    assert list(shortest_paths(graph, {"s", "x"}, {"t"})) == [["s", "a", "t"]]


def test_get_shortest_paths_plus_n_uses_node_set_keys_and_includes_plus_n_paths():
    graph = build_demo_graph()

    shortest_only = get_shortest_paths_plus_n(graph, "sources", "targets", n=0)
    plus_one = get_shortest_paths_plus_n(graph, "sources", "targets", n=1)

    assert {tuple(path) for path in shortest_only} == {
        ("s1", "a", "t"),
        ("s1", "b", "t"),
    }
    assert {tuple(path) for path in plus_one} == {
        ("s1", "a", "t"),
        ("s1", "b", "t"),
        ("s1", "c", "d", "t"),
    }


def test_get_all_shortest_paths_handles_missing_nodes_and_k_shortest_edge_budget():
    graph = build_demo_graph()

    assert get_all_shortest_paths(graph, {"missing"}, {"t"}) == []

    paths = get_all_shortest_paths(graph, {"s1"}, {"t"}, n_edges=3)
    assert {tuple(path) for path in paths} == {
        ("s1", "a", "t"),
        ("s1", "b", "t"),
    }


def test_through_helpers_return_expected_intermediates_and_paths():
    graph = build_demo_graph()

    through_map = shortest_through(graph, {"s1"}, {"a", "b", "c"}, {"t"})
    assert through_map == {"t": {"s1": {"a", "b"}}}

    paths = list(all_shortest_paths_through_any(graph, {"s1"}, {"a", "b"}, {"t"}))
    assert {tuple(path) for path in paths} == {
        ("s1", "a", "t"),
        ("s1", "b", "t"),
    }


def test_remove_inf_returns_copy_without_infinite_weight_edges():
    graph = DirectedGraph()
    graph.add_edge("a", "b", weight=1)
    graph.add_edge("b", "c", weight=math.inf)

    trimmed = remove_inf(graph, weight="weight")

    assert set(graph.edges) == {("a", "b"), ("b", "c")}
    assert set(trimmed.edges) == {("a", "b")}
