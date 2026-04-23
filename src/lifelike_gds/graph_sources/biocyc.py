"""Shared BioCyc graph-source logic used by different database backends."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lifelike_gds.graph_sources.domain_config import (
    BIOCYC_CURRENCY_METABOLITE_LABEL,
    BIOCYC_DEFAULT_EXCLUDED_NODE_LABELS,
    BIOCYC_EDGE_DESC_DICT,
)
from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.utils import get_id

CURRENCY_METABOLITE_LABEL = BIOCYC_CURRENCY_METABOLITE_LABEL
DEFAULT_EXCLUDED_NODE_LABELS = list(BIOCYC_DEFAULT_EXCLUDED_NODE_LABELS)
EDGE_DESC_DICT = dict(BIOCYC_EDGE_DESC_DICT)


class Biocyc(GraphSource):
    """Database-agnostic BioCyc graph source with shared domain behavior."""

    @classmethod
    def get_node_name(cls, node: Dict[str, Any]) -> Optional[str]:
        return node.get("name") or node.get("displayName")

    @classmethod
    def get_node_desc(cls, node: Dict[str, Any]) -> Optional[str]:
        entity_type = node.get("entityType")
        display_name = node.get("displayName")
        if entity_type and display_name:
            return f"{entity_type} {display_name}"
        return display_name or node.get("name")

    @classmethod
    def set_edge_description(
        cls,
        graph: Any,
        start_node: Dict[str, Any],
        end_node: Dict[str, Any],
        edge_type: str,
        key: Optional[str] = None,
    ) -> None:
        source_display_name = f"{start_node.get('entityType')}({start_node.get('displayName')})"
        target_display_name = f"{end_node.get('entityType')}({end_node.get('displayName')})"
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
        for node in nodes:
            node_id = get_id(node)
            if node_id not in graph:
                continue
            lines = [f"NODE: {node.get('entityType')}"]
            lines.extend(node.get("synonyms", []))
            detail = node.get("detail", "")
            if detail:
                lines.extend(["", "DETAIL:", detail])
            graph.nodes[node_id]["description"] = "\n".join(lines)

    def set_edges_description(self, edges: List[Dict[str, Any]], graph: Any) -> None:
        for edge in edges:
            start_node = edge.get("start_node") or edge.get("source_node")
            end_node = edge.get("end_node") or edge.get("target_node")
            edge_type = edge.get("type") or edge.get("label")
            if start_node and end_node and edge_type:
                self.set_edge_description(graph, start_node, end_node, edge_type, key=edge.get("key"))
