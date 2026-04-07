import os

from lifelike_gds.network.inbetweenness_trace import InBetweennessTrace
from lifelike_gds.network.radiate_trace import RadiateTrace
from lifelike_gds.arango_network.reactome import *
from lifelike_gds.network.trace_graph_nx import TraceGraphNx
from lifelike_gds.network.trace_graph_utils import *

dbname = os.getenv('ARANGO_DATABASE', 'reactome-human')
db_version = 'reactome-human from 12152021 dump'
# database = ReactomeDB(dbname, uri, username, password)


UPDOWN_GENES = "updowngenes"
METABS = "metabs"

"""
LL-4139
Run Betweenness analysis from updown genes to metabs.
Compare betweenness data with pagerank (intersection).

Since betweenness used subgraph of shortest paths. Run pageranks using the same subgraph to compare.  Then compare pageranks 
using the whole graph (whole database)
"""


class UpdownGeneMetabTrace(RadiateTrace, InBetweennessTrace):
    def __init__(self, dbname, uri, username, password, input_dir='./eno/input', output_dir='./eno/output'):
        self.graphsource = Reactome(ReactomeDB(dbname, uri, username, password))
        TraceGraphNx.__init__(self, self.graphsource, False)
        self.source_nodes = self.get_updown_genes(input_dir=input_dir)
        self.target_nodes = self.get_metabs(input_dir=input_dir)
        self.datadir = output_dir
        self.init_graph()

    def init_graph(self):
        self.init_default_graph()
        # self.graphsource.database.add_shortest_paths_nodes_rels_to_nx(self.graph, self.source_nodes, self.target_nodes,
        #                                                               rels=REACTOME_TRACE_RELS,
        #                                                               exclude_nodes=self.graphsource.database.get_currency_nodes())
        self.set_node_set_from_arango_nodes(self.source_nodes, UPDOWN_GENES, "up and down endo genes")
        self.set_node_set_from_arango_nodes(self.target_nodes, METABS, 'endo metabolites')

    def get_updown_genes(self, input_dir='./eno/input'):
        infile = f"updown.tsv"
        query = """
        FOR n IN reactome
            FILTER "ReferenceEntity" in n.labels && n.databaseName = "NCBI Gene" && n.identifier in @genes
            FOR r IN INBOUND n IN referenceGene
                FILTER "ReferenceEntity" in r.labels
                FOR phys IN INBOUND r IN referenceEntity
                    FILTER "PhysicalEntity" in phys.labels
                    RETURN {phys: phys}
        """
        df = pd.read_csv(os.path.join(input_dir, infile), header=None, dtype='str')
        gene_ids = [n for n in df[0]]
        nodes = self.graphsource.database.get_raw_value(query, genes=gene_ids)
        print(f"{len(df)} gene_ids, matched to {len(nodes)} proteins")
        return nodes

    def get_metabs(self, input_dir='./eno/input'):
        infile = f"metabolite.txt"
        query = """
        FOR r IN reactome 
            FILTER "ReferenceEntity" in r.labels && r.databaseName == 'ChEBI' && r.identifier in @metabs
            FOR n IN INBOUND r referenceEntity
                FILTER "PhysicalEntity" in n.labels
                RETURN n
        """
        df = pd.read_csv(os.path.join(input_dir, infile), dtype='str')
        print(len(df))
        chebi_ids = [n for n in df['chebi']]
        nodes = self.graphsource.database.get_raw_value(query, metabs=chebi_ids)
        print(f"{len(df)} chebi_ids, matched to {len(nodes)} chemicals")
        return nodes

    def write_pagerank_betweenness_compare_data_to_excel(self, output_dir='./eno/output', num_nodes=2000):
        self.compute_inbetweenness(UPDOWN_GENES, METABS)
        self.set_pagerank_and_numreach(UPDOWN_GENES, 'forward')
        self.set_pagerank_and_numreach(METABS, 'reverse')
        pagerank_name = RadiateTrace.get_pagerank_prop_name(UPDOWN_GENES)
        rev_pagerank_name = RadiateTrace.get_rev_pagerank_prop_name(METABS)
        set_intersection_pagerank(self.graph, pagerank_name, rev_pagerank_name)
        filename = f"{UPDOWN_GENES}_to_{METABS}_pagerank_betweenness_data_compare.xlsx"
        # exclude starting and ending nodes.
        # exludes_nodes = self.graph.node_set(UPDOWN_GENES) | self.graph.node_set(METABS)
        # excludes = [n for n in exludes_nodes]
        all_nodes = set()

        forward_nodes = self.get_most_weighted_nodes(self.get_pagerank_prop_name(UPDOWN_GENES), num_nodes)
        back_nodes = self.get_most_weighted_nodes(self.get_rev_pagerank_prop_name(METABS), num_nodes)
        between_nodes = self.get_most_weighted_nodes(self.get_betweenness_prop_name(UPDOWN_GENES, METABS), num_nodes)
        inter_nodes = self.get_least_weighted_nodes(self.get_intersection_rank_prop_name(UPDOWN_GENES, METABS),
                                                    num_nodes)
        all_nodes.update(forward_nodes)
        all_nodes.update(back_nodes)
        all_nodes.update(between_nodes)
        all_nodes.update(inter_nodes)

        df = self.get_nodes_detail_as_dataframe(all_nodes)
        filepath = os.path.join(output_dir, filename)
        logging.info(f"export top {num_nodes} pagerank betweenness compare data into {filepath}")
        df.to_excel(filepath)

    def betweenness_traces(self):
        stIds = ['R-HSA-5652172', 'R-ALL-29926', 'R-HSA-381226']
        # stIds = ['R-HSA-5652172']
        selected_nodes = self.graphsource.database.get_nodes_by_attr(stIds, 'stId', 'db_Reactome')
        print(len(selected_nodes))
        self.compute_inbetweenness(UPDOWN_GENES, METABS)
        self.export_inbetweenness_data(UPDOWN_GENES, METABS, f"{UPDOWN_GENES}-{METABS}-betweenness_rel.xlsx")
        self.add_inbetweenness_trace_networks_with_selected_nodes(selected_nodes, UPDOWN_GENES, METABS,
                                                                  include_allshortest_path=False)
        self.write_to_sankey_file(f"{UPDOWN_GENES}_to_{METABS}_selected_nodes_betweenness_traces_rel.graph")


if __name__ == '__main__':
    job = UpdownGeneMetabTrace('reactome-human')
    # job.betweenness_traces()
    job.write_pagerank_betweenness_compare_data_to_excel()
