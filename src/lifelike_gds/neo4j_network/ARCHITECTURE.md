"""
Neo4j Network Analysis Architecture
====================================

OVERVIEW
--------
This document describes the refactored Neo4j-based network analysis module
created for GDS-Public to enable graph data analysis using Neo4j instead of ArangoDB.
The architecture maintains modularity, separation of concerns, and reusability.

PROJECT STRUCTURE
-----------------

src/lifelike_gds/
├── network/                 (Generic, database-agnostic graph algorithms)
│   ├── graph_utils.py       (NetworkX graph manipulation)
│   ├── trace_utils.py       (Tracing algorithms)
│   ├── graph_algorithms.py  (Network algorithms)
│   ├── collection_utils.py  (Collection utilities)
│   ├── graph_props.py       (Graph property handling)
│   ├── graph_io.py          (Import/export)
│   └── groups.py            (Node grouping)
│
├── arango_network/          (ArangoDB-specific implementation - UNCHANGED)
│   ├── database.py          (ArangoDB connection & queries)
│   ├── trace_graph_nx.py    (Arango-based trace graphs)
│   ├── radiate_trace.py     (Arango-based radiate analysis)
│   ├── shortest_paths_trace.py
│   ├── inbetweenness_trace.py
│   ├── config.yml           (ArangoDB config)
│   └── ...
│
└── neo4j_network/           (NEW: Neo4j-specific implementation)
    ├── __init__.py          (Module exports)
    ├── neo4j_utils.py       (Core Neo4j connection & query builders)
    ├── database.py          (Neo4j Database & GraphSource classes)
    ├── config.yml           (Neo4j configuration)
    ├── config_utils.py      (Config file loading)
    ├── trace_graph_nx.py    (Neo4j-based TraceGraphNx)
    ├── trace_graph_utils.py (Trace-specific utilities)
    ├── radiate_trace.py     (PageRank-based radiate analysis)
    ├── shortest_paths_trace.py (Shortest path analysis)
    ├── inbetweenness_trace.py (Betweenness centrality analysis - TODO)
    └── reactome.py          (Neo4j Reactome-specific handlers - TODO)


ARCHITECTURE PATTERNS
---------------------

1. DATABASE ABSTRACTION LAYER
   └─ Pattern: Bridge Pattern
   
   neo4j_utils.py
   ├── Neo4jConnection: Low-level connection management
   │   └─ Handles authentication, session management, error handling
   │   └─ Methods: execute_query, get_records, get_dataframe, get_single_value
   │
   └── Neo4jQueryBuilder: Reusable Cypher query templates
       ├─ get_nodes_by_ids()
       ├─ get_nodes_by_property()
       ├─ get_relationships_between_nodes()
       ├─ get_shortest_paths()
       └─ get_all_shortest_paths()

   database.py
   ├── Database: Mid-level database operations
   │   └─ Wraps Neo4jConnection with domain-specific methods
   │   └─ Interface mirrors ArangoDB's Database class for compatibility
   │   └─ Methods: run_query, get_dict, get_dataframe, get_nodes_by_node_ids, etc.
   │
   └── GraphSource: Graph metadata and Neo4j operations
       └─ Bridges Database operations with TraceGraphNx
       └─ Handles node/edge descriptions, graph initialization


2. GRAPH ANALYSIS LAYER
   └─ Pattern: Inheritance + Composition
   
   NetworkX Backend (from src/lifelike_gds/network/)
   ├── Lightweight, algorithm-focused graph structures
   ├── DirectedGraph, MultiDirectedGraph wrappers
   └── Generic algorithms (PageRank, shortest paths, etc.)
   
   TraceGraphNx (neo4j_network/trace_graph_nx.py)
   ├── Orchestrator for loading Neo4j data into NetworkX
   ├── Bridges Neo4j queries with NetworkX algorithms
   ├── Methods for adding/managing nodes, edges, node sets
   └── Lazy loading of node properties from Neo4j
   
   Specialized Analyses (Inheritance from TraceGraphNx)
   ├── RadiateTrace (PageRank-based influence analysis)
   │   └─ Methods: set_pagerank_and_numreach(), export_pagerank_data()
   ├── ShortestPathTrace (Path-finding analysis)
   │   └─ Methods: add_shortest_paths(), add_k_shortest_paths()
   └── InteractionPathTrace (Typed relationship filtering)
       └─ Methods: add_typed_shortest_paths()


3. CONFIGURATION MANAGEMENT
   └─ Pattern: Strategy Pattern (Environment-based)
   
   .env file
   └─ Environment variables for Neo4j connection (modern best practice)
      ├─ NEO4J_URI: Connection URI
      ├─ NEO4J_USER: Database username
      ├─ NEO4J_PASSWORD: Database password
      ├─ NEO4J_DATABASE: Database name
      └─ NEO4J_ENCRYPTED: Enable encryption (true/false)
   
   config_utils.py
   └─ Dynamic config loading using python-dotenv
      ├─ Automatically discovers .env files in common locations
      ├─ Falls back to system environment variables
      └─ Provides convenience functions: read_config(), get_neo4j_config(), get_config_value()


4. UTILITY FUNCTIONS LAYER
   └─ Pattern: Utility/Helper Class
   
   trace_graph_utils.py
   ├── add_pagerank(): Calculate and store PageRank
   ├── set_nReach(): Calculate node reachability
   ├── set_intersection_pagerank(): Multi-target PageRank
   ├── write_sankey_file(): Export to Sankey format
   ├── write_cytoscape_file(): Export to Cytoscape format
   ├── k_shortest_paths(): Find k paths between nodes
   ├── single_shortest_paths(): Paths from one source to multiple targets
   └── Helper functions for path extraction and processing


COMPARISON: ArangoDB vs Neo4j
------------------------------

ArangoDB Implementation (arango_network/)
├── Query Language: AQL (ArangoDB Query Language)
├── Traversal: FOR loops with FILTER operations
├── Query Pattern:
│   FOR n IN collection
│   FILTER n.property IN @values
│   RETURN n
└── Database Type: Multi-model (documents, graphs, search)

Neo4j Implementation (neo4j_network/)
├── Query Language: Cypher
├── Traversal: Pattern matching with relationships
├── Query Pattern:
│   MATCH (n:Label)
│   WHERE n.property IN $values
│   RETURN n
└── Database Type: Property graph (native graph database)

ADVANTAGES OF NEO4J:
✓ Native graph database optimized for relationship traversal
✓ More intuitive Cypher query language for graph operations
✓ Better performance for relationship-heavy queries
✓ Built-in shortest path algorithms
✓ Stronger graph-specific indexing
✓ More active graph analysis community


DATA FLOW EXAMPLES
------------------

Example 1: Creating and Analyzing a Radiate Graph
--------------------------------------------------

from lifelike_gds.neo4j_network import Database, GraphSource
from lifelike_gds.neo4j_network.radiate_trace import RadiateTrace

# 1. Initialize database connection
db = Database(
    collection_label="Reactome",
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password"
)

# 2. Create graph source
graph_source = GraphSource(db, node_label_prop="displayName")

# 3. Initialize trace graph
trace = RadiateTrace(graph_source)

# 4. Load graph data
trace.init_default_graph(exclude_currency=True)

# 5. Set up source node set (from Neo4j query)
trace.add_nodes(
    "MATCH (n:Reactome) WHERE n.label in $labels RETURN id(n) as node_id",
    labels=["Gene", "Protein"]
)

# 6. Calculate PageRank with personalization
personalization = {node_id: 1.0 for node_id in trace.graph.nodes()}
trace.set_pagerank_and_numreach(
    "source_set",
    direction="both",
    personalization=personalization
)

# 7. Export results
trace.export_pagerank_data(
    sources="source_set",
    filename="pagerank_results.xlsx",
    num_nodes=3000
)

# 8. Clean and export graph
trace.clean_graph()
trace.export_to_file("analysis_graph.graphml")


Example 2: Finding Shortest Paths
-----------------------------------

from lifelike_gds.neo4j_network.shortest_paths_trace import ShortestPathTrace

trace = ShortestPathTrace(graph_source)
trace.init_default_graph()

# Add shortest paths between sources and targets
found = trace.add_shortest_paths(
    sources="gene_set",
    targets="metabolite_set",
    shortest_paths_plus_n=2  # Also includes paths up to +2 edges longer
)

if found:
    trace.export_to_file("shortest_paths_graph.graphml")
    trace.export_to_file("shortest_paths_data.cytoscape")


Example 3: Custom Query with Neo4j Utils
------------------------------------------

from lifelike_gds.neo4j_network.neo4j_utils import Neo4jConnection, Neo4jQueryBuilder

# Work directly with Neo4j
conn = Neo4jConnection(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password"
)

# Use query builder for common patterns
query, params = Neo4jQueryBuilder.get_nodes_by_property(
    collection_label="Reactome",
    property_name="geneSymbol",
    property_values=["BRCA1", "TP53"]
)

results = conn.get_dataframe(query, **params)
print(results)


EXTENDING THE FRAMEWORK
-----------------------

To add new analysis types (e.g., Betweenness Centrality):

1. Create new file: inbetweenness_trace.py
   └─ Inherit from TraceGraphNx
   └─ Implement analysis-specific methods

2. Add utility functions to trace_graph_utils.py
   └─ Implement algorithm (e.g., calculate_betweenness())
   └─ Add export functions if needed

3. Update __init__.py to export new class

4. Example structure:

   from lifelike_gds.neo4j_network.trace_graph_nx import TraceGraphNx
   
   class BetweennessTrace(TraceGraphNx):
       def __init__(self, graphsource):
           super().__init__(graphsource, directed=True)
       
       def calculate_betweenness(self, normalized=True):
           # Implementation
           pass


TESTING GUIDE
-------------

To test the neo4j_network module:

1. Start a Neo4j instance:
   docker run -d -p 7687:7687 -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes neo4j

2. Load test data (create nodes and relationships)

3. Test basic functionality:
   from lifelike_gds.neo4j_network import Database, GraphSource
   db = Database("TestCollection")
   assert db.connection is not None

4. Test query builders:
   from lifelike_gds.neo4j_network.neo4j_utils import Neo4jQueryBuilder
   query, params = Neo4jQueryBuilder.get_nodes_by_ids("TestLabel", [1, 2, 3])
   assert "WHERE id(n) IN" in query

5. Test trace analysis:
   trace = RadiateTrace(graph_source)
   trace.init_default_graph()
   # Assert graph has nodes and edges


PERFORMANCE CONSIDERATIONS
---------------------------

1. Query Optimization
   ├─ Use Cypher EXPLAIN/PROFILE for query analysis
   ├─ Create appropriate Neo4j indexes on frequently-queried properties
   ├─ Batch queries when possible
   └─ Use Neo4j query result streaming for large datasets

2. Memory Management
   ├─ Load graph incrementally rather than all at once
   ├─ Use clean_graph() to remove unused nodes/edges
   ├─ Consider graph projection for large networks
   └─ Stream results rather than loading all into memory

3. Scalability Patterns
   ├─ For large graphs: Use Neo4j's built-in algorithms (GDS library)
   ├─ Consider Neo4j Enterprise features for sharding
   ├─ Use Cypher's native path-finding for large datasets
   └─ Leverage Neo4j's APOC procedures for complex operations


MIGRATION FROM ARANGODB
-----------------------

Existing code using arango_network can be migrated by:

1. Replace imports:
   OLD: from lifelike_gds.arango_network.database import Database
   NEW: from lifelike_gds.neo4j_network.database import Database

2. Update configuration:
   Modify config.yml to point to Neo4j instance

3. Minimal code changes required (interfaces are compatible)

4. Query translation guide:
   AQL (ArangoDB)          →  Cypher (Neo4j)
   FOR n IN collection     →  MATCH (n:Label)
   FILTER condition        →  WHERE condition
   RETURN expr             →  RETURN expr
   WITH                    →  WITH


FUTURE ENHANCEMENTS
-------------------

1. Neo4j Graph Data Science (GDS) Library Integration
   └─ Use built-in algorithms for better performance
   └─ Implement: PageRank, Betweenness, Degree Centrality, etc.

2. Streaming/Parallel Processing
   └─ Implement async/await for non-blocking queries
   └─ Support batch imports

3. Query Caching
   └─ Cache frequently-used queries
   └─ Implement LRU cache for results

4. Reactome-specific optimizations
   └─ Create specialized Reactome query builders
   └─ Add disease pathway analysis
   └─ Implement BioCyc support

5. Advanced Visualizations
   └─ Enhanced Cytoscape export
   └─ Interactive Sankey diagrams
   └─ Network statistics dashboards


CONTACT & SUPPORT
-----------------

For questions about neo4j_network module architecture:
- Review this document
- Check example usage in docstrings
- Reference comparable arango_network implementations
- Consult Neo4j Cypher documentation: https://neo4j.com/docs/cypher-manual/
"""
