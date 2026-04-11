import lifelike_gds.graph_sources as graph_sources


def test_graph_sources_package_exports_expected_symbols():
    assert graph_sources.__all__ == [
        "Biocyc",
        "BiocycDB",
        "Database",
        "GraphSource",
        "Neo4jConnection",
        "Neo4jQueryBuilder",
        "Reactome",
        "ReactomeDB",
        "TraceGraphNx",
        "read_config",
    ]

    for name in graph_sources.__all__:
        assert hasattr(graph_sources, name)
