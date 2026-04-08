"""Unit tests for the shortest-path smoke-test example."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


EXAMPLE_PATH = Path(__file__).resolve().parents[1] / 'examples' / 'simple_shortest_path_graph.py'


def load_example_module():
    """Load the example module directly from its file path."""
    spec = importlib.util.spec_from_file_location('simple_shortest_path_graph', EXAMPLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load example module from {EXAMPLE_PATH}')

    module = importlib.util.module_from_spec(spec)
    fake_dotenv = types.ModuleType('dotenv')
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    fake_pathway_graphx = types.ModuleType('pathway_graphx')
    fake_pathway_graphx.__path__ = []
    fake_network = types.ModuleType('pathway_graphx.network')
    fake_network.__path__ = []
    fake_shortest_paths_trace = types.ModuleType('pathway_graphx.network.shortest_paths_trace')
    fake_shortest_paths_trace.ShortestPathTrace = type('ShortestPathTrace', (), {})
    fake_utils = types.ModuleType('pathway_graphx.utils')
    fake_utils.get_id = lambda node: node['id']
    fake_utils.get_project_root = lambda: Path('/tmp')

    fake_modules = {
        'dotenv': fake_dotenv,
        'pathway_graphx': fake_pathway_graphx,
        'pathway_graphx.network': fake_network,
        'pathway_graphx.network.shortest_paths_trace': fake_shortest_paths_trace,
        'pathway_graphx.utils': fake_utils,
    }
    with patch.dict(sys.modules, fake_modules, clear=False):
        spec.loader.exec_module(module)
    return module


class BuildGraphSourceTests(unittest.TestCase):
    """Verify Neo4j Reactome database and graph-source construction."""

    def setUp(self) -> None:
        self.example = load_example_module()

    def test_build_graphsource_creates_neo4j_reactome_database_and_datasource(self) -> None:
        db_cls = MagicMock(name='neo4j_reactome_db_cls')
        graph_cls = MagicMock(name='neo4j_reactome_graph_cls')
        database_instance = object()
        graphsource_instance = object()
        db_cls.return_value = database_instance
        graph_cls.return_value = graphsource_instance

        fake_backend_module = types.ModuleType('pathway_graphx.graph_sources')
        fake_backend_module.ReactomeDB = db_cls
        fake_backend_module.Reactome = graph_cls

        with patch.dict(sys.modules, {'pathway_graphx.graph_sources': fake_backend_module}, clear=False):
            database, graphsource = self.example.build_graphsource(db_name='demo_neo4j')

        self.assertIs(database, database_instance)
        self.assertIs(graphsource, graphsource_instance)
        db_cls.assert_called_once_with(database='demo_neo4j')
        graph_cls.assert_called_once_with(database_instance)


class ExportShortestPathGraphLifecycleTests(unittest.TestCase):
    """Verify database connection lifecycle in the example runner."""

    def setUp(self) -> None:
        self.example = load_example_module()

    def test_export_shortest_path_graph_closes_database(self) -> None:
        database = MagicMock()
        graphsource = MagicMock()
        graphsource.get_node_name.side_effect = lambda node: node['name']

        source_node = {'id': 1, 'name': 'source'}
        target_node = {'id': 2, 'name': 'target'}

        tracegraph = MagicMock()
        tracegraph.write_to_sankey_file = MagicMock()
        tracegraph.add_shortest_paths.return_value = True

        with (
            patch.object(self.example, 'build_graphsource', return_value=(database, graphsource)),
            patch.object(self.example, 'ShortestPathTrace', return_value=tracegraph),
            patch.object(self.example, 'resolve_nodes', side_effect=[[source_node], [target_node]]),
            patch.object(self.example, 'get_id', side_effect=lambda node: node['id']),
        ):
            outfile = self.example.export_shortest_path_graph(
                source_prop='name',
                source_val='source',
                target_prop='name',
                target_val='target',
                output_dir=Path('/tmp/gds-test-output'),
                output_name='test.graph',
                db_name='demo',
            )

        self.assertEqual(outfile, Path('/tmp/gds-test-output/test.graph'))
        database.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
