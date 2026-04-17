from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, TypedDict

PhysicsBodyType = Literal["static", "dynamic", "kinematic"]
PhysicsShapeType = Literal["box", "circle", "polygon"]
PhysicsJointType = Literal["distance", "fixed"]
PhysicsCollisionDetectionMode = Literal["discrete", "continuous"]


class PhysicsPoint(TypedDict):
    x: float
    y: float


class PhysicsRayHit(TypedDict, total=False):
    entity: str
    entity_id: int
    distance: float
    point: PhysicsPoint
    normal: PhysicsPoint
    is_trigger: bool


class PhysicsAABBHit(TypedDict):
    entity: str
    entity_id: int
    is_trigger: bool


class PhysicsBackendInfo(TypedDict):
    name: str
    available: bool
    unavailable_reason: Optional[str]


class PhysicsBackendSelection(TypedDict):
    requested_backend: str
    effective_backend: Optional[str]
    used_fallback: bool
    fallback_reason: Optional[str]
    unavailable_reason: Optional[str]


@dataclass(frozen=True)
class PhysicsContact:
    entity_a: str
    entity_b: str
    entity_a_id: int
    entity_b_id: int
    is_trigger: bool


@dataclass(frozen=True)
class PhysicsFilterSpec:
    layer: str = ""
    is_sensor: bool = False
    category_bits: int | None = None
    mask_bits: int | None = None
    group_index: int | None = None


@dataclass(frozen=True)
class PhysicsBodySpec:
    body_type: PhysicsBodyType = "static"
    simulated: bool = True
    gravity_scale: float = 1.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    freeze_x: bool = False
    freeze_y: bool = False
    use_full_kinematic_contacts: bool = False
    collision_detection_mode: PhysicsCollisionDetectionMode = "discrete"


@dataclass(frozen=True)
class PhysicsShapeSpec:
    shape_type: PhysicsShapeType = "box"
    enabled: bool = True
    width: float = 0.0
    height: float = 0.0
    radius: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    points: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    friction: float = 0.2
    restitution: float = 0.0
    density: float = 1.0
    filter: PhysicsFilterSpec = field(default_factory=PhysicsFilterSpec)


@dataclass(frozen=True)
class PhysicsJointSpec:
    enabled: bool = True
    joint_type: PhysicsJointType = "distance"
    connected_entity: str = ""
    anchor_x: float = 0.0
    anchor_y: float = 0.0
    connected_anchor_x: float = 0.0
    connected_anchor_y: float = 0.0
    rest_length: float = 0.0
    damping_ratio: float = 0.0
    frequency_hz: float = 0.0
    collide_connected: bool = False


@dataclass(frozen=True)
class PhysicsEntitySnapshot:
    entity_id: int
    entity_name: str
    layer: str = ""
    transform_x: float | None = None
    transform_y: float | None = None
    transform_rotation: float | None = None
    body: PhysicsBodySpec | None = None
    shape: PhysicsShapeSpec | None = None
    joint: PhysicsJointSpec | None = None

    @property
    def has_transform(self) -> bool:
        return (
            self.transform_x is not None
            and self.transform_y is not None
            and self.transform_rotation is not None
        )
