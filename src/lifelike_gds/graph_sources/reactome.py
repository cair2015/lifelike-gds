"""Shared Reactome graph-source logic used by different database backends."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import networkx as nx

from lifelike_gds.graph_sources.domain_config import (
    REACTOME_ALLOWED_NODE_ENTITY_TYPES,
    REACTOME_CURRENCY_METABOLITE_LABEL,
    REACTOME_DEFAULT_EXCLUDED_NODE_LABELS,
    REACTOME_EDGE_DESC_DICT,
    REACTOME_TRACE_RELATIONSHIP_TYPES,
    REACTOME_TRACE_RELATIONSHIP_TYPES_WITH_REF,
)
from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.utils import get_id

ALLOWED_NODE_ENTITY_TYPES = list(REACTOME_ALLOWED_NODE_ENTITY_TYPES)
REACTOME_TRACE_RELS = list(REACTOME_TRACE_RELATIONSHIP_TYPES)
REACTOME_TRACE_RELS_WITH_REF = list(REACTOME_TRACE_RELATIONSHIP_TYPES_WITH_REF)
CURRENCY_METABOLITE_LABEL = REACTOME_CURRENCY_METABOLITE_LABEL
DEFAULT_EXCLUDED_NODE_LABELS = list(REACTOME_DEFAULT_EXCLUDED_NODE_LABELS)
EDGE_DESC_DICT = dict(REACTOME_EDGE_DESC_DICT)


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
