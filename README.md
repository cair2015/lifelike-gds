# Lifelike GDS

Lifelike GDS provides graph database analysis tools focused on Neo4j-backed Reactome workflows. The canonical Python package is `lifelike_gds`.

## Project Overview

Lifelike GDS is designed for:
- Neo4j-backed Reactome graph exploration
- Network analysis and shortest path algorithms
- Radiate analysis for exploring pathway connectivity
- Reusable graph utilities built on NetworkX

## Requirements

- Python >= 3.11
- `uv` package manager

## Quick Start

From the project root:

```bash
just setup
```

Run the test suite with:

```bash
just test
```

## Package Names

- Distribution name: `lifelike-gds`
- Canonical import package: `lifelike_gds`

## Project Structure

```text
.
├── src/
│   └── lifelike_gds/        # Canonical package
│       ├── graph_sources/     # Graph-source classes and Neo4j adapters
│       ├── network/           # Shared graph analysis code
│       └── utils/             # Utilities
├── examples/                  # Examples and migration candidates
├── notebooks/                 # Jupyter notebooks
├── neo4j-db/                  # Neo4j database notes and dumps
├── data/                      # Input/output graph data
├── pyproject.toml             # Project configuration
└── justfile                   # Task automation
```

## Development Workflow

Common commands:
- `just setup`
- `just test`
- `just lint`
- `just format`
- `just typecheck`

## References

- Neo4j Documentation: https://neo4j.com/docs/
- Reactome: https://reactome.org/
- uv Documentation: https://docs.astral.sh/uv/
