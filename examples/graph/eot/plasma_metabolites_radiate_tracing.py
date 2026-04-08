from lifelike_gds.network.radiate_trace import *
from lifelike_gds.arango_network.reactome_db import *

NODE_SETS = ['Survivor and Non-Survivor', 'Survivor', 'Non-Survivor']
"""
The analysis manually added chemical reference entities into the projected graph, and performed pagerank 
analysis and traces using reference entity as starting nodes instead of physical entity
"""


class PlasmaMetabolitesRadiateTracing:
    def __init__(self, dbname, output_dir='./eot/output'):
        database = ReactomeDB(dbname)
        self.graphsource = Reactome(database)
        self.tracegraph = RadiateTrace(self.graphsource)
        self.graphsource.initiate_trace_graph(self.tracegraph)
        self.tracegraph.set_datadir(output_dir)

    def _get_plasma_metabolite_reference_entities(self, group, input_dir='./eot/input'):
        """
        Each metabolite (ref_id) could match to multiple reactome entities. Trying to use reference entities as
        analysis sources
        @param group: Survior, Non-Survivor, or None.  If None, return all
        return a dict for chemical->nodes
        """
        file = "PlasmaMetabolites_name_match.xlsx"
        df = pd.read_excel(os.path.join(input_dir, file))
        if group:
            df = df[['ref_id', group]].dropna()
            ref_ids = [id for id in df['ref_id'].drop_duplicates()]
        else:
            ref_ids = [id for id in df['ref_id'].dropna().drop_duplicates()]
            group = 'All'
            df = df['ref_id'].dropna()
        print(group, "nodes:", len(df), "ref_ids:", len(ref_ids))
        return ref_ids

    def add_group_nodes(self, group, reverse_reference, input_dir='./eot/input'):
        """
        Add reference entities into the projected graph. If the reference entities are for sources,
        the relationship 'referenceEntity' need to be reversed to 'hasEntity'
        Args:
            input_dir:
            group: survival groups, key for list of reference ids
            reverse_reference: If true, reverse 'referenceEntity' direction, and change edge type to 'hasEntity'
        Returns:
        """
        # add metabolite reference entities
        node_query2 = """
            FOR n IN reactome
                FILTER "ReferenceEntity" in n.labels && n.dbId in @ref_ids
                RETURN { node_id: TO_NUMBER(n._key) }
        """
        if reverse_reference:
            node_rel2 = """
                FOR n IN reactome 
                    FILTER "ReferenceEntity" in n.labels && n.dbId in @ref_ids
                    FOR m,r IN INBOUND n referenceEntity
                        RETURN {
                            source: TO_NUMBER(n._key),
                            target: TO_NUMBER(m._key),
                            type: 'hasEntity'
                        }
            """
        else:
            node_rel2 = """
                FOR n IN reactome
                    FILTER "ReferenceEntity" in n.labels && n.dbId in @ref_ids
                    FOR m,r IN INBOUND n referenceEntity
                        RETURN {
                            source: TO_NUMBER(m._key),
                            target: TO_NUMBER(n._key),
                            type: 'referenceEntity'
                        }
            """
        ref_ids = self._get_plasma_metabolite_reference_entities(group, input_dir=input_dir)
        self.tracegraph.add_nodes(node_query2, ref_ids=ref_ids)
        self.tracegraph.add_rels(node_rel2, ref_ids=ref_ids)
        graph_info = f"Graph: nodes={self.tracegraph.graph.number_of_nodes()}, edges={self.tracegraph.graph.number_of_edges()}"
        logging.info(graph_info)
        desc = f"most changed metabolites in {group} group"
        nodes = self.graphsource.database.get_nodes_by_attr(ref_ids, 'dbId', 'ReferenceEntity')
        self.tracegraph.set_node_set_from_arango_nodes(nodes, group, desc)

    def write_radiate_trace_workflow(self, group="Non-Survivor", num_top_nodes=2, forward=True):
        """
        Automatically select the top ranked nodes, and create radiate traces graph file
        Args:
            group:  Survior or Non-Survivor group
            num_top_nodes: number of top nodes for traces
            forward: if True, run pagerank then create traces from source to selected nodes.
                Otherwise, run reverse pagerank, then create traces from selected nodes to source nodes.
        Returns:
        """
        self.tracegraph.graph = self.tracegraph.orig_graph.copy()
        self.add_group_nodes(group, forward)
        if forward:
            effect = "influencing"
            direction = "forward"
            weight_prop = RadiateTrace.get_pagerank_prop_name(group)
        else:
            effect = "influenced"
            direction = "reverse"
            weight_prop = RadiateTrace.get_rev_pagerank_prop_name(group)
        filename = f"Radiate_{group}_metabolites_{effect}_top{num_top_nodes}_pagerank.graph"
        self.tracegraph.set_pagerank_and_numreach(group, direction)

        excludes = self.tracegraph.graph.node_set(group)
        top_node_ids = self.tracegraph.get_most_weighted_nodes(weight_prop, num_top_nodes, exclude_nodes=excludes)
        top_nodes = self.tracegraph.graphsource.database.get_nodes_by_node_ids(top_node_ids)
        if forward:
            self.tracegraph.add_traces_from_sources_to_each_selected_nodes(top_nodes, group, weight_prop)
        else:
            self.tracegraph.add_traces_from_each_selected_nodes_to_targets(top_nodes, group, weight_prop)
        self.tracegraph.write_to_sankey_file(filename)

    def write_radiate_trace_to_selected_node(self, selected_stIds, group="Non-Survivor", forward=True):
        """
        given selected ids, create trace graph
        Args:
            selected_stIds: list of stIds
            group: Survior or Non-Survivor
            forward: if true, create traces from sources to selected nodes.
            Otherwise, create traces from selected nodes to sources
        Returns:
        """
        self.tracegraph.graph = self.tracegraph.orig_graph.copy()
        self.add_group_nodes(group, forward)
        if forward:
            effect = "to"
            direction = "forward"
        else:
            effect = "from"
            direction = "reverse"
        filename = f"Radiate_{group}_metabolites_{effect}_reaction2046101.graph"
        self.tracegraph.set_pagerank_and_numreach(group, direction)
        nodes = self.graphsource.database.get_nodes_by_attr(['R-HSA-2046101'], 'stId', 'Event')
        if forward:
            self.tracegraph.add_traces_from_sources_to_each_selected_nodes(nodes, group)
        else:
            self.tracegraph.add_traces_from_each_selected_nodes_to_targets(nodes, group)
        self.tracegraph.write_to_sankey_file(filename)

    def write_best_n_radiate_workflow(self):
        groups = ["Non-Survivor", "Survivor"]
        for group in groups:
            # self.write_radiate_trace_workflow(group, 1, True, True)
            # self.write_radiate_trace_workflow(group, 1, False, True)
            self.write_radiate_trace_workflow(group, 5, True)
            self.write_radiate_trace_workflow(group, 5, False)
            # self.write_radiate_trace_workflow(group, 10, True)
            # self.write_radiate_trace_workflow(group, 10, False)


if __name__ == '__main__':
    task = PlasmaMetabolitesRadiateTracing('reactome-human')
    task.write_radiate_trace_to_selected_node(['R-HSA-2046101'], forward=False)
    # task.write_best_n_radiate_workflow()
