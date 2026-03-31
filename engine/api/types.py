"""
engine/api/types.py - Data contracts for the public API.
"""

from typing import Any, Dict, Optional, TypedDict

from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection


class Vector2D(TypedDict):
    x: float
    y: float


class ComponentData(TypedDict):
    """Generic component payload."""

    type: str
    properties: Dict[str, Any]


class EntityData(TypedDict):
    """Serializable entity snapshot returned by EngineAPI."""

    name: str
    active: bool
    tag: str
    layer: str
    parent: Optional[str]
    prefab_instance: Optional[Any]
    components: Dict[str, Any]
    component_metadata: Dict[str, Dict[str, Any]]


class ActionResult(TypedDict):
    """Outcome for an EngineAPI action."""

    success: bool
    message: Optional[str]
    data: Optional[Any]


class EngineStatus(TypedDict):
    """Current runtime status."""

    state: str
    frame: int
    time: float
    fps: int
    entity_count: int
