"""
engine/api/__init__.py - Exposición pública de la API

Permite importar:
    from engine.api import EngineAPI, EngineError, EntityData
"""

from __future__ import annotations

import importlib
from typing import Any

from engine.api.errors import (
    ComponentNotFoundError,
    EngineError,
    EntityNotFoundError,
    InvalidOperationError,
    LevelLoadError,
)
from engine.api.types import ActionResult, ComponentData, EngineStatus, EntityData, Vector2D
from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EngineAPI": ("engine.api.engine_api", "EngineAPI"),
}

__all__ = [
    "EngineError",
    "EntityNotFoundError",
    "ComponentNotFoundError",
    "InvalidOperationError",
    "LevelLoadError",
    "EngineStatus",
    "EntityData",
    "ComponentData",
    "ActionResult",
    "Vector2D",
    "PhysicsBackendInfo",
    "PhysicsBackendSelection",
    "EngineAPI",
]


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
