import logging
import numpy as np

# NOTE: Added this because of a circular import between biocyc_utils and trace_utils!


def get_groups(trace_network):
    """
    Get group integers for a list of traces. If a trace is not assigned a group an integer will be returned for it which will be unique for different node ids in the query end of the trace.
    :param trace_network: trace network dict
    :return: int vector.
    """
    traces = trace_network["traces"]
    groups = np.asarray([t.get("group", -1) for t in traces])
    undef = groups == -1
    if not undef.any():
        return groups

    track = "source" if trace_network["query"] == trace_network["sources"] else "target"
    nodes = np.asarray([t[track] for t in traces])
    # if any nodes have a group assigned in another trace then copy it to other traces for that node
    for n, g in zip(nodes, groups):
        if g != -1:
            groups[nodes == n] = g

    # make a pile of integers not already in use that we can assign to the unassigned groups
    unused_integers = np.arange(len(groups))
    unused_integers = unused_integers[~np.isin(unused_integers, groups)]

    # zip stops at shortest iterable so it automatically ignores excess unused integers
    sorted_nodes = sorted(list(set(nodes[undef])))
    for n, g in zip(sorted_nodes, unused_integers):
        groups[nodes == n] = g

    return groups


def set_default_groups(D):
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
