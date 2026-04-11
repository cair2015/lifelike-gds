"""Integration smoke tests for a real local Neo4j Reactome database."""

from __future__ import annotations

import os


import dotenv
import pytest
pytestmark = pytest.mark.integration

dotenv.load_dotenv()


def _require_env(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        pytest.skip(
            f"Skipping real Neo4j smoke test; missing env vars: {', '.join(missing)}"
        )


def test_neo4j_reactome_connection_and_datasource_creation() -> None:
    _require_env("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

    from lifelike_gds.graph_sources import Reactome, ReactomeDB

    database = ReactomeDB(database="neo4j")
    try:
        graphsource = Reactome(database)
        assert graphsource.database is database
        assert database.connection is not None
        assert database.connection.driver is not None
        assert database.connection.database == "neo4j"
    finally:
        database.close()


def test_neo4j_reactome_graph_projection_loads_into_tracegraph() -> None:
    _require_env("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

    from lifelike_gds.graph_sources import Reactome, ReactomeDB
    from lifelike_gds.network.trace_graph_nx import TraceGraphNx

    database = ReactomeDB(database="neo4j")
    try:
        graphsource = Reactome(database)
        tracegraph = TraceGraphNx(graphsource)
        tracegraph.init_default_graph(exclude_node_labels=[])

        num_nodes = tracegraph.graph.number_of_nodes()
        num_edges = tracegraph.graph.number_of_edges()

        assert num_nodes > 0, "Neo4j Reactome graph projection should contain nodes"
        assert num_edges > 0, "Neo4j Reactome graph projection should contain edges"
        assert database.connection.database == "neo4j"
    finally:
        database.close()
