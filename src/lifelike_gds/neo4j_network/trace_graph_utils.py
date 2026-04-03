"""
Trace graph utility functions for Neo4j-based analysis.

This module provides helper functions for trace graph operations,
including PageRank calculations, path analysis, and file export.
"""

import logging
import os
from typing import List, Dict, Any, Optional, Set, Tuple

import networkx as nx
import pandas as pd
from neo4j.graph import Path

logger = logging.getLogger(__name__)


def add_pagerank(
    graph: "DirectedGraph",
    sources: str,
    pagerank_prop: str = "pagerank",
    personalization: Optional[Dict[int, float]] = None,
    reverse: bool = False,
    contribution: bool = False,
) -> None:
    """
    Calculate and add PageRank to graph nodes.
    
    Args:
        graph: NetworkX graph (DirectedGraph wrapper)
        sources: Name of source node set
        pagerank_prop: Property name to store PageRank values
        personalization: Initial personalization weights for sources
        reverse: Calculate reverse (incoming) PageRank
        contribution: Calculate contribution edges for Sankey visualization
    """
    source_set = graph.node_set(sources)
    
    if not source_set:
        logger.warning(f"Source set '{sources}' is empty")
        return
    
    # Prepare personalization weights
    if personalization is None:
        # Equal weight for all sources
        personalization = {node: 1.0 / len(source_set) for node in source_set}
    else:
        # Normalize personalization weights
        total = sum(personalization.values())
        if total > 0:
            personalization = {node: weight / total for node, weight in personalization.items()}
    
    # Use reverse graph if needed
    compute_graph = graph
    if reverse:
        compute_graph = graph.reverse()
    
    try:
        # Calculate PageRank
        pagerank = nx.pagerank(
            compute_graph,
            personalization=personalization,
            weight="weight",
        )
        
        # Store PageRank values
        nx.set_node_attributes(graph, pagerank, pagerank_prop)
        logger.info(f"Added PageRank '{pagerank_prop}' to {len(pagerank)} nodes")
        
        if contribution:
            _add_pagerank_contributions(graph, pagerank, reverse)
    
    except Exception as e:
        logger.error(f"Failed to calculate PageRank: {e}")
        raise


def _add_pagerank_contributions(
    graph: "DirectedGraph",
    pagerank: Dict[int, float],
    reverse: bool = False,
) -> None:
    """
    Add PageRank contribution values to edges for Sankey visualization.
    
    Args:
        graph: NetworkX graph
        pagerank: PageRank values
        reverse: Whether using reverse PageRank
    """
    # For each edge, calculate contribution based on PageRank
    contributions = {}
    
    for source, target in graph.edges():
        # Contribution is proportional to target's PageRank
        contribution_val = pagerank.get(target, 0.0)
        contributions[(source, target)] = contribution_val
    
    nx.set_edge_attributes(graph, contributions, "contribution")


def set_nReach(
    graph: "DirectedGraph",
    sources: str,
    reverse: bool = False,
) -> None:
    """
    Set number of reachable source nodes for each node.
    
    Args:
        graph: NetworkX graph
        sources: Name of source node set
        reverse: Calculate from reverse direction
    """
    source_set = graph.node_set(sources)
    
    if not source_set:
        logger.warning(f"Source set '{sources}' is empty")
        return
    
    compute_graph = graph
    if reverse:
        compute_graph = graph.reverse()
    
    # Calculate reachability from sources to all other nodes
    nreach = {}
    for node in graph.nodes():
        nreach[node] = 0
    
    for source in source_set:
        try:
            # Get all reachable nodes from this source
            reachable = nx.descendants(compute_graph, source)
            for node in reachable:
                nreach[node] = nreach.get(node, 0) + 1
        except nx.NetworkXError:
            pass
    
    # Store nReach values
    prop_name = "nReach_reverse" if reverse else "nReach"
    nx.set_node_attributes(graph, nreach, prop_name)
    logger.info(f"Added reachability counts to graph")


def set_intersection_pagerank(
    graph: "DirectedGraph",
    sources: str,
    targets: str,
    prop_name: str = "intersect_pagerank",
) -> None:
    """
    Calculate PageRank for nodes that reach multiple targets.
    
    Args:
        graph: NetworkX graph
        sources: Name of source node set
        targets: Name of target node set
        prop_name: Property name to store results
    """
    source_set = graph.node_set(sources)
    target_set = graph.node_set(targets)
    
    if not source_set or not target_set:
        logger.warning("Source or target set is empty")
        return
    
    # Calculate which nodes can reach each target
    intersection_ranks = {}
    for node in graph.nodes():
        intersection_ranks[node] = 0.0
    
    # For each target, calculate PageRank from sources constrained to paths to that target
    for target in target_set:
        try:
            # Find predecessors of target
            predecessors = nx.ancestors(graph, target)
            if predecessors:
                # Calculate PageRank within subgraph
                subgraph = graph.subgraph(predecessors | {target})
                personalization = {n: 1.0 / len(source_set) for n in source_set if n in subgraph}
                
                if personalization:
                    local_pr = nx.pagerank(subgraph, personalization=personalization)
                    for node, rank in local_pr.items():
                        intersection_ranks[node] = intersection_ranks.get(node, 0.0) + rank
        except nx.NetworkXError:
            pass
    
    nx.set_node_attributes(graph, intersection_ranks, prop_name)
    logger.info(f"Added intersection PageRank to graph")


def write_sankey_file(
    graph,
    filepath: str,
    layout: Optional[Dict[int, Tuple[float, float]]] = None,
) -> None:
    """
    Export graph as Sankey diagram data.
    
    Args:
        graph: NetworkX graph
        filepath: Output file path
        layout: Optional node layout dictionary
    """
    # Implement Sankey export
    logger.info(f"Sankey file export not yet implemented: {filepath}")
    pass


def write_cytoscape_file(
    graph,
    filepath: str,
    format_type: str = "cytoscape",
) -> None:
    """
    Export graph in Cytoscape-compatible format.
    
    Args:
        graph: NetworkX graph
        filepath: Output file path
        format_type: Format type (cytoscape, json, etc.)
    """
    # Implement Cytoscape export
    logger.info(f"Cytoscape file export not yet implemented: {filepath}")
    pass


def k_shortest_paths(
    graph,
    source: int,
    target: int,
    k: int = 1,
    weight: Optional[str] = None,
) -> List[List[int]]:
    """
    Find k shortest paths between source and target.
    
    Args:
        graph: NetworkX graph
        source: Source node ID
        target: Target node ID
        k: Number of shortest paths to find
        weight: Optional edge weight attribute
        
    Returns:
        List of paths (each path is a list of node IDs)
    """
    try:
        if hasattr(nx, 'shortest_simple_paths'):
            paths = list(nx.shortest_simple_paths(graph, source, target, weight=weight))
            return paths[:k]
        else:
            # Fallback for older NetworkX versions
            try:
                path = nx.shortest_path(graph, source, target, weight=weight)
                return [path]
            except nx.NetworkXNoPath:
                return []
    except (nx.NetworkXError, nx.NetworkXNoPath) as e:
        logger.debug(f"No paths found from {source} to {target}: {e}")
        return []


def single_shortest_paths(
    graph,
    source: int,
    targets: Set[int],
    weight: Optional[str] = None,
) -> Dict[int, List[int]]:
    """
    Find shortest paths from source to multiple targets.
    
    Args:
        graph: NetworkX graph
        source: Source node ID
        targets: Set of target node IDs
        weight: Optional edge weight attribute
        
    Returns:
        Dictionary mapping target nodes to their shortest paths
    """
    paths = {}
    
    try:
        # Calculate shortest path lengths from source
        lengths = nx.single_source_shortest_path_length(graph, source, weight=weight)
        
        # For each target, get the path
        for target in targets:
            if target in lengths:
                try:
                    path = nx.shortest_path(graph, source, target, weight=weight)
                    paths[target] = path
                except nx.NetworkXNoPath:
                    pass
    
    except nx.NetworkXError as e:
        logger.debug(f"Error calculating paths from {source}: {e}")
    
    return paths


def get_node_set_nodes(graph) -> Set[int]:
    """
    Get all nodes that belong to any named node set.
    
    Args:
        graph: NetworkX graph
        
    Returns:
        Set of node IDs
    """
    all_nodes = set()
    
    node_sets = graph.graph.get("node_sets", {})
    for node_set_data in node_sets.values():
        if isinstance(node_set_data, dict):
            nodes = node_set_data.get("nodes", set())
            all_nodes.update(nodes)
    
    return all_nodes


def extract_node_ids_from_path(path: Path) -> List[int]:
    """
    Extract node IDs from Neo4j path object.
    
    Args:
        path: Neo4j Path object
        
    Returns:
        List of node IDs
    """
    node_ids = []
    
    if hasattr(path, 'nodes'):
        for node in path.nodes:
            if hasattr(node, 'id'):
                node_ids.append(node.id)
            elif isinstance(node, dict) and 'id' in node:
                node_ids.append(node['id'])
    
    return node_ids


def extract_relationships_from_path(path: Path) -> List[Tuple[int, int, str]]:
    """
    Extract relationships from Neo4j path object.
    
    Args:
        path: Neo4j Path object
        
    Returns:
        List of (source_id, target_id, relationship_type) tuples
    """
    relationships = []
    
    if hasattr(path, 'relationships'):
        for rel in path.relationships:
            if hasattr(rel, 'start_node') and hasattr(rel, 'end_node'):
                source_id = rel.start_node.id if hasattr(rel.start_node, 'id') else None
                target_id = rel.end_node.id if hasattr(rel.end_node, 'id') else None
                rel_type = rel.type if hasattr(rel, 'type') else None
                
                if source_id is not None and target_id is not None and rel_type is not None:
                    relationships.append((source_id, target_id, rel_type))
    
    return relationships
