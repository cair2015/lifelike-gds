"""Integration tests for real Reactome database connections.

These tests use the actual env-based configuration and are intended to verify:

1. The database connection can be established.
2. The corresponding Reactome graph source can be created.

Expected environment variables:
- ArangoDB: `ARANGO_URI`, `ARANGO_USER`, `ARANGO_PASSWORD`
- Neo4j: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`

Notes:
- ArangoDB is tested against database name `reactome`.
- Neo4j is tested against database name `neo4j` (community edition default).
"""

from __future__ import annotations

import os
import unittest
import dotenv

dotenv.load_dotenv()


def _require_env(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise unittest.SkipTest(
            f"Skipping real database connection test; missing env vars: {', '.join(missing)}"
        )


class ReactomeDatabaseConnectionTests(unittest.TestCase):
    """Real connection tests for Reactome database adapters."""

    def test_arango_reactome_connection_and_datasource_creation(self) -> None:
        _require_env("ARANGO_URI", "ARANGO_USER", "ARANGO_PASSWORD")

        from lifelike_gds.arango_network import Reactome, ReactomeDB

        database = ReactomeDB(dbname="reactome")
        try:
            graphsource = Reactome(database)
            self.assertIs(graphsource.database, database)
            self.assertIsNotNone(database.db)
            self.assertIsNotNone(database.driver)
        finally:
            database.close()

    def test_neo4j_reactome_connection_and_datasource_creation(self) -> None:
        _require_env("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

        from lifelike_gds.neo4j_network import Reactome, ReactomeDB

        database = ReactomeDB(database="neo4j")
        try:
            graphsource = Reactome(database)
            self.assertIs(graphsource.database, database)
            self.assertIsNotNone(database.connection)
            self.assertIsNotNone(database.connection.driver)
            self.assertEqual(database.connection.database, "neo4j")
        finally:
            database.close()


class ReactomeGraphSourceLoadingTests(unittest.TestCase):
    """Real graph-loading tests for Reactome graph sources."""

    # def test_arango_reactome_graphsource_loads_graph_and_reports_size(self) -> None:
    #     _require_env("ARANGO_URI", "ARANGO_USER", "ARANGO_PASSWORD")

    #     from lifelike_gds.arango_network import Reactome, ReactomeDB
    #     from lifelike_gds.network.trace_graph_nx import TraceGraphNx

    #     database = ReactomeDB(dbname="reactome")
    #     try:
    #         graphsource = Reactome(database)
    #         tracegraph = TraceGraphNx(graphsource)
    #         tracegraph.init_default_graph(exclude_currency=False)

    #         num_nodes = tracegraph.graph.number_of_nodes()
    #         num_edges = tracegraph.graph.number_of_edges()

    #         self.assertGreater(num_nodes, 0, "Arango Reactome graph should contain nodes")
    #         self.assertGreater(num_edges, 0, "Arango Reactome graph should contain edges")
    #         print(f"Arango Reactome graph size: nodes={num_nodes}, edges={num_edges}")
    #     finally:
    #         database.close()

    def test_neo4j_reactome_graphsource_loads_graph_and_reports_size(self) -> None:
        _require_env("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

        from lifelike_gds.neo4j_network import Reactome, ReactomeDB
        from lifelike_gds.network.trace_graph_nx import TraceGraphNx

        database = ReactomeDB(database="neo4j")
        try:
            graphsource = Reactome(database)
            tracegraph = TraceGraphNx(graphsource)
            tracegraph.init_default_graph(exclude_currency=False)

            num_nodes = tracegraph.graph.number_of_nodes()
            num_edges = tracegraph.graph.number_of_edges()

            self.assertGreater(num_nodes, 0, "Neo4j Reactome graph should contain nodes")
            self.assertGreater(num_edges, 0, "Neo4j Reactome graph should contain edges")
            self.assertEqual(database.connection.database, "neo4j")
            print(f"Neo4j Reactome graph size: nodes={num_nodes}, edges={num_edges}")
        finally:
            database.close()


class ReactomeRealDataIntegrationTests(unittest.TestCase):
    """Integration tests that exercise real Reactome data through the public API."""

#     def test_arango_reactome_sample_node_lookup_and_detail_loading(self) -> None:
#         _require_env("ARANGO_URI", "ARANGO_USER", "ARANGO_PASSWORD")

#         from lifelike_gds.arango_network import Reactome, ReactomeDB
#         from lifelike_gds.network.trace_graph_nx import TraceGraphNx
#         from lifelike_gds.utils import get_id

#         database = ReactomeDB(dbname="biocyc")
#         try:
#             sample_query = """
#                 FOR n IN reactome
#                     FILTER n.displayName != null
#                     LIMIT 1
#                     RETURN {
#                         node_id: TO_NUMBER(n._key),
#                         displayName: n.displayName
#                     }
#             """
#             sample_df = database.get_dataframe(sample_query)
#             self.assertFalse(sample_df.empty, "Expected at least one Reactome node in ArangoDB")

#             node_id = int(sample_df.iloc[0]["node_id"])
#             display_name = str(sample_df.iloc[0]["displayName"])

#             matches = database.get_nodes_by_attr([display_name], "displayName")
#             self.assertGreater(len(matches), 0)
#             self.assertIn(node_id, {get_id(node) for node in matches})

#             graphsource = Reactome(database)
#             tracegraph = TraceGraphNx(graphsource)
#             tracegraph.graph.add_node(node_id)
#             graphsource.load_node_details([node_id], tracegraph.graph)

#             self.assertIn("displayName", tracegraph.graph.nodes[node_id])
#             self.assertEqual(tracegraph.graph.nodes[node_id]["displayName"], display_name)

#             export_df = graphsource.get_node_data_for_export([node_id], tracegraph.graph)
#             self.assertFalse(export_df.empty)
#             self.assertIn(node_id, export_df.index)
#             print(
#                 f"Arango Reactome sample node loaded successfully: "
#                 f"id={node_id}, displayName={display_name}"
#             )
#         finally:
#             database.close()

    def test_neo4j_reactome_sample_node_lookup_and_detail_loading(self) -> None:
        _require_env("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

        from lifelike_gds.neo4j_network import Reactome, ReactomeDB
        from lifelike_gds.network.trace_graph_nx import TraceGraphNx
        from lifelike_gds.utils import get_id

        database = ReactomeDB(database="neo4j")
        try:
            sample_query = """
                MATCH (n:PhysicalEntity)
                WHERE n.displayName IS NOT NULL
                RETURN elementId(n) AS node_id, n.displayName AS displayName
                LIMIT 1
            """
            sample_df = database.get_dataframe(sample_query)
            self.assertFalse(sample_df.empty, "Expected at least one Reactome node in Neo4j")

            node_id = str(sample_df.iloc[0]["node_id"])
            display_name = str(sample_df.iloc[0]["displayName"])

            matches = database.get_nodes_by_attr([display_name], "displayName")
            self.assertGreater(len(matches), 0)
            self.assertIn(node_id, {get_id(node) for node in matches})

            graphsource = Reactome(database)
            tracegraph = TraceGraphNx(graphsource)
            tracegraph.graph.add_node(node_id)
            graphsource.load_node_details([node_id], tracegraph.graph)

            self.assertIn("displayName", tracegraph.graph.nodes[node_id])
            self.assertEqual(tracegraph.graph.nodes[node_id]["displayName"], display_name)

            export_df = graphsource.get_node_data_for_export([node_id], tracegraph.graph)
            self.assertFalse(export_df.empty)
            self.assertIn(node_id, export_df.index)
            print(
                f"Neo4j Reactome sample node loaded successfully: "
                f"id={node_id}, displayName={display_name}"
            )
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()
