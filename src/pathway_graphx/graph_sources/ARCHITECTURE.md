# Graph Sources Architecture

PathwayGraphX uses a layered architecture:

1. `pathway_graphx.graph_sources` handles Neo4j connectivity and source-specific queries.
2. `pathway_graphx.network` contains shared graph loading, tracing, and export logic.
3. Examples and notebooks build on top of those layers.

## Important Components

- `Database`: wraps Neo4j connection and query execution
- `GraphSource`: backend adapter used by the analysis layer
- `Reactome`: Reactome-specific graph source implementation
- `TraceGraphNx`: shared NetworkX graph container and tracing entry point

## Current Direction

The maintained backend focus is Neo4j with Reactome data. The repository no longer carries the old `arango_network` source implementation in `src/`, and package imports should now use `pathway_graphx`.
