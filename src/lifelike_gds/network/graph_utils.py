#!/usr/bin/env python3
import itertools as it
import logging
import networkx as nx
import numpy as np
import sys
from typing import List, Optional, TypeAlias

from lifelike_gds.network.collection_utils import (
    dict2str,
    union as clxn_u_union,
)
from lifelike_gds.network.graph_props import (
    from_multi_edges,
    get_all_node_props,
    get_node_prop,
    get_node_prop_dict,
    get_node_prop_func,
    get_node_props,
    get_node_props_dict,
    get_nodes_by_func,
    get_nodes_by_prop,
    get_edge_prop,
    get_edge_props,
    get_edge_prop_dict,
    get_edge_props_dict,
    get_edges_by_func,
    get_edges_by_prop,
    get_edges_by_prop_match,
    set_edge_props,
    set_node_props,
    set_node_props_value,
)

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO, force=True)

DirectedGraphLike: TypeAlias = "DirectedGraph | MultiDirectedGraph"


# GETTERS


def get_leaves(D: DirectedGraphLike) -> set:
    """
    Return leaf nodes in a directed graph.

    Leaves are defined as nodes with out-degree ``0`` and in-degree greater
    than ``0``. Isolates are excluded because they are treated separately,
    often as storage for nodes hidden inside collapsed edges.

    :param D: Directed graph to inspect.
    :return: Set of leaf node ids.
    """
    return {n for n, d in D.out_degree() if d == 0} - set(nx.isolates(D))


def get_roots(D: DirectedGraphLike) -> set:
    """
    Return root nodes in a directed graph.

    Roots are defined as nodes with in-degree ``0`` and out-degree greater than
    ``0``. Isolates are excluded.

    :param D: Directed graph to inspect.
    :return: Set of root node ids.
    """
    return {n for n, d in D.in_degree() if d == 0} - set(nx.isolates(D))


# MODIFY GRAPH


def subgraph(G, nodes):
    """
    Apparently recursion error can appear for large graphs when taking subgraph.
    Change the limit temporarily.
    :param G:
    :param nodes:
    :return:
    """
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(len(G))
    _G = G.subgraph(nodes)
    sys.setrecursionlimit(limit)
    return _G


def graph_filter_inplace(G, *nodes):
    for ns in nodes:
        for i, n in enumerate(ns):
            if not n in G:
                del ns[i]


def trim_leaves(D: DirectedGraphLike, exclude=None) -> DirectedGraphLike:
    """
    Remove leaves from a directed graph until none remain.

    :param D: Directed graph to trim.
    :param exclude: Nodes to preserve, given either as a set of node ids or as
        a key in ``D.graph["node_sets"]``.
    :return: The modified graph ``D``.
    """
    if exclude is None:
        leaves = get_leaves(D)
        while len(leaves) > 0:
            D.remove_nodes_from(leaves)
            leaves = get_leaves(D)
    else:
        exclude = D.node_set(exclude)
        leaves = get_leaves(D).difference(exclude)
        while len(leaves) > 0:
            D.remove_nodes_from(leaves)
            leaves = get_leaves(D).difference(exclude)

    return D


def trim_roots(D: DirectedGraphLike, exclude=None) -> DirectedGraphLike:
    """
    Remove roots from a directed graph until none remain.

    :param D: Directed graph to trim.
    :param exclude: Nodes to preserve while trimming roots.
    :return: The modified graph ``D``.
    """
    if exclude is None:
        roots = get_roots(D)
        while len(roots) > 0:
            D.remove_nodes_from(roots)
            roots = get_roots(D)
    else:
        roots = get_roots(D).difference(exclude)
        while len(roots) > 0:
            D.remove_nodes_from(roots)
            roots = get_roots(D).difference(exclude)

    return D


def trim_leaves_collapsed(
    D: DirectedGraphLike, exclude=None
) -> DirectedGraphLike:
    """
    Trim leaves while preserving metadata for nodes hidden in collapsed edges.

    :param D: Directed graph to trim.
    :param exclude: Nodes to preserve while trimming leaves.
    :return: The modified graph ``D``.
    """
    node_props = D.getd(nodes=get_collapsed_edge_nodes(D))
    trim_leaves(D, exclude)
    # keep data only for the nodes that are still present within collapsed edges, not all nodes that used to be referenced
    D.add_nodes_from((n, node_props[n]) for n in get_collapsed_edge_nodes(D))
    return D


def trim_roots_collapsed(
    D: DirectedGraphLike, exclude=None
) -> DirectedGraphLike:
    """
    Trim roots while preserving metadata for nodes hidden in collapsed edges.

    :param D: Directed graph to trim.
    :param exclude: Nodes to preserve while trimming roots.
    :return: The modified graph ``D``.
    """
    node_props = D.getd(nodes=get_collapsed_edge_nodes(D))
    trim_roots(D, exclude)
    # keep data only for the nodes that are still present within collapsed edges, not all nodes that used to be referenced
    D.add_nodes_from((n, node_props[n]) for n in get_collapsed_edge_nodes(D))
    return D


def remove_nodes(G, *nodes, copy=True):
    if copy:
        G = G.copy()
    G.remove_nodes_from(clxn_u_union(*nodes))
    return G


def keep_nodes(G, *nodes, copy=True):
    if copy:
        G = G.copy()
    G.remove_nodes_from(set(G) - clxn_u_union(*nodes))
    return G


def remove_edges(G, *edges, copy=True):
    if copy:
        G = G.copy()
    G.remove_edges_from(clxn_u_union(*edges))
    return G


def keep_edges(G, *edges, copy=True):
    if copy:
        G = G.copy()
    G.remove_edges_from(set(G) - clxn_u_union(*edges))
    return G


def remove_node_edges(G, nodes):
    """
    Remove edges that involve a set of nodes without removing the nodes.
    :param G:
    :param nodes:
    :return:
    """
    G.remove_edges_from(set(G.in_edges(nodes)) | set(G.out_edges(nodes)))


def graph_union(*Gs):
    """
    Different from nx.union where the graphs cannot overlap.
    :param Gs:
    :return:
    """
    R = MultiDirectedGraph() if any(G.is_multigraph() for G in Gs) else DirectedGraph()

    for G in Gs:
        R.add_nodes_from(G.nodes(data=True))
        R.add_edges_from(G.edges(data=True))

    if all(G.name != "" for G in Gs):
        message = ["Union of graphs: " + ", ".join(f'"{G.name}"' for G in Gs) + "."]
    else:
        message = [f"Union of {len(Gs)} graphs."]
        R.name = "+".join(G.name for G in Gs)
    message.append(
        "Union of "
        + ", ".join(str(G.number_of_nodes()) for G in Gs)
        + f" nodes = {R.number_of_nodes()}."
    )
    message.append(
        "Union of "
        + ", ".join(str(G.number_of_edges()) for G in Gs)
        + f" edges = {R.number_of_edges()}."
    )
    R.log(" ".join(message))

    for G in Gs:
        # add graph properties, keep nothing in cases of conflict.
        if "node_sets" in G.graph:
            for k, ns in G.graph["node_sets"].items():
                ns = set(ns)
                R_ns = R.graph.setdefault("node_sets", {}).setdefault(k, ns)
                if R_ns != ns:
                    before = len(R_ns)
                    R_ns |= ns
                    string = f'Different node set "{k}" found'
                    if "name" in G.graph:
                        string += f' in e.g. "{G.name}"'
                    string += f". Union of {before} and {len(ns)} elements became {len(R_ns)}."
                    logging.warning(string)
                    R.log(string)

    for G in Gs:
        if "trace_networks" in G.graph:
            R.graph.setdefault("trace_networks", []).extend(G.graph["trace_networks"])

    _meta_union(R, Gs, "_node_sets")
    _meta_union(R, Gs, "node_props")

    return R


def _meta_union(R, Gs, meta_key):
    for G in Gs:
        if meta_key in G.graph:
            for key, meta in G.graph[meta_key].items():
                if key not in R.graph.setdefault(meta_key, {}):
                    R.graph[meta_key][key] = meta
                else:
                    meta_R = R.graph[meta_key][key]
                    if meta_R == meta:
                        continue
                    if all(k in meta and meta[k] == v for k, v in meta_R.items()):
                        logging.info(
                            f'Adding {", ".join(meta.keys() - meta_R.keys())} to the {meta_key} {key}.'
                        )
                    else:
                        logging.warning(f"Updating {meta_key} {key}.")
                    meta_R.update(meta)


def get_largest_component(D: DirectedGraphLike, start_nodes):
    """
    Keep only the largest weakly connected component of a directed graph.

    :param D: Directed graph whose components should be examined.
    :param start_nodes: Starting nodes to retain if they remain in the largest
        component.
    :return: Tuple of ``(subgraph, filtered_start_nodes)``.
    """
    # the graph consists of multiple disconnected components
    subDs = list(nx.weakly_connected_components(D))
    subD_lens = [len(g) for g in subDs]
    n_largest = max(subD_lens)
    n_total = sum(subD_lens)
    logging.info(
        "Largest connected component contains {:d}/{:d}={:.2f}% nodes".format(
            n_largest, n_total, n_largest / n_total * 100
        )
    )

    # only use the largest connected component
    D = D.subgraph(subDs[np.argmax(subD_lens)])
    start_nodes = [s for s in start_nodes if s in D]
    return D, start_nodes


def collapse_nodes(D: DirectedGraphLike, nodes) -> "MultiDirectedGraph":
    """
    Collapse intermediate nodes into edge metadata.

    :param D: Directed graph to transform.
    :param nodes: Set of node ids to collapse.
    :return: New ``MultiDirectedGraph`` with collapsed edges.
    """
    MD = MultiDirectedGraph(D)
    for n in nodes:
        # new edges are created between all combinations of original in-edges and out-edges
        for pred in D.predecessors(n):
            for succ in D.successors(n):
                MD.add_edge(pred, succ, inedge=D[pred][n], outedge=D[n][succ], node=n)

    # remove the edges that involve the nodes but don't remove the nodes themselves since we need their properties
    remove_node_edges(MD, nodes)
    return MD


def expand_nodes(MD, expand_paths=False):
    """
    Inverse of the collapse_nodes function.
    Finds nodes buried in collapsed edges under "node", "inedge" and "outedge" props.
    :param MD: collapsed MultiDirectedGraph.
    :param expand_paths: If True then also modify paths so they connect in the expanded schema.
    :return: un-collapsed MultiDirectedGraph.
    """
    if expand_paths:
        # TODO: add someting like
        #  all_shortest_max2_paths_along(D_g2m_e, *updown2aak1)
        #  or do it only for each add_edge/remove_edge operation
        raise NotImplementedError
    D = MD.copy()
    for u, v, k, d in MD.edges(data=True, keys=True):
        if {"node", "inedge", "outedge"} <= d.keys():
            D.add_edge(u, d["node"], **d["inedge"])
            D.add_edge(d["node"], v, **d["outedge"])
            D.remove_edge(u, v, k)
    return D


def get_collapsed_edge_nodes(D: DirectedGraphLike) -> set:
    return set(_get_collapsed_edge_nodes(D))


def _get_collapsed_edge_nodes(D: DirectedGraphLike):
    """
    Yield node ids referenced inside collapsed-edge metadata.

    :param D: Directed graph whose edge metadata should be scanned.
    :return: Iterator of node ids mentioned in edge ``nodes`` metadata or in
        nested ``inedge``/``outedge`` metadata.
    """
    for u, v, d in D.edges(data=True):
        for n in d.get("nodes", set()):
            yield n
        if "inedge" in d:
            for n in d["inedge"].get("nodes", set()):
                yield n
        if "outedge" in d:
            for n in d["outedge"].get("nodes", set()):
                yield n


# PATHS


def get_path_edges(path):
    """
    Get the unique edges found in a path assuming the path follows the direction of edges if they are directed.
    :param path:
    :return:
    """
    return set(zip(path[:-1], path[1:]))


def get_path_directed_edges(D: DirectedGraphLike, path) -> set:
    """
    Get unique edges found in a path which may walk edges against the direction.
    The edges will in that case be returned flipped as to list unique edges as they are directed in the graph.
    Assumes that either the edge or its flipped version are in the graph.
    :param D: Directed graph used to determine canonical edge direction.
    :param path: node path
    :return: set of edge tuples
    """
    edges = get_path_edges(path)
    D_edges = edges & set(
        D.edges()
    )  # using this instead of D.edges since the latter will give 3-tuples for multi graph
    flipped = edges - D_edges
    return D_edges | {e[::-1] for e in flipped}


def get_edge_path(path):
    """

    :param path: list of nodes ids.
    :return: list of edge (node source, node target) tuples in the direction of walking, not necessarily the direction of the edge.
    """
    return list(zip(path[:-1], path[1:]))


def get_edge_paths(paths):
    """
    Convert node path to edge path, which is the same as getting non-unique edges separately for multiple node paths.
    :param paths:
    :return:
    """
    return [get_edge_path(p) for p in paths]


def get_directed_edge_paths(D: DirectedGraphLike, paths):
    """
    Convert node path to edge path where edges not found in D are flipped, assuming that they are present but were traversed against their direction.

    :param D: Directed graph used to orient edges.
    :param paths: Iterable of node paths.
    :return: List of edge paths whose edge tuples match the direction stored in
        ``D``.
    """
    edge_paths = get_edge_paths(paths)
    for ep in edge_paths:
        for i, e in enumerate(ep):
            if e not in D.edges:
                ep[i] = e[::-1]
    return edge_paths


def edge_path_nodes(edge_path):
    starts = [u for u, _ in edge_path]
    ends = [v for _, v in edge_path]
    assert starts[1:] == ends[:-1], "Intermediary nodes doesn't match in edge path"
    return starts + [ends[-1]]


def get_node_paths(edge_paths):
    return [edge_path_nodes(p) for p in edge_paths]


def get_edges(paths):
    return [e for p in paths for e in zip(p[:-1], p[1:])]


def get_unique_edges(paths):
    return {e for p in paths for e in zip(p[:-1], p[1:])}


def get_ends_edges(paths):
    """
    Get unique edges for each unique end node
    :param paths: list of lists of node ids
    :return: {end0: {(source0, target0), (...), ...}, end1: {(...), (...), ...}}
    """
    out = {p[-1]: set() for p in paths}
    for p in paths:
        out[p[-1]] |= get_path_edges(p)
    return out


def get_node_visits(paths):
    visits = {n: 0 for p in paths for n in p}
    for p in paths:
        for n in p:
            visits[n] += 1
    return visits


def add_visits(G, paths, key="visits"):
    add_node_visits(G, paths, key)
    add_edge_visits(G, paths, key)


def add_node_visits(G, paths, key="visits"):
    set_node_props_value(G, 0, **{key: get_node_visits(paths)})


def add_edge_visits(G, paths, key="visits"):
    for f, t, d in G.edges(data=True):
        d[key] = 0
    for p in paths:
        for f, t in zip(p[:-1], p[1:]):
            G[f][t][key] += 1


def path_product(*paths):
    """
    given "paths" where each element are a list of interchangeable paths.
    Do a itertool product so we get all combinations of paths through each of the interchangeable options.
    :param paths: list of lists of lists of node ids. First layer is the ordering. Second layer is alternative paths. Third layer is node ids.
    :return: list of lists of node ids.
    """
    chains = [list(it.chain(*prods)) for prods in it.product(*paths)]
    # in most cases one would probably be doing something like [1, 2, 3] + [3, 4, 5] so we remove the duplicate ends/starts (3)
    for i, chain in enumerate(chains):
        chain = np.asarray(chain)
        chains[i] = [chains[i][0]] + list(chain[1:][chain[1:] != chain[:-1]])

    return chains


def get_node_shortest(paths):
    """
    For each node among paths get length of shortest path that it is part of.
    :param paths:
    :return:
    """
    shortest = {}
    for p in paths:
        l = len(p) - 1
        for n in p:
            shortest[n] = min(shortest.get(n, 9999), l)
    return shortest


def set_shortest(G, paths, key="shortest"):
    set_node_shortest(G, paths, key)
    set_edge_shortest(G, paths, key)
    for n, d in G.nodes(data=True):
        if d[key] == 999:
            d[key] = None


def set_node_shortest(G, paths, key="shortest"):
    set_node_props_value(G, default=999, **{key: get_node_shortest(paths)})


def set_edge_shortest(G, paths, key="shortest"):
    for f, t, d in G.edges(data=True):
        d[key] = 999
    for p in paths:
        l = len(p) - 1
        for f, t in zip(p[:-1], p[1:]):
            G[f][t][key] = min(G[f][t][key], l)


def get_node_starts(paths):
    """
    Get unique starting points leading to each unique node.
    :param paths:
    :return:
    """
    starts = {n: set() for p in paths for n in p}
    for p in paths:
        for n in p:
            starts[n].add(p[0])
    return starts


def get_node_ends(paths):
    """
    Get unique end points leading to each unique node.
    :param paths:
    :return: {node0: {end1, end4, ...}, node1: {...}, ...}
    """
    ends = {n: set() for p in paths for n in p}
    for p in paths:
        for n in p:
            ends[n].add(p[-1])
    return ends


def get_nEdgePaths(edge_paths, i=0):
    """
    Get number of paths that each starting node starts.
    :param edge_paths: list of edge paths.
    :param i: index of node to look for, i.e. 0 or -1 to get start or end node of each path.
    :return: dict mapping from node ids to the number of edge paths they are at the beginning of.
    """
    starts = [p[i][i] for p in edge_paths]
    return dict(zip(*np.unique(starts, return_counts=True)))


def get_path_label_count(D: DirectedGraphLike, path, label):
    return sum(1 for n in path if label in D.nodes[n]["labels"])


# CLASS


class DirectedGraph(nx.DiGraph):
    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        # make sure some properties are deeper copies
        for k in ["node_sets", "log"]:
            if k in self.graph:
                self.graph[k] = self.graph[k].copy()

    def copy(self, as_view=False):
        out = super().copy(self)
        # make sure some properties are deeper copies
        for k in ["node_sets", "log"]:
            if k in out.graph:
                out.graph[k] = self.graph[k].copy()
        return out

    def get(
        self, *props, nodes=None, insensitive=False, func_filter=None, **prop_filter
    ):
        """
        Central access point for getting nodes and node properties.
        :param props: str, list or set of str. Optionally return specific properties. Default is node ids if prop_filter is given or all properties if nodes are given.
        :param nodes: optionally filter by node id
        :param insensitive: bool. Should string prop filters be case insensitive comparisons?
        :param func_filter: optionally function for filtering given node dict returning bool
        :param prop_filter: optionally filter by property values or funcs on values
        :return: list
        """
        # first the node selection
        if len(prop_filter) > 0:
            nodes = get_nodes_by_prop(
                self, nodes, insensitive=insensitive, **prop_filter
            )
        if func_filter is not None:
            nodes = get_nodes_by_func(self, func_filter, nodes=nodes)
        # Are we doing a node selection?
        if len(props) == 0:
            # did we do a node selection?
            if len(prop_filter) > 0 or func_filter is not None:
                return nodes
            # return all properties for the given nodes.
            if nodes is None:
                nodes = self.nodes
            return [self.nodes[n] for n in nodes]
        # return prop or props
        elif len(props) == 1:
            if props[0] == "all":
                return get_all_node_props(self, nodes)
            return get_node_prop(self, props[0], nodes)
        return get_node_props(self, props, nodes)

    def getd(
        self, *props, nodes=None, insensitive=False, func_filter=None, **prop_filter
    ):
        """
        Same as get, but return dicts when applicable.
        :param props: str node prop key, or a function of node prop dict. The latter is only implemented for single prop arg.
        :param nodes:
        :param insensitive: bool. Should string prop filters be case insensitive comparisons?
        :param func_filter: optionally function for filtering given node dict returning bool
        :param prop_filter:
        :return:
        """
        # first the node selection
        if len(prop_filter) > 0:
            nodes = get_nodes_by_prop(
                self, nodes, insensitive=insensitive, **prop_filter
            )
        if func_filter is not None:
            nodes = get_nodes_by_func(self, func_filter, nodes=nodes)
        # Are we doing a node selection?
        if len(props) == 0:
            # return all properties for the given/filtered nodes.
            if nodes is None:
                nodes = self.nodes
            return {n: self.nodes[n] for n in nodes}
        # return prop or props
        elif len(props) == 1:
            if callable(props[0]):
                return get_node_prop_func(self, props[0], nodes)
            else:
                return get_node_prop_dict(self, props[0], nodes)
        return get_node_props_dict(self, props, nodes)

    def gete(
        self, *props, edges=None, insensitive=False, func_filter=None, **prop_filters
    ):
        """
        Central access point for getting edges and edge properties. Only if something is found is it returned.
        :param props: str, list or set of str. Optionally return specific properties. Default is edge ids if prop_filter is given or all properties if edges are given.
        :param edges: optionally filter by (source id, target id) tuples
        :param insensitive: bool. Should string prop filters be case insensitive comparisons?
        :param func_filter: optionally function for filtering given edge dict returning bool
        :param prop_filters: optionally filter by property values
        :return: list
        """
        # first the edge selection
        if len(prop_filters) > 0:
            edges = get_edges_by_prop(
                self, edges, insensitive=insensitive, **prop_filters
            )
        if func_filter is not None:
            edges = get_edges_by_func(self, func_filter, edges=edges)
        # Are we doing an edge selection?
        if len(props) == 0:
            # did we do a node selection?
            if len(prop_filters) > 0 or func_filter is not None:
                return edges
            # return all properties for the given nodes.
            if edges is None:
                edges = self.edges
            return [self.edges[e] for e in edges]
        # return prop or props
        elif len(props) == 1:
            return get_edge_prop(self, props[0], edges)
        return get_edge_props(self, props, edges)

    def geted(
        self, *props, edges=None, insensitive=False, func_filter=None, **prop_filters
    ):
        """
        Same as gete, but return dicts with keys when values are found.
        Central access point for getting edges and edge properties. Only if something is found is it returned.
        :param props: str, list or set of str. Optionally return specific properties. Default is edge ids if prop_filter is given or all properties if edges are given.
        :param edges: optionally filter by (source id, target id) tuples
        :param insensitive: bool. Should string prop filters be case insensitive comparisons?
        :param func_filter: optionally function for filtering given edge dict returning bool
        :param prop_filters: optionally filter by property values
        :return: list
        """
        # first the edge selection
        if len(prop_filters) > 0:
            edges = get_edges_by_prop_match(
                self, edges, insensitive=insensitive, **prop_filters
            )
        if func_filter is not None:
            edges = get_edges_by_func(self, func_filter, edges=edges)
        # Are we doing an edge selection?
        if len(props) == 0:
            # return all properties for the given/filtered edges.
            if edges is None:
                edges = self.edges
            return {e: self.edges[e] for e in edges}
        # return prop or props
        elif len(props) == 1:
            return get_edge_prop_dict(self, props[0], edges)
        return get_edge_props_dict(self, props, edges)

    def set(self, *nodes, default=None, **props):
        """
        Set node properties.
        :param nodes: Node selection for setting the properties.
        :param default: Default value to set for any node not in "nodes" or when using a function, if the function fails due to a missing property (KeyError)
        :param props: keys are node prop name, value is either a scalar to set on all nodes in "nodes", a dict mapping node to value or a function of node props dict.
        :return:
        """
        if "nodes" in props:
            # added here by mistake. We fix this quietly.
            nodes = (*nodes, props["nodes"])
            del props["nodes"]
        # if no nodes selection is given then we change all nodes. This is different from the case where an empty set of nodes were given.
        elif len(nodes) == 0:
            nodes = (self.nodes,)
        nodes = [self.node_set(ns) for ns in nodes]
        set_node_props(self, *nodes, default=default, **props)

    def sete(self, *edges, default=None, **props):
        """
        Set edge properties.
        :param edges:
        :param default:
        :param props:
        :return:
        """
        if "edges" in props:
            # added here by mistake. We fix this quietly.
            edges = (*edges, props["edges"])
            del props["edges"]
        # if no edge selection is given then we change all edges. This is different from the case where an empty set of edges were given.
        elif len(edges) == 0:
            edges = (self.edges,)
        set_edge_props(self, *edges, default=default, **props)

    def remove(self, *nodes, copy=True, func_filter=None, **prop_filters):
        """
        Remove nodes.
        :param nodes: sets of nodes to remove
        :param copy: remove from a copy or inplace?
        :param func_filter: selection function passed to self.get function
        :param prop_filters: node selection criteria passed to self.get function
        :return: graph with some nodes removed
        """
        # starting with set allows for entries of "nodes" to be list instead of having to be set.
        nodes = set.union(set(), *nodes)
        if len(nodes) == 0:
            nodes = None
        if func_filter is not None or len(prop_filters) > 0:
            nodes = self.get(nodes=nodes, func_filter=func_filter, **prop_filters)
        out = remove_nodes(self, nodes, copy=copy)

        if len(nodes) == 0:
            logging.info("No nodes were removed.")
        message = [f"Removed {len(nodes)} nodes reducing size to {len(out)}."]
        if func_filter is not None:
            message.append("A function filter was applied.")
        if len(prop_filters) > 0:
            message.append(
                f"Nodes were removed with the properties: {dict2str(prop_filters)}."
            )
        out.log(" ".join(message))

        return out

    def removee(self, *edges, copy=True, func_filter=None, **prop_filters):
        """
        Remove edges.
        :param edges: sets of edges to remove
        :param copy: remove from a copy or inplace?
        :param func_filter: selection function passed to self.gete function
        :param prop_filters: edge selection criteria passed to self.gete function
        :return: graph with some edges removed
        """
        # starting with set allows for entries of "edges" to be list instead of having to be set.
        edges = set.union(set(), *edges)
        if len(edges) == 0:
            edges = None
        if func_filter is not None or len(prop_filters) > 0:
            edges = self.gete(edges=edges, func_filter=func_filter, **prop_filters)
        out = remove_edges(self, edges, copy=copy)

        if len(edges) == 0:
            logging.info("No edges were removed.")
        message = [
            f"Removed {len(edges)} edges reducing number of edges to {out.number_of_edges()}."
        ]
        if func_filter is not None:
            message.append("A function filter was applied.")
        if len(prop_filters) > 0:
            message.append(
                f"Edges were removed with the properties: {dict2str(prop_filters)}."
            )
        out.log(" ".join(message))

        return out

    def keep(self, *nodes, copy=True, func_filter=None, **prop_filters):
        """
        Remove nodes by indicating what to keep (subgraph).
        :param nodes: sets of nodes to keep
        :param copy: keep from a copy or inplace?
        :param func_filter: selection function passed to self.get function
        :param prop_filters: node selection criteria passed to self.get function
        :return: graph with some nodes removed
        """
        nodes = set.union(*nodes)
        if len(nodes) == 0:
            nodes = None
        if func_filter is not None or len(prop_filters) > 0:
            nodes = self.get(nodes=nodes, func_filter=func_filter, **prop_filters)
        return keep_nodes(self, nodes, copy=copy)

    def keepe(self, *edges, copy=True, func_filter=None, **prop_filters):
        """
        Remove edges by indicating which to keep.
        :param edges: sets of edges to keep
        :param copy: keep from a copy or inplace?
        :param func_filter: selection function passed to self.gete function
        :param prop_filters: edge selection criteria passed to self.gete function
        :return: graph with some edges removed
        """
        edges = set.union(*edges)
        if len(edges) == 0:
            edges = None
        if func_filter is not None or len(prop_filters) > 0:
            edges = self.gete(edges=edges, func_filter=func_filter, **prop_filters)
        return keep_edges(self, edges, copy=copy)

    def get_successors(self, nodes):
        """
        Get successors of multiple nodes that doesn't have to be present in the graph.
        :param nodes: iterable of nodes that may not all be in the graph.
        :return: set of nodes that have edges from the given nodes.
        """
        return {s for n in set(self).intersection(nodes) for s in self.successors(n)}

    def get_predecessors(self, nodes):
        """
        Get predecessors of multiple nodes that doesn't have to be present in the graph.
        :param nodes: iterable of nodes that may not all be in the graph.
        :return: set of nodes that have edges toward the given nodes.
        """
        return {p for n in set(self).intersection(nodes) for p in self.predecessors(n)}

    def has_in(self, nodes, exclude=True):
        """
        Does a set of nodes have in-edges?
        :param nodes: set of nodes
        :param exclude: set of nodes, None or bool. If True (Default) use "nodes".
        """
        if exclude is True:
            exclude = nodes
        elif exclude is False or exclude is None:
            exclude = set()
        return len(self.get_predecessors(nodes) - exclude) > 0

    def has_out(self, nodes, exclude=True):
        """
        Does a set of nodes have out-edges?
        :param nodes: set of nodes
        :param exclude: set of nodes or bool. If True (Default) use "nodes".
        """
        if exclude is True:
            exclude = nodes
        elif exclude is False or exclude is None:
            exclude = set()
        return len(self.get_successors(nodes) - exclude) > 0

    def node_set(self, key_or_set):
        """
        Get a node set in the graph given a key or simply return the input if it is not supposed to be a key to a node set.
        :param key_or_set: None, set of node ids, or node_set key
        :return: set of node ids or None
        """
        if key_or_set is None:
            return None
        if not np.isscalar(key_or_set):
            return set(key_or_set)
        try:
            node_set = self.graph["node_sets"][key_or_set]
        except KeyError:
            # is it a single node id?
            if key_or_set in self:
                return {key_or_set}
            # is a bool node property?
            nodes = self.get(**{key_or_set: True})
            if len(nodes) > 0:
                return nodes
            # key is missing
            raise
        else:
            # node set is found, if it has meta data return the set
            try:
                return node_set["nodes"]
            except TypeError:
                return node_set

    def get_node_set_name(self, key):
        try:
            return self.graph["_node_sets"][key]["name"]
        except KeyError:
            return key

    def get_node_set_description(self, key):
        try:
            return self.graph["_node_sets"][key]["description"]
        except KeyError:
            return self.get_node_set_name(key)

    def set_node_set(self, key: str, nodes, **meta):
        """
        structured as "graph"."node_sets".node_set_key.(set of nodes node)
        and meta under "graph"."_node_sets".node_set_key.meta_property_key.meta_property_value
        So we currently store node set meta data in separate entry "_node_sets" so "node_sets" has backwards compatibility
        :param key: key to store node set under (and to store node set meta under)
        :param nodes: single node id or set of node ids
        :param meta: meta properties for node sets, e.g. name=..., description=...
        :return:
        """
        if np.isscalar(nodes):
            nodes = {nodes}
        else:
            nodes = set(nodes)
        self.graph.setdefault("node_sets", {})[key] = nodes
        if len(meta) > 0:
            self.graph.setdefault("_node_sets", {}).setdefault(key, {}).update(meta)

    def node_set_key(self, key_or_set, default_key=None):
        """
        Get a node set and its key, i.e. key in D.graph["node_sets"] in a flexible manner.
        If it does not exist in D.graph["node_sets"] it will be added and returned.
        If a node set is given without a name but is found in D.graph["node_sets"] the one found in D.graph["node_sets"] will be returned with its key.
        If the name is found as key in D.graph["node_sets"] and the set is different then the set will be overwritten with a warning.
        :param key_or_set: key in D.graph["node_sets"] or a node set
        :param default_key: optional key in D.graph["node_sets"] which is only used if key_or_set is a set.
        :return: set of node ids, str key if a key in D.graph["node_sets"] contains the node set after this call.
        """
        assert (
            key_or_set is not None
        ), "None not accepted for key_or_set in node_set_name"
        # make sure we have the node_sets defined if we use them. Lazy loading.
        self.graph.setdefault("node_sets", {})
        node_set = self.node_set(key_or_set)
        # a key was given in key_or_set
        if type(node_set) is set and np.isscalar(key_or_set):
            return node_set, key_or_set
        # is the given set new?
        elif not node_set in self.graph["node_sets"].values():
            assert default_key is not None, "Can't add set without default_key set"
            if (
                default_key in self.graph["node_sets"]
                and node_set != self.graph["node_sets"][default_key]
            ):
                logging.warning(f"Overwriting {default_key}")
            self.graph["node_sets"][default_key] = set(node_set)
            return node_set, default_key
        else:
            # given set already exists, find it (first match).
            # return its existing key, ignore default_key
            for k, s in self.graph["node_sets"].items():
                if s == node_set:
                    return node_set, k

    def log(self, text):
        """
        This is not a setter, but rather an appender. Add textual description to the graph for each operation done to the graph.
        :param text: str to append after newline.
        :return: Full log text, after it is edited in-place
        """
        if "log" in self.graph:
            self.graph["log"].append(text)
        else:
            self.graph["log"] = [text]
        return self.graph["log"][-1]

    def get_log(self, n=None):
        """
        Get string from logging, optionally for a limited number of recent logs.
        :param n: number of recent logs to return, default all.
        :return: str
        """
        logs = self.graph.get("log", [])
        if n is None:
            return "\n".join(logs)
        return "\n".join(logs[-n:])

    def describe(self, text):
        if "description" not in self.graph:
            self.graph["description"] = text
        else:
            self.graph["description"] += "\n" + text

    def get_node_prop_name(self, node_prop_key):
        try:
            return self.graph["node_props"][node_prop_key]["name"]
        except KeyError:
            return node_prop_key

    def get_node_prop_description(self, node_prop_key):
        try:
            return self.graph["node_props"][node_prop_key]["description"]
        except KeyError:
            return self.get_node_prop_name(node_prop_key)

    def name_node_props(self, **node_prop_names):
        """
        Add human readable names for node properties.
        Structure is "graph"."node_props".node_prop_key."name".node_prop_name
        :param node_prop_names: k=node prop key, v=text name
        :return:
        """
        node_props = self.graph.setdefault("node_props", {})
        for node_prop_key, node_prop_name in node_prop_names.items():
            node_props.setdefault(node_prop_key, {})["name"] = node_prop_name

    def describe_node_props(self, **node_prop_descriptions):
        """
        Add human readable descriptions for node properties.
        Structure is "graph"."node_props".node_prop_key."description".node_prop_description
        :param node_prop_descriptions: k=node prop key, v=text description
        :return:
        """
        node_props = self.graph.setdefault("node_props", {})
        for node_prop_key, node_prop_description in node_prop_descriptions.items():
            node_props.setdefault(node_prop_key, {})[
                "description"
            ] = node_prop_description

    def _get_query_prop_for_tn(
        self, sources_key: str, targets_key: str, sources, targets, query: str = None
    ) -> str:
        """Generates a string meant to be used as the value of the 'query' property for trace networks.


        Args:
            sources_key (str):
            targets_key (str):
            sources: key in self.graph["node_sets"].
            targets: same as sources, except for targets.
            query (str, optional): String to indicate the query set key. Defaults to None.

        Returns:
            str: String representing the 'query' property for a trace network.
        """
        # Set the trace network 'query' property
        if query is None:
            if len(sources) >= len(targets):
                query_log_message = f'Setting trace network "query" to {sources_key} since it is a bigger node set than {targets_key}.'
                retval = sources_key
            else:
                query_log_message = f'Setting trace network "query" to {targets_key} since it is a bigger node set than {sources_key}.'
                retval = targets_key
            logging.info(query_log_message + ' Use "query" arg to avoid this.')
            self.describe(query_log_message)
            return retval
        else:
            return query

    def _get_name_prop_for_tn(
        self, method: str, sources_key: str, targets_key: str, name: str = None
    ) -> str:
        """Generates a string meant to be used as the value of the 'name' property for trace networks.


        Args:
            method (str): String representing the method used to generate node_paths.
            sources_key (str):
            targets_key (str):
            name (str, optional): Name of the trace network.

        Returns:
            str: String representing the 'name' property for a trace network.
        """

        retval = f"{sources_key} -[{method}]-> {targets_key}" if name is None else name
        if retval in {tn["name"] for tn in self.graph["trace_networks"]}:
            raise ValueError("Trace network name already in use")
        return retval

    def _get_default_sizing_prop_for_tn(
        self, method: str, default_sizing: str = None
    ) -> str:
        """Generates a string meant to be used as the value of the 'name' property for trace networks.


        Args:
            method (str): String representing the method used to generate node_paths.
            default_sizing (str, optional): Name of default sizing definition for the trace network.

        Returns:
            str: String representing the 'default_sizing' property for a trace network.
        """
        return method if default_sizing is None else default_sizing

    def set_sizing(self, key, node_sizing=None, link_sizing=None, **meta):
        """
        Add or set a sizing definition.
        A sizing definition has a name, node sizing property key, link sizing property key and optionally a description.
        :param key: Sizing definition key.
        :param node_sizing: default to name param
        :param link_sizing: default to name param + "_contribution"
        :param meta: e.g. name="...", description="..."
        :return:
        """
        if node_sizing is None:
            if len(self.getd(key)) == 0:
                raise NotImplementedError(
                    f"{key} is not a node property. Using edge property is yet to be implemented."
                )
            node_sizing = key
        if link_sizing is None:
            link_sizing = key + "_contribution"

        sizing = {}
        try:
            sizing.update(self.graph["node_props"][key])
        except KeyError:
            pass
        sizing.update(dict(node_sizing=node_sizing, link_sizing=link_sizing))
        sizing.update(meta)

        sizings = self.graph.setdefault("sizing", {})
        if key not in sizings:
            sizings[key] = sizing
        elif sizings[key] != sizing:
            logging.warning(f'Modifying sizing definition "{key}".')
            sizings[key].update(sizing)

    def add_trace_network(
        self,
        sources,
        targets,
        node_paths,
        method: str,  # TODO: Need to verify that this is purely descriptive, and not evaluated as function or something later
        description: str,
        sources_key: str = None,
        targets_key: str = None,
        undirected=False,
        reverse=False,
        default_sizing=None,
        name: str = None,
        query: str = None,
    ):
        """
        Add an entry to a list self.graph["trace_networks"].


        :param self: (Multi)DirectedGraph, networkx graph will be converted.
        :param sources: key in self.graph["node_sets"].
        :param targets: same as sources, except for targets.
        :param node_paths: List of node paths objects.
        :param method: String representing the method used to generate node_paths.
        :param description: String description for the trace.
        :param sources_key: Optional string key to give to sources if "sources" is a set of node ids. Assigned a new value if None is given.
        :param targets_key: Optional string key to give to targets if "targets" is a set of node ids. Assigned a new value if None is given.
        :param undirected: Bool representing whether this trace is undirected.
        :param reverse: Bool which if true reverses source and target sets for convenience.
        :param default_sizing: Name of default sizing definition for this trace network. Assigned a new value if None is given.
        :param name: Optional string name for the trace. Assigned a new value if None is given.
        :param query: Optional string to indicate the query set key. Assigned a new value if None is given.
        """
        # TODO: Consider relaxing some of these, if a reasonable default is possible
        for arg_name, arg_val in zip(
            ["sources", "targets", "node_paths", "method", "description"],
            [sources, targets, node_paths, method, description],
        ):
            if arg_val is None:
                raise ValueError(f"Argument `{arg_name}` cannot be None.")

        trace_networks = self.graph.setdefault("trace_networks", [])

        if reverse:
            sources, targets = targets, sources
            sources_key, targets_key = targets_key, sources_key

        sources, sources_key = self.node_set_key(
            sources,
            sources_key
            if sources_key is not None
            else f"trace{len(trace_networks)}_sources",
        )
        targets, targets_key = self.node_set_key(
            targets,
            targets_key
            if targets_key is not None
            else f"trace{len(trace_networks)}_targets",
        )

        trace_network = dict(
            sources=sources_key,
            targets=targets_key,
            method=method,
            description=description,
            query=self._get_query_prop_for_tn(
                sources_key, targets_key, sources, targets, query
            ),
            name=self._get_name_prop_for_tn(method, sources_key, targets_key, name),
            default_sizing=self._get_default_sizing_prop_for_tn(method, default_sizing),
        )

        # If the sizing we set above does not already exist in the 'sizing' property, set it now
        if trace_network["default_sizing"] not in self.graph.get("sizing", {}):
            # TODO: This is truly awful, but if method = min(length) a NotImplementedError will be
            # thrown in set_sizing. I'm not really sure how else to handle this honestly.
            if method != "min(length)":
                logging.info(
                    f'Default sizing for trace network set to new sizing definition "{method}"'
                )
                self.set_sizing(method)
        else:
            logging.info(
                f'Default sizing for trace network set to weighting match "{method}"'
            )

        # with undirected we can walk edges against the direction so we should make sure to list them in the right direction
        if undirected:
            edges = [get_path_directed_edges(self, p) for p in node_paths]
        else:
            edges = [get_path_edges(p) for p in node_paths]

        if self.is_multigraph():
            edges = [from_multi_edges(self, es) for es in edges]

        n_unique_nodes = len({n for p in node_paths for n in p})
        n_unique_edges = len({e for es in edges for e in es})

        traces = {}
        for p, es in zip(node_paths, edges):
            # for a single trace we have a single start and end point but there can be multiple node paths to list
            trace = traces.setdefault((p[0], p[-1]), {})
            trace.setdefault("node_paths", []).append(p)
            trace.setdefault("edges", set()).update(es)

        # we can't use tuple as key in json so let's be consistent
        trace_network["traces"] = []
        for (source, target), trace in traces.items():
            trace["source"] = source
            trace["target"] = target
            trace_network["traces"].append(trace)

        if len(trace_network["traces"]) > 0:
            trace_networks.append(trace_network)
            self.log(
                " ".join(
                    [
                        f'Trace network "{name}" from "{sources_key}" to "{targets_key}".',
                        f'Description="{trace_network["description"]}".',
                        f'Method={trace_network["method"]}.',
                        f"Default sizing={default_sizing}.",
                        f"{n_unique_nodes} and {n_unique_edges} unique nodes and edges.",
                    ]
                )
            )
        else:
            logging.warning("No traces found.")


class MultiDirectedGraph(DirectedGraph, nx.MultiDiGraph):
    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)

    def geted(self, *props, edges=None, func_filter=None, **prop_filters):
        if edges is not None:
            edges = from_multi_edges(self, edges)
        return super().geted(
            *props, edges=edges, func_filter=func_filter, **prop_filters
        )

    def gete(self, *props, edges=None, func_filter=None, **prop_filters):
        if edges is not None:
            edges = from_multi_edges(self, edges)
        return super().gete(
            *props, edges=edges, func_filter=func_filter, **prop_filters
        )

    def sete(self, *edges, default=None, **props):
        if edges is not None:
            edges = from_multi_edges(self, edges)
        return super().sete(edges=edges, default=default, **props)
