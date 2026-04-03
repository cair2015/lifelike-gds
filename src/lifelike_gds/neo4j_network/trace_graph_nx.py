"""
Neo4j_based TraceGraph using NetworkX for network analysis.

This module provides the TraceGraphNx class that loads graph data from Neo4j,
builds lightweight NetworkX graphs, and performs network analysis operations.
"""

import logging
import os.path
from typing import List, Optional

import networkx as nx
import pandas as pd

from lifelike_gds.neo4j_network.database import GraphSource
from lifelike_gds.network.groups import set_default_groups
from lifelike_gds.network.graph_utils import MultiDirectedGraph, DirectedGraph
from lifelike_gds.network.trace_utils import add_trace_network, get_traced_nodes
from lifelike_gds.network.collection_utils import dict_max_ties, dict_min_ties
from lifelike_gds.utils import get_id

logger = logging.getLogger(__name__)


class TraceGraphNx:
    """
    Neo4j-based lightweight trace graph using NetworkX backend.
    
    This class creates a projected graph from Neo4j containing only node IDs
    and relationships. Detailed node properties are loaded on-demand from Neo4j.
    """

    def __init__(self, graphsource: GraphSource, directed: bool = True, multigraph: bool = True):
        """
        Initialize TraceGraphNx with Neo4j as data source.
        
        Args:
            graphsource: GraphSource instance for Neo4j queries
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

    def init_default_graph(
        self,
        exclude_currency: bool = True,
        exclude_secondary: bool = True,
    ) -> None:
        """
        Initialize graph with default nodes and relationships from Neo4j.
        
        Args:
            exclude_currency: Exclude currency metabolite nodes
            exclude_secondary: Exclude secondary metabolite nodes
        """
        self.graphsource.initiate_trace_graph(self, exclude_currency, exclude_secondary)

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
        Add nodes to graph from Neo4j query result.
        
        Query should return 'node_id' column containing node IDs.
        
        Args:
            node_query: Cypher query returning node IDs
            **parameters: Query parameters
        """
        node_data = self.graphsource.database.get_dataframe(node_query, **parameters)
        
        if not node_data.empty:
            nodes = [int(n) for n in node_data["node_id"]]
            self.graph.add_nodes_from(nodes)
            logger.info(f"Added {len(nodes)} nodes to graph")

    def add_rels(self, rel_query: str, **parameters) -> None:
        """
        Add relationships to graph from Neo4j query result.
        
        Query should return 'source', 'target', and 'type' columns.
        
        Args:
            rel_query: Cypher query returning relationships
            **parameters: Query parameters
        """
        rel_data = self.graphsource.database.get_dataframe(rel_query, **parameters)
        
        for _, row in rel_data.iterrows():
            source = int(row["source"])
            target = int(row["target"])
            rel_type = row["type"]
            self.graph.add_edge(source, target, label=rel_type)
        
        logger.info(f"Added {len(rel_data)} relationships to graph")

    def add_nodes_rels_from_paths(self, paths: List[dict]) -> None:
        """
        Add nodes and relationships from Neo4j path results.
        
        Args:
            paths: List of path dictionaries from Neo4j
        """
        node_ids = set()
        edges = []
        
        for path in paths:
            # Extract nodes and relationships from path
            # This assumes paths are in appropriate Neo4j format
            pass
        
        self.graph.add_nodes_from(node_ids)
        
        for source, target, rel_type in edges:
            self.graph.add_edge(source, target, label=rel_type)
        
        logger.info(f"Added {len(node_ids)} nodes and {len(edges)} edges from paths")

    def set_node_set(self, key: str, nodes: set, **meta) -> None:
        """
        Set a named node set in the graph.
        
        Args:
            key: Unique identifier for the node set
            nodes: Set of node IDs
            **meta: Additional metadata for the node set
        """
        self.graph.set_node_set(key, nodes, **meta)

    def set_node_set_from_neo4j_nodes(
        self,
        nodes: List[dict],
        name: str,
        desc: str,
    ) -> None:
        """
        Create node set from Neo4j node records.
        
        Args:
            nodes: List of Neo4j node records
            name: Name for the node set
            desc: Description for the node set
        """
        # Extract IDs from Neo4j node records
        node_ids = []
        for node in nodes:
            if isinstance(node, dict):
                node_id = node.get("id") or node.get("element_id")
                if node_id:
                    node_ids.append(int(node_id))
        
        node_set = set(node_ids).intersection(self.graph.nodes)
        self.graph.set_node_set(name, node_set, name=name, description=desc)
        logger.info(f"Created node set '{name}' with {len(node_set)} nodes")

    def set_node_set_for_node(self, node: dict) -> str:
        """
        Create node set for a single node.
        
        Args:
            node: Neo4j node record
            
        Returns:
            Node set key
        """
        # Extract node ID
        node_id = node.get("id") or node.get("element_id")
        if not node_id:
            raise ValueError("Cannot extract ID from node")
        
        node_id = int(node_id)
        key = f"node_{node_id}"
        name = node.get("displayName") or node.get("name", str(node_id))
        
        self.set_node_set(key, {node_id}, name=name, description=name)
        return key

    def add_graph_description(self, desc: str) -> None:
        """
        Add description to graph.
        
        Args:
            desc: Description text
        """
        self.graph.describe(desc)

    def set_nodes_flag(self, node_set_name: str, flag_val: any) -> None:
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

    def load_node_detail_from_neo4j(self, nodes: List[int]) -> None:
        """
        Load detailed node properties from Neo4j.
        
        Args:
            nodes: List of node IDs
        """
        if not nodes:
            return
        
        query = f"""
        MATCH (n:{self.graphsource.database.collection_label})
        WHERE id(n) IN $node_ids
        RETURN properties(n) as props, id(n) as node_id
        """
        
        neo4j_nodes = self.graphsource.database.run_query(query, node_ids=nodes)
        
        for node in neo4j_nodes:
            node_id = int(node.get("node_id"))
            props = node.get("props", {})
            
            if node_id in self.graph.nodes:
                # Update node with properties
                self.graph.nodes[node_id].update(props)
                self.graph.nodes[node_id]["labels"] = props.get("labels", [])
                self.graph.nodes[node_id]["label"] = props.get("displayName") or props.get("name")
        
        logger.info(f"Loaded details for {len(neo4j_nodes)} nodes")

    def clean_graph(self) -> None:
        """
        Remove unused nodes and edges to create lightweight graph.
        
        Keeps only nodes and edges that are part of traces or in named node sets.
        """
        node_size1 = len(self.graph)
        nodes = get_traced_nodes(self.graph)
        
        # Get nodes in named node sets
        nodeset_nodes = set()
        for node_set in self.graph.graph.get("node_sets", {}).values():
            nodeset_nodes.update(node_set.get("nodes", set()))
        
        nodes.update(nodeset_nodes)
        self.graph = self.graph.keep(nodes)
        node_size2 = len(self.graph)
        
        logger.info(f"Cleaned graph: {node_size1} -> {node_size2} nodes")
        set_default_groups(self.graph)

    def load_graph_detail(self) -> None:
        """
        Load detailed properties for all nodes in graph.
        """
        node_ids = list(self.graph.nodes())
        
        if not node_ids:
            return
        
        query = f"""
        MATCH (n:{self.graphsource.database.collection_label})
        WHERE id(n) IN $node_ids
        RETURN id(n) as node_id, properties(n) as props
        """
        
        neo4j_nodes = self.graphsource.database.run_query(query, node_ids=node_ids)
        
        for node in neo4j_nodes:
            node_id = int(node.get("node_id"))
            props = node.get("props", {})
            
            if node_id in self.graph.nodes:
                self.graph.nodes[node_id].update(props)
        
        logger.info(f"Loaded detail for {len(neo4j_nodes)} nodes")

    def get_node_set_names(self) -> List[str]:
        """
        Get list of all node set names in graph.
        
        Returns:
            List of node set names
        """
        return list(self.graph.graph.get("node_sets", {}).keys())

    def get_node_set(self, key: str) -> set:
        """
        Get nodes in a named node set.
        
        Args:
            key: Node set key
            
        Returns:
            Set of node IDs
        """
        try:
            return self.graph.node_set(key)
        except KeyError:
            logger.warning(f"Node set '{key}' not found")
            return set()

    def export_to_file(self, filepath: str, format: str = "graphml") -> None:
        """
        Export graph to file.
        
        Args:
            filepath: Output file path
            format: Export format ('graphml', 'json', etc.)
        """
        data_dir = self.datadir or "."
        full_path = os.path.join(data_dir, filepath)
        
        if format == "graphml":
            nx.write_graphml(self.graph, full_path)
        elif format == "gml":
            nx.write_gml(self.graph, full_path)
        elif format == "adjlist":
            nx.write_adjlist(self.graph, full_path)
        else:
            logger.error(f"Unsupported export format: {format}")
            return
        
        logger.info(f"Exported graph to {full_path}")
