import lifelike_gds


def test_package_init_has_expected_docstring():
    assert lifelike_gds.__doc__ == "Lifelike GDS package for Neo4j and Reactome graph analysis."
