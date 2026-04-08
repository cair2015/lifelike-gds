# `graph_sources`

The `graph_sources` package contains the maintained graph-source classes and Neo4j-backed database adapters for PathwayGraphX. It provides the domain-specific source logic used by the shared tracing and NetworkX analysis code under `pathway_graphx.network`.

## Main Modules

- `biocyc.py`: shared BioCyc graph-source behavior
- `reactome.py`: shared Reactome graph-source behavior
- `database.py`: Neo4j connection management and query helpers
- `neo4j_utils.py`: low-level Neo4j driver and Cypher utilities
- `reactome_db.py`: Reactome-specific graph source and database adapter
- `biocyc_db.py`: BioCyc-specific adapter retained in the package surface

## Typical Usage

```python
from pathway_graphx.graph_sources import Reactome, ReactomeDB
from pathway_graphx.network.shortest_paths_trace import ShortestPathTrace

database = ReactomeDB(database='neo4j')
reactome = Reactome(database)
tracegraph = ShortestPathTrace(reactome)
```

## Configuration

Expected environment variables:
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`
- `NEO4J_ENCRYPTED`

## Scope

PathwayGraphX now focuses on Neo4j and Reactome. The former ArangoDB-specific source package is no longer part of the maintained `src/` tree.
