from __future__ import annotations

from typing import Any

from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.physics.types import (
    PhysicsBodySpec,
    PhysicsCollisionDetectionMode,
    PhysicsEntitySnapshot,
    PhysicsFilterSpec,
    PhysicsJointSpec,
    PhysicsJointType,
    PhysicsShapeSpec,
    PhysicsShapeType,
)

_VALID_BODY_TYPES = {"static", "dynamic", "kinematic"}
_VALID_SHAPE_TYPES = {"box", "circle", "polygon"}
_VALID_JOINT_TYPES = {"distance", "fixed"}
_VALID_CCD_MODES = {"discrete", "continuous"}


def snapshot_world(world: Any) -> list[PhysicsEntitySnapshot]:
    return [snapshot_entity(entity) for entity in world.get_all_entities()]


def snapshot_entity(entity: Any) -> PhysicsEntitySnapshot:
    transform = entity.get_component(Transform)
    rigidbody = entity.get_component(RigidBody)
    collider = entity.get_component(Collider)
    joint = entity.get_component(Joint2D)
    return PhysicsEntitySnapshot(
        entity_id=int(entity.id),
        entity_name=str(entity.name),
        layer=str(getattr(entity, "layer", "") or ""),
        transform_x=None if transform is None else float(transform.x),
        transform_y=None if transform is None else float(transform.y),
        transform_rotation=None if transform is None else float(transform.rotation),
        body=None if rigidbody is None else body_spec_from_component(rigidbody),
        shape=None if collider is None else shape_spec_from_component(collider, layer=str(getattr(entity, "layer", "") or "")),
        joint=None if joint is None else joint_spec_from_component(joint),
    )


def body_spec_from_component(rigidbody: RigidBody) -> PhysicsBodySpec:
    body_type = str(rigidbody.body_type or "dynamic")
    if body_type not in _VALID_BODY_TYPES:
        body_type = "dynamic"
    collision_detection_mode = str(rigidbody.collision_detection_mode or "discrete")
    if collision_detection_mode not in _VALID_CCD_MODES:
        collision_detection_mode = "discrete"
    return PhysicsBodySpec(
        body_type=body_type,  # type: ignore[arg-type]
        simulated=bool(rigidbody.simulated),
        gravity_scale=float(rigidbody.gravity_scale),
        velocity_x=float(rigidbody.velocity_x),
        velocity_y=float(rigidbody.velocity_y),
        freeze_x=bool(rigidbody.freeze_x),
        freeze_y=bool(rigidbody.freeze_y),
        use_full_kinematic_contacts=bool(rigidbody.use_full_kinematic_contacts),
        collision_detection_mode=collision_detection_mode,  # type: ignore[arg-type]
    )


def shape_spec_from_component(collider: Collider, *, layer: str = "") -> PhysicsShapeSpec:
    shape_type = str(collider.shape_type or "box")
    if shape_type not in _VALID_SHAPE_TYPES:
        shape_type = "box"
    return PhysicsShapeSpec(
        shape_type=shape_type,  # type: ignore[arg-type]
        enabled=bool(collider.enabled),
        width=float(collider.width),
        height=float(collider.height),
        radius=float(collider.radius),
        offset_x=float(collider.offset_x),
        offset_y=float(collider.offset_y),
        points=tuple(
            (float(point[0]), float(point[1]))
            for point in collider.points
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ),
        friction=float(collider.friction),
        restitution=float(collider.restitution),
        density=float(collider.density),
        filter=PhysicsFilterSpec(
            layer=str(layer or ""),
            is_sensor=bool(collider.is_trigger),
        ),
    )


def joint_spec_from_component(joint: Joint2D) -> PhysicsJointSpec:
    joint_type = str(joint.joint_type or "distance")
    if joint_type not in _VALID_JOINT_TYPES:
        joint_type = "distance"
    return PhysicsJointSpec(
        enabled=bool(joint.enabled),
        joint_type=joint_type,  # type: ignore[arg-type]
        connected_entity=str(joint.connected_entity or ""),
        anchor_x=float(joint.anchor_x),
        anchor_y=float(joint.anchor_y),
        connected_anchor_x=float(joint.connected_anchor_x),
        connected_anchor_y=float(joint.connected_anchor_y),
        rest_length=float(joint.rest_length),
        damping_ratio=float(joint.damping_ratio),
        frequency_hz=float(joint.frequency_hz),
        collide_connected=bool(joint.collide_connected),
    )


def build_body_signature(snapshot: PhysicsEntitySnapshot) -> tuple[Any, ...] | None:
    shape = snapshot.shape
    if shape is None:
        return None
    body = snapshot.body
    return (
        snapshot.entity_name,
        str(shape.shape_type),
        float(shape.width),
        float(shape.height),
        float(shape.radius),
        tuple((float(point[0]), float(point[1])) for point in shape.points),
        float(shape.offset_x),
        float(shape.offset_y),
        bool(shape.filter.is_sensor),
        float(shape.friction),
        float(shape.restitution),
        float(shape.density),
        None
        if body is None
        else (
            body.body_type,
            float(body.gravity_scale),
            bool(body.freeze_x),
            bool(body.freeze_y),
            str(body.collision_detection_mode),
        ),
    )


def build_joint_signature(snapshot: PhysicsEntitySnapshot) -> tuple[Any, ...] | None:
    joint = snapshot.joint
    if joint is None:
        return None
    return (
        joint.joint_type,
        joint.connected_entity,
        float(joint.anchor_x),
        float(joint.anchor_y),
        float(joint.connected_anchor_x),
        float(joint.connected_anchor_y),
        float(joint.rest_length),
        float(joint.damping_ratio),
        float(joint.frequency_hz),
        bool(joint.collide_connected),
    )
