#!/usr/bin/env python3
import itertools
import logging
import networkx as nx
from networkx.exception import NetworkXNoPath, NodeNotFound
import numpy as np
import pandas as pd
import sys

from lifelike_gds.network.collection_utils import (
    dict_take,
    dict_take_values
)
from lifelike_gds.network.graph_utils import (
    DirectedGraph,
    get_edge_path,
    get_unique_edges,
    path_product,
)

logging.basicConfig(format="%(message)s", level=logging.INFO)

### CENTRALITY AND INFLUENCE

# some centralities https://networkx.org/documentation/stable/reference/algorithms/centrality.html
# eigenvector centrality just sums the eigenvector centralities of incoming nodes. It works for both directed and undirected. Symmetric vs non-symmetric R in source:
#        Power and Centrality: A Family of Measures.
#        American Journal of Sociology 92(5):1170–1182, 1986
#        http://www.leonidzhukov.net/hse/2014/socialnetworks/papers/Bonacich-Centrality.pdf
# Katz adds attenuation factor alpha so the weight of a path 3 edges long is alpha^3 where for eigenvector it is basically like using alpha==1
# one thing missing from these are a starting weight to the shortlist. Centralities will only appear because of cycles in a directed graph.
# a pagerank adds random jumps to any node so that fixes it, but we only want those jumps to shortlist genes.
# I think the solution is something like adding <1 probabilities for jumping to shortlist genes.
# pagerank adds damping factor alpha which is e.g. 0.85 according to wiki means that a normalized adjacency matrix A gets modified to alpha A + (1-alpha) /N so we get a probability 0.15 to jump to a random node.
# we don't want that.
# We also have assignment of outgoing edges to dangling nodes that is by default a uniform distribution:
# https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html#networkx.algorithms.link_analysis.pagerank_alg.pagerank
# So we either want to get edges onto shortlist genes from all nodes or from dangling and we either want to accomplish that by modifying the graph ourselves or maybe by tweaking the use of pagerank with its personalization parameter etc.
# after reading the pagerank code above from networkx I can see it is written such that personalization is controlling where those 1-alpha leaking jumps per iteration goes,
# and that dangling nodes takes all of their alpha remaining value and sends it to "dangling" which by default is the same as the personalization dict.
# So it seems I can get what I want through pagerank by tweaking those two args depending on how I want to use the 1-alpha leak and the dangling nodes.


def eigenvector_influence(
    G, sources, w=None, weight="weight", numpy_method=False, tol=1.0e-6, max_iter=500
):
    """
    Modified eigenvector centrality measuring how much nodes are influenced by "start_nodes"
    :param G: networkx graph
    :param sources: list of node ids
    :param w: scalar. Default is 1/indegree (for edges providing "leak" from all nodes)
    :param weight: string name for weight property
    :param numpy_method:
    :return: list of level of influence for each node
    """
    sources = {s for s in sources if s in G}
    g = G.copy()
    if w is None:
        w = 1 / len(sources)  # taken from pageRank
    g.add_edges_from(
        (n, s, {"type": "centrality", weight: w}) for s in sources for n in G
    )
    nstart = {v: 0 for v in g}
    for v in sources:
        nstart[v] = 1
    if not numpy_method:
        return nx.eigenvector_centrality(
            g, nstart=nstart, weight=weight, max_iter=max_iter, tol=tol
        )
    else:
        return nx.eigenvector_centrality_numpy(
            g, weight=weight, max_iter=max_iter, tol=tol
        )


def eigenvector_influence_dangling(G, sources, w):
    """
    Modified eigenvector centrality measuring how much nodes are influenced by "start_nodes"
    :param G: networkx graph
    :param sources: list of node ids
    :return: list of level of influence for each node
    """
    sources = {s for s in sources if s in G}
    g = G.copy()
    g.add_edges_from(
        (n, s, {"type": "centrality", "weight": w})
        for s in sources
        for n in G
        if G.out_degree(n) == 0
    )
    nstart = {v: 0 for v in g}
    for v in sources:
        nstart[v] = 1
    return nx.eigenvector_centrality(g, nstart=nstart, weight="weight", max_iter=500)


def katz_influence(G, sources, w=None, weight="weight", tol=1.0e-6, max_iter=1000):
    """
    Modified katz centrality measuring how much nodes are influenced by "start_nodes"
    :param G: networkx graph
    :param sources: list of node ids
    :return: list of level of influence for each node
    """
    sources = {s for s in sources if s in G}
    g = G.copy()
    if w is None:
        w = 1 / len(sources)  # taken from pageRank
    g.add_edges_from(
        (n, s, {"type": "centrality", weight: w}) for s in sources for n in G
    )
    nstart = {v: 0 for v in g}
    for v in sources:
        nstart[v] = 1
    return nx.katz_centrality(
        g, nstart=nstart, weight=weight, tol=tol, max_iter=max_iter
    )


def add_influence_contribution(D, reverse=False, weight="weight", **node_prop_keys):
    """
    Edges are annotated with influence contribution 2-tuples where the first value is the edge size at the source and the second value is the edge size at the target.
    If "reverse" is False (default) that will be equivalent to a tuple (source node centrality influence * edge weight / sum(source node outgoing edge weights), contribution onto target)
    and if "reverse" is True then the meaning of those two entries will be flipped to preserve the order that focuses on edge sizing for Sankey plotting etc.
    :param D: (Multi)DirectedGraph
    :param reverse: if True the contribution will calculated for a reverse centrality influence.
    :param weight:
    :param node_prop_keys: keys are the edge property name to store values in, values are the key in node props for the stored centrality influence.
    :return:
    """
    _D = D.reverse(copy=False) if reverse else D

    # first store the contribution given BY each node
    for edge_prop_key, node_prop_key in node_prop_keys.items():
        for u, u_cent in _D.nodes(data=node_prop_key):
            outgoing = [e[-1] for e in _D.out_edges(u, data=True)]
            sum_weight = sum(d.get(weight, 1) for d in outgoing)
            for d in outgoing:
                d[edge_prop_key] = (
                    (u_cent if u_cent is not None else 0)
                    * d.get(weight, 1)
                    / sum_weight
                )

    # then store the proportion of resulting scores in each node that the incoming edges each provided
    for edge_prop_key, node_prop_key in node_prop_keys.items():
        for v, v_cent in _D.nodes(data=node_prop_key):
            incoming = [e[-1] for e in _D.in_edges(v, data=True)]
            sum_contribution = sum(d[edge_prop_key] for d in incoming)
            for d in incoming:
                if sum_contribution == 0:
                    d[edge_prop_key] = d[edge_prop_key], 0
                else:
                    d[edge_prop_key] = (
                        d[edge_prop_key],
                        (v_cent if v_cent is not None else 0)
                        * d[edge_prop_key]
                        / sum_contribution,
                    )

    # flip 2-tuples so the order follows the direction of edge in D
    if reverse:
        for u, v, d in _D.edges(data=True):
            for edge_prop_key, node_prop_key in node_prop_keys.items():
                d[edge_prop_key] = d[edge_prop_key][::-1]



# TODO: Could this (and perhaps other traversals) be re-implemented as class methods? It seems like
# the execution of this method in particular is dependent on the type of graph passed in.
def shortest_paths(D, sources, targets, weight=None, undirected=False):
    """
    Single example of a shortest path for each source vs target combination.
    :param D:
    :param sources:
    :param targets:
    :param weight:
    :param undirected:
    :return: generator of list of node paths
    """
    if type(sources) in [str, int]:
        sources = [sources]
    if type(targets) in [str, int]:
        targets = [targets]
    G = D.to_undirected() if undirected else D
    for s in sources:
        for t in targets:
            try:
                yield nx.shortest_path(G, s, t, weight=weight)
            except NetworkXNoPath:
                pass


def all_node_minsum_paths(D, sources, targets, node_weight, n_edges=None):
    """
    Get all paths that have the smallest sum of a given node property along the path.
    :param D: directed graph
    :param sources:
    :param targets:
    :param node_weight: the node property key
    :param n_edges: aim to get at least this number of unique edges back, so return more than the very shortest.
    :return:
    """
    # add temp edge weight. This temp property approach is way faster than using weight=lambda u, v, d: ...
    tempkey = node_weight + "_minsum"
    for u, v, d in D.edges(data=True):
        d[tempkey] = D.nodes[u][node_weight]
    paths = get_all_shortest_paths(D, sources, targets, n_edges=n_edges, weight=tempkey)
    for u, v, d in D.edges(data=True):
        del d[tempkey]
    return paths


def all_node_maxsum_paths(D, sources, targets, node_weight, n_edges=None):
    """
    Get all shortest paths weighted by a given node property along the path where a higher value in the property is a better connection.
    If the property is 0 then the node will not be traversed.
    :param D: directed graph
    :param sources:
    :param targets:
    :param node_weight: the node property key
    :param n_edges: aim to get at least this number of unique edges back, so return more than the very shortest.
    :return:
    """
    # add temp edge weight. This temp property approach is way faster than using weight=lambda u, v, d: ...
    tempkey = node_weight + "_maxsum"
    _D = D.copy(as_view=False)
    # this code will result in missing paths from source to dest
    # _D.remove_nodes_from(D.get(**{node_weight: 0}))
    for u, v, d in _D.edges(data=True):
        max_value = max(
            D.nodes[u][node_weight] if not D.nodes[u].get(node_weight) is None else 0,
            D.nodes[v][node_weight] if not D.nodes[v].get(node_weight) is None else 0,
        )
        d[tempkey] = (1 / max_value) if max_value > 0 else sys.maxsize
        # d[tempkey] = 1 / _D.nodes[u][node_weight]
    paths = get_all_shortest_paths(
        _D, sources, targets, n_edges=n_edges, weight=tempkey
    )
    # still necessary to delete the tempkey as the dicts might the same as for D
    for u, v, d in _D.edges(data=True):
        del d[tempkey]
    return paths


def get_shortest_paths_plus_n(
    D,
    sources: str,
    targets: str,
    n=0,
    max_path_length=10,
    undirected=False,
    weight=None,
) -> list:
    """Calculates all paths from sources to targets that are the length of the shortest path plus any number n. A maximum threshold can be given, default 10.

    Args:
        D: The network to calculate shortest paths for.
        sources (str): the descriptor for the set of source nodes.
        targets (str): the descriptor for the set of target nodes.
        n (int, optional): Modifier which will be added to the length of the shortest path to determine the maximum length of paths to find. Defaults to 0.
        max_path_length (int, optional): Threshold for the length of paths to find. Defaults to 10.
        undirected (bool, optional): Boolean describing whether the given network is undirected or not. Defaults to False.

    Returns:
        list: A list representing all the paths found.
    """
    sources = D.node_set(sources) & D.nodes
    targets = D.node_set(targets) & D.nodes
    if undirected:
        D = D.to_undirected()

    if n == 0:
        return all_shortest_paths(D, sources, targets, weight)

    shortest_paths_plus_n = []
    for s in sources:
        for t in targets:
            try:
                shortest_path_len = 0
                for p in nx.shortest_simple_paths(D, s, t, weight):
                    # First path found is always a shortest path
                    if shortest_path_len == 0:
                        shortest_path_len = len(p)
                    # If the length of the path is > shortest path len + n, then we can stop
                    if len(p) > shortest_path_len + n:
                        break
                    shortest_paths_plus_n.append(p)
            except NetworkXNoPath:
                continue
    return shortest_paths_plus_n


def get_all_shortest_paths(
    D, sources, targets, n_edges=None, weight=None, undirected=False
):
    """
    Convenient access-point for both the shortest path search and k shortest path search.
    :param D:
    :param sources:
    :param targets:
    :param n_edges:
    :param weight:
    :param undirected:
    :return:
    """
    if (
        weight is not None
        and not callable(weight)
        and not any(weight in d for u, v, d in D.edges(data=True))
    ):
        logging.warning(f"No weight {weight} found for any edge in the graph.")
    sources = D.node_set(sources) & D.nodes
    targets = D.node_set(targets) & D.nodes
    if undirected:
        D = D.to_undirected()
    if n_edges is None:
        return all_shortest_paths(D, sources, targets, weight=weight)
    else:
        # NOTE: This is a perfect example of a confusing side effect...what does it even mean to
        # construct a DG from a MDG?
        if D.is_multigraph():
            D = DirectedGraph(D)
            if weight is not None:
                logging.log(
                    logging.INFO if callable(weight) else logging.WARNING,
                    "k shortest paths not implemented for multigraph, converting.",
                )
        return list(_short_paths(D, sources, targets, n_edges, weight=weight))


def all_shortest_paths(D, sources, targets, weight=None):
    """

    :param D:
    :param sources: node set
    :param targets: node set
    :param weight:
    :return: list of node paths
    """
    return [
        p
        for s in sources
        for t in targets
        for p in _all_shortest_paths(D, s, t, weight=weight)
    ]


def _short_paths(D, sources, targets, n_edges, weight=None):
    """
    Collect shortest paths until there are at least "n_edges" unique edges among all paths.
    This function returns proportional numbers of paths from each source vs target.
    Another approach could be to return shortest paths among all, with a guarantee for at least one from each source vs target.
    :param D:
    :param sources:
    :param targets:
    :param n_edges:
    :param weight:
    :return:
    """
    k = n_edges  # rough upper bound
    # generator that supplies one path at a time for each source vs target, sorted by shortness
    unique_edges = set()
    for ps in itertools.zip_longest(
        *(
            _all_k_shortest_paths(D, s, t, k, weight=weight)
            for s in sources
            for t in targets
        ),
        fillvalue=[],
    ):
        for p in ps:
            if p:
                yield p
        unique_edges |= get_unique_edges(ps)
        if len(unique_edges) >= n_edges:
            break


def _all_shortest_paths(D, source, target, weight=None):
    """

    :param D:
    :param source:
    :param target:
    :param weight:
    :return: generator or empty list
    """
    try:
        for p in nx.all_shortest_paths(D, source, target, weight=weight):
            yield p
    except (NetworkXNoPath, NodeNotFound) as e:
        logging.error(e)
        return []


def _all_k_shortest_paths(D, source, target, k, weight=None):
    """
    Get all k shortest paths, which means that paths will be returned from shortest to longest
    stopping when all paths are returned with the same length as the k-th shortest path.
    This means more than k paths will be returned if many paths have the same length and
    fewer will be returned if fewer than k simple paths exist from source to target.
    :param D: graph
    :param source: node id
    :param target: node id
    :param k: try to return this many short paths, not guaranteed to return exactly k paths
    :param weight: string edge property or function(u, v, d)
    :return: generator for node paths
    """
    l = 0
    try:
        for i, p in enumerate(
            nx.shortest_simple_paths(D, source, target, weight=weight)
        ):
            if i >= k:
                if len(p) > l:
                    break
            else:
                l = len(p)
            yield p
    except (NetworkXNoPath, NodeNotFound):
        return []


def all_shortest_path(D, sources, targets, weight=None):
    """
    All paths between min. one node from "sources" and min. one from "targets" that are as short as the shortest path between any node from "sources" and any node from "targets"
    :param D:
    :param sources:
    :param targets:
    :param weight:
    :return:
    """
    paths = get_all_shortest_paths(D, sources, targets, weight=weight)
    dist = min(len(p) for p in paths)
    return [p for p in paths if len(p) == dist]


def _all_2step_paths(D, u, v):
    for n in D.successors(u):
        if D.has_successor(n, v):
            yield [u, n, v]


def _all_shortest_max2_paths(D, u, v):
    if D.has_successor(u, v):
        return [[u, v]]
    return _all_2step_paths(D, u, v)


def all_simple_paths(D, sources, targets, cutoff=100):
    return list(_all_simple_paths(D, sources, targets, cutoff=cutoff))


def _all_simple_paths(D, sources, targets, cutoff=100):
    if type(sources) in [str, int]:
        sources = {sources}
    if type(targets) in [str, int]:
        targets = {targets}
    targets = set(targets).difference(
        sources
    )  # if any source is in targets all_simple_paths fail silently
    sources.intersection_update(D.nodes)
    return (
        p for s in sources for p in nx.all_simple_paths(D, s, targets, cutoff=cutoff)
    )


def all_simple_paths_noInter(D, sources, targets, cutoff=100):
    """
    Same as all_simple_paths except we don't want paths that goes through any source or target as an intermediary node.
    :param D:
    :param sources:
    :param targets:
    :param cutoff:
    :return:
    """
    if type(sources) in [str, int]:
        sources = {sources}
    if type(targets) in [str, int]:
        targets = {targets}
    nodes = set(sources).union(targets)
    return [
        p
        for p in _all_simple_paths(D, sources, targets, cutoff)
        if len(nodes.intersection(p[1:-1])) == 0
    ]


def all_simple_paths_through(D, sources, through, targets, cutoff=100):
    """

    :param D:
    :param sources:
    :param through:
    :param targets:
    :param cutoff:
    :return:
    """
    p1s = all_simple_paths(D, sources, through, cutoff=cutoff // 2)
    p2s = all_simple_paths(D, through, targets, cutoff=cutoff // 2)
    return [p1 + p2[1:] for p1 in p1s for p2 in p2s]


def all_shortest_paths_through(D, sources, through, targets):
    """
    Shortest paths starting at each source going through each "through" ending at each target
    :param D:
    :param sources:
    :param through:
    :param targets:
    :return:
    """
    p1s = get_all_shortest_paths(D, sources, through)
    p2s = get_all_shortest_paths(D, through, targets)
    return [p1 + p2[1:] for p1 in p1s for p2 in p2s]


def all_shortest_paths_through_any(D, sources, through, targets):
    return list(_all_shortest_paths_through_any(D, sources, through, targets))


def _all_shortest_paths_through_any(D, sources, through, targets):
    """
    All shortest path starting at each source, ending at each target going through any of the "through"
    :param D:
    :param sources:
    :param through:
    :param targets:
    :return:
    """
    if type(sources) in [str, int]:
        sources = {sources}
    if type(through) in [str, int]:
        through = {through}
    if type(targets) in [str, int]:
        targets = {targets}
    sources = {n for n in sources if n in D}
    through = {n for n in through if n in D}
    targets = {n for n in targets if n in D}
    short_thru = shortest_through(D, sources, through, targets)
    for t in short_thru:
        for s in short_thru[t]:
            for thru in short_thru[t][s]:
                source2thrus = list(nx.all_shortest_paths(D, s, thru))
                thrus2target = list(nx.all_shortest_paths(D, thru, t))
                for p1 in source2thrus:
                    for p2 in thrus2target:
                        yield p1 + p2[1:]


def all_shortest_paths_along(D, *alongs):
    """
    Connect the dots. Given list of nodes that may not be directly connected, get the shortest paths that connects the disconnected steps.
    :param D: graph
    :param alongs: list of nodes to be connected in the shortest way possible.
    :return: list of paths. Each path is a list of nodes.
    """
    return [
        p
        for nodes in alongs
        for p in path_product(
            *(nx.all_shortest_paths(D, u, v) for u, v in get_edge_path(nodes))
        )
    ]


def all_2step_paths_along(D, *alongs):
    """
    Fill in the blanks (nodes) between each node in each list given in alongs.
    Paths are only found if there is a connection between each pair of nodes through exactly 1 other node.
    :param D: graph
    :param alongs: list of nodes to be connected through single extra steps.
    :return: list of paths. Each path is a list of nodes.
    """
    return [
        p
        for nodes in alongs
        for p in path_product(
            *(_all_2step_paths(D, u, v) for u, v in get_edge_path(nodes))
        )
    ]


def all_shortest_max2_paths_along(D, *alongs):
    """
    Fill in the blanks (nodes) between each node in each list given in alongs.
    If there is a direct link from a node to the next in a path then that is kept, rather than a 2 step path.
    :param D: graph
    :param alongs: list of nodes to be connected through single extra steps.
    :return: list of paths. Each path is a list of nodes.
    """
    return [
        p
        for nodes in alongs
        for p in path_product(
            *(_all_shortest_max2_paths(D, u, v) for u, v in get_edge_path(nodes))
        )
    ]


def path_subgraph(D, paths):
    return D.edge_subgraph(e for p in paths for e in zip(p[:-1], p[1:]))


def simple_paths_subgraph(D, sources, targets, cutoff=100):
    return path_subgraph(D, _all_simple_paths(D, sources, targets, cutoff=cutoff))


def shortest_paths_subgraph(D, sources, targets, weight=None, undirected=False):
    return path_subgraph(
        D, shortest_paths(D, sources, targets, weight=weight, undirected=undirected)
    )


def all_shortest_paths_subgraph(D, sources, targets, weight=None):
    return path_subgraph(D, get_all_shortest_paths(D, sources, targets, weight=weight))


def all_shortest_path_subgraph(D, sources, targets, weight=None):
    return path_subgraph(D, all_shortest_path(D, sources, targets, weight=weight))


def get_shortest(paths):
    """
    Get shortest path among a list of paths.
    :param paths: list of paths.
    :return: shortest path
    """
    return paths[np.argmin([len(p) for p in paths])]


def get_all_shortest(paths):
    """
    Get all shortest path among a list of paths.
    :param paths: list of paths.
    :return: paths that are as long as the shortest one
    """
    l = min(len(p) - 1 for p in paths)
    return [p for p in paths if len(p) == l]


def get_all_shortest_endpoints(paths):
    """
    Get all shortest paths among a list of paths from each unique starting node and end node.
    :param paths: list of paths.
    :return: shortest paths between each start and end point
    """
    sources = {p[0] for p in paths}
    targets = {p[-1] for p in paths}
    shortests = {s: {t: [] for t in targets} for s in sources}
    for p in paths:
        best = shortests[p[0]][p[-1]]
        if len(best) == 0 or len(best[0]) == len(p):
            best.append(p)
        elif len(best[0]) > len(p):
            shortests[p[0]][p[-1]] = [p]
    # unpack
    return [p for s in shortests for t in shortests[s] for p in shortests[s][t]]


def get_all_shortest_paths_node_weight(paths, weights):
    """
    Get all shortest paths among a list of paths from each unique starting node and end node.
    This version has path length equal to sum of the values taken from "weights".
    :param paths: list of paths.
    :param weights: {node1: length to walk over this node, node2: length2, ...}
    :return: shortest paths between each start and end point
    """
    sources = {p[0] for p in paths}
    targets = {p[-1] for p in paths}
    lengths = [sum(weights[n] for n in p) for p in paths]
    shortests = {s: {t: [] for t in targets} for s in sources}
    for i, (p, l) in enumerate(zip(paths, lengths)):
        best = shortests[p[0]][p[-1]]
        if len(best) == 0:
            best.append(i)
        else:
            bestL = lengths[best[0]]
            if bestL == l:
                best.append(i)
            elif bestL > l:
                shortests[p[0]][p[-1]] = [i]
    # unpack
    return [paths[i] for s in shortests for t in shortests[s] for i in shortests[s][t]]


def all_shortest_path_length(G, sources):
    """
    Shortest path length from all sources in "sources" toward all nodes in G.
    :param G: graph
    :param sources: iterable of node ids
    :return: {n0: {source3: int shortest_path_length, ...}, n1: ...}
    """
    out = {n: {} for n in G}
    for s in set(G).intersection(sources):
        for n, d in nx.shortest_path_length(G, s).items():
            out[n][s] = d
    return out


def average_shortest_path_length(G, sources, targets):
    """
    Get the average shortest for each source to the given targets when a source has any paths to targets.
    :param G:
    :param sources:
    :param targets:
    :return: {source2: int, ...}
    """
    sources = set(G).intersection(sources)
    targets = set(G).intersection(targets)
    # we can do fewer calls to nx.shortest_path_length
    if len(targets) < len(sources):
        dists = {
            t: dict_take(nx.shortest_path_length(G, target=t), sources) for t in targets
        }
        out = {s: [] for s in sources}
        for t, svs in dists.items():
            for s, v in svs.items():
                out[s].append(v)
        return {s: np.mean(vs) for s, vs in out.items() if len(vs) > 0}
    else:
        dists = {
            s: dict_take_values(nx.shortest_path_length(G, s), targets) for s in sources
        }
        return {s: vs.mean() for s, vs in dists.items() if len(vs) > 0}


def shortest_path_length(G, sources):
    """
    Shortest path length from any source in "sources" toward all nodes in G.
    Should be NaN if no path is found.
    :param G: graph
    :param sources: iterable of node ids
    :return: {n0: int shortest_path_length0, n1: int, ...}
    """
    sources = [s for s in sources if s in G]
    return dict(pd.DataFrame([nx.shortest_path_length(G, s) for s in sources]).min())


def shortest_path_lengths_through(G, sources, through):
    """
    Shortest path lengths from any source in "sources" through all node in "through" toward all nodes in G.
    Should be NaN if no path is found.
    :param G: graph
    :param sources: iterable of node ids
    :param through: iterable of node ids
    :return: pandas dataframe with "through" along rows and all nodes in G along columns
    """
    sources = [n for n in sources if n in G]
    through = [n for n in through if n in G]
    # a row with shortest path length for each node in "through" and a column for each node in G
    fromThrough = pd.DataFrame([nx.shortest_path_length(G, s) for s in through])
    fromSource = shortest_path_length(G, sources)
    # add distance between source and "through"
    source2through = np.asarray([fromSource.get(t, np.nan) for t in through])
    source2through2all = source2through.reshape(-1, 1) + fromThrough.values
    return pd.DataFrame(source2through2all, columns=fromThrough.columns, index=through)


def shortest_path_length_through(G, sources, through):
    """
    Shortest path length from any source in "sources" through any node in "through" toward all nodes in G.
    Should be NaN if no path is found.
    :param G: graph
    :param sources: iterable of node ids
    :param through: iterable of node ids
    :return: {n0: int shortest_path_length0, n1: int, ...}
    """
    return dict(
        shortest_path_lengths_through(G, sources, through).min(axis=0, skipna=True)
    )


def all_shortest_path_lengths_through(G, sources, through):
    """
    Get the shortest path length from each source through each "through" to each target node in G
    :param G:
    :param sources:
    :param through:
    :return: pandas dataframe with levels "source", "through" and columns "target"
    """
    sources = {n for n in sources if n in G}
    through = {n for n in through if n in G}
    fromSource = pd.DataFrame(
        {s: nx.shortest_path_length(G, s) for s in sources}
    ).transpose()
    fromThrough = pd.DataFrame(
        {s: nx.shortest_path_length(G, s) for s in through}
    ).transpose()
    fromSource.index.name = "source"
    fromThrough.index.name = "through"
    fromSource = pd.concat({n: fromSource for n in through}, names=["through"])
    fromThrough = pd.concat({n: fromThrough for n in sources}, names=["source"])
    return fromThrough + fromSource


def shortest_through(G, sources, through, targets):
    """
    Get the intermediaries from "through" for each source vs target pair that is part of the shortest path from source to target going through one of the "through" nodes.
    :param G:
    :param sources:
    :param through:
    :param targets:
    :return: {target0: {source0: [through2, through5, ...], ...}, target1: {source0: [], source1: [through1], ...}, ...}
    """
    dists = all_shortest_path_lengths_through(G, sources, through)
    return {
        t: {
            s: set(group.index.get_level_values("through")[group.min() == group])
            for s, group in dists[t].groupby("source")
        }
        for t in targets
    }


def descendant_of(D, roots):
    """
    Find out which of the roots a node is a descendant of.
    :param D:
    :param roots:
    :return: {node0: [root0, root1, ...], node1: [root0, ...], ...}
    """
    descOf = {n: set() for n in D}
    for r in roots:
        if r in D:
            for desc in nx.descendants(D, r):
                descOf[desc].add(r)
    return descOf


def descendant_of_any(D, roots):
    """
    Get set of nodes that are descendant of at least on of the given roots.
    :param D: DirectedGraph or networkx graph
    :param roots: set of nodes
    :return: set of nodes
    """
    return set.union(*(nx.descendants(D, r) for r in roots & D.nodes))


def descendant_of_through(D, roots, through):
    """
    Find out which of the roots a node is a descendant of through a directed path that has to go through a node given in "through".
    :param D:
    :param roots:
    :param through:
    :return:
    """
    descOfRoot = descendant_of(D, roots)
    descOfThrough = descendant_of(D, through)
    # empty set included in set.union so we avoid error in case of no elements in ts
    return {
        n: set.union(set(), *(descOfRoot[t] for t in ts))
        for n, ts in descOfThrough.items()
    }


def reachable(D, roots):
    descOf = descendant_of(D, roots)
    # add start nodes as "descendants" to themselves, so not strictly descendants anymore.
    for r in roots:
        if r in descOf:
            descOf[r].add(r)
    return descOf


def reachable_through(D, roots, through):
    """
    Currently always including root even if there is no path from any root to any through to the given root.
    :param D:
    :param roots:
    :param through:
    :return:
    """
    reachRoot = reachable(D, roots)
    reachThrough = reachable(D, through)
    # empty set included in set.union so we avoid error in case of no elements in ts
    reach = {
        n: set.union(set(), *(reachRoot[t] for t in ts))
        for n, ts in reachThrough.items()
    }
    for r in roots:
        if r in reach:
            reach[r].add(r)
    return reach


def any_reachable(D, roots):
    """
    Get nodes that are reachable from at least one of the roots.
    :param D: DirectedGraph
    :param roots: set of node ids or key to the graph's node sets
    :return: set of node ids
    """
    roots = D.node_set(roots)
    return descendant_of_any(D, roots) | (roots & D.nodes)


def remove_inf(D, weight=None):
    """
    For weighted traversal we consider a weight the length of an edge. If an edge is inf long this function can be useful to remove those.
    They are removed in a copy that is returned, the given graph is not modified.
    :param D: DirectedGraph
    :param weight: str name of edge property that may be inf
    :return: old DirectedGraph or a new modified version
    """
    if weight is None:
        return D
    inf = D.gete(**{weight: np.inf})
    if len(inf) == 0:
        return D
    _D = D.copy()
    _D.remove_edges_from(inf)
    logging.info(
        f"Made copy of graph without inf edges, reducing it from {len(D)} to {len(_D)} nodes and from {nx.number_of_edges(D)} to {nx.number_of_edges(_D)} edges."
    )
    return _D
