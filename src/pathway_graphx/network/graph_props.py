"""Property-based helpers for querying and annotating NetworkX graphs."""

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


def _prop_match(d, **prop_filter):
    """Return ``True`` when all property filters match the data mapping."""
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
    """Like :func:`_prop_match`, but compares string values case-insensitively."""
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
            pass
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
    return {n for n in nodes if f(G.nodes[n])}


def _get_edges_by_f(G, f, edges=None):
    if edges is None:
        edges = (
            G.edges(keys=True, data=True) if G.is_multigraph() else G.edges(data=True)
        )
        return {e[:-1] for e in edges if f(e[-1])}
    if G.is_multigraph():
        edges = from_multi_edges(G, edges)
    return {e for e in edges if f(G.edges[e])}


def get_nodes_by_func(G, func, nodes=None):
    """Return nodes whose property dictionaries satisfy ``func``."""

    def f(d):
        try:
            return func(d)
        except KeyError:
            return False

    return _get_nodes_by_f(G, f, nodes)


def get_edges_by_func(G, func, edges=None):
    """Return edges whose property dictionaries satisfy ``func``."""

    def f(d):
        try:
            return func(d)
        except KeyError:
            return False

    return _get_edges_by_f(G, f, edges)


def get_nodes_by_prop_func(G, nodes=None, **prop_func_filter):
    """Return nodes for which each property-specific predicate returns ``True``."""

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
    """Return edges for which each property-specific predicate returns ``True``."""

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
    """Return nodes whose properties match all requested values."""
    f = _prop_match_insensitive if insensitive else _prop_match
    return get_nodes_by_func(G, lambda d: f(d, **prop_filter), nodes)


def get_edges_by_prop_match(G, edges=None, insensitive=False, **prop_filter):
    """Return edges whose properties match all requested values."""
    f = _prop_match_insensitive if insensitive else _prop_match
    return get_edges_by_func(G, lambda d: f(d, **prop_filter), edges)


def get_nodes_by_prop(G, nodes=None, insensitive=False, **prop_filters):
    """Return nodes that satisfy value filters and callable filters together."""
    funcs = {k: v for k, v in prop_filters.items() if callable(v)}
    props = {k: v for k, v in prop_filters.items() if not callable(v)}
    if len(props) > 0:
        nodes = get_nodes_by_prop_match(G, nodes, insensitive, **props)
    if len(funcs) > 0:
        nodes = get_nodes_by_prop_func(G, nodes, **funcs)
    return nodes


def get_edges_by_prop(G, edges=None, insensitive=False, **prop_filters):
    """Return edges that satisfy value filters and callable filters together."""
    funcs = {k: v for k, v in prop_filters.items() if callable(v)}
    props = {k: v for k, v in prop_filters.items() if not callable(v)}
    if len(props) > 0:
        edges = get_edges_by_prop_match(G, edges, insensitive, **props)
    if len(funcs) > 0:
        edges = get_edges_by_prop_func(G, edges, **funcs)
    return edges


def _get_any_nodes_by_prop(G, **kwargs):
    """Yield nodes that match at least one of the requested property filters."""

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


def set_node_props_value(G, *nodes, default=None, **props):
    """Set node properties from scalar values or per-node mappings."""
    nodes = list(nodes)
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
            if default is not None:
                for n, d in G.nodes(data=True):
                    d[propname] = default
            for n in nodes:
                G.nodes[n][propname] = assign


def set_edge_props_value(G, *edges, default=None, **props):
    """Set edge properties from scalar values or per-edge mappings."""
    edges = list(edges)
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
            if default is not None:
                for u, v, d in G.edges(data=True):
                    d[propname] = default
            for e in edges:
                G.edges[e][propname] = assign


def get_edge_prop_func(G, func, default=None):
    """Return an edge-to-value mapping produced by ``func`` over edge data."""

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
    """Set node properties using functions evaluated against node data."""
    set_node_props_value(
        G,
        *nodes,
        **{k: get_node_prop_func(G, f, default=default) for k, f in funcs.items()},
    )


def set_edge_props_func(G, *nodes, default=None, **funcs):
    """Set edge properties using functions evaluated against edge data."""
    set_edge_props_value(
        G,
        *nodes,
        **{k: get_edge_prop_func(G, f, default=default) for k, f in funcs.items()},
    )


def set_node_props(G, *nodes, default=None, **props):
    """Set node properties, dispatching callables to ``set_node_props_func``."""
    funcs = {k: v for k, v in props.items() if callable(v)}
    props = {k: v for k, v in props.items() if not callable(v)}
    if len(props) > 0:
        set_node_props_value(G, *nodes, default=default, **props)
    if len(funcs) > 0:
        set_node_props_func(G, *nodes, default=default, **funcs)


def set_edge_props(G, *edges, default=None, **props):
    """Set edge properties, dispatching callables to ``set_edge_props_func``."""
    funcs = {k: v for k, v in props.items() if callable(v)}
    props = {k: v for k, v in props.items() if not callable(v)}
    if len(props) > 0:
        set_edge_props_value(G, *edges, default=default, **props)
    if len(funcs) > 0:
        set_edge_props_func(G, *edges, default=default, **funcs)


def outgoing_inherit(G, key, newkey=None):
    """Copy a node property onto each outgoing edge from that node."""
    if newkey is None:
        newkey = key
    for u, v, d in G.edges(data=True):
        d[newkey] = G.nodes[u][key]


def set_outgoing(D, **kwargs):
    """Annotate each edge with values looked up from its source node."""
    for prop_name, node2value in kwargs.items():
        for u, v, d in D.edges(data=True):
            d[prop_name] = node2value[u]


def set_ingoing(D, **kwargs):
    """Annotate each edge with values looked up from its target node."""
    for prop_name, node2value in kwargs.items():
        for u, v, d in D.edges(data=True):
            d[prop_name] = node2value[v]


def _get_inv_props(**kwargs):
    inv = {}
    for prop_name, node2value in kwargs.items():
        node2value = dict(node2value)
        keys, values = dict_keys(node2value), dict_values(node2value)
        inv[f"1/{prop_name}"] = dict(zip(keys, 1 / values))
    return inv


def set_outgoing_inv(D, **kwargs):
    """Set outgoing edge properties and matching inverse-valued properties."""
    set_outgoing(D, **kwargs, **_get_inv_props(**kwargs))


def set_ingoing_inv(D, **kwargs):
    """Set incoming edge properties and matching inverse-valued properties."""
    set_ingoing(D, **kwargs, **_get_inv_props(**kwargs))


def set_ingoing_indegree(D):
    """Annotate incoming edges with indegree and reciprocal indegree."""
    set_ingoing_inv(
        D,
        indegree={n: degree for n, degree in dict(D.in_degree()).items() if degree != 0},
    )


def set_outgoing_outdegree(D):
    """Annotate outgoing edges with outdegree and reciprocal outdegree."""
    set_outgoing_inv(
        D,
        outdegree={
            n: degree for n, degree in dict(D.out_degree()).items() if degree != 0
        },
    )


def set_indegrees(D, indegrees=None, *keys):
    """Add indegree and reciprocal indegree properties to edges."""
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
    """Mark two node sets as ``start`` and ``end``."""
    set_node_props_value(D, mark={n: "start" for n in start_nodes})
    set_node_props_value(D, mark={n: "end" for n in end_nodes})


def get_max_nodes(D, prop, n=1, include=None, exclude=None):
    """Return tied top nodes for the given property after include/exclude filters."""
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
        logging.warning("No nodes given include and exclude sets.")
        return set()
    prop_dict = D.getd(prop, nodes=nodes)
    if len(prop_dict) == 0:
        logging.warning(
            f'No node property "{prop}" for the given include and exclude set.'
        )
        return set()
    return dict_max_ties(prop_dict, n)


def get_min_nodes(D, prop, n=1, include=None, exclude=None):
    """Return tied bottom nodes for the given property after include/exclude filters."""
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
        logging.warning("No nodes given include and exclude sets.")
        return set()
    prop_dict = D.getd(prop, nodes=nodes)
    if len(prop_dict) == 0:
        logging.warning(
            f'No node property "{prop}" for the given include and exclude set.'
        )
        return set()
    return dict_min_ties(prop_dict, n)


def flat_props(G):
    """Flatten a nested ``properties`` mapping onto each node dictionary."""
    for n, d in G.nodes(data=True):
        for k, v in d["properties"].items():
            d[k] = v
        del d["properties"]


def get_node_prop_keys(G, nodes=None):
    """Return all node property keys across the graph or a node subset."""
    if nodes is None:
        nodes = set(G)
    return set.union(set(), *(G.nodes[n].keys() for n in nodes))


def get_node_prop(G, key, nodes=None):
    """Return a list of node property values for ``key``."""
    if nodes is None:
        return [d.get(key) for n, d in G.nodes(data=True)]
    return [G.nodes[n].get(key) for n in nodes if n in G]


def get_edge_prop(G, key, edges=None):
    """Return a list of edge property values for ``key``."""
    if edges is None:
        return [d.get(key) for u, v, d in G.edges(data=True)]
    return [G.edges[e].get(key) for e in edges if e in G.edges]


def get_node_prop_func(G, func, nodes=None, default=None):
    """Return a node-to-value mapping produced by ``func`` over node data."""

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
    """Return tuples of node property values for the requested keys."""
    if nodes is None:
        return [tuple(d[k] for k in keys) for n, d in G.nodes(data=True)]
    return [tuple(G.nodes[n][k] for k in keys) for n in nodes]


def get_edge_props(G, keys, edges=None):
    """Return tuples of edge property values for the requested keys."""
    if edges is None:
        return [tuple(d.get(k) for k in keys) for u, v, d in G.edges(data=True)]
    return [tuple(G.edges[e].get(k) for k in keys) for e in edges]


def get_all_node_props(G, nodes=None):
    """Return all node data dictionaries, optionally restricted to ``nodes``."""
    if nodes is None:
        return [d for n, d in G.nodes(data=True)]
    return [G.nodes[n] for n in nodes]


def get_node_prop_dict(G, key, nodes=None):
    """Return a node-to-property mapping for nodes that have ``key``."""
    if nodes is None:
        return {n: d[key] for n, d in G.nodes(data=True) if key in d}
    return {n: G.nodes[n][key] for n in nodes if n in G and key in G.nodes[n]}


def get_edge_prop_dict(G, key, edges=None):
    """Return an edge-to-property mapping, including multigraph edge keys."""
    if not G.is_multigraph():
        if edges is None:
            return {(u, v): d[key] for u, v, d in G.edges(data=True) if key in d}
        return {e: G.edges[e][key] for e in edges & G.edges if key in G.edges[e]}
    if edges is None:
        return {
            (u, v, k): d[key]
            for u, v, k, d in G.edges(data=True, keys=True)
            if key in d
        }
    return {
        e: G.edges[e][key]
        for e in from_multi_edges(G, edges) & G.edges
        if key in G.edges[e]
    }


def get_node_props_dict(G, keys, nodes=None):
    """Return a node-to-tuple mapping for the requested property keys."""
    if nodes is None:
        return {n: tuple(d[k] for k in keys) for n, d in G.nodes(data=True)}
    return {n: tuple(G.nodes[n][k] for k in keys) for n in nodes if n in G}


def get_edge_props_dict(G, keys, edges=None):
    """Return an edge-to-tuple mapping for the requested property keys."""
    if not G.is_multigraph():
        if edges is None:
            return {(u, v): tuple(d[k] for k in keys) for u, v, d in G.edges(data=True)}
        return {e: tuple(G.edges[e][k] for k in keys) for e in edges if e in G.edges}
    if edges is None:
        return {
            (u, v, k): tuple(d[pk] for pk in keys)
            for u, v, k, d in G.edges(data=True, keys=True)
        }
    return {
        e: tuple(G.edges[e][pk] for pk in keys)
        for e in from_multi_edges(G, edges) & G.edges
    }


def from_multi_edge(M, multi_edge):
    """Expand a multigraph edge specifier into concrete ``(u, v, key)`` edges."""
    if not M.has_edge(*multi_edge):
        return []
    try:
        u, v = multi_edge
    except ValueError:
        return [multi_edge]
    return [(u, v, k) for k in M[u][v].keys()]


def from_multi_edges(M, multi_edges):
    """Expand many multigraph edge specifiers into keyed edge tuples."""
    return {e for me in multi_edges for e in from_multi_edge(M, me)}
