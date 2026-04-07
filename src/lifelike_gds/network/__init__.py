"""
Generic Network Analysis Module

Provides database-agnostic graph analysis algorithms and utilities.
This module includes foundational classes and algorithms that work
with any database backend through the GraphSource interface.
"""

from lifelike_gds.network.graph_source import GraphSource

__all__ = ["GraphSource"]
