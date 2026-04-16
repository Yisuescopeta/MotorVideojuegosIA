"""
engine/systems/physics_system.py - Sistema de fisica
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.config import GRAVITY_DEFAULT, GROUND_Y_TEMP
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.spatial_hash import SpatialHash2D

AABB = tuple[float, float, float, float]


@dataclass(frozen=True)
class _SolidCandidate:
    entity: Entity
    collider: Collider


class PhysicsSystem:
    """Sistema que aplica fisica 2D determinista y simple."""

    def __init__(self, gravity: float = GRAVITY_DEFAULT) -> None:
        self.gravity: float = gravity
        self._step_metrics: dict[str, float] = {
            "ccd_bodies": 0,
            "swept_checks": 0,
            "candidate_solids": 0,
        }
        self._swept_contacts: list[tuple[int, int]] = []
        self._swept_contact_set: set[tuple[int, int]] = set()
        self._spatial_hash_cell_size: float = 128.0

    def update(self, world: World, delta_time: float) -> None:
        self._step_metrics = {"ccd_bodies": 0, "swept_checks": 0, "candidate_solids": 0}
        self._swept_contacts = []
        self._swept_contact_set = set()
        entities = world.get_entities_with(Transform, RigidBody)
        static_like_candidates: dict[int, _SolidCandidate] = {}
        moving_candidates: list[_SolidCandidate] = []
        grid = SpatialHash2D(cell_size=self._spatial_hash_cell_size)

        for entity in world.get_entities_with(Transform, Collider):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            if transform is None or collider is None or not collider.enabled or collider.is_trigger:
                continue
            if not self._is_solid_body(entity):
                continue
            candidate = _SolidCandidate(entity=entity, collider=collider)
            rigidbody = entity.get_component(RigidBody)
            if rigidbody is None or rigidbody.body_type == "static":
                static_like_candidates[int(entity.id)] = candidate
                grid.insert(entity.id, collider.get_bounds(transform.x, transform.y))
            else:
                moving_candidates.append(candidate)

        moving_candidates.sort(key=lambda candidate: int(candidate.entity.id))

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

            delta_x = 0.0 if rigidbody.freeze_x else rigidbody.velocity_x * delta_time
            delta_y = 0.0 if rigidbody.freeze_y else rigidbody.velocity_y * delta_time
            continuous_mode = bool(
                collider is not None and collider.enabled and rigidbody.collision_detection_mode == "continuous"
            )
            nearby_solids = self._collect_candidate_solids(
                world,
                entity,
                rigidbody,
                collider,
                transform,
                grid,
                static_like_candidates,
                moving_candidates,
                delta_x,
                delta_y,
            )
            self._step_metrics["candidate_solids"] += len(nearby_solids)
            if continuous_mode:
                self._step_metrics["ccd_bodies"] += 1

            if rigidbody.freeze_x:
                rigidbody.velocity_x = 0.0
            else:
                if continuous_mode and collider is not None and collider.enabled:
                    delta_x = self._sweep_horizontal(entity, transform, rigidbody, collider, nearby_solids, delta_x)
                transform.x += delta_x
                if collider is not None and collider.enabled:
                    self._resolve_horizontal(transform, rigidbody, collider, nearby_solids)

            if rigidbody.freeze_y:
                rigidbody.velocity_y = 0.0
            else:
                if continuous_mode and collider is not None and collider.enabled:
                    delta_y = self._sweep_vertical(entity, transform, rigidbody, collider, nearby_solids, delta_y)
                transform.y += delta_y
                rigidbody.is_grounded = False
                if collider is not None and collider.enabled:
                    self._resolve_vertical(transform, rigidbody, collider, nearby_solids)
                    if not rigidbody.is_grounded:
                        rigidbody.is_grounded = self._has_ground_support(entity, transform, collider, nearby_solids)

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

    def _collect_candidate_solids(
        self,
        world: World,
        entity: Entity,
        rigidbody: RigidBody,
        collider: Collider | None,
        transform: Transform,
        grid: SpatialHash2D,
        static_like_candidates: dict[int, _SolidCandidate],
        moving_candidates: list[_SolidCandidate],
        delta_x: float,
        delta_y: float,
    ) -> list[_SolidCandidate]:
        if collider is None or not collider.enabled:
            return []
        current_aabb = collider.get_bounds(transform.x, transform.y)
        swept_aabb = self._build_swept_aabb(current_aabb, delta_x, delta_y)
        candidates: list[_SolidCandidate] = []
        seen_ids: set[int] = set()
        for candidate_id in sorted(grid.query(swept_aabb)):
            if candidate_id == entity.id:
                continue
            candidate = static_like_candidates.get(candidate_id)
            if candidate is None:
                continue
            if not self._should_resolve(world, entity, rigidbody, candidate.entity):
                continue
            seen_ids.add(int(candidate_id))
            candidates.append(candidate)
        for candidate in moving_candidates:
            candidate_id = int(candidate.entity.id)
            if candidate_id == int(entity.id) or candidate_id in seen_ids:
                continue
            if not self._should_resolve(world, entity, rigidbody, candidate.entity):
                continue
            other_transform = candidate.entity.get_component(Transform)
            if other_transform is None or not candidate.collider.enabled:
                continue
            candidate_aabb = candidate.collider.get_bounds(other_transform.x, other_transform.y)
            if not self._aabb_overlaps(swept_aabb, candidate_aabb):
                continue
            seen_ids.add(candidate_id)
            candidates.append(candidate)
        return candidates

    def _build_swept_aabb(self, aabb: AABB, delta_x: float, delta_y: float) -> AABB:
        left, top, right, bottom = aabb
        moved_left = left + delta_x
        moved_top = top + delta_y
        moved_right = right + delta_x
        moved_bottom = bottom + delta_y
        return (
            min(left, moved_left),
            min(top, moved_top),
            max(right, moved_right),
            max(bottom, moved_bottom),
        )

    def _aabb_overlaps(self, aabb_a: AABB, aabb_b: AABB) -> bool:
        left_a, top_a, right_a, bottom_a = aabb_a
        left_b, top_b, right_b, bottom_b = aabb_b
        return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b

    def _resolve_horizontal(
        self,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[_SolidCandidate],
    ) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        for other in solids:
            other_transform = other.entity.get_component(Transform)
            if other_transform is None or not other.collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other.collider.get_bounds(other_transform.x, other_transform.y)
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
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[_SolidCandidate],
    ) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        for other in solids:
            other_transform = other.entity.get_component(Transform)
            if other_transform is None or not other.collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other.collider.get_bounds(other_transform.x, other_transform.y)
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
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[_SolidCandidate],
        delta_x: float,
    ) -> float:
        if abs(delta_x) <= 1e-6:
            return delta_x
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_x
        for other in solids:
            other_transform = other.entity.get_component(Transform)
            if other_transform is None or not other.collider.enabled:
                continue
            self._step_metrics["swept_checks"] += 1
            o_left, o_top, o_right, o_bottom = other.collider.get_bounds(other_transform.x, other_transform.y)
            overlap_y = top < o_bottom and bottom > o_top
            if not overlap_y:
                continue
            if delta_x > 0:
                gap = o_left - right
                if 0.0 <= gap <= safe_delta:
                    safe_delta = min(safe_delta, max(0.0, gap))
                    self._record_swept_contact(entity, other.entity)
            else:
                gap = o_right - left
                if safe_delta <= gap <= 0.0:
                    safe_delta = max(safe_delta, min(0.0, gap))
                    self._record_swept_contact(entity, other.entity)
        return safe_delta

    def _sweep_vertical(
        self,
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[_SolidCandidate],
        delta_y: float,
    ) -> float:
        if abs(delta_y) <= 1e-6:
            return delta_y
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta_y
        for other in solids:
            other_transform = other.entity.get_component(Transform)
            if other_transform is None or not other.collider.enabled:
                continue
            self._step_metrics["swept_checks"] += 1
            o_left, o_top, o_right, o_bottom = other.collider.get_bounds(other_transform.x, other_transform.y)
            overlap_x = left < o_right and right > o_left
            if not overlap_x:
                continue
            if delta_y > 0:
                gap = o_top - bottom
                if 0.0 <= gap <= safe_delta:
                    safe_delta = min(safe_delta, max(0.0, gap))
                    self._record_swept_contact(entity, other.entity)
            else:
                gap = o_bottom - top
                if safe_delta <= gap <= 0.0:
                    safe_delta = max(safe_delta, min(0.0, gap))
                    self._record_swept_contact(entity, other.entity)
        return safe_delta

    def _record_swept_contact(self, entity: Entity, other: Entity) -> None:
        pair = tuple(sorted((int(entity.id), int(other.id))))
        if pair not in self._swept_contact_set:
            self._swept_contact_set.add(pair)
            self._swept_contacts.append(pair)

    def _has_ground_support(
        self,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        solids: list[_SolidCandidate],
    ) -> bool:
        left, _, right, bottom = collider.get_bounds(transform.x, transform.y)
        probe_top = bottom
        probe_bottom = bottom + 1.0
        for other in solids:
            if other.entity.id == entity.id:
                continue
            other_transform = other.entity.get_component(Transform)
            if other_transform is None or not other.collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other.collider.get_bounds(other_transform.x, other_transform.y)
            overlap_x = left < o_right and right > o_left
            overlap_y = probe_top <= o_bottom and probe_bottom >= o_top
            if overlap_x and overlap_y:
                return True
        return False
