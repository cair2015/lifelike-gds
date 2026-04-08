"""Integration tests for real Neo4j Reactome database connections."""

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
    """Real connection tests for Neo4j Reactome adapters."""

    def test_neo4j_reactome_connection_and_datasource_creation(self) -> None:
        _require_env('NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD')

        from pathway_graphx.graph_sources import Reactome, ReactomeDB

        database = ReactomeDB(database='neo4j')
        try:
            graphsource = Reactome(database)
            self.assertIs(graphsource.database, database)
            self.assertIsNotNone(database.connection)
            self.assertIsNotNone(database.connection.driver)
            self.assertEqual(database.connection.database, 'neo4j')
        finally:
            database.close()


class ReactomeGraphSourceLoadingTests(unittest.TestCase):
    """Real graph-loading tests for Neo4j Reactome graph sources."""

    def test_neo4j_reactome_graphsource_loads_graph_and_reports_size(self) -> None:
        _require_env('NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD')

        from pathway_graphx.graph_sources import Reactome, ReactomeDB
        from pathway_graphx.network.trace_graph_nx import TraceGraphNx

        database = ReactomeDB(database='neo4j')
        try:
            graphsource = Reactome(database)
            tracegraph = TraceGraphNx(graphsource)
            tracegraph.init_default_graph(exclude_currency=False)

            num_nodes = tracegraph.graph.number_of_nodes()
            num_edges = tracegraph.graph.number_of_edges()

            self.assertGreater(num_nodes, 0, 'Neo4j Reactome graph should contain nodes')
            self.assertGreater(num_edges, 0, 'Neo4j Reactome graph should contain edges')
            self.assertEqual(database.connection.database, 'neo4j')
        finally:
            database.close()


class ReactomeRealDataIntegrationTests(unittest.TestCase):
    """Integration tests that exercise real Reactome data through the public API."""

    def test_neo4j_reactome_sample_node_lookup_and_detail_loading(self) -> None:
        _require_env('NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD')

        from pathway_graphx.graph_sources import Reactome, ReactomeDB
        from pathway_graphx.network.trace_graph_nx import TraceGraphNx
        from pathway_graphx.utils import get_id

        database = ReactomeDB(database='neo4j')
        try:
            sample_query = """
                MATCH (n:PhysicalEntity)
                WHERE n.displayName IS NOT NULL
                RETURN elementId(n) AS node_id, n.displayName AS displayName
                LIMIT 1
            """
            sample_df = database.get_dataframe(sample_query)
            self.assertFalse(sample_df.empty, 'Expected at least one Reactome node in Neo4j')

            node_id = str(sample_df.iloc[0]['node_id'])
            display_name = str(sample_df.iloc[0]['displayName'])

            matches = database.get_nodes_by_attr([display_name], 'displayName')
            self.assertGreater(len(matches), 0)
            self.assertIn(node_id, {get_id(node) for node in matches})

            graphsource = Reactome(database)
            tracegraph = TraceGraphNx(graphsource)
            tracegraph.graph.add_node(node_id)
            graphsource.load_node_details([node_id], tracegraph.graph)

            self.assertIn('displayName', tracegraph.graph.nodes[node_id])
            self.assertEqual(tracegraph.graph.nodes[node_id]['displayName'], display_name)

            export_df = graphsource.get_node_data_for_export([node_id], tracegraph.graph)
            self.assertFalse(export_df.empty)
            self.assertIn(node_id, export_df.index)
        finally:
            database.close()


if __name__ == '__main__':
    unittest.main()
