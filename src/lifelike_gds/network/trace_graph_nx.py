"""
Unified TraceGraph using NetworkX for network analysis.

This module provides the TraceGraphNx class that loads graph data from any database
implementation (ArangoDB, Neo4j, etc.), builds lightweight NetworkX graphs, and
performs network analysis operations. All network analysis is database-agnostic
and uses NetworkX for algorithms.
"""

import logging
import os.path
import inspect
from typing import Any, List, Optional, Set, Union
from pathlib import Path

import networkx as nx
import pandas as pd

from lifelike_gds.network.groups import set_default_groups
from lifelike_gds.network.graph_utils import MultiDirectedGraph, DirectedGraph
from lifelike_gds.network.trace_utils import add_trace_network, get_traced_nodes
from lifelike_gds.network.trace_graph_utils import write_sankey_file, write_cytoscape_file
from lifelike_gds.network.collection_utils import dict_max_ties, dict_min_ties
logger = logging.getLogger(__name__)


class TraceGraphNx:
    """
    Database-agnostic lightweight trace graph using NetworkX backend.
    
    This class creates a projected graph containing only node IDs and relationships.
    Detailed node properties are loaded on-demand from the database via GraphSource.
    
    The class is independent of the underlying database (ArangoDB, Neo4j, etc.)
    and relies on a GraphSource interface for database operations.
    """

    def __init__(self, graphsource, directed: bool = True, multigraph: bool = True):
        """
        Initialize TraceGraphNx with a database source.
        
        Args:
            graphsource: Database source implementing GraphSource interface
            directed: Whether graph is directed (default: True)
            multigraph: Whether to use MultiDiGraph (default: True)
        """
        self.graphsource = graphsource
        self.directed = directed
        self.paths = []
        self.datadir = "."
        
        if multigraph:
            self.graph = MultiDirectedGraph(nx.MultiDiGraph())
        else:
            self.graph = DirectedGraph(nx.DiGraph())
        
        # Save original graph for multiple analyses
        self.orig_graph = self.graph

    def init_default_graph(self, exclude_currency: bool = True, exclude_secondary: bool = True) -> None:
        """
        Initialize graph with default nodes and relationships from database.
        
        Args:
            exclude_currency: Exclude currency metabolite nodes
            exclude_secondary: Exclude secondary metabolite nodes
        """
        initiate_trace_graph = self.graphsource.initiate_trace_graph
        kwargs = {"exclude_currency": exclude_currency}
        signature = inspect.signature(initiate_trace_graph)

        if (
            "exclude_secondary" in signature.parameters
            or any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
        ):
            kwargs["exclude_secondary"] = exclude_secondary

        initiate_trace_graph(self, **kwargs)

    def set_datadir(self, datadir: str) -> None:
        """
        Set data directory for output files.
        
        Args:
            datadir: Path to data directory
        """
        self.datadir = datadir
        if not os.path.exists(datadir):
            os.makedirs(datadir, exist_ok=True)

    def add_nodes(self, node_query: str, **parameters) -> None:
        """
        Add nodes to graph from database query result.
        
        Query should return 'node_id' column containing node IDs.
        
        Args:
            node_query: Query string (Cypher, AQL, etc.) returning node IDs
            **parameters: Query parameters
        """
        node_data = self.graphsource.database.get_dataframe(node_query, **parameters)
        
        if not node_data.empty:
            nodes = list(node_data["node_id"])
            self.graph.add_nodes_from(nodes)
            logger.info(f"Added {len(nodes)} nodes to graph")

    def add_rels(self, rel_query: str, **parameters) -> None:
        """
        Add relationships to graph from database query result.
        
        Query should return 'source', 'target', and 'type' columns.
        
        Args:
            rel_query: Query string returning relationships
            **parameters: Query parameters
        """
        rel_data = self.graphsource.database.get_dataframe(rel_query, **parameters)
        
        for _, row in rel_data.iterrows():
            source = row["source"]
            target = row["target"]
            rel_type = row["type"]
            self.graph.add_edge(source, target, label=rel_type)
        
        logger.info(f"Added {len(rel_data)} relationships to graph")

    def add_nodes_rels_from_paths(self, paths: List) -> None:
        """
        Add nodes and relationships from database path results.
        
        Args:
            paths: List of path objects from database
        """
        for p in paths:
            self.graph.add_nodes_from([self.graphsource.get_node_id(n) for n in p.nodes])
            for r in p.relationships:
                self.graph.add_edge(
                    self.graphsource.get_node_id(r.start_node),
                    self.graphsource.get_node_id(r.end_node),
                    label=r.type,
                )

    def set_node_set(self, key: str, nodes: Set[int], **meta) -> None:
        """
        Set a named node set in the graph.
        
        Args:
            key: Unique identifier for the node set
            nodes: Set of node IDs
            **meta: Additional metadata for the node set (name, description, etc.)
        """
        self.graph.set_node_set(key, nodes, **meta)

    def set_node_set_from_db_nodes(self, nodes: List, name: str, desc: str) -> None:
        """
        Create node set from database node records.
        
        Uses the active graph source to extract node IDs from database objects.
        
        Args:
            nodes: List of database node records/objects
            name: Name for the node set
            desc: Description for the node set
        """
        node_ids = [self.graphsource.get_node_id(n) for n in nodes]
        node_set = set(node_ids).intersection(self.graph.nodes)
        self.graph.set_node_set(name, node_set, name=name, description=desc)
        logger.info(f"Created node set '{name}' with {len(node_set)} nodes")

    def set_node_set_from_arango_nodes(self, nodes: List, name: str, desc: str) -> None:
        """Backward-compatible alias kept for older notebooks and examples."""
        self.set_node_set_from_db_nodes(nodes, name, desc)

    def set_node_set_for_node(self, node) -> str:
        """
        Create node set for a single node.
        
        Args:
            node: Database node record/object
            
        Returns:
            Node set key
        """
        node_id = self.graphsource.get_node_id(node)
        key = f"node_{node_id}"
        name = node.get('displayName') or node.get('name', str(node_id))
        
        self.set_node_set(key, {node_id}, name=name, description=name)
        return key

    def add_graph_description(self, desc: str) -> None:
        """
        Add description to graph.
        
        Args:
            desc: Description text
        """
        self.graph.describe(desc)

    def set_nodes_flag(self, node_set_name: str, flag_val) -> None:
        """
        Set flag value for all nodes in a node set.
        
        Args:
            node_set_name: Name of the node set
            flag_val: Flag value to set
        """
        nodes = self.graph.node_set(node_set_name)
        node_vals = {n: flag_val for n in nodes}
        nx.set_node_attributes(self.graph, node_vals, "flag")

    def get_node_label(self, node_id: int) -> str:
        """
        Get label for a node.
        
        Args:
            node_id: Node ID
            
        Returns:
            Node label/display name
        """
        return self.graph.nodes[node_id].get(self.graphsource.node_label_prop, str(node_id))

    def load_node_detail_from_db(self, nodes: List[Any]) -> None:
        """
        Load detailed node properties from database.
        
        Args:
            nodes: List of node IDs
        """
        self.graphsource.load_node_details(nodes, self.graph)

    def clean_graph(self) -> None:
        """
        Remove unused nodes and edges to create lightweight graph.
        
        Keeps only nodes and edges that are part of traces or in named node sets.
        """
        node_size1 = len(self.graph)
        nodes = get_traced_nodes(self.graph)
        
        # Get nodes in named node sets
        nodeset_nodes = set()
        node_sets = self.graph.graph.get("node_sets", {})
        for node_set in node_sets.values():
            # nodeset_nodes.update(node_set.get("nodes", set()))
            nodeset_nodes.update(node_set)
        
        nodes.update(nodeset_nodes)
        self.graph = self.graph.keep(nodes)
        node_size2 = len(self.graph)
        
        logger.info(f"Cleaned graph: {node_size1} -> {node_size2} nodes")
        set_default_groups(self.graph)

    def load_graph_detail(self) -> None:
        """
        Load detailed properties for all nodes and edges in graph.
        """
        node_ids = list(self.graph.nodes())
        self.graphsource.load_node_details(node_ids, self.graph)
        self.graphsource.load_edge_details(self.graph)

    def get_nodes_detail_as_dataframe(self, node_ids: List[Any]) -> pd.DataFrame:
        """
        Get node properties as DataFrame.
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            DataFrame with node properties
        """
        return self.graphsource.get_node_data_for_export(node_ids, self.graph)

    def get_most_weighted_nodes(
        self,
        weighted_prop_name: str,
        num_nodes: int,
        include_nodes: Optional[List[int]] = None,
        exclude_nodes: Optional[List[int]] = None,
    ) -> List[int]:
        """
        Get top weighted nodes based on a node property.
        
        Args:
            weighted_prop_name: Node property name to use for weighting
            num_nodes: Number of top nodes to return
            include_nodes: If provided, only consider these nodes
            exclude_nodes: If provided, exclude these nodes
            
        Returns:
            List of top node IDs
        """
        if include_nodes:
            nodes = set(include_nodes)
        else:
            nodes = set(self.graph.nodes)
        
        if exclude_nodes:
            nodes = nodes - set(exclude_nodes)
        
        prop_dict = self.graph.getd(weighted_prop_name, nodes=nodes)
        best_nodes = dict_max_ties(prop_dict, num_nodes)
        return best_nodes.tolist()

    def get_least_weighted_nodes(
        self,
        weighted_prop_name: str,
        num_nodes: int,
        include_nodes: Optional[List[int]] = None,
        exclude_nodes: Optional[List[int]] = None,
    ) -> List[int]:
        """
        Get bottom weighted nodes based on a node property.
        
        Args:
            weighted_prop_name: Node property name to use for weighting
            num_nodes: Number of bottom nodes to return
            include_nodes: If provided, only consider these nodes
            exclude_nodes: If provided, exclude these nodes
            
        Returns:
            List of bottom node IDs
        """
        if include_nodes:
            nodes = set(include_nodes)
        else:
            nodes = set(self.graph.nodes)
        
        if exclude_nodes:
            nodes = nodes - set(exclude_nodes)
        
        prop_dict = self.graph.getd(weighted_prop_name, nodes=nodes)
        best_nodes = dict_min_ties(prop_dict, num_nodes)
        return list(best_nodes)

    def add_selected_nodes_traces_combined_network(
        self,
        selected_nodes_key: str,
        weight_property: str,
        sources: Optional[str] = None,
        targets: Optional[str] = None,
        trace_name: str = "",
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add traces from sources to all selected nodes, and/or from selected nodes to targets.
        
        Args:
            selected_nodes_key: Node set name for selected nodes
            weight_property: Node property to use for weighted traces
            sources: Source node set name (optional)
            targets: Target node set name (optional)
            trace_name: Base name for trace networks
            shortest_paths_plus_n: Include paths N steps longer than shortest
        """
        if sources:
            logger.info(f"Adding trace network from {sources} to {selected_nodes_key}")
            add_trace_network(
                self.graph,
                sources,
                selected_nodes_key,
                name=f"{trace_name}. Highest influence",
                maxsum=weight_property,
                query=sources,
                shortest_paths_plus_n=shortest_paths_plus_n,
            )
            add_trace_network(
                self.graph,
                sources,
                selected_nodes_key,
                name=f"{trace_name}. Shortest paths",
                query=sources,
                shortest_paths_plus_n=shortest_paths_plus_n,
            )
        
        if targets:
            logger.info(f"Adding trace network from {selected_nodes_key} to {targets}")
            add_trace_network(
                self.graph,
                selected_nodes_key,
                targets,
                name=f"{trace_name}. Highest influence",
                maxsum=weight_property,
                query=targets,
                shortest_paths_plus_n=shortest_paths_plus_n,
            )
            add_trace_network(
                self.graph,
                selected_nodes_key,
                targets,
                name=f"{trace_name}. Shortest paths",
                query=targets,
                shortest_paths_plus_n=shortest_paths_plus_n,
            )

    def add_selected_nodes_trace_networks(
        self,
        selected_nodes: List,
        weight_property: str,
        trace_name_prefix: str,
        sources: Optional[str] = None,
        targets: Optional[str] = None,
        include_allshortest_path: bool = True,
        shortest_paths_plus_n: int = 0,
    ) -> None:
        """
        Add trace networks for each selected node individually.
        
        Args:
            selected_nodes: List of selected database node objects
            weight_property: Node property to use for weighted traces
            trace_name_prefix: Prefix for trace names (e.g., 'Forward')
            sources: Source node set name (optional)
            targets: Target node set name (optional)
            include_allshortest_path: Whether to include shortest path traces
            shortest_paths_plus_n: Include paths N steps longer than shortest
        """
        for i, node in enumerate(selected_nodes):
            select_key = self.set_node_set_for_node(node)
            select_name = self.graph.get_node_set_name(select_key)
            
            if sources:
                source_name = self.graph.get_node_set_name(sources)
                logger.info(f"Adding trace network {source_name} to {select_name} #{i+1}")
                tracename = f"{trace_name_prefix} #{i+1} ({select_name}). High influence using {weight_property}"
                
                add_trace_network(
                    self.graph,
                    sources,
                    select_key,
                    name=tracename,
                    maxsum=weight_property,
                    query=sources,
                    shortest_paths_plus_n=shortest_paths_plus_n,
                )
                
                if include_allshortest_path:
                    add_trace_network(
                        self.graph,
                        sources,
                        select_key,
                        name=f"{trace_name_prefix} #{i + 1} ({select_name}). Shortest paths.",
                        query=sources,
                        shortest_paths_plus_n=shortest_paths_plus_n,
                    )

            if targets:
                target_name = self.graph.get_node_set_name(targets)
                logger.info(f"Adding trace network from {select_name} #{i+1} to {target_name}")
                tracename = f"{trace_name_prefix} #{i + 1} ({select_name}). High influence using {weight_property}"
                
                add_trace_network(
                    self.graph,
                    select_key,
                    targets,
                    name=tracename,
                    maxsum=weight_property,
                    query=targets,
                    shortest_paths_plus_n=shortest_paths_plus_n,
                )
                
                if include_allshortest_path:
                    add_trace_network(
                        self.graph,
                        select_key,
                        targets,
                        name=f"{trace_name_prefix} #{i + 1} ({select_name}). Shortest paths",
                        query=targets,
                        shortest_paths_plus_n=shortest_paths_plus_n,
                    )

    def write_to_sankey_file(self, filename: Union[str, Path]) -> None:
        """
        Export graph to Sankey format JSON file.
        
        Args:
            filename: Output file path (str or Path, should end with .json or .graph)
        """
        write_sankey_file(str(filename), self.graph)
        logger.info(f"Graph exported to {filename}")

    def write_to_cytoscape_file(self, filename: Union[str, Path]) -> None:
        """
        Export graph to Cytoscape-compatible JSON format.
        
        Args:
            filename: Output file path (str or Path, should end with .json)
        """
        write_cytoscape_file(str(filename), self.graph)
        logger.info(f"Graph exported to {filename}")
