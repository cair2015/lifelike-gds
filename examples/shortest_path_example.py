from lifelike_gds.network.shortest_paths_trace import ShortestPathTrace
from lifelike_gds.network.graph_source import GraphSource
from lifelike_gds.graph_sources.domain_config import REACTOME_TRACE_NODE_LABEL
from lifelike_gds.graph_sources.reactome_db import ReactomeDB
from lifelike_gds.graph_sources.reactome import Reactome
from lifelike_gds.network.shortest_paths_trace import ShortestPathTrace

from pathlib import Path
import pandas as pd
import os, dotenv

dotenv.load_dotenv()
curr_path = Path(__file__).parent.resolve()
data_dir = curr_path.parent / "data"

output_dir = data_dir/ "output"
os.makedirs(output_dir, exist_ok=True)

source_name = 'metabolites'
source_stIds = ['R-ALL-1247892', 'R-ALL-198836', 'R-ALL-2395761', 'R-ALL-444200', 'R-ALL-2173764', 'R-ALL-30158', 'R-ALL-429590']

target_name = 'HIF1A'
target_stId = 'R-HSA-1234131'

database = ReactomeDB(uri=os.getenv("NEO4J_URI"),
                      username=os.getenv("NEO4J_USERNAME"),
                      password=os.getenv("NEO4J_PASSWORD"),
                      database=os.getenv("NEO4J_DATABASE"))

reactome = Reactome(database=database)

source_nodes = database.get_nodes_by_attr(
    attr_values=source_stIds,
    attr_name='stId',
    node_label=reactome.node_label
)
target_nodes = database.get_nodes_by_attr(
    attr_values=[target_stId],
    attr_name='stId',
    node_label=reactome.node_label
)

print(f"Found {len(source_nodes)} source nodes and {len(target_nodes)} target nodes.")

tracegraph = ShortestPathTrace(reactome)
tracegraph.set_datadir(output_dir)

tracegraph.init_default_graph()
tracegraph.write_shortest_paths(source_name=source_name, source_nodes=source_nodes, 
                                target_name=target_name, target_nodes=target_nodes, 
                                graph_description="Reactome") 
