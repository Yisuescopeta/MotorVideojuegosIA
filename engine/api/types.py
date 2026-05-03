"""
engine/api/types.py - Data contracts for the public API.
"""

from typing import Dict, List, Optional, TypedDict, Union


class Vector2D(TypedDict):
    x: float
    y: float


class ComponentData(TypedDict):
    """Generic component payload."""

    type: str
    properties: Dict[str, Union[str, int, float, bool, list, dict, None]]


class EntityData(TypedDict):
    """Serializable entity snapshot returned by EngineAPI."""

    name: str
    active: bool
    tag: str
    layer: str
    parent: Optional[str]
    prefab_instance: Optional[dict]
    components: Dict[str, Dict[str, Union[str, int, float, bool, list, dict, None]]]
    component_metadata: Dict[str, Dict[str, Union[str, int, float, bool, list, dict, None]]]


class ActionResult(TypedDict):
    """Outcome for an EngineAPI action."""

    success: bool
    message: Optional[str]
    data: Optional[Union[Dict, List, str, int, float, bool, None]]


class EngineStatus(TypedDict):
    """Current runtime status."""

    state: str
    frame: int
    time: float
    fps: int
    entity_count: int


class PhysicsRayResult(TypedDict, total=False):
    """Result of query_physics_ray."""

    hit: bool
    entity_id: str
    point: Dict[str, float]
    normal: Dict[str, float]
    distance: float


class PhysicsAABBResult(TypedDict, total=False):
    """Result of query_physics_aabb."""

    entities: List[Dict[str, object]]


class ProfilerReport(TypedDict, total=False):
    """Reporte del profiler."""

    frame_time_ms: float
    systems: Dict[str, float]
    entity_count: int
