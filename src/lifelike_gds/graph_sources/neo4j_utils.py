"""Utilities for connecting to Neo4j and building common Cypher queries."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from neo4j import GraphDatabase, TrustSystemCAs
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


class Neo4jQueryBuilder:
    """Build common Neo4j Cypher queries used by graph source adapters."""

    @staticmethod
    def _label_clause(collection_label: Optional[str]) -> str:
        """Format a Cypher label clause from an optional label."""
        return f":{collection_label}" if collection_label else ""

    @classmethod
    def get_nodes_by_ids(
        cls,
        node_ids: List[Union[int, str]],
        collection_label: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Build a Cypher query to retrieve nodes by their Neo4j element ids."""
        label_clause = cls._label_clause(collection_label)
        query = f"""
        MATCH (n{label_clause})
        WHERE elementId(n) IN $node_ids
        RETURN n
        """
        return query, {"node_ids": node_ids}

    @classmethod
    def get_nodes_by_property(
        cls,
        property_name: str,
        property_values: List[Any],
        collection_label: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        label_clause = cls._label_clause(collection_label)
        query = f"""
        MATCH (n{label_clause})
        WHERE n.{property_name} IN $values
        RETURN n
        """
        return query, {"values": property_values}
