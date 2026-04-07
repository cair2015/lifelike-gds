import pandas as pd
from typing import List

from lifelike_gds.arango_network.database import Database, GraphSource
from lifelike_gds.network.trace_graph_nx import TraceGraphNx
import logging
import networkx as nx

from lifelike_gds.network.graph_utils import DirectedGraph
from lifelike_gds.utils import get_id

CURRENCY_METABOLITES = [
    'NAD-P-OR-NOP', 'NADH-P-OR-NOP', 'Donor-H2', 'Acceptor', 'HYDROGEN-PEROXIDE', 'OXYGEN-MOLECULE',
    'NAD', 'NADP', 'NADH', 'NADPH', 'WATER', 'CARBON-DIOXIDE', 'FAD', 'CO-A', 'UDP', 'AMMONIA', 'NA+',
    'AMMONIUM', 'PROTON', 'CARBON-MONOXIDE', 'GTP', 'ADP', 'GDP', 'AMP', 'ATP', '3-5-ADP', 'PPI', 'Pi'
]

CURRENCY_LABEL = 'CurrencyMetabolite'

EDGE_DESC_DICT = {
    'ELEMENT_OF': 'is element of',
    'ENCODES': 'encodes',
    'MODIFIED_TO': 'is modified to',
    'COMPONENT_OF': 'is component of',
    'CONSUMED_BY': 'is consumed by',
    'PRODUCES': 'produces',
    'IN_PATHWAY': 'is in',
    'CATALYZES': 'catalyzes',
    'REGULATES': 'regulates',
    'HAS_GENE': 'contains',
    'ACTIVATES': 'activates',
    'INHIBITS': 'inhibits'
}


class BiocycDB(Database):
    def __init__(self, dbname, uri=None, username=None, password=None):
        super().__init__('biocyc', dbname, uri, username, password)

    def get_nodes_by_attr(self, attr_values: List[str], attr_name, node_label='db_BioCyc'):
        return super().get_nodes_by_attr(attr_values, attr_name, node_label)

    def get_graph_data_for_networkx(self, exclude_currency=True, exclude_secondary=True):
        match_stmt = f"""
            FOR n in biocyc
                {f'FILTER "{CURRENCY_LABEL}" NOT IN n.labels' if exclude_currency else ''}
                FOR m, r IN OUTBOUND n GRAPH "all"
                    {f'FILTER "{CURRENCY_LABEL}" NOT IN m.labels' if exclude_currency else ''}
                    {'FILTER r.SECONDARY = undefined' if exclude_secondary else ''}
        """
        query_node = match_stmt + """
                    FOR node in [n, m]
                        RETURN { node_id:  TO_NUMBER(node._key) }
        """
        query_rel = match_stmt + """
                    RETURN {
                        source: TO_NUMBER(n._key),
                        target: TO_NUMBER(m._key),
                        rel: r.label
                    }
        """
        return self.get_dataframe(query_node), self.get_dataframe(query_rel)


class Biocyc(GraphSource):
    def __init__(self, database: BiocycDB):
        super().__init__(database)

    @classmethod
    def get_node_name(cls, node):
        name = node.get('name')
        if not name:
            name = node.get('displayName')
        return name

    @classmethod
    def get_node_desc(cls, node):
        return f"{node.get('entityType')} {node.get('displayName')}"

    @classmethod
    def set_edge_description(cls, D, startNode, endNode, edgeType, key=None):
        source_display_name = f"{startNode.get('entityType')}({startNode.get('displayName')})"
        target_display_name = f"{endNode.get('entityType')}({endNode.get('displayName')})"
        nlg = f"{source_display_name} | {edgeType} | {target_display_name}"
        desc = f"RELATIONSHIP: {edgeType}\n{nlg}"
        if key is None:
            e = (get_id(startNode), get_id(endNode))
        else:
            e = (get_id(startNode), get_id(endNode), key)
        D.edges[e]['description'] = desc

    def set_nodes_description(self, arango_nodes, D):
        for n in arango_nodes:
            lines = [f"NODE: {n.get('entityType')}"]
            lines.extend(n.get('synonyms', []))
            detail = n.get('detail', '')
            if detail:
                lines.append('')
                lines.append('DETAIL:')
                lines.append(detail)
            D.nodes[get_id(n)]['description'] = '\n'.join(lines)

    def set_edges_description(self, arango_edges, D: DirectedGraph):
        for edge in arango_edges:
            self.add_edge_description(edge.start_node, edge.end_node, edge.type, D)

    def initiate_trace_graph(self, tracegraph:TraceGraphNx, exclude_currency=True, exclude_secondary=True):
        node_query = f"""
            FOR n in biocyc
                {f'FILTER "{CURRENCY_LABEL}" NOT IN n.labels' if exclude_currency else ''}
        """ + """
                RETURN { node_id: TO_NUMBER(n._key) }
        """
        rel_query = f"""
            FOR n in biocyc
                {f'FILTER "{CURRENCY_LABEL}" NOT IN n.labels' if exclude_currency else ''}
                FOR m, r IN OUTBOUND n GRAPH "all"
                    {f'FILTER "{CURRENCY_LABEL}" NOT IN m.labels' if exclude_currency else ''}
                    {'FILTER r.SECONDARY == null' if exclude_secondary else ''}
        """ + """
                    RETURN { 
                        source: TO_NUMBER(n._key),
                        target: TO_NUMBER(m._key),
                        type: r.label
                    }
        """
        tracegraph.add_nodes(node_query)
        tracegraph.add_rels(rel_query)
        graph_info = f"Graph: nodes={tracegraph.graph.number_of_nodes()}, edges={tracegraph.graph.number_of_edges()}"
        logging.info(graph_info)
        return tracegraph

    def load_graph_to_tracegraph(self, tracegraph, exclude_ndoes: List = None):
        if exclude_ndoes:
            exclude_ids = [get_id(n) for n in exclude_ndoes]
        else:
            exclude_ids = []
        node_query = f"""
            FOR n in biocyc
                {f'FILTER TO_NUMBER(n._key) NOT IN @exclude_ids' if exclude_ids else ''}
        """ + """
                RETURN { node_id: TO_NUMBER(n._key) }
        """
        rel_query = f"""
            FOR n in biocyc
                {f'FILTER TO_NUMBER(n._key) NOT IN @exclude_ids' if exclude_ids else ''}
                FOR m, r IN OUTBOUND n GRAPH "all"
                    {f'FILTER TO_NUMBER(m._key) NOT IN @exclude_ids' if exclude_ids else ''}
        """ + """
                    RETURN { 
                        source: TO_NUMBER(n._key),
                        target: TO_NUMBER(m._key),
                        type: r.label
                    }
        """
        tracegraph.add_nodes(node_query, exclude_ids=exclude_ids)
        tracegraph.add_rels(rel_query, exclude_ids=exclude_ids)
        graph_info = f"Graph: nodes={tracegraph.graph.number_of_nodes()}, edges={tracegraph.graph.number_of_edges()}"
        logging.info(graph_info)
        return tracegraph

    def get_node_data_for_excel(self, node_ids:List[str]):
        query = """
            FOR n IN biocyc
                FILTER TO_NUMBER(n._key) IN @nids
                    let lbls = (for l in n.labels filter ! starts_with(l, 'db_') return l)
                    RETURN {
                        id: TO_NUMBER(n._key),
                        eid: n.eid,
                        displayName: n.displayName,
                        description: n.detail,
                        entityType: n.entityType,
                        labels: lbls
                    }
            """
        df = self.database.get_dataframe(query, nids=node_ids)

        # get reaction genes, protein genes and compound pathways
        query = """
            LET nodes = (
                FOR n IN biocyc
                    FILTER TO_NUMBER(n._key) IN @nids
                    RETURN n
            )
            FOR r in union(
                (
                    FOR n IN nodes
                        FILTER 'Reaction' IN n.labels
                        FOR a IN INBOUND n catalyzes
                            FOR b in 0..5 INBOUND a component_of
                                FOR g IN INBOUND b encodes
                                    FILTER "Gene" IN g.labels
                                    COLLECT id = TO_NUMBER(n._key) INTO enrichment = g.name
                        RETURN {"id": id, "enrichment": enrichment}
                ),
                (
                    FOR n IN nodes
                        FILTER 'Protein' IN n.labels
                            FOR b IN 0..5 INBOUND n component_of
                                FOR g IN INBOUND b encodes
                                    FILTER "Gene" IN g.labels
                                    COLLECT id = TO_NUMBER(n._key) INTO enrichment = g.name
                        RETURN {"id": id, "enrichment": enrichment}
                ),
                (
                    FOR n IN nodes
                        FILTER 'Compound' IN n.labels
                            FOR r IN ANY n graph "all"
                                FILTER "Reaction" IN r.labels
                                FOR p IN ANY r graph "all"
                                    FILTER "Pathway" IN p.labels
                                    COLLECT id = TO_NUMBER(n._key) INTO enrichment = p.name
                        RETURN {"id": id, "enrichment": enrichment}
                )   
            )
                RETURN r
        """
        df_enrich = self.database.get_dataframe(query, nids=node_ids)
        df = pd.merge(df, df_enrich, on='id', how='left')
        return df

