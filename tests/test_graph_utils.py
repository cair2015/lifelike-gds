from pathway_graphx.network.graph_utils import (
    DirectedGraph,
    MultiDirectedGraph,
    get_leaves,
    get_path_directed_edges,
    get_roots,
    graph_union,
    path_product,
    trim_leaves,
)


def test_trim_leaves_respects_node_set_exclusions():
    graph = DirectedGraph()
    graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")])
    graph.add_node("isolated")
    graph.set_node_set("keep", {"c"})

    assert get_roots(graph) == {"a"}
    assert get_leaves(graph) == {"d"}

    trim_leaves(graph, exclude="keep")

    assert set(graph.nodes) == {"a", "b", "c", "isolated"}


def test_graph_union_merges_node_sets_trace_networks_and_meta():
    graph1 = DirectedGraph(name="g1")
    graph1.add_edge("a", "b")
    graph1.set_node_set("sources", {"a"})
    graph1.graph["trace_networks"] = [{"name": "tn1", "traces": []}]
    graph1.name_node_props(score="Score")

    graph2 = DirectedGraph(name="g2")
    graph2.add_edge("b", "c")
    graph2.set_node_set("sources", {"b"})
    graph2.graph["trace_networks"] = [{"name": "tn2", "traces": []}]
    graph2.describe_node_props(score="Demo score")

    union_graph = graph_union(graph1, graph2)

    assert isinstance(union_graph, DirectedGraph)
    assert union_graph.graph["node_sets"]["sources"] == {"a", "b"}
    assert [tn["name"] for tn in union_graph.graph["trace_networks"]] == ["tn1", "tn2"]
    assert union_graph.graph["node_props"]["score"] == {
        "name": "Score",
        "description": "Demo score",
    }


def test_directed_graph_node_set_lookup_and_set_apply_reference_semantics():
    graph = DirectedGraph()
    graph.add_nodes_from(
        [
            ("a", {"active": True, "kind": "gene"}),
            ("b", {"active": False, "kind": "gene"}),
            ("c", {"active": True, "kind": "protein"}),
        ]
    )

    graph.set({"a"}, score=10, default=0)

    assert graph.node_set("active") == {"a", "c"}
    assert graph.node_set_key({"a", "c"}, default_key="selected") == (
        {"a", "c"},
        "selected",
    )
    assert graph.get(kind="gene") == {"a", "b"}
    assert graph.getd("score") == {"a": 10, "b": 0, "c": 0}


def test_path_helpers_and_trace_network_registration_work_together():
    graph = DirectedGraph()
    graph.add_edges_from(
        [("s", "m1"), ("m1", "t"), ("s", "m2"), ("m2", "t"), ("c", "b"), ("a", "b")]
    )

    assert get_path_directed_edges(graph, ["a", "b", "c"]) == {("a", "b"), ("c", "b")}
    assert path_product([[1, 2, 3], [1, 4, 3]], [[3, 5]]) == [
        [1, 2, 3, 5],
        [1, 4, 3, 5],
    ]

    graph.add_trace_network(
        {"s"},
        {"t"},
        [["s", "m1", "t"], ["s", "m2", "t"]],
        method="min(length)",
        description="demo",
        sources_key="sources",
        targets_key="targets",
        name="demo trace",
    )

    trace_network = graph.graph["trace_networks"][0]
    assert trace_network["query"] == "sources"
    assert trace_network["name"] == "demo trace"
    assert trace_network["default_sizing"] == "min(length)"
    assert len(trace_network["traces"]) == 1
    trace = trace_network["traces"][0]
    assert trace["source"] == "s"
    assert trace["target"] == "t"
    assert {tuple(path) for path in trace["node_paths"]} == {
        ("s", "m1", "t"),
        ("s", "m2", "t"),
    }
    assert trace["edges"] == {("s", "m1"), ("m1", "t"), ("s", "m2"), ("m2", "t")}


def test_multidirected_graph_expands_pair_edges_for_dictionary_access():
    graph = MultiDirectedGraph()
    graph.add_edge("a", "b", key="k1", weight=1)
    graph.add_edge("a", "b", key="k2", weight=2)

    assert graph.geted("weight", edges={("a", "b")}) == {
        ("a", "b", "k1"): 1,
        ("a", "b", "k2"): 2,
    }
