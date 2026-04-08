"""Neo4j-specific Reactome database adapter."""

from __future__ import annotations

import logging
from pprint import pformat
from typing import List, Optional

from lifelike_gds.network.reactome import (
    ALLOWED_NODE_ENTITY_TYPES,
    EDGE_DESC_DICT,
    REACTOME_TRACE_RELS,
    REACTOME_TRACE_RELS_WITH_REF,
    Reactome,
    SECONDARY_CHEMS,
    SECONDARY_LABEL,
)
from lifelike_gds.neo4j_network.database import Database

logger = logging.getLogger(__name__)


class ReactomeDB(Database):
    """Neo4j query adapter for the Reactome graph."""

    def __init__(
        self,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        collection_label: str = "",
    ):
        super().__init__(
            collection_label=collection_label,
            database=database,
            uri=uri,
            username=username,
            password=password,
        )

    def get_summation_data(self, nodes: List[dict]):
        node_ids = [str(node["id"]) for node in nodes]
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (n{label_clause})-[:summation]->(s:Summation)
        WHERE elementId(n) IN $node_ids
        RETURN elementId(n) AS id, s.text AS text
        """
        return {
            row["id"]: row["text"]
            for row in self.get_query_values(query, node_ids=node_ids)
            if "id" in row and "text" in row
        }

    def get_gene_names(self, nodes: List[dict]):
        node_ids = [str(node["id"]) for node in nodes]
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (n{label_clause})-[:referenceEntity]->(r)
        WHERE elementId(n) IN $node_ids AND size(coalesce(r.geneName, [])) > 0
        RETURN elementId(n) AS id, r.geneName AS geneNames
        """
        return {
            row["id"]: row["geneNames"]
            for row in self.get_query_values(query, node_ids=node_ids)
            if "id" in row and "geneNames" in row
        }

    def get_entity_nodes_by_gene_ids(self, gene_ids: List[str]):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (n{label_clause}:ReferenceEntity)
        WHERE n.identifier IN $genes AND n.databaseName = 'NCBI Gene'
        MATCH (n)<-[:referenceGene]-(re:ReferenceEntity)<-[:referenceEntity]-(phys:PhysicalEntity)
        RETURN phys AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, genes=gene_ids))
        logger.info("%s gene_ids matched to %s nodes", len(gene_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_gene_ids(self, gene_ids: List[str]):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (n{label_clause}:ReferenceEntity)
        WHERE n.identifier IN $genes AND n.databaseName = 'NCBI Gene'
        MATCH (n)<-[:referenceGene]-(m:ReferenceEntity)
        RETURN m AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, genes=gene_ids))
        logger.info("%s gene_ids matched to %s reference nodes", len(gene_ids), len(nodes))
        return nodes

    def get_entity_nodes_by_chebi_ids(self, chebi_ids: List[str]):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (r{label_clause}:ReferenceEntity)
        WHERE r.databaseName = 'ChEBI' AND r.identifier IN $metabs
        MATCH (phys:PhysicalEntity)-[:referenceEntity]->(r)
        RETURN phys AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, metabs=chebi_ids))
        logger.info("%s chebi_ids matched to %s nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_chebi_ids(self, chebi_ids: List[str]):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (r{label_clause}:ReferenceEntity)
        WHERE r.databaseName = 'ChEBI' AND r.identifier IN $metabs
        RETURN r AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, metabs=chebi_ids))
        logger.info("%s chebi_ids matched to %s reference nodes", len(chebi_ids), len(nodes))
        return nodes

    @staticmethod
    def _render_where_clause(filters: List[str]) -> str:
        """Render a Cypher ``WHERE`` clause from a list of filter expressions."""
        return f"WHERE {' AND '.join(filters)}" if filters else ""

    @staticmethod
    def _build_trace_graph_filters(
        exclude_secondary_metabolites: bool = True,
        exclude_nodes: Optional[List[str]] = None,
    ) -> List[str]:
        """Build filter expressions shared by trace graph projection queries."""
        filters: List[str] = []

        if exclude_secondary_metabolites:
            filters.extend(
                [
                    f"NOT '{SECONDARY_LABEL}' IN labels(n)",
                    f"NOT '{SECONDARY_LABEL}' IN labels(m)",
                ]
            )
        if exclude_nodes:
            filters.extend(
                ["NOT elementId(n) IN $exclude_ids", "NOT elementId(m) IN $exclude_ids"]
            )

        return filters

    @classmethod
    def build_trace_graph_projection_queries(
        cls,
        collection_label: str = "",
        exclude_secondary_metabolites: bool = True,
        exclude_nodes: Optional[List[str]] = None,
    ) -> tuple[str, str, dict]:
        """Return projection queries for a provided label without a DB connection."""
        label_clause = f":{collection_label}" if collection_label else ""
        rel_type_clause = "|".join(REACTOME_TRACE_RELS)
        filters = cls._build_trace_graph_filters(
            exclude_secondary_metabolites=exclude_secondary_metabolites,
            exclude_nodes=exclude_nodes,
        )
        where_clause = cls._render_where_clause(filters)

        node_query = f"""
        MATCH (n{label_clause})-[r:{rel_type_clause}]->(m{label_clause})
        {where_clause}
        UNWIND [n, m] AS x
        RETURN DISTINCT elementId(x) AS node_id
        """
        rel_query = f"""
        MATCH (n{label_clause})-[r:{rel_type_clause}]->(m{label_clause})
        {where_clause}
        RETURN elementId(n) AS source, elementId(m) AS target, type(r) AS type
        """
        params = {"exclude_ids": exclude_nodes} if exclude_nodes else {}
        return node_query, rel_query, params

    def get_trace_graph_data(
        self,
        exclude_secondary_metabolites: bool = True,
        exclude_nodes: Optional[List[str]] = None,
    ):
        node_query, rel_query, params = self.build_trace_graph_projection_queries(
            collection_label=self.collection_label,
            exclude_secondary_metabolites=exclude_secondary_metabolites,
            exclude_nodes=exclude_nodes,
        )
        return self.get_dataframe(node_query, **params), self.get_dataframe(rel_query, **params)

    def get_node_data_for_excel(self, node_ids: List[str]):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        query = f"""
        MATCH (n{label_clause})
        WHERE elementId(n) IN $node_ids
        OPTIONAL MATCH (n)-[:referenceEntity]->(r)
        WITH n, r
        RETURN
            elementId(n) AS id,
            n.stId AS stId,
            n.name AS name,
            n.displayName AS displayName,
            n.synonyms AS synonyms,
            head(coalesce(r.geneName, [])) AS geneName,
            r.identifier AS chebiUniprot,
            n.entityType AS entityType,
            labels(n) AS labels
        """
        return self.get_dataframe(query, node_ids=node_ids)


def print_trace_graph_projection_queries(
    collection_label: str = "",
    scenarios: Optional[List[dict]] = None,
) -> None:
    """Print projection queries for a few common filter combinations.

    Args:
        collection_label: Optional node label to include in the projection.
        scenarios: Optional list of scenario dicts. Each dict may contain:
            ``name``, ``exclude_secondary_metabolites``, and ``exclude_nodes``.
    """
    if scenarios is None:
        scenarios = [
            {
                "name": "default_filters",
                "exclude_secondary_metabolites": True,
                "exclude_nodes": None,
            },
            {
                "name": "include_secondary_metabolites",
                "exclude_secondary_metabolites": False,
                "exclude_nodes": None,
            },
            {
                "name": "exclude_specific_nodes",
                "exclude_secondary_metabolites": True,
                "exclude_nodes": ["4:demo-source", "4:demo-target"],
            },
        ]

    for scenario in scenarios:
        name = scenario.get("name", "unnamed_scenario")
        node_query, rel_query, params = ReactomeDB.build_trace_graph_projection_queries(
            collection_label=collection_label,
            exclude_secondary_metabolites=scenario.get(
                "exclude_secondary_metabolites",
                True,
            ),
            exclude_nodes=scenario.get("exclude_nodes"),
        )
        print(f"=== {name} ===")
        print(f"collection_label={collection_label!r}")
        print(f"params={pformat(params)}")
        print("node_query:")
        print(node_query.strip())
        print("rel_query:")
        print(rel_query.strip())
        print()


__all__ = [
    "ALLOWED_NODE_ENTITY_TYPES",
    "EDGE_DESC_DICT",
    "REACTOME_TRACE_RELS",
    "REACTOME_TRACE_RELS_WITH_REF",
    "Reactome",
    "ReactomeDB",
    "SECONDARY_CHEMS",
    "SECONDARY_LABEL",
]


if __name__ == "__main__":
    print_trace_graph_projection_queries()
