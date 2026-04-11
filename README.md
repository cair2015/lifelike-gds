# Lifelike GDS

Lifelike GDS is a personal fork and refactoring effort based on [SBRG/GDS-Public](https://github.com/SBRG/GDS-Public).

The original project was developed several years ago around Python 3.9 and an earlier dependency stack. This fork was started to modernize the codebase for current Python and library versions, clean up project structure, and simplify the graph-database integration around Neo4j and Reactome workflows.

## Purpose

This repository is intended as:

- a modernization pass on the original codebase
- a working space for refactoring legacy graph-analysis utilities
- a reference point for Neo4j-backed Reactome querying and tracing workflows

The project is not currently under active feature development. It is being rounded out and preserved as a personal fork in its current refactored state.

Lifelike GDS is designed for:

- Neo4j-backed Reactome graph exploration
- network analysis and shortest path algorithms
- radiate analysis for exploring pathway connectivity
- reusable graph utilities built on NetworkX
- exporting trace graphs as JSON for Sankey-style visualization workflows

## Current Status

The repository includes:

- a renamed and reorganized Python package: `lifelike_gds`
- updates for newer Python and dependency versions
- refactored Neo4j connection and graph-source code
- unit tests plus optional integration tests for local Neo4j-based workflows

Some planned work remains incomplete, including broader examples, notebooks, and fuller test coverage.

## Requirements

- Python 3.11+
- `uv`

## Getting Started

Install dependencies:

```bash
just setup
```

Run the default test suite:

```bash
just test
```

Run integration tests separately:

```bash
uv run pytest integration -m integration
```

## Package Names

- Distribution name: `lifelike-gds`
- Import package: `lifelike_gds`

## Development Commands

- `just setup`
- `just test`
- `just lint`
- `just format`
- `just typecheck`

## References

- Original project: https://github.com/SBRG/GDS-Public
- Neo4j Documentation: https://neo4j.com/docs/
- Reactome: https://reactome.org/
- uv Documentation: https://docs.astral.sh/uv/
