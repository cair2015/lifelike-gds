import pandas as pd

from lifelike_gds.graph_sources.domain_config import REACTOME_TRACE_NODE_LABEL
from lifelike_gds.graph_sources.reactome_db import ReactomeDB


def make_reactome_db():
    return object.__new__(ReactomeDB)


def test_reactome_db_summation_and_gene_name_queries():
    db = make_reactome_db()
    query_calls = []

    def fake_get_query_values(query, **parameters):
        query_calls.append((query, parameters))
        if "[:summation]" in query:
            return [{"id": "1", "text": "ATP summary"}, {"other": "ignored"}]
        return [{"id": "1", "geneNames": ["ATP1"]}, {"id": "2"}]

    db.get_query_values = fake_get_query_values

    assert db.get_summation_data([{"id": "1"}], node_label="Reactome") == {"1": "ATP summary"}
    assert db.get_gene_names([{"id": "1"}], node_label="Reactome") == {"1": ["ATP1"]}
    assert "MATCH (n:Reactome)-[:summation]->(s:Summation)" in query_calls[0][0]
    assert query_calls[0][1] == {"node_ids": ["1"]}
    assert "MATCH (n:Reactome)-[:referenceEntity]->(r)" in query_calls[1][0]
    assert query_calls[1][1] == {"node_ids": ["1"]}


def test_reactome_db_entity_and_reference_lookup_queries():
    db = make_reactome_db()
    run_calls = []

    def fake_run_query(query, **parameters):
        run_calls.append((query, parameters))
        if "referenceGene" in query and "phys:PhysicalEntity" in query:
            return [{"n": {"id": "11", "displayName": "Protein A"}}]
        if "referenceGene" in query:
            return [{"n": {"id": "12", "displayName": "Reference A"}}]
        if "phys:PhysicalEntity" in query:
            return [{"n": {"id": "21", "displayName": "Metabolite A"}}]
        return [{"n": {"id": "22", "displayName": "Ref Metabolite A"}}]

    db.run_query = fake_run_query

    entity_nodes = db.get_entity_nodes_by_gene_ids(["1017"], node_label="Reactome")
    ref_nodes = db.get_reference_nodes_by_gene_ids(["1017"], node_label="Reactome")
    chebi_nodes = db.get_entity_nodes_by_chebi_ids(["CHEBI:1"], node_label="Reactome")
    chebi_ref_nodes = db.get_reference_nodes_by_chebi_ids(["CHEBI:1"], node_label="Reactome")

    assert entity_nodes == [{"id": "11", "displayName": "Protein A"}]
    assert ref_nodes == [{"id": "12", "displayName": "Reference A"}]
    assert chebi_nodes == [{"id": "21", "displayName": "Metabolite A"}]
    assert chebi_ref_nodes == [{"id": "22", "displayName": "Ref Metabolite A"}]

    assert "n.databaseName = 'NCBI Gene'" in run_calls[0][0]
    assert run_calls[0][1] == {"genes": ["1017"]}
    assert "MATCH (r:Reactome:ReferenceEntity)" in run_calls[2][0]
    assert run_calls[2][1] == {"metabs": ["CHEBI:1"]}


def test_reactome_db_excel_query_passthrough():
    db = make_reactome_db()
    frame_calls = []
    expected = pd.DataFrame([{"id": "n1", "displayName": "ATP"}])

    def fake_get_dataframe(query, parameters=None):
        frame_calls.append((query, parameters))
        return expected

    db.get_dataframe = fake_get_dataframe

    result = db.get_node_data_for_excel(["n1"], node_label="Reactome")
    assert result.equals(expected)
    assert "OPTIONAL MATCH (n)-[:referenceEntity]->(r)" in frame_calls[0][0]
    assert frame_calls[0][1] == {"node_ids": ["n1"]}


def test_reactome_db_reference_entity_query_uses_optional_label():
    db = make_reactome_db()
    run_calls = []

    def fake_run_query(query, **parameters):
        run_calls.append((query, parameters))
        return [{"n": {"id": "33", "displayName": "Entity A"}}]

    db.run_query = fake_run_query

    nodes = db.get_reference_entity_nodes(
        ref_databasename="ChEBI",
        ref_identifiers=["CHEBI:1"],
        node_label=REACTOME_TRACE_NODE_LABEL,
    )

    assert nodes == [{"id": "33", "displayName": "Entity A"}]
    assert f"MATCH (n:{REACTOME_TRACE_NODE_LABEL})-[:referenceEntity]->(r)" in run_calls[0][0]
    assert "RETURN r AS n" in run_calls[0][0]
    assert run_calls[0][1] == {
        "ref_databasename": "ChEBI",
        "ref_identifiers": ["CHEBI:1"],
    }
