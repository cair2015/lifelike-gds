"""Utilities for connecting to Neo4j and building common Cypher queries."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from neo4j import GraphDatabase, Result, TrustSystemCAs
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Manage a Neo4j driver and expose small query convenience helpers."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
        encrypted: bool = False,
        trust=None,
        max_connection_lifetime: int = 3600,
    ) -> None:
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database

        if encrypted and trust is None:
            trust = TrustSystemCAs()

        try:
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
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j at %s", uri)
        except Neo4jError as exc:
            logger.error("Failed to connect to Neo4j: %s", exc)
            raise

    def close(self) -> None:
        """Close the underlying Neo4j driver."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def __enter__(self) -> "Neo4jConnection":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Result:
        """Execute a Cypher query and return the raw Neo4j result."""
        if parameters is None:
            parameters = {}

        db = database or self.database

        try:
            with self.driver.session(database=db) as session:
                return session.run(query, parameters)
        except Neo4jError as exc:
            logger.error("Query execution failed: %s\nQuery: %s", exc, query)
            raise

    def get_records(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a query and return a list of record dictionaries."""
        if parameters is None:
            parameters = {}

        db = database or self.database

        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                # Preserve Neo4j objects so callers can still inspect metadata
                # such as ``element_id`` during later normalization steps.
                return [dict(record.items()) for record in result]
        except Neo4jError as exc:
            logger.error("Query failed: %s\nQuery: %s", exc, query)
            raise

    def get_dataframe(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> pd.DataFrame:
        """Execute a query and return the result as a DataFrame."""
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
        """Return the first value from the first record."""
        records = self.get_records(query, parameters, database)
        if not records:
            raise ValueError("No records returned from query")
        return next(iter(records[0].values()))

    def get_single_record(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the first record from a query result."""
        records = self.get_records(query, parameters, database)
        if not records:
            raise ValueError("No records returned from query")
        return records[0]


class Neo4jQueryBuilder:
    """Build common Neo4j Cypher queries used by graph source adapters."""

    @staticmethod
    def get_nodes_by_ids(
        node_ids: List[Union[int, str]],
        collection_label: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        label_clause = f":{collection_label}" if collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE elementId(n) IN $node_ids
        RETURN n
        """
        return query, {"node_ids": node_ids}

    @staticmethod
    def get_nodes_by_property(
        property_name: str,
        property_values: List[Any],
        collection_label: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
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
        rel_filter = ""
        if relationship_types:
            rel_filter = f":{'|'.join(relationship_types)}"

        query = f"""
        MATCH (s)-[r{rel_filter}]->(t)
        WHERE elementId(s) IN $source_ids AND elementId(t) IN $target_ids
        RETURN elementId(s) as source, elementId(t) as target, type(r) as type, properties(r) as properties
        """
        return query, {"source_ids": source_ids, "target_ids": target_ids}

    @staticmethod
    def get_shortest_paths(
        source_ids: List[Union[int, str]],
        target_ids: List[Union[int, str]],
        relationship_types: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> tuple[str, Dict[str, Any]]:
        rel_filter = ""
        if relationship_types:
            rel_filter = f":{'|'.join(relationship_types)}"

        depth_constraint = f"*1..{max_depth}" if max_depth else "*"

        query = f"""
        MATCH (s), (t)
        WHERE elementId(s) IN $source_ids AND elementId(t) IN $target_ids
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
        rel_filter = ""
        if relationship_types:
            rel_filter = f":{'|'.join(relationship_types)}"

        depth_constraint = f"*1..{max_depth}" if max_depth else "*"

        query = f"""
        MATCH (s), (t)
        WHERE elementId(s) IN $source_ids AND elementId(t) IN $target_ids
        MATCH p = allShortestPaths((s)-[{rel_filter}{depth_constraint}]->(t))
        RETURN p
        """
        return query, {"source_ids": source_ids, "target_ids": target_ids}

    @staticmethod
    def get_currency_nodes(collection_label: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
        label_clause = f":{collection_label}" if collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE 'CurrencyMetabolite' IN labels(n)
        RETURN DISTINCT n
        """
        return query, {}

    @staticmethod
    def extract_nodes_from_paths(paths_variable: str = "p") -> str:
        """Return a Cypher fragment that unwinds nodes from matched paths."""
        return f"UNWIND nodes({paths_variable}) as node RETURN DISTINCT node"

    @staticmethod
    def extract_relationships_from_paths(paths_variable: str = "p") -> str:
        """Return a Cypher fragment that unwinds relationships from matched paths."""
        return (
            "UNWIND relationships("
            f"{paths_variable}"
            ") as rel RETURN DISTINCT elementId(startNode(rel)) as source, "
            "elementId(endNode(rel)) as target, type(rel) as type"
        )
