#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import Any

import networkx as nx


from lifelike_gds.network.graph_algorithms import (
    all_node_minsum_paths,
    all_node_maxsum_paths,
    get_shortest_paths_plus_n,
)

from lifelike_gds.network.graph_utils import (
    DirectedGraph,
    MultiDirectedGraph,
    get_path_edges,
    get_path_directed_edges,
    from_multi_edges,
)

TraceGraphLike = DirectedGraph | MultiDirectedGraph


def add_trace_network(
    D: TraceGraphLike | nx.DiGraph | nx.MultiDiGraph,
    sources: str | set[Any],
    targets: str | set[Any],
    sources_key: str | None = None,
    targets_key: str | None = None,
    reverse: bool = False,
    weight: str | None = None,
    minsum: str | None = None,
    maxsum: str | None = None,
    n_edges: int | None = None,
    undirected: bool = False,
    default_sizing: str | None = None,
    name: str | None = None,
    description: str | None = None,
    query: str | None = None,
    shortest_paths_plus_n: int = 0,
) -> tuple[int | None, int]:
    """
    Create a trace-network entry on a graph and return its index and path count.

    ``sources`` and ``targets`` may be existing node-set keys or raw node-id
    sets. Raw sets are registered on the graph automatically before tracing.
    """
    if type(D) == nx.DiGraph:
        D = DirectedGraph(D)
    elif type(D) == nx.MultiDiGraph:
        D = MultiDirectedGraph(D)

    trace_networks = D.graph.setdefault("trace_networks", [])

    if reverse:
        sources, targets = targets, sources
        sources_key, targets_key = targets_key, sources_key
    sources, sources_key = D.node_set_key(
        sources,
        sources_key
        if sources_key is not None
        else f"trace{len(trace_networks)}_sources",
    )
    targets, targets_key = D.node_set_key(
        targets,
        targets_key
        if targets_key is not None
        else f"trace{len(trace_networks)}_targets",
    )

    trace_network = dict(sources=sources_key, targets=targets_key)
    if query is not None:
        trace_network["query"] = query
    else:
        if len(sources) >= len(targets):
            trace_network["query"] = sources_key
            message = f'Setting trace network "query" to {sources_key} since it is a bigger node set than {targets_key}.'
        else:
            trace_network["query"] = targets_key
            message = f'Setting trace network "query" to {targets_key} since it is a bigger node set than {sources_key}.'
        logging.info(message + ' Use "query" arg to avoid this.')
        D.describe(message)

    assert (
        sum(m is not None for m in [weight, minsum, maxsum]) <= 1
    ), "weight, minsum, and maxsum are mutually exclusive"
    if minsum is not None:
        method = minsum
        if undirected:
            raise NotImplementedError
        trace_network["method"] = f"min(sum({minsum}))"
        node_paths = all_node_minsum_paths(D, sources, targets, minsum, n_edges=n_edges)
    elif maxsum is not None:
        method = maxsum
        if undirected:
            raise NotImplementedError
        trace_network["method"] = f"max(sum({maxsum}))"
        node_paths = all_node_maxsum_paths(D, sources, targets, maxsum, n_edges=n_edges)
    else:
        method = weight
        if weight is None:
            trace_network["method"] = "min(length)"
        else:
            trace_network["method"] = f"min(sum({weight}))"
        node_paths = get_shortest_paths_plus_n(
            D, sources, targets, n=shortest_paths_plus_n, weight=weight
        )

    if name is None:
        name = f'{sources_key} -[{trace_network["method"]}]-> {targets_key}'
    assert name not in {
        tn["name"] for tn in D.graph["trace_networks"]
    }, "Trace network name already in use"
    trace_network["name"] = name
    message = [f'Trace network "{name}" from "{sources_key}" to "{targets_key}".']
    if description is None:
        description = f"Shortest paths starting at {D.get_node_set_description(sources_key)}, and ending at {D.get_node_set_description(targets_key)}."
        if minsum is not None:
            description += (
                f" Shortness weighted by min {D.get_node_prop_description(minsum)}."
            )
        elif maxsum is not None:
            description += (
                f" Shortness weighted by max {D.get_node_prop_description(maxsum)}."
            )
        elif weight is not None:
            description += (
                f" Shortness weighted by min {D.get_node_prop_description(weight)}."
            )

    trace_network["description"] = description
    message.append(f'Description="{description}".')
    message.append(f"Method={trace_network['method']}.")

    if default_sizing is None:
        if method in D.graph.get("sizing", {}):
            default_sizing = method
        elif method is not None:
            D.set_sizing(method)
            default_sizing = method

    if default_sizing is not None:
        trace_network["default_sizing"] = default_sizing
        message.append(f"Default sizing={default_sizing}.")

    if undirected:
        edges = [get_path_directed_edges(D, p) for p in node_paths]
    else:
        edges = [get_path_edges(p) for p in node_paths]
    if D.is_multigraph():
        edges = [from_multi_edges(D, es) for es in edges]

    n_unique_nodes = len({n for p in node_paths for n in p})
    n_unique_edges = len({e for es in edges for e in es})
    message.append(f"{n_unique_nodes} and {n_unique_edges} unique nodes and edges.")

    traces = {}
    for p, es in zip(node_paths, edges):
        trace = traces.setdefault((p[0], p[-1]), {})
        trace.setdefault("node_paths", []).append(p)
        trace.setdefault("edges", set()).update(es)

    trace_network["traces"] = []
    for (source, target), trace in traces.items():
        trace["source"] = source
        trace["target"] = target
        trace_network["traces"].append(trace)
    if len(trace_network["traces"]) > 0:
        trace_networks.append(trace_network)
        D.log(" ".join(message))
        return len(trace_networks) - 1, len(node_paths)
    else:
        logging.warning("No traces found.")
        return None, len(node_paths)


def get_traced_edges(D: TraceGraphLike) -> set[tuple[Any, ...]]:
    """Return all edges referenced by the graph's trace networks."""
    return set(_get_traced_edges(D))


def _get_traced_edges(D: TraceGraphLike):
    """
    Yield all edges referenced by the graph's trace networks.

    Includes ``detail_edges`` entries when they are present.
    """
    for tn in D.graph["trace_networks"]:
        for t in tn["traces"]:
            for e in t["edges"]:
                yield e
            if "detail_edges" in t:
                for e in t["detail_edges"]:
                    yield e[:2]


def get_traced_nodes(D: TraceGraphLike) -> set[Any]:
    """Return all node ids referenced by traces or traced edges."""
    return set(_get_traced_nodes(D))


def _get_traced_nodes(D: TraceGraphLike):
    """
    Yield all node ids that appear anywhere in the graph's trace payloads.
    """
    if "trace_networks" not in D.graph:
        return set()
    for tn in D.graph["trace_networks"]:
        for t in tn["traces"]:
            for p in t["node_paths"]:
                for n in p:
                    yield n

    for e in _get_traced_edges(D):
        yield e[0]
        yield e[1]


def get_trace_detail_graphs(D: TraceGraphLike) -> dict[tuple[Any, Any], TraceGraphLike]:
    """
    Build one detail graph per trace that contains ``detail_edges``.

    Returns:
        Mapping from ``(source, target)`` pairs to newly created graphs.
    """
    Ds = {}
    for tn in D.graph["trace_networks"]:
        for t in tn["traces"]:
            if "detail_edges" not in t:
                continue
            detail_edges = t["detail_edges"]
            source = t["source"]
            target = t["target"]
            assert (source, target) not in Ds, f"Duplicate {(source, target)}"
            _D = Ds[(source, target)] = D.__class__()
            _D.add_nodes_from([(n, D.nodes[n]) for e in detail_edges for n in e[:2]])
            _D.add_edges_from(detail_edges)
            _D.name = D.name
            _D.graph["description"] = "\n\n".join(
                d.get("description", "") for d in [D.graph, tn, t]
            )
            node_sets = _D.graph["node_sets"] = D.graph["node_sets"]
            node_sets["source"] = {source}
            node_sets["target"] = {target}
    return Ds


def link_index(data: dict[str, Any]) -> None:
    """
    Replace edge tuples in trace payloads with link-array indexes in place.

    Args:
        data: ``nx.node_link_data``-style payload.
    """
    link_key = "links" if "links" in data else "edges"
    if data["multigraph"]:
        edge2index = {
            (l["source"], l["target"], l["key"]): i
            for i, l in enumerate(data[link_key])
        }
    else:
        edge2index = {
            (l["source"], l["target"]): i for i, l in enumerate(data[link_key])
        }

    for tn in data["graph"]["trace_networks"]:
        for t in tn["traces"]:
            t["edges"] = [edge2index[e] for e in t["edges"]]

    if data["multigraph"]:
        for link in data[link_key]:
            del link["key"]
