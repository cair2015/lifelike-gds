"""
Neo4j utility functions for database connection, query execution, and result handling.

This module provides core abstractions for interacting with Neo4j databases,
including connection management, query execution, and result conversion to various formats.
"""

import logging
from typing import List, Dict, Any, Optional, Union

import pandas as pd
from neo4j import GraphDatabase, Session, Driver, Result, TrustSystemCAs
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """
    Manages Neo4j database connection and provides methods for query execution.
    
    Attributes:
        driver: Neo4j driver instance
        uri: Neo4j connection URI
        username: Database username
        password: Database password
        database: Default database name
    """

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
        encrypted: bool = False,
        trust=None,
        max_connection_lifetime: int = 3600,
    ):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j server URI (e.g., 'bolt://localhost:7687')
            username: Database username
            password: Database password
            database: Default database name (default: 'neo4j')
            encrypted: Whether to use encryption (default: False)
            trust: Trust strategy for TLS connections. Can be:
                - None (default, no verification)
                - TrustSystemCAs() (verify using system CA certificates)
                - TrustAll() (trust all certificates)
                - TrustCustomCAs(path) (verify using custom CA certificates)
            max_connection_lifetime: Maximum connection lifetime in seconds
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        
        # Default to TrustSystemCAs if encrypted is True but trust is not specified
        if encrypted and trust is None:
            trust = TrustSystemCAs()
        
        try:
            # Build driver config
            driver_kwargs = {
                "encrypted": encrypted,
                "max_connection_lifetime": max_connection_lifetime,
            }
            if trust is not None:
                driver_kwargs["trust"] = trust
            
            self.driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                **driver_kwargs,
            )
            # Test connection
            self.driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {uri}")
        except Neo4jError as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Result:
        """
        Execute a Cypher query and return the raw Result object.
        
        Args:
            query: Cypher query string
            parameters: Query parameters dictionary
            database: Specific database to query (uses default if not specified)
            
        Returns:
            Neo4j Result object for manual processing
            
        Raises:
            Neo4jError: If query execution fails
        """
        if parameters is None:
            parameters = {}
        
        db = database or self.database
        
        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                return result
        except Neo4jError as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    def get_records(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute query and return list of record dictionaries.
        
        Args:
            query: Cypher query string
            parameters: Query parameters dictionary
            database: Specific database to query
            
        Returns:
            List of dictionaries, one per result record
        """
        if parameters is None:
            parameters = {}
        
        db = database or self.database
        
        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                records = [record.data() for record in result]
                return records
        except Neo4jError as e:
            logger.error(f"Query failed: {e}\nQuery: {query}")
            raise

    def get_dataframe(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Execute query and return results as a pandas DataFrame.
        
        Args:
            query: Cypher query string
            parameters: Query parameters dictionary
            database: Specific database to query
            
        Returns:
            pandas DataFrame with query results
        """
        records = self.get_records(query, parameters, database)
        
        if not records:
            return pd.DataFrame()
        
        return pd.DataFrame(records)

    def get_single_value(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Any:
        """
        Execute query and return first value from first record.
        
        Args:
            query: Cypher query string
            parameters: Query parameters dictionary
            database: Specific database to query
            
        Returns:
            Single value from first record
            
        Raises:
            ValueError: If no records returned
        """
        records = self.get_records(query, parameters, database)
        
        if not records:
            raise ValueError("No records returned from query")
        
        first_record = records[0]
        # Return the first value in the record
        return next(iter(first_record.values()))

    def get_single_record(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute query and return first record only.
        
        Args:
            query: Cypher query string
            parameters: Query parameters dictionary
            database: Specific database to query
            
        Returns:
            First record as dictionary
            
        Raises:
            ValueError: If no records returned
        """
        records = self.get_records(query, parameters, database)
        
        if not records:
            raise ValueError("No records returned from query")
        
        return records[0]


class Neo4jQueryBuilder:
    """
    Helper class for building common Neo4j Cypher queries.
    
    This class provides methods for constructing frequently-used queries
    for node retrieval, relationship traversal, and path finding.
    """

    @staticmethod
    def get_nodes_by_ids(
        node_ids: List[Union[int, str]], collection_label: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query to retrieve nodes by their IDs.
        
        Args:
            node_ids: List of node IDs to retrieve
            collection_label: Optional node label in Neo4j (e.g., 'Reactome', 'BioCyc')
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        label_clause = f":{collection_label}" if collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE id(n) IN $node_ids
        RETURN n
        """
        return query, {"node_ids": node_ids}

    @staticmethod
    def get_nodes_by_property(
        property_name: str,
        property_values: List[Any],
        collection_label: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query to retrieve nodes by property values.
        
        Args:
            property_name: Name of the property to filter on
            property_values: List of values to match
            collection_label: Optional node label in Neo4j
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        label_clause = f":{collection_label}" if collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE n.{property_name} IN $values
        RETURN n
        """
        return query, {"values": property_values}

    @staticmethod
    def get_relationships_between_nodes(
        source_ids: List[Union[int, str]],
        target_ids: List[Union[int, str]],
        relationship_types: Optional[List[str]] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query to retrieve relationships between two sets of nodes.
        
        Args:
            source_ids: List of source node IDs
            target_ids: List of target node IDs
            relationship_types: Optional list of relationship types to filter on
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        rel_filter = ""
        if relationship_types:
            rel_types_str = "|".join(relationship_types)
            rel_filter = f":{rel_types_str}"
        
        query = f"""
        MATCH (s)-[r{rel_filter}]->(t)
        WHERE id(s) IN $source_ids AND id(t) IN $target_ids
        RETURN id(s) as source, id(t) as target, type(r) as type, properties(r) as properties
        """
        return query, {"source_ids": source_ids, "target_ids": target_ids}

    @staticmethod
    def get_shortest_paths(
        source_ids: List[Union[int, str]],
        target_ids: List[Union[int, str]],
        relationship_types: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query to retrieve shortest paths between source and target nodes.
        
        Args:
            source_ids: List of source node IDs
            target_ids: List of target node IDs
            relationship_types: Optional list of relationship types to filter on
            max_depth: Optional maximum path depth
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        rel_filter = ""
        if relationship_types:
            rel_types_str = "|".join(relationship_types)
            rel_filter = f":{rel_types_str}"
        
        depth_constraint = ""
        if max_depth:
            depth_constraint = f"*1..{max_depth}"
        else:
            depth_constraint = "*"
        
        query = f"""
        MATCH (s), (t)
        WHERE id(s) IN $source_ids AND id(t) IN $target_ids
        MATCH p = shortestPath((s)-[{rel_filter}{depth_constraint}]->(t))
        RETURN p
        """
        return query, {"source_ids": source_ids, "target_ids": target_ids}

    @staticmethod
    def get_all_shortest_paths(
        source_ids: List[Union[int, str]],
        target_ids: List[Union[int, str]],
        relationship_types: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query to retrieve all shortest paths between source and target nodes.
        
        Args:
            source_ids: List of source node IDs
            target_ids: List of target node IDs
            relationship_types: Optional list of relationship types to filter on
            max_depth: Optional maximum path depth
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        rel_filter = ""
        if relationship_types:
            rel_types_str = "|".join(relationship_types)
            rel_filter = f":{rel_types_str}"
        
        depth_constraint = ""
        if max_depth:
            depth_constraint = f"*1..{max_depth}"
        else:
            depth_constraint = "*"
        
        query = f"""
        MATCH (s), (t)
        WHERE id(s) IN $source_ids AND id(t) IN $target_ids
        MATCH p = allShortestPaths((s)-[{rel_filter}{depth_constraint}]->(t))
        RETURN p
        """
        return query, {"source_ids": source_ids, "target_ids": target_ids}

    @staticmethod
    def get_currency_nodes(collection_label: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
        """
        Build query to retrieve currency/secondary metabolite nodes.
        
        Args:
            collection_label: Optional node label in Neo4j
            
        Returns:
            Tuple of (query_string, parameters_dict)
        """
        label_clause = f":{collection_label}" if collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE 'CurrencyMetabolite' IN labels(n) OR 'SecondaryMetabolite' IN labels(n)
        RETURN DISTINCT n
        """
        return query, {}

    @staticmethod
    def extract_nodes_from_paths(paths_variable: str = "p") -> str:
        """
        Return Cypher fragment to extract all nodes from paths.
        
        Note: This returns a query fragment that should be used in a RETURN clause
        after paths have been matched.
        
        Args:
            paths_variable: Variable name for paths in query
            
        Returns:
            Cypher RETURN clause fragment for extracting nodes
        """
        return f"UNWIND nodes({paths_variable}) as node RETURN DISTINCT node"

    @staticmethod
    def extract_relationships_from_paths(paths_variable: str = "p") -> str:
        """
        Return Cypher fragment to extract all relationships from paths.
        
        Note: This returns a query fragment that should be used in a RETURN clause
        after paths have been matched.
        
        Args:
            paths_variable: Variable name for paths in query
            
        Returns:
            Cypher RETURN clause fragment for extracting relationships
        """
        return f"UNWIND relationships({paths_variable}) as rel RETURN DISTINCT id(startNode(rel)) as source, id(endNode(rel)) as target, type(rel) as type"
