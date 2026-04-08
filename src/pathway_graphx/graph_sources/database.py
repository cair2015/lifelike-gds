"""
Neo4j database abstraction layer for graph data queries.

This module provides the Database and GraphSource classes that abstract
Neo4j database operations and enable modular network analysis.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from pathway_graphx.network.graph_source import GraphSource as GraphSourceBase
from pathway_graphx.graph_sources.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder
from pathway_graphx.utils.config_utils import read_config

logger = logging.getLogger(__name__)


class Database:
    """
    Neo4j database wrapper providing high-level query interfaces.
    
    This class abstracts Neo4j operations and provides methods for executing
    queries and retrieving results in various formats (records, DataFrames, etc.).
    """

    def __init__(
        self,
        collection_label: Optional[str] = None,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        encrypted: Optional[bool] = None,
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
            collection_label: Optional primary node label in Neo4j (e.g., 'Reactome')
            database: Neo4j database name. If not provided, reads from NEO4J_DATABASE env var.
            uri: Neo4j connection URI. If not provided, reads from NEO4J_URI env var.
            username: Database username. If not provided, reads from NEO4J_USER env var.
            password: Database password. If not provided, reads from NEO4J_PASSWORD env var.
            
        Raises:
            KeyError: If required environment variables are not found or no parameters provided.
        """
        self.collection_label = collection_label

        if not uri or not username or not password or not database:
            config = read_config("neo4j")
            uri = uri or config["uri"]
            username = username or config["user"]
            password = password or config["password"]
            database = database or config["database"]
            if encrypted is None:
                encrypted = config.get("encrypted", False)

        self.connection = Neo4jConnection(
            uri=uri,
            username=username,
            password=password,
            database=database,
            encrypted=bool(encrypted),
        )

    @staticmethod
    def _normalize_node(node: Any) -> Dict[str, Any]:
        if isinstance(node, dict):
            if "id" in node:
                return node
            if len(node) == 1:
                return Database._normalize_node(next(iter(node.values())))

        try:
            props = dict(node.items())
        except Exception:
            if isinstance(node, dict):
                props = dict(node)
            else:
                raise TypeError(f"Unable to normalize Neo4j node {node!r}")

        element_id = getattr(node, "element_id", None)
        if element_id is None and isinstance(node, dict):
            element_id = node.get("element_id") or node.get("id")
        if element_id is not None:
            props["id"] = str(element_id)
            props.setdefault("element_id", str(element_id))
            props.setdefault("_key", str(element_id))

        labels = getattr(node, "labels", None)
        if labels is not None:
            props.setdefault("labels", list(labels))
        return props

    def _normalize_node_records(self, records: List[Dict[str, Any]], key: str = "n") -> List[Dict[str, Any]]:
        nodes = []
        for record in records:
            value = record.get(key, record) if isinstance(record, dict) else record
            nodes.append(self._normalize_node(value))
        return nodes

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

    def get_nodes_by_node_ids(self, id_list: List[Any]) -> List[Dict[str, Any]]:
        """
        Retrieve nodes by their Neo4j IDs.
        
        Args:
            id_list: List of node IDs
            
        Returns:
            List of node records
        """
        query, params = Neo4jQueryBuilder.get_nodes_by_ids(id_list, self.collection_label)
        return self._normalize_node_records(self.run_query(query, **params))

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
        query, params = Neo4jQueryBuilder.get_nodes_by_property(attr_name, attr_values, label)
        return self._normalize_node_records(self.run_query(query, **params))

    def get_currency_nodes(self) -> List[Dict[str, Any]]:
        """
        Retrieve currency and secondary metabolite nodes.
        
        Returns:
            List of currency/secondary metabolite node records
        """
        query, params = Neo4jQueryBuilder.get_currency_nodes(self.collection_label)
        return self._normalize_node_records(self.run_query(query, **params))

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
        WHERE elementId(s) IN $source_ids AND elementId(t) IN $target_ids
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
        WHERE elementId(s) IN $source_ids AND elementId(t) IN $target_ids
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

        source_ids = [self._extract_id(n) for n in sources]
        target_ids = [self._extract_id(n) for n in targets]
        
        # Get all nodes in shortest paths
        node_query = """
        MATCH (s), (t)
        WHERE elementId(s) IN $source_ids AND elementId(t) IN $target_ids
        MATCH p = allShortestPaths((s)-[*]->(t))
        UNWIND nodes(p) as n
        RETURN DISTINCT elementId(n) as node_id
        """
        
        node_params = {
            "source_ids": source_ids,
            "target_ids": target_ids,
        }
        
        node_data = self.get_dataframe(node_query, **node_params)
        nodes = list(node_data["node_id"])
        D.add_nodes_from(nodes)
        
        # Get relationships between these nodes
        rel_query = """
        MATCH (n)-[r]->(m)
        WHERE elementId(n) IN $node_ids AND elementId(m) IN $node_ids
        RETURN elementId(n) as source, elementId(m) as target, type(r) as type
        """
        
        rel_params = {"node_ids": nodes}
        rel_data = self.get_dataframe(rel_query, **rel_params)
        
        for _, row in rel_data.iterrows():
            D.add_edge(row["source"], row["target"], label=row["type"])
        
        logger.info(f"Added {len(nodes)} nodes and {len(rel_data)} edges to graph")

    @staticmethod
    def _extract_id(node: Any) -> Any:
        """
        Extract ID from a node object.
        
        Handles various node representations:
        - Dict with 'id' or 'element_id' key
        - Object with id attribute
        - Integer (returned as-is)
        
        Args:
            node: Node object or ID
            
        Returns:
            Node ID as a backend-specific string or integer
        """
        if isinstance(node, dict):
            if "element_id" in node:
                return str(node["element_id"])
            if "id" in node:
                return str(node["id"])
        elif hasattr(node, "element_id"):
            return str(node.element_id)
        elif hasattr(node, "id"):
            return str(node.id)
        elif isinstance(node, int):
            return node
        elif isinstance(node, str):
            return node
        
        raise ValueError(f"Cannot extract ID from node: {node}")


class GraphSource(GraphSourceBase):
    """Marker base class for Neo4j-backed graph sources."""
