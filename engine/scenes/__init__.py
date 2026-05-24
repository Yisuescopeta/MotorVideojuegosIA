"""Scene package exports.

Reexports are lazy so export runtime can import `engine.scenes.scene` without
pulling editor-only dependencies through `SceneManager`.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "Scene": ("engine.scenes.scene", "Scene"),
    "SceneManager": ("engine.scenes.scene_manager", "SceneManager"),
}

__all__ = list(_LAZY_IMPORTS)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    names = set(globals()) | set(__all__)
    return sorted(names)
