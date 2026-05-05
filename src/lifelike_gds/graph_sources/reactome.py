"""Shared Reactome graph-source logic used by different database backends."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import networkx as nx

from lifelike_gds.graph_sources.domain_config import (
    REACTOME_EDGE_DESC_DICT,
    REACTOME_EXCLUDED_NODE_LABELS,
    REACTOME_REFERENCE_REL_TYPE,
    REACTOME_TRACE_NODE_LABEL,
    REACTOME_TRACE_RELATIONSHIP_TYPES,
)
from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.utils import get_id
from lifelike_gds.graph_sources.reactome_db import ReactomeDB

if TYPE_CHECKING:
    from lifelike_gds.network.trace_graph_nx import TraceGraphNx

REACTOME_TRACE_RELS = list(REACTOME_TRACE_RELATIONSHIP_TYPES)
REACTOME_TRACE_RELS_WITH_REF = [*REACTOME_TRACE_RELATIONSHIP_TYPES, REACTOME_REFERENCE_REL_TYPE]
EDGE_DESC_DICT = dict(REACTOME_EDGE_DESC_DICT)


class Reactome(GraphSource):
    """Database-agnostic Reactome graph source with shared domain behavior."""

    def __init__(
        self,
        database: ReactomeDB,
        node_label: str = REACTOME_TRACE_NODE_LABEL,
        node_label_prop: str = "displayName",
    ) -> None:
        super().__init__(database=database, node_label_prop=node_label_prop)
        self.node_label = node_label

    def get_node_query_label(self) -> str | None:
        return self.node_label

    @staticmethod
    def _format_label_clause(node_label: str | None) -> str:
        return f":{node_label}" if node_label else ""

    def initiate_trace_graph(
        self,
        tracegraph: TraceGraphNx,
        exclude_node_labels: list[str] = REACTOME_EXCLUDED_NODE_LABELS,
        **_: Any,
    ) -> None:
        excl_clause = " AND ".join(
            f"NOT a:{lbl} AND NOT b:{lbl}" for lbl in exclude_node_labels
        )
        rel_types = list(REACTOME_TRACE_RELATIONSHIP_TYPES)
        node_label = self._format_label_clause(self.node_label)

        query = f"""
        MATCH (a{node_label})-[r]->(b{node_label})
        WHERE {excl_clause}
        AND type(r) IN $rel_types
        RETURN
          elementId(a) AS source,
          elementId(b) AS target,
          type(r) AS relationship_type,
          elementId(r) AS relationship_id
        """
        rows = self.database.get_query_values(query, rel_types=rel_types)
        tracegraph.add_relationship_rows(
            rows,
            source_key="source",
            target_key="target",
            label_key="relationship_type",
        )

    def add_reference_entity_relationships(self, ref_nodes: List[Dict[str, Any]], tracegraph: TraceGraphNx) -> None:
        node_ids = [get_id(node) for node in ref_nodes]
        if not node_ids:
            return
        label_clause = self._format_label_clause(self.node_label)
        query = f"""
        MATCH (a)-[r:{REACTOME_REFERENCE_REL_TYPE}]->(b{label_clause})
        WHERE elementId(a) IN $node_ids
        RETURN 
            elementId(a) AS source,
            elementId(b) AS target,
            type(r) AS relationship_type,
            elementId(r) AS relationship_id
        """
        rows = self.database.get_query_values(query, node_ids=node_ids)
        tracegraph.add_relationship_rows(
            rows,
            source_key="source",
            target_key="target",
            label_key="relationship_type",
        )
    

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
        node_summation = self.database.get_summation_data(
            nodes,
            node_label=self.node_label,
        )
        nx.set_node_attributes(graph, node_summation, "summation")

    # def add_gene_names(self, nodes: List[Dict[str, Any]], graph: Any) -> None:
    #     if not hasattr(self.database, "get_gene_names"):
    #         return
    #     node_gene_names = self.database.get_gene_names(
    #         nodes,
    #         node_label=self.node_label,
    #     )
    #     nx.set_node_attributes(graph, node_gene_names, "gene_names")

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
