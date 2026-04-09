"""Neo4j database abstraction layer for graph data queries."""

from __future__ import annotations

from pprint import pformat
from typing import Any, Dict, Iterable, List, Optional, Sequence, Type

import pandas as pd

from pathway_graphx.graph_sources.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder
from pathway_graphx.utils.config_utils import read_config


class Database:
    """Neo4j database wrapper providing high-level query interfaces."""

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
    def format_label_clause(collection_label: Optional[str]) -> str:
        """Return a Cypher label suffix such as ``:Reactome`` or an empty string."""
        return f":{collection_label}" if collection_label else ""

    @property
    def label_clause(self) -> str:
        """Return the configured collection label formatted for Cypher queries."""
        return self.format_label_clause(self.collection_label)

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
    ) -> List[Dict[str, Any]]:
        return [
            self._normalize_node(record.get(key, record) if isinstance(record, dict) else record)
            for record in records
        ]

    @staticmethod
    def _render_where_clause(filters: Sequence[str]) -> str:
        """Render a Cypher ``WHERE`` clause from a list of filter expressions."""
        return f"WHERE {' AND '.join(filters)}" if filters else ""

    @staticmethod
    def _normalize_excluded_node_labels(
        exclude_node_labels: Optional[Sequence[str]],
        default_excluded_node_labels: Optional[Sequence[str]] = None,
    ) -> Optional[List[str]]:
        labels = default_excluded_node_labels if exclude_node_labels is None else exclude_node_labels
        return list(labels) if labels else None

    @staticmethod
    def _build_projection_filters(
        aliases: Sequence[str],
        exclude_nodes: Optional[Sequence[str]] = None,
        exclude_node_labels: Optional[Sequence[str]] = None,
    ) -> List[str]:
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
        """Return the relationship pattern used in trace-graph projections."""
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
    ) -> tuple[str, str, dict]:
        """Return node/edge projection queries without requiring a live DB connection."""
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
    ):
        node_query, rel_query, params = self.build_trace_graph_projection_queries(
            collection_label=self.collection_label or "",
            exclude_nodes=exclude_nodes,
            exclude_node_labels=exclude_node_labels,
        )
        return self.get_dataframe(node_query, **params), self.get_dataframe(rel_query, **params)

    @classmethod
    def default_trace_graph_projection_scenarios(cls) -> List[Dict[str, object]]:
        """Return a few representative projection-filter scenarios for inspection."""
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
        scenarios: Optional[List[dict]] = None,
    ) -> None:
        """Print representative trace-graph projection queries for manual inspection."""
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

    def run_query(self, query: str, **parameters: Any) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return records as dictionaries."""
        return self.connection.get_records(query, parameters)

    def get_dict(self, query: str, **parameters: Any) -> List[Dict[str, Any]]:
        """Alias for :meth:`run_query` kept for compatibility."""
        return self.run_query(query, **parameters)

    def get_dataframe(self, query: str, **parameters: Any) -> pd.DataFrame:
        """Execute a query and return the result as a DataFrame."""
        return self.connection.get_dataframe(query, parameters)

    def get_raw_value(self, query: str, **parameters: Any) -> List[Dict[str, Any]]:
        """Alias for :meth:`run_query` kept for compatibility."""
        return self.run_query(query, **parameters)

    def get_single_value(self, query: str, **parameters: Any) -> Any:
        """Execute a query and return the first value from the first record."""
        return self.connection.get_single_value(query, parameters)

    def get_query_values(self, query: str, **parameters: Any) -> List[Dict[str, Any]]:
        """Alias for :meth:`run_query`."""
        return self.run_query(query, **parameters)

    def get_nodes_by_node_ids(self, id_list: List[Any]) -> List[Dict[str, Any]]:
        """Retrieve nodes by their Neo4j element IDs."""
        query, params = Neo4jQueryBuilder.get_nodes_by_ids(id_list, self.collection_label)
        return self._normalize_node_records(self.run_query(query, **params))

    def get_nodes_by_attr(
        self,
        attr_values: List[Any],
        attr_name: str,
        node_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve nodes by property values."""
        label = node_label or self.collection_label
        query, params = Neo4jQueryBuilder.get_nodes_by_property(attr_name, attr_values, label)
        return self._normalize_node_records(self.run_query(query, **params))

    def get_currency_nodes(self) -> List[Dict[str, Any]]:
        """Retrieve nodes labeled as currency metabolites."""
        query, params = Neo4jQueryBuilder.get_currency_nodes(self.collection_label)
        return self._normalize_node_records(self.run_query(query, **params))


def print_trace_graph_projection_queries(
    database_class: Type[Database],
    collection_label: str = "",
    scenarios: Optional[List[dict]] = None,
) -> None:
    """Module-level wrapper for printing projection queries from a database class."""
    database_class.print_trace_graph_projection_queries(
        collection_label=collection_label,
        scenarios=scenarios,
    )


__all__ = ["Database", "print_trace_graph_projection_queries"]
