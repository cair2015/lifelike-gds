from lifelike_gds.network.radiate_trace import *
from lifelike_gds.arango_network.reactome_db import *

GROUP_A = ["Survivor"]
GROUP_D = ["Non-Survivor"]
GROUP_DA = ["NonServivor_over_Survivor"]
SOURCES = "plasma_metabs"


class MetabsFoldChangeAbsAnalysis(object):
    """
    Personalized page rank analysis using folder change absolute values as starting values.
    Compare pageranks for GroupA and D using different weight values
    D - Non-Survivor
    A - Survivor
    """

    def __init__(self, dbname, input_dir='./eot/input', output_dir='./eot/output'):
        self.graphsource = Reactome(ReactomeDB(dbname))
        self.tracegraph = RadiateTrace(self.graphsource)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.tracegraph.datadir = self.output_dir
        self.group_a_values = {}
        self.group_d_values = {}
        self.group_da_values = {}
        self.init_graph()

    def read_metabs_data(self):
        """
        Formate data, print dataframe to excel file
        Returns: dataframe with FC data
        """
        file = f"{self.input_dir}/plasma_metab_FC.xlsx"
        df1 = pd.read_excel(file, sheet_name="name-match", usecols=["name", "stId", "compartment_select"])
        df1 = df1[df1["compartment_select"] == 1]
        df1["lower_name"] = df1['name'].str.lower()
        df2 = pd.read_excel(
            file,
            sheet_name="Sheet1",
            usecols=["Metabolite name", "A-FC-ABS", "D-FC-ABS", "D/A-FC-ABS"]
        )
        df2["lower_name"] = df2["Metabolite name"].str.lower()
        df = pd.merge(df1, df2, on='lower_name', how='outer')
        print(len(df), len(df1), len(df2))
        df.to_excel(f"{self.output_dir}/plasma_metab_FC_match.xlsx", index=False)
        df = df.dropna()
        print(len(df))
        return df

    def init_graph(self):
        """
        initial trace graph, set source node set, and get source node weight values
        Returns:
        """
        self.graphsource.initiate_trace_graph(self.tracegraph)
        df_data = self.read_metabs_data()
        stIds = [n for n in df_data['stId']]
        query = """
            FOR n IN reactome
                FILTER "PhysicalEntity" in n.labels && n.stId in @stIds
                RETURN {
                    id: TO_NUMBER(n._key),
                    stId: n.stId
                }
        """
        df_ids = self.graphsource.database.get_dataframe(query, stIds=stIds)
        ids = [id for id in df_ids['id']]
        df = pd.merge(df_ids, df_data, on='stId')
        print(len(df))
        self.group_a_values = {row['id']: row['A-FC-ABS'] for index, row in df.iterrows()}
        self.group_d_values = {row['id']: row['D-FC-ABS'] for index, row in df.iterrows()}
        self.group_da_values = {row['id']: row['D/A-FC-ABS'] for index, row in df.iterrows()}
        self.tracegraph.set_node_set(
            SOURCES,
            ids,
            name=SOURCES,
            description='plasma metabs with rna-seq changes between survivor and non-survior groups'
        )

    def export_pagerank_values(self):
        """
        Export pagerank based on different source node weight
        Returns:
        """
        self.tracegraph.graph = self.tracegraph.orig_graph.copy()
        self.tracegraph.export_pagerank_data(SOURCES, f"{SOURCES}_pageranks_with_Survivor_rnaseq_FC_vals.xlsx",
                                             sources_personalization=self.group_a_values, num_nodes=5000)
        self.tracegraph.graph = self.tracegraph.orig_graph.copy()
        self.tracegraph.export_pagerank_data(SOURCES, f"{SOURCES}_pageranks_with_NonSurvivor_rnaseq_FC_vals.xlsx",
                                             sources_personalization=self.group_d_values, num_nodes=5000)
        self.tracegraph.graph = self.tracegraph.orig_graph.copy()
        self.tracegraph.export_pagerank_data(
            SOURCES,
            f"{SOURCES}_pageranks_with_NonServivor_over_Survivor_rnaseq_FC_vals.xlsx",
            sources_personalization=self.group_da_values,
            num_nodes=5000
        )


if __name__ == "__main__":
    task = MetabsFoldChangeAbsAnalysis('reactome-human')
    task.export_pagerank_values()
