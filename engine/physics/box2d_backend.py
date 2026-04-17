from __future__ import annotations

import math
from typing import Any, Optional

from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.physics.backend import PhysicsAABBHit, PhysicsBackend, PhysicsContact, PhysicsRayHit
from engine.physics.ecs_adapter import build_body_signature, build_joint_signature, snapshot_world
from engine.physics.types import PhysicsBodySpec, PhysicsEntitySnapshot

try:
    from Box2D import (
        b2AABB,
        b2ContactListener,
        b2QueryCallback,
        b2RayCastCallback,
        b2Vec2,
        b2World,
    )
except Exception:  # pragma: no cover - optional dependency path
    b2AABB = None
    b2ContactListener = object
    b2QueryCallback = object
    b2RayCastCallback = object
    b2Vec2 = None
    b2World = None


class _ContactListener(b2ContactListener):  # type: ignore[misc]
    def __init__(self, owner: "Box2DPhysicsBackend") -> None:
        super().__init__()
        self._owner = owner

    def BeginContact(self, contact: Any) -> None:  # noqa: N802
        self._owner._on_begin_contact(contact)


class _RayCastCollector(b2RayCastCallback):  # type: ignore[misc]
    def __init__(self, hits: list[PhysicsRayHit], max_distance: float) -> None:
        super().__init__()
        self._hits = hits
        self._max_distance = float(max_distance)

    def ReportFixture(self, fixture: Any, point: Any, normal: Any, fraction: float) -> float:  # noqa: N802
        body = fixture.body
        entity_id = int(body.userData["entity_id"])
        self._hits.append(
            {
                "entity": body.userData["entity_name"],
                "entity_id": entity_id,
                "distance": float(self._max_distance * fraction),
                "point": {"x": float(point[0]), "y": float(point[1])},
                "normal": {"x": float(normal[0]), "y": float(normal[1])},
                "is_trigger": bool(fixture.sensor),
            }
        )
        return 1.0


class _AABBQueryCollector(b2QueryCallback):  # type: ignore[misc]
    def __init__(self, hits: dict[int, PhysicsAABBHit]) -> None:
        super().__init__()
        self._hits = hits

    def ReportFixture(self, fixture: Any) -> bool:  # noqa: N802
        body = fixture.body
        entity_id = int(body.userData["entity_id"])
        self._hits[entity_id] = {
            "entity": body.userData["entity_name"],
            "entity_id": entity_id,
            "is_trigger": bool(fixture.sensor),
        }
        return True


class Box2DPhysicsBackend(PhysicsBackend):
    backend_name = "box2d"

    def __init__(self, gravity: float = 600.0, event_bus: Optional[Any] = None, fixed_dt: float = 1.0 / 60.0) -> None:
        if b2World is None:
            raise RuntimeError("Box2D python package is not available")
        self._event_bus = event_bus
        self._gravity = float(gravity)
        self._fixed_dt = float(fixed_dt)
        self._accumulator = 0.0
        self._world = b2World(gravity=(0.0, self._gravity), doSleep=True)
        self._listener = _ContactListener(self)
        self._world.contactListener = self._listener
        self._bodies: dict[int, Any] = {}
        self._signatures: dict[int, tuple[Any, ...]] = {}
        self._joints: dict[int, Any] = {}
        self._joint_signatures: dict[int, tuple[Any, ...]] = {}
        self._latest_contacts: list[PhysicsContact] = []
        self._step_metrics: dict[str, float] = {"substeps": 0, "contacts": 0, "ccd_bodies": 0, "joints": 0}

    def set_event_bus(self, event_bus: Optional[Any]) -> None:
        self._event_bus = event_bus

    def sync_world(self, world: Any) -> None:
        snapshots = snapshot_world(world)
        current_ids = {snapshot.entity_id for snapshot in snapshots}
        snapshots_by_id = {snapshot.entity_id: snapshot for snapshot in snapshots}
        snapshots_by_name = {snapshot.entity_name: snapshot for snapshot in snapshots}

        for entity_id in list(set(self._bodies.keys()) - current_ids):
            self.destroy_body(entity_id)
        for joint_id in list(set(self._joints.keys()) - current_ids):
            self._destroy_joint(joint_id)

        for snapshot in snapshots:
            if not snapshot.has_transform or snapshot.shape is None or not snapshot.shape.enabled:
                self.destroy_body(snapshot.entity_id)
                continue
            self._sync_body_from_snapshot(snapshot)

        self._sync_joints(snapshots_by_id, snapshots_by_name)

    def destroy_body(self, entity_id: int) -> None:
        body = self._bodies.pop(int(entity_id), None)
        self._signatures.pop(int(entity_id), None)
        if body is not None:
            self._world.DestroyBody(body)

    def _sync_body_from_snapshot(self, snapshot: PhysicsEntitySnapshot) -> None:
        shape = snapshot.shape
        if not snapshot.has_transform or shape is None or not shape.enabled:
            return
        signature = build_body_signature(snapshot)
        if signature is None:
            return
        body = self._bodies.get(int(snapshot.entity_id))
        if self._signatures.get(snapshot.entity_id) == signature:
            if body is not None:
                self._sync_body_runtime_state(body, snapshot)
            return
        self.destroy_body(snapshot.entity_id)
        body = self._create_body_for_snapshot(snapshot)
        self._bodies[snapshot.entity_id] = body
        self._signatures[snapshot.entity_id] = signature

    def step(self, world: Any, dt: float) -> None:
        self.sync_world(world)
        self._latest_contacts = []
        self._step_metrics = {"substeps": 0, "contacts": 0, "ccd_bodies": 0, "joints": len(self._joints)}
        self._accumulator += float(dt)
        while self._accumulator >= self._fixed_dt:
            self._world.Step(self._fixed_dt, 8, 3)
            self._accumulator -= self._fixed_dt
            self._step_metrics["substeps"] += 1
        self._world.ClearForces()
        self._sync_world_from_box2d(world)
        self._step_metrics["contacts"] = len(self._latest_contacts)

    def query_ray(
        self,
        world: Any,
        origin: tuple[float, float],
        direction: tuple[float, float],
        max_distance: float,
    ) -> list[PhysicsRayHit]:
        self.sync_world(world)
        ox, oy = float(origin[0]), float(origin[1])
        dx, dy = float(direction[0]), float(direction[1])
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return []
        target = (ox + (dx / length) * max_distance, oy + (dy / length) * max_distance)
        hits: list[PhysicsRayHit] = []
        self._world.RayCast(_RayCastCollector(hits, max_distance), (ox, oy), target)
        return sorted(hits, key=lambda item: (item["distance"], item["entity_id"]))

    def query_aabb(self, world: Any, bounds: tuple[float, float, float, float]) -> list[PhysicsAABBHit]:
        self.sync_world(world)
        lower = b2Vec2(float(bounds[0]), float(bounds[1]))
        upper = b2Vec2(float(bounds[2]), float(bounds[3]))
        box = b2AABB(lowerBound=lower, upperBound=upper)
        hits: dict[int, PhysicsAABBHit] = {}
        self._world.QueryAABB(_AABBQueryCollector(hits), box)
        return [hits[key] for key in sorted(hits)]

    def collect_contacts(self, world: Any) -> list[PhysicsContact]:
        del world
        return list(self._latest_contacts)

    def get_step_metrics(self) -> dict[str, float]:
        return dict(self._step_metrics)

    def _create_body_for_snapshot(self, snapshot: PhysicsEntitySnapshot) -> Any:
        shape = snapshot.shape
        if not snapshot.has_transform or shape is None:
            raise ValueError("Physics snapshot requires transform and shape data to create a Box2D body")
        body_spec = snapshot.body
        body_type = "static"
        if body_spec is not None:
            body_type = body_spec.body_type
        body = (
            self._world.CreateDynamicBody(position=(snapshot.transform_x, snapshot.transform_y))
            if body_type == "dynamic"
            else self._world.CreateStaticBody(position=(snapshot.transform_x, snapshot.transform_y))
        )
        if body_type == "kinematic":
            body.type = 1  # b2_kinematicBody
        if body_spec is not None:
            body.linearVelocity = self._constrained_linear_velocity(body_spec)
            body.gravityScale = body_spec.gravity_scale
            body.bullet = body_spec.collision_detection_mode == "continuous"
        body.userData = {"entity_id": int(snapshot.entity_id), "entity_name": snapshot.entity_name}
        fixture_kwargs = {
            "density": float(shape.density),
            "friction": float(shape.friction),
            "restitution": float(shape.restitution),
            "isSensor": bool(shape.filter.is_sensor),
        }
        shape_type = str(shape.shape_type or "box")
        if shape_type == "circle":
            body.CreateCircleFixture(radius=float(shape.radius), pos=(float(shape.offset_x), float(shape.offset_y)), **fixture_kwargs)
        elif shape_type == "polygon" and shape.points:
            body.CreatePolygonFixture(vertices=[(float(point[0]), float(point[1])) for point in shape.points], **fixture_kwargs)
        else:
            body.CreatePolygonFixture(
                box=(
                    float(shape.width) / 2.0,
                    float(shape.height) / 2.0,
                    (float(shape.offset_x), float(shape.offset_y)),
                    0.0,
                ),
                **fixture_kwargs,
            )
        return body

    def _sync_body_runtime_state(self, body: Any, snapshot: PhysicsEntitySnapshot) -> None:
        if not snapshot.has_transform:
            return
        if abs(float(body.position[0]) - float(snapshot.transform_x)) > 1e-5 or abs(float(body.position[1]) - float(snapshot.transform_y)) > 1e-5:
            body.position = (float(snapshot.transform_x), float(snapshot.transform_y))
        desired_angle = math.radians(float(snapshot.transform_rotation))
        if abs(float(body.angle) - desired_angle) > 1e-5:
            body.angle = desired_angle
        body_spec = snapshot.body
        if body_spec is None:
            body.linearVelocity = (0.0, 0.0)
            return
        desired_velocity = self._constrained_linear_velocity(body_spec)
        if (
            abs(float(body.linearVelocity[0]) - desired_velocity[0]) > 1e-5
            or abs(float(body.linearVelocity[1]) - desired_velocity[1]) > 1e-5
        ):
            body.linearVelocity = desired_velocity
        if abs(float(getattr(body, "gravityScale", 1.0)) - float(body_spec.gravity_scale)) > 1e-5:
            body.gravityScale = float(body_spec.gravity_scale)
        desired_bullet = body_spec.collision_detection_mode == "continuous"
        if bool(getattr(body, "bullet", False)) != desired_bullet:
            body.bullet = desired_bullet

    def _sync_world_from_box2d(self, world: Any) -> None:
        for entity in world.get_all_entities():
            body = self._bodies.get(int(entity.id))
            if body is None:
                continue
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            if transform is not None:
                frozen_x = float(transform.x)
                frozen_y = float(transform.y)
                next_x = float(body.position[0])
                next_y = float(body.position[1])
                if rigidbody is not None:
                    if rigidbody.freeze_x:
                        next_x = frozen_x
                    if rigidbody.freeze_y:
                        next_y = frozen_y
                    if next_x != float(body.position[0]) or next_y != float(body.position[1]):
                        body.position = (next_x, next_y)
                transform.x = next_x
                transform.y = next_y
                transform.rotation = math.degrees(float(body.angle))
            if rigidbody is not None:
                velocity_x = 0.0 if rigidbody.freeze_x else float(body.linearVelocity[0])
                velocity_y = 0.0 if rigidbody.freeze_y else float(body.linearVelocity[1])
                if velocity_x != float(body.linearVelocity[0]) or velocity_y != float(body.linearVelocity[1]):
                    body.linearVelocity = (velocity_x, velocity_y)
                rigidbody.velocity_x = velocity_x
                rigidbody.velocity_y = velocity_y
                if rigidbody.collision_detection_mode == "continuous":
                    self._step_metrics["ccd_bodies"] += 1

    def _constrained_linear_velocity(self, body_spec: PhysicsBodySpec) -> tuple[float, float]:
        velocity_x = 0.0 if body_spec.freeze_x else float(body_spec.velocity_x)
        velocity_y = 0.0 if body_spec.freeze_y else float(body_spec.velocity_y)
        return (velocity_x, velocity_y)

    def _sync_joints(
        self,
        snapshots_by_id: dict[int, PhysicsEntitySnapshot],
        snapshots_by_name: dict[str, PhysicsEntitySnapshot],
    ) -> None:
        valid_joint_ids: set[int] = set()
        for entity_id, snapshot in snapshots_by_id.items():
            joint = snapshot.joint
            if joint is None or not joint.enabled or not joint.connected_entity:
                self._destroy_joint(entity_id)
                continue
            connected_snapshot = snapshots_by_name.get(joint.connected_entity)
            if connected_snapshot is None:
                self._destroy_joint(entity_id)
                continue
            body_a = self._bodies.get(int(entity_id))
            body_b = self._bodies.get(int(connected_snapshot.entity_id))
            if body_a is None or body_b is None or not snapshot.has_transform or not connected_snapshot.has_transform:
                self._destroy_joint(entity_id)
                continue
            signature = build_joint_signature(snapshot)
            if signature is None:
                self._destroy_joint(entity_id)
                continue
            valid_joint_ids.add(int(entity_id))
            if self._joint_signatures.get(int(entity_id)) == signature:
                continue
            self._destroy_joint(entity_id)
            self._joints[int(entity_id)] = self._create_joint(snapshot, connected_snapshot)
            self._joint_signatures[int(entity_id)] = signature
        for entity_id in list(set(self._joints.keys()) - valid_joint_ids):
            self._destroy_joint(entity_id)

    def _create_joint(self, snapshot: PhysicsEntitySnapshot, connected_snapshot: PhysicsEntitySnapshot) -> Any:
        joint = snapshot.joint
        if joint is None:
            raise ValueError("Physics snapshot requires joint data to create a Box2D joint")
        body_a = self._bodies[int(snapshot.entity_id)]
        body_b = self._bodies[int(connected_snapshot.entity_id)]
        anchor_a = (
            float(snapshot.transform_x + joint.anchor_x),
            float(snapshot.transform_y + joint.anchor_y),
        )
        anchor_b = (
            float(connected_snapshot.transform_x + joint.connected_anchor_x),
            float(connected_snapshot.transform_y + joint.connected_anchor_y),
        )
        if joint.joint_type == "fixed":
            return self._world.CreateWeldJoint(
                bodyA=body_a,
                bodyB=body_b,
                anchor=anchor_a,
                collideConnected=bool(joint.collide_connected),
            )
        length = float(joint.rest_length)
        if length <= 0.0:
            length = math.hypot(anchor_b[0] - anchor_a[0], anchor_b[1] - anchor_a[1])
        return self._world.CreateDistanceJoint(
            bodyA=body_a,
            bodyB=body_b,
            anchorA=anchor_a,
            anchorB=anchor_b,
            length=length,
            frequencyHz=float(joint.frequency_hz),
            dampingRatio=float(joint.damping_ratio),
            collideConnected=bool(joint.collide_connected),
        )

    def _destroy_joint(self, entity_id: int) -> None:
        joint = self._joints.pop(int(entity_id), None)
        self._joint_signatures.pop(int(entity_id), None)
        if joint is not None:
            self._world.DestroyJoint(joint)

    def _on_begin_contact(self, contact: Any) -> None:
        fixture_a = contact.fixtureA
        fixture_b = contact.fixtureB
        body_a = fixture_a.body
        body_b = fixture_b.body
        payload = PhysicsContact(
            entity_a=str(body_a.userData["entity_name"]),
            entity_b=str(body_b.userData["entity_name"]),
            entity_a_id=int(body_a.userData["entity_id"]),
            entity_b_id=int(body_b.userData["entity_id"]),
            is_trigger=bool(fixture_a.sensor or fixture_b.sensor),
        )
        self._latest_contacts.append(payload)
        if self._event_bus is not None:
            self._event_bus.emit(
                "on_trigger_enter" if payload.is_trigger else "on_collision",
                {
                    "entity_a": payload.entity_a,
                    "entity_b": payload.entity_b,
                    "entity_a_id": payload.entity_a_id,
                    "entity_b_id": payload.entity_b_id,
                    "is_trigger": payload.is_trigger,
                },
            )
