import pathway_graphx


def test_package_init_has_expected_docstring():
    assert pathway_graphx.__doc__ == "PathwayGraphX package for Neo4j and Reactome graph analysis."
