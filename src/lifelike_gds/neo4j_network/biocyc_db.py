"""Neo4j-specific BioCyc database adapter."""

from __future__ import annotations

from typing import List, Optional

from lifelike_gds.network.biocyc import (
    Biocyc,
    CURRENCY_LABEL,
    CURRENCY_METABOLITES,
    EDGE_DESC_DICT,
)
from lifelike_gds.neo4j_network.database import Database


class BiocycDB(Database):
    """Neo4j query adapter for the BioCyc graph."""

    def __init__(
        self,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        collection_label: str = "BioCyc",
    ):
        super().__init__(
            collection_label=collection_label,
            database=database,
            uri=uri,
            username=username,
            password=password,
        )

    def get_graph_data_for_networkx(
        self,
        exclude_currency: bool = True,
        exclude_secondary: bool = True,
        exclude_nodes: Optional[List[str]] = None,
    ):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        node_filters = []
        rel_filters = []
        if exclude_currency:
            node_filters.append(f"NOT '{CURRENCY_LABEL}' IN labels(n)")
            rel_filters.extend(
                [
                    f"NOT '{CURRENCY_LABEL}' IN labels(n)",
                    f"NOT '{CURRENCY_LABEL}' IN labels(m)",
                ]
            )
        if exclude_secondary:
            rel_filters.append("coalesce(r.SECONDARY, false) = false")
        if exclude_nodes:
            node_filters.append("NOT elementId(n) IN $exclude_ids")
            rel_filters.extend(
                ["NOT elementId(n) IN $exclude_ids", "NOT elementId(m) IN $exclude_ids"]
            )

        node_where = f"WHERE {' AND '.join(node_filters)}" if node_filters else ""
        rel_where = f"WHERE {' AND '.join(rel_filters)}" if rel_filters else ""

        node_query = f"""
        MATCH (n{label_clause})
        {node_where}
        RETURN DISTINCT elementId(n) AS node_id
        """
        rel_query = f"""
        MATCH (n{label_clause})-[r]->(m{label_clause})
        {rel_where}
        RETURN elementId(n) AS source, elementId(m) AS target, type(r) AS type
        """
        params = {"exclude_ids": exclude_nodes} if exclude_nodes else {}
        return self.get_dataframe(node_query, **params), self.get_dataframe(rel_query, **params)

    def get_node_data_for_excel(self, node_ids: List[str]):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE elementId(n) IN $node_ids
        RETURN
            elementId(n) AS id,
            n.eid AS eid,
            coalesce(n.displayName, n.name) AS displayName,
            coalesce(n.detail, n.description) AS description,
            n.entityType AS entityType,
            [label IN labels(n) WHERE NOT label STARTS WITH 'db_'] AS labels
        """
        return self.get_dataframe(query, node_ids=node_ids)


__all__ = [
    "Biocyc",
    "BiocycDB",
    "CURRENCY_LABEL",
    "CURRENCY_METABOLITES",
    "EDGE_DESC_DICT",
]
