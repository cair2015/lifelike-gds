"""Neo4j database abstraction layer for graph data queries."""

from __future__ import annotations

from pprint import pformat
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Type

import pandas as pd

from lifelike_gds.graph_sources.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder
from lifelike_gds.utils.config_utils import read_config

if TYPE_CHECKING:
    from lifelike_gds.network.graph_source import GraphSourceDatabase

NodeRecord = dict[str, Any]
ProjectionData = tuple[pd.DataFrame, pd.DataFrame]
ProjectionScenario = dict[str, object]


class Neo4jDatabase:
    """
    Neo4j-backed query adapter used by graph-source implementations.

    This class implements the ``GraphSourceDatabase`` protocol consumed by
    ``lifelike_gds.network.graph_source.GraphSource``. In practice, graph-source
    adapters use this class to:

    - fetch projected node and relationship rows for trace graphs
    - load normalized node records by id
    - retrieve export-oriented node data tables

    The class is intentionally Neo4j-specific even though the historical alias
    ``Database`` is still kept for backward compatibility.
    """

    DEFAULT_EXCLUDED_NODE_LABELS: Sequence[str] = ()
    TRACE_RELATIONSHIP_TYPES: Optional[Sequence[str]] = None

    def __init__(
        self,
        collection_label: Optional[str] = None,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        encrypted: Optional[bool] = None,
    ) -> None:
        """
        Initialize a Neo4j database adapter.

        Args:
            collection_label: Optional node label used to scope graph queries.
            database: Neo4j database name. When omitted, read from config.
            uri: Neo4j connection URI. When omitted, read from config.
            username: Neo4j username. When omitted, read from config.
            password: Neo4j password. When omitted, read from config.
            encrypted: Whether to use an encrypted Neo4j connection. When
                omitted, read from config.
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

    @property
    def label_clause(self) -> str:
        """Return the configured collection label formatted for Cypher queries."""
        return self.format_label_clause(self.collection_label)

    @staticmethod
    def _normalize_node(node: Any) -> NodeRecord:
        """
        Normalize a Neo4j node-like value into a plain dictionary.

        Args:
            node: Raw Neo4j node object or dictionary-like wrapper.

        Returns:
            A plain dictionary containing normalized id fields and labels.

        Raises:
            TypeError: If ``node`` cannot be converted into a mapping.
        """
        if isinstance(node, dict):
            if "id" in node:
                return node
            if len(node) == 1:
                return Neo4jDatabase._normalize_node(next(iter(node.values())))

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
            element_id = str(element_id)
            props["id"] = element_id
            props.setdefault("element_id", element_id)
            props.setdefault("_key", element_id)

        labels = getattr(node, "labels", None)
        if labels is not None:
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
        return [
            self._normalize_node(record.get(key, record) if isinstance(record, dict) else record)
            for record in records
        ]

    @staticmethod
    def _render_where_clause(filters: Sequence[str]) -> str:
        """
        Render a Cypher ``WHERE`` clause from filter expressions.

        Args:
            filters: Individual Cypher boolean expressions.

        Returns:
            Complete ``WHERE`` clause or an empty string when no filters exist.
        """
        return f"WHERE {' AND '.join(filters)}" if filters else ""

    @staticmethod
    def _normalize_excluded_node_labels(
        exclude_node_labels: Optional[Sequence[str]],
        default_excluded_node_labels: Optional[Sequence[str]] = None,
    ) -> Optional[List[str]]:
        """
        Resolve explicit and default node-label exclusions.

        Args:
            exclude_node_labels: Explicit labels to exclude.
            default_excluded_node_labels: Fallback labels used when the explicit
                value is ``None``.

        Returns:
            Normalized label list or ``None`` when no exclusions apply.
        """
        labels = default_excluded_node_labels if exclude_node_labels is None else exclude_node_labels
        return list(labels) if labels else None

    @staticmethod
    def _build_projection_filters(
        aliases: Sequence[str],
        exclude_nodes: Optional[Sequence[str]] = None,
        exclude_node_labels: Optional[Sequence[str]] = None,
    ) -> List[str]:
        """
        Build Cypher filter expressions for trace-graph projections.

        Args:
            aliases: Node-variable aliases that should receive the filters.
            exclude_nodes: Optional node element ids to exclude.
            exclude_node_labels: Optional node labels to exclude.

        Returns:
            List of Cypher boolean expressions.
        """
        filters: List[str] = []

        if exclude_nodes:
            filters.extend([f"NOT elementId({alias}) IN $exclude_ids" for alias in aliases])
        if exclude_node_labels:
            filters.extend(
                [
                    f"NONE(label IN labels({alias}) WHERE label IN $exclude_node_labels)"
                    for alias in aliases
                ]
            )
        return filters

    @classmethod
    def _build_projection_params(
        cls,
        exclude_nodes: Optional[Sequence[str]] = None,
        exclude_node_labels: Optional[Sequence[str]] = None,
        default_excluded_node_labels: Optional[Sequence[str]] = None,
    ) -> Dict[str, List[str]]:
        """
        Build query parameters for trace-graph projection queries.

        Args:
            exclude_nodes: Optional node element ids to exclude.
            exclude_node_labels: Optional node labels to exclude.
            default_excluded_node_labels: Default labels used when no explicit
                exclusion list is provided.

        Returns:
            Query parameter mapping for projection queries.
        """
        normalized_exclude_labels = cls._normalize_excluded_node_labels(
            exclude_node_labels,
            default_excluded_node_labels,
        )
        params: Dict[str, List[str]] = {}
        if exclude_nodes:
            params["exclude_ids"] = [str(node_id) for node_id in exclude_nodes]
        if normalized_exclude_labels:
            params["exclude_node_labels"] = normalized_exclude_labels
        return params

    @classmethod
    def get_projection_relationship_pattern(cls) -> str:
        """
        Return the relationship pattern used in trace-graph projections.

        Returns:
            Cypher relationship pattern constrained by
            ``TRACE_RELATIONSHIP_TYPES`` when configured.
        """
        if cls.TRACE_RELATIONSHIP_TYPES:
            rel_type_clause = "|".join(cls.TRACE_RELATIONSHIP_TYPES)
            return f"-[r:{rel_type_clause}]->"
        return "-[r]->"

    @classmethod
    def build_trace_graph_projection_queries(
        cls,
        collection_label: str = "",
        exclude_nodes: Optional[List[str]] = None,
        exclude_node_labels: Optional[List[str]] = None,
    ) -> tuple[str, str, dict[str, List[str]]]:
        """
        Build node and relationship projection queries for a trace graph.

        Args:
            collection_label: Optional label used to scope matched nodes.
            exclude_nodes: Optional node element ids to exclude.
            exclude_node_labels: Optional node labels to exclude.

        Returns:
            Tuple of ``(node_query, relationship_query, params)``.
        """
        label_clause = cls.format_label_clause(collection_label)
        normalized_exclude_labels = cls._normalize_excluded_node_labels(
            exclude_node_labels,
            cls.DEFAULT_EXCLUDED_NODE_LABELS,
        )
        where_clause = cls._render_where_clause(
            cls._build_projection_filters(
                ("n", "m"),
                exclude_nodes=exclude_nodes,
                exclude_node_labels=normalized_exclude_labels,
            )
        )
        relationship_pattern = cls.get_projection_relationship_pattern()

        node_query = f"""
        MATCH (n{label_clause}){relationship_pattern}(m{label_clause})
        {where_clause}
        UNWIND [n, m] AS x
        RETURN DISTINCT elementId(x) AS node_id
        """
        rel_query = f"""
        MATCH (n{label_clause}){relationship_pattern}(m{label_clause})
        {where_clause}
        RETURN elementId(n) AS source, elementId(m) AS target, type(r) AS type
        """
        params = cls._build_projection_params(
            exclude_nodes=exclude_nodes,
            exclude_node_labels=normalized_exclude_labels,
        )
        return node_query, rel_query, params

    def get_trace_graph_data(
        self,
        exclude_nodes: Optional[List[str]] = None,
        exclude_node_labels: Optional[List[str]] = None,
    ) -> ProjectionData:
        """
        Execute the default trace-graph projection queries.

        Args:
            exclude_nodes: Optional node element ids to exclude.
            exclude_node_labels: Optional node labels to exclude.

        Returns:
            Tuple of ``(node_rows, relationship_rows)`` as DataFrames.
        """
        node_query, rel_query, params = self.build_trace_graph_projection_queries(
            collection_label=self.collection_label or "",
            exclude_nodes=exclude_nodes,
            exclude_node_labels=exclude_node_labels,
        )
        return self.get_dataframe(node_query, **params), self.get_dataframe(rel_query, **params)

    @classmethod
    def default_trace_graph_projection_scenarios(cls) -> List[Dict[str, object]]:
        """
        Return representative projection scenarios for debugging and inspection.

        Returns:
            Scenario dictionaries that can be passed to
            :meth:`print_trace_graph_projection_queries`.
        """
        default_excluded_labels = cls._normalize_excluded_node_labels(
            None,
            cls.DEFAULT_EXCLUDED_NODE_LABELS,
        ) or []
        additional_excluded_labels = [*default_excluded_labels, "ExampleExcludedLabel"]
        return [
            {
                "name": "default_filters",
                "exclude_nodes": None,
                "exclude_node_labels": default_excluded_labels,
            },
            {
                "name": "include_all_labels",
                "exclude_nodes": None,
                "exclude_node_labels": [],
            },
            {
                "name": "exclude_specific_nodes",
                "exclude_nodes": ["4:demo-source", "4:demo-target"],
                "exclude_node_labels": default_excluded_labels,
            },
            {
                "name": "exclude_additional_node_labels",
                "exclude_nodes": None,
                "exclude_node_labels": additional_excluded_labels,
            },
        ]

    @classmethod
    def print_trace_graph_projection_queries(
        cls,
        collection_label: str = "",
        scenarios: Optional[List[ProjectionScenario]] = None,
    ) -> None:
        """
        Print representative projection queries for manual inspection.

        Args:
            collection_label: Optional node label used to scope matched nodes.
            scenarios: Optional projection scenarios. When omitted, uses the
                defaults returned by :meth:`default_trace_graph_projection_scenarios`.
        """
        scenarios = scenarios or cls.default_trace_graph_projection_scenarios()
        for scenario in scenarios:
            name = scenario.get("name", "unnamed_scenario")
            node_query, rel_query, params = cls.build_trace_graph_projection_queries(
                collection_label=collection_label,
                exclude_nodes=scenario.get("exclude_nodes"),
                exclude_node_labels=scenario.get("exclude_node_labels"),
            )
            print(f"=== {name} ===")
            print(f"collection_label={collection_label!r}")
            print(f"params={pformat(params)}")
            print("node_query:")
            print(node_query.strip())
            print("rel_query:")
            print(rel_query.strip())
            print()

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

    def get_dict(self, query: str, **parameters: Any) -> List[NodeRecord]:
        """
        Return query results as dictionaries.

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            List of records represented as dictionaries.
        """
        return self.run_query(query, **parameters)

    def get_dataframe(self, query: str, **parameters: Any) -> pd.DataFrame:
        """
        Execute a query and return the result as a DataFrame.

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            DataFrame containing the query result rows.
        """
        return self.connection.get_dataframe(query, parameters)

    def get_raw_value(self, query: str, **parameters: Any) -> List[NodeRecord]:
        """
        Return raw query records.

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            List of records represented as dictionaries.
        """
        return self.run_query(query, **parameters)

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
        Return all query records as dictionaries.

        Args:
            query: Cypher query text.
            **parameters: Query parameters.

        Returns:
            List of records represented as dictionaries.
        """
        return self.run_query(query, **parameters)

    def get_nodes_by_node_ids(self, id_list: List[Any]) -> List[NodeRecord]:
        """
        Retrieve normalized nodes by their Neo4j element ids.

        Args:
            id_list: Neo4j element ids to fetch.

        Returns:
            List of normalized node dictionaries.
        """
        query, params = Neo4jQueryBuilder.get_nodes_by_ids(id_list, self.collection_label)
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
            node_label: Optional label override. Defaults to ``collection_label``.

        Returns:
            List of normalized node dictionaries.
        """
        label = node_label or self.collection_label
        query, params = Neo4jQueryBuilder.get_nodes_by_property(attr_name, attr_values, label)
        return self._normalize_node_records(self.run_query(query, **params))

    def get_currency_nodes(self) -> List[NodeRecord]:
        """
        Retrieve normalized nodes labeled as currency metabolites.

        Returns:
            List of normalized currency-metabolite node dictionaries.
        """
        query, params = Neo4jQueryBuilder.get_currency_nodes(self.collection_label)
        return self._normalize_node_records(self.run_query(query, **params))


def print_trace_graph_projection_queries(
    database_class: Type[Neo4jDatabase],
    collection_label: str = "",
    scenarios: Optional[List[ProjectionScenario]] = None,
) -> None:
    """
    Module-level wrapper for printing projection queries from a database class.

    Args:
        database_class: Database class whose projection helpers should be used.
        collection_label: Optional node label used to scope matched nodes.
        scenarios: Optional projection scenarios to print.
    """
    database_class.print_trace_graph_projection_queries(
        collection_label=collection_label,
        scenarios=scenarios,
    )


# Backward-compatible alias kept for existing imports.
Database = Neo4jDatabase

__all__ = ["Database", "Neo4jDatabase", "print_trace_graph_projection_queries"]
