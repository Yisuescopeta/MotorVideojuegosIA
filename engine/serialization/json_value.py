from __future__ import annotations

import copy
from typing import Any


class FrozenJsonDict(dict):
    """Read-only dict used to retain JSON-like payloads safely."""

    def _readonly(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("FrozenJsonDict is read-only")

    __setitem__ = _readonly
    __delitem__ = _readonly
    clear = _readonly
    pop = _readonly
    popitem = _readonly
    setdefault = _readonly
    update = _readonly
    __ior__ = _readonly


class FrozenJsonList(list):
    """Read-only list used to retain JSON-like payloads safely."""

    def _readonly(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("FrozenJsonList is read-only")

    __setitem__ = _readonly
    __delitem__ = _readonly
    append = _readonly
    clear = _readonly
    extend = _readonly
    insert = _readonly
    pop = _readonly
    remove = _readonly
    reverse = _readonly
    sort = _readonly
    __iadd__ = _readonly
    __imul__ = _readonly


def freeze_json_value(value: Any) -> Any:
    """Recursively freeze JSON-like payloads while preserving scalar values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (FrozenJsonDict, FrozenJsonList)):
        return value
    if isinstance(value, dict):
        return FrozenJsonDict({key: freeze_json_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return FrozenJsonList(freeze_json_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze_json_value(item) for item in value)
    return copy.deepcopy(value)


def thaw_json_value(value: Any) -> Any:
    """Materialize frozen JSON-like payloads as plain serializable containers."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {key: thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [thaw_json_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(thaw_json_value(item) for item in value)
    return copy.deepcopy(value)


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
