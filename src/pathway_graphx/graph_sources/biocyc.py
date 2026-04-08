"""Shared BioCyc graph-source logic used by different database backends."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pathway_graphx.network.graph_source import GraphSource
from pathway_graphx.utils import get_id

logger = logging.getLogger(__name__)

CURRENCY_METABOLITES = [
    "NAD-P-OR-NOP",
    "NADH-P-OR-NOP",
    "Donor-H2",
    "Acceptor",
    "HYDROGEN-PEROXIDE",
    "OXYGEN-MOLECULE",
    "NAD",
    "NADP",
    "NADH",
    "NADPH",
    "WATER",
    "CARBON-DIOXIDE",
    "FAD",
    "CO-A",
    "UDP",
    "AMMONIA",
    "NA+",
    "AMMONIUM",
    "PROTON",
    "CARBON-MONOXIDE",
    "GTP",
    "ADP",
    "GDP",
    "AMP",
    "ATP",
    "3-5-ADP",
    "PPI",
    "Pi",
]

CURRENCY_LABEL = "CurrencyMetabolite"

EDGE_DESC_DICT = {
    "ELEMENT_OF": "is element of",
    "ENCODES": "encodes",
    "MODIFIED_TO": "is modified to",
    "COMPONENT_OF": "is component of",
    "CONSUMED_BY": "is consumed by",
    "PRODUCES": "produces",
    "IN_PATHWAY": "is in",
    "CATALYZES": "catalyzes",
    "REGULATES": "regulates",
    "HAS_GENE": "contains",
    "ACTIVATES": "activates",
    "INHIBITS": "inhibits",
}


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
        edge_ref = (get_id(start_node), get_id(end_node), key) if key is not None else (get_id(start_node), get_id(end_node))
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

    def initiate_trace_graph(
        self,
        tracegraph: Any,
        exclude_currency: bool = True,
        exclude_secondary: bool = True,
    ) -> None:
        node_rows, rel_rows = self.database.get_graph_data_for_networkx(
            exclude_currency=exclude_currency,
            exclude_secondary=exclude_secondary,
        )
        self.populate_tracegraph(tracegraph, node_rows, rel_rows)
        logger.info(
            "Loaded BioCyc trace graph: nodes=%s edges=%s",
            tracegraph.graph.number_of_nodes(),
            tracegraph.graph.number_of_edges(),
        )

    def load_graph_to_tracegraph(
        self,
        tracegraph: Any,
        exclude_nodes: Optional[List[int]] = None,
    ) -> None:
        node_rows, rel_rows = self.database.get_graph_data_for_networkx(
            exclude_currency=False,
            exclude_secondary=False,
            exclude_nodes=exclude_nodes,
        )
        self.populate_tracegraph(tracegraph, node_rows, rel_rows)
        logger.info(
            "Loaded BioCyc graph projection: nodes=%s edges=%s",
            tracegraph.graph.number_of_nodes(),
            tracegraph.graph.number_of_edges(),
        )

    def get_node_data_for_excel(self, node_ids: List[int]):
        return self.database.get_node_data_for_excel(node_ids)
