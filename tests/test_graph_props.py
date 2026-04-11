import networkx as nx

from lifelike_gds.network.graph_props import (
    from_multi_edge,
    from_multi_edges,
    get_edge_prop_dict,
    get_edges_by_prop,
    get_nodes_by_prop,
    get_node_prop_dict,
    outgoing_inherit,
    set_edge_props,
    set_node_props,
)


def test_get_nodes_by_prop_supports_scalar_iterable_and_case_insensitive_matching():
    graph = nx.DiGraph()
    graph.add_node("a", kind="Gene", aliases=["ALPHA", "BETA"], score=4)
    graph.add_node("b", kind="protein", aliases=["gamma"], score=2)
    graph.add_node("c", score=8)

    assert get_nodes_by_prop(graph, kind="Gene") == {"a"}
    assert get_nodes_by_prop(graph, aliases={"BETA"}) == {"a"}
    assert get_nodes_by_prop(graph, insensitive=True, kind="PROTEIN") == {"b"}
    assert get_nodes_by_prop(graph, score=lambda value: value >= 4) == {"a", "c"}


def test_get_edges_by_prop_combines_value_and_callable_filters():
    graph = nx.DiGraph()
    graph.add_edge("a", "b", relation="activates", weight=2)
    graph.add_edge("b", "c", relation="inhibits", weight=1)
    graph.add_edge("c", "d", relation="activates", weight=5)

    assert get_edges_by_prop(graph, relation="activates") == {("a", "b"), ("c", "d")}
    assert get_edges_by_prop(graph, weight=lambda value: value > 1) == {
        ("a", "b"),
        ("c", "d"),
    }
    assert get_edges_by_prop(
        graph, relation="activates", weight=lambda value: value > 2
    ) == {("c", "d")}


def test_set_node_props_assigns_defaults_scalars_and_function_values():
    graph = nx.DiGraph()
    graph.add_nodes_from(["a", "b", "c"])
    graph.nodes["a"]["score"] = 1
    graph.nodes["b"]["score"] = 4

    set_node_props(graph, {"a", "b"}, default=0, category={"a": "source"}, label="x")
    set_node_props(graph, doubled=lambda data: data["score"] * 2, default=-1)

    assert get_node_prop_dict(graph, "category") == {"a": "source", "b": 0}
    assert get_node_prop_dict(graph, "label") == {"a": "x", "b": "x", "c": 0}
    assert get_node_prop_dict(graph, "doubled") == {"a": 2, "b": 8, "c": -1}


def test_set_edge_props_and_outgoing_inherit_update_selected_edges():
    graph = nx.DiGraph()
    graph.add_node("a", signal="up")
    graph.add_node("b", signal="down")
    graph.add_node("c", signal="flat")
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")

    set_edge_props(
        graph,
        {("a", "b")},
        default="none",
        confidence={("a", "b"): "high"},
        flag=True,
    )
    outgoing_inherit(graph, "signal", newkey="source_signal")

    assert get_edge_prop_dict(graph, "confidence") == {("a", "b"): "high"}
    assert get_edge_prop_dict(graph, "flag") == {
        ("a", "b"): True,
        ("b", "c"): "none",
    }
    assert get_edge_prop_dict(graph, "source_signal") == {
        ("a", "b"): "up",
        ("b", "c"): "down",
    }


def test_multigraph_helpers_expand_edge_pairs_to_keyed_edges():
    graph = nx.MultiDiGraph()
    graph.add_edge("a", "b", key="k1", weight=1)
    graph.add_edge("a", "b", key="k2", weight=2)
    graph.add_edge("b", "c", key="k3", weight=3)

    assert set(from_multi_edge(graph, ("a", "b"))) == {
        ("a", "b", "k1"),
        ("a", "b", "k2"),
    }
    assert from_multi_edge(graph, ("a", "b", "k1")) == [("a", "b", "k1")]
    assert from_multi_edges(graph, {("a", "b"), ("b", "c", "k3")}) == {
        ("a", "b", "k1"),
        ("a", "b", "k2"),
        ("b", "c", "k3"),
    }
    assert get_edge_prop_dict(graph, "weight", edges={("a", "b")}) == {
        ("a", "b", "k1"): 1,
        ("a", "b", "k2"): 2,
    }
