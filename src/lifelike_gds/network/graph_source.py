"""Abstract graph-source interface and shared helpers for trace analysis."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

import pandas as pd

from lifelike_gds.utils import get_id

if TYPE_CHECKING:
    from lifelike_gds.network.trace_graph_nx import TraceGraphNx
    from lifelike_gds.network.graph_utils import DirectedGraph


class GraphSource(ABC):
    """
    Abstract base class for graph data source operations.
    
    This class defines the interface that database-specific implementations must provide.
    It acts as a bridge between database operations and trace graph analysis.
    
    Subclasses must implement the abstract methods to work with their specific database.
    """

    def __init__(self, database: Any, node_label_prop: str = "displayName") -> None:
        """
        Initialize graph source.
        
        Args:
            database: Database instance implementing database operations
            node_label_prop: Property name to use for node labels/display names
        """
        self.database = database
        self.node_label_prop = node_label_prop

    @classmethod
    def get_node_id(cls, node: Any) -> Any:
        """Return the backend-specific node identifier used in projected graphs."""
        return get_id(node)

    @staticmethod
    def unwrap_node_record(record: Any) -> Dict[str, Any]:
        """Normalize database query results to a plain node-property dictionary."""
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
        """Populate a projected NetworkX graph from node/edge query results."""
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
        """
        Extract node name/display name from node record.
        
        Args:
            node: Node record from database
            
        Returns:
            Node display name if available, None otherwise
        """
        pass

    @classmethod
    @abstractmethod
    def get_node_desc(cls, node: Dict[str, Any]) -> Optional[str]:
        """
        Extract node description from node record.
        
        Args:
            node: Node record from database
            
        Returns:
            Node description if available, None otherwise
        """
        pass

    @abstractmethod
    def set_nodes_description(self, nodes: List[Dict[str, Any]], graph: Any) -> None:
        """
        Set node descriptions in graph from database records.
        
        Args:
            nodes: List of node records from database
            graph: NetworkX graph object to update
        """
        pass

    @abstractmethod
    def set_edges_description(self, edges: List[Dict[str, Any]], graph: Any) -> None:
        """
        Set edge descriptions in graph from database records.
        
        Args:
            edges: List of edge records from database
            graph: NetworkX graph object to update
        """
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
        """
        Set description for a specific edge.
        
        Args:
            graph: NetworkX graph object
            start_node: Source node ID
            end_node: Target node ID
            edge_type: Type of relationship/edge
            key: Optional edge key for MultiDiGraph
        """
        pass

    def retrieve_node_properties(self, graph: Any) -> None:
        """Backward-compatible alias for loading projected-node details."""
        self.load_node_details(list(graph.nodes), graph)

    @abstractmethod
    def initiate_trace_graph(
        self,
        tracegraph: "TraceGraphNx",
        exclude_currency: bool = True,
        exclude_secondary: bool = True,
    ) -> None:
        """
        Initialize trace graph with data from database.
        
        Args:
            tracegraph: TraceGraphNx instance to populate
            exclude_currency: Whether to exclude currency metabolites
            exclude_secondary: Whether to exclude secondary metabolites
        """
        pass

    @abstractmethod
    def load_graph_to_tracegraph(
        self,
        tracegraph: "TraceGraphNx",
        exclude_nodes: Optional[List[Any]] = None,
    ) -> None:
        """
        Load full graph data to trace graph.
        
        Args:
            tracegraph: TraceGraphNx instance to populate
            exclude_nodes: Optional nodes to exclude from loading
        """
        pass

    @abstractmethod
    def get_node_data_for_excel(self, node_ids: List[Any]) -> List[Dict[str, Any]]:
        """
        Retrieve node data for Excel export.
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            List of node data dictionaries formatted for export
        """
        pass

    def load_node_details(self, node_ids: List[Any], graph: Any) -> None:
        """Load node attributes into an existing projected graph."""
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
        """Populate edge descriptions using already-loaded node metadata."""
        if graph.is_multigraph():
            edges: Iterable[Any] = graph.edges(keys=True, data=True)
        else:
            edges = graph.edges(data=True)

        for edge in edges:
            if graph.is_multigraph():
                source, target, key, data = edge
            else:
                source, target, data = edge
                key = None

            edge_type = data.get("label") or data.get("type")
            if not edge_type:
                continue

            start_node = graph.nodes[source]
            end_node = graph.nodes[target]
            self.set_edge_description(graph, start_node, end_node, edge_type, key=key)

    def get_node_data_for_export(self, node_ids: List[Any], graph: Any) -> pd.DataFrame:
        """Return a merged export frame containing DB and graph-derived properties."""
        df = self._as_dataframe(self.get_node_data_for_excel(node_ids))
        if df.empty:
            df = pd.DataFrame(index=node_ids)
        elif "id" in df.columns:
            df = df.set_index("id", drop=False)

        if graph is None:
            return df

        graph_rows = []
        for node_id in node_ids:
            if node_id in graph:
                row = {"id": node_id}
                row.update(dict(graph.nodes[node_id]))
                graph_rows.append(row)

        if not graph_rows:
            return df

        graph_df = pd.DataFrame(graph_rows).drop_duplicates(subset="id").set_index("id", drop=False)
        if df.empty:
            return graph_df

        merged = df.combine_first(graph_df)
        for column in graph_df.columns:
            merged[column] = graph_df[column].combine_first(merged[column])
        return merged
