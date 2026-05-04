"""Neo4j-specific Reactome database adapter."""

from __future__ import annotations

import logging
from typing import List, Optional

from lifelike_gds.graph_sources.database import Neo4jDatabase
from lifelike_gds.graph_sources.domain_config import (
    REACTOME_EDGE_DESC_DICT,
    REACTOME_EXCLUDED_NODE_LABELS,
    REACTOME_TRACE_RELATIONSHIP_TYPES,
    REACTOME_TRACE_RELATIONSHIP_TYPES_WITH_REF,
)
from lifelike_gds.graph_sources.reactome import Reactome

logger = logging.getLogger(__name__)

EDGE_DESC_DICT = dict(REACTOME_EDGE_DESC_DICT)
REACTOME_TRACE_RELS = list(REACTOME_TRACE_RELATIONSHIP_TYPES)
REACTOME_TRACE_RELS_WITH_REF = list(REACTOME_TRACE_RELATIONSHIP_TYPES_WITH_REF)


class ReactomeDB(Neo4jDatabase):
    """Neo4j query adapter for the Reactome graph."""

    DEFAULT_EXCLUDED_NODE_LABELS = tuple(REACTOME_EXCLUDED_NODE_LABELS)
    TRACE_RELATIONSHIP_TYPES = tuple(REACTOME_TRACE_RELATIONSHIP_TYPES)

    def __init__(
        self,
        database: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        collection_label: str = "",
    ) -> None:
        super().__init__(
            collection_label=collection_label,
            database=database,
            uri=uri,
            username=username,
            password=password,
        )

    def get_summation_data(self, nodes: List[dict]) -> dict[str, str]:
        node_ids = [str(node["id"]) for node in nodes]
        query = f"""
        MATCH (n{self.label_clause})-[:summation]->(s:Summation)
        WHERE elementId(n) IN $node_ids
        RETURN elementId(n) AS id, s.text AS text
        """
        return {
            row["id"]: row["text"]
            for row in self.get_query_values(query, node_ids=node_ids)
            if "id" in row and "text" in row
        }

    def get_gene_names(self, nodes: List[dict]) -> dict[str, List[str]]:
        node_ids = [str(node["id"]) for node in nodes]
        query = f"""
        MATCH (n{self.label_clause})-[:referenceEntity]->(r)
        WHERE elementId(n) IN $node_ids AND size(coalesce(r.geneName, [])) > 0
        RETURN elementId(n) AS id, r.geneName AS geneNames
        """
        return {
            row["id"]: row["geneNames"]
            for row in self.get_query_values(query, node_ids=node_ids)
            if "id" in row and "geneNames" in row
        }

    def get_entity_nodes_by_gene_ids(self, gene_ids: List[str]) -> List[dict]:
        query = f"""
        MATCH (n{self.label_clause}:ReferenceEntity)
        WHERE n.identifier IN $genes AND n.databaseName = 'NCBI Gene'
        MATCH (n)<-[:referenceGene]-(re:ReferenceEntity)<-[:referenceEntity]-(phys:PhysicalEntity)
        RETURN phys AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, genes=gene_ids))
        logger.info("%s gene_ids matched to %s nodes", len(gene_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_gene_ids(self, gene_ids: List[str]) -> List[dict]:
        query = f"""
        MATCH (n{self.label_clause}:ReferenceEntity)
        WHERE n.identifier IN $genes AND n.databaseName = 'NCBI Gene'
        MATCH (n)<-[:referenceGene]-(m:ReferenceEntity)
        RETURN m AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, genes=gene_ids))
        logger.info("%s gene_ids matched to %s reference nodes", len(gene_ids), len(nodes))
        return nodes

    def get_entity_nodes_by_chebi_ids(self, chebi_ids: List[str]) -> List[dict]:
        query = f"""
        MATCH (r{self.label_clause}:ReferenceEntity)
        WHERE r.databaseName = 'ChEBI' AND r.identifier IN $metabs
        MATCH (phys:PhysicalEntity)-[:referenceEntity]->(r)
        RETURN phys AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, metabs=chebi_ids))
        logger.info("%s chebi_ids matched to %s nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_chebi_ids(self, chebi_ids: List[str]) -> List[dict]:
        query = f"""
        MATCH (r{self.label_clause}:ReferenceEntity)
        WHERE r.databaseName = 'ChEBI' AND r.identifier IN $metabs
        RETURN r AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, metabs=chebi_ids))
        logger.info("%s chebi_ids matched to %s reference nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_node_data_for_excel(self, node_ids: List[str]) -> object:
        query = f"""
        MATCH (n{self.label_clause})
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


__all__ = [
    "EDGE_DESC_DICT",
    "REACTOME_TRACE_RELS",
    "REACTOME_TRACE_RELS_WITH_REF",
    "Reactome",
    "ReactomeDB",
]


if __name__ == "__main__":
    ReactomeDB.print_trace_graph_projection_queries()
