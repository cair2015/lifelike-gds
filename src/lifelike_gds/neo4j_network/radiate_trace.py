"""
Radiate trace analysis for Neo4j-based networks.

This module provides radiate analysis functionality, calculating how network
influence spreads from source nodes through the network using PageRank metrics.
"""

import logging
from typing import List, Dict, Optional, Tuple

import pandas as pd

from lifelike_gds.neo4j_network.trace_graph_nx import TraceGraphNx
from lifelike_gds.neo4j_network.trace_graph_utils import (
    add_pagerank,
    set_nReach,
    set_intersection_pagerank,
)
from lifelike_gds.network.trace_utils import add_trace_network

logger = logging.getLogger(__name__)


class RadiateTrace(TraceGraphNx):
    """
    Radiate trace analysis using Neo4j data.
    
    Performs PageRank-based analysis to identify influential nodes
    and paths from source nodes through the network.
    """

    def __init__(self, graphsource, multigraph: bool = True):
        """
        Initialize RadiateTrace.
        
        Args:
            graphsource: GraphSource instance for Neo4j queries
            multigraph: Whether to use MultiDiGraph (default: True)
        """
        super().__init__(graphsource, directed=True, multigraph=multigraph)

    @classmethod
    def get_pagerank_prop_name(cls, sources: str) -> str:
        """
        Get property name for forward PageRank.
        
        Args:
            sources: Name of source node set
            
        Returns:
            Property name for storing PageRank
        """
        return "pagerank"

    @classmethod
    def get_rev_pagerank_prop_name(cls, sources: str) -> str:
        """
        Get property name for reverse PageRank.
        
        Args:
            sources: Name of source node set
            
        Returns:
            Property name for storing reverse PageRank
        """
        return "rev_pagerank"

    @classmethod
    def get_intersection_rank_prop_name(cls, sources: str, targets: str) -> str:
        """
        Get property name for intersection PageRank.
        
        Args:
            sources: Name of source node set
            targets: Name of target node set
            
        Returns:
            Property name for storing intersection PageRank
        """
        return "intersect_pagerank"

    def set_pagerank_and_numreach(
        self,
        sources: str,
        direction: str = "both",
        personalization: Optional[Dict[int, float]] = None,
        contribution: bool = False,
    ) -> Tuple[bool, bool]:
        """
        Set personalized PageRank and reachability counts from sources.
        
        Args:
            sources: Name of source node set
            direction: 'forward', 'reverse', or 'both'
            personalization: Optional node weights for personalized PageRank
            contribution: Whether to calculate edge contributions
            
        Returns:
            Tuple of (has_incoming, has_outgoing) booleans
        """
        logger.info(f"Setting PageRank and reachability for source set: {sources}")
        
        source_set = self.graph.node_set(sources)
        
        if not source_set:
            logger.warning(f"Source set '{sources}' is empty")
            return False, False
        
        has_out = self.graph.has_out(source_set)
        has_in = self.graph.has_in(source_set)
        
        # Forward direction
        if has_out and direction in ("forward", "both"):
            pagerank_prop = RadiateTrace.get_pagerank_prop_name(sources)
            add_pagerank(
                self.graph,
                sources,
                pagerank_prop=pagerank_prop,
                personalization=personalization,
                contribution=contribution,
            )
            set_nReach(self.graph, sources)
        
        # Reverse direction
        if has_in and direction in ("reverse", "both"):
            rev_pagerank_prop = RadiateTrace.get_rev_pagerank_prop_name(sources)
            add_pagerank(
                self.graph,
                sources,
                pagerank_prop=rev_pagerank_prop,
                personalization=personalization,
                reverse=True,
                contribution=contribution,
            )
            set_nReach(self.graph, sources, reverse=True)
        
        return has_in, has_out

    def set_pagerank(
        self,
        sources: str,
        pagerank_prop: str,
        reverse: bool = False,
        personalization: Optional[Dict[int, float]] = None,
        contribution: bool = True,
    ) -> None:
        """
        Calculate and set PageRank for a source set.
        
        Args:
            sources: Name of source node set
            pagerank_prop: Property name to store PageRank values
            reverse: Whether to calculate reverse PageRank
            personalization: Optional node weights
            contribution: Whether to calculate edge contributions
        """
        add_pagerank(
            self.graph,
            sources,
            pagerank_prop=pagerank_prop,
            personalization=personalization,
            reverse=reverse,
            contribution=contribution,
        )

    def export_pagerank_data(
        self,
        sources: str,
        filename: str,
        sources_personalization: Optional[Dict[int, float]] = None,
        direction: str = "both",
        num_nodes: int = 3000,
        exclude_sources: bool = True,
    ) -> None:
        """
        Calculate PageRank and export results to Excel file.
        
        Args:
            sources: Name of source node set
            filename: Output Excel file path
            sources_personalization: Optional weights for source nodes
            direction: 'both', 'forward', or 'reverse'
            num_nodes: Maximum number of nodes to export
            exclude_sources: Whether to exclude source nodes from export
        """
        logger.info(f"Exporting PageRank data to {filename}")
        
        # Calculate PageRank
        self.set_pagerank_and_numreach(
            sources,
            direction=direction,
            personalization=sources_personalization,
            contribution=True,
        )
        
        # Extract PageRank values
        pagerank_prop = RadiateTrace.get_pagerank_prop_name(sources)
        pagerank_data = []
        
        for node_id, attrs in self.graph.nodes(data=True):
            if pagerank_prop in attrs:
                pagerank_data.append({
                    "node_id": node_id,
                    "pagerank": attrs[pagerank_prop],
                    "label": attrs.get("label", str(node_id)),
                })
        
        # Sort by PageRank
        df_pagerank = pd.DataFrame(pagerank_data)
        
        if not df_pagerank.empty:
            df_pagerank = df_pagerank.sort_values("pagerank", ascending=False)
            
            if exclude_sources:
                source_set = self.graph.node_set(sources)
                df_pagerank = df_pagerank[~df_pagerank["node_id"].isin(source_set)]
            
            # Limit to num_nodes
            df_pagerank = df_pagerank.head(num_nodes)
        
        # Export to Excel
        try:
            df_pagerank.to_excel(filename, index=False)
            logger.info(f"Exported {len(df_pagerank)} nodes to {filename}")
        except Exception as e:
            logger.error(f"Failed to export PageRank data: {e}")
            raise

    def add_radiate_analysis(
        self,
        sources: str,
        targets: Optional[str] = None,
        direction: str = "both",
        personalization: Optional[Dict[int, float]] = None,
    ) -> Optional[int]:
        """
        Add radiate analysis trace network.
        
        Args:
            sources: Name of source node set
            targets: Optional name of target node set
            direction: 'both', 'forward', or 'reverse'
            personalization: Optional node weights
            
        Returns:
            Index of added trace network, or None if failed
        """
        # Calculate PageRank
        has_in, has_out = self.set_pagerank_and_numreach(
            sources,
            direction=direction,
            personalization=personalization,
        )
        
        if not has_out and not has_in:
            logger.warning(f"No paths found from source set '{sources}'")
            return None
        
        # Add trace network
        source_name = self.graph.get_node_set_name(sources) if hasattr(self.graph, "get_node_set_name") else sources
        
        network_name = f"Radiate from {source_name}"
        
        try:
            if targets:
                target_name = self.graph.get_node_set_name(targets) if hasattr(self.graph, "get_node_set_name") else targets
                network_name = f"Radiate from {source_name} to {target_name}"
                
                networkIdx, num_paths = add_trace_network(
                    self.graph,
                    sources,
                    targets,
                    name=network_name,
                )
            else:
                networkIdx, num_paths = add_trace_network(
                    self.graph,
                    sources,
                    sources,  # Use sources as targets too
                    name=network_name,
                )
            
            if networkIdx is not None:
                self.add_graph_description(network_name)
                logger.info(f"Added radiate analysis: {network_name}")
            
            return networkIdx
        
        except Exception as e:
            logger.error(f"Failed to add radiate analysis: {e}")
            return None
