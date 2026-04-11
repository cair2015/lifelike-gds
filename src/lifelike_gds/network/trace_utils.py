#!/usr/bin/env python3
import logging
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


def add_trace_network(
    D,
    sources,
    targets,
    sources_key=None,
    targets_key=None,
    reverse=False,
    weight=None,
    minsum=None,
    maxsum=None,
    n_edges=None,
    undirected=False,
    default_sizing=None,
    name=None,
    description=None,
    query=None,
    shortest_paths_plus_n=0,
):
    """
    Add an entry to a list D.graph["trace_networks"].
    :param D: (Multi)DirectedGraph, networkx graph will be converted.
    :param sources: key in D.graph["node_sets"].
    If set of nodes is given without name_sources they will be looked for in D.graph["node_sets"]. If not found they will be given a new arbitrary name.
    :param targets: same as sources, except for targets.
    :param sources_key: optional string key to give to sources if "sources" is a set of node ids.
    :param targets_key: optional string key to give to targets if "targets" is a set of node ids.
    :param reverse: if True simply reverses source and target sets for convenience.
    :param weight: get all shortest paths with min(sum(edge weight))
    :param minsum: get all shortest paths with min(sum(node weight))
    :param maxsum: get all shortest paths with min(sum(1/node weight))
    :param n_edges: set a lower bound on number of unique edges in the trace network
    :param undirected: bool. Undirected shortest paths.
    :param default_sizing: name of default sizing definition for this trace network.
    Defaults to looking for a sizing definition with the same name as a given "weight", "minsum" or "maxsum".
    If any of those are given and a sizing definition is not found then one will be made possibly copying name and description from a node property matching key.
    :param name: optional str text name
    :param description: optional str text description. If not given, one will be generated.
    :param query: optional str to indicate the query set key. Default: take set key from the bigger set among sources and targets.
    :return: trace_network index if traces were found else None
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


def get_traced_edges(D):
    return set(_get_traced_edges(D))


def _get_traced_edges(D):
    """
    Get all edges mentioned in traces.
    :param D:
    :return:
    """
    for tn in D.graph["trace_networks"]:
        for t in tn["traces"]:
            for e in t["edges"]:
                yield e
            if "detail_edges" in t:
                for e in t["detail_edges"]:
                    yield e[:2]


def get_traced_nodes(D):
    return set(_get_traced_nodes(D))


def _get_traced_nodes(D):
    """
    Get all nodes that are in any trace of D.
    :param D:
    :return: iterator for set of node ids
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


def get_trace_detail_graphs(D):
    """
    Get a separate graph for each of the "detail_edges" entries in each trace.
    :param D:
    :return: dict mapping from (source, target) to graph
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


def link_index(data):
    """
    Use indexing in "link" list instead of (u, v) or (u, v, k)
    :param data: node_link_data dict representation of graph
    :return:
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
