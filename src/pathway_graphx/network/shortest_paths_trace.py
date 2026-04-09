"""Shortest path trace analysis for network graphs.

This module provides shortest path finding and analysis functionality,
identifying the most direct paths between node sets in a graph. The
implementation is database-agnostic and delegates graph loading to a
``GraphSource`` implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TypeAlias

from pathway_graphx.network.trace_graph_nx import TraceGraphNx
from pathway_graphx.network.trace_utils import add_trace_network

logger = logging.getLogger(__name__)

NodeSetRef: TypeAlias = str


class ShortestPathTrace(TraceGraphNx):
    """Run shortest-path-based trace analysis on a projected graph.

    The class creates one or more trace-network entries on ``self.graph`` by
    connecting source and target node sets with shortest paths. It supports
    plain shortest paths today and exposes placeholders for k-shortest,
    all-shortest, and weighted variants.
    """

    def __init__(self, graphsource: Any, multigraph: bool = True) -> None:
        """Initialize the shortest-path tracer.

        Args:
            graphsource: Graph source that can populate and enrich the NetworkX
                projection used by this tracer.
            multigraph: Whether to back the tracer with ``nx.MultiDiGraph``.
        """
        super().__init__(graphsource, directed=True, multigraph=multigraph)

    def add_shortest_paths(
        self,
        sources: NodeSetRef,
        targets: NodeSetRef,
        sources_as_query: bool = True,
        shortest_paths_plus_n: int = 0,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """Add one or more shortest-path trace networks.

        Args:
            sources: Source node-set key.
            targets: Target node-set key.
            sources_as_query: Whether the source set should be recorded as the
                query set on the created trace network.
            shortest_paths_plus_n: Also include paths up to ``n`` edges longer
                than the strict shortest path length.
            name: Optional custom network name. When ``shortest_paths_plus_n``
                is greater than zero and ``name`` is provided, the same name is
                reused for each iteration.
            description: Optional custom network description.

        Returns:
            ``True`` when at least one path was added across all iterations,
            otherwise ``False``.
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        query = sources if sources_as_query else targets
        has_paths = False

        for n in range(shortest_paths_plus_n + 1):
            plus_n_str = f"+{n}" if n > 0 else ""
            network_name = (
                name
                or f"Shortest{plus_n_str} paths from {source_name} to {target_name}"
            )

            try:
                _network_idx, num_paths = add_trace_network(
                    self.graph,
                    sources,
                    targets,
                    name=network_name,
                    description=description,
                    query=query,
                    shortest_paths_plus_n=n,
                )
            except Exception:
                logger.exception(
                    "Failed to add shortest paths for '%s' -> '%s' at +%s",
                    source_name,
                    target_name,
                    n,
                )
                continue

            if num_paths > 0:
                has_paths = True
                self.add_graph_description(f"{network_name}: {num_paths} paths")
                logger.info("Added %s: %s paths", network_name, num_paths)
            else:
                logger.info("No paths found for %s", network_name)

        return has_paths

    def add_k_shortest_paths(
        self,
        sources: NodeSetRef,
        targets: NodeSetRef,
        k: int = 1,
        name: Optional[str] = None,
    ) -> bool:
        """Add a k-shortest-path trace network.

        Note:
            The current implementation falls back to ``add_shortest_paths`` and
            therefore does **not** yet honor ``k``.

        Args:
            sources: Source node-set key.
            targets: Target node-set key.
            k: Requested number of shortest paths per source/target pair.
            name: Optional custom network name.

        Returns:
            ``True`` if at least one path was added, otherwise ``False``.
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        network_name = (
            name or f"K-shortest paths (k={k}) from {source_name} to {target_name}"
        )

        if k != 1:
            logger.warning(
                "k=%s requested for %s, but only single shortest paths are currently implemented.",
                k,
                network_name,
            )

        try:
            return self.add_shortest_paths(sources, targets, name=network_name)
        except Exception:
            logger.exception("Failed to add k-shortest paths for %s", network_name)
            return False

    def add_all_shortest_paths(
        self,
        sources: NodeSetRef,
        targets: NodeSetRef,
        max_length: Optional[int] = None,
        name: Optional[str] = None,
    ) -> bool:
        """Add an all-shortest-path trace network.

        Note:
            ``max_length`` is currently accepted for API compatibility but is
            not yet applied.

        Args:
            sources: Source node-set key.
            targets: Target node-set key.
            max_length: Optional maximum path length filter.
            name: Optional custom network name.

        Returns:
            ``True`` if at least one path was added, otherwise ``False``.
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        network_name = name or f"All shortest paths from {source_name} to {target_name}"

        if max_length is not None:
            logger.warning(
                "max_length=%s was provided for %s, but it is not currently enforced.",
                max_length,
                network_name,
            )

        try:
            return self.add_shortest_paths(sources, targets, name=network_name)
        except Exception:
            logger.exception("Failed to add all shortest paths for %s", network_name)
            return False

    def add_weighted_shortest_paths(
        self,
        sources: NodeSetRef,
        targets: NodeSetRef,
        weight_property: str,
        name: Optional[str] = None,
    ) -> bool:
        """Add a weighted shortest-path trace network.

        Note:
            ``weight_property`` is currently accepted for API compatibility but
            is not yet applied when computing paths.

        Args:
            sources: Source node-set key.
            targets: Target node-set key.
            weight_property: Edge-property name to use as a path weight.
            name: Optional custom network name.

        Returns:
            ``True`` if at least one path was added, otherwise ``False``.
        """
        source_name = self._get_node_set_name(sources)
        target_name = self._get_node_set_name(targets)
        network_name = (
            name or f"Weighted shortest paths from {source_name} to {target_name}"
        )

        logger.warning(
            "weight_property='%s' was requested for %s, but weighted shortest paths are not currently implemented.",
            weight_property,
            network_name,
        )

        try:
            return self.add_shortest_paths(sources, targets, name=network_name)
        except Exception:
            logger.exception(
                "Failed to add weighted shortest paths for %s", network_name
            )
            return False

    def _get_node_set_name(self, node_set_key: NodeSetRef) -> str:
        """Return a display name for a node set."""
        try:
            if hasattr(self.graph, "get_node_set_name"):
                return self.graph.get_node_set_name(node_set_key)
        except Exception:
            logger.debug(
                "Graph backend does not expose get_node_set_name", exc_info=True
            )

        try:
            node_sets = self.graph.graph.get("node_sets", {})
            if node_set_key in node_sets:
                return node_sets[node_set_key].get("name", node_set_key)
        except Exception:
            logger.debug("Unable to read node_sets metadata from graph", exc_info=True)

        return node_set_key


class InteractionPathTrace(ShortestPathTrace):
    """Specialized shortest-path tracer for interaction-path analysis."""

    def __init__(self, graphsource: Any, multigraph: bool = True) -> None:
        """Initialize the interaction-path tracer."""
        super().__init__(graphsource, multigraph=multigraph)
