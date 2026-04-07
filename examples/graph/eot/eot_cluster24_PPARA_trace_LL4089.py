import os

from lifelike_gds.network.radiate_trace import RadiateTrace
from lifelike_gds.arango_network.reactome import *

"""
get the shortest paths and highest influence paths from "PPARKA:RXRA Coactivator complex" to cluster2 cluster 4 in and out metabolites. 
The highest influence paths will be calculated based on personalized rev pageranks with cluster2,4 chemicals.

trace output folder: https://staging.lifelike.bio/projects/GDS-Results/folders/02oW0MmJGGARE4s8S9vQDH
"""

uri = os.getenv('ARANGO_URI', 'bolt://localhost:7687')
username = os.getenv('ARANGO_USER', 'arango')
password = os.getenv('ARANGO_PASSWORD', 'rcai')
dbname = os.getenv('ARANGO_DATABASE', 'reactome-human')
db_version = 'reactome-human from 12152021 dump'
database = ReactomeDB(dbname, uri, username, password)

source_name = "cluster24_chemicals"
source_desc = "EoT cluster2,4 in and out chemicals"
source_file = "endo_match_inout_chems.xlsx"


def get_source_nodes(input_dir='./eot/input'):
    infile = os.path.join(input_dir, source_file)
    df = pd.read_excel(infile, usecols=['Cluster', 'IN stId', 'OUT stId'])
    df = df[(df['Cluster'] == 2) | (df['Cluster'] == 4)]
    chem_ids = [id for id in df["IN stId"].dropna()] + [id for id in df["OUT stId"].dropna()]
    nodes = database.get_nodes_by_attr(list(chem_ids), 'stId', 'PhysicalEntity')
    return nodes


def get_selected_nodes():
    displayName = "PPARA:RXRA Coactivator complex [nucleoplasm]"
    selected_nodes = database.get_nodes_by_attr([displayName], 'displayName')
    return selected_nodes


def write_traces_from_PPARA_RXRA_Complex_to_inout_chemicals(output_dir='./eot/output'):
    tracegraph = RadiateTrace(Reactome(database))
    tracegraph.datadir = output_dir
    tracegraph.init_default_graph()
    # set rev_pageranks for inout chemicals
    source_nodes = get_source_nodes()
    tracegraph.set_node_set_from_arango_nodes(source_nodes, source_name, source_desc)
    rev_pagerank_prop = 'rev_pagerank'
    tracegraph.set_pagerank(source_name, rev_pagerank_prop, reverse=True)

    # add graph description
    tracegraph.add_graph_description(f'Database: {db_version}\n')
    selected_nodes = get_selected_nodes()
    # there is only one node in the selected_nodes
    selected_node_set = tracegraph.set_node_set_for_node(selected_nodes[0])
    tracegraph.add_traces_from_each_selected_nodes_to_targets(selected_nodes, source_name, rev_pagerank_prop)
    tracegraph.write_to_sankey_file(f"PPARA-RXRA-complex_to_EoT_cluster24_chemicals.graph")


# main method call
write_traces_from_PPARA_RXRA_Complex_to_inout_chemicals()
