import importlib
import json
import sys
import types
from pathlib import Path

import networkx as nx
import numpy as np

from pathway_graphx.network.graph_utils import DirectedGraph


def load_graph_io_module():
    fake_excel_utils = types.ModuleType("pathway_graphx.utils.excel_utils")
    fake_excel_utils.write = lambda *args, **kwargs: None
    fake_utils_pkg = types.ModuleType("pathway_graphx.utils")
    fake_utils_pkg.__path__ = []

    original_excel = sys.modules.get("pathway_graphx.utils.excel_utils")
    original_utils = sys.modules.get("pathway_graphx.utils")
    sys.modules["pathway_graphx.utils"] = fake_utils_pkg
    sys.modules["pathway_graphx.utils.excel_utils"] = fake_excel_utils
    try:
        sys.modules.pop("pathway_graphx.network.graph_io", None)
        return importlib.import_module("pathway_graphx.network.graph_io")
    finally:
        if original_utils is not None:
            sys.modules["pathway_graphx.utils"] = original_utils
        else:
            sys.modules.pop("pathway_graphx.utils", None)
        if original_excel is not None:
            sys.modules["pathway_graphx.utils.excel_utils"] = original_excel
        else:
            sys.modules.pop("pathway_graphx.utils.excel_utils", None)


def test_serializable_node_link_data_converts_sets_and_numpy_ints():
    graph_io = load_graph_io_module()
    graph = DirectedGraph()
    graph.add_node("n1", tags={"a", "b"}, value=np.int64(4))
    graph.add_edge("n1", "n2", flags={"x"})

    data = graph_io.serializable_node_link_data(graph)

    node = next(node for node in data["nodes"] if node["id"] == "n1")
    assert sorted(node["tags"]) == ["a", "b"]
    assert node["value"] == 4
    edge_list = data.get("links", data.get("edges"))
    assert edge_list[0]["flags"] == ["x"]


def test_numpy_encoder_handles_core_numpy_types():
    graph_io = load_graph_io_module()

    payload = {
        "i": np.int64(3),
        "f": np.float64(1.5),
        "b": np.bool_(True),
        "a": np.array([1, 2]),
        "c": np.complex64(2 + 3j),
    }

    encoded = json.loads(json.dumps(payload, cls=graph_io.NumpyEncoder))
    assert encoded == {
        "i": 3,
        "f": 1.5,
        "b": True,
        "a": [1, 2],
        "c": {"real": 2.0, "imag": 3.0},
    }


def test_write_json_and_read_json_round_trip_plain_files(tmp_path):
    graph_io = load_graph_io_module()
    payload = {"name": "demo", "value": np.int64(5)}
    out = tmp_path / "graph.json"

    graph_io.write_json(payload, str(out))

    assert out.exists()
    assert graph_io.read_json(str(out)) == {"name": "demo", "value": 5}


def test_write_graphml_serializes_non_scalar_and_none_values(tmp_path):
    graph_io = load_graph_io_module()
    graph = nx.DiGraph()
    graph.add_node("a", labels=["x", "y"], optional=None)
    graph.add_node("b")
    graph.add_edge("a", "b", notes={"seen"}, weight=2)
    out = Path(tmp_path) / "demo.graphml"

    graph_io.write_graphml(str(out), graph)

    loaded = nx.read_graphml(out)
    assert loaded.nodes["a"]["labels"] == "['x', 'y']"
    assert "optional" not in loaded.nodes["a"]
    assert loaded.edges[("a", "b")]["notes"] == "{'seen'}"
