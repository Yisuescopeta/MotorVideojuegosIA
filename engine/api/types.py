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


class ShapeCastResult(TypedDict, total=False):
    """Resultado de query_physics_shape_cast."""

    hit: bool
    entity_id: int
    entity: str
    position: Dict[str, float]
    normal: Dict[str, float]
    fraction: float


class MotionTestResult(TypedDict, total=False):
    """Resultado de query_physics_motion (body_test_motion)."""

    travel_x: float
    travel_y: float
    remainder_x: float
    remainder_y: float
    collision_point_x: float
    collision_point_y: float
    collision_normal_x: float
    collision_normal_y: float
    collider_velocity_x: float
    collider_velocity_y: float
    collision_depth: float
    collision_safe_fraction: float
    collision_unsafe_fraction: float
    collision_local_shape: int
    collider_id: int
    collider_entity_name: str
    collider_shape: int


class ProfilerReport(TypedDict, total=False):
    """Reporte del profiler."""

    frame_time_ms: float
    systems: Dict[str, float]
    entity_count: int
