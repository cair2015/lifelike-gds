from lifelike_gds.arango_network.database import *
from lifelike_gds.arango_network.trace_graph_nx import TraceGraphNx
from lifelike_gds.network.graph_utils import DirectedGraph
import networkx as nx
import re
import logging

from lifelike_gds.utils import get_id

allowedNodeEntityTypes = ['Chemical', 'Protein', 'Entity', 'Reaction', 'Gene', 'Compound', 'Species', 'Study', 'Pathway', 'Phenotype', 'Anatomy',
     'Lab Strain', 'Note', 'Cause', 'Observation', 'Association', 'Effect', 'Correlation', 'Map', 'Link', 'Lab Sample', 'Food',
     'Phenomena', 'Company', 'Mutation']

# TRACE_RELS = ['activeUnitOf', 'candidateOf', 'catalystOf', 'catalyzes', 'componentOf', 'input', 'memberOf', 'output',
#         'referenceEntity', 'regulates', 'regulatorOf', 'repeatedUnitOf', 'requiredInput']
REACTOME_TRACE_RELS = [
    'activeUnitOf',
    'candidateOf',
    'catalystOf',
    'catalyzes',
    'componentOf',
    'input',
    'memberOf',
    'output',
    'regulates',
    'regulatorOf',
    'repeatedUnitOf',
    'requiredInput'
]
REACTOME_TRACE_RELS_WITH_REF = REACTOME_TRACE_RELS + ['referenceEntity']

SECONDARY_CHEMS = ["3',5'-ADP", 'ADP', 'AMP', 'ATP', 'CO', 'CO2', 'Ca2+', 'Cl-', 'CoA-SH', 'FAD', 'FADH2', 'GDP', 'GTP', 'H+', 'H2O', 'H2O2', 'HCO3-', 'K+', 'NAD(P)+', 'NAD(P)H', 'NAD+', 'NADH', 'NADP+', 'NADPH', 'NH3', 'NH4+', 'Na+', 'O2', 'O2.-', 'PAP', 'PPi', 'PPi(3-)', 'Pi', 'UDP', 'Ub', "adenosine 5'-monophosphate", 'phosphate']

SECONDARY_LABEL = 'SecondaryMetabolite'

TRACE_MEMORY_GRAPH_NAME = "traceNetwork"
TRACE_REVERSE_MEMORY_GRAPH_NAME = 'revTraceNetwork'


EDGE_DESC_DICT = {
            'activeUnitOf': 'is active unit of',
            'candidateOf': 'is candidate of',
            'catalystOf': 'is catalyst of',
            'catalyzes': 'catalyzes',
            'componentOf': 'is component of',
            'hasComponent': 'has component',
            'input': 'is consumed by',
            'memberOf': 'is member of',
            'output': 'produces',
            'referenceEntity': 'has reference entity',
            'regulates': 'regulates',
            'regulatorOf': 'is regulator of',
            'repeatedUnitOf': 'is repeated unit of',
            'requiredInput': 'is required input for'
        }


class ReactomeDB(Database):
    def __init__(self, dbname=None, uri=None, username=None, password=None):
        super().__init__('reactome', dbname, uri, username, password)

    def get_summation_data(self, nodes: []):
        """
        load summation for given list of reactome nodes
        return dict of nodeId-summation
        """
        ids = [get_id(n) for n in nodes]
        query = """
        FOR n IN reactome
            FILTER TO_NUMBER(n._key) in @ids
            FOR s IN OUTBOUND n summation
                FILTER "Summation" in s.labels
                RETURN {
                    id: TO_NUMBER(n._key),
                    text: s.text
                }
            """
        return dict(self.get_query_values(query, ids=ids))

    def get_gene_names(self, nodes):
        """
        Load gene names from reference entities
        Args:
            nodes: list of arango nodes
        Returns: dictionary of nodeId and geneNames
        """
        # TODO: check new version of this query
        ids = [get_id(n) for n in nodes]
        query = """
            FOR n in reactome
                FILTER TO_NUMBER(n._key) IN @nids
                FOR r IN OUTBOUND n referenceEntity
                    FILTER length(r.geneName) > 0
                    RETURN {
                        id: TO_NUMBER(n._key),
                        geneNames: r.geneName
                    }
        """
        return dict(self.get_query_values(query, ids=ids))

    def get_nodes_by_attr(self, attr_values: [], attr_name, node_label='db_Reactome'):
        return super().get_nodes_by_attr(attr_values, attr_name, node_label)

    """
    Get PhysicalEntities by NCBI gene ids.
    """
    def get_entity_nodes_by_gene_ids(self, gene_ids:[]):
        query = """
        FOR n IN reactome
            FILTER n.identifier in @genes && "ReferenceEntity" in n.labels && n.databaseName == "NCBI Gene"
            FOR re IN INBOUND n referenceGene
                FOR phys IN INBOUND re referenceEntity
                FILTER "PhysicalEntity" in phys.labels
                RETURN phys
                """
        nodes = self.get_raw_value(query, genes=gene_ids)
        logging.info(f"{len(gene_ids)} gene_ids, matched to {len(nodes)} nodes")
        return nodes

    def get_reference_nodes_by_gene_ids(self, gene_ids:[]):
        query = """
        FOR n IN reactome
            FILTER n.identifier in @genes && "ReferenceEntity" in n.labels && n.databaseName == "NCBI Gene"
            FOR m IN INBOUND n referenceGene
                FILTER "ReferenceEntity" in m.labels
                RETURN {m: m}
        """
        nodes = self.get_raw_value(query, genes=gene_ids)
        logging.info(f"{len(gene_ids)} gene_ids, matched to {len(nodes)} nodes")
        return nodes

    """
    Get PhysicalEntities by ChEBI ids
    """
    def get_entity_nodes_by_chebi_ids(self, chebi_ids:[]):
        query = """
        FOR n IN reactome
            FILTER "PhysicalEntity" in n.labels
            FOR r IN OUTBOUND n referenceEntity
                FILTER "ReferenceEntity" in r.labels && r.databaseName == "ChEBI" && r.identifier in @metabs
                RETURN n
        """
        nodes = self.get_raw_value(query, metabs=chebi_ids)
        logging.info(f"{len(chebi_ids)} chebi_ids, matched to {len(nodes)} nodes")
        return nodes

    def get_reference_nodes_by_chebi_ids(self, chebi_ids:[]):
        query = """
        FOR r IN reactome
            FILTER "ReferenceEntity" in r.labels && r.databaseName == "ChEBI" && r.identifier in @metabs
            RETURN {r: r}
        """
        nodes = self.get_raw_value(query, metabs=chebi_ids)
        logging.info(f"{len(chebi_ids)} chebi_ids, matched to {len(nodes)} nodes")
        return nodes

    @classmethod
    def get_node_entity_type(cls, node):
        """
        Currently, sankey only allow the entity type in the list allowedNodeEntityTypes
        """
        entity_type = node.get('entityType', 'Entity')
        if entity_type in allowedNodeEntityTypes:
            return entity_type
        return 'Entity'


class Reactome(GraphSource):
    def __init__(self, database: ReactomeDB):
        super().__init__(database)

    @classmethod
    def get_node_name(cls, node):
        name = node.get('name')
        if not name:
            name = cls.split_displayName(node.get('displayName'))[0]
        return name

    @classmethod
    def get_node_desc(cls, node):
        return f"{node.get('entityType')} {node.get('displayName')}"

    def add_summation(self, arango_nodes, D):
        node_summation = self.database.get_summation_data(arango_nodes)
        nx.set_node_attributes(D, node_summation, 'summation')

    def add_gene_names(self, arango_nodes, D):
        node_gene_names = self.database.get_gene_names(arango_nodes)
        nx.set_node_attributes(D, node_gene_names, 'gene_names')

    def initiate_trace_graph(self, tracegraph:TraceGraphNx, exclude_secondary_metabolites=True, exclude_secondary=True):
        """
        Default method to initiate trace graph. The default graph does not include reference entities
        Args:
            tracegraph: TraceGraphNx
            exclude_secondary_metabolites: if true, all secondary metobolites will be excluded from the graph.
        Returns:
        """
        logging.info("load reactome graph")
        if exclude_secondary_metabolites:
            node_lists_query = ','.join(
                f"""            
                    FLATTEN(
                        FOR n IN {rel}
                            RETURN [n._from, n._to]
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            node_query = f"""
                FOR n IN UNION_DISTINCT(
                    {node_lists_query}
                )
            """ + """
                    LET key = PARSE_IDENTIFIER(n).key
                    FOR node in reactome
                        FILTER node._key == key && "SecondaryMetabolite" NOT IN node.labels
                        RETURN {node_id: TO_NUMBER(key)}
            """
            rel_lists_query = ','.join(
                f"""            
                    (
                        FOR n IN {rel}
                            RETURN n
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            rel_query = f"""
                FOR n IN UNION_DISTINCT(
                    {rel_lists_query}
                )
            """ + """
                    LET key_from = PARSE_IDENTIFIER(n._from).key
                    FOR node_from in reactome
                        FILTER node_from._key == key_from && "SecondaryMetabolite" NOT IN node_from.labels
                        LET key_to = PARSE_IDENTIFIER(n._to).key
                        FOR node_to in reactome
                            FILTER node_to._key == key_to && "SecondaryMetabolite" NOT IN node_to.labels                       
                            RETURN {
                                source: TO_NUMBER(node_from._key),
                                target: TO_NUMBER(node_to._key),
                                type: n.label
                            }
            """
        else:
            node_lists_query = ','.join(
                f"""            
                    FLATTEN(
                        FOR n IN {rel}
                            RETURN [n._from, n._to]
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            node_query = f"""
                FOR n IN UNION_DISTINCT(
                    {node_lists_query}
                )
            """ + """
                    RETURN {node_id: TO_NUMBER(PARSE_IDENTIFIER(n).key)}
            """
            rel_lists_query = ','.join(
                f"""            
                    (
                        FOR n IN {rel}
                            RETURN n
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            rel_query = f"""
                FOR n IN UNION_DISTINCT(
                    {rel_lists_query}
                )
            """ + """
                    RETURN {
                        source: PARSE_IDENTIFIER(n._from).key,
                        target: PARSE_IDENTIFIER(n._to).key,
                        type: n.label
                    }
            """
        tracegraph.add_nodes(node_query)
        tracegraph.add_rels(rel_query)
        logging.info(nx.info(tracegraph.graph))
        return tracegraph

    def custome_init_trace_graph(self, tracegraph:TraceGraphNx, excluding_nodes):
        """
        Initiate tracegraph by excluding given list of nodes
        Args:
            tracegraph: TraceGraphNx
            excluding_nodes: list of arango nodes to be excluded from the graph for analysis or tracing
        Returns:
        """
        logging.info("load reactome graph")
        node_ids = [get_id(n) for n in excluding_nodes]
        if excluding_nodes:
            node_lists_query = ','.join(
                f"""            
                    FLATTEN(
                        FOR n IN {rel}
                            RETURN [n._from, n._to]
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            node_query = f"""
                FOR n IN UNION_DISTINCT(
                    {node_lists_query}
                )
            """ + """
                    LET key = PARSE_IDENTIFIER(n).key
                    FILTER key NOT IN @node_ids
                    return {node_id: key}
            """
            rel_lists_query = ','.join(
                f"""            
                    (
                        FOR n IN {rel}
                            RETURN n
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            rel_query = f"""
                FOR n IN UNION_DISTINCT(
                    {rel_lists_query}
                )
            """ + """
                    LET key_from = PARSE_IDENTIFIER(n._from).key
                    LET key_to = PARSE_IDENTIFIER(n._to).key
                    FILTER key_from NOT IN @node_ids && key_to NOT IN @node_ids
                    RETURN {
                        source: key_from,
                        target: key_to,
                        type: n.label
                    }
            """
        else:
            node_lists_query = ','.join(
                f"""            
                    FLATTEN(
                        FOR n IN {rel}
                            RETURN [n._from, n._to]
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            node_query = f"""
                FOR n IN UNION_DISTINCT(
                    {node_lists_query}
                )
            """ + """
            
                    LET key = PARSE_IDENTIFIER(n).key
                    return {node_id: key}
            """
            rel_lists_query = ','.join(
                f"""            
                    (
                        FOR n IN {rel}
                            RETURN n
                    
                    )
                """ for rel in REACTOME_TRACE_RELS
            )
            rel_query = f"""
                FOR n IN UNION_DISTINCT(
                    {rel_lists_query}
                )
            """ + """
                    RETURN {
                        source: PARSE_IDENTIFIER(n._from).key,
                        target: PARSE_IDENTIFIER(n._to).key,
                        type: n.label
                    }
            """
        tracegraph.add_nodes(node_query, rels=REACTOME_TRACE_RELS, node_ids=node_ids)
        tracegraph.add_rels(rel_query, rels=REACTOME_TRACE_RELS, node_ids=node_ids)
        logging.info(nx.info(tracegraph.graph))
        return tracegraph

    @classmethod
    def set_edge_description(cls, D, startNode, endNode, edgeType, key=None):
        source_display_name = f"{startNode.get('entityType')}({cls.split_displayName(startNode.get('displayName'))[0]})"
        target_display_name = f"{endNode.get('entityType')}({cls.split_displayName(endNode.get('displayName'))[0]})"
        nlg = f"{source_display_name} | {edgeType} | {target_display_name}"
        desc = f"RELATIONSHIP: {edgeType}\n{nlg}"
        if key is None:
            e = (get_id(startNode), get_id(endNode))
        else:
            e = (get_id(startNode), get_id(endNode), key)
        # D.edges[e]['NLG'] = nlg
        D.edges[e]['description'] = desc

    def set_nodes_description(self, arango_nodes, D):
        self.add_summation(arango_nodes, D)
        for n in arango_nodes:
            lines = [f"NODE: {n.get('entityType')}"]
            lines.extend(n.get('synonyms', []))
            lines.append('')
            if "summation" in D.nodes[get_id(n)]:
                lines.append('SUMMATION:')
                lines.append(D.nodes[get_id(n)]['summation'])
            D.nodes[get_id(n)]['description'] = '\n'.join(lines)

    def set_edges_description(self, arango_edges, D:DirectedGraph):
        # if isinstance(D, MultiDirectedGraph):
        #     # summations = cls.get_reactome_edge_descriptions(D)
        for edge in arango_edges:
            self.add_edge_description(edge.start_node, edge.end_node, edge.type, D)

    @classmethod
    def split_displayName(cls, displayName):
        """
        Split compartment and name part of displayName.
        If no compartment indicated, then an empty string is returned in its place
        :param displayName: string
        :return: (string, string)
        """
        if not re.fullmatch('.+ \[[A-Za-z0-9- ]+]', displayName): return displayName, ""
        compartment = re.findall('\[([A-Za-z0-9- ]+)]', displayName)[0]
        # -3 for length of " [...]"
        return displayName[:-len(compartment) - 3], compartment

    def get_node_data_for_excel(self, node_ids: []):
        # TODO: check new version of this query
        query = """
            FOR n in reactome
                FILTER TO_NUMBER(n._key) IN @nids
                LET gene = first(
                    FOR r IN OUTBOUND n referenceEntity
                        FILTER length(r.geneName) > 0
                        RETURN {
                            name: first(r.geneName),
                            identifier: r.identifier
                        }
                )
                RETURN {
                    id: TO_NUMBER(n._key),
                    stId: n.stId,
                    name: n.name,
                    displayName: n.displayName,
                    synonyms: n.synonyms,
                    geneName: gene.name,
                    chebiUniprot: gene.identifier,
                    entityType: n.entityType,
                    labels: n.labels
                }
        """
        return self.database.get_dataframe(query, nids=node_ids)




if __name__ == "__main__":
    import os, dotenv
    dotenv.load_dotenv()
    database = ReactomeDB(os.getenv('ARANGO_DATABASE', 'reactome'),
                          os.getenv('ARANGO_URI', 'localhost'), 
                          os.getenv('ARANGO_USER', 'root'), 
                          os.getenv('ARANGO_PASSWORD', ''))
    nodes = database.get_entity_nodes_by_chebi_ids(['17336'])
    print(nodes)












