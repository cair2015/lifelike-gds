import networkx as nx

from lifelike_gds.network.groups import get_groups, set_default_groups


def test_get_groups_reuses_existing_group_for_same_source_when_query_matches_sources():
    trace_network = {
        "query": {"s1", "s2"},
        "sources": {"s1", "s2"},
        "traces": [
            {"source": "s1", "target": "t1", "group": 7},
            {"source": "s1", "target": "t2"},
            {"source": "s2", "target": "t3"},
            {"source": "s2", "target": "t4"},
        ],
    }

    assert list(get_groups(trace_network)) == [7, 7, 0, 0]


def test_get_groups_uses_target_side_when_query_differs_from_sources():
    trace_network = {
        "query": {"t1", "t2"},
        "sources": {"s1"},
        "traces": [
            {"source": "s1", "target": "t2"},
            {"source": "s2", "target": "t1"},
            {"source": "s3", "target": "t2"},
        ],
    }

    assert list(get_groups(trace_network)) == [1, 0, 1]


def test_set_default_groups_populates_only_missing_group_values():
    graph = nx.DiGraph()
    graph.graph["trace_networks"] = [
        {
            "query": {"s1"},
            "sources": {"s1"},
            "traces": [
                {"source": "s1", "target": "t1", "group": 5},
                {"source": "s1", "target": "t2"},
                {"source": "s2", "target": "t3"},
            ],
        }
    ]

    set_default_groups(graph)

    traces = graph.graph["trace_networks"][0]["traces"]
    assert [trace["group"] for trace in traces] == [5, 5, 0]
