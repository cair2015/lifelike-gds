"""Neo4j database abstraction layer for shared graph data queries."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from lifelike_gds.graph_sources.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder
from lifelike_gds.utils.config_utils import read_config

NodeRecord = dict[str, Any]


class Neo4jDatabase:
    """
    Neo4j-backed query adapter used by graph-source implementations.

    This class implements the ``GraphSourceDatabase`` protocol consumed by
    ``lifelike_gds.network.graph_source.GraphSource``. In practice, graph-source
    adapters use this class to load normalized node records by id and
    retrieve export-oriented node data tables.

    The class is intentionally Neo4j-specific even though the historical alias
    ``Database`` is still kept for backward compatibility.
    """

    def __init__(
        self,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        encrypted: Optional[bool] = None,
    ) -> None:
        """
        Initialize a Neo4j database adapter.

        Args:
            database: Neo4j database name. When omitted, read from config.
            uri: Neo4j connection URI. When omitted, read from config.
            username: Neo4j username. When omitted, read from config.
            password: Neo4j password. When omitted, read from config.
            encrypted: Whether to use an encrypted Neo4j connection. When
                omitted, read from config.
        """
        if not uri or not username or not password or not database:
            config = read_config("neo4j")
            uri = uri or config["uri"]
            username = username or config["user"]
            password = password or config["password"]
            database = database or config["database"]
            if encrypted is None:
                encrypted = config.get("encrypted", False)

        self.connection: Neo4jConnection = Neo4jConnection(
            uri=uri,
            username=username,
            password=password,
            database=database,
            encrypted=bool(encrypted),
        )

    @staticmethod
    def format_label_clause(collection_label: Optional[str]) -> str:
        """
        Build a Cypher label clause from an optional collection label.

        Args:
            collection_label: Optional label such as ``"Reactome"``.

        Returns:
            Cypher label suffix such as ``":Reactome"`` or an empty string.
        """
        return f":{collection_label}" if collection_label else ""

    @staticmethod
    def _normalize_node(node: Any) -> NodeRecord:
        """
        Normalize a Neo4j node-like value into a plain dictionary.

        Args:
            node: Raw Neo4j node object or dictionary-like wrapper.

        Returns:
            A plain dictionary containing normalized id fields and labels.
        """
        # Handle simple dict case
        if isinstance(node, dict):
            return dict(node)
        
        # Try to extract properties from Neo4j node object
        props = dict(getattr(node, "items", lambda: [])()) or {}
        
        # Add element_id if available
        element_id = getattr(node, "element_id", None)
        if element_id:
            element_id = str(element_id)
            props["id"] = element_id
            props.setdefault("element_id", element_id)
            props.setdefault("_key", element_id)
        
        # Add labels if available
        labels = getattr(node, "labels", None)
        if labels:
            props.setdefault("labels", list(labels))
        
        return props

    def _normalize_node_records(
        self,
        records: Iterable[Any],
        key: str = "n",
    ) -> List[NodeRecord]:
        """
        Normalize a sequence of query records into plain node dictionaries.

        Args:
            records: Query result records or raw node values.
            key: Record key containing the node payload when records are dicts.

        Returns:
            List of normalized node dictionaries.
        """
        normalized = []
        for record in records:
            # Extract the node from the record if it's a dict with the specified key
            node = record.get(key, record) if isinstance(record, dict) else record
            normalized.append(self._normalize_node(node))
        return normalized

    def close(self) -> None:
        """Close the underlying database connection."""
        self.connection.close()

    def run_query(self, query: str, **parameters: Any) -> List[NodeRecord]:
        """
        Execute a Cypher query and return records as dictionaries.

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            List of records represented as dictionaries.
        """
        return self.connection.get_records(query, parameters)

    def get_dataframe(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Execute a query and return the result as a DataFrame.

        Args:
            query: Cypher query text.
            parameters: Query parameters as a dictionary.

        Returns:
            DataFrame containing the query result rows.
        """
        return self.connection.get_dataframe(query, parameters or {})

    def get_single_value(self, query: str, **parameters: Any) -> Any:
        """
        Execute a query and return the first value from the first record.

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            First scalar value from the first returned record.
        """
        return self.connection.get_single_value(query, parameters)

    def get_query_values(self, query: str, **parameters: Any) -> List[NodeRecord]:
        """
        Execute a query and return all records as dictionaries.
        Alias for run_query().

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            List of records represented as dictionaries.
        """
        return self.run_query(query, **parameters)

    def get_nodes_by_node_ids(
        self,
        id_list: List[Any],
        node_label: Optional[str] = None,
    ) -> List[NodeRecord]:
        """
        Retrieve normalized nodes by their Neo4j element ids.

        Args:
            id_list: Neo4j element ids to fetch.
            node_label: Optional label used to scope matched nodes.

        Returns:
            List of normalized node dictionaries.
        """
        query, params = Neo4jQueryBuilder.get_nodes_by_ids(id_list, node_label)
        return self._normalize_node_records(self.run_query(query, **params))

    def get_nodes_by_attr(
        self,
        attr_values: List[Any],
        attr_name: str,
        node_label: Optional[str] = None,
    ) -> List[NodeRecord]:
        """
        Retrieve normalized nodes by matching a property against many values.

        Args:
            attr_values: Property values to match.
            attr_name: Property name to match against.
            node_label: Optional label used to scope matched nodes.

        Returns:
            List of normalized node dictionaries.
        """
        query, params = Neo4jQueryBuilder.get_nodes_by_property(
            attr_name,
            attr_values,
            node_label,
        )
        return self._normalize_node_records(self.run_query(query, **params))


# Backward-compatible alias kept for existing imports.
Database = Neo4jDatabase

__all__ = ["Database", "Neo4jDatabase"]
