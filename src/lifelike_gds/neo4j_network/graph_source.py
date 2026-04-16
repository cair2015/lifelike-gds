"""Abstract graph-source interface and shared helpers for trace analysis."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

import pandas as pd

from lifelike_gds.utils import get_id

if TYPE_CHECKING:
    from lifelike_gds.network.graph_utils import DirectedGraph
    from lifelike_gds.neo4j_network.trace_graph_nx import TraceGraphNx


class GraphSource(ABC):
    """
    Abstract base class for graph data source operations.

    Database-specific backends should implement this interface so the trace
    graph layer can remain database-agnostic.
    """

    def __init__(self, database: Any, node_label_prop: str = "displayName") -> None:
        self.database = database
        self.node_label_prop = node_label_prop

    @classmethod
    def get_node_id(cls, node: Any) -> Any:
        return get_id(node)

    @staticmethod
    def unwrap_node_record(record: Any) -> Dict[str, Any]:
        if isinstance(record, dict):
            if "id" in record or "_key" in record:
                return record
            if len(record) == 1:
                value = next(iter(record.values()))
                if isinstance(value, dict):
                    return value
        return record

    @staticmethod
    def _as_dataframe(rows: Any) -> pd.DataFrame:
        if isinstance(rows, pd.DataFrame):
            return rows.copy()
        if rows is None:
            return pd.DataFrame()
        return pd.DataFrame(list(rows))

    def populate_tracegraph(
        self,
        tracegraph: "TraceGraphNx",
        node_rows: Any,
        rel_rows: Any,
    ) -> None:
        node_data = self._as_dataframe(node_rows)
        if not node_data.empty and "node_id" in node_data.columns:
            tracegraph.graph.add_nodes_from(node_id for node_id in node_data["node_id"])

        rel_data = self._as_dataframe(rel_rows)
        if not rel_data.empty:
            for _, row in rel_data.iterrows():
                tracegraph.graph.add_edge(
                    row["source"],
                    row["target"],
                    label=row["type"],
                )

    @classmethod
    @abstractmethod
    def get_node_name(cls, node: Dict[str, Any]) -> Optional[str]:
        pass

    @classmethod
    @abstractmethod
    def get_node_desc(cls, node: Dict[str, Any]) -> Optional[str]:
        pass

    @abstractmethod
    def set_nodes_description(self, nodes: List[Dict[str, Any]], graph: Any) -> None:
        pass

    @abstractmethod
    def set_edges_description(self, edges: List[Dict[str, Any]], graph: Any) -> None:
        pass

    @classmethod
    @abstractmethod
    def set_edge_description(
        cls,
        graph: Any,
        start_node: int,
        end_node: int,
        edge_type: str,
        key: Optional[str] = None,
    ) -> None:
        pass

    def retrieve_node_properties(self, graph: Any) -> None:
        self.load_node_details(list(graph.nodes), graph)

    @abstractmethod
    def initiate_trace_graph(
        self,
        **kwargs,
    ) -> None:
        pass

    @abstractmethod
    def load_graph_to_tracegraph(
        self,
        tracegraph: "TraceGraphNx",
        exclude_nodes: Optional[List[Any]] = None,
        exclude_node_labels: Optional[List[str]] = None,
    ) -> None:
        pass

    @abstractmethod
    def get_node_data_for_excel(self, node_ids: List[Any]) -> List[Dict[str, Any]]:
        pass

    def load_node_details(self, node_ids: List[Any], graph: Any) -> None:
        raw_nodes = self.database.get_nodes_by_node_ids(node_ids)
        nodes = [self.unwrap_node_record(node) for node in raw_nodes]
        valid_nodes = []

        for node in nodes:
            node_id = self.get_node_id(node)
            if node_id not in graph:
                continue
            graph.nodes[node_id].update(node)
            valid_nodes.append(node)

        if valid_nodes:
            self.set_nodes_description(valid_nodes, graph)

    def load_edge_details(self, graph: Any) -> None:
        if graph.is_multigraph():
            edge_refs: Iterable[Any] = list(graph.edges(keys=True))
        else:
            edge_refs = list(graph.edges)

        if not edge_refs:
            return

        source_ids = {edge[0] for edge in edge_refs}
        target_ids = {edge[1] for edge in edge_refs}
        node_lookup = {
            self.get_node_id(node): node
            for node in map(
                self.unwrap_node_record,
                self.database.get_nodes_by_node_ids(list(source_ids | target_ids)),
            )
        }

        edge_records = []
        for edge_ref in edge_refs:
            source_id, target_id = edge_ref[0], edge_ref[1]
            source_node = node_lookup.get(source_id)
            target_node = node_lookup.get(target_id)
            if not source_node or not target_node:
                continue
            edge_records.append(
                {
                    "start_node": source_node,
                    "end_node": target_node,
                    "type": graph.edges[edge_ref].get("label"),
                    "key": edge_ref[2] if len(edge_ref) > 2 else None,
                }
            )

        if edge_records:
            self.set_edges_description(edge_records, graph)

    def get_node_data_for_export(self, node_ids: List[Any], graph: Any):
        df = self.get_node_data_for_excel(node_ids)
        if isinstance(df, pd.DataFrame) and not df.empty and "id" in df.columns:
            df = df.set_index("id", drop=False)
            for node_id in node_ids:
                if node_id in graph.nodes and node_id in df.index:
                    for key, value in graph.nodes[node_id].items():
                        if key not in df.columns:
                            df[key] = None
                        df.at[node_id, key] = value
        return df