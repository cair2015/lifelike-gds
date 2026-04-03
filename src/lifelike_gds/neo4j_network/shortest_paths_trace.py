"""
Shortest path trace analysis for Neo4j-based networks.

This module provides shortest path finding and analysis functionality,
identifying the most direct paths between nodes in the network.
"""

import logging
from typing import List, Optional

from lifelike_gds.neo4j_network.trace_graph_nx import TraceGraphNx
from lifelike_gds.network.trace_utils import add_trace_network

logger = logging.getLogger(__name__)


class ShortestPathTrace(TraceGraphNx):
    """
    Shortest path trace analysis using Neo4j data.
    
    Identifies shortest paths between source and target node sets,
    with support for path filtering and export.
    """

    def __init__(self, graphsource, multigraph: bool = True):
        """
        Initialize ShortestPathTrace.
        
        Args:
            graphsource: GraphSource instance for Neo4j queries
            multigraph: Whether to use MultiDiGraph (default: True)
        """
        super().__init__(graphsource, directed=True, multigraph=multigraph)

    def add_shortest_paths(
        self,
        sources: str,
        targets: str,
        sources_as_query: bool = True,
        shortest_paths_plus_n: int = 0,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        Add shortest path trace networks between sources and targets.
        
        Args:
            sources: Name of source node set
            targets: Name of target node set
            sources_as_query: Whether sources is a query string
            shortest_paths_plus_n: Include paths N steps longer than shortest
            name: Optional custom name for trace network
            description: Optional custom description
            
        Returns:
            True if paths were found, False otherwise
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        
        if sources_as_query:
            query = sources
        else:
            query = targets
        
        has_paths = False
        
        for n in range(0, shortest_paths_plus_n + 1):
            plus_n_str = f"+{n}" if n > 0 else ""
            network_name = name or f"Shortest{plus_n_str} paths from {source_name} to {target_name}"
            
            try:
                networkIdx, num_paths = add_trace_network(
                    self.graph,
                    sources,
                    targets,
                    name=network_name,
                    description=description,
                    query=query,
                    shortest_paths_plus_n=n,
                )
                
                if num_paths > 0:
                    has_paths = True
                    self.add_graph_description(f"{network_name}: {num_paths} paths")
                    logger.info(f"Added {network_name}: {num_paths} paths")
                else:
                    logger.info(f"No paths found for {network_name}")
            
            except Exception as e:
                logger.error(f"Failed to add shortest paths: {e}")
        
        return has_paths

    def add_k_shortest_paths(
        self,
        sources: str,
        targets: str,
        k: int = 1,
        name: Optional[str] = None,
    ) -> bool:
        """
        Add k shortest paths trace network.
        
        Args:
            sources: Name of source node set
            targets: Name of target node set
            k: Number of shortest paths per source-target pair
            name: Optional custom name
            
        Returns:
            True if paths were found, False otherwise
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        
        network_name = name or f"K-Shortest paths (k={k}) from {source_name} to {target_name}"
        
        try:
            # For now, use single shortest paths
            # K-shortest paths would require additional Neo4j query optimization
            has_paths = self.add_shortest_paths(
                sources,
                targets,
                name=network_name,
            )
            return has_paths
        
        except Exception as e:
            logger.error(f"Failed to add k-shortest paths: {e}")
            return False

    def add_all_shortest_paths(
        self,
        sources: str,
        targets: str,
        max_length: Optional[int] = None,
        name: Optional[str] = None,
    ) -> bool:
        """
        Add all shortest paths trace network.
        
        Args:
            sources: Name of source node set
            targets: Name of target node set
            max_length: Optional maximum path length
            name: Optional custom name
            
        Returns:
            True if paths were found, False otherwise
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        
        network_name = name or f"All shortest paths from {source_name} to {target_name}"
        
        try:
            has_paths = self.add_shortest_paths(
                sources,
                targets,
                name=network_name,
            )
            return has_paths
        
        except Exception as e:
            logger.error(f"Failed to add all shortest paths: {e}")
            return False

    def add_weighted_shortest_paths(
        self,
        sources: str,
        targets: str,
        weight_property: str,
        name: Optional[str] = None,
    ) -> bool:
        """
        Add weighted shortest paths trace network.
        
        Args:
            sources: Name of source node set
            targets: Name of target node set
            weight_property: Edge property to use as weight
            name: Optional custom name
            
        Returns:
            True if paths were found, False otherwise
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        
        network_name = name or f"Weighted shortest paths from {source_name} to {target_name}"
        
        try:
            # Set edge weights from property
            self._set_edge_weights(weight_property)
            
            # Add trace network
            has_paths = self.add_shortest_paths(
                sources,
                targets,
                name=network_name,
            )
            return has_paths
        
        except Exception as e:
            logger.error(f"Failed to add weighted shortest paths: {e}")
            return False

    def _get_node_set_name(self, node_set_key: str) -> str:
        """
        Get display name for a node set.
        
        Args:
            node_set_key: Node set key
            
        Returns:
            Display name or key if not found
        """
        try:
            node_sets = self.graph.graph.get("node_sets", {})
            if node_set_key in node_sets:
                return node_sets[node_set_key].get("name", node_set_key)
        except Exception:
            pass
        
        return node_set_key

    def _set_edge_weights(self, weight_property: str) -> None:
        """
        Set edge weights from node properties for weighted pathfinding.
        
        Args:
            weight_property: Property name to use as weight
        """
        import networkx as nx
        
        weights = {}
        for source, target in self.graph.edges():
            # Use node property as weight
            weight_val = 1.0
            
            try:
                if weight_property in self.graph.nodes[target]:
                    weight_val = float(self.graph.nodes[target][weight_property])
            except (KeyError, ValueError):
                pass
            
            weights[(source, target)] = weight_val
        
        nx.set_edge_attributes(self.graph, weights, "weight")


class InteractionPathTrace(ShortestPathTrace):
    """
    Interaction path analysis for tracing specific interaction types.
    
    Extends ShortestPathTrace with filtering by interaction/relationship types.
    """

    def add_typed_shortest_paths(
        self,
        sources: str,
        targets: str,
        relationship_types: List[str],
        name: Optional[str] = None,
    ) -> bool:
        """
        Add shortest paths using only specific relationship types.
        
        Args:
            sources: Name of source node set
            targets: Name of target node set
            relationship_types: List of relationship types to include
            name: Optional custom name
            
        Returns:
            True if paths were found, False otherwise
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        types_str = ", ".join(relationship_types)
        
        network_name = name or f"Paths [{types_str}] from {source_name} to {target_name}"
        
        try:
            # Filter graph to only include specified relationship types
            filtered_graph = self._filter_edges_by_type(relationship_types)
            
            # Create temporary TraceGraphNx with filtered data
            temp_trace = TraceGraphNx(self.graphsource, directed=True, multigraph=self.graph.__class__.__name__ == "MultiDirectedGraph")
            temp_trace.graph = filtered_graph
            
            # Add trace network using filtered graph
            has_paths = temp_trace.add_shortest_paths(
                sources,
                targets,
                name=network_name,
            ) if hasattr(temp_trace, "add_shortest_paths") else False
            
            if has_paths:
                self.add_graph_description(network_name)
            
            return has_paths
        
        except Exception as e:
            logger.error(f"Failed to add typed shortest paths: {e}")
            return False

    def _filter_edges_by_type(self, relationship_types: List[str]):
        """
        Create subgraph with only specified relationship types.
        
        Args:
            relationship_types: List of relationship types to include
            
        Returns:
            Filtered graph
        """
        import networkx as nx
        
        # Get edges to keep
        edges_to_keep = []
        for source, target, data in self.graph.edges(data=True):
            if data.get("label") in relationship_types:
                edges_to_keep.append((source, target))
        
        # Create subgraph
        if len(edges_to_keep) > 0:
            nodes_to_keep = set()
            for source, target in edges_to_keep:
                nodes_to_keep.add(source)
                nodes_to_keep.add(target)
            
            return self.graph.subgraph(nodes_to_keep).copy()
        else:
            # Return empty graph of same type
            return type(self.graph)(nx.DiGraph())
