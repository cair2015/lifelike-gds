#!/usr/bin/env python3
import logging
import networkx as nx
import numpy as np

from pathway_graphx.network.collection_utils import (
    dict_keys,
    dict_max_ties,
    dict_min_ties,
    dict_values,
    intersects,
)

logging.basicConfig(level=logging.INFO)


### GETTERS BY PROPS


def _prop_match(d, **prop_filter):
    """
    Check if there is a match for node or edge properties given in d for a filter given by prop_filter.
    :param d:
    :param prop_filter:
    :return:
    """
    for propname, filtervals in prop_filter.items():
        try:
            vals = d[propname]
        except KeyError:
            return False
        if np.isscalar(filtervals):
            filtervals = {filtervals}
        try:
            if vals in filtervals or (
                not np.isscalar(vals) and intersects(vals, filtervals)
            ):
                continue
        except TypeError:
            if intersects(vals, filtervals):
                continue
        return False
    return True


def _prop_match_insensitive(d, **prop_filter):
    """
    Check if there is a case-insensitive match for node or edge properties given in d for a filter given by prop_filter.
    Allows for non-string values, so one can mix string insensitive filtering with integer filtering without problem.
    :param d:
    :param prop_filter:
    :return:
    """
    for propname, filtervals in prop_filter.items():
        try:
            vals = d[propname]
        except KeyError:
            return False
        if np.isscalar(filtervals):
            filtervals = {filtervals}
        try:
            if np.isscalar(vals):
                vals = vals.lower()
            else:
                vals = {v.lower() for v in vals}
            filtervals = {v.lower() for v in filtervals}
        except AttributeError:
            pass  # allow for e.g. int filtering
        try:
            if vals in filtervals or (
                not np.isscalar(vals) and intersects(vals, filtervals)
            ):
                continue
        except TypeError:
            if intersects(vals, filtervals):
                continue
        return False
    return True


def _get_nodes_by_f(G, f, nodes=None):
    if nodes is None:
        return {n for n, d in G.nodes(data=True) if f(d)}
    else:
        return {n for n in nodes if f(G.nodes[n])}


def _get_edges_by_f(G, f, edges=None):
    if edges is None:
        edges = (
            G.edges(keys=True, data=True) if G.is_multigraph() else G.edges(data=True)
        )
        return {e[:-1] for e in edges if f(e[-1])}
    else:
        if G.is_multigraph():
            edges = from_multi_edges(G, edges)
        return {e for e in edges if f(G.edges[e])}


def get_nodes_by_func(G, func, nodes=None):
    def f(d):
        try:
            return func(d)
        except KeyError:
            return False

    return _get_nodes_by_f(G, f, nodes)


def get_edges_by_func(G, func, edges=None):
    """

    :param G: (multi) directed graph
    :param func:
    :param edges:
    :return:
    """

    def f(d):
        try:
            return func(d)
        except KeyError:
            return False

    return _get_edges_by_f(G, f, edges)


def get_nodes_by_prop_func(G, nodes=None, **prop_func_filter):
    """
    Get nodes from G where a function given the value of a property returns True.
    :param G: graph
    :param nodes: only among these nodes
    :param prop_func_filter: {k:v, ...}. k is the name of a property,
        for which a value will be provided to the function given in v
    :return: set of nodes
    """

    def f(d):
        try:
            for prop_key, func in prop_func_filter.items():
                if not func(d[prop_key]):
                    return False
        except KeyError:
            return False
        return True

    return _get_nodes_by_f(G, f, nodes)


def get_edges_by_prop_func(G, edges=None, **prop_func_filter):
    """
    Get nodes from G where a function given the value of a property returns True.
    :param G: graph
    :param edges: only among these edges
    :param prop_func_filter: {k:v, ...}. k is the name of a property,
        for which a value will be provided to the function given in v
    :return: set of nodes
    """

    def f(d):
        try:
            for prop_key, func in prop_func_filter.items():
                if not func(d[prop_key]):
                    return False
        except KeyError:
            return False
        return True

    return _get_edges_by_f(G, f, edges)


def get_nodes_by_prop_match(G, nodes=None, insensitive=False, **prop_filter):
    """
    Get nodes from G where there is a match between ALL given values and values found under a specific key.
    :param G:
    :param nodes: only among these nodes
    :param insensitive: bool. Should string comparisons be case-insensitive?
    :param prop_filter: look up k, match the value found against v. v can be a list of terms.
        if there are multiple k,v pairs, any match is a match
    :return:
    """
    f = _prop_match_insensitive if insensitive else _prop_match
    return get_nodes_by_func(G, lambda d: f(d, **prop_filter), nodes)


def get_edges_by_prop_match(G, edges=None, insensitive=False, **prop_filter):
    """
    Get edges from G where there is a match between ALL given values and values found under a specific key.
    :param G:
    :param edges: only among these edges
    :param insensitive: bool. Should str comparisons be case-insensitive?
    :param prop_filter: look up k, match the value found against v. v can be a list of terms.
        If there are multiple k,v pairs, any match is a match
    :return:
    """
    f = _prop_match_insensitive if insensitive else _prop_match
    return get_edges_by_func(G, lambda d: f(d, **prop_filter), edges)


def get_nodes_by_prop(G, nodes=None, insensitive=False, **prop_filters):
    """
    Get nodes from G where all filters are satisfied.
    :param G:
    :param nodes: only among these nodes
    :param insensitive: bool. Should string comparisons be case-insensitive?
    :param prop_filters: {k:v, ...} v can be either a function or a value for matching
    :return: node set
    """
    funcs = {k: v for k, v in prop_filters.items() if callable(v)}
    props = {k: v for k, v in prop_filters.items() if not callable(v)}
    if len(props) > 0:
        nodes = get_nodes_by_prop_match(G, nodes, insensitive, **props)
    if len(funcs) > 0:
        nodes = get_nodes_by_prop_func(G, nodes, **funcs)
    return nodes


def get_edges_by_prop(G, edges=None, insensitive=False, **prop_filters):
    """
    Get nodes from G where all filters are satisfied.
    :param G:
    :param edges: only among these nodes
    :param insensitive: bool. Should string comparisons be case-insensitive?
    :param prop_filters: {k:v, ...} v can be either a function or a value for matching
    :return: node set
    """
    funcs = {k: v for k, v in prop_filters.items() if callable(v)}
    props = {k: v for k, v in prop_filters.items() if not callable(v)}
    if len(props) > 0:
        edges = get_edges_by_prop_match(G, edges, insensitive, **props)
    if len(funcs) > 0:
        edges = get_edges_by_prop_func(G, edges, **funcs)
    return edges


def _get_any_nodes_by_prop(G, **kwargs):
    """
    Get nodes from G where there is a match between ANY given values and values found under a specific key.
    :param G:
    :param kwargs: look up k, match the value found against v. v can be a list of terms.
        If there are multiple k,v pairs, any match is a match
    :return:
    """

    def _get_node_property(N, key):
        try:
            return N[key]
        except KeyError:
            return N[key]

    for k, v in kwargs.items():
        if type(v) is not list:
            kwargs[k] = [v]

    for n in G:
        try:
            props = {k: _get_node_property(G.nodes[n], k) for k in kwargs.keys()}
        except KeyError:
            continue
        for k, prop in props.items():
            if prop in kwargs[k]:
                yield n
                break
            if type(prop) is list and intersects(prop, kwargs[k]):
                yield n
                break


# SETTERS ON PROPS


def set_node_props_value(G, *nodes, default=None, **props):
    """
    Add property to nodes with a name from key in props. Value is either a scalar or a dict with node ids as keys.
    :param G:
    :param nodes: "props" only applies to these specific nodes each given as a set, list or scalar
    :param default: Nodes not in the intersection between "nodes" and keys of "props"
        dict will be given a default value if this is specified
    :param props: scalar OR {"property_name": {node_id0: value0, node_id1: value1, ...}}
    :return: None
    """
    # collect nodes
    nodes = list(nodes)  # it is a tuple so we can't do index assignment
    for i, ns in enumerate(nodes):
        if np.isscalar(ns):
            nodes[i] = {ns}
    nodes = set.union(set(), *nodes)

    for propname, assign in props.items():
        if type(assign) is dict:
            if default is not None:
                if len(nodes) == 0:
                    for n, d in G.nodes(data=True):
                        d[propname] = assign.get(n, default)
                else:
                    for n in nodes:
                        G.nodes[n][propname] = assign.get(n, default)
            else:
                if len(nodes) == 0:
                    for n, val in assign.items():
                        G.nodes[n][propname] = val
                else:
                    for n in nodes & assign.keys():
                        G.nodes[n][propname] = assign[n]

        else:
            # assign scalar
            if default is not None:
                for n, d in G.nodes(data=True):
                    d[propname] = default
            for n in nodes:
                G.nodes[n][propname] = assign


def set_edge_props_value(G, *edges, default=None, **props):
    """
    Add property to edges with a name from key in props. Value is either a scalar or a dict with edge ids as keys.
    :param G:
    :param edges: "props" only applies to these specific edges each given as a set, list or scalar
    :param default: Edges not in the intersection between "edges" and keys of "props"
        dict will be given a default value if this is specified
    :param props: scalar OR
        {"property_name": {(source_node0, target_node0): value0, (source_node1, target_node1): value1, ...}}
    :return: None
    """
    # collect nodes
    edges = list(edges)  # it is a tuple so we can't do index assignment
    for i, es in enumerate(edges):
        if type(es) == tuple:
            edges[i] = {es}
    edges = set.union(set(), *edges)

    for propname, assign in props.items():
        if type(assign) is dict:
            if default is not None:
                if len(edges) == 0:
                    for u, v, d in G.edges(data=True):
                        d[propname] = assign.get((u, v), default)
                else:
                    for e in edges:
                        G.edges[e][propname] = assign.get(e, default)
            else:
                if len(edges) == 0:
                    for e, val in assign.items():
                        G.edges[e][propname] = val
                else:
                    for e in edges & assign.keys():
                        G.edges[e][propname] = assign[e]

        else:
            # assign scalar
            if default is not None:
                for u, v, d in G.edges(data=True):
                    d[propname] = default
            for e in edges:
                G.edges[e][propname] = assign


def get_edge_prop_func(G, func, default=None):
    def f(d):
        try:
            return func(d)
        except KeyError:
            return default

    out = {(u, v): f(d) for u, v, d in G.edges(data=True)}
    if default is not None:
        return out
    return {n: v for n, v in out.items() if v is not None}


def set_node_props_func(G, *nodes, default=None, **funcs):
    """
    Apply function to prop of nodes in G, then set a prop for those nodes to the function output.
    :param G:
    :param nodes:
    :param default:
    :param funcs: keys are new name for prop, value is a function that takes the prop dict as input
    :return:
    """
    set_node_props_value(
        G,
        *nodes,
        **{k: get_node_prop_func(G, f, default=default) for k, f in funcs.items()},
    )


def set_edge_props_func(G, *nodes, default=None, **funcs):
    """
    Apply function to prop of nodes in G, then set a prop for those nodes to the function output.
    :param G:
    :param nodes:
    :param default:
    :param funcs: keys are new name for prop, value is a function that takes the prop dict as input
    :return:
    """
    set_edge_props_value(
        G,
        *nodes,
        **{k: get_edge_prop_func(G, f, default=default) for k, f in funcs.items()},
    )


def set_node_props(G, *nodes, default=None, **props):
    funcs = {k: v for k, v in props.items() if callable(v)}
    props = {k: v for k, v in props.items() if not callable(v)}
    if len(props) > 0:
        set_node_props_value(G, *nodes, default=default, **props)
    if len(funcs) > 0:
        set_node_props_func(G, *nodes, default=default, **funcs)


def set_edge_props(G, *edges, default=None, **props):
    funcs = {k: v for k, v in props.items() if callable(v)}
    props = {k: v for k, v in props.items() if not callable(v)}
    if len(props) > 0:
        set_edge_props_value(G, *edges, default=default, **props)
    if len(funcs) > 0:
        set_edge_props_func(G, *edges, default=default, **funcs)


def outgoing_inherit(G, key, newkey=None):
    """
    Outgoing edges inherit a property from the node.
    :param G:
    :param key: name of node property
    :param newkey: name of new edge property, default same as "key"
    :return:
    """
    if newkey is None:
        newkey = key
    for u, v, d in G.edges(data=True):
        d[newkey] = G.nodes[u][key]


def set_outgoing(D, **kwargs):
    """
    Add properties to outgoing edges from specified nodes.
    :param D: (multi) directed graph
    :param kwargs: keys are names of prop to add, values are dicts mapping from node id to value to add.
    :return: None
    """
    for prop_name, node2value in kwargs.items():
        for u, v, d in D.edges(data=True):
            d[prop_name] = node2value[u]


def set_ingoing(D, **kwargs):
    """
    Add properties to ingoing edges from specified nodes.
    :param D: (multi) directed graph
    :param kwargs: keys are names of prop to add, values are dicts mapping from node id to value to add.
    :return: None
    """
    for prop_name, node2value in kwargs.items():
        for u, v, d in D.edges(data=True):
            d[prop_name] = node2value[v]


def _get_inv_props(**kwargs):
    inv = {}
    for prop_name, node2value in kwargs.items():
        # necessary for indegree and outdegree view
        node2value = dict(node2value)
        keys, values = dict_keys(node2value), dict_values(node2value)
        inv[f"1/{prop_name}"] = dict(zip(keys, 1 / values))
    return inv


def set_outgoing_inv(D, **kwargs):
    """
    Add properties and the inverse (1/value) version named 1/name
    :param D: (multi) directed graph
    :param kwargs:
    :return:
    """
    set_outgoing(D, **kwargs, **_get_inv_props(**kwargs))


def set_ingoing_inv(D, **kwargs):
    """
    Add properties and the inverse (1/value) version named 1/name
    :param D: (multi) directed graph
    :param kwargs:
    :return:
    """
    set_ingoing(D, **kwargs, **_get_inv_props(**kwargs))


def set_ingoing_indegree(D):
    """
    Avoid divide by zero by excluding degree node annotations of zero.
    Since it is going to be added to the incoming edges,
        if indegree is zero then the 1/0 doesn't get added to anything anyways.
    :param D:
    :return:
    """
    set_ingoing_inv(
        D,
        indegree={
            n: degree for n, degree in dict(D.in_degree()).items() if degree != 0
        },
    )


def set_outgoing_outdegree(D):
    set_outgoing_inv(
        D,
        outdegree={
            n: degree for n, degree in dict(D.out_degree()).items() if degree != 0
        },
    )


def set_indegrees(D, indegrees=None, *keys):
    """
    Add node indegree and 1/indegree property to ingoing edges in D.
    :param D: directed graph
    :param indegrees: dict mapping from dbId to indegree. Default is calculating from D
    :param keys: indegree keys matches this node property, e.g. "dbId"
    :return: None
    """
    if indegrees is None:
        indegrees = D.in_degree()
        for u, v, d in D.edges(data=True):
            d["indegree"] = indegrees[v]
            d["1/indegree"] = 1 / d["indegree"]

    else:
        mapping = get_node_prop_dict(D, D.nodes, *keys)
        for u, v, d in D.edges(data=True):
            try:
                d["indegree"] = indegrees[mapping[v]]
            except KeyError:
                pass
            else:
                d["1/indegree"] = 1 / d["indegree"]

        n_has_indegree = sum(1 for u, v, d in D.edges(data=True) if "indegree" in d)
        n_edges = nx.number_of_edges(D)
        logging.info(
            "{:d}/{:d} ({:.3f}%) edges with indegree property".format(
                n_has_indegree, n_edges, n_has_indegree / n_edges * 100
            )
        )


def set_marks(D, start_nodes, end_nodes):
    set_node_props_value(D, mark={n: "start" for n in start_nodes})
    set_node_props_value(D, mark={n: "end" for n in end_nodes})


# GETTERS


def get_max_nodes(D, prop, n=1, include=None, exclude=None):
    """
    Get nodes with the highest value in a given prop.
    :param D: DirectedGraph
    :param prop: key of property with values to compare
    :param n: number of tied top nodes to return
    :param include: set of nodes to include, default is all nodes.
    :param exclude: set of nodes to exclude, default is D.graph["node_sets"]["sources"] and D.graph["node_sets"]["targets"]
    :return:
    """
    if include is None:
        include = D.nodes
    else:
        include = D.node_set(include)
    if exclude is None:
        exclude = D.graph["node_sets"].get("sources", set()) | D.graph["node_sets"].get(
            "targets", set()
        )
    else:
        exclude = D.node_set(exclude)
    nodes = set(include) - set(exclude)
    if len(nodes) == 0:
        logging.warning(f"No nodes given include and exclude sets.")
        return set()
    prop_dict = D.getd(prop, nodes=nodes)
    if len(prop_dict) == 0:
        logging.warning(
            f'No node property "{prop}" for the given include and exclude set.'
        )
        return set()
    return dict_max_ties(prop_dict, n)


def get_min_nodes(D, prop, n=1, include=None, exclude=None):
    if include is None:
        include = D.nodes
    else:
        include = D.node_set(include)
    if exclude is None:
        exclude = D.graph["node_sets"].get("sources", set()) | D.graph["node_sets"].get(
            "targets", set()
        )
    else:
        exclude = D.node_set(exclude)
    nodes = set(include) - set(exclude)
    if len(nodes) == 0:
        logging.warning(f"No nodes given include and exclude sets.")
        return set()
    prop_dict = D.getd(prop, nodes=nodes)
    if len(prop_dict) == 0:
        logging.warning(
            f'No node property "{prop}" for the given include and exclude sets.'
        )
        return set()
    return dict_min_ties(prop_dict, n)


# MODIFY


def flat_props(G):
    """
    Move arango properties from a dict under key "properties" to the main/top-level dict for each node.
    :param G:
    :return: None
    """
    for n, d in G.nodes(data=True):
        for k, v in d["properties"].items():
            d[k] = v
        del d["properties"]


### GET PROPERTIES


def get_node_prop_keys(G, nodes=None):
    """
    Get all unique node property keys for either all nodes in G or a subset.
    :param G:
    :param nodes: node set
    :return: set of node property keys
    """
    if nodes is None:
        nodes = set(G)
    return set.union(set(), *(G.nodes[n].keys() for n in nodes))


def get_node_prop(G, key, nodes=None):
    if nodes is None:
        return [d.get(key) for n, d in G.nodes(data=True)]
    else:
        return [G.nodes[n].get(key) for n in nodes if n in G]


def get_edge_prop(G, key, edges=None):
    if edges is None:
        return [d.get(key) for u, v, d in G.edges(data=True)]
    else:
        return [G.edges[e].get(key) for e in edges if e in G.edges]


def get_node_prop_func(G, func, nodes=None, default=None):
    def f(d):
        try:
            return func(d)
        except KeyError:
            return default

    if nodes is None:
        out = {n: f(d) for n, d in G.nodes(data=True)}
    else:
        out = {n: f(G.nodes[n]) for n in nodes}

    if default is not None:
        return out
    return {n: v for n, v in out.items() if v is not None}


def get_node_props(G, keys, nodes=None):
    if nodes is None:
        return [tuple(d[k] for k in keys) for n, d in G.nodes(data=True)]
    else:
        return [tuple(G.nodes[n][k] for k in keys) for n in nodes]


def get_edge_props(G, keys, edges=None):
    if edges is None:
        return [tuple(d.get(k) for k in keys) for u, v, d in G.edges(data=True)]
    else:
        return [tuple(G.edges[e].get(k) for k in keys) for e in edges]


def get_all_node_props(G, nodes=None):
    if nodes is None:
        return [d for n, d in G.nodes(data=True)]
    return [G.nodes[n] for n in nodes]


def get_node_prop_dict(G, key, nodes=None):
    if nodes is None:
        return {n: d[key] for n, d in G.nodes(data=True) if key in d}
    else:
        return {n: G.nodes[n][key] for n in nodes if n in G and key in G.nodes[n]}


def get_edge_prop_dict(G, key, edges=None):
    if not G.is_multigraph():
        if edges is None:
            return {(u, v): d[key] for u, v, d in G.edges(data=True) if key in d}
        else:
            return {e: G.edges[e][key] for e in edges & G.edges if key in G.edges[e]}
    else:
        if edges is None:
            return {
                (u, v, k): d[key]
                for u, v, k, d in G.edges(data=True, keys=True)
                if key in d
            }
        else:
            # make sure we have (u, v, k) tuples
            return {
                e: G.edges[e][key]
                for e in from_multi_edges(G, edges) & G.edges
                if key in G.edges[e]
            }


def get_node_props_dict(G, keys, nodes=None):
    if nodes is None:
        return {n: tuple(d[k] for k in keys) for n, d in G.nodes(data=True)}
    else:
        return {n: tuple(G.nodes[n][k] for k in keys) for n in nodes if n in G}


def get_edge_props_dict(G, keys, edges=None):
    if not G.is_multigraph():
        if edges is None:
            return {(u, v): tuple(d[k] for k in keys) for u, v, d in G.edges(data=True)}
        else:
            return {
                e: tuple(G.edges[e][k] for k in keys) for e in edges if e in G.edges
            }
    else:
        if edges is None:
            return {
                (u, v, k): tuple(d[pk] for pk in keys)
                for u, v, k, d in G.edges(data=True, keys=True)
            }
        else:
            # make sure we have (u, v, k) tuples
            return {
                e: tuple(G.edges[e][pk] for pk in keys)
                for e in from_multi_edges(G, edges) & G.edges
            }


### EDGE SPECIFIC


def from_multi_edge(M, multi_edge):
    """
    Get all edges for a multi graph given a multi edge
    :param M: multi graph
    :param multi_edge: meant for (u, v) but handles (u, v, k)
    :return: iterable of (u, v, k)
    """
    if not M.has_edge(*multi_edge):
        return []
    try:
        u, v = multi_edge
    except ValueError:
        return [multi_edge]
    return [(u, v, k) for k in M[u][v].keys()]


def from_multi_edges(M, multi_edges):
    return {e for me in multi_edges for e in from_multi_edge(M, me)}
