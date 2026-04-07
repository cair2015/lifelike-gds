"""
Trace graph utility functions for network analysis.

This module provides helper functions for trace graph operations, including:
- PageRank calculations
- Path analysis  
- File export (Sankey, Cytoscape)
- Node set operations

All functions are database-agnostic and work with NetworkX graphs.
"""

import logging
import sys
from typing import List, Dict, Any, Optional, Set

import networkx as nx
import pandas as pd
from networkx.exception import NetworkXNoPath, NodeNotFound

from lifelike_gds.network.graph_io import read_gpickle, serializable_node_link_data, write_json
from lifelike_gds.network.graph_algorithms import add_influence_contribution

logger = logging.getLogger(__name__)


# ============================================================================
# File Export Functions
# ============================================================================

def convert_gpickle_to_json(gpicklefile: str) -> None:
    """
    Convert a NetworkX graph from gpickle format to JSON format.
    
    Args:
        gpicklefile: Path to input .gpickle.gz file
    """
    D = read_gpickle(gpicklefile)
    jsonfile = gpicklefile.replace('.gpickle.gz', '.json')
    write_json(D, jsonfile)


def write_sankey_file(filename: str, D) -> None:
    """
    Export graph to Sankey format JSON file.
    
    Uses indexed edges instead of (source, target) tuples for more compact representation.
    Creates parent directories as needed.
    
    Args:
        filename: Output file path (should end with .json)
        D: NetworkX MultiDiGraph or DiGraph
    """
    from pathlib import Path
    
    # Create parent directories if they don't exist
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    
    data = serializable_node_link_data(D)
    link_index(data)
    write_json(data, filename)


def write_cytoscape_file(filename: str, D) -> None:
    """
    Export graph to Cytoscape-compatible JSON format.
    Creates parent directories as needed.
    
    Args:
        filename: Output file path (should end with .json)
        D: NetworkX graph
    """
    from pathlib import Path
    
    # Create parent directories if they don't exist
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    
    data = nx.cytoscape_data(D)
    data['data'] = {}
    for e in data['elements']['edges']:
        e['data']['source'] = str(e['data']['source'])
        e['data']['target'] = str(e['data']['target'])
    write_json(data, filename)


def link_index(data: Dict) -> None:
    """
    Replace edge references in trace networks with array indices.
    
    Converts edge tuples to indices in the links array for more compact JSON.
    
    Args:
        data: Node-link format graph dictionary (modified in place)
    """
    # Handle case where there are no links or trace networks
    if "links" not in data or not data["links"]:
        return
    
    if "trace_networks" not in data.get("graph", {}):
        return
    
    if data["multigraph"]:
        edge2index = {
            (l["source"], l["target"], l["key"]): i 
            for i, l in enumerate(data["links"])
        }
    else:
        edge2index = {
            (l["source"], l["target"]): i 
            for i, l in enumerate(data["links"])
        }

    for tn in data["graph"]["trace_networks"]:
        for t in tn["traces"]:
            t["edges"] = [edge2index[e] for e in t["edges"]]

    if data["multigraph"]:
        for link in data["links"]:
            del link["key"]


# ============================================================================
# PageRank Functions
# ============================================================================

def add_pagerank(
    graph,
    sources: str,
    pagerank_prop: str = "pagerank",
    personalization: Optional[Dict[int, float]] = None,
    reverse: bool = False,
    contribution: bool = False,
    tol: float = 1e-7,
) -> None:
    """
    Calculate and add personalized PageRank to graph nodes.
    
    This is a modified PageRank that measures influence from specific source nodes.
    
    Args:
        graph: NetworkX DirectedGraph (can be MultiDiGraph)
        sources: Name of source node set in graph
        pagerank_prop: Property name to store PageRank values (default: "pagerank")
        personalization: Optional dictionary of node weights for personalized PageRank
        reverse: If True, calculate PageRank on reversed graph
        contribution: If True, calculate edge contribution values for Sankey
        tol: Convergence tolerance for PageRank algorithm
    """
    compute_graph = graph.reverse() if reverse else graph
    
    if not pagerank_prop:
        pagerank_prop = f'pagerank_{sources}'
        if reverse:
            pagerank_prop = 'rev_' + pagerank_prop
    
    df = pagerank_influence(
        compute_graph,
        sources,
        personalization,
        method="scipy" if graph.is_multigraph() else "iteration",
        tol=tol,
    )
    
    pageranks = {row['node']: row['pagerank'] for _, row in df.iterrows()}
    nstarts = {row['node']: row['nstart'] for _, row in df.iterrows()}

    nx.set_node_attributes(graph, pageranks, pagerank_prop)
    filtered_nstart = {k: v for k, v in nstarts.items() if v > 0}
    nx.set_node_attributes(graph, filtered_nstart, 'start_val')
    
    if contribution:
        add_influence_contribution(
            graph,
            reverse=reverse,
            weight=pagerank_prop,
            **{f"{pagerank_prop}_contribution": pagerank_prop}
        )
    
    logger.info(f"Added PageRank '{pagerank_prop}' to {len(pageranks)} nodes")


def pagerank_influence(
    D,
    sources_name: str,
    personalization: Optional[Dict] = None,
    weight: Optional[str] = None,
    method: str = "iteration",
    tol: float = 1e-6,
) -> pd.DataFrame:
    """
    Calculate modified PageRank for measuring influence from sources.
    
    Args:
        D: NetworkX DirectedGraph
        sources_name: Node set name for personalization sources
        personalization: Optional personalization weights dict
        weight: Edge weight attribute name (default: None = unweighted)
        method: Algorithm method ('iteration', 'numpy', 'scipy')
        tol: Convergence tolerance
        
    Returns:
        DataFrame with node IDs and their pagerank and nstart values
    """
    sources = D.node_set(sources_name) & set(D.nodes)
    nstart = {v: 0 for v in D}
    
    for v in sources:
        nstart[v] = 1
    
    if personalization:
        for v, val in personalization.items():
            if v not in nstart:
                logger.warning(f"Personalization node {v} not in graph")
            else:
                nstart[v] = val
    
    try:
        pageranks = nx.pagerank(
            D,
            personalization=nstart,
            weight=weight,
            max_iter=500 if method.startswith("iter") else 100,
            tol=tol,
        )
    except TypeError:
        # Fallback for older NetworkX versions
        pageranks = nx.pagerank(
            D,
            personalization=nstart,
            weight=weight,
        )
    
    df1 = pd.DataFrame(list(pageranks.items()), columns=['node', 'pagerank'])
    df2 = pd.DataFrame(list(nstart.items()), columns=['node', 'nstart'])
    df = pd.merge(df1, df2, on='node', how='outer')
    return df


def set_nReach(graph, sources: str, reverse: bool = False) -> None:
    """
    Set node property indicating number of reachable sources.
    
    Counts how many source nodes can reach (or are reachable from) each node.
    
    Args:
        graph: NetworkX DirectedGraph
        sources: Name of source node set
        reverse: If True, count sources that can be reached from each node
    """
    node_set_name = graph.get_node_set_name(sources)
    node_set = graph.node_set(sources)
    nReach_prop = f'nReach'
    
    if reverse:
        nReach_prop = 'rev_' + nReach_prop
    
    prop_name = f"number of {node_set_name} nodes that can "
    if reverse:
        prop_name += "be reached from this node"
    else:
        prop_name += "reach to this node"
    
    graph.name_node_props(**{nReach_prop: prop_name})
    
    compute_graph = graph.reverse() if reverse else graph
    nReach = {n: 0 for n in graph}
    
    for s in set(compute_graph).intersection(node_set):
        reach = nx.single_source_shortest_path(compute_graph, s)
        for n in reach.keys():
            nReach[n] += 1
    
    graph.set(**{nReach_prop: nReach})
    logger.info(f"Added reachability counts (nReach) to graph")


def set_intersection_pagerank(
    graph,
    source_pagerank_name: str,
    target_rev_pagerank_name: str,
    intersect_pagerank_name: Optional[str] = None,
) -> None:
    """
    Calculate intersection PageRank combining forward and reverse PageRank.
    
    Uses formula: p1*p2/(p1+p2-p1*p2) where p1 is source PageRank
    and p2 is target reverse PageRank.
    
    Args:
        graph: NetworkX DirectedGraph
        source_pagerank_name: Property name for forward PageRank
        target_rev_pagerank_name: Property name for reverse PageRank
        intersect_pagerank_name: Property name to store result (default: 'inter_pagerank')
    """
    source_pageranks = graph.getd(source_pagerank_name)
    target_rev_pageranks = graph.getd(target_rev_pagerank_name)
    
    if not source_pageranks:
        logger.warning(f"No pagerank found for {source_pagerank_name}")
        return
    
    if not target_rev_pageranks:
        logger.warning(f"No reverse pagerank found for {target_rev_pagerank_name}")
        return
    
    df = pd.DataFrame(dict(
        source_pagerank=source_pageranks,
        target_pagerank=target_rev_pageranks,
    ))
    
    p1 = df['source_pagerank']
    p2 = df['target_pagerank']
    # Avoid division by zero
    denominator = p1 + p2 - (p1 * p2)
    denominator = denominator.replace(0, 1e-10)
    df['inter_pagerank'] = (p1 * p2) / denominator
    
    df.index.name = 'node'
    df.reset_index(inplace=True)
    
    if not intersect_pagerank_name:
        intersect_pagerank_name = 'inter_pagerank'
    
    nx.set_node_attributes(
        graph,
        {row['node']: row["inter_pagerank"] for _, row in df.iterrows()},
        intersect_pagerank_name
    )
    logger.info(f"Added intersection PageRank to graph")


# ============================================================================
# Path Finding Functions
# ============================================================================

def k_shortest_paths(
    G,
    source: int,
    target: int,
    k: int = 1,
    weight: Optional[str] = None,
) -> List[List[int]]:
    """
    Find k shortest paths between source and target.
    
    Args:
        G: NetworkX graph
        source: Source node ID
        target: Target node ID
        k: Number of shortest paths to find
        weight: Optional edge weight attribute
        
    Returns:
        List of paths (each path is a list of node IDs)
    """
    paths = []
    n = 1
    try:
        for p in nx.shortest_simple_paths(G, source, target, weight=weight):
            if n > k:
                break
            paths.append(p)
            n += 1
    except (nx.NetworkXNoPath, nx.NetworkXError):
        return []
    return paths


def single_shortest_paths(
    G,
    sources: Set[int],
    targets: Set[int],
    weight: Optional[str] = None,
) -> List[List[int]]:
    """
    Find single shortest path from each source to each target.
    
    Args:
        G: NetworkX graph
        sources: Set of source node IDs
        targets: Set of target node IDs
        weight: Optional edge weight attribute
        
    Returns:
        List of paths (each path is a list of node IDs)
    """
    paths = []
    for s in sources:
        for t in targets:
            for p in _all_shortest_paths(G, s, t, weight=weight):
                paths.append(p)
                break  # Only take the first (shortest) path
    return paths


def _all_shortest_paths(
    D,
    source: int,
    target: int,
    weight: Optional[str] = None,
):
    """
    Generator for all shortest paths between source and target.
    
    Args:
        D: NetworkX graph
        source: Source node ID
        target: Target node ID
        weight: Optional edge weight attribute
        
    Yields:
        Shortest paths as lists of node IDs
    """
    try:
        for p in nx.all_shortest_paths(D, source, target, weight=weight):
            yield p
    except (NetworkXNoPath, NodeNotFound):
        return


def all_shortest_paths(
    D,
    sources: Set[int],
    targets: Set[int],
    weight: Optional[str] = None,
) -> List[List[int]]:
    """
    Find all shortest paths from any source to any target.
    
    Args:
        D: NetworkX graph
        sources: Set of source node IDs
        targets: Set of target node IDs  
        weight: Optional edge weight attribute
        
    Returns:
        List of all shortest paths
    """
    return [
        p
        for s in sources
        for t in targets
        for p in _all_shortest_paths(D, s, t, weight=weight)
    ]


def all_node_maxsum_paths(
    D,
    sources: Set[int],
    targets: Set[int],
    node_weight: str,
) -> List[List[int]]:
    """
    Find shortest paths weighted by node properties (max-sum).
    
    Higher values in the node weight property indicate better connections.
    
    Args:
        D: NetworkX graph
        sources: Set of source node IDs
        targets: Set of target node IDs
        node_weight: Node property name to use for weighting
        
    Returns:
        List of weighted shortest paths
    """
    tempkey = node_weight + "_maxsum"
    _D = D.copy(as_view=False)
    set_edge_weight_by_source_node_weight(_D, tempkey)
    paths = all_shortest_paths(_D, sources, targets, weight=tempkey)
    remove_edge_prop(D, tempkey)
    return paths


def set_edge_weight_by_source_node_weight(
    D,
    edge_weight_prop: str,
    node_weight_prop: Optional[str] = None,
    inverse: bool = True,
) -> None:
    """
    Set edge weights based on source node property.
    
    Args:
        D: NetworkX DiGraph (modified in place)
        edge_weight_prop: Property name to store edge weights
        node_weight_prop: Node property to use (default: same as edge_weight_prop)
        inverse: If True, use 1/weight; if False, use weight directly
    """
    if not node_weight_prop:
        node_weight_prop = edge_weight_prop
    
    for u, v, d in D.edges(data=True):
        u_wt = D.nodes[u].get(node_weight_prop, 0)
        if inverse:
            d[edge_weight_prop] = (1 / u_wt) if u_wt > 0 else sys.maxsize
        else:
            d[edge_weight_prop] = u_wt


def remove_edge_prop(D, edge_prop_name: str) -> None:
    """
    Remove property from all edges in graph.
    
    Args:
        D: NetworkX graph (modified in place)
        edge_prop_name: Property name to remove
    """
    for u, v, d in D.edges(data=True):
        if edge_prop_name in d:
            del d[edge_prop_name]


# ============================================================================
# Node Set Functions
# ============================================================================

def get_node_set_nodes(D) -> Set[int]:
    """
    Get all nodes that belong to any named node set in graph.
    
    Args:
        D: NetworkX graph
        
    Returns:
        Set of all node IDs in named node sets
    """
    nodes = set()
    if "node_sets" in D.graph:
        for k, ns in D.graph["node_sets"].items():
            if isinstance(ns, dict) and "nodes" in ns:
                nodes.update(ns["nodes"])
            elif isinstance(ns, set):
                nodes.update(ns)
    return nodes
