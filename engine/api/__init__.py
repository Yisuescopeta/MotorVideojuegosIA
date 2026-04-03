"""
engine/api/__init__.py - Exposición pública de la API

Permite importar:
    from engine.api import EngineAPI, EngineError, EntityData
"""

from engine.api.engine_api import EngineAPI
from engine.api.errors import (
    ComponentNotFoundError,
    EngineError,
    EntityNotFoundError,
    InvalidOperationError,
    LevelLoadError,
)
from engine.api.types import ActionResult, ComponentData, EngineStatus, EntityData, Vector2D
from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection

__all__ = [
    "EngineAPI",
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
]
