"""
Radiate trace analysis using NetworkX and database-agnostic implementation.

This module provides PageRank-based radiate analysis to identify influential nodes
and pathways from source nodes through the network. Works with any database backend.
"""

import logging
import os
from typing import List, Dict, Optional, Tuple

import pandas as pd

from pathway_graphx.network.trace_graph_nx import TraceGraphNx
from pathway_graphx.network.trace_graph_utils import (
    add_pagerank,
    set_nReach,
    set_intersection_pagerank,
)
from pathway_graphx.network.trace_utils import add_trace_network
from pathway_graphx.network.collection_utils import dict_max_ties

logger = logging.getLogger(__name__)


class RadiateTrace(TraceGraphNx):
    """
    Radiate trace analysis for network graphs.
    
    Performs PageRank-based analysis to identify influential nodes
    and paths from source nodes through the network. Database-agnostic.
    """

    def __init__(self, graphsource, multigraph: bool = True):
        """
        Initialize RadiateTrace.
        
        Args:
            graphsource: Database source implementing GraphSource interface
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
            Tuple of (has_incoming_edges, has_outgoing_edges) booleans
        """
        logger.info(f"Setting PageRank and reachability for source set: {sources}")
        
        source_set = self.graph.node_set(sources)
        
        if not source_set:
            logger.warning(f"Source set '{sources}' is empty")
            return False, False
        
        has_out = self.graph.has_out(source_set)
        has_in = self.graph.has_in(source_set)
        
        # Forward direction (PageRank flowing out from sources)
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
        
        # Reverse direction (PageRank flowing into sources)
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
        
        if sources_personalization is None:
            sources_personalization = {}

        # Calculate PageRank
        has_in, has_out = self.set_pagerank_and_numreach(
            sources,
            personalization=sources_personalization,
            direction=direction,
        )

        pr_name = self.get_pagerank_prop_name(sources)
        pr_reach = 'nReach'
        rev_pr_name = self.get_rev_pagerank_prop_name(sources)
        rev_reach = 'rev_' + pr_reach

        excludes = []
        if exclude_sources:
            excludes = self.graph.node_set(sources)

        best_forward_nodes = []
        best_reverse_nodes = []

        # Process forward PageRanks
        if has_out and direction != 'reverse':
            includes = [
                n for n, p in self.graph.nodes(data=True)
                if p.get(pr_name, 0) > 0
            ]
            if len(includes) > 0:
                best_forward_nodes = self.get_most_weighted_nodes(
                    pr_name,
                    num_nodes,
                    include_nodes=includes,
                    exclude_nodes=excludes,
                )

        # Process reverse PageRanks
        if has_in and direction != 'forward':
            includes = [
                n for n, p in self.graph.nodes(data=True)
                if p.get(rev_pr_name, 0) > 0
            ]
            if len(includes) > 0:
                best_reverse_nodes = self.get_most_weighted_nodes(
                    rev_pr_name,
                    num_nodes,
                    include_nodes=includes,
                    exclude_nodes=excludes,
                )

        all_nodes = set(best_forward_nodes + best_reverse_nodes)
        df = self.get_nodes_detail_as_dataframe(list(all_nodes))
        df['select'] = ''

        filepath = os.path.join(self.datadir, filename)
        logger.info(f"Exporting top {num_nodes} PageRank nodes to {filepath}")
        
        try:
            with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                if len(best_forward_nodes) > 0:
                    df_forward = df[df.index.isin(set(best_forward_nodes))]
                    if has_in and direction != 'forward':
                        cols_to_drop = [c for c in [rev_pr_name, rev_reach] if c in df_forward.columns]
                        df_forward = df_forward.drop(columns=cols_to_drop, errors='ignore')
                    df_forward.sort_values(by=[pr_name], ascending=False, inplace=True)
                    df_forward.to_excel(writer, sheet_name="pageranks")

                if len(best_reverse_nodes) > 0:
                    df_reverse = df[df.index.isin(set(best_reverse_nodes))]
                    if has_out and direction != 'reverse':
                        cols_to_drop = [c for c in [pr_name, pr_reach] if c in df_reverse.columns]
                        df_reverse = df_reverse.drop(columns=cols_to_drop, errors='ignore')
                    df_reverse.sort_values(by=[rev_pr_name], ascending=False, inplace=True)
                    df_reverse.to_excel(writer, sheet_name="reverse pageranks")

            logger.info(f"Exported to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export PageRank data: {e}")
            raise

    def add_traces_from_sources_to_each_selected_nodes(
        self,
        selected_nodes: List,
        sources: str,
        weighted_prop: Optional[str] = None,
        selected_nodes_name: Optional[str] = None,
        include_shortest_paths: bool = True,
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add individual traces from sources to each selected node.
        
        Args:
            selected_nodes: List of selected database node objects
            sources: Source node set name
            weighted_prop: PageRank property name (optional)
            selected_nodes_name: User-defined name for selected nodes
            include_shortest_paths: Whether to include shortest path traces
            shortest_paths_plus_n: Include paths N steps longer than shortest
        """
        if not weighted_prop:
            weighted_prop = self.get_pagerank_prop_name(sources)
        
        prefix = 'Forward'
        if selected_nodes_name:
            prefix += ' ' + selected_nodes_name
        
        self.add_selected_nodes_trace_networks(
            selected_nodes,
            weighted_prop,
            prefix,
            sources=sources,
            include_allshortest_path=include_shortest_paths,
            shortest_paths_plus_n=shortest_paths_plus_n,
        )
        
        if selected_nodes_name:
            self.add_graph_description(
                f"Traces from {sources} to each of the {len(selected_nodes)} {selected_nodes_name} nodes"
            )
        else:
            self.add_graph_description(
                f"Traces from {sources} to each of the {len(selected_nodes)} selected nodes"
            )

    def add_trace_from_sources_to_all_selected_nodes(
        self,
        selected_nodeset: str,
        sources: str,
        weighted_prop: Optional[str] = None,
        trace_name: str = 'Forward combined',
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add traces from sources to all selected nodes combined.
        
        Args:
            selected_nodeset: Node set name for selected nodes
            sources: Source node set name
            weighted_prop: PageRank property name (optional)
            trace_name: Name for trace network
            shortest_paths_plus_n: Include paths N steps longer than shortest
        """
        if not weighted_prop:
            weighted_prop = self.get_pagerank_prop_name(sources)
        
        self.add_selected_nodes_traces_combined_network(
            selected_nodeset,
            weighted_prop,
            sources=sources,
            targets=None,
            trace_name=trace_name,
            shortest_paths_plus_n=shortest_paths_plus_n,
        )
        
        self.add_graph_description(f"Traces from {sources} to all {selected_nodeset}")

    def add_traces_from_each_selected_nodes_to_targets(
        self,
        selected_nodes: List,
        targets: str,
        weighted_prop: Optional[str] = None,
        selected_nodes_name: Optional[str] = None,
        include_allshortest_path: bool = True,
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add traces from each selected node to targets.
        
        Args:
            selected_nodes: List of selected database node objects
            targets: Target node set name
            weighted_prop: PageRank property name (optional)
            selected_nodes_name: User-defined name for selected nodes
            include_allshortest_path: Whether to include shortest path traces
            shortest_paths_plus_n: Include paths N steps longer than shortest
        """
        if not weighted_prop:
            weighted_prop = self.get_rev_pagerank_prop_name(targets)
        
        prefix = 'Reverse'
        if selected_nodes_name:
            prefix += ' ' + selected_nodes_name
        
        self.add_selected_nodes_trace_networks(
            selected_nodes,
            weighted_prop,
            prefix,
            targets=targets,
            include_allshortest_path=include_allshortest_path,
            shortest_paths_plus_n=shortest_paths_plus_n,
        )
        
        if selected_nodes_name:
            self.add_graph_description(
                f"Traces from each of the {len(selected_nodes)} {selected_nodes_name} nodes to {targets}"
            )
        else:
            self.add_graph_description(
                f"Traces from each of the {len(selected_nodes)} selected nodes to {targets}"
            )

    def add_trace_from_all_selected_nodes_to_targets(
        self,
        selected_nodeset: str,
        targets: str,
        weighted_prop: Optional[str] = None,
        trace_name: str = 'Reverse combined',
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add traces from all selected nodes to targets combined.
        
        Args:
            selected_nodeset: Node set name for selected nodes
            targets: Target node set name
            weighted_prop: PageRank property name (optional)
            trace_name: Name for trace network
            shortest_paths_plus_n: Include paths N steps longer than shortest
        """
        if not weighted_prop:
            weighted_prop = self.get_rev_pagerank_prop_name(targets)
        
        self.add_selected_nodes_traces_combined_network(
            selected_nodeset,
            weighted_prop,
            sources=None,
            targets=targets,
            trace_name=trace_name,
            shortest_paths_plus_n=shortest_paths_plus_n,
        )
        
        self.add_graph_description(f"Traces from all {selected_nodeset} to {targets}")

    def set_intersection_pagerank(
        self,
        source_pr: str,
        target_rev_pr: str,
        intersect_pr: str,
    ) -> None:
        """
        Calculate intersection PageRank combining forward and reverse PageRank.
        
        Args:
            source_pr: Property name for forward PageRank
            target_rev_pr: Property name for reverse PageRank
            intersect_pr: Property name to store intersection PageRank
        """
        set_intersection_pagerank(self.graph, source_pr, target_rev_pr, intersect_pr)

    def export_intersection_pageranks(
        self,
        excel_filename: str,
        source_set: str,
        target_set: str,
        source_personalization: Optional[Dict[int, float]] = None,
        target_personalization: Optional[Dict[int, float]] = None,
        num_nodes: int = 3000,
        exclude_sources: bool = True,
    ) -> None:
        """
        Calculate intersection PageRank and export to Excel file.
        
        Args:
            excel_filename: Output Excel file path
            source_set: Source node set name
            target_set: Target node set name
            source_personalization: Optional weights for source nodes
            target_personalization: Optional weights for target nodes
            num_nodes: Maximum number of nodes to export
            exclude_sources: Whether to exclude source/target nodes
        """
        if source_personalization is None:
            source_personalization = {}
        if target_personalization is None:
            target_personalization = {}

        # Calculate PageRanks
        self.set_pagerank_and_numreach(
            source_set,
            direction='forward',
            personalization=source_personalization,
        )
        self.set_pagerank_and_numreach(
            target_set,
            direction='reverse',
            personalization=target_personalization,
        )

        # Get property names
        pr_prop = self.get_pagerank_prop_name(source_set)
        rev_pr_prop = self.get_rev_pagerank_prop_name(target_set)
        inter_pr_prop = self.get_intersection_rank_prop_name(source_set, target_set)

        # Calculate intersection
        self.set_intersection_pagerank(pr_prop, rev_pr_prop, inter_pr_prop)

        # Get nodes with both forward and reverse PageRank
        excluded = []
        if exclude_sources:
            excluded = list(self.graph.node_set(source_set)) + list(self.graph.node_set(target_set))

        inter_nodes = [
            n for n, d in self.graph.nodes(data=True)
            if d.get(pr_prop, 0) > 0 and d.get(rev_pr_prop, 0) > 0
        ]

        nodes = self.get_most_weighted_nodes(
            inter_pr_prop,
            num_nodes,
            include_nodes=inter_nodes,
            exclude_nodes=excluded,
        )

        df = self.get_nodes_detail_as_dataframe(nodes)
        df.sort_values(by=[inter_pr_prop], ascending=False, inplace=True)
        df['select'] = ''

        filepath = os.path.join(self.datadir, excel_filename)
        logger.info(f"Exporting intersection PageRank to {filepath}")
        
        try:
            df.to_excel(filepath, index=False)
            logger.info(f"Exported {len(df)} nodes to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export intersection PageRank: {e}")
            raise
