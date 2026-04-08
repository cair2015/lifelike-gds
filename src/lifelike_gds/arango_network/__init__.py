"""
ArangoDB backend adapters for lifelike_gds.

This package contains Arango-specific connection, query, and graph-source
implementations. Shared network analysis logic lives in ``lifelike_gds.network``.
"""

from lifelike_gds.arango_network.database import Database, GraphSource
from lifelike_gds.arango_network.biocyc_db import Biocyc, BiocycDB
from lifelike_gds.arango_network.reactome_db import Reactome, ReactomeDB

__all__ = [
    "Biocyc",
    "BiocycDB",
    "Database",
    "GraphSource",
    "Reactome",
    "ReactomeDB",
]
