"""Neo4j-specific BioCyc database adapter."""

from __future__ import annotations

from typing import List, Optional

from lifelike_gds.graph_sources.biocyc import Biocyc
from lifelike_gds.graph_sources.domain_config import (
    BIOCYC_CURRENCY_METABOLITE_LABEL,
    BIOCYC_DEFAULT_EXCLUDED_NODE_LABELS,
    BIOCYC_EDGE_DESC_DICT,
)
from lifelike_gds.graph_sources.database import Neo4jDatabase

CURRENCY_METABOLITE_LABEL = BIOCYC_CURRENCY_METABOLITE_LABEL
DEFAULT_EXCLUDED_NODE_LABELS = list(BIOCYC_DEFAULT_EXCLUDED_NODE_LABELS)
EDGE_DESC_DICT = dict(BIOCYC_EDGE_DESC_DICT)


class BiocycDB(Neo4jDatabase):
    """Neo4j query adapter for the BioCyc graph."""

    DEFAULT_EXCLUDED_NODE_LABELS = tuple(BIOCYC_DEFAULT_EXCLUDED_NODE_LABELS)

    def __init__(
        self,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        collection_label: str = "BioCyc",
    ) -> None:
        super().__init__(
            collection_label=collection_label,
            database=database,
            uri=uri,
            username=username,
            password=password,
        )

    def get_graph_data_for_networkx(
        self,
        exclude_nodes: Optional[List[str]] = None,
        exclude_node_labels: Optional[List[str]] = None,
    ):
        """Backward-compatible alias for BioCyc trace graph projection data."""
        return self.get_trace_graph_data(
            exclude_nodes=exclude_nodes,
            exclude_node_labels=exclude_node_labels,
        )

    def get_node_data_for_excel(self, node_ids: List[str]) -> object:
        query = f"""
        MATCH (n{self.label_clause})
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
    "DEFAULT_EXCLUDED_NODE_LABELS",
    "CURRENCY_METABOLITE_LABEL",
    "EDGE_DESC_DICT",
]
