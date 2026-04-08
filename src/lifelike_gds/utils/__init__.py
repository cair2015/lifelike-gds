from numbers import Integral

from lifelike_gds.utils.path_utils import get_project_root


def _normalize_id_value(value):
    if isinstance(value, Integral) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        return int(value) if value.isdigit() else value
    return value


def get_id(n):
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
