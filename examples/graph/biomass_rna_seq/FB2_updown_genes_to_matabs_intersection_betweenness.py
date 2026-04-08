import os

from lifelike_gds.arango_network.biocyc_db import *
from lifelike_gds.network.inbetweenness_trace import *
from lifelike_gds.network.radiate_trace import *
from lifelike_gds.network.trace_graph_utils import *

"""
sources: Feedbatch 2 imodulon genes with RNA-seq fold changes from early to later (26-34 hrs) timepoints. 
Use the absolute fold-change values and log2 fold-change values.
targets: biomass precursor metabs

perform intersection pageranks (source personalized with starting values, target no tarting values)

"""
UPDOWN_GENES = 'FB2Updowns'
METABS = "BiomassMetabs"


class FB2UpdownGenesToBiomassMetabs(RadiateTrace, InBetweennessTrace):
    def __init__(self, dbname, exclude_currency=True):
        self.database = BiocycDB(dbname)
        TraceGraphNx.__init__(self, Biocyc(self.database))
        self.gene_nodes, self.fc_values, self.log2_values = self.get_updown_genes_with_vals()
        self.metab_nodes = self.get_biomass_metabs()
        self.datadir = output_dir
        self.init_graph(exclude_currency)

    def init_graph(self, exclude_currency):
        self.init_default_graph(exclude_currency)
        self.set_node_set_from_arango_nodes(self.gene_nodes, UPDOWN_GENES,
                                            "rnaseq up and down changed genes with cut-off log2 > 1")
        self.set_node_set_from_arango_nodes(self.metab_nodes, METABS, "Biomass precursor metabolites")

    def get_updown_genes_with_vals(self, file="./metal_biomass/input/updown_genes_FC_log2of1cutoff.xlsx"):
        df = pd.read_excel(file, usecols=['biocyc_id', 'FC', 'log2'])
        # print(df.head())
        # find database node for genes and node id (arango_id)
        nodes = self.database.get_nodes_by_attr([id for id in df['biocyc_id']], 'biocyc_id', 'db_BioCyc')
        df_nodes = pd.DataFrame(dict(
            biocyc_id={n.id: n.get('biocyc_id') for n in nodes}
        ))
        df_nodes.index.name = 'id'
        df_nodes.reset_index(inplace=True)
        # merge with data in input file
        df = df_nodes.merge(df, on='biocyc_id')
        # print(df.head())
        # print(len(df), len(df_nodes))
        fc_vals = {}
        log2_vals = {}
        for index, row in df.iterrows():
            fc_vals[row['id']] = row['FC']
            log2_vals[row['id']] = row['log2']
        return nodes, fc_vals, log2_vals

    def get_biomass_metabs(self):
        file = f"{input_dir}/metals_biomassPrecursors_hector.xlsx"
        df = pd.read_excel(file, sheet_name="Sheet2")
        ids = [id for id in df['biocyc_id']]
        nodes = self.database.get_nodes_by_attr(ids, 'biocyc_id', 'db_BioCyc')
        return nodes

    def write_pagerank_betweenness_compare_data_to_excel(self, outfile, num_nodes=3000, source_start_val=None,
                                                         exclude_sourcetarget_nodes_from_outputfile=False):
        """
        Compoute pageranks, intersection pageranks and betweenness values, and write the computed data into excel file
        Args:
            outfile:
            num_nodes: number of top ranked nodes (for each calculated properties) to export
            source_start_val:  dict for the sources (for forward pagerank) and targets for reverse pagerank) wegiths
            exclude_sourcetarget_nodes_from_outputfile: if True, exclude the source and target nodes from exported file
        Returns:
        """
        if source_start_val is None:
            source_start_val = {}
        self.graph = self.orig_graph.copy()
        self.compute_inbetweenness(UPDOWN_GENES, METABS, sources_weight=source_start_val)
        self.set_pagerank_and_numreach(UPDOWN_GENES, 'forward', source_start_val)
        self.set_pagerank_and_numreach(METABS, 'reverse')
        set_intersection_pagerank(self.graph, UPDOWN_GENES, METABS)

        exclude_nodes = []
        if exclude_sourcetarget_nodes_from_outputfile:
            # exclude starting and ending nodes from the highest ranked nodes file, optional
            exclude_nodes = self.graph.node_set(UPDOWN_GENES) | self.graph.node_set(METABS)

        forward_nodes = self.get_most_weighted_nodes(self.get_pagerank_prop_name(UPDOWN_GENES), num_nodes,
                                                     exclude_nodes=exclude_nodes)
        back_nodes = self.get_most_weighted_nodes(self.get_rev_pagerank_prop_name(METABS), num_nodes,
                                                  exclude_nodes=exclude_nodes)
        between_nodes = self.get_most_weighted_nodes(self.get_betweenness_prop_name(UPDOWN_GENES, METABS), num_nodes,
                                                     exclude_nodes=exclude_nodes)
        inter_nodes = self.get_least_weighted_nodes(self.get_intersection_rank_prop_name(UPDOWN_GENES, METABS),
                                                    num_nodes, exclude_nodes=exclude_nodes)
        all_nodes = set()
        all_nodes.update(forward_nodes)
        all_nodes.update(back_nodes)
        all_nodes.update(between_nodes)
        all_nodes.update(inter_nodes)

        df = self.get_nodes_detail_as_dataframe(all_nodes)
        filepath = f"{self.datadir}/{outfile}"
        logging.info(f"export top {num_nodes} pagerank betweenness compare data into {filepath}")
        df.to_excel(filepath)

    def write_pagerank_inbetweenness_file(self, outfile, num_nodes=3000, inbetweenness=True):
        """
        Compute pageranks/inbetweenness using different weights.
        Args:
            outfile:
            num_nodes: number of top nodes to export
            inbetweenness: if True, also calculate and export inbetweeness values
        Returns:
        """
        self.graph = self.orig_graph.copy()
        pr = 'PR'  # no weight
        pr_fc = 'PR_FC'  # use Fold-change as weight
        pr_log2 = 'PR_Log2'  # use log2(fold-change) as weight
        rev_pr = 'PR_rev'
        inter_pr = 'inter_PR'
        inter_fc = 'inter_FC'
        inter_log2 = 'inter_log2'

        btw = 'inbtw'
        btw_pr = 'inbtw_PR'
        btw_fc = 'inbtw_PR_FC'
        btw_log2 = 'inbtw_PR_Log2'

        add_pagerank(self.graph, UPDOWN_GENES, pagerank_prop=pr, contribution=False)
        add_pagerank(self.graph, UPDOWN_GENES, personalization=self.fc_values, pagerank_prop=pr_fc,
                     contribution=False)
        add_pagerank(self.graph, UPDOWN_GENES, personalization=self.log2_values, pagerank_prop=pr_log2,
                     contribution=False)
        add_pagerank(self.graph, METABS, pagerank_prop=rev_pr, reverse=True)
        set_intersection_pagerank(self.graph, pr, rev_pr, inter_pr)
        set_intersection_pagerank(self.graph, pr_fc, rev_pr, inter_fc)
        set_intersection_pagerank(self.graph, pr_log2, rev_pr, inter_log2)

        if inbetweenness:
            self.compute_inbetweenness(UPDOWN_GENES, METABS, btw)
            self.compute_inbetweenness(UPDOWN_GENES, METABS, btw_pr, pr)
            self.compute_inbetweenness(UPDOWN_GENES, METABS, btw_fc, pr_fc)
            self.compute_inbetweenness(UPDOWN_GENES, METABS, btw_log2, pr_log2)
        # set source and target nodes property
        status_props = {n: 'source' for n in self.graph.node_set(UPDOWN_GENES)}
        status_props.update({n: 'target' for n in self.graph.node_set(METABS)})
        nx.set_node_attributes(self.graph, status_props, 'status')
        nodes = set()
        if inbetweenness:
            nodes = set([n for n, d in self.graph.nodes(data=True) if
                         (btw in d) or (btw_pr in d) or (btw_fc in d) or (btw_log2 in d)])
        inter_nodes = [n for n, d in self.graph.nodes(data=True) if (d[rev_pr] > 0) and (d[pr] > 0)]
        nodes.update(self.get_most_weighted_nodes(inter_pr, num_nodes, include_nodes=inter_nodes))
        nodes.update(self.get_most_weighted_nodes(inter_fc, num_nodes, include_nodes=inter_nodes))
        nodes.update(self.get_most_weighted_nodes(inter_log2, num_nodes, include_nodes=inter_nodes))
        print(len(nodes))
        df = self.get_nodes_detail_as_dataframe(nodes)
        df.to_excel(os.path.join(self.datadir, outfile), index=False)

    def write_betweenness_file(self, outfile):
        """
        Calculate pagerank and weighted pageranks for the sources, calculate pagerank for targets. Then compute inbetweenness
        using weighted and unweighted edges.  The values were exported to file
        Args:
            outfile:
        Returns:
        """
        pr = 'PR'
        pr_fc = 'PR_FC'
        pr_log2 = 'PR_Log2'
        rev_pr = 'PR_rev'  # for target

        btw = 'inbtw'
        btw_pr = 'inbtw_PR'  # inbetweenness based on pagerank
        btw_fc = 'inbtw_PR_FC'  # inbetweenness based on pagerank with fold-change
        btw_log2 = 'inbtw_PR_Log2'  # inbetweenness based on pagerank with log2(fold-change)

        add_pagerank(self.graph, UPDOWN_GENES, pagerank_prop=pr, contribution=False)
        add_pagerank(self.graph, UPDOWN_GENES, personalization=self.fc_values, pagerank_prop=pr_fc,
                     contribution=False)
        add_pagerank(self.graph, UPDOWN_GENES, personalization=self.log2_values, pagerank_prop=pr_log2,
                     contribution=False)
        add_pagerank(self.graph, METABS, pagerank_prop=rev_pr, reverse=True)

        self.compute_inbetweenness(UPDOWN_GENES, METABS, btw)
        self.compute_inbetweenness(UPDOWN_GENES, METABS, btw_pr, pr)
        self.compute_inbetweenness(UPDOWN_GENES, METABS, btw_fc, pr_fc)
        self.compute_inbetweenness(UPDOWN_GENES, METABS, btw_log2, pr_log2)

        # set source and target nodes property
        status_props = {n: 'source' for n in self.graph.node_set(UPDOWN_GENES)}
        status_props.update({n: 'target' for n in self.graph.node_set(METABS)})
        nx.set_node_attributes(self.graph, status_props, 'status')
        nodes = set([n for n, d in self.graph.nodes(data=True) if
                     (btw in d) or (btw_pr in d) or (btw_fc in d) or (btw_log2 in d)])
        print(len(nodes))
        df = self.get_nodes_detail_as_dataframe(nodes)
        df.to_excel(os.path.join(self.datadir, outfile), index=False)

    def write_single_path_traces(self):
        selected = ['CPD-15318', 'CPD-546', 'FRU1P']
        nodes = self.graphsource.database.get_nodes_by_attr(selected, 'biocyc_id', 'db_BioCyc')
        selected_set_name = 'selected_compounds'
        self.set_node_set_from_arango_nodes(nodes, selected_set_name,
                                            'compounds cannot be found for intersection analysis')
        self.add_single_shortest_path(UPDOWN_GENES, selected_set_name)
        self.add_single_shortest_path(selected_set_name, METABS)
        self.write_to_sankey_file('crash_missed_compounds_traces.graph')

    def write_traces_with_selected_inter_nodes(self, node_eids: [], name, desc):
        selected_nodes = self.graphsource.database.get_nodes_by_attr(node_eids, 'eid', 'db_BioCyc')
        pr = 'PR'
        rev_pr = 'PR_rev'
        add_pagerank(self.graph, UPDOWN_GENES, pagerank_prop=pr, contribution=True)
        add_pagerank(self.graph, METABS, pagerank_prop=rev_pr, reverse=True, contribution=True)
        self.set_node_set_from_arango_nodes(selected_nodes, name, desc)
        self.add_traces_from_sources_to_each_selected_nodes(selected_nodes, UPDOWN_GENES, pr, name)
        if len(selected_nodes) > 1:
            self.add_trace_from_sources_to_all_selected_nodes(name, UPDOWN_GENES, pr, f"Forward {name}")
        self.add_traces_from_each_selected_nodes_to_targets(selected_nodes, METABS, rev_pr, name)
        if len(selected_nodes) > 1:
            self.add_trace_from_all_selected_nodes_to_targets(name, METABS, rev_pr, f"Reverse {name}")

        filename = f'Trace_Crash_{UPDOWN_GENES}_{METABS}_with_{name}.graph'
        self.graph.describe(desc)
        self.graph.describe(f"Traces from {UPDOWN_GENES} to {name} and from {name} to {METABS}")
        self.write_to_sankey_file(filename)


def write_pagerank_file():
    """
    export weighted pagerank data with top 3000 nodes, exclude secondary metabolites from analysis.
    Intersection-rank values were calculated using formulus p1*p2/(p1+p2-(p1*p2))
    Returns: a file with weighted pageranks and intersection rank values using different weights (no weight, FC-wight, log2(FC)-weight).
    I used the ecocyc-gds-mod2 datgabase for the original analysis.
    """
    num_nodes = 3000
    trace = FB2UpdownGenesToBiomassMetabs('ecocyc-25.5-gds', True)
    # filename = f"{UPDOWN_GENES}_to_{METABS}_pagerank_betweenness_{num_nodes}.xlsx"
    filename = f"Crash_UpdownGenes_biomassMetags_pagerank_exclude_sec_{num_nodes}.xlsx"
    trace.write_pagerank_inbetweenness_file(filename, num_nodes, False)


def write_inbetweenness_file():
    """
    Calculate inbetweenness using different edge weights.  The default one inbtw did not use weight
    Returns:
    """
    trace = FB2UpdownGenesToBiomassMetabs('ecocyc-25.5-gds', True)
    filename = f"Crash_{UPDOWN_GENES}_{METABS}_inbetweenness.xlsx"
    trace.write_betweenness_file(filename)


def write_traces_with_ZnMn():
    selected_ids = ['ZN+2', 'MN+2']
    name = 'Zn-Mn'
    desc = 'Top ranked metals Zn2+ and Mn2+ by unweighted pagerank intersection analysis'
    trace = FB2UpdownGenesToBiomassMetabs('ecocyc-25.5-gds', True)
    trace.write_traces_with_selected_inter_nodes(selected_ids, name, desc)


def write_traces_with_top_betweenness_rxn():
    selected_ids = ['L-GLN-FRUCT-6-P-AMINOTRANS-RXN_r']
    name = "GLN-FRUCT-6P-AMINOTRANS-RXN"
    desc = "Top ranked nodes from in-betweenness analysis"
    trace = FB2UpdownGenesToBiomassMetabs('ecocyc-25.5-gds', True)
    trace.write_traces_with_selected_inter_nodes(selected_ids, name, desc)


if __name__ == "__main__":
    # write_pagerank_file()
    # write_inbetweenness_file
    # write_traces_with_ZnMn()
    write_traces_with_top_betweenness_rxn()
