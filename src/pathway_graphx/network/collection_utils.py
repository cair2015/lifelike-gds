#!/usr/bin/env python3
import numpy as np
import pandas as pd
from scipy.stats import rankdata


def _argmax(x, n):
    """
    Get indexes of top n from x
    :param x: collection
    :param n: number of top values returned
    :return: unsorted indexes for top n values in x
    """
    if n >= len(x):
        return np.arange(len(x))  # return all, avoid ValueError and IndexError
    return np.argpartition(x, -n)[-n:]


def _argmax_ties(x, n):
    """
    Get indexes of values in x that are as large as the top n
    :param x: collection
    :param n: number of top values
    :return: unsorted indexes for entries in x, not necessarily n elements.
    """
    if n >= len(x):
        return np.arange(len(x))  # return all, avoid ValueError and IndexError
    return np.where(x >= np.partition(x, -n)[-n])[0]


def _argmin(x, n):
    """
    Get indexes of bottom n from x
    :param x: collection
    :param n: number of bottom values returned
    :return: unsorted indexes for top n values in x
    """
    if n >= len(x):
        return np.arange(len(x))  # return all, avoid ValueError and IndexError
    return np.argpartition(x, n)[:n]


def _argmin_ties(x, n):
    """
    Get indexes of values in x that are as small as the bottom n
    :param x: collection
    :param n: at least this number of bottom values returned
    :return: unsorted indexes for entries in x, not necessarily n elements.
    """
    if n >= len(x):
        return np.arange(len(x))  # return all, avoid ValueError and IndexError
    return np.where(x <= np.partition(x, n)[n - 1])[0]


def argmax(x, n):
    """
    Sorted version of _argmax
    :param x:
    :param n:
    :return:
    """
    idx = _argmax(x, n)
    return idx[np.argsort(np.take(x, idx))[::-1]]


def argmax_ties(x, n):
    """
    Sorted version of _argmax_ties
    :param x:
    :param n:
    :return:
    """
    idx = _argmax_ties(x, n)
    return idx[np.argsort(np.take(x, idx))[::-1]]


def argmin(x, n):
    """
    Sorted version of _argmin
    :param x:
    :param n:
    :return:
    """
    idx = _argmin(x, n)
    return idx[np.argsort(np.take(x, idx))]


def argmin_ties(x, n):
    """
    Sorted version of _argmin_ties
    :param x:
    :param n:
    :return:
    """
    idx = _argmin_ties(x, n)
    return idx[np.argsort(np.take(x, idx))]


def rank(a, desc=False):
    return rankdata(-a) if desc else rankdata(a)


def dict_keys(d):
    return np.asarray(list(d.keys()))


def dict_values(d):
    return np.asarray(list(d.values()))


def dict_take_values(d, keys):
    return np.asarray([d[k] for k in keys if k in d])


def dict_max(d, n=1):
    return dict_keys(d)[argmax(dict_values(d), n)]


def dict_max_ties(d, n=1):
    return dict_keys(d)[argmax_ties(dict_values(d), n)]


def dict_min(d, n=1):
    return dict_keys(d)[argmin(dict_values(d), n)]


def dict_min_ties(d, n=1):
    return dict_keys(d)[argmin_ties(dict_values(d), n)]


def dict_mul(*dicts):
    d1 = dicts[0]
    for d2 in dicts[1:]:
        assert d1.keys() == d2.keys()
        d1 = {k: v * d2[k] for k, v in d1.items()}
    return d1


def dict_func(d, f):
    """
    Perform potentially vectorized function on values of a dict.
    :param d: dict
    :param f: function given dict values as a numpy array
    :return: dict with keys from d and values changed with f
    """
    return dict(zip(dict_keys(d), f(dict_values(d))))


def dict_rank(d, desc=False):
    """
    Get the rank for dict values
    :param d:
    :param desc: descending order
    :return:
    """
    return dict_func(d, lambda a: rank(a, desc=desc))


def dict_take(d, keys):
    return {n: d[n] for n in keys if n in d}


def dict_del(d, keys):
    """
    Get a copy of dict without entries given in "keys"
    Unlike del, this doesn't throw errors if the keys are already not in dict.
    :param d: dict
    :param keys:
    :return: dict
    """
    return {n: d[n] for n in d.keys() - keys}


def dict2str(d):
    """
    Prettier representation of string, e.g. dict(a=1, b=2) -> a=1, b=2
    :param d: dict
    :return: string
    """
    return ", ".join(f"{k}={v}" for k, v in d.items())


def intersects(s1, s2):
    """
    Conveniently check if two collections intersect
    :param s1: collection
    :param s2: collection
    :return: bool
    """
    return not set(s1).isdisjoint(s2)


def union(*collections):
    """
    Convenient union that allows for no inputs and for first element in collections to not be a set, e.g. a list.
    :param collections: lists, sets, etc.
    :return: set union
    """
    return set.union(set(), *collections)


def agg_by_all(d, agg):
    """
    Aggregate a value for each record that are identical (except for the aggregation value).
    Aggregate with sum implemented.
    :param d: dict of lists. {"agg": [1, 1, 2, 1, ...], "key0": [...], "key2": [...]}.
        nth element of each list makes up a record
        Any scalar entry will be converted to a list of the full length as a side-effect
    :param agg: str key for dict where the entry contains the values to aggregate.
    :return: a dict of lists where each record is now unique.
    """
    df = pd.DataFrame(d)
    agg = df.groupby(list(d.keys() - {agg})).sum()
    return agg.reset_index().to_dict("list")
