"""Helpers for assigning stable group ids to trace records."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np


def get_groups(trace_network: dict[str, Any]) -> np.ndarray:
    """
    Return group ids for each trace in a trace-network payload.

    Existing groups are preserved. Missing groups are assigned so that traces
    sharing the relevant query-side node receive the same group id.
    """
    traces = trace_network["traces"]
    groups = np.asarray([t.get("group", -1) for t in traces])
    undef = groups == -1
    if not undef.any():
        return groups

    track = "source" if trace_network["query"] == trace_network["sources"] else "target"
    nodes = np.asarray([t[track] for t in traces])

    # If a node already has a defined group in one trace, reuse it for the others.
    for n, g in zip(nodes, groups):
        if g != -1:
            groups[nodes == n] = g

    # Recompute undefined positions after inheriting any existing groups.
    undef = groups == -1
    unused_integers = np.arange(len(groups))
    unused_integers = unused_integers[~np.isin(unused_integers, groups)]

    # ``zip`` stops at the shortest iterable, which naturally handles excess ids.
    sorted_nodes = sorted(list(set(nodes[undef])))
    for n, g in zip(sorted_nodes, unused_integers):
        groups[nodes == n] = g

    return groups


def set_default_groups(D: Any) -> None:
    """
    Populate missing ``group`` fields across the graph's trace networks.

    Args:
        D: Graph whose ``graph["trace_networks"]`` payload should be normalized.
    """
    if "trace_networks" not in D.graph:
        logging.warning("No trace networks to set group for.")
    elif all("group" in t for tn in D.graph["trace_networks"] for t in tn["traces"]):
        logging.info("All traces already have their group defined.")
    else:
        for tn in D.graph["trace_networks"]:
            for t, g in zip(tn["traces"], get_groups(tn)):
                if "group" in t:
                    assert t["group"] == g, "Bug in get_groups"
                else:
                    t["group"] = g
