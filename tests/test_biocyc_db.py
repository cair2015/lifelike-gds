import pandas as pd

from pathway_graphx.graph_sources.biocyc_db import BiocycDB


def make_biocyc_db():
    db = object.__new__(BiocycDB)
    db.collection_label = "BioCyc"
    return db


def test_biocyc_db_projection_alias_passes_through_filters():
    db = make_biocyc_db()
    calls = []

    def fake_get_trace_graph_data(exclude_nodes=None, exclude_node_labels=None):
        calls.append(
            {
                "exclude_nodes": exclude_nodes,
                "exclude_node_labels": exclude_node_labels,
            }
        )
        return "nodes-frame", "rels-frame"

    db.get_trace_graph_data = fake_get_trace_graph_data

    result = db.get_graph_data_for_networkx(
        exclude_nodes=["b1"],
        exclude_node_labels=["CurrencyMetabolite"],
    )

    assert result == ("nodes-frame", "rels-frame")
    assert calls == [
        {
            "exclude_nodes": ["b1"],
            "exclude_node_labels": ["CurrencyMetabolite"],
        }
    ]


def test_biocyc_db_excel_query_passthrough():
    db = make_biocyc_db()
    frame_calls = []
    expected = pd.DataFrame([{"id": "b1", "displayName": "ATP"}])

    def fake_get_dataframe(query, **parameters):
        frame_calls.append((query, parameters))
        return expected

    db.get_dataframe = fake_get_dataframe

    result = db.get_node_data_for_excel(["b1"])
    assert result.equals(expected)
    assert "MATCH (n:BioCyc)" in frame_calls[0][0]
    assert "coalesce(n.displayName, n.name) AS displayName" in frame_calls[0][0]
    assert "[label IN labels(n) WHERE NOT label STARTS WITH 'db_'] AS labels" in frame_calls[0][0]
    assert frame_calls[0][1] == {"node_ids": ["b1"]}
