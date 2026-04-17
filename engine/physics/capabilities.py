from __future__ import annotations

from dataclasses import dataclass

from engine.physics.types import PhysicsBodyType, PhysicsJointType, PhysicsShapeType


@dataclass(frozen=True)
class PhysicsBackendCapabilities:
    backend_name: str
    body_types: tuple[PhysicsBodyType, ...]
    shape_types: tuple[PhysicsShapeType, ...]
    joint_types: tuple[PhysicsJointType, ...]
    supports_ray_queries: bool
    supports_aabb_queries: bool
    supports_contact_events: bool
    supports_contact_normals: bool
    supports_materials: bool
    supports_ccd: bool
    supports_sensors: bool
    supports_runtime_body_sync: bool
    supports_collision_masks: bool = False
    supports_shape_queries: bool = False


_BACKEND_CAPABILITIES: dict[str, PhysicsBackendCapabilities] = {
    "legacy_aabb": PhysicsBackendCapabilities(
        backend_name="legacy_aabb",
        body_types=("static", "dynamic", "kinematic"),
        shape_types=("box",),
        joint_types=(),
        supports_ray_queries=True,
        supports_aabb_queries=True,
        supports_contact_events=True,
        supports_contact_normals=False,
        supports_materials=False,
        supports_ccd=True,
        supports_sensors=True,
        supports_runtime_body_sync=False,
    ),
    "box2d": PhysicsBackendCapabilities(
        backend_name="box2d",
        body_types=("static", "dynamic", "kinematic"),
        shape_types=("box", "circle", "polygon"),
        joint_types=("distance", "fixed"),
        supports_ray_queries=True,
        supports_aabb_queries=True,
        supports_contact_events=True,
        supports_contact_normals=True,
        supports_materials=True,
        supports_ccd=True,
        supports_sensors=True,
        supports_runtime_body_sync=True,
    ),
}


def get_backend_capabilities(backend_name: str) -> PhysicsBackendCapabilities | None:
    return _BACKEND_CAPABILITIES.get(str(backend_name or "").strip())


def list_backend_capabilities() -> list[PhysicsBackendCapabilities]:
    return [_BACKEND_CAPABILITIES[name] for name in sorted(_BACKEND_CAPABILITIES)]
