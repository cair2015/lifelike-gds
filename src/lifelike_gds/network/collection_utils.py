"""Helpers for ranking, selecting, and aggregating collection-like data."""

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def _argmax(x, n):
    """Return unsorted indexes for the largest ``n`` values in ``x``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.argpartition(x, -n)[-n:]


def _argmax_ties(x, n):
    """Return unsorted indexes whose values are tied with the top ``n``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.where(x >= np.partition(x, -n)[-n])[0]


def _argmin(x, n):
    """Return unsorted indexes for the smallest ``n`` values in ``x``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.argpartition(x, n)[:n]


def _argmin_ties(x, n):
    """Return unsorted indexes whose values are tied with the bottom ``n``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.where(x <= np.partition(x, n)[n - 1])[0]


def argmax(x, n):
    """Return indexes for the largest ``n`` values in descending order."""
    idx = _argmax(x, n)
    return idx[np.argsort(np.take(x, idx))[::-1]]


def argmax_ties(x, n):
    """Return indexes tied with the top ``n`` values in descending order."""
    idx = _argmax_ties(x, n)
    return idx[np.argsort(np.take(x, idx))[::-1]]


def argmin(x, n):
    """Return indexes for the smallest ``n`` values in ascending order."""
    idx = _argmin(x, n)
    return idx[np.argsort(np.take(x, idx))]


def argmin_ties(x, n):
    """Return indexes tied with the bottom ``n`` values in ascending order."""
    idx = _argmin_ties(x, n)
    return idx[np.argsort(np.take(x, idx))]


def rank(a, desc=False):
    """Return 1-based ranks for ``a`` using SciPy's default tie behavior."""
    return rankdata(-a) if desc else rankdata(a)


def dict_keys(d):
    """Return dictionary keys as a NumPy array."""
    return np.asarray(list(d.keys()))


def dict_values(d):
    """Return dictionary values as a NumPy array."""
    return np.asarray(list(d.values()))


def dict_take_values(d, keys):
    """Return values for the subset of ``keys`` that exist in ``d``."""
    return np.asarray([d[k] for k in keys if k in d])


def dict_max(d, n=1):
    """Return the keys for the top ``n`` values in ``d``."""
    return dict_keys(d)[argmax(dict_values(d), n)]


def dict_max_ties(d, n=1):
    """Return keys tied with the top ``n`` values in ``d``."""
    return dict_keys(d)[argmax_ties(dict_values(d), n)]


def dict_min(d, n=1):
    """Return the keys for the bottom ``n`` values in ``d``."""
    return dict_keys(d)[argmin(dict_values(d), n)]


def dict_min_ties(d, n=1):
    """Return keys tied with the bottom ``n`` values in ``d``."""
    return dict_keys(d)[argmin_ties(dict_values(d), n)]


def dict_mul(*dicts):
    """Multiply matching values across dictionaries with identical keys."""
    d1 = dicts[0]
    for d2 in dicts[1:]:
        assert d1.keys() == d2.keys()
        d1 = {k: v * d2[k] for k, v in d1.items()}
    return d1


def dict_func(d, f):
    """Apply a function to dictionary values and rebuild a dictionary."""
    return dict(zip(dict_keys(d), f(dict_values(d))))


def dict_rank(d, desc=False):
    """Return ranks for dictionary values while preserving the keys."""
    return dict_func(d, lambda a: rank(a, desc=desc))


def dict_take(d, keys):
    """Return a new dictionary with the subset of keys present in ``d``."""
    return {n: d[n] for n in keys if n in d}


def dict_del(d, keys):
    """Return a copy of ``d`` without the given keys."""
    return {n: d[n] for n in d.keys() - keys}


def dict2str(d):
    """Format a dictionary as ``key=value`` pairs joined by commas."""
    return ", ".join(f"{k}={v}" for k, v in d.items())


def intersects(s1, s2):
    """Return ``True`` when the two collections share any element."""
    return not set(s1).isdisjoint(s2)


def union(*collections):
    """Return the set union of any number of collection inputs."""
    return set.union(set(), *collections)


def agg_by_all(d, agg):
    """
    Group identical records and sum the column named by ``agg``.

    ``d`` is expected to be a dictionary of column-like values that can be
    loaded into a DataFrame.
    """
    df = pd.DataFrame(d)
    agg = df.groupby(list(d.keys() - {agg})).sum()
    return agg.reset_index().to_dict("list")
