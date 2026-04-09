import numpy as np

from pathway_graphx.network.collection_utils import (
    agg_by_all,
    argmax,
    argmax_ties,
    argmin,
    argmin_ties,
    dict_del,
    dict_func,
    dict_max,
    dict_max_ties,
    dict_min,
    dict_min_ties,
    dict_mul,
    dict_rank,
    dict_take,
    dict_take_values,
    intersects,
    rank,
    union,
)


def test_arg_functions_sort_and_include_ties():
    values = np.array([5, 1, 5, 3, 1])

    assert list(argmax(values, 2)) == [2, 0]
    assert list(argmax_ties(values, 1)) == [2, 0]
    assert set(argmin(values, 2)) == {1, 4}
    assert list(values[argmin(values, 2)]) == [1, 1]
    assert set(argmin_ties(values, 1)) == {1, 4}
    assert list(values[argmin_ties(values, 1)]) == [1, 1]


def test_arg_functions_return_all_indexes_when_n_exceeds_length():
    values = np.array([4, 2, 3])

    assert list(argmax(values, 5)) == [0, 2, 1]
    assert list(argmin(values, 5)) == [1, 2, 0]


def test_rank_supports_ascending_and_descending_order():
    values = np.array([10, 20, 20, 30])

    assert list(rank(values)) == [1.0, 2.5, 2.5, 4.0]
    assert list(rank(values, desc=True)) == [4.0, 2.5, 2.5, 1.0]


def test_dict_selection_helpers_preserve_reference_behavior():
    values = {"a": 2, "b": 5, "c": 5, "d": 1}

    assert list(dict_take_values(values, ["b", "x", "a"])) == [5, 2]
    assert set(dict_max(values, 2)) == {"b", "c"}
    assert [values[key] for key in dict_max(values, 2)] == [5, 5]
    assert set(dict_max_ties(values, 1)) == {"b", "c"}
    assert [values[key] for key in dict_max_ties(values, 1)] == [5, 5]
    assert list(dict_min(values, 1)) == ["d"]
    assert set(dict_min_ties(values, 2)) == {"d", "a"}
    assert sorted(values[key] for key in dict_min_ties(values, 2)) == [1, 2]


def test_dict_transform_helpers_cover_subset_delete_rank_and_multiply():
    values = {"a": 2, "b": 5, "c": 5}

    assert dict_mul(values, {"a": 10, "b": 2, "c": 3}) == {
        "a": 20,
        "b": 10,
        "c": 15,
    }
    assert dict_func(values, lambda arr: arr + 1) == {"a": 3, "b": 6, "c": 6}
    assert dict_rank(values, desc=True) == {"a": 3.0, "b": 1.5, "c": 1.5}
    assert dict_take(values, ["c", "x", "a"]) == {"c": 5, "a": 2}
    assert dict_del(values, {"b", "z"}) == {"a": 2, "c": 5}


def test_set_helpers_and_aggregation_match_expected_behavior():
    assert intersects([1, 2], [2, 3]) is True
    assert intersects([1], [2, 3]) is False
    assert union([1, 2], {2, 3}, ()) == {1, 2, 3}

    records = {
        "group": ["x", "x", "y"],
        "kind": ["a", "a", "b"],
        "score": [1, 2, 4],
    }

    assert agg_by_all(records, "score") == {
        "group": ["x", "y"],
        "kind": ["a", "b"],
        "score": [3, 4],
    }
