"""
In-betweenness trace analysis using NetworkX and database-agnostic implementation.

This module provides betweenness centrality analysis to identify influential nodes
and pathways connecting source and target nodes. Works with any database backend.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import networkx as nx

from lifelike_gds.network.trace_graph_nx import TraceGraphNx
from lifelike_gds.network.trace_graph_utils import (
    all_shortest_paths,
    remove_edge_prop,
    set_edge_weight_by_source_node_weight,
)


class InBetweennessTrace(TraceGraphNx):
    """
    In-betweenness trace analysis for network graphs.
    
    Computes betweenness centrality for nodes based on shortest paths between
    source and target node sets. Database-agnostic implementation.
    """
    
    def __init__(self, graphsource: Any, multigraph: bool = True) -> None:
        super().__init__(graphsource, multigraph=multigraph)

    def get_betweenness_prop_name(self, sources: str, targets: str) -> str:
        """
        Generate property name for betweenness values.
        
        Args:
            sources: Source node set name
            targets: Target node set name
            
        Returns:
            Property name string
        """
        return f"{sources}_{targets}_betweenness"

    def compute_inbetweenness(
        self,
        sources: str,
        targets: str,
        inbetweenness_prop_name: str | None = None,
        pagerank_prop: str | None = None,
    ) -> None:
        """
        Compute betweenness for paths from sources to destination, and save the value to given node property
        Args:
            sources: source node set name
            targets: target node set name
            inbetweenness_prop_name: property name for inbetweenness value
            pagerank_prop: optional node pagerank prop for calculate edge weight
        Returns:
        """
        logging.info('start computing inbetweenness')
        source_nodes = self.graph.node_set(sources)
        target_nodes = self.graph.node_set(targets)

        tempkey = None
        if pagerank_prop:
            tempkey = 'edge_wt'
            set_edge_weight_by_source_node_weight(self.graph, tempkey, pagerank_prop)

        inbetweenness: dict[Any, float] = {}
        for source_id in source_nodes:
            for target_id in target_nodes:
                # get all shortest paths between source and target
                paths = all_shortest_paths(self.graph, [source_id], [target_id], tempkey)
                if not paths:
                    continue
                num_paths = len(paths)
                # get nodes in all the paths, then count frequencies
                nodes = []
                for path in paths:
                    nodes.extend(path)
                node_freq = self._freq_count(nodes)
                # add frequences from each (source, target) pair to get betweenness values
                for k, v in node_freq.items():
                    freq = inbetweenness.setdefault(k, 0)
                    inbetweenness[k] = freq + float(v) / float(num_paths)
        sum_val = sum([v for v in inbetweenness.values()])
        betweenness_scaled = {k: v / sum_val for k, v in inbetweenness.items()}
        if not inbetweenness_prop_name:
            inbetweenness_prop_name = self.get_betweenness_prop_name(sources, targets)
        nx.set_node_attributes(self.graph, inbetweenness, inbetweenness_prop_name)
        nx.set_node_attributes(self.graph, betweenness_scaled, inbetweenness_prop_name + '_scaled')
        # clean up temp edge weight
        if tempkey:
            remove_edge_prop(self.graph, tempkey)

    def _freq_count(self, items: Iterable[Any]) -> dict[Any, int]:
        """
        Count item frequencies in an iterable.
        """
        items = list(items)
        freqs = {i: 0 for i in items}
        for k in freqs.keys():
            freqs[k] = items.count(k)
        return freqs

    def export_inbetweenness_data(
        self,
        sources: str,
        targets: str,
        filename: str,
        do_compute: bool = False,
    ) -> None:
        if do_compute:
            self.compute_inbetweenness(sources, targets)
        prop_name = self.get_betweenness_prop_name(sources, targets)
        all_nodes = [n for n, p in self.graph.nodes(data=True) if prop_name in p]
        exclude = set.union(self.graph.node_set(sources), self.graph.node_set(targets))
        export_nodes = set(all_nodes) - exclude
        df = self.get_nodes_detail_as_dataframe(export_nodes)
        filepath = f"{self.datadir}/{filename}"
        logging.info(f"export betweenness data into {filepath}")
        df.reset_index(drop=True).to_excel(filepath, index=False)

    def add_trace_from_sources_to_all_selected_nodes(
        self, 
        selected_nodeset: str,
        sources: str, 
        weighted_prop: str,
        trace_name: str = 'Sources to selected',
        shortest_paths_plus_n: int = 0,
    ) -> None:
        self.add_selected_nodes_traces_combined_network(
            selected_nodeset, 
            weighted_prop, 
            sources, 
            targets=None,
            trace_name=trace_name,
            shortest_paths_plus_n=shortest_paths_plus_n)
        self.add_graph_description(f"Traces from {sources} to all {selected_nodeset};")

    def add_trace_from_all_selected_nodes_to_targets(
        self, 
        selected_nodeset: str, 
        targets: str, 
        weighted_prop: str,
        trace_name: str = 'Selected to targets',
        shortest_paths_plus_n: int = 0,
    ) -> None:
        self.add_selected_nodes_traces_combined_network(
            selected_nodeset, 
            weighted_prop, 
            sources=None, 
            targets=targets,
            trace_name=trace_name, 
            shortest_paths_plus_n=shortest_paths_plus_n)
        self.add_graph_description(f"traces from all {selected_nodeset} to {targets}")

    def add_inbetweenness_trace_networks_with_selected_nodes(
        self, 
        select: str, 
        sources: str, 
        targets: str,
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add two traces: source to selected nodes, selected nodes to targets
        Args:
            select: selected node set name
            sources: source set name
            targets: target set name
            shortest_paths_plus_n: number of additional shortest paths to include
        Returns:
        """
        self.compute_inbetweenness(sources, targets)
        prop_name = self.get_betweenness_prop_name(sources, targets)
        self.add_trace_from_sources_to_all_selected_nodes(
            select,
            sources,
            prop_name,
            trace_name='Sources to selected',
            shortest_paths_plus_n=shortest_paths_plus_n)
        self.add_trace_from_all_selected_nodes_to_targets(
            select,
            targets,
            prop_name,
            trace_name='Selected to targets',
            shortest_paths_plus_n=shortest_paths_plus_n)


    def add_inbetweenness_trace_networks_with_selected_nodes_original(
        self,
        selected_nodes: list[dict[str, Any]],
        sources: str,
        targets: str,
        include_allshortest_path: bool = True,
        do_compute: bool = False,
        add_graphdesc: bool = True,
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add two traces: source to selected nodes, selected nodes to targets
        Args:
            selected_nodes: list of nodes
            sources: source set name
            targets: target set name
            include_allshortest_path: if True, add shortest paths to the graph
            do_compute: if True, compute in-betweenness values
            add_graphdesc: if True, add graph description
            shortest_paths_plus_n: number of additional shortest paths to include
        Returns:
        """
        if do_compute:
            self.compute_inbetweenness(sources, targets)
        prop_name = self.get_betweenness_prop_name(sources, targets)
        self.add_selected_nodes_trace_networks(selected_nodes, prop_name, 'inbetweenness', sources, targets, 
                                               include_allshortest_path, shortest_paths_plus_n=shortest_paths_plus_n)
        if add_graphdesc:
            self.add_graph_description(f"Traces from {sources} to {len(selected_nodes)} selected nodes;")
            self.add_graph_description(f"Traces from {len(selected_nodes)} selected nodes to {targets};")

    def add_best_n_inbetweenness_nodes_to_trace_networks(
        self,
        sources: str,
        targets: str,
        num: int = 10,
        do_compute: bool = False,
    ) -> None:
        """
        Add best n nodes.  Need to add more filters for the best nodes
        e.g. excluding EntitySet for reactome graph, excluding nodes based on num of source node reaches
        """
        if do_compute:
            self.compute_inbetweenness(sources, targets)
        source_nodes = self.graph.node_set(sources)
        target_nodes = self.graph.node_set(targets)
        excluded = source_nodes.union(target_nodes)
        prop_name = self.get_betweenness_prop_name(sources, targets)
        selected_nodes = self.get_most_weighted_nodes(prop_name, num, exclude_nodes=excluded)
        selected_key = f"top_{num}_{prop_name}"
        self.graph.set_node_set(
            selected_key,
            set(selected_nodes),
            name=f"top {num} betweenness nodes",
            description=f"top {num} nodes by {prop_name}",
        )
        self.add_inbetweenness_trace_networks_with_selected_nodes(
            selected_key,
            sources,
            targets,
        )
        self.add_graph_description(f"Traces from {sources} to top {num} betweenness nodes;")
        self.add_graph_description(f"Traces from top {num} betweenness nodes to {targets};")
