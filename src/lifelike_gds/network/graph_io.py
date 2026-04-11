#!/usr/bin/env python3
import copy
import gzip
import logging
from os.path import expanduser

import networkx as nx
import numpy as np
import pandas as pd
import simplejson as json

from lifelike_gds.utils.excel_utils import write as xl_u_write

from lifelike_gds.network.collection_utils import dict_max
from lifelike_gds.network.graph_algorithms import (
    all_shortest_paths_subgraph,
    shortest_paths_subgraph,
    simple_paths_subgraph,
)
from lifelike_gds.network.graph_utils import DirectedGraph, MultiDirectedGraph


def read_json(fname):
    fname = expanduser(fname)
    fh = gzip.open(fname, "rt") if fname.endswith(".gz") else open(fname)
    with fh as infile:
        return json.load(infile)


def read_apoc_json(fname):
    """
    Read json from arango databases exported with call apoc.export.json.all("...")
    :param fname:
    :return:
    """
    fname = expanduser(fname)
    fh = gzip.open(fname, "rt") if fname.endswith(".gz") else open(fname)
    with fh as infile:
        graph = json.loads("[" + ",".join(infile.readlines()) + "]")

    nodes = [d for d in graph if d["type"] == "node"]
    relationships = [d for d in graph if d["type"] == "relationship"]
    for d in nodes:
        del d["type"]
    for d in relationships:
        del d["type"]

    D = nx.DiGraph()
    D.add_nodes_from((int(d.pop("id")), {**d.pop("properties"), **d}) for d in nodes)
    D.add_edges_from(
        (int(d.pop("start")["id"]), int(d.pop("end")["id"]), d) for d in relationships
    )
    if nx.number_of_isolates(D) > 0:
        logging.warning("{:d} isolated nodes found".format(nx.number_of_isolates(D)))
    return D


def read_gpickle(fname):
    if fname.endswith(".gz"):
        with gzip.open(fname, "rb") as fp:
            D = nx.read_gpickle(fp)
    else:
        D = nx.read_gpickle(fname)
    return MultiDirectedGraph(D) if D.is_multigraph() else DirectedGraph(D)


def write_gpickle(G, fname):
    if fname.endswith(".gz"):
        with gzip.open(fname, "wb") as fp:
            nx.write_gpickle(G, fp)
    else:
        nx.write_gpickle(G, fname)


def write_graphml(fname, G):
    """
    Write graph to graphml which does not support non-scalars or None so they are converted to string and removed, respectively.
    :param fname:
    :param G:
    :return: None
    """

    def fix_scalar_None(d):
        for k in list(d):
            if d[k] is None:
                del d[k]
        for k, vs in d.items():
            if not np.isscalar(vs):
                d[k] = str(vs)

    _G = G.copy()

    for n, d in _G.nodes(data=True):
        fix_scalar_None(d)
    for u, v, d in _G.edges(data=True):
        fix_scalar_None(d)
    fix_scalar_None(_G.graph)

    nx.write_graphml(_G, expanduser(fname))


def write_arango_graphml(fname, D, centrality=None):
    """
    Write graph with centrality as a property and convert list properties to strings.
    :param fname:
    :param D:
    :param centrality: dict
    :return: None
    """
    if centrality is not None:
        assert type(centrality) is dict, "centrality should be a dict"
    graph = D.copy()
    for n in D:
        if centrality is not None:
            graph.nodes[n]["centrality"] = centrality[n]
        for k, v in graph.nodes[n]["properties"].items():
            if type(v) is list:
                v = str(v)
            graph.nodes[n][k] = v
        del graph.nodes[n]["properties"]
        graph.nodes[n]["labels"] = str(graph.nodes[n]["labels"])

    for u, v, d in graph.edges(data=True):
        for k, vs in d.items():
            if type(vs) is list:
                d[k] = str(vs)

    nx.write_graphml(graph, expanduser(fname))


def write_graphml_top(
    fname, D, start_nodes, centrality, top, method="simple", weight="weight"
):
    if method == "simple":
        write_arango_graphml(
            fname,
            simple_paths_subgraph(D, start_nodes, dict_max(centrality, top)),
            centrality,
        )
    elif method == "shortest":
        write_arango_graphml(
            fname,
            shortest_paths_subgraph(
                D, start_nodes, dict_max(centrality, top), weight=weight
            ),
            centrality,
        )
    elif method == "all_shortest":
        write_arango_graphml(
            fname,
            all_shortest_paths_subgraph(
                D, start_nodes, dict_max(centrality, top), weight=weight
            ),
            centrality,
        )


def _serializable_formats(d):
    """
    Recursively find and replace sets, tuples -> list and int64 -> int32.
    :param d:
    :return: None
    """
    try:
        dict_iter = d.items()
    except AttributeError:
        if type(d) == str:
            return
        try:
            enum_iter = enumerate(d)
        except TypeError:
            return
        else:
            for i, v in enum_iter:
                if type(v) == set:
                    d[i] = list(v)
                elif type(v) == np.int64:
                    d[i] = int(v)
                else:
                    _serializable_formats(v)
    else:
        for k, v in dict_iter:
            if type(v) == set:
                d[k] = list(v)
            elif type(v) == np.int64:
                d[k] = int(v)
            else:
                _serializable_formats(v)


def serializable_node_link_data(G):
    data = copy.deepcopy(nx.node_link_data(G))
    _serializable_formats(data)
    return data


def serializable_cytoscape_data(G):
    data = copy.deepcopy(nx.cytoscape_data(G))
    _serializable_formats(data)
    return data


def write_json(obj: dict, fname: str, zip_it=False):
    """
    Write json or json.gz to file or stdout where numpy types are handled and a git commit hash is prepended.
    :param obj:
    :param fname: filename to write to
    :return:
    """
    logging.info(f'writing {fname.rsplit(".", 1)[0]}')
    fp = gzip.open(fname, "w") if zip_it else open(fname, "w")
    json.dump(obj, fp, indent=True, cls=NumpyEncoder)
    fp.close()


class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for numpy data types taken from https://github.com/hmallen/numpyencoder"""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.complexfloating,)):
            return {"real": obj.real, "imag": obj.imag}
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, (np.void)):
            return None

        return json.JSONEncoder.default(self, obj)


def nodes2tsv(D, fname):
    """
    Write node properties from D to a tab-separated file.
    :param D: (Multi)DirectedGraph
    :param fname: str filename
    :return:
    """
    pd.DataFrame(D.get(), index=list(D)).to_csv(fname, sep="\t", index_label="arango_id")


def nodes2excel(D, fname: str):
    logging.info(f'writing {fname.rsplit(".", 1)[0]}')
    df = pd.DataFrame(D.get(), index=list(D))
    df_meta = pd.DataFrame(index=df.columns)
    if "node_props" in D.graph:
        df_meta = pd.DataFrame.from_dict(D.graph["node_props"], orient="index").join(
            df_meta, how="right"
        )

    xl_u_write(
        fname,
        sheets={"node property meta": df_meta, "node_properties": df},
        indexes=["node property key", "arango_id"],
    )
