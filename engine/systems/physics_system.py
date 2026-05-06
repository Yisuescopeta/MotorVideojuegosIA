"""
engine/systems/physics_system.py - Sistema de fisica
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

from engine.components.animatable_body_2d import AnimatableBody2D
from engine.components.area2d import Area2D
from engine.components.collider import Collider
from engine.components.collision_filter_2d import CollisionFilter2D
from engine.components.collision_shape_set_2d import CollisionShape2DDef, CollisionShapeSet2D
from engine.components.joint2d import Joint2D
from engine.components.rigidbody import RigidBody
from engine.components.static_body_2d import StaticBody2D
from engine.components.transform import Transform
from engine.config import GRAVITY_DEFAULT
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.spatial_hash import SpatialHash2D
from engine.resources.physics_material import load_physics_material

AABB = tuple[float, float, float, float]


@dataclass(frozen=True)
class _SolidCandidate:
    entity: Entity
    collider: Collider


class PhysicsSystem:
    """Sistema que aplica fisica 2D determinista y simple."""

    @staticmethod
    def _collider_to_shape_params(collider: Collider) -> dict[str, Any]:
        """Convert Collider to shape params dict compatible with swept_shape_toi."""
        shape_type = str(collider.shape_type or "box")
        if shape_type == "circle":
            return {"radius": float(collider.radius)}
        elif shape_type == "capsule":
            return {"radius": float(collider.radius), "height": float(collider.capsule_height)}
        elif shape_type == "polygon":
            pts = getattr(collider, "points", None)
            if pts and len(pts) >= 3:
                return {"vertices": [list(p) for p in pts]}
            # Fallback: use aabb dimensions as polygon
            return {"vertices": [
                [-collider.width / 2, -collider.height / 2],
                [collider.width / 2, -collider.height / 2],
                [collider.width / 2, collider.height / 2],
                [-collider.width / 2, collider.height / 2],
            ]}
        else:
            return {"width": float(collider.width), "height": float(collider.height)}

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
        self._event_bus: Optional[Any] = None  # type: ignore[no-any-explicit]  # EventBus: tipo externo determinado en runtime

    def set_event_bus(self, event_bus: Optional[Any]) -> None:  # type: ignore[no-any-explicit]  # EventBus: tipo externo determinado en runtime
        self._event_bus = event_bus

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
            effective_type = self._get_effective_body_type(entity)
            solid_aabb = self._get_solid_composite_aabb(entity, transform, collider)
            if effective_type == "static":
                static_like_candidates[int(entity.id)] = candidate
                grid.insert(entity.id, solid_aabb)
            else:
                moving_candidates.append(candidate)

        moving_candidates.sort(key=lambda candidate: int(candidate.entity.id))

        transform_changed = False
        physics_changed = False
        for entity in entities:
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            if transform is None or rigidbody is None or not rigidbody.simulated:
                continue
            before_transform_state = (transform.x, transform.y)
            before_rigidbody_state = (
                rigidbody.velocity_x,
                rigidbody.velocity_y,
                rigidbody.is_grounded,
            )
            effective_type = self._get_effective_body_type(entity)
            if effective_type == "static":
                if rigidbody is not None:
                    rigidbody._clear_force_buffers()
                    rigidbody.velocity_x = 0.0
                    rigidbody.velocity_y = 0.0
                physics_changed = physics_changed or before_rigidbody_state != (
                    rigidbody.velocity_x if rigidbody else 0.0,
                    rigidbody.velocity_y if rigidbody else 0.0,
                    rigidbody.is_grounded if rigidbody else False,
                )
                continue

            collider = entity.get_component(Collider)

            # --- Sleeping check (before processing forces) ---
            self._check_sleeping(rigidbody, delta_time)

            # Skip sleeping bodies for motion integration
            if rigidbody.sleeping:
                rigidbody._clear_force_buffers()
                transform_changed = transform_changed or before_transform_state != (transform.x, transform.y)
                physics_changed = physics_changed or before_rigidbody_state != (
                    rigidbody.velocity_x,
                    rigidbody.velocity_y,
                    rigidbody.is_grounded,
                )
                continue

            if rigidbody.body_type == "dynamic" and not rigidbody.is_grounded:
                grav_x, grav_y = self._get_effective_gravity(world, entity, transform, rigidbody)
                rigidbody.velocity_x += grav_x * rigidbody.gravity_scale * delta_time
                rigidbody.velocity_y += grav_y * rigidbody.gravity_scale * delta_time

            if rigidbody.body_type == "dynamic":
                effective_linear_damp = self._get_effective_linear_damp(world, entity, transform, rigidbody)
                damping_factor = max(0.0, 1.0 - effective_linear_damp * delta_time)
                rigidbody.velocity_x *= damping_factor
                rigidbody.velocity_y *= damping_factor

            if rigidbody.body_type == "dynamic" and rigidbody.angular_velocity != 0.0:
                transform.rotation += rigidbody.angular_velocity * delta_time
                effective_angular_damp = self._get_effective_angular_damp(world, entity, transform, rigidbody)
                angular_damping_factor = max(0.0, 1.0 - effective_angular_damp * delta_time)
                rigidbody.angular_velocity *= angular_damping_factor

            if rigidbody.body_type == "dynamic":
                # Aplicar impulsos instantáneos (cambian velocidad directamente)
                if rigidbody._impulse_buffer_x != 0.0 or rigidbody._impulse_buffer_y != 0.0:
                    mass = rigidbody.mass
                    if mass > 0.0:
                        rigidbody.velocity_x += rigidbody._impulse_buffer_x / mass
                        rigidbody.velocity_y += rigidbody._impulse_buffer_y / mass

                # Aplicar fuerzas acumuladas (F=ma → a=F/m, v+=a*dt)
                if rigidbody._force_buffer_x != 0.0 or rigidbody._force_buffer_y != 0.0:
                    mass = rigidbody.mass
                    if mass > 0.0:
                        rigidbody.velocity_x += (rigidbody._force_buffer_x / mass) * delta_time
                        rigidbody.velocity_y += (rigidbody._force_buffer_y / mass) * delta_time

                # Aplicar torque acumulado
                if rigidbody._torque_buffer != 0.0:
                    inertia = rigidbody.inertia
                    if inertia > 0.0:
                        angular_accel = rigidbody._torque_buffer / inertia
                        rigidbody.angular_velocity += angular_accel * delta_time

                # --- Constant forces (applied every frame, not consumed) ---
                if rigidbody.constant_force_x != 0.0 or rigidbody.constant_force_y != 0.0:
                    mass = rigidbody.mass
                    if mass > 0.0:
                        rigidbody.velocity_x += (rigidbody.constant_force_x / mass) * delta_time
                        rigidbody.velocity_y += (rigidbody.constant_force_y / mass) * delta_time

                if rigidbody.constant_torque != 0.0:
                    inertia = rigidbody.inertia
                    if inertia > 0.0:
                        rigidbody.angular_velocity += (rigidbody.constant_torque / inertia) * delta_time

                # --- Custom integrator callback ---
                if rigidbody.custom_integrator and self._event_bus is not None:
                    self._event_bus.emit("rigidbody_integrate_forces", {
                        "entity_id": int(entity.id),
                        "entity_name": entity.name,
                        "velocity_x": rigidbody.velocity_x,
                        "velocity_y": rigidbody.velocity_y,
                        "angular_velocity": rigidbody.angular_velocity,
                        "mass": rigidbody.mass,
                        "inertia": rigidbody.inertia,
                        "delta_time": delta_time,
                    })

            # Limpiar buffers al final del frame (siempre, incluso para static/kinematic)
            rigidbody._clear_force_buffers()

            delta_x = 0.0 if rigidbody.freeze_x else rigidbody.velocity_x * delta_time
            delta_y = 0.0 if rigidbody.freeze_y else rigidbody.velocity_y * delta_time
            ccd_active = rigidbody.ccd_mode != "disabled"
            continuous_mode = bool(
                collider is not None and collider.enabled
                and (rigidbody.collision_detection_mode == "continuous" or ccd_active)
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
            if ccd_active:
                self._step_metrics["ccd_bodies"] += 1
            elif rigidbody.collision_detection_mode == "continuous":
                self._step_metrics["ccd_bodies"] += 1

            cast_shape_mode = rigidbody.ccd_mode == "cast_shape" and collider is not None and collider.enabled

            if cast_shape_mode:
                # --- Shape-based CCD: 2D sweep + per-axis resolution ---
                if (not rigidbody.freeze_x or not rigidbody.freeze_y):
                    hit = self._sweep_shape_cast(
                        entity, transform, collider, nearby_solids, delta_x, delta_y
                    )
                    if hit is not None:
                        pos = hit.get("position", {})
                        transform.x = float(pos.get("x", transform.x + delta_x))
                        transform.y = float(pos.get("y", transform.y + delta_y))
                        rigidbody.velocity_x = 0.0
                        rigidbody.velocity_y = 0.0
                        self._step_metrics["swept_checks"] += 1
                    else:
                        if not rigidbody.freeze_x:
                            transform.x += delta_x
                        if not rigidbody.freeze_y:
                            transform.y += delta_y
                # Per-axis collision resolution after shape CCD move
                if collider is not None and collider.enabled:
                    if not rigidbody.freeze_x:
                        self._resolve_horizontal(transform, rigidbody, collider, nearby_solids)
                rigidbody.is_grounded = False
                if collider is not None and collider.enabled:
                    if not rigidbody.freeze_y:
                        self._resolve_vertical(transform, rigidbody, collider, nearby_solids)
                    if not rigidbody.is_grounded and not rigidbody.freeze_y:
                        rigidbody.is_grounded = self._has_ground_support(
                            entity, transform, collider, nearby_solids
                        )
            else:
                # --- Existing per-axis AABB sweep (cast_ray / continuous) ---
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

            # --- Lock rotation ---
            if rigidbody.lock_rotation:
                rigidbody.angular_velocity = 0.0

            transform_changed = transform_changed or before_transform_state != (transform.x, transform.y)
            physics_changed = physics_changed or before_rigidbody_state != (
                rigidbody.velocity_x,
                rigidbody.velocity_y,
                rigidbody.is_grounded,
            )

        self._resolve_joints(world, delta_time)

        if transform_changed:
            world.touch_transform()
        if physics_changed:
            world.touch_physics()

    def get_step_metrics(self) -> dict[str, float]:
        return dict(self._step_metrics)

    def consume_swept_contacts(self) -> list[tuple[int, int]]:
        contacts = list(self._swept_contacts)
        self._swept_contacts = []
        self._swept_contact_set = set()
        return contacts

    def _check_sleeping(self, body: RigidBody, dt: float) -> None:
        """Energy-based sleeping — body goes to sleep after time_to_sleep seconds
        of velocity below thresholds."""
        if not body.can_sleep or body.body_type != "dynamic":
            return
        vel = math.sqrt(body.velocity_x ** 2 + body.velocity_y ** 2)
        ang = abs(body.angular_velocity)
        if vel < body.sleep_linear_threshold and ang < body.sleep_angular_threshold:
            body._sleep_timer += dt
            if body._sleep_timer >= body.time_to_sleep:
                body.sleeping = True
                body.velocity_x = 0.0
                body.velocity_y = 0.0
                body.angular_velocity = 0.0
        else:
            body._sleep_timer = 0.0
            body.sleeping = False

    def _get_effective_gravity(
        self, world: World, entity: Entity, transform: Transform, rigidbody: RigidBody
    ) -> tuple[float, float]:
        """Get gravity from area overrides or default global gravity."""
        best_priority = -1
        best_gx = 0.0
        best_gy = self.gravity
        best_is_point = False
        best_unit_dist = 0.0
        best_area_entity: Entity | None = None

        for area_entity in world.iter_entities():
            area = area_entity.get_component(Area2D)
            if area is None or not area.enabled:
                continue
            if area.space_override == "disabled":
                continue
            area_collider = area_entity.get_component(Collider)
            if area_collider is None:
                continue
            area_transform = area_entity.get_component(Transform)
            if area_transform is None:
                continue

            body_left, body_top, body_right, body_bottom = self._get_body_bounds(entity, transform)
            a_left, a_top, a_right, a_bottom = area_collider.get_bounds(
                area_transform.x, area_transform.y
            )
            if not (body_left < a_right and body_right > a_left and
                    body_top < a_bottom and body_bottom > a_top):
                continue

            if area.priority > best_priority:
                best_priority = area.priority
                best_gx = area.gravity_override_x
                best_gy = area.gravity_override_y
                best_is_point = area.gravity_point
                best_unit_dist = area.gravity_distance_scale
                best_area_entity = area_entity

        if best_priority < 0:
            return (0.0, self.gravity)

        if best_priority >= 0 and best_is_point and best_unit_dist > 0.0 and best_area_entity is not None:
            area_transform = best_area_entity.get_component(Transform)
            if area_transform is not None:
                dx = area_transform.x - transform.x
                dy = area_transform.y - transform.y
                dist = math.hypot(dx, dy)
                if dist >= 1e-6:
                    strength = max(0.0, 1.0 - dist / best_unit_dist)
                    mag = math.hypot(best_gx, best_gy)
                    if mag < 1e-6:
                        mag = self.gravity
                    return (dx / dist * mag * strength, dy / dist * mag * strength)
        if best_priority >= 0:
            return (best_gx, best_gy)

        return (best_gx, best_gy)

    def _get_body_bounds(self, entity: Entity, transform: Transform) -> tuple[float, float, float, float]:
        """Get AABB for any entity that might fall into an area."""
        collider = entity.get_component(Collider)
        if collider is not None:
            return collider.get_bounds(transform.x, transform.y)
        return (transform.x, transform.y, transform.x, transform.y)

    def _get_effective_linear_damp(
        self, world: World, entity: Entity, transform: Transform, rigidbody: RigidBody
    ) -> float:
        """Get linear damping from area overrides or use body's own damping."""
        best_priority = -1
        best_damp = rigidbody.linear_damping

        for area_entity in world.iter_entities():
            area = area_entity.get_component(Area2D)
            if area is None or not area.enabled:
                continue
            if area.space_override == "disabled":
                continue
            if area.linear_damp_override == 0.0:
                continue
            area_collider = area_entity.get_component(Collider)
            if area_collider is None:
                continue
            area_transform = area_entity.get_component(Transform)
            if area_transform is None:
                continue

            body_left, body_top, body_right, body_bottom = self._get_body_bounds(entity, transform)
            a_left, a_top, a_right, a_bottom = area_collider.get_bounds(
                area_transform.x, area_transform.y
            )
            if not (body_left < a_right and body_right > a_left and
                    body_top < a_bottom and body_bottom > a_top):
                continue

            if area.priority > best_priority:
                best_priority = area.priority
                best_damp = area.linear_damp_override

        return best_damp

    def _get_effective_angular_damp(
        self, world: World, entity: Entity, transform: Transform, rigidbody: RigidBody
    ) -> float:
        """Get angular damping from area overrides or use body's own damping."""
        best_priority = -1
        best_damp = rigidbody.angular_damping

        for area_entity in world.iter_entities():
            area = area_entity.get_component(Area2D)
            if area is None or not area.enabled:
                continue
            if area.space_override == "disabled":
                continue
            if area.angular_damp_override == 0.0:
                continue
            area_collider = area_entity.get_component(Collider)
            if area_collider is None:
                continue
            area_transform = area_entity.get_component(Transform)
            if area_transform is None:
                continue

            body_left, body_top, body_right, body_bottom = self._get_body_bounds(entity, transform)
            a_left, a_top, a_right, a_bottom = area_collider.get_bounds(
                area_transform.x, area_transform.y
            )
            if not (body_left < a_right and body_right > a_left and
                    body_top < a_bottom and body_bottom > a_top):
                continue

            if area.priority > best_priority:
                best_priority = area.priority
                best_damp = area.angular_damp_override

        return best_damp

    def _is_solid_body(self, entity: Entity) -> bool:
        rigidbody = entity.get_component(RigidBody)
        if rigidbody is None:
            return True
        return rigidbody.simulated and rigidbody.body_type in ("dynamic", "kinematic", "static")

    @staticmethod
    def _get_effective_body_type(entity: Entity) -> str:
        """Returns the effective body type considering StaticBody2D/AnimatableBody2D."""
        rigidbody = entity.get_component(RigidBody)
        has_static = entity.has_component(StaticBody2D)
        has_animatable = entity.has_component(AnimatableBody2D)
        if has_static or has_animatable:
            return "static"
        if rigidbody is None:
            return "static"
        return rigidbody.body_type

    @staticmethod
    def _get_entity_shape_aabbs(entity: Entity, transform: Transform) -> list[tuple[AABB, CollisionShape2DDef | None]]:
        """Return (AABB, shape_def|None) for each enabled non-trigger shape on entity."""
        shape_set = entity.get_component(CollisionShapeSet2D)
        if shape_set is not None:
            enabled = shape_set.get_enabled_non_trigger_shapes()
            if enabled:
                return [(s.get_bounds(transform.x, transform.y), s) for s in enabled]
        collider = entity.get_component(Collider)
        if collider is not None and collider.enabled and not collider.is_trigger:
            return [(collider.get_bounds(transform.x, transform.y), None)]
        return []

    @staticmethod
    def _get_solid_composite_aabb(entity: Entity, transform: Transform, collider: Collider) -> AABB:
        """Return composite bounds for spatial hash. Uses shape set if present."""
        shape_set = entity.get_component(CollisionShapeSet2D)
        if shape_set is not None:
            enabled = shape_set.get_enabled_non_trigger_shapes()
            if enabled:
                return shape_set.get_composite_bounds(transform.x, transform.y)
        return collider.get_bounds(transform.x, transform.y)

    @staticmethod
    def _get_material_path_from_entity(entity: Entity) -> str:
        """Extract physics_material_override_path from RigidBody or StaticBody2D."""
        rb = entity.get_component(RigidBody)
        if rb and rb.physics_material_override_path:
            return rb.physics_material_override_path
        sb = entity.get_component(StaticBody2D)
        if sb and sb.physics_material_override_path:
            return sb.physics_material_override_path
        return ""

    @staticmethod
    def _resolve_material_props(path: str, collider: Collider) -> tuple[float, float]:
        """Return (bounce, friction) from physics material if path valid, else collider fallback."""
        if path:
            mat = load_physics_material(path)
            if mat is not None:
                return mat.get_effective_bounce(), mat.get_effective_friction()
        return collider.restitution, collider.friction

    def _layers_can_collide(self, world: World, entity: Entity, other: Entity) -> bool:
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{entity.layer}|{other.layer}", True))

    def _should_resolve(self, world: World, entity: Entity, rigidbody: RigidBody, other: Entity) -> bool:
        if not self._layers_can_collide(world, entity, other):
            return False
        if not self._filter_allows_collision(entity, other):
            return False
        other_rigidbody = other.get_component(RigidBody)
        if rigidbody.body_type == "kinematic":
            if other_rigidbody is None:
                return rigidbody.use_full_kinematic_contacts
            if other_rigidbody.body_type == "static":
                return rigidbody.use_full_kinematic_contacts
        return True

    def _filter_allows_collision(self, entity_a: Entity, entity_b: Entity) -> bool:
        return CollisionFilter2D.should_collide(
            entity_a.get_component(CollisionFilter2D),
            entity_b.get_component(CollisionFilter2D),
        )

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
            candidate_aabb = self._get_solid_composite_aabb(
                candidate.entity, other_transform, candidate.collider,
            )
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
            for o_aabb, shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                o_left, o_top, o_right, o_bottom = o_aabb
                overlap_y = top < o_bottom and bottom > o_top
                overlap_x = left < o_right and right > o_left
                if not overlap_x or not overlap_y:
                    continue
                if rigidbody.velocity_x > 0:
                    transform.x -= right - o_left
                elif rigidbody.velocity_x < 0:
                    transform.x += o_right - left

                # Apply friction and bounce
                my_bounce, my_friction = self._resolve_material_props(
                    rigidbody.physics_material_override_path, collider,
                )
                if shape_def is not None:
                    other_bounce = shape_def.restitution
                    other_friction = shape_def.friction
                else:
                    other_bounce, other_friction = self._resolve_material_props(
                        self._get_material_path_from_entity(other.entity), other.collider,
                    )
                bounce = max(my_bounce, other_bounce)
                friction = (my_friction + other_friction) * 0.5
                if not math.isfinite(bounce):
                    bounce = 1.0
                if math.isnan(friction):
                    friction = 1.0
                rigidbody.velocity_x *= -bounce
                rigidbody.velocity_y *= max(0.0, 1.0 - friction * 0.5)

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
            for o_aabb, shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                o_left, o_top, o_right, o_bottom = o_aabb
                overlap_y = top < o_bottom and bottom > o_top
                overlap_x = left < o_right and right > o_left
                if not overlap_x or not overlap_y:
                    continue
                if rigidbody.velocity_y > 0:
                    transform.y -= bottom - o_top
                    rigidbody.is_grounded = True
                elif rigidbody.velocity_y < 0:
                    transform.y += o_bottom - top

                # Apply friction and bounce
                my_bounce, my_friction = self._resolve_material_props(
                    rigidbody.physics_material_override_path, collider,
                )
                if shape_def is not None:
                    other_bounce = shape_def.restitution
                    other_friction = shape_def.friction
                else:
                    other_bounce, other_friction = self._resolve_material_props(
                        self._get_material_path_from_entity(other.entity), other.collider,
                    )
                bounce = max(my_bounce, other_bounce)
                friction = (my_friction + other_friction) * 0.5
                if not math.isfinite(bounce):
                    bounce = 1.0
                if math.isnan(friction):
                    friction = 1.0
                rigidbody.velocity_y *= -bounce
                rigidbody.velocity_x *= max(0.0, 1.0 - friction * 0.5)

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
            for o_aabb, _shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                self._step_metrics["swept_checks"] += 1
                o_left, o_top, o_right, o_bottom = o_aabb
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
            for o_aabb, _shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                self._step_metrics["swept_checks"] += 1
                o_left, o_top, o_right, o_bottom = o_aabb
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

    def _sweep_shape_cast(
        self,
        entity: Entity,
        transform: Transform,
        collider: Collider,
        solids: list[_SolidCandidate],
        delta_x: float,
        delta_y: float,
    ) -> dict | None:
        """Shape-based 2D CCD sweep using swept_shape_toi.

        Returns dict with safe_distance/hit_entity/normal/position or None if no hit.
        """
        from engine.physics.shapes import ShapeFactory
        from engine.physics.swept_collision import swept_shape_toi

        total_dist = math.hypot(delta_x, delta_y)
        if total_dist <= 1e-6:
            return None

        dx = delta_x / total_dist
        dy = delta_y / total_dist

        shape_type = str(collider.shape_type or "box")
        shape_params = self._collider_to_shape_params(collider)

        best_hit: dict | None = None
        best_distance = total_dist

        for solid in solids:
            if solid.entity.id == entity.id:
                continue
            other_transform = solid.entity.get_component(Transform)
            if other_transform is None or not solid.collider.enabled:
                continue

            target_shape = ShapeFactory.build(solid.collider, other_transform.x, other_transform.y)
            target_info = {
                "entity": str(solid.entity.name),
                "entity_id": int(solid.entity.id),
                "is_trigger": bool(solid.collider.is_trigger),
            }

            hit = swept_shape_toi(
                shape_type=shape_type,
                shape_params=shape_params,
                origin=(float(transform.x) + float(collider.offset_x), float(transform.y) + float(collider.offset_y)),
                direction=(dx, dy),
                max_distance=total_dist,
                target_shape=target_shape,
                target_info=target_info,
            )

            if hit is not None and hit.get("hit"):
                dist = float(hit["fraction"]) * total_dist
                if dist < best_distance:
                    best_distance = dist
                    best_hit = hit

        if best_hit is not None:
            # Record swept contact for external consumers (events, contact monitoring)
            hit_eid = best_hit.get("entity_id", 0)
            if hit_eid:
                for solid in solids:
                    if int(solid.entity.id) == int(hit_eid):
                        self._record_swept_contact(entity, solid.entity)
                        break
            return {
                "safe_distance": best_distance,
                "hit_entity": best_hit.get("entity", ""),
                "position": best_hit.get("position", {"x": 0.0, "y": 0.0}),
                "normal": best_hit.get("normal", {"x": 0.0, "y": 0.0}),
                "entity_id": hit_eid,
            }
        return None

    def _record_swept_contact(self, entity: Entity, other: Entity) -> None:
        left_id = int(entity.id)
        right_id = int(other.id)
        pair = (min(left_id, right_id), max(left_id, right_id))
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
            for o_aabb, _shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                o_left, o_top, o_right, o_bottom = o_aabb
                overlap_x = left < o_right and right > o_left
                overlap_y = probe_top <= o_bottom and probe_bottom >= o_top
                if overlap_x and overlap_y:
                    return True
        return False

    def _resolve_joints(self, world: World, dt: float) -> None:
        """Resolve joint constraints between entities."""
        for entity in world.iter_entities():
            joint = entity.get_component(Joint2D)
            if not joint or not joint.connected_entity:
                continue
            other = world.get_entity_by_name(joint.connected_entity)
            if not other:
                continue
            transform_a = entity.get_component(Transform)
            transform_b = other.get_component(Transform)
            rigid_a = entity.get_component(RigidBody)
            rigid_b = other.get_component(RigidBody)
            if not transform_a or not transform_b:
                continue
            if joint.joint_type == "fixed":
                self._resolve_fixed_joint(transform_a, transform_b, rigid_a, rigid_b)
            elif joint.joint_type == "distance":
                self._resolve_distance_joint(transform_a, transform_b, rigid_a, rigid_b)
            elif joint.joint_type == "pin":
                self._resolve_pin_joint(transform_a, transform_b, rigid_a, rigid_b, joint, dt)
            elif joint.joint_type == "groove":
                self._resolve_groove_joint(transform_a, transform_b, rigid_a, rigid_b, joint)
            elif joint.joint_type == "damped_spring":
                self._resolve_spring_joint(transform_a, transform_b, rigid_a, rigid_b, joint, dt)

    def _resolve_fixed_joint(
        self,
        trans_a: Transform,
        trans_b: Transform,
        rigid_a: RigidBody | None,
        rigid_b: RigidBody | None,
    ) -> None:
        """Fixed joint: lock both position and rotation between two bodies."""
        mid_x = (trans_a.x + trans_b.x) * 0.5
        mid_y = (trans_a.y + trans_b.y) * 0.5
        if rigid_a and rigid_a.body_type == "dynamic":
            trans_a.x = mid_x
            trans_a.y = mid_y
            rigid_a.velocity_x = 0.0
            rigid_a.velocity_y = 0.0
        if rigid_b and rigid_b.body_type == "dynamic":
            trans_b.x = mid_x
            trans_b.y = mid_y
            rigid_b.velocity_x = 0.0
            rigid_b.velocity_y = 0.0

    def _resolve_distance_joint(
        self,
        trans_a: Transform,
        trans_b: Transform,
        rigid_a: RigidBody | None,
        rigid_b: RigidBody | None,
    ) -> None:
        """Distance joint: maintain a fixed distance between two bodies."""
        dx = trans_b.x - trans_a.x
        dy = trans_b.y - trans_a.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.0001:
            return
        if rigid_a and rigid_a.body_type == "dynamic":
            rigid_a.velocity_x = 0.0
            rigid_a.velocity_y = 0.0
        if rigid_b and rigid_b.body_type == "dynamic":
            rigid_b.velocity_x = 0.0
            rigid_b.velocity_y = 0.0

    def _resolve_pin_joint(
        self,
        trans_a: Transform,
        trans_b: Transform,
        rigid_a: RigidBody | None,
        rigid_b: RigidBody | None,
        joint: Joint2D,
        dt: float,
    ) -> None:
        """Pin joint: constrains positions to same point + optional angular limits and motor."""
        dx = trans_b.x - trans_a.x
        dy = trans_b.y - trans_a.y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist > 0.01 and joint.softness > 0:
            correction = dist * min(joint.softness * 10, 0.5)
            nx = dx / max(dist, 0.0001)
            ny = dy / max(dist, 0.0001)
            if rigid_a and rigid_a.body_type == "dynamic":
                trans_a.x += nx * correction * 0.5
                trans_a.y += ny * correction * 0.5
            if rigid_b and rigid_b.body_type == "dynamic":
                trans_b.x -= nx * correction * 0.5
                trans_b.y -= ny * correction * 0.5

        if joint.angular_limit_enabled and rigid_b:
            if trans_b.rotation < joint.angular_limit_lower:
                trans_b.rotation = joint.angular_limit_lower
            elif trans_b.rotation > joint.angular_limit_upper:
                trans_b.rotation = joint.angular_limit_upper

        if joint.motor_enabled and rigid_b:
            rigid_b.angular_velocity += joint.motor_target_velocity * dt

    def _resolve_groove_joint(
        self,
        trans_a: Transform,
        trans_b: Transform,
        rigid_a: RigidBody | None,
        rigid_b: RigidBody | None,
        joint: Joint2D,
    ) -> None:
        """Groove joint: body B constrained to slide along a line (groove) on body A."""
        ix, iy = joint.initial_offset
        local_x = trans_b.x - trans_a.x - ix
        _ = trans_b.y - trans_a.y - iy
        clamped_x = max(0.0, min(joint.groove_length, local_x))
        trans_b.x = trans_a.x + ix + clamped_x
        trans_b.y = trans_a.y + iy

    def _resolve_spring_joint(
        self,
        trans_a: Transform,
        trans_b: Transform,
        rigid_a: RigidBody | None,
        rigid_b: RigidBody | None,
        joint: Joint2D,
        dt: float,
    ) -> None:
        """Damped spring: applies spring force proportional to displacement from rest length."""
        dx = trans_b.x - trans_a.x
        dy = trans_b.y - trans_a.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.0001:
            return
        displacement = dist - joint.rest_length
        force = -joint.stiffness * displacement
        rel_vx = (rigid_b.velocity_x if rigid_b else 0.0) - (rigid_a.velocity_x if rigid_a else 0.0)
        rel_vy = (rigid_b.velocity_y if rigid_b else 0.0) - (rigid_a.velocity_y if rigid_a else 0.0)
        nx = dx / dist
        ny = dy / dist
        rel_v = rel_vx * nx + rel_vy * ny
        force -= joint.damping * rel_v
        fx = nx * force * dt
        fy = ny * force * dt
        inv_mass_a = 1.0 / rigid_a.mass if (rigid_a and rigid_a.body_type == "dynamic") else 0.0
        inv_mass_b = 1.0 / rigid_b.mass if (rigid_b and rigid_b.body_type == "dynamic") else 0.0
        total_inv = inv_mass_a + inv_mass_b
        if total_inv <= 0:
            return
        if rigid_a and rigid_a.body_type == "dynamic":
            rigid_a.velocity_x -= fx * (inv_mass_a / total_inv)
            rigid_a.velocity_y -= fy * (inv_mass_a / total_inv)
        if rigid_b and rigid_b.body_type == "dynamic":
            rigid_b.velocity_x += fx * (inv_mass_b / total_inv)
            rigid_b.velocity_y += fy * (inv_mass_b / total_inv)
