"""Neo4j-specific Reactome database adapter."""

from __future__ import annotations

import logging
from typing import List, Optional

from lifelike_gds.graph_sources.database import Neo4jDatabase

logger = logging.getLogger(__name__)


class ReactomeDB(Neo4jDatabase):
    """Neo4j query adapter for the Reactome graph."""

    def get_summation_data(
        self,
        nodes: List[dict],
        node_label: Optional[str] = None,
    ) -> dict[str, str]:
        node_ids = [str(node["id"]) for node in nodes]
        label_clause = self.format_label_clause(node_label)
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

    def get_gene_names(
        self,
        nodes: List[dict],
        node_label: Optional[str] = None,
    ) -> dict[str, List[str]]:
        node_ids = [str(node["id"]) for node in nodes]
        label_clause = self.format_label_clause(node_label)
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
    
    def get_refrence_nodes(
        self,
        ref_databasename: str,
        ref_identifiers: List[str]
    ) -> Optional[dict]:
        query = f"""
        MATCH (n:ReferenceEntity)
        WHERE n.databaseName = $ref_databasename AND n.identifier in $ref_identifiers
        RETURN n
        """
        result = self.run_query(query, ref_databasename=ref_databasename, ref_identifiers=ref_identifiers   )
        return self._normalize_node_records(result)

    
    def get_entity_nodes_by_reference_entities(
        self,
        ref_databasename: str,
        ref_identifiers: List[str],
        node_label: Optional[str] = None,
    ) -> List[dict]:
        """
        Retrieve normalized nodes by matching reference entity database and identifier. 
        Args:
            ref_databasename: Reference entity database name to match.
            ref_identifiers: Reference entity identifiers to match.
            node_label: Optional label used to scope matched entity nodes.

        Returns:
            List of normalized physical entity node dictionaries.
        """
        label_clause = self.format_label_clause(node_label)
        query = f"""
        MATCH (n{label_clause})-[:referenceEntity]->(r:ReferenceEntity)
        WHERE r.databaseName = $ref_databasename AND r.identifier IN $ref_identifiers
        RETURN n
        """
        print(query)
        return self._normalize_node_records(
            self.run_query(
                query,
                ref_databasename=ref_databasename,
                ref_identifiers=ref_identifiers,
            )
        )

    def get_entity_nodes_by_chebi_ids(
        self,
        chebi_ids: List[str],
        node_label: Optional[str] = None,
    ) -> List[dict]:
        label_clause = self.format_label_clause(node_label)
        query = f"""
        MATCH (r{label_clause}:ReferenceEntity)
        WHERE r.databaseName = 'ChEBI' AND r.identifier IN $metabs
        MATCH (phys:PhysicalEntity)-[:referenceEntity]->(r)
        RETURN phys AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, metabs=chebi_ids))
        logger.info("%s chebi_ids matched to %s nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_entity_nodes_by_gene_ids(
        self,
        gene_ids: List[str],
        node_label: Optional[str] = None,
    ) -> List[dict]:
        label_clause = self.format_label_clause(node_label)
        query = f"""
        MATCH (n{label_clause}:ReferenceEntity)
        WHERE n.identifier IN $genes AND n.databaseName = 'NCBI Gene'
        MATCH (n)<-[:referenceGene]-(re:ReferenceEntity)<-[:referenceEntity]-(phys:PhysicalEntity)
        RETURN phys AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, genes=gene_ids))
        logger.info("%s gene_ids matched to %s nodes", len(gene_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_gene_ids(
        self,
        gene_ids: List[str],
        node_label: Optional[str] = None,
    ) -> List[dict]:
        label_clause = self.format_label_clause(node_label)
        query = f"""
        MATCH (n{label_clause}:ReferenceEntity)
        WHERE n.identifier IN $genes AND n.databaseName = 'NCBI Gene'
        MATCH (n)<-[:referenceGene]-(m:ReferenceEntity)
        RETURN m AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, genes=gene_ids))
        logger.info("%s gene_ids matched to %s reference nodes", len(gene_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_chebi_ids(
        self,
        chebi_ids: List[str],
        node_label: Optional[str] = None,
    ) -> List[dict]:
        label_clause = self.format_label_clause(node_label)
        query = f"""
        MATCH (r{label_clause}:ReferenceEntity)
        WHERE r.databaseName = 'ChEBI' AND r.identifier IN $metabs
        RETURN r AS n
        """
        nodes = self._normalize_node_records(self.run_query(query, metabs=chebi_ids))
        logger.info("%s chebi_ids matched to %s reference nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_node_data_for_excel(
        self,
        node_ids: List[str],
        node_label: Optional[str] = None,
    ) -> object:
        label_clause = self.format_label_clause(node_label)
        query = f"""
        MATCH (n{label_clause})
        WHERE elementId(n) IN $node_ids
        OPTIONAL MATCH (n)-[:referenceEntity]->(r)
        WITH n, r
        RETURN
            elementId(n) AS id,
            n.dbId as dbId,
            n.stId AS stId,
            n.displayName AS displayName,
            n.name AS name,
            r.databaseName + ":" + r.identifier as referenceEntity,
            n.entityType as entityType
        """
        return self.get_dataframe(query, parameters={'node_ids': node_ids})


__all__ = ["ReactomeDB"]
