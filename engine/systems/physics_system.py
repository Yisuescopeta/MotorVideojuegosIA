"""
engine/systems/physics_system.py - Sistema de fÃ­sica
"""

from __future__ import annotations

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.config import GRAVITY_DEFAULT, GROUND_Y_TEMP
from engine.ecs.entity import Entity
from engine.ecs.world import World


class PhysicsSystem:
    """Sistema que aplica fÃ­sica 2D determinista y simple."""

    def __init__(self, gravity: float = GRAVITY_DEFAULT) -> None:
        self.gravity: float = gravity
        self._step_metrics: dict[str, float] = {"ccd_bodies": 0, "swept_checks": 0}
        self._swept_contacts: list[tuple[int, int]] = []
        self._swept_contact_set: set[tuple[int, int]] = set()

    def update(self, world: World, delta_time: float) -> None:
        self._step_metrics = {"ccd_bodies": 0, "swept_checks": 0}
        self._swept_contacts = []
        self._swept_contact_set = set()
        entities = world.get_entities_with(Transform, RigidBody)
        solids = [
            entity
            for entity in world.get_entities_with(Transform, Collider)
            if self._is_solid_body(entity) and entity.get_component(Collider) is not None and not entity.get_component(Collider).is_trigger
        ]

        for entity in entities:
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            if transform is None or rigidbody is None or not rigidbody.simulated:
                continue
            if rigidbody.body_type == "static":
                rigidbody.velocity_x = 0.0
                rigidbody.velocity_y = 0.0
                continue

            collider = entity.get_component(Collider)
            if rigidbody.body_type == "dynamic" and not rigidbody.is_grounded:
                rigidbody.velocity_y += self.gravity * rigidbody.gravity_scale * delta_time

            if rigidbody.freeze_x:
                rigidbody.velocity_x = 0.0
            else:
                delta_x = rigidbody.velocity_x * delta_time
                if collider is not None and collider.enabled and rigidbody.collision_detection_mode == "continuous":
                    self._step_metrics["ccd_bodies"] += 1
                    delta_x = self._sweep_horizontal(world, entity, transform, rigidbody, collider, solids, delta_x)
                transform.x += delta_x
                if collider is not None and collider.enabled:
                    self._resolve_horizontal(world, entity, transform, rigidbody, collider, solids)

            if rigidbody.freeze_y:
                rigidbody.velocity_y = 0.0
            else:
                delta_y = rigidbody.velocity_y * delta_time
                if collider is not None and collider.enabled and rigidbody.collision_detection_mode == "continuous":
                    delta_y = self._sweep_vertical(world, entity, transform, rigidbody, collider, solids, delta_y)
                transform.y += delta_y
                rigidbody.is_grounded = False
                if collider is not None and collider.enabled:
                    self._resolve_vertical(world, entity, transform, rigidbody, collider, solids)
                    if not rigidbody.is_grounded:
                        rigidbody.is_grounded = self._has_ground_support(world, entity, transform, collider, solids)

            if rigidbody.body_type == "dynamic" and not rigidbody.is_grounded and transform.y > GROUND_Y_TEMP:
                transform.y = GROUND_Y_TEMP
                rigidbody.velocity_y = 0.0
                rigidbody.is_grounded = True

    def get_step_metrics(self) -> dict[str, float]:
        return dict(self._step_metrics)

    def consume_swept_contacts(self) -> list[tuple[int, int]]:
        contacts = list(self._swept_contacts)
        self._swept_contacts = []
        self._swept_contact_set = set()
        return contacts

    def _is_solid_body(self, entity: Entity) -> bool:
        rigidbody = entity.get_component(RigidBody)
        if rigidbody is None:
            return True
        return rigidbody.simulated and rigidbody.body_type in ("dynamic", "kinematic", "static")

    def _layers_can_collide(self, world: World, entity: Entity, other: Entity) -> bool:
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{entity.layer}|{other.layer}", True))

    def _should_resolve(self, world: World, entity: Entity, rigidbody: RigidBody, other: Entity) -> bool:
        if not self._layers_can_collide(world, entity, other):
            return False
        other_rigidbody = other.get_component(RigidBody)
        if rigidbody.body_type == "kinematic":
            if other_rigidbody is None:
                return rigidbody.use_full_kinematic_contacts
            if other_rigidbody.body_type == "static":
                return rigidbody.use_full_kinematic_contacts
        return True

    def _resolve_horizontal(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[Entity],
    ) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        for other in solids:
            if other.id == entity.id or not self._should_resolve(world, entity, rigidbody, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_y = top < o_bottom and bottom > o_top
            overlap_x = left < o_right and right > o_left
            if not overlap_x or not overlap_y:
                continue
            if rigidbody.velocity_x > 0:
                transform.x -= right - o_left
            elif rigidbody.velocity_x < 0:
                transform.x += o_right - left
            rigidbody.velocity_x = 0.0
            left, top, right, bottom = collider.get_bounds(transform.x, transform.y)

    def _resolve_vertical(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[Entity],
    ) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        for other in solids:
            if other.id == entity.id or not self._should_resolve(world, entity, rigidbody, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_y = top < o_bottom and bottom > o_top
            overlap_x = left < o_right and right > o_left
            if not overlap_x or not overlap_y:
                continue
            if rigidbody.velocity_y > 0:
                transform.y -= bottom - o_top
                rigidbody.is_grounded = True
            elif rigidbody.velocity_y < 0:
                transform.y += o_bottom - top
            rigidbody.velocity_y = 0.0
            left, top, right, bottom = collider.get_bounds(transform.x, transform.y)

    def _sweep_horizontal(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[Entity],
        delta_x: float,
    ) -> float:
        if abs(delta_x) <= 1e-6:
            return delta_x
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_x
        for other in solids:
            if other.id == entity.id or not self._should_resolve(world, entity, rigidbody, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            self._step_metrics["swept_checks"] += 1
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_y = top < o_bottom and bottom > o_top
            if not overlap_y:
                continue
            if delta_x > 0:
                gap = o_left - right
                if 0.0 <= gap <= safe_delta:
                    safe_delta = min(safe_delta, max(0.0, gap))
                    self._record_swept_contact(entity, other)
            else:
                gap = o_right - left
                if safe_delta <= gap <= 0.0:
                    safe_delta = max(safe_delta, min(0.0, gap))
                    self._record_swept_contact(entity, other)
        return safe_delta

    def _sweep_vertical(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[Entity],
        delta_y: float,
    ) -> float:
        if abs(delta_y) <= 1e-6:
            return delta_y
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_y
        for other in solids:
            if other.id == entity.id or not self._should_resolve(world, entity, rigidbody, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            self._step_metrics["swept_checks"] += 1
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_x = left < o_right and right > o_left
            if not overlap_x:
                continue
            if delta_y > 0:
                gap = o_top - bottom
                if 0.0 <= gap <= safe_delta:
                    safe_delta = min(safe_delta, max(0.0, gap))
                    self._record_swept_contact(entity, other)
            else:
                gap = o_bottom - top
                if safe_delta <= gap <= 0.0:
                    safe_delta = max(safe_delta, min(0.0, gap))
                    self._record_swept_contact(entity, other)
        return safe_delta

    def _record_swept_contact(self, entity: Entity, other: Entity) -> None:
        pair = tuple(sorted((int(entity.id), int(other.id))))
        if pair not in self._swept_contact_set:
            self._swept_contact_set.add(pair)
            self._swept_contacts.append(pair)

    def _has_ground_support(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        solids: list[Entity],
    ) -> bool:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        probe_top = bottom
        probe_bottom = bottom + 1.0
        for other in solids:
            if other.id == entity.id or not self._layers_can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_x = left < o_right and right > o_left
            overlap_y = probe_top <= o_bottom and probe_bottom >= o_top
            if overlap_x and overlap_y:
                return True
        return False
