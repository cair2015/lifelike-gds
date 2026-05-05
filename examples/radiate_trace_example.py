from lifelike_gds.network.trace_graph_nx import TraceGraphNx
from lifelike_gds.graph_sources.domain_config import REACTOME_TRACE_NODE_LABEL
from lifelike_gds.graph_sources.reactome_db import ReactomeDB
from lifelike_gds.graph_sources.reactome import Reactome
from lifelike_gds.network.radiate_trace import RadiateTrace

from pathlib import Path
import pandas as pd
import os, dotenv

dotenv.load_dotenv()
curr_path = Path(__file__).parent.resolve()
data_dir = curr_path.parent / "data"

output_dir = data_dir/ "output"
os.makedirs(output_dir, exist_ok=True)

def _get_database() -> ReactomeDB:
    return ReactomeDB(uri=os.getenv("NEO4J_URI"),
                      username=os.getenv("NEO4J_USERNAME"),
                      password=os.getenv("NEO4J_PASSWORD"),
                      database=os.getenv("NEO4J_DATABASE"))

def export_radiate_traces(
    tracegraph,
    source_name,
    source_nodes,
    forward_nodes: list=None,
    reverse_nodes: list=None,
):
    """
    Export radiate traces for forward and reverse analysis.

    Args:
        tracegraph: TraceGraphNx instance to populate with traces.
        source_name: The data set name for radiate analysis.
        source_nodes: List of source nodes used for radiate analysis.
        forward_nodes: List of nodes selected based on forward pageranks.
        reverse_nodes: List of nodes selected based on reverse pageranks.
    """
    tracegraph.graph = tracegraph.orig_graph.copy()
    tracegraph.set_node_set_from_arango_nodes(
        source_nodes, source_name, source_name
    )

    # set pagerank or rev_pagerank property
    pagerank_prop = 'pagerank'
    rev_pagerank_prop = 'rev_pagerank'

    if forward_nodes:
        tracegraph.set_pagerank(source_name, pagerank_prop, False)

    if reverse_nodes:
        tracegraph.set_pagerank(source_name, rev_pagerank_prop, True)

    # add graph description
    tracegraph.add_graph_description('Reactome')

    # add forward traces
    if forward_nodes:
        nodeset_name = 'forward select'
        tracegraph.set_node_set_from_arango_nodes(
            forward_nodes, nodeset_name, nodeset_name
        )
            
        # add traces from sources to each selected nodes
        tracegraph.add_traces_from_sources_to_each_selected_nodes(
            forward_nodes,
            source_name,
            weighted_prop=pagerank_prop,
            selected_nodes_name=nodeset_name,
        )

        # add traces from sources to all selected nodes
        tracegraph.add_trace_from_sources_to_all_selected_nodes(
            nodeset_name,
            source_name,
            weighted_prop=pagerank_prop,
            trace_name=f'Forward combined selected nodes',
        )

    # add reverse traces
    if reverse_nodes:
        nodeset_name = 'reverse select'
        tracegraph.set_node_set_from_arango_nodes(
            reverse_nodes, nodeset_name, nodeset_name
        )

        # add traces from each selected nodes to SOURCE_SET genes
        tracegraph.add_traces_from_each_selected_nodes_to_targets(
            reverse_nodes,
            source_name,
            weighted_prop=rev_pagerank_prop,
            selected_nodes_name=nodeset_name,
        )

        # add traces from all reverse-selected nodes to SOURCE_SET
        tracegraph.add_trace_from_all_selected_nodes_to_targets(
            nodeset_name,
            source_name,
            weighted_prop=rev_pagerank_prop,
            trace_name=f"Reverse combined selected nodes",
        )


    # write all traces into one graph file
    graph_file = f'Radiate_traces_for_{source_name}.graph'
    tracegraph.write_to_sankey_file(graph_file)


def radiate_Trace_with_AKT1_proteins():
    referance_database_name = 'UniProt'
    reference_ids = ['P31749']
    source_name = "AKT1_Proteins"
    source_description = "AKT1 protein reference entity nodes in Reactome"
    
    database = _get_database()
    graphsource = Reactome(database)
    # Get source nodes
    source_nodes = database.get_entity_nodes_by_reference_entities(
        ref_databasename=referance_database_name,
        ref_identifiers=reference_ids,
        node_label=graphsource.get_node_query_label()
    )

    forward_target_stids = ['R-HSA-5674400', 'R-HSA-2219528', 'R-HSA-9856530']
    reverse_target_stids = ['R-ALL-1250243']
    forward_nodes = database.get_nodes_by_attr (
        attr_values=forward_target_stids,
        attr_name='stId',
        node_label=REACTOME_TRACE_NODE_LABEL,
    )
    reverse_nodes = database.get_nodes_by_attr (
        attr_values=reverse_target_stids,
        attr_name='stId',
        node_label=REACTOME_TRACE_NODE_LABEL,
    )
    print((f"Found {len(source_nodes)} source nodes, {len(forward_nodes)} forward nodes, and {len(reverse_nodes)} reverse nodes."))

    # Initialize TraceGraph and RadiateTrace
    tracegraph = RadiateTrace(graphsource)
    tracegraph.datadir = output_dir
    tracegraph.init_default_graph()

    export_radiate_traces(
        tracegraph=tracegraph,
        source_name=source_name,
        source_nodes=source_nodes,
        forward_nodes=forward_nodes,
        reverse_nodes=reverse_nodes,
    )


if __name__ == "__main__":
    radiate_Trace_with_AKT1_proteins()
