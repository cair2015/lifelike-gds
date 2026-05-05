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

def _export_radiate_analysis(
    tracegraph: TraceGraphNx,
    source_name: str,
    source_decription: str,
    source_nodes: list,
    exclude_sources_from_file=False,
    rows_export=1000,
):
    tracegraph.graph = tracegraph.orig_graph.copy()
    tracegraph.set_node_set_from_arango_nodes(
        source_nodes, source_name, source_decription
    )
    outfile_name = f"Radiate_analysis_for_{source_name}.xlsx"
    tracegraph.export_pagerank_data(
        source_name,
        outfile_name,
        direction='both',
        num_nodes=rows_export,
        exclude_sources=exclude_sources_from_file,
    )

def _get_database() -> ReactomeDB:
    return ReactomeDB(uri=os.getenv("NEO4J_URI"),
                      username=os.getenv("NEO4J_USERNAME"),
                      password=os.getenv("NEO4J_PASSWORD"),
                      database=os.getenv("NEO4J_DATABASE"))


def radiate_analysis_with_stids():

    stIds = ['R-ALL-1247892', 'R-ALL-198836', 'R-ALL-2395761', 'R-ALL-444200', 'R-ALL-2173764', 'R-ALL-30158', 'R-ALL-429590', 'R-ALL-352014', 'R-HSA-70968']
    source_name = "diagnosis-metabolites"
    source_description = "Metabolites associated with diagnosis of some disease"
    
    database = _get_database()

    # Get source nodes
    source_nodes = database.get_nodes_by_attr(
        attr_values=stIds,
        attr_name='stId',
        node_label=REACTOME_TRACE_NODE_LABEL,
    )
    print(f"Found {len(source_nodes)} source nodes.")

    # Initialize TraceGraph and RadiateTrace
    tracegraph = RadiateTrace(Reactome(database))
    tracegraph.datadir = output_dir
    tracegraph.init_default_graph()

    # Export radiate analysis
    _export_radiate_analysis(
        tracegraph=tracegraph,
        source_name=source_name,
        source_decription=source_description,
        source_nodes=source_nodes,
        exclude_sources_from_file=False,
        rows_export=1000,
    )

def radiate_analysis_with_reference_entity_nodes():
    referance_database_name = 'UniProt'
    reference_ids = ['P31749']
    source_name = "AKT1"
    source_description = "AKT1 protein reference entity nodes in Reactome"
    
    database = _get_database()
    graphsource = Reactome(database)
    # Get source nodes
    source_nodes = database.get_reference_entity_nodes(
        ref_databasename=referance_database_name,
        ref_identifiers=reference_ids,
        node_label=graphsource.get_node_query_label()
    )

    print(f"Found {len(source_nodes)} source nodes with get_reference_entity_nodes method.")

    # Initialize TraceGraph and RadiateTrace
    tracegraph = RadiateTrace(graphsource)
    tracegraph.datadir = output_dir
    tracegraph.init_default_graph()

    graphsource.add_reference_entity_relationships(source_nodes, tracegraph)

    # Export radiate analysis
    _export_radiate_analysis(
        tracegraph=tracegraph,
        source_name=source_name,
        source_decription=source_description,
        source_nodes=source_nodes,
        exclude_sources_from_file=False,
        rows_export=1000,
    )

def radiate_analysis_with_protein():
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

    print(f"Found {len(source_nodes)} source nodes with get_entity_nodes_by_reference_entities method.")

    # Initialize TraceGraph and RadiateTrace
    tracegraph = RadiateTrace(graphsource)
    tracegraph.datadir = output_dir
    tracegraph.init_default_graph()

    # Export radiate analysis
    _export_radiate_analysis(
        tracegraph=tracegraph,
        source_name=source_name,
        source_decription=source_description,
        source_nodes=source_nodes,
        exclude_sources_from_file=False,
        rows_export=1000,
    )



if __name__ == "__main__":
    radiate_analysis_with_protein()
