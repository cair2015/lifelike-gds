# Neo4j Network Module - Quick Start Guide

## Overview

The `neo4j_network` module provides a complete Neo4j-based implementation for network analysis in GDS-Public. It maintains the same interface patterns as `arango_network` while leveraging Neo4j's native graph capabilities.

## Module Contents

### Core Files

| File | Purpose |
|------|---------|
| `neo4j_utils.py` | Low-level Neo4j connection, query execution, and Cypher query builders |
| `database.py` | High-level database abstraction (Database, GraphSource classes) |
| `.env.example` | Example environment variables for configuration |
| `config_utils.py` | Configuration loading using python-dotenv |
| `trace_graph_nx.py` | TraceGraphNx: Orchestrates Neo4j data loading into NetworkX graphs |
| `trace_graph_utils.py` | Utility functions: PageRank, path algorithms, file export |
| `radiate_trace.py` | RadiateTrace: PageRank-based influence analysis |
| `shortest_paths_trace.py` | ShortestPathTrace & InteractionPathTrace: Path-finding analysis |

## Key Design Principles

### 1. **Modularity**
- `neo4j_utils.py` provides reusable Neo4j operations
- `database.py` adds domain-specific abstractions
- `trace_graph_*.py` files handle specialized analyses
- Easy to extend with new analysis types

### 2. **Database Agnostic Upper Layers**
- `network/` folder contains generic NetworkX algorithms
- Works with any graph data loaded into NetworkX
- Can be reused by arango_network, neo4j_network, etc.

### 3. **Interface Compatibility**
- Database and GraphSource classes mirror arango_network interfaces
- Easy migration from ArangoDB to Neo4j
- Minimal code changes required for existing code

## Typical Usage Pattern

```python
# 1. Initialize database connection
from lifelike_gds.neo4j_network import Database, GraphSource
from lifelike_gds.neo4j_network.radiate_trace import RadiateTrace

db = Database(collection_label="Reactome")
graph_source = GraphSource(db)

# 2. Create analysis
trace = RadiateTrace(graph_source)
trace.init_default_graph()

# 3. Add source and target node sets
trace.set_node_set("sources", {node_id1, node_id2, ...})
trace.set_node_set("targets", {node_id3, node_id4, ...})

# 4. Execute analysis
trace.set_pagerank_and_numreach("sources", direction="both")

# 5. Export results
trace.export_pagerank_data("sources", "results.xlsx")
```

## Configuration

The module uses environment variables for Neo4j configuration. Create a `.env` file in your project root or the neo4j_network directory:

```bash
# Copy the example configuration
cp src/lifelike_gds/neo4j_network/.env.example .env

# Edit .env with your Neo4j credentials
nano .env
```

Environment variables:
- `NEO4J_URI`: Connection URI (default: `bolt://localhost:7687`)
- `NEO4J_USER`: Username (default: `neo4j`)
- `NEO4J_PASSWORD`: Password (required)
- `NEO4J_DATABASE`: Database name (default: `neo4j`)
- `NEO4J_ENCRYPTED`: Use encryption (default: `false`)

The module will search for `.env` files in these locations (in order):
1. Current directory (`.env`)
2. Current working directory 
3. neo4j_network directory
4. Project root

**Note:** Add `.env` to `.gitignore` to avoid committing credentials!

## Query Examples

### Basic Node Query
```python
db = Database("Reactome")
results = db.get_dataframe("""
    MATCH (n:Reactome)
    WHERE n.geneSymbol IN $genes
    RETURN id(n) as node_id, n.displayName as name
""", genes=["BRCA1", "TP53"])
```

### Shortest Paths
```python
trace = ShortestPathTrace(graph_source)
trace.init_default_graph()
trace.add_shortest_paths(sources="gene_set", targets="metabolite_set")
```

### Custom PageRank Analysis
```python
trace = RadiateTrace(graph_source)
trace.init_default_graph()
personalization = {node_id: weight for node_id, weight in source_weights.items()}
trace.set_pagerank_and_numreach("sources", personalization=personalization)
trace.export_pagerank_data("sources", "analysis.xlsx")
```

## Architecture Comparison

### network/ (Generic Graph Library)
- ✓ Algorithm library (PageRank, shortest paths, etc.)
- ✓ Graph manipulation utilities
- ✓ Database-agnostic
- ✓ Works with NetworkX directly

### arango_network/ (ArangoDB Implementation)
- ✓ ArangoDB connection management
- ✓ AQL query execution
- ✓ Bridges ArangoDB → NetworkX
- ✓ Specific analyses (radiate, paths, etc.)

### neo4j_network/ (Neo4j Implementation) - NEW
- ✓ Neo4j connection management
- ✓ Cypher query execution
- ✓ Bridges Neo4j → NetworkX
- ✓ Specific analyses (radiate, paths, etc.)
- ✓ Same interface as arango_network for compatibility

## Extending the Module

### Add New Analysis Type

1. Create new file in `neo4j_network/`
2. Inherit from `TraceGraphNx`
3. Implement analysis-specific methods
4. Add utilities to `trace_graph_utils.py` if needed
5. Update `__init__.py`

Example:
```python
from lifelike_gds.neo4j_network.trace_graph_nx import TraceGraphNx

class MyAnalysis(TraceGraphNx):
    def __init__(self, graphsource):
        super().__init__(graphsource, directed=True)
    
    def run_analysis(self, node_set):
        # Implementation
        pass
```

## Key Differences from ArangoDB

| Aspect | ArangoDB | Neo4j |
|--------|----------|-------|
| Query Language | AQL | Cypher |
| Query Style | FOR loops | MATCH patterns |
| Relationship Handling | Manual joins | Native relationships |
| Graph Optimization | Multi-model | Graph-native |
| Performance (graphs) | Good | Excellent |

## Migration Guide

To migrate existing code from arango_network:

```python
# OLD
from lifelike_gds.arango_network import Database, GraphSource
from lifelike_gds.arango_network.radiate_trace import RadiateTrace

# NEW
from lifelike_gds.neo4j_network import Database, GraphSource
from lifelike_gds.neo4j_network.radiate_trace import RadiateTrace

# Rest of code remains largely the same!
```

## Files of Interest for Further Development

- `trace_graph_utils.py` - Add more graph algorithms here
- `trace_graph_nx.py` - Add graph loading/management methods
- `neo4j_utils.py` - Add Neo4j-specific query patterns
- `config.yml` - Customize connection settings

## See Also

- `ARCHITECTURE.md` - Detailed architecture documentation
- `network/` folder - Generic graph algorithms
- `arango_network/` - Reference implementation (ArangoDB)
- Neo4j Cypher Manual - https://neo4j.com/docs/cypher-manual/
