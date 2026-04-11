"""Neo4j-native shortest-path tracing without NetworkX."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, TypeAlias

from lifelike_gds.graph_sources.neo4j_utils import Neo4jQueryBuilder
from lifelike_gds.utils import get_id

logger = logging.getLogger(__name__)

NodeSetRef: TypeAlias = str


@dataclass(slots=True)
class NodeSet:
    """A named set of database node ids with optional display metadata."""

    key: str
    nodes: set[str] = field(default_factory=set)
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass(slots=True)
class TraceRecord:
    """One source-target trace made of one or more shortest paths."""

    source: str
    target: str
    node_paths: List[List[str]]
    relationships: List[List[Dict[str, Any]]]


@dataclass(slots=True)
class TraceNetworkRecord:
    """Metadata and collected traces for a shortest-path query."""

    name: str
    sources: str
    targets: str
    query: str
    method: str
    description: Optional[str] = None
    traces: List[TraceRecord] = field(default_factory=list)


class ShortestPathTrace:
    """Run shortest-path traces directly in Neo4j."""

    def __init__(self, graphsource: Any) -> None:
        self.graphsource = graphsource
        self.database = graphsource.database
        self.node_sets: Dict[str, NodeSet] = {}
        self.trace_networks: List[TraceNetworkRecord] = []
        self.graph_description: List[str] = []

    def set_node_set(self, key: str, nodes: set[str], **meta: Any) -> None:
        """Register a named node set."""
        normalized = {str(node_id) for node_id in nodes}
        self.node_sets[key] = NodeSet(
            key=key,
            nodes=normalized,
            name=meta.get("name"),
            description=meta.get("description"),
        )

    def set_node_set_from_db_nodes(self, nodes: List[Any], name: str, desc: str) -> None:
        """Register a named node set from resolved Neo4j node records."""
        node_ids = {str(get_id(node)) for node in nodes}
        self.set_node_set(name, node_ids, name=name, description=desc)

    def add_graph_description(self, desc: str) -> None:
        """Append free-form graph metadata."""
        self.graph_description.append(desc)

    def get_node_set_name(self, key: str) -> str:
        """Return the display name for a node set when available."""
        node_set = self.node_sets.get(key)
        if node_set and node_set.name:
            return node_set.name
        return key

    def add_shortest_paths(
        self,
        sources: NodeSetRef,
        targets: NodeSetRef,
        sources_as_query: bool = True,
        shortest_paths_plus_n: int = 0,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Fetch shortest paths between two named node sets from Neo4j."""
        if shortest_paths_plus_n != 0:
            raise NotImplementedError(
                "Neo4j-native shortest_paths_plus_n is not implemented yet."
            )

        source_ids = self._require_node_set(sources)
        target_ids = self._require_node_set(targets)

        network_name = name or (
            f"Shortest paths from {self.get_node_set_name(sources)} "
            f"to {self.get_node_set_name(targets)}"
        )
        query_key = sources if sources_as_query else targets
        trace_network = TraceNetworkRecord(
            name=network_name,
            sources=sources,
            targets=targets,
            query=query_key,
            method="min(length)",
            description=description,
        )

        traces = self._get_all_shortest_path_records(source_ids, target_ids)
        trace_network.traces.extend(traces)

        if trace_network.traces:
            self.trace_networks.append(trace_network)
            self.add_graph_description(f"{network_name}: {len(trace_network.traces)} traces")
            logger.info("Added %s with %s source-target trace groups", network_name, len(trace_network.traces))
            return True

        logger.info("No shortest paths found for %s", network_name)
        return False

    def add_all_shortest_paths(
        self,
        sources: NodeSetRef,
        targets: NodeSetRef,
        max_length: Optional[int] = None,
        name: Optional[str] = None,
    ) -> bool:
        """Alias for shortest paths, since this implementation already returns all shortest paths."""
        if max_length is not None:
            logger.warning("max_length=%s is not currently enforced.", max_length)
        return self.add_shortest_paths(sources, targets, name=name)

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-JSON-friendly representation of the collected traces."""
        return {
            "node_sets": {
                key: {
                    "nodes": sorted(node_set.nodes),
                    "name": node_set.name,
                    "description": node_set.description,
                }
                for key, node_set in self.node_sets.items()
            },
            "graph_description": list(self.graph_description),
            "trace_networks": [self._trace_network_to_dict(network) for network in self.trace_networks],
        }

    def _require_node_set(self, key: str) -> List[str]:
        node_set = self.node_sets.get(key)
        if node_set is None:
            raise KeyError(f"Unknown node set {key!r}")
        if not node_set.nodes:
            raise ValueError(f"Node set {key!r} is empty")
        return sorted(node_set.nodes)

    def _get_all_shortest_path_records(
        self,
        source_ids: List[str],
        target_ids: List[str],
    ) -> List[TraceRecord]:
        query, params = Neo4jQueryBuilder.get_all_shortest_paths(
            source_ids=source_ids,
            target_ids=target_ids,
            relationship_types=self._get_relationship_types(),
        )
        paths = self.database.run_query(query, **params)

        grouped: Dict[tuple[str, str], TraceRecord] = {}
        for row in paths:
            path = row.get("p")
            if path is None:
                continue

            node_path = [str(get_id(node)) for node in path.nodes]
            relationship_path = [
                {
                    "id": str(rel.element_id),
                    "source": str(get_id(rel.start_node)),
                    "target": str(get_id(rel.end_node)),
                    "type": rel.type,
                }
                for rel in path.relationships
            ]
            trace_key = (node_path[0], node_path[-1])
            trace = grouped.setdefault(
                trace_key,
                TraceRecord(
                    source=node_path[0],
                    target=node_path[-1],
                    node_paths=[],
                    relationships=[],
                ),
            )
            trace.node_paths.append(node_path)
            trace.relationships.append(relationship_path)

        return list(grouped.values())

    def _get_relationship_types(self) -> Optional[List[str]]:
        relationship_types = getattr(self.database, "TRACE_RELATIONSHIP_TYPES", None)
        if relationship_types is None:
            return None
        return list(relationship_types)

    @staticmethod
    def _trace_network_to_dict(network: TraceNetworkRecord) -> Dict[str, Any]:
        network_dict = asdict(network)
        network_dict["traces"] = [asdict(trace) for trace in network.traces]
        return network_dict
