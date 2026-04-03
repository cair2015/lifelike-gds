"""
Neo4j database abstraction layer for graph data queries.

This module provides the Database and GraphSource classes that abstract
Neo4j database operations and enable modular network analysis.
"""

import logging
from typing import List, Dict, Any, Optional

import pandas as pd
from neo4j import Record

from lifelike_gds.neo4j_network.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder
from lifelike_gds.neo4j_network.config_utils import read_config

logger = logging.getLogger(__name__)


class Database:
    """
    Neo4j database wrapper providing high-level query interfaces.
    
    This class abstracts Neo4j operations and provides methods for executing
    queries and retrieving results in various formats (records, DataFrames, etc.).
    """

    def __init__(
        self,
        collection_label: str,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize Neo4j database connection.
        
        Configuration is loaded from environment variables if not provided as parameters.
        Set these environment variables or use a .env file:
            NEO4J_URI: Connection URI (e.g., bolt://localhost:7687)
            NEO4J_USER: Database username
            NEO4J_PASSWORD: Database password
            NEO4J_DATABASE: Database name (default: neo4j)
        
        Args:
            collection_label: Primary node label in Neo4j (e.g., 'Reactome')
            database: Neo4j database name. If not provided, reads from NEO4J_DATABASE env var.
            uri: Neo4j connection URI. If not provided, reads from NEO4J_URI env var.
            username: Database username. If not provided, reads from NEO4J_USER env var.
            password: Database password. If not provided, reads from NEO4J_PASSWORD env var.
            
        Raises:
            KeyError: If required environment variables are not found or no parameters provided.
        """
        self.collection_label = collection_label
        
        # Load from config if not specified
        if not uri or not username or not password or not database:
            config = read_config()
            neo4j_config = config.get("neo4j", {})
            
            if not uri:
                uri = neo4j_config.get("uri", "bolt://localhost:7687")
            if not username:
                username = neo4j_config.get("user", "neo4j")
            if not password:
                password = neo4j_config.get("password", "password")
            if not database:
                database = neo4j_config.get("database", "neo4j")
        
        self.connection = Neo4jConnection(
            uri=uri,
            username=username,
            password=password,
            database=database,
        )

    def close(self):
        """Close the database connection."""
        self.connection.close()

    def run_query(
        self,
        query: str,
        **parameters: Any,
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return list of result records.
        
        Args:
            query: Cypher query string
            **parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        return self.connection.get_records(query, parameters)

    def get_dict(
        self,
        query: str,
        **parameters: Any,
    ) -> List[Dict[str, Any]]:
        """
        Alias for run_query for compatibility with ArangoDB interface.
        
        Args:
            query: Cypher query string
            **parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        return self.run_query(query, **parameters)

    def get_dataframe(
        self,
        query: str,
        **parameters: Any,
    ) -> pd.DataFrame:
        """
        Execute query and return results as pandas DataFrame.
        
        Args:
            query: Cypher query string
            **parameters: Query parameters
            
        Returns:
            pandas DataFrame with query results
        """
        return self.connection.get_dataframe(query, parameters)

    def get_raw_value(
        self,
        query: str,
        **parameters: Any,
    ) -> List[Dict[str, Any]]:
        """
        Alias for run_query for compatibility.
        
        Args:
            query: Cypher query string
            **parameters: Query parameters
            
        Returns:
            List of result records
        """
        return self.run_query(query, **parameters)

    def get_single_value(
        self,
        query: str,
        **parameters: Any,
    ) -> Any:
        """
        Execute query and return first value from first record.
        
        Args:
            query: Cypher query string
            **parameters: Query parameters
            
        Returns:
            Single value from first record
        """
        return self.connection.get_single_value(query, parameters)

    def get_query_values(
        self,
        query: str,
        **parameters: Any,
    ) -> List[Dict[str, Any]]:
        """
        Alias for run_query.
        
        Args:
            query: Cypher query string
            **parameters: Query parameters
            
        Returns:
            List of result records
        """
        return self.run_query(query, **parameters)

    def get_nodes_by_node_ids(self, id_list: List[int]) -> List[Dict[str, Any]]:
        """
        Retrieve nodes by their Neo4j IDs.
        
        Args:
            id_list: List of node IDs
            
        Returns:
            List of node records
        """
        query, params = Neo4jQueryBuilder.get_nodes_by_ids(self.collection_label, id_list)
        return self.run_query(query, **params)

    def get_nodes_by_attr(
        self,
        attr_values: List[Any],
        attr_name: str,
        node_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve nodes by property values.
        
        Args:
            attr_values: List of attribute values to match
            attr_name: Name of the attribute property
            node_label: Optional node label (uses collection_label if not specified)
            
        Returns:
            List of node records
        """
        label = node_label or self.collection_label
        query, params = Neo4jQueryBuilder.get_nodes_by_property(label, attr_name, attr_values)
        return self.run_query(query, **params)

    def get_currency_nodes(self) -> List[Dict[str, Any]]:
        """
        Retrieve currency and secondary metabolite nodes.
        
        Returns:
            List of currency/secondary metabolite node records
        """
        query, params = Neo4jQueryBuilder.get_currency_nodes(self.collection_label)
        return self.run_query(query, **params)

    def get_shortest_path_len(
        self,
        sources: List[Any],
        targets: List[Any],
        rels: Optional[List[str]] = None,
        exclude_nodes: Optional[List[Any]] = None,
        include_nodes: Optional[List[Any]] = None,
    ) -> pd.DataFrame:
        """
        Get shortest path lengths between sources and targets.
        
        Args:
            sources: List of source nodes
            targets: List of target nodes
            rels: Optional list of relationship types to include
            exclude_nodes: Optional nodes to exclude from paths
            include_nodes: Optional nodes that must be in paths
            
        Returns:
            DataFrame with shortest path information
        """
        source_ids = [self._extract_id(n) for n in sources]
        target_ids = [self._extract_id(n) for n in targets]
        
        query = """
        MATCH (s), (t)
        WHERE id(s) IN $source_ids AND id(t) IN $target_ids
        MATCH p = shortestPath((s)-[*]->(t))
        RETURN s.displayName as sourceName, t.displayName as targetName, length(p) as shortestPathLen
        """
        
        params = {
            "source_ids": source_ids,
            "target_ids": target_ids,
        }
        
        return self.get_dataframe(query, **params)

    def get_shortest_paths(
        self,
        sources: List[Any],
        targets: List[Any],
        rels: Optional[List[str]] = None,
        exclude_nodes: Optional[List[Any]] = None,
        include_nodes: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all shortest paths between sources and targets.
        
        Args:
            sources: List of source nodes
            targets: List of target nodes
            rels: Optional list of relationship types to include
            exclude_nodes: Optional nodes to exclude from paths
            include_nodes: Optional nodes that must be in paths
            
        Returns:
            List of path records
        """
        source_ids = [self._extract_id(n) for n in sources]
        target_ids = [self._extract_id(n) for n in targets]
        
        query = """
        MATCH (s), (t)
        WHERE id(s) IN $source_ids AND id(t) IN $target_ids
        MATCH p = allShortestPaths((s)-[*]->(t))
        RETURN p
        """
        
        params = {
            "source_ids": source_ids,
            "target_ids": target_ids,
        }
        
        return self.run_query(query, **params)

    def add_shortest_paths_nodes_rels_to_nx(
        self,
        D,  # NetworkX DiGraph
        sources: List[Any],
        targets: List[Any],
        rels: Optional[List[str]] = None,
        exclude_nodes: Optional[List[Any]] = None,
        include_nodes: Optional[List[Any]] = None,
    ):
        """
        Query shortest paths and add nodes/relationships to NetworkX graph.
        
        Args:
            D: NetworkX DiGraph object
            sources: List of source nodes
            targets: List of target nodes
            rels: Optional list of relationship types
            exclude_nodes: Optional nodes to exclude
            include_nodes: Optional nodes that must be included
        """
        import networkx as nx
        
        source_ids = [self._extract_id(n) for n in sources]
        target_ids = [self._extract_id(n) for n in targets]
        
        # Get all nodes in shortest paths
        node_query = """
        MATCH (s), (t)
        WHERE id(s) IN $source_ids AND id(t) IN $target_ids
        MATCH p = allShortestPaths((s)-[*]->(t))
        UNWIND nodes(p) as n
        RETURN DISTINCT id(n) as node_id
        """
        
        node_params = {
            "source_ids": source_ids,
            "target_ids": target_ids,
        }
        
        node_data = self.get_dataframe(node_query, **node_params)
        nodes = [int(n) for n in node_data["node_id"]]
        D.add_nodes_from(nodes)
        
        # Get relationships between these nodes
        rel_query = """
        MATCH (n)-[r]->(m)
        WHERE id(n) IN $node_ids AND id(m) IN $node_ids
        RETURN id(n) as source, id(m) as target, type(r) as type
        """
        
        rel_params = {"node_ids": nodes}
        rel_data = self.get_dataframe(rel_query, **rel_params)
        
        for _, row in rel_data.iterrows():
            D.add_edge(int(row["source"]), int(row["target"]), label=row["type"])
        
        logger.info(f"Added {len(nodes)} nodes and {len(rel_data)} edges to graph")

    @staticmethod
    def _extract_id(node: Any) -> int:
        """
        Extract ID from a node object.
        
        Handles various node representations:
        - Dict with 'id' or 'element_id' key
        - Object with id attribute
        - Integer (returned as-is)
        
        Args:
            node: Node object or ID
            
        Returns:
            Node ID as integer
        """
        if isinstance(node, dict):
            if "id" in node:
                return int(node["id"])
            elif "element_id" in node:
                return int(node["element_id"])
        elif hasattr(node, "id"):
            return int(node.id)
        elif isinstance(node, int):
            return node
        
        raise ValueError(f"Cannot extract ID from node: {node}")


class GraphSource:
    """
    Abstract graph source providing database operations for network analysis.
    
    This class acts as a bridge between Neo4j database operations and
    trace graph analysis.
    """

    def __init__(self, database: Database, node_label_prop: str = "displayName"):
        """
        Initialize graph source.
        
        Args:
            database: Database instance for queries
            node_label_prop: Property name to use for node labels
        """
        self.database = database
        self.node_label_prop = node_label_prop

    @classmethod
    def get_node_name(cls, node: Dict[str, Any]) -> Optional[str]:
        """
        Extract node name/display name from node dict.
        
        Args:
            node: Node record
            
        Returns:
            Node display name if available
        """
        return node.get("displayName") or node.get("name")

    @classmethod
    def get_node_desc(cls, node: Dict[str, Any]) -> Optional[str]:
        """
        Extract node description from node dict.
        
        Args:
            node: Node record
            
        Returns:
            Node description if available
        """
        return node.get("description")

    def set_nodes_description(self, neo4j_nodes: List[Dict[str, Any]], D) -> None:
        """
        Set node descriptions in graph from Neo4j nodes.
        
        Args:
            neo4j_nodes: List of node records from Neo4j
            D: NetworkX graph object
        """
        for node in neo4j_nodes:
            node_id = node.get("id")
            if node_id and node_id in D:
                D.nodes[node_id]["description"] = self.get_node_desc(node)

    def set_edges_description(self, neo4j_edges: List[Dict[str, Any]], D) -> None:
        """
        Set edge descriptions in graph from Neo4j edges.
        
        Args:
            neo4j_edges: List of edge records from Neo4j
            D: NetworkX graph object
        """
        # Implement edge description setting
        pass

    @classmethod
    def set_edge_description(
        cls,
        D,
        start_node: int,
        end_node: int,
        edge_type: str,
        key: Optional[str] = None,
    ) -> None:
        """
        Set description for a specific edge.
        
        Args:
            D: NetworkX graph object
            start_node: Source node ID
            end_node: Target node ID
            edge_type: Type of relationship
            key: Optional edge key for MultiDiGraph
        """
        if D.has_edge(start_node, end_node):
            if key and hasattr(D, "get_edge_data"):
                edge_data = D.get_edge_data(start_node, end_node, key)
            else:
                edge_data = D.get_edge_data(start_node, end_node)
            
            if edge_data and isinstance(edge_data, dict):
                edge_data["description"] = f"{edge_type} relationship"

    def retrieve_node_properties(self, graph) -> None:
        """
        Retrieve and set node properties from Neo4j.
        
        Args:
            graph: NetworkX graph object
        """
        # Load node details from database
        pass

    def initiate_trace_graph(
        self,
        tracegraph,
        exclude_currency: bool = True,
        exclude_secondary: bool = True,
    ) -> None:
        """
        Initialize trace graph with data from Neo4j.
        
        Args:
            tracegraph: TraceGraphNx instance
            exclude_currency: Whether to exclude currency metabolites
            exclude_secondary: Whether to exclude secondary metabolites
        """
        query = f"""
        MATCH (n:{self.database.collection_label})
        RETURN id(n) as node_id
        """
        
        # Build node filters
        if exclude_currency or exclude_secondary:
            query += " WHERE NOT ("
            filters = []
            if exclude_currency:
                filters.append("'CurrencyMetabolite' IN labels(n)")
            if exclude_secondary:
                filters.append("'SecondaryMetabolite' IN labels(n)")
            query += " OR ".join(filters)
            query += ")"
        
        # Add nodes to trace graph
        tracegraph.add_nodes(query)
        
        # Get relationships
        rel_query = f"""
        MATCH (n:{self.database.collection_label})-[r]->(m:{self.database.collection_label})
        RETURN id(n) as source, id(m) as target, type(r) as type
        """
        tracegraph.add_rels(rel_query)

    def load_graph_to_tracegraph(self, tracegraph, exclude_nodes=None) -> None:
        """
        Load full graph data to trace graph.
        
        Args:
            tracegraph: TraceGraphNx instance
            exclude_nodes: Optional nodes to exclude
        """
        # Implementation for full graph loading
        pass

    def get_node_data_for_excel(self, node_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Retrieve node data for Excel export.
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            List of node data dictionaries
        """
        query = f"""
        MATCH (n:{self.database.collection_label})
        WHERE id(n) IN $node_ids
        RETURN n
        """
        return self.database.run_query(query, node_ids=node_ids)
