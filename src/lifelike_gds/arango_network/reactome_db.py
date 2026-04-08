"""ArangoDB-specific Reactome database adapter."""

from __future__ import annotations

import logging
from typing import List, Optional

from lifelike_gds.arango_network.database import Database
from lifelike_gds.network.reactome import (
    ALLOWED_NODE_ENTITY_TYPES,
    EDGE_DESC_DICT,
    REACTOME_TRACE_RELS,
    REACTOME_TRACE_RELS_WITH_REF,
    Reactome,
    SECONDARY_CHEMS,
    SECONDARY_LABEL,
)
from lifelike_gds.utils import get_id

logger = logging.getLogger(__name__)


class ReactomeDB(Database):
    """ArangoDB query adapter for the Reactome graph."""

    def __init__(
        self,
        dbname: Optional[str] = None,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__("reactome", dbname=dbname, uri=uri, username=username, password=password)

    def get_summation_data(self, nodes: List[dict]):
        ids = [get_id(node) for node in nodes]
        query = """
        FOR n IN reactome
            FILTER TO_NUMBER(n._key) IN @ids
            FOR s IN OUTBOUND n summation
                FILTER "Summation" IN s.labels
                RETURN {
                    id: TO_NUMBER(n._key),
                    text: s.text
                }
        """
        return {
            row["id"]: row["text"]
            for row in self.get_query_values(query, ids=ids)
            if "id" in row and "text" in row
        }

    def get_gene_names(self, nodes: List[dict]):
        ids = [get_id(node) for node in nodes]
        query = """
            FOR n IN reactome
                FILTER TO_NUMBER(n._key) IN @ids
                FOR r IN OUTBOUND n referenceEntity
                    FILTER LENGTH(r.geneName) > 0
                    RETURN {
                        id: TO_NUMBER(n._key),
                        geneNames: r.geneName
                    }
        """
        return {
            row["id"]: row["geneNames"]
            for row in self.get_query_values(query, ids=ids)
            if "id" in row and "geneNames" in row
        }

    def get_nodes_by_attr(self, attr_values: List[str], attr_name: str, node_label: str = "db_Reactome"):
        return super().get_nodes_by_attr(attr_values, attr_name, node_label)

    def get_entity_nodes_by_gene_ids(self, gene_ids: List[str]):
        query = """
        FOR n IN reactome
            FILTER n.identifier IN @genes && "ReferenceEntity" IN n.labels && n.databaseName == "NCBI Gene"
            FOR re IN INBOUND n referenceGene
                FOR phys IN INBOUND re referenceEntity
                    FILTER "PhysicalEntity" IN phys.labels
                    RETURN phys
        """
        nodes = self.get_raw_value(query, genes=gene_ids)
        logger.info("%s gene_ids matched to %s nodes", len(gene_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_gene_ids(self, gene_ids: List[str]):
        query = """
        FOR n IN reactome
            FILTER n.identifier IN @genes && "ReferenceEntity" IN n.labels && n.databaseName == "NCBI Gene"
            FOR m IN INBOUND n referenceGene
                FILTER "ReferenceEntity" IN m.labels
                RETURN {m: m}
        """
        nodes = self.get_raw_value(query, genes=gene_ids)
        logger.info("%s gene_ids matched to %s reference nodes", len(gene_ids), len(nodes))
        return nodes

    def get_entity_nodes_by_chebi_ids(self, chebi_ids: List[str]):
        query = """
        FOR n IN reactome
            FILTER "PhysicalEntity" IN n.labels
            FOR r IN OUTBOUND n referenceEntity
                FILTER "ReferenceEntity" IN r.labels && r.databaseName == "ChEBI" && r.identifier IN @metabs
                RETURN n
        """
        nodes = self.get_raw_value(query, metabs=chebi_ids)
        logger.info("%s chebi_ids matched to %s nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_reference_nodes_by_chebi_ids(self, chebi_ids: List[str]):
        query = """
        FOR r IN reactome
            FILTER "ReferenceEntity" IN r.labels && r.databaseName == "ChEBI" && r.identifier IN @metabs
            RETURN {r: r}
        """
        nodes = self.get_raw_value(query, metabs=chebi_ids)
        logger.info("%s chebi_ids matched to %s reference nodes", len(chebi_ids), len(nodes))
        return nodes

    def get_trace_graph_data(
        self,
        exclude_secondary_metabolites: bool = True,
        exclude_secondary: bool = True,
        exclude_nodes: Optional[List[int]] = None,
    ):
        del exclude_secondary
        exclude_ids = [get_id(node) for node in exclude_nodes] if exclude_nodes else []
        node_lists_query = ",".join(
            f"""
                FLATTEN(
                    FOR n IN {rel}
                        RETURN [n._from, n._to]
                )
            """
            for rel in REACTOME_TRACE_RELS
        )
        rel_lists_query = ",".join(
            f"""
                (
                    FOR n IN {rel}
                        RETURN n
                )
            """
            for rel in REACTOME_TRACE_RELS
        )

        secondary_filter = 'FILTER "SecondaryMetabolite" NOT IN node.labels'
        source_secondary_filter = 'FILTER "SecondaryMetabolite" NOT IN node_from.labels'
        target_secondary_filter = 'FILTER "SecondaryMetabolite" NOT IN node_to.labels'
        exclude_node_filter = "FILTER key NOT IN @exclude_ids" if exclude_ids else ""
        exclude_source_filter = "FILTER key_from NOT IN @exclude_ids" if exclude_ids else ""
        exclude_target_filter = "FILTER key_to NOT IN @exclude_ids" if exclude_ids else ""

        node_query = f"""
            FOR n IN UNION_DISTINCT(
                {node_lists_query}
            )
                LET key = TO_NUMBER(PARSE_IDENTIFIER(n).key)
                {exclude_node_filter}
                FOR node IN reactome
                    FILTER TO_NUMBER(node._key) == key
                    {secondary_filter if exclude_secondary_metabolites else ''}
                    RETURN {{node_id: key}}
        """
        rel_query = f"""
            FOR n IN UNION_DISTINCT(
                {rel_lists_query}
            )
                LET key_from = TO_NUMBER(PARSE_IDENTIFIER(n._from).key)
                LET key_to = TO_NUMBER(PARSE_IDENTIFIER(n._to).key)
                {exclude_source_filter}
                {exclude_target_filter}
                FOR node_from IN reactome
                    FILTER TO_NUMBER(node_from._key) == key_from
                    {source_secondary_filter if exclude_secondary_metabolites else ''}
                    FOR node_to IN reactome
                        FILTER TO_NUMBER(node_to._key) == key_to
                        {target_secondary_filter if exclude_secondary_metabolites else ''}
                        RETURN {{
                            source: key_from,
                            target: key_to,
                            type: n.label
                        }}
        """
        parameters = {"exclude_ids": exclude_ids} if exclude_ids else {}
        return self.get_dataframe(node_query, **parameters), self.get_dataframe(rel_query, **parameters)

    def get_node_data_for_excel(self, node_ids: List[int]):
        query = """
            FOR n IN reactome
                FILTER TO_NUMBER(n._key) IN @nids
                LET gene = FIRST(
                    FOR r IN OUTBOUND n referenceEntity
                        FILTER LENGTH(r.geneName) > 0
                        RETURN {
                            name: FIRST(r.geneName),
                            identifier: r.identifier
                        }
                )
                RETURN {
                    id: TO_NUMBER(n._key),
                    stId: n.stId,
                    name: n.name,
                    displayName: n.displayName,
                    synonyms: n.synonyms,
                    geneName: gene.name,
                    chebiUniprot: gene.identifier,
                    entityType: n.entityType,
                    labels: n.labels
                }
        """
        return self.get_dataframe(query, nids=node_ids)


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
