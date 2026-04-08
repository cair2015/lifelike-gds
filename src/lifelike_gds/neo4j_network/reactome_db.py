"""Neo4j-specific Reactome database adapter."""

from __future__ import annotations

import logging
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

    def get_trace_graph_data(
        self,
        exclude_secondary_metabolites: bool = True,
        exclude_secondary: bool = True,
        exclude_nodes: Optional[List[str]] = None,
    ):
        label_clause = f":{self.collection_label}" if self.collection_label else ""
        rel_type_clause = "|".join(REACTOME_TRACE_RELS)
        node_filters = []
        rel_filters = []

        if exclude_secondary_metabolites:
            node_filters.append(f"NOT '{SECONDARY_LABEL}' IN labels(n)")
            rel_filters.extend(
                [
                    f"NOT '{SECONDARY_LABEL}' IN labels(n)",
                    f"NOT '{SECONDARY_LABEL}' IN labels(m)",
                ]
            )
        if exclude_secondary:
            rel_filters.append("coalesce(r.secondary, false) = false")
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
        WITH n
        MATCH (n)-[r:{rel_type_clause}]->()
        RETURN DISTINCT elementId(n) AS node_id
        UNION
        MATCH ()-[r:{rel_type_clause}]->(n{label_clause})
        {node_where}
        RETURN DISTINCT elementId(n) AS node_id
        """
        rel_query = f"""
        MATCH (n{label_clause})-[r:{rel_type_clause}]->(m{label_clause})
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
    "ALLOWED_NODE_ENTITY_TYPES",
    "EDGE_DESC_DICT",
    "REACTOME_TRACE_RELS",
    "REACTOME_TRACE_RELS_WITH_REF",
    "Reactome",
    "ReactomeDB",
    "SECONDARY_CHEMS",
    "SECONDARY_LABEL",
]
