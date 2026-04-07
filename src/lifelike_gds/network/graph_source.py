"""
Abstract graph source interface for database operations.

This module defines the GraphSource abstract base class that provides a common interface
for database operations needed by trace graph analysis. Specific implementations for
ArangoDB, Neo4j, and other databases inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING

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

    @abstractmethod
    def retrieve_node_properties(self, graph: Any) -> None:
        """
        Retrieve and set node properties from database.
        
        Args:
            graph: NetworkX graph object to update
        """
        pass

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
        exclude_nodes: Optional[List[int]] = None,
    ) -> None:
        """
        Load full graph data to trace graph.
        
        Args:
            tracegraph: TraceGraphNx instance to populate
            exclude_nodes: Optional nodes to exclude from loading
        """
        pass

    @abstractmethod
    def get_node_data_for_excel(self, node_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Retrieve node data for Excel export.
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            List of node data dictionaries formatted for export
        """
        pass
