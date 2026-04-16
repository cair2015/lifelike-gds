"""Shared Reactome graph-source logic used by different database backends."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import networkx as nx

from lifelike_gds.neo4j_network.graph_source import GraphSource
from lifelike_gds.neo4j_network.trace_graph_nx import TraceGraphNx
from lifelike_gds.utils import get_id
from lifelike_gds.neo4j_network.database import Database

logger = logging.getLogger(__name__)

ALLOWED_NODE_ENTITY_TYPES = [
    "Chemical",
    "Protein",
    "Entity",
    "Reaction",
    "Gene",
    "Compound",
    "Species",
    "Study",
    "Pathway",
    "Phenotype",
    "Anatomy",
    "Lab Strain",
    "Note",
    "Cause",
    "Observation",
    "Association",
    "Effect",
    "Correlation",
    "Map",
    "Link",
    "Lab Sample",
    "Food",
    "Phenomena",
    "Company",
    "Mutation",
]

REACTOME_TRACE_RELS = [
    "activeUnitOf",
    "candidateOf",
    "catalystOf",
    "catalyzes",
    "componentOf",
    "input",
    "memberOf",
    "output",
    "regulates",
    "regulatorOf",
    "repeatedUnitOf",
    "requiredInput",
]
REACTOME_TRACE_RELS_WITH_REF = REACTOME_TRACE_RELS + ["referenceEntity"]

CURRENCY_METABOLITE_LABEL = "CurrencyMetabolite"
DEFAULT_EXCLUDED_NODE_LABELS = [CURRENCY_METABOLITE_LABEL]

EDGE_DESC_DICT = {
    "activeUnitOf": "is active unit of",
    "candidateOf": "is candidate of",
    "catalystOf": "is catalyst of",
    "catalyzes": "catalyzes",
    "componentOf": "is component of",
    "hasComponent": "has component",
    "input": "is consumed by",
    "memberOf": "is member of",
    "output": "produces",
    "referenceEntity": "has reference entity",
    "regulates": "regulates",
    "regulatorOf": "is regulator of",
    "repeatedUnitOf": "is repeated unit of",
    "requiredInput": "is required input for",
}


class Reactome(GraphSource):
    """Database-agnostic Reactome graph source with shared domain behavior."""

    @classmethod
    def get_node_name(cls, node: Dict[str, Any]) -> Optional[str]:
        return node.get("name") or cls.split_display_name(node.get("displayName", ""))[0]

    @classmethod
    def get_node_desc(cls, node: Dict[str, Any]) -> Optional[str]:
        entity_type = node.get("entityType")
        display_name = node.get("displayName")
        if entity_type and display_name:
            return f"{entity_type} {display_name}"
        return display_name or node.get("name")

    @classmethod
    def get_node_entity_type(cls, node: Dict[str, Any]) -> str:
        """Map unsupported entity types back to the generic Reactome entity bucket."""
        entity_type = node.get("entityType", "Entity")
        if entity_type in ALLOWED_NODE_ENTITY_TYPES:
            return entity_type
        return "Entity"

    @classmethod
    def split_display_name(cls, display_name: str) -> tuple[str, str]:
        """Split a Reactome display name into base name and compartment."""
        if not display_name:
            return "", ""
        if not re.fullmatch(r".+ \[[A-Za-z0-9- ]+]", display_name):
            return display_name, ""
        compartment = re.findall(r"\[([A-Za-z0-9- ]+)]", display_name)[0]
        return display_name[: -len(compartment) - 3], compartment

    def add_summation(self, nodes: List[Dict[str, Any]], graph: Any) -> None:
        if not hasattr(self.database, "get_summation_data"):
            return
        node_summation = self.database.get_summation_data(nodes)
        nx.set_node_attributes(graph, node_summation, "summation")

    def add_gene_names(self, nodes: List[Dict[str, Any]], graph: Any) -> None:
        if not hasattr(self.database, "get_gene_names"):
            return
        node_gene_names = self.database.get_gene_names(nodes)
        nx.set_node_attributes(graph, node_gene_names, "gene_names")

    def initiate_trace_graph(
        self,
        tracegraph: Any,
        exclude_node_labels: Optional[List[str]] = None,
    ) -> None:
        node_rows, rel_rows = self.database.get_trace_graph_data(
            exclude_node_labels=exclude_node_labels,
        )
        self.populate_tracegraph(tracegraph, node_rows, rel_rows)
        logger.info(
            "Loaded Reactome trace graph: nodes=%s edges=%s",
            tracegraph.graph.number_of_nodes(),
            tracegraph.graph.number_of_edges(),
        )

    def load_graph_to_tracegraph(
        self,
        tracegraph: TraceGraphNx,
        exclude_nodes: Optional[List[int]] = None,
        exclude_node_labels: Optional[List[str]] = None,
    ) -> None:
        node_rows, rel_rows = self.database.get_trace_graph_data(
            exclude_nodes=exclude_nodes,
            exclude_node_labels=exclude_node_labels,
        )
        self.populate_tracegraph(tracegraph, node_rows, rel_rows)
        logger.info(
            "Loaded Reactome graph projection: nodes=%s edges=%s",
            tracegraph.graph.number_of_nodes(),
            tracegraph.graph.number_of_edges(),
        )

    @classmethod
    def set_edge_description(
        cls,
        graph: Any,
        start_node: Dict[str, Any],
        end_node: Dict[str, Any],
        edge_type: str,
        key: Optional[str] = None,
    ) -> None:
        source_display_name = (
            f"{start_node.get('entityType')}"
            f"({cls.split_display_name(start_node.get('displayName', ''))[0]})"
        )
        target_display_name = (
            f"{end_node.get('entityType')}"
            f"({cls.split_display_name(end_node.get('displayName', ''))[0]})"
        )
        nlg = f"{source_display_name} | {edge_type} | {target_display_name}"
        desc = f"RELATIONSHIP: {edge_type}\n{nlg}"
        edge_ref = (
            (get_id(start_node), get_id(end_node), key)
            if key is not None
            else (get_id(start_node), get_id(end_node))
        )
        if edge_ref in graph.edges:
            graph.edges[edge_ref]["description"] = desc

    def set_nodes_description(self, nodes: List[Dict[str, Any]], graph: Any) -> None:
        self.add_summation(nodes, graph)
        for node in nodes:
            node_id = get_id(node)
            if node_id not in graph:
                continue
            lines = [f"NODE: {node.get('entityType')}"]
            lines.extend(node.get("synonyms", []))
            lines.append("")
            if "summation" in graph.nodes[node_id]:
                lines.extend(["SUMMATION:", graph.nodes[node_id]["summation"]])
            graph.nodes[node_id]["description"] = "\n".join(lines)

    def set_edges_description(self, edges: List[Dict[str, Any]], graph: Any) -> None:
        for edge in edges:
            start_node = edge.get("start_node") or edge.get("source_node")
            end_node = edge.get("end_node") or edge.get("target_node")
            edge_type = edge.get("type") or edge.get("label")
            if start_node and end_node and edge_type:
                self.set_edge_description(graph, start_node, end_node, edge_type, key=edge.get("key"))

    def get_node_data_for_excel(self, node_ids: List[int]):
        return self.database.get_node_data_for_excel(node_ids)
    


class ReactomeDB(Database):
    """Neo4j query adapter for the Reactome graph."""

    DEFAULT_EXCLUDED_NODE_LABELS = tuple(DEFAULT_EXCLUDED_NODE_LABELS)
    TRACE_RELATIONSHIP_TYPES = tuple(REACTOME_TRACE_RELS)

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
    
if __name__ == "__main__":
    db = ReactomeDB()
    nodes = db.get_entity_nodes_by_chebi_ids(["37565", "456215"])
    print(nodes)