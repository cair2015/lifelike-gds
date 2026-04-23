"""Utility helpers used by the core network package."""

from __future__ import annotations

from numbers import Integral
from typing import Any, TypeAlias

IdValue: TypeAlias = int | str
IdSource: TypeAlias = Any

__all__ = ["get_id"]


def _normalize_id_value(value: Any) -> IdValue | Any:
    """Normalize common id representations to stable Python scalar values."""
    if isinstance(value, Integral) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return int(value) if value.isdigit() else value
    return value


def get_id(n: IdSource) -> IdValue:
    """
    Extract a node identifier from common node-like values.

    This helper accepts plain ids, dictionaries, and lightweight object records
    that expose one of the common id attributes used throughout the package.

    Args:
        n: Raw id value or node-like object.

    Returns:
        The normalized id as an ``int`` when numeric, otherwise a ``str``.

    Raises:
        KeyError: If no supported id field can be found.
    """
    if isinstance(n, Integral) and not isinstance(n, bool):
        return int(n)
    if isinstance(n, str):
        return int(n) if n.isdigit() else n
    if isinstance(n, dict):
        for key in ("id", "_key", "node_id", "element_id"):
            if key in n and n[key] is not None:
                return _normalize_id_value(n[key])
        if len(n) == 1:
            return get_id(next(iter(n.values())))
    if hasattr(n, "element_id"):
        return _normalize_id_value(n.element_id)
    if hasattr(n, "id"):
        return _normalize_id_value(n.id)
    if hasattr(n, "_key"):
        return _normalize_id_value(n._key)
    raise KeyError(f"Unable to determine node id for {n!r}")
