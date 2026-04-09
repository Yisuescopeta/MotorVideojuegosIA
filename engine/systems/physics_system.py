"""
engine/systems/physics_system.py - Sistema de fisica
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.config import GRAVITY_DEFAULT, GROUND_Y_TEMP
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.backend import PhysicsContact


class PhysicsSystem:
    """Sistema que aplica fisica 2D determinista y simple."""

    MAX_SUBSTEP: float = 1.0 / 120.0
    CONTACT_EPSILON: float = 0.05
    SKIN_WIDTH: float = 0.01
    GROUND_PROBE_DISTANCE: float = 2.0
    GROUND_SNAP_DISTANCE: float = 2.0

    def __init__(
        self,
        gravity: float = GRAVITY_DEFAULT,
        *,
        contact_slop: float | None = None,
        ground_contact_tolerance: float | None = None,
        skin_width: float | None = None,
    ) -> None:
        self.gravity: float = gravity
        self._step_metrics: dict[str, float] = {"ccd_bodies": 0, "swept_checks": 0}
        self._swept_contacts: list[tuple[int, int]] = []
        self._swept_contact_set: set[tuple[int, int]] = set()
        self.contact_slop: float = float(self.CONTACT_EPSILON if contact_slop is None else contact_slop)
        self.ground_contact_tolerance: float = float(
            self.GROUND_SNAP_DISTANCE if ground_contact_tolerance is None else ground_contact_tolerance
        )
        self.skin_width: float = float(self.SKIN_WIDTH if skin_width is None else skin_width)
        self._frame_contacts: list[PhysicsContact] = []
        self._frame_contact_index: dict[tuple[Any, ...], PhysicsContact] = {}
        self._body_contact_states: dict[int, dict[str, Any]] = {}

    def update(self, world: World, delta_time: float) -> None:
        self._step_metrics = {"ccd_bodies": 0, "swept_checks": 0, "substeps": 0, "contacts": 0, "grounded_bodies": 0}
        self._swept_contacts = []
        self._swept_contact_set = set()
        self._frame_contacts = []
        self._frame_contact_index = {}
        self._reset_body_contact_states(world)
        step_count = max(1, int(math.ceil(max(0.0, float(delta_time)) / self.MAX_SUBSTEP)))
        step_dt = float(delta_time) / float(step_count)
        self._step_metrics["substeps"] = float(step_count)
        for _ in range(step_count):
            self._update_step(world, step_dt)
        self._step_metrics["contacts"] = float(len(self._frame_contacts))
        self._step_metrics["grounded_bodies"] = float(
            sum(1 for state in self._body_contact_states.values() if bool(state.get("grounded")))
        )

    def _update_step(self, world: World, delta_time: float) -> None:
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
            if collider is not None and collider.enabled and rigidbody.velocity_y >= 0.0:
                rigidbody.is_grounded = self._stabilize_ground_contact(world, entity, transform, rigidbody, collider, solids)

            if rigidbody.body_type == "dynamic" and not rigidbody.is_grounded:
                rigidbody.velocity_y += self.gravity * rigidbody.gravity_scale * delta_time
            elif rigidbody.is_grounded and rigidbody.velocity_y > 0.0:
                rigidbody.velocity_y = 0.0

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
                        rigidbody.is_grounded = self._stabilize_ground_contact(world, entity, transform, rigidbody, collider, solids)

            if rigidbody.body_type == "dynamic" and not rigidbody.is_grounded and transform.y > GROUND_Y_TEMP:
                transform.y = GROUND_Y_TEMP
                rigidbody.velocity_y = 0.0
                rigidbody.is_grounded = True

            rigidbody.is_grounded = bool(self._get_body_contact_state(entity.id)["grounded"]) or bool(rigidbody.is_grounded)

    def get_step_metrics(self) -> dict[str, float]:
        return dict(self._step_metrics)

    def consume_swept_contacts(self) -> list[tuple[int, int]]:
        contacts = list(self._swept_contacts)
        self._swept_contacts = []
        self._swept_contact_set = set()
        return contacts

    def get_frame_contacts(self) -> list[PhysicsContact]:
        return list(self._frame_contacts)

    def get_body_contact_state(self, entity_id: int) -> dict[str, Any]:
        state = self._body_contact_states.get(int(entity_id))
        if state is None:
            return self._default_body_contact_state()
        return deepcopy(state)

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
            penetration = min(right, o_right) - max(left, o_left)
            if penetration <= 0.0:
                continue
            normal_x = self._horizontal_contact_normal(transform, rigidbody, other_transform)
            if rigidbody.velocity_x > 0:
                transform.x -= penetration + self.skin_width
            elif rigidbody.velocity_x < 0:
                transform.x += penetration + self.skin_width
            elif normal_x < 0.0:
                transform.x -= penetration + self.skin_width
            else:
                transform.x += penetration + self.skin_width
            rigidbody.velocity_x = 0.0
            self._record_contact(
                entity,
                other,
                normal_x=normal_x,
                normal_y=0.0,
                penetration=penetration,
                contact_type="wall",
                source="overlap",
                separation=0.0,
            )
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
            penetration = min(bottom, o_bottom) - max(top, o_top)
            if penetration <= 0.0:
                continue
            normal_y = self._vertical_contact_normal(transform, rigidbody, other_transform)
            if rigidbody.velocity_y > 0:
                transform.y -= penetration + self.skin_width
                rigidbody.is_grounded = True
            elif rigidbody.velocity_y < 0:
                transform.y += penetration + self.skin_width
            elif normal_y < 0.0:
                transform.y -= penetration + self.skin_width
                rigidbody.is_grounded = True
            else:
                transform.y += penetration + self.skin_width
            rigidbody.velocity_y = 0.0
            contact_type = "floor" if normal_y < 0.0 else "ceiling"
            self._record_contact(
                entity,
                other,
                normal_x=0.0,
                normal_y=normal_y,
                penetration=penetration,
                contact_type=contact_type,
                source="overlap",
                separation=0.0,
                supporting=contact_type == "floor",
            )
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
            overlap_y = self._ranges_overlap_with_slop(top, bottom, o_top, o_bottom)
            if not overlap_y:
                continue
            if delta_x > 0:
                gap = o_left - right
                hit, candidate_delta, penetration, separation = self._compute_positive_sweep_delta(gap, safe_delta)
                if hit:
                    safe_delta = min(safe_delta, candidate_delta)
                    rigidbody.velocity_x = 0.0
                    self._record_swept_contact(entity, other)
                    self._record_contact(
                        entity,
                        other,
                        normal_x=-1.0,
                        normal_y=0.0,
                        penetration=penetration,
                        contact_type="wall",
                        source="swept",
                        separation=separation,
                    )
            else:
                gap = o_right - left
                hit, candidate_delta, penetration, separation = self._compute_negative_sweep_delta(gap, safe_delta)
                if hit:
                    safe_delta = max(safe_delta, candidate_delta)
                    rigidbody.velocity_x = 0.0
                    self._record_swept_contact(entity, other)
                    self._record_contact(
                        entity,
                        other,
                        normal_x=1.0,
                        normal_y=0.0,
                        penetration=penetration,
                        contact_type="wall",
                        source="swept",
                        separation=separation,
                    )
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
            overlap_x = self._ranges_overlap_with_slop(left, right, o_left, o_right)
            if not overlap_x:
                continue
            if delta_y > 0:
                gap = o_top - bottom
                hit, candidate_delta, penetration, separation = self._compute_positive_sweep_delta(gap, safe_delta)
                if hit:
                    safe_delta = min(safe_delta, candidate_delta)
                    rigidbody.velocity_y = 0.0
                    rigidbody.is_grounded = True
                    self._record_swept_contact(entity, other)
                    self._record_contact(
                        entity,
                        other,
                        normal_x=0.0,
                        normal_y=-1.0,
                        penetration=penetration,
                        contact_type="floor",
                        source="swept",
                        separation=separation,
                        supporting=True,
                    )
            else:
                gap = o_bottom - top
                hit, candidate_delta, penetration, separation = self._compute_negative_sweep_delta(gap, safe_delta)
                if hit:
                    safe_delta = max(safe_delta, candidate_delta)
                    rigidbody.velocity_y = 0.0
                    self._record_swept_contact(entity, other)
                    self._record_contact(
                        entity,
                        other,
                        normal_x=0.0,
                        normal_y=1.0,
                        penetration=penetration,
                        contact_type="ceiling",
                        source="swept",
                        separation=separation,
                    )
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
        return self._find_ground_support(world, entity, transform, collider, solids) is not None

    def _stabilize_ground_contact(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list[Entity],
    ) -> bool:
        support = self._find_ground_support(world, entity, transform, collider, solids)
        if support is None:
            return False
        gap = float(support["gap"])
        if gap > self.ground_contact_tolerance:
            return False
        if gap > self.contact_slop:
            transform.y += gap
        if rigidbody.velocity_y > 0.0:
            rigidbody.velocity_y = 0.0
        self._record_contact(
            entity,
            support["entity"],
            normal_x=0.0,
            normal_y=-1.0,
            penetration=0.0,
            contact_type="floor",
            source="snap_probe",
            separation=max(0.0, gap),
            supporting=True,
        )
        return True

    def _find_ground_support(
        self,
        world: World,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        solids: list[Entity],
    ) -> dict[str, Any] | None:
        left, _, right, bottom = collider.get_bounds(transform.x, transform.y)
        probe_inset = min(1.0, max(0.0, (right - left) * 0.1))
        probe_left = left + probe_inset
        probe_right = right - probe_inset
        if probe_left >= probe_right:
            probe_left = left
            probe_right = right
        probe_top = bottom - self.contact_slop
        probe_bottom = bottom + self.GROUND_PROBE_DISTANCE
        nearest_support: dict[str, Any] | None = None
        for other in solids:
            if other.id == entity.id or not self._layers_can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_x = probe_left < (o_right - self.contact_slop) and probe_right > (o_left + self.contact_slop)
            if not overlap_x:
                continue
            gap = o_top - bottom
            overlap_y = probe_top <= o_bottom and probe_bottom >= o_top
            if not overlap_y or gap < -self.contact_slop:
                continue
            if nearest_support is None or gap < float(nearest_support["gap"]):
                nearest_support = {
                    "gap": float(gap),
                    "entity": other,
                }
        if nearest_support is None:
            return None
        return nearest_support

    def _reset_body_contact_states(self, world: World) -> None:
        self._body_contact_states = {}
        for entity in world.get_entities_with(RigidBody):
            self._body_contact_states[int(entity.id)] = self._default_body_contact_state()

    def _default_body_contact_state(self) -> dict[str, Any]:
        return {
            "grounded": False,
            "touching_wall_left": False,
            "touching_wall_right": False,
            "touching_ceiling": False,
            "ground_normal": {"x": 0.0, "y": 0.0},
            "ground_entity": None,
            "ground_entity_id": None,
            "support_distance": None,
            "contact_count": 0,
        }

    def _get_body_contact_state(self, entity_id: int) -> dict[str, Any]:
        key = int(entity_id)
        state = self._body_contact_states.get(key)
        if state is None:
            state = self._default_body_contact_state()
            self._body_contact_states[key] = state
        return state

    def _record_contact(
        self,
        entity: Entity,
        other: Entity,
        *,
        normal_x: float,
        normal_y: float,
        penetration: float,
        contact_type: str,
        source: str,
        separation: float,
        supporting: bool = False,
        is_trigger: bool = False,
    ) -> None:
        contact = PhysicsContact(
            entity_a=entity.name,
            entity_b=other.name,
            entity_a_id=int(entity.id),
            entity_b_id=int(other.id),
            is_trigger=bool(is_trigger),
            normal_x=float(normal_x),
            normal_y=float(normal_y),
            penetration=float(max(0.0, penetration)),
            contact_type=str(contact_type),
            source=str(source),
            separation=float(max(0.0, separation)),
        )
        key = (
            int(contact.entity_a_id),
            int(contact.entity_b_id),
            str(contact.contact_type),
            bool(contact.is_trigger),
            str(contact.source),
        )
        existing = self._frame_contact_index.get(key)
        if existing is None:
            self._frame_contacts.append(contact)
            self._frame_contact_index[key] = contact
        else:
            existing.penetration = max(float(existing.penetration), float(contact.penetration))
            if float(existing.separation) <= 0.0:
                existing.separation = float(contact.separation)
            elif float(contact.separation) > 0.0:
                existing.separation = min(float(existing.separation), float(contact.separation))
            if supporting and float(contact.normal_y) < 0.0:
                existing.normal_x = float(contact.normal_x)
                existing.normal_y = float(contact.normal_y)
        if not is_trigger:
            self._update_body_contact_state(entity, other, contact, supporting=supporting)

    def _update_body_contact_state(
        self,
        entity: Entity,
        other: Entity,
        contact: PhysicsContact,
        *,
        supporting: bool,
    ) -> None:
        state = self._get_body_contact_state(entity.id)
        state["contact_count"] = int(state["contact_count"]) + 1
        if str(contact.contact_type) == "floor" or supporting:
            state["grounded"] = True
            state["ground_normal"] = {
                "x": float(contact.normal_x or 0.0),
                "y": float(contact.normal_y or 0.0),
            }
            state["ground_entity"] = other.name
            state["ground_entity_id"] = int(other.id)
            state["support_distance"] = float(contact.separation)
        elif str(contact.contact_type) == "ceiling":
            state["touching_ceiling"] = True
        elif str(contact.contact_type) == "wall":
            normal_x = float(contact.normal_x or 0.0)
            if normal_x > 0.0:
                state["touching_wall_left"] = True
            elif normal_x < 0.0:
                state["touching_wall_right"] = True

    def _horizontal_contact_normal(self, transform: Transform, rigidbody: RigidBody, other_transform: Transform) -> float:
        if rigidbody.velocity_x > 0.0:
            return -1.0
        if rigidbody.velocity_x < 0.0:
            return 1.0
        return -1.0 if float(transform.x) < float(other_transform.x) else 1.0

    def _vertical_contact_normal(self, transform: Transform, rigidbody: RigidBody, other_transform: Transform) -> float:
        if rigidbody.velocity_y > 0.0:
            return -1.0
        if rigidbody.velocity_y < 0.0:
            return 1.0
        return -1.0 if float(transform.y) < float(other_transform.y) else 1.0

    def _ranges_overlap_with_slop(
        self,
        min_a: float,
        max_a: float,
        min_b: float,
        max_b: float,
    ) -> bool:
        tolerance = max(self.contact_slop, self.skin_width)
        return float(min_a) < float(max_b) + tolerance and float(max_a) > float(min_b) - tolerance

    def _compute_positive_sweep_delta(self, gap: float, safe_delta: float) -> tuple[bool, float, float, float]:
        tolerance = max(self.contact_slop, self.skin_width)
        if float(gap) < -tolerance or float(gap) > float(safe_delta):
            return False, float(safe_delta), 0.0, 0.0
        clamped_gap = max(0.0, float(gap))
        candidate_delta = min(float(safe_delta), max(0.0, clamped_gap - self.skin_width))
        penetration = max(0.0, -float(gap))
        separation = max(0.0, clamped_gap - candidate_delta)
        if clamped_gap <= tolerance:
            candidate_delta = min(candidate_delta, 0.0)
            separation = 0.0
        return True, candidate_delta, penetration, separation

    def _compute_negative_sweep_delta(self, gap: float, safe_delta: float) -> tuple[bool, float, float, float]:
        tolerance = max(self.contact_slop, self.skin_width)
        if float(gap) > tolerance or float(gap) < float(safe_delta):
            return False, float(safe_delta), 0.0, 0.0
        clamped_gap = min(0.0, float(gap))
        candidate_delta = max(float(safe_delta), min(0.0, clamped_gap + self.skin_width))
        penetration = max(0.0, float(gap))
        separation = max(0.0, abs(clamped_gap - candidate_delta))
        if abs(clamped_gap) <= tolerance:
            candidate_delta = max(candidate_delta, 0.0)
            separation = 0.0
        return True, candidate_delta, penetration, separation
