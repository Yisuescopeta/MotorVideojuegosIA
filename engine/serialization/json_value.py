from __future__ import annotations

import copy
from typing import Any


def clone_json_value(value: Any) -> Any:
    """Clone serializable data, reserving deepcopy for unsupported values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        if all(item is None or isinstance(item, (bool, int, float, str)) for item in value.values()):
            return value.copy()
        return {key: clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        if all(item is None or isinstance(item, (bool, int, float, str)) for item in value):
            return value.copy()
        return [clone_json_value(item) for item in value]
    if isinstance(value, tuple):
        if all(item is None or isinstance(item, (bool, int, float, str)) for item in value):
            return value
        return tuple(clone_json_value(item) for item in value)
    return copy.deepcopy(value)
