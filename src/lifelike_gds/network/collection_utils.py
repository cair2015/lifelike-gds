"""Helpers for ranking, selecting, and aggregating collection-like data."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping
from typing import Any, TypeVar

import numpy as np
import pandas as pd
from scipy.stats import rankdata

K = TypeVar("K")
V = TypeVar("V", int, float, np.number)
T = TypeVar("T")


def _argmax(x: Collection[float], n: int) -> np.ndarray:
    """Return unsorted indexes for the largest ``n`` values in ``x``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.argpartition(x, -n)[-n:]


def _argmax_ties(x: Collection[float], n: int) -> np.ndarray:
    """Return unsorted indexes whose values are tied with the top ``n``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.where(x >= np.partition(x, -n)[-n])[0]


def _argmin(x: Collection[float], n: int) -> np.ndarray:
    """Return unsorted indexes for the smallest ``n`` values in ``x``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.argpartition(x, n)[:n]


def _argmin_ties(x: Collection[float], n: int) -> np.ndarray:
    """Return unsorted indexes whose values are tied with the bottom ``n``."""
    if n >= len(x):
        return np.arange(len(x))
    return np.where(x <= np.partition(x, n)[n - 1])[0]


def argmax(x: Collection[float], n: int) -> np.ndarray:
    """Return indexes for the largest ``n`` values in descending order."""
    idx = _argmax(x, n)
    return idx[np.argsort(np.take(x, idx))[::-1]]


def argmax_ties(x: Collection[float], n: int) -> np.ndarray:
    """Return indexes tied with the top ``n`` values in descending order."""
    idx = _argmax_ties(x, n)
    return idx[np.argsort(np.take(x, idx))[::-1]]


def argmin(x: Collection[float], n: int) -> np.ndarray:
    """Return indexes for the smallest ``n`` values in ascending order."""
    idx = _argmin(x, n)
    return idx[np.argsort(np.take(x, idx))]


def argmin_ties(x: Collection[float], n: int) -> np.ndarray:
    """Return indexes tied with the bottom ``n`` values in ascending order."""
    idx = _argmin_ties(x, n)
    return idx[np.argsort(np.take(x, idx))]


def rank(a: Collection[float], desc: bool = False) -> np.ndarray:
    """Return 1-based ranks for ``a`` using SciPy's default tie behavior."""
    return rankdata(-a) if desc else rankdata(a)


def dict_keys(d: Mapping[K, Any]) -> np.ndarray:
    """Return dictionary keys as a NumPy array."""
    return np.asarray(list(d.keys()))


def dict_values(d: Mapping[Any, V]) -> np.ndarray:
    """Return dictionary values as a NumPy array."""
    return np.asarray(list(d.values()))


def dict_take_values(d: Mapping[K, V], keys: Iterable[K]) -> np.ndarray:
    """Return values for the subset of ``keys`` that exist in ``d``."""
    return np.asarray([d[k] for k in keys if k in d])


def dict_max(d: Mapping[K, V], n: int = 1) -> np.ndarray:
    """Return the keys for the top ``n`` values in ``d``."""
    return dict_keys(d)[argmax(dict_values(d), n)]


def dict_max_ties(d: Mapping[K, V], n: int = 1) -> np.ndarray:
    """Return keys tied with the top ``n`` values in ``d``."""
    return dict_keys(d)[argmax_ties(dict_values(d), n)]


def dict_min(d: Mapping[K, V], n: int = 1) -> np.ndarray:
    """Return the keys for the bottom ``n`` values in ``d``."""
    return dict_keys(d)[argmin(dict_values(d), n)]


def dict_min_ties(d: Mapping[K, V], n: int = 1) -> np.ndarray:
    """Return keys tied with the bottom ``n`` values in ``d``."""
    return dict_keys(d)[argmin_ties(dict_values(d), n)]


def dict_mul(*dicts: Mapping[K, float]) -> dict[K, float]:
    """Multiply matching values across dictionaries with identical keys."""
    d1 = dicts[0]
    for d2 in dicts[1:]:
        assert d1.keys() == d2.keys()
        d1 = {k: v * d2[k] for k, v in d1.items()}
    return d1


def dict_func(d: Mapping[K, V], f: Callable[[np.ndarray], np.ndarray]) -> dict[K, Any]:
    """Apply a function to dictionary values and rebuild a dictionary."""
    return dict(zip(dict_keys(d), f(dict_values(d))))


def dict_rank(d: Mapping[K, float], desc: bool = False) -> dict[K, Any]:
    """Return ranks for dictionary values while preserving the keys."""
    return dict_func(d, lambda a: rank(a, desc=desc))


def dict_take(d: Mapping[K, V], keys: Iterable[K]) -> dict[K, V]:
    """Return a new dictionary with the subset of keys present in ``d``."""
    return {n: d[n] for n in keys if n in d}


def dict_del(d: Mapping[K, V], keys: Collection[K]) -> dict[K, V]:
    """Return a copy of ``d`` without the given keys."""
    return {n: d[n] for n in d.keys() - keys}


def dict2str(d: Mapping[Any, Any]) -> str:
    """Format a dictionary as ``key=value`` pairs joined by commas."""
    return ", ".join(f"{k}={v}" for k, v in d.items())


def intersects(s1: Collection[Any], s2: Collection[Any]) -> bool:
    """Return ``True`` when the two collections share any element."""
    return not set(s1).isdisjoint(s2)


def union(*collections: Collection[T]) -> set[T]:
    """Return the set union of any number of collection inputs."""
    return set.union(set(), *collections)


def agg_by_all(d: Mapping[str, Collection[Any]], agg: str) -> dict[str, list[Any]]:
    """
    Group identical records and sum the column named by ``agg``.

    ``d`` is expected to be a dictionary of column-like values that can be
    loaded into a DataFrame.
    """
    df = pd.DataFrame(d)
    agg = df.groupby(list(d.keys() - {agg})).sum()
    return agg.reset_index().to_dict("list")
