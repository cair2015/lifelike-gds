import os
import dotenv
from pathlib import Path

from lifelike_gds.arango_network.reactome import *
from lifelike_gds.network.shortest_paths_trace import ShortestPathTrace
from lifelike_gds.utils import get_project_root


"""
Create shortest paths traces from endo in-chemical to out-chemical, by selecting different cluster group (1-5).
Compare paths by excluding different chemicals from the traces, e.g. H+, H2O, or all secondary metabs
"""

dotenv.load_dotenv()  # Load environment variables from .env file

db_version = 'reactome-human from 12152021 dump'
database = ReactomeDB()

# get data folder path
OUTPUT_DIR = get_project_root() / 'data' / 'output'

SOURCE_NODE_NAME = 'p-STAT3'
TARGET_NODE_NAME = 'IL6'

def create_tracegraph(exclude, output_dir='./eot/output'):
    reactome = Reactome(database)
    tracegraph = ShortestPathTrace(reactome)

    graphdesc = 'Projected graph '
    if not exclude:
        print('no exclude')
        tracegraph.init_default_graph(exclude_currency=False)
        graphdesc += 'contains all chemicals'
    elif exclude == 'ALL':
        print("exclude ", exclude)
        tracegraph.init_default_graph()
        graphdesc += 'has all secondary metabolites removed'
    else:
        print("exclude ", exclude)
        exclude_nodes = database.get_nodes_by_attr(exclude, 'name')
        reactome.custome_init_trace_graph(tracegraph, exclude_nodes)
        graphdesc += f'has the following chemicals removed: {exclude}'
    tracegraph.datadir = output_dir
    tracegraph.add_graph_description(db_version)
    tracegraph.add_graph_description(graphdesc)
    return tracegraph


def get_graph_name(cluster_num, exclude):
    graphName = f"{SOURCE_NODE_NAME}-{TARGET_NODE_NAME}-shortest-paths"
    return graphName


def write_inout_shortest_paths_sankey(tracegraph:ShortestPathTrace, inout_paris, cluster_num, exclude):
    tracegraph.graph = tracegraph.orig_graph.copy()
    sources = database.get_nodes_by_attr(SOURCE_NODE_NAME, 'name')
    targets = database.get_nodes_by_attr(TARGET_NODE_NAME, 'name')

    for s in sources:
        for t in targets:
            tracegraph.add_shortest_paths(s.id, t.id)
    tracegraph.add_shortest_paths(source[0].id, target[0].id)
    sources = []
    targets = []
    for id1, id2 in inout_paris:
        source = database.get_nodes_by_attr([id1], 'stId')
        target = database.get_nodes_by_attr([id2], 'stId')
        if source and target:
            source_name = tracegraph.set_node_set_for_node(source[0])
            target_name = tracegraph.set_node_set_for_node(target[0])
            tracegraph.add_shortest_paths(source_name, target_name)
        sources += source
        targets += target
    ingroup = f"eot_cluster{cluster_num}_in"
    outgroup = f"eot_cluster{cluster_num}_out"
    tracegraph.set_node_set_from_db_nodes(sources, ingroup, ingroup)
    tracegraph.set_node_set_from_db_nodes(targets, outgroup, outgroup)
    tracegraph.add_shortest_paths(ingroup, outgroup)

    outfileName = f"{get_graph_name(cluster_num, exclude)}.graph"
    tracegraph.write_to_sankey_file(OUTPUT_DIR / outfileName)


def generate_eot_cluster_inout_shortest_paths_sankey(cluster_nums: list, exclude='ALL'):
    infile = INPUT_DIR / FILE_NAME
    df = pd.read_excel(infile, usecols=['Cluster', 'IN stId', 'OUT stId'])
    df = df.dropna()
    tracegraph = create_tracegraph(exclude)
    for cluster_num in cluster_nums:
        df_c = df[df['Cluster'] == cluster_num]
        cluster_pairs = [(row['IN stId'], row['OUT stId']) for index, row in df_c.iterrows()]
        write_inout_shortest_paths_sankey(tracegraph, cluster_pairs, cluster_num, exclude)


if __name__ == '__main__':
    print(DATA_DIR)
    generate_eot_cluster_inout_shortest_paths_sankey([2, 4])
