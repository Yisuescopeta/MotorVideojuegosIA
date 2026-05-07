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
from engine.physics.contact_solver import ContactConstraint2D, ImpulseSolver2D
from engine.physics.island_manager import Island2D, IslandBuilder2D
from engine.physics.spatial_hash import SpatialHash2D
from engine.resources.physics_material import load_physics_material

AABB = tuple[float, float, float, float]


class _StaticSolverBody:
    """Lightweight static body representation for the PGS solver."""
    body_type = "static"
    mass = 0.0
    velocity_x = 0.0
    velocity_y = 0.0
    can_sleep = True


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
        self._impulse_solver = ImpulseSolver2D()
        self._solver_iterations: int = 8
        self._body_id_to_island: dict[int, Island2D] = {}
        self._position_correction_ratio: float = 0.05  # Minimal safety net; PGS position solve handles main correction
        self._PUSH_OUT_MIN_OVERLAP: float = 0.005

    def set_event_bus(self, event_bus: Optional[Any]) -> None:  # type: ignore[no-any-explicit]  # EventBus: tipo externo determinado en runtime
        self._event_bus = event_bus

    def update(self, world: World, delta_time: float, shared_grid: SpatialHash2D | None = None) -> None:
        self._step_metrics = {"ccd_bodies": 0, "swept_checks": 0, "candidate_solids": 0, "island_count": 0, "sleeping_islands": 0}
        self._swept_contacts = []
        self._swept_contact_set = set()
        entities = world.get_entities_with(Transform, RigidBody)
        static_like_candidates: dict[int, _SolidCandidate] = {}
        moving_candidates: list[_SolidCandidate] = []
        grid = shared_grid if shared_grid is not None else SpatialHash2D(cell_size=self._spatial_hash_cell_size)

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
                if shared_grid is None:
                    grid.insert(entity.id, solid_aabb)
            else:
                moving_candidates.append(candidate)
        self._last_grid = grid

        moving_candidates.sort(key=lambda candidate: int(candidate.entity.id))

        # ── PASO 1: Integrar fuerzas + recolectar constraints globalmente ──
        all_constraints: list[ContactConstraint2D] = []
        all_bodies: dict[int, Any] = {}
        body_deltas: dict[int, tuple[float, float]] = {}
        body_nearby: dict[int, list[_SolidCandidate]] = {}
        sleeping_body_ids: set[int] = set()
        initial_transform_states: dict[int, tuple[float, float]] = {}
        initial_rigidbody_states: dict[int, tuple[float, float, bool]] = {}
        entity_transforms: dict[int, Transform] = {}
        for entity in world.iter_entities():
            transform = entity.get_component(Transform)
            if transform is not None:
                entity_transforms[int(entity.id)] = transform

        for entity in entities:
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            if transform is None or rigidbody is None or not rigidbody.simulated:
                continue
            effective_type = self._get_effective_body_type(entity)
            if effective_type == "static":
                if rigidbody is not None:
                    rigidbody._clear_force_buffers()
                    rigidbody.velocity_x = 0.0
                    rigidbody.velocity_y = 0.0
                continue

            collider = entity.get_component(Collider)

            # Sleeping check (per-body)
            self._check_sleeping(rigidbody, delta_time)
            if rigidbody.sleeping:
                sleeping_body_ids.add(int(entity.id))
                rigidbody._clear_force_buffers()
                continue

            # ── Force integration ──
            initial_transform_states[int(entity.id)] = (transform.x, transform.y)
            initial_rigidbody_states[int(entity.id)] = (rigidbody.velocity_x, rigidbody.velocity_y, rigidbody.is_grounded)
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
                if rigidbody._impulse_buffer_x != 0.0 or rigidbody._impulse_buffer_y != 0.0:
                    mass = rigidbody.mass
                    if mass > 0.0:
                        rigidbody.velocity_x += rigidbody._impulse_buffer_x / mass
                        rigidbody.velocity_y += rigidbody._impulse_buffer_y / mass
                if rigidbody._force_buffer_x != 0.0 or rigidbody._force_buffer_y != 0.0:
                    mass = rigidbody.mass
                    if mass > 0.0:
                        rigidbody.velocity_x += (rigidbody._force_buffer_x / mass) * delta_time
                        rigidbody.velocity_y += (rigidbody._force_buffer_y / mass) * delta_time
                if rigidbody._torque_buffer != 0.0:
                    inertia = rigidbody.inertia
                    if inertia > 0.0:
                        angular_accel = rigidbody._torque_buffer / inertia
                        rigidbody.angular_velocity += angular_accel * delta_time
                if rigidbody.constant_force_x != 0.0 or rigidbody.constant_force_y != 0.0:
                    mass = rigidbody.mass
                    if mass > 0.0:
                        rigidbody.velocity_x += (rigidbody.constant_force_x / mass) * delta_time
                        rigidbody.velocity_y += (rigidbody.constant_force_y / mass) * delta_time
                if rigidbody.constant_torque != 0.0:
                    inertia = rigidbody.inertia
                    if inertia > 0.0:
                        rigidbody.angular_velocity += (rigidbody.constant_torque / inertia) * delta_time
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

            rigidbody._clear_force_buffers()

            delta_x = 0.0 if rigidbody.freeze_x else rigidbody.velocity_x * delta_time
            delta_y = 0.0 if rigidbody.freeze_y else rigidbody.velocity_y * delta_time

            # Collect candidate solids
            nearby_solids = self._collect_candidate_solids(
                world, entity, rigidbody, collider, transform,
                grid, static_like_candidates, moving_candidates,
                delta_x, delta_y,
            )
            self._step_metrics["candidate_solids"] += len(nearby_solids)
            body_nearby[int(entity.id)] = nearby_solids
            body_deltas[int(entity.id)] = (delta_x, delta_y)

            # ── Construir constraints (sin resolver PGS aun) ──
            if collider is not None and collider.enabled and not collider.is_trigger:
                all_bodies[int(entity.id)] = rigidbody
                tentative_x = transform.x + delta_x
                tentative_y = transform.y + delta_y

                for solid in nearby_solids:
                    if solid.entity.id == entity.id:
                        continue
                    other_rb = solid.entity.get_component(RigidBody)
                    is_static = (other_rb is None or other_rb.body_type == "static")
                    is_dynamic = (other_rb is not None and other_rb.simulated
                                  and other_rb.body_type in ("dynamic", "kinematic"))
                    if not is_static and not is_dynamic:
                        continue
                    other_transform = solid.entity.get_component(Transform)
                    if other_transform is None:
                        continue

                    my_bounds = collider.get_bounds(tentative_x, tentative_y)
                    other_bounds = solid.collider.get_bounds(other_transform.x, other_transform.y)
                    if not self._aabb_overlaps(my_bounds, other_bounds):
                        continue

                    left_a, top_a, right_a, bottom_a = my_bounds
                    left_b, top_b, right_b, bottom_b = other_bounds
                    overlap_left = right_a - left_b
                    overlap_right = right_b - left_a
                    overlap_top = bottom_a - top_b
                    overlap_bottom = bottom_b - top_a
                    overlap_x = min(overlap_left, overlap_right)
                    overlap_y = min(overlap_top, overlap_bottom)

                    if overlap_x < overlap_y:
                        normal_x = 1.0 if tentative_x < other_transform.x else -1.0
                        normal_y = 0.0
                        depth = overlap_x
                    else:
                        normal_x = 0.0
                        normal_y = 1.0 if tentative_y < other_transform.y else -1.0
                        depth = overlap_y

                    if depth < -0.001:
                        continue

                    my_bounce, my_friction_val = self._resolve_material_props(
                        rigidbody.physics_material_override_path, collider,
                    )
                    other_bounce, other_friction_val = self._resolve_material_props(
                        self._get_material_path_from_entity(solid.entity), solid.collider,
                    )
                    restitution = max(my_bounce, other_bounce)
                    if not math.isfinite(restitution):
                        restitution = 0.0
                    restitution = max(0.0, min(1.0, restitution))
                    friction = math.sqrt(max(0.0, my_friction_val) * max(0.0, other_friction_val))
                    if not math.isfinite(friction):
                        friction = 1.0

                    inv_mass_self = 1.0 / rigidbody.mass if (rigidbody.mass > 0 and rigidbody.body_type == "dynamic") else 0.0
                    if other_rb is None or other_rb.body_type == "static":
                        inv_mass_other = 0.0
                        all_bodies[int(solid.entity.id)] = _StaticSolverBody()
                    else:
                        inv_mass_other = 1.0 / other_rb.mass if (other_rb.mass > 0 and other_rb.body_type == "dynamic") else 0.0
                        all_bodies[int(solid.entity.id)] = other_rb

                    total_inv = inv_mass_self + inv_mass_other
                    if total_inv <= 1e-10:
                        continue

                    mass_normal = 1.0 / total_inv
                    mass_tangent = mass_normal
                    # Compute bias from current-depth (not tentative) to avoid
                    # over-correcting collisions that only overlap in speculative positions.
                    current_bounds = collider.get_bounds(transform.x, transform.y)
                    c_left_a, c_top_a, c_right_a, c_bottom_a = current_bounds
                    c_overlap_left = c_right_a - left_b
                    c_overlap_right = right_b - c_left_a
                    c_overlap_top = c_bottom_a - top_b
                    c_overlap_bottom = bottom_b - c_top_a
                    c_overlap_x = min(c_overlap_left, c_overlap_right)
                    c_overlap_y = min(c_overlap_top, c_overlap_bottom)
                    c_current_depth = c_overlap_x if c_overlap_x < c_overlap_y else c_overlap_y
                    c_effective_current = max(0.0, c_current_depth)
                    bias = min(ImpulseSolver2D.MAX_BIAS,
                               ImpulseSolver2D.BAUMGARTE_FACTOR * max(0.0, c_effective_current - ImpulseSolver2D.SLOP) / max(delta_time, 1e-6))
                    contact_x = (max(left_a, left_b) + min(right_a, right_b)) / 2.0
                    contact_y = (max(top_a, top_b) + min(bottom_a, bottom_b)) / 2.0

                    # Compute lever arms for rotational inertia
                    rA_x = contact_x - transform.x
                    rA_y = contact_y - transform.y
                    rB_x = contact_x - other_transform.x
                    rB_y = contact_y - other_transform.y

                    constraint = ContactConstraint2D(
                        entity_a_id=int(entity.id),
                        entity_b_id=int(solid.entity.id),
                        normal_x=normal_x, normal_y=normal_y,
                        tangent_x=-normal_y, tangent_y=normal_x,
                        depth=depth, mass_normal=mass_normal, mass_tangent=mass_tangent,
                        restitution=restitution, friction=friction, bias=bias,
                        contact_x=contact_x, contact_y=contact_y,
                        rA_x=rA_x, rA_y=rA_y, rB_x=rB_x, rB_y=rB_y,
                    )
                    all_constraints.append(constraint)

        # ── Build joint constraints (PGS bilateral) ──
        joint_constraints = self._build_joint_constraints(world, delta_time)
        # Register joint bodies in all_bodies if not already present
        for jc in joint_constraints:
            if jc.entity_a_id not in all_bodies:
                ea = world.get_entity(jc.entity_a_id)
                if ea is not None:
                    rba = ea.get_component(RigidBody)
                    if rba is not None:
                        all_bodies[jc.entity_a_id] = rba
            if jc.entity_b_id not in all_bodies:
                eb = world.get_entity(jc.entity_b_id)
                if eb is not None:
                    rbb = eb.get_component(RigidBody)
                    if rbb is not None:
                        all_bodies[jc.entity_b_id] = rbb
        all_constraints.extend(joint_constraints)

        # ── PASO 2: Construir islas + PGS solve por isla ──
        joint_pairs = self._collect_joint_pairs(world)
        active_body_ids = {eid for eid in body_deltas if eid not in sleeping_body_ids}
        all_body_ids_for_islands = active_body_ids | {eid for eid in all_bodies if eid not in active_body_ids}

        islands = IslandBuilder2D.build_islands(
            all_constraints, joint_pairs, all_body_ids_for_islands,
            self._body_id_to_island,
        )

        sleeping_count = 0
        for island in islands:
            if island.sleeping:
                sleeping_count += 1
                for bid in island.body_ids:
                    body = all_bodies.get(bid)
                    if body is not None and hasattr(body, 'velocity_x'):
                        body.velocity_x = 0.0
                        body.velocity_y = 0.0
                        if hasattr(body, 'sleeping'):
                            body.sleeping = True
                continue

            island_constraints = [c for c in all_constraints
                                  if c.entity_a_id in island.body_ids
                                  and c.entity_b_id in island.body_ids]
            if island_constraints:
                self._impulse_solver.solve(island_constraints, all_bodies, delta_time, self._solver_iterations)

            if island_constraints:
                transforms_for_island = {
                    bid: entity_transforms[bid]
                    for bid in island.body_ids
                    if bid in entity_transforms
                }
                if transforms_for_island:
                    self._impulse_solver.solve_positions(
                        island_constraints, transforms_for_island, all_bodies,
                        delta_time=delta_time, iterations=5,
                    )

            self._check_island_sleeping(island, all_bodies, delta_time)
            if island.sleeping:
                sleeping_count += 1

        self._step_metrics["island_count"] = len(islands)
        self._step_metrics["sleeping_islands"] = sleeping_count

        # Persistir island mapping para siguiente frame
        self._body_id_to_island = {}
        for island in islands:
            for bid in island.body_ids:
                self._body_id_to_island[bid] = island

        # ── PASO 3: Per-body movimiento + push-out ──
        transform_changed = False
        physics_changed = False

        for entity in entities:
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            if transform is None or rigidbody is None or not rigidbody.simulated:
                continue

            eid = int(entity.id)
            before_transform_state = initial_transform_states.get(eid, (transform.x, transform.y))
            before_rigidbody_state = initial_rigidbody_states.get(
                eid, (rigidbody.velocity_x, rigidbody.velocity_y, rigidbody.is_grounded)
            )

            effective_type = self._get_effective_body_type(entity)
            if effective_type == "static":
                physics_changed = physics_changed or before_rigidbody_state != (rigidbody.velocity_x, rigidbody.velocity_y, rigidbody.is_grounded)
                continue

            if int(entity.id) in sleeping_body_ids:
                transform_changed = transform_changed or before_transform_state != (transform.x, transform.y)
                physics_changed = physics_changed or before_rigidbody_state != (rigidbody.velocity_x, rigidbody.velocity_y, rigidbody.is_grounded)
                continue

            collider = entity.get_component(Collider)
            nearby_solids = body_nearby.get(int(entity.id), [])

            # Recalcular deltas con velocidades corregidas por PGS
            delta_x = 0.0 if rigidbody.freeze_x else rigidbody.velocity_x * delta_time
            delta_y = 0.0 if rigidbody.freeze_y else rigidbody.velocity_y * delta_time

            ccd_active = rigidbody.ccd_mode != "disabled"
            continuous_mode = bool(
                collider is not None and collider.enabled
                and (rigidbody.collision_detection_mode == "continuous" or ccd_active)
            )
            if ccd_active or rigidbody.collision_detection_mode == "continuous":
                self._step_metrics["ccd_bodies"] += 1

            cast_shape_mode = rigidbody.ccd_mode == "cast_shape" and collider is not None and collider.enabled

            if cast_shape_mode:
                if (not rigidbody.freeze_x or not rigidbody.freeze_y):
                    hit = self._sweep_shape_cast(entity, transform, collider, nearby_solids, delta_x, delta_y)
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
                if collider is not None and collider.enabled:
                    if not rigidbody.freeze_x:
                        self._resolve_horizontal(transform, rigidbody, collider, nearby_solids)
                rigidbody.is_grounded = False
                if collider is not None and collider.enabled:
                    if not rigidbody.freeze_y:
                        self._resolve_vertical(transform, rigidbody, collider, nearby_solids)
                    if not rigidbody.is_grounded and not rigidbody.freeze_y:
                        rigidbody.is_grounded = self._has_ground_support(entity, transform, collider, nearby_solids)
            else:
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

            if rigidbody.lock_rotation:
                rigidbody.angular_velocity = 0.0

            transform_changed = transform_changed or before_transform_state != (transform.x, transform.y)
            physics_changed = physics_changed or before_rigidbody_state != (rigidbody.velocity_x, rigidbody.velocity_y, rigidbody.is_grounded)

        # StaticBody2D constant velocity (moving platforms)
        for entity in world.get_entities_with(Transform, StaticBody2D):
            transform = entity.get_component(Transform)
            sb = entity.get_component(StaticBody2D)
            if transform is None or sb is None:
                continue
            if sb.constant_linear_velocity_x != 0.0 or sb.constant_linear_velocity_y != 0.0:
                transform.x += sb.constant_linear_velocity_x * delta_time
                transform.y += sb.constant_linear_velocity_y * delta_time
                transform_changed = True
            if sb.constant_angular_velocity != 0.0:
                transform.rotation += sb.constant_angular_velocity * delta_time
                transform_changed = True

        self._resolve_joints(world, delta_time)

        if transform_changed:
            world.touch_transform()
        if physics_changed:
            world.touch_physics()

    def get_step_metrics(self) -> dict[str, float]:
        return dict(self._step_metrics)

    @property
    def solver_iterations(self) -> int:
        """Numero de iteraciones del solver PGS (default 8)."""
        return self._solver_iterations

    @solver_iterations.setter
    def solver_iterations(self, value: int) -> None:
        if value < 1:
            value = 1
        self._solver_iterations = value

    def get_solver_metrics(self) -> dict[str, Any]:
        return {
            "warm_start_cache_size": self._impulse_solver.warm_start_cache_size,
            "iterations": self._solver_iterations,
            "island_count": self._step_metrics.get("island_count", 0),
            "sleeping_islands": self._step_metrics.get("sleeping_islands", 0),
        }

    @property
    def spatial_grid(self) -> SpatialHash2D | None:
        """The spatial hash grid built during the last update(). None before first update."""
        return getattr(self, '_last_grid', None)

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

    def _check_island_sleeping(self, island: Island2D, bodies: dict[int, Any], dt: float) -> None:
        """Check if all bodies in an island are still enough to sleep the whole island."""
        all_still = True
        max_time_to_sleep = 0.5  # default

        for bid in island.body_ids:
            body = bodies.get(bid)
            if body is None:
                continue
            # Static bodies never prevent island sleep (they don't move)
            body_type = getattr(body, 'body_type', 'dynamic')
            if body_type == 'static':
                continue
            if not hasattr(body, 'can_sleep') or not body.can_sleep:
                all_still = False
                break
            if body_type != 'dynamic':
                continue

            vel = math.sqrt(getattr(body, 'velocity_x', 0.0) ** 2 + getattr(body, 'velocity_y', 0.0) ** 2)
            ang = abs(getattr(body, 'angular_velocity', 0.0))
            threshold_lin = getattr(body, 'sleep_linear_threshold', 0.5)
            threshold_ang = getattr(body, 'sleep_angular_threshold', 0.1)
            tts = getattr(body, 'time_to_sleep', 0.5)

            if vel >= threshold_lin or ang >= threshold_ang:
                all_still = False
                break
            max_time_to_sleep = max(max_time_to_sleep, tts)

        if all_still and not island.sleeping:
            island.sleep_timer += dt
            if island.sleep_timer >= max_time_to_sleep:
                island.sleeping = True
                for bid in island.body_ids:
                    body = bodies.get(bid)
                    if body is not None and hasattr(body, 'velocity_x'):
                        body.velocity_x = 0.0
                        body.velocity_y = 0.0
                        if hasattr(body, 'angular_velocity'):
                            body.angular_velocity = 0.0
                        if hasattr(body, 'sleeping'):
                            body.sleeping = True
        elif not all_still:
            island.sleep_timer = 0.0
            island.sleeping = False

    def _get_effective_gravity(
        self, world: World, entity: Entity, transform: Transform, rigidbody: RigidBody
    ) -> tuple[float, float]:
        """Get gravity from area overrides or default global gravity with mode support."""
        overlapping: list[tuple[int, Area2D, Entity]] = []
        for area_entity in world.iter_entities():
            area = area_entity.get_component(Area2D)
            if area is None or not area.enabled:
                continue
            mode = getattr(area, "gravity_space_override", area.space_override)
            if mode == "disabled":
                continue
            if area.gravity_override_x == 0.0 and area.gravity_override_y == 0.0:
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
            overlapping.append((area.priority, area, area_entity))

        if not overlapping:
            return (0.0, self.gravity)

        overlapping.sort(key=lambda x: x[0])

        final_gx = 0.0
        final_gy = self.gravity
        combining = True

        for _priority, area, _area_entity in overlapping:
            mode = getattr(area, "gravity_space_override", area.space_override)
            if mode == "disabled":
                continue
            elif mode == "replace":
                final_gx = area.gravity_override_x
                final_gy = area.gravity_override_y
                combining = False
            elif mode == "replace_combine":
                final_gx = area.gravity_override_x
                final_gy = area.gravity_override_y
                combining = True
            elif mode == "combine_replace":
                if combining:
                    final_gx += area.gravity_override_x
                    final_gy += area.gravity_override_y
                combining = False
            elif mode == "combine":
                if combining:
                    final_gx += area.gravity_override_x
                    final_gy += area.gravity_override_y

        # Point gravity: use the highest-priority REPLACE or REPLACE_COMBINE area
        for _priority, area, area_entity in overlapping:
            mode = getattr(area, "gravity_space_override", area.space_override)
            if mode in ("replace", "replace_combine") and area.gravity_point:
                area_transform = area_entity.get_component(Transform)
                if area_transform is not None and area.gravity_distance_scale > 0.0:
                    dx = area_transform.x - transform.x
                    dy = area_transform.y - transform.y
                    dist = math.hypot(dx, dy)
                    if dist >= 1e-6:
                        strength = max(0.0, 1.0 - dist / area.gravity_distance_scale)
                        mag = math.hypot(area.gravity_override_x, area.gravity_override_y)
                        if mag < 1e-6:
                            mag = self.gravity
                        return (dx / dist * mag * strength, dy / dist * mag * strength)
            break

        return (final_gx, final_gy)

    def _get_body_bounds(self, entity: Entity, transform: Transform) -> tuple[float, float, float, float]:
        """Get AABB for any entity that might fall into an area."""
        collider = entity.get_component(Collider)
        if collider is not None:
            return collider.get_bounds(transform.x, transform.y)
        return (transform.x, transform.y, transform.x, transform.y)

    def _get_effective_linear_damp(
        self, world: World, entity: Entity, transform: Transform, rigidbody: RigidBody
    ) -> float:
        """Get linear damping from area overrides or use body's own damping with mode support."""
        overlapping: list[tuple[int, Area2D, Entity]] = []
        for area_entity in world.iter_entities():
            area = area_entity.get_component(Area2D)
            if area is None or not area.enabled:
                continue
            mode = getattr(area, "linear_damp_space_override", area.space_override)
            if mode == "disabled":
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
            overlapping.append((area.priority, area, area_entity))

        if not overlapping:
            return rigidbody.linear_damping

        overlapping.sort(key=lambda x: x[0])

        final_damp = rigidbody.linear_damping
        combining = True

        for _priority, area, _area_entity in overlapping:
            mode = getattr(area, "linear_damp_space_override", area.space_override)
            if mode == "replace":
                final_damp = area.linear_damp_override
                combining = False
            elif mode == "replace_combine":
                final_damp = area.linear_damp_override
                combining = True
            elif mode == "combine_replace":
                if combining:
                    final_damp += area.linear_damp_override
                combining = False
            elif mode == "combine":
                if combining:
                    final_damp += area.linear_damp_override

        return final_damp

    def _get_effective_angular_damp(
        self, world: World, entity: Entity, transform: Transform, rigidbody: RigidBody
    ) -> float:
        """Get angular damping from area overrides or use body's own damping with mode support."""
        overlapping: list[tuple[int, Area2D, Entity]] = []
        for area_entity in world.iter_entities():
            area = area_entity.get_component(Area2D)
            if area is None or not area.enabled:
                continue
            mode = getattr(area, "angular_damp_space_override", area.space_override)
            if mode == "disabled":
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
            overlapping.append((area.priority, area, area_entity))

        if not overlapping:
            return rigidbody.angular_damping

        overlapping.sort(key=lambda x: x[0])

        final_damp = rigidbody.angular_damping
        combining = True

        for _priority, area, _area_entity in overlapping:
            mode = getattr(area, "angular_damp_space_override", area.space_override)
            if mode == "replace":
                final_damp = area.angular_damp_override
                combining = False
            elif mode == "replace_combine":
                final_damp = area.angular_damp_override
                combining = True
            elif mode == "combine_replace":
                if combining:
                    final_damp += area.angular_damp_override
                combining = False
            elif mode == "combine":
                if combining:
                    final_damp += area.angular_damp_override

        return final_damp

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
        if has_static:
            return "static"
        if has_animatable:
            anim = entity.get_component(AnimatableBody2D)
            if anim is not None and anim.sync_to_physics:
                return "static"
            if rigidbody is not None:
                return rigidbody.body_type
            return "kinematic"
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

    @staticmethod
    def _compute_push_out_ratio(
        my_rigidbody: RigidBody,
        other_entity: Entity,
    ) -> tuple[float, float]:
        """Compute (my_ratio, other_ratio) for mass-weighted positional correction.

        Dynamic bodies share the push-out based on inverse mass ratio.
        Static/kinematic bodies don't move (other_ratio = 0).
        """
        other_rb = other_entity.get_component(RigidBody)
        if other_rb is None or other_rb.body_type != "dynamic":
            return (1.0, 0.0)
        my_mass = max(my_rigidbody.mass, 0.001)
        other_mass = max(other_rb.mass, 0.001)
        total = my_mass + other_mass
        # Inverse mass: lighter body moves more
        my_ratio = other_mass / total
        other_ratio = my_mass / total
        return (my_ratio, other_ratio)

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
            for o_aabb, _shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                o_left, o_top, o_right, o_bottom = o_aabb
                overlap_y = top < o_bottom and bottom > o_top
                overlap_x = left < o_right and right > o_left
                if not overlap_x or not overlap_y:
                    continue
                # Mass-weighted bilateral push-out
                my_ratio, other_ratio = self._compute_push_out_ratio(rigidbody, other.entity)
                if rigidbody.velocity_x > 0:
                    correction = (right - o_left) * self._position_correction_ratio
                    transform.x -= correction * my_ratio
                    if other_ratio > 0.0:
                        other_transform.x += correction * other_ratio
                elif rigidbody.velocity_x < 0:
                    correction = (o_right - left) * self._position_correction_ratio
                    transform.x += correction * my_ratio
                    if other_ratio > 0.0:
                        other_transform.x -= correction * other_ratio
                elif other_ratio > 0.0:
                    # At rest but overlapping another dynamic body — push out based on penetration
                    overlap_right = right - o_left
                    overlap_left = o_right - left
                    if overlap_right > self._PUSH_OUT_MIN_OVERLAP and overlap_right >= overlap_left:
                        correction = overlap_right * self._position_correction_ratio
                        transform.x -= correction * my_ratio
                        other_transform.x += correction * other_ratio
                    elif overlap_left > self._PUSH_OUT_MIN_OVERLAP:
                        correction = overlap_left * self._position_correction_ratio
                        transform.x += correction * my_ratio
                        other_transform.x -= correction * other_ratio
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
            for o_aabb, _shape_def in self._get_entity_shape_aabbs(other.entity, other_transform):
                o_left, o_top, o_right, o_bottom = o_aabb
                overlap_y = top < o_bottom and bottom > o_top
                overlap_x = left < o_right and right > o_left
                if not overlap_x or not overlap_y:
                    continue
                # Mass-weighted bilateral push-out
                my_ratio, other_ratio = self._compute_push_out_ratio(rigidbody, other.entity)
                if rigidbody.velocity_y > 0:
                    correction = (bottom - o_top) * self._position_correction_ratio
                    transform.y -= correction * my_ratio
                    if other_ratio > 0.0:
                        other_transform.y += correction * other_ratio
                    rigidbody.is_grounded = (other_ratio == 0.0)
                    if not rigidbody.is_grounded:
                        other_rb = other.entity.get_component(RigidBody)
                        if other_rb is not None and other_rb.velocity_y <= 1.0:
                            rigidbody.is_grounded = True
                elif rigidbody.velocity_y < 0:
                    correction = (o_bottom - top) * self._position_correction_ratio
                    transform.y += correction * my_ratio
                    if other_ratio > 0.0:
                        other_transform.y -= correction * other_ratio
                elif other_ratio > 0.0:
                    # At rest but overlapping another dynamic body — push out based on penetration
                    overlap_bottom = bottom - o_top
                    overlap_top = o_bottom - top
                    if overlap_bottom > self._PUSH_OUT_MIN_OVERLAP and overlap_bottom >= overlap_top:
                        correction = overlap_bottom * self._position_correction_ratio
                        transform.y -= correction * my_ratio
                        other_transform.y += correction * other_ratio
                    elif overlap_top > self._PUSH_OUT_MIN_OVERLAP:
                        correction = overlap_top * self._position_correction_ratio
                        transform.y += correction * my_ratio
                        other_transform.y -= correction * other_ratio
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
            other_rb = other.entity.get_component(RigidBody)
            if other_rb is not None and other_rb.body_type == "dynamic" and other_rb.velocity_y > 1.0:
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
        for entity in world.get_entities_with(Joint2D):
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
                # Linear part handled by PGS bilateral constraints.
                # Lock relative rotation between the two bodies.
                a_dynamic = rigid_a is not None and rigid_a.body_type == "dynamic"
                b_dynamic = rigid_b is not None and rigid_b.body_type == "dynamic"
                if a_dynamic and b_dynamic:
                    mid_rot = (transform_a.rotation + transform_b.rotation) * 0.5
                    transform_a.rotation = mid_rot
                    transform_b.rotation = mid_rot
                    rigid_a.angular_velocity = 0.0
                    rigid_b.angular_velocity = 0.0
                elif a_dynamic:
                    transform_a.rotation = transform_b.rotation
                    rigid_a.angular_velocity = 0.0
                elif b_dynamic:
                    transform_b.rotation = transform_a.rotation
                    rigid_b.angular_velocity = 0.0
            elif joint.joint_type == "distance":
                # PGS handles velocity-level constraint; this is the final positional pass
                self._resolve_distance_joint(transform_a, transform_b, rigid_a, rigid_b, joint)
            elif joint.joint_type == "pin":
                # Position handled by PGS bilateral constraints
                # Only apply angular limits and motor here
                if joint.angular_limit_enabled and rigid_b:
                    if transform_b.rotation < joint.angular_limit_lower:
                        transform_b.rotation = joint.angular_limit_lower
                    elif transform_b.rotation > joint.angular_limit_upper:
                        transform_b.rotation = joint.angular_limit_upper
                if joint.motor_enabled and rigid_b:
                    rigid_b.angular_velocity += joint.motor_target_velocity * dt
            elif joint.joint_type == "groove":
                self._resolve_groove_joint(transform_a, transform_b, rigid_a, rigid_b, joint)
            elif joint.joint_type == "damped_spring":
                self._resolve_spring_joint(transform_a, transform_b, rigid_a, rigid_b, joint, dt)

    def _collect_joint_pairs(self, world: World) -> list[tuple[int, int]]:
        """Collect (body_a_id, body_b_id) pairs for all active joints.

        Used by IslandBuilder2D to add joint edges to the connectivity graph.
        """
        pairs: list[tuple[int, int]] = []
        for entity in world.get_entities_with(Joint2D):
            joint = entity.get_component(Joint2D)
            if not joint or not joint.enabled or not joint.connected_entity:
                continue
            other = world.get_entity_by_name(joint.connected_entity)
            if not other:
                continue
            pairs.append((int(entity.id), int(other.id)))
        return pairs

    def _build_joint_constraints(
        self, world: World, delta_time: float,
    ) -> list[ContactConstraint2D]:
        """Build PGS-compatible bilateral constraints for fixed, distance, and pin joints."""
        constraints: list[ContactConstraint2D] = []
        for entity in world.get_entities_with(Joint2D):
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
                # Fixed joint: 2 constraints (x and y) to lock relative position
                # Constraint in X
                dx = transform_b.x - transform_a.x
                c_x = ContactConstraint2D(
                    entity_a_id=int(entity.id),
                    entity_b_id=int(other.id),
                    normal_x=1.0, normal_y=0.0,
                    tangent_x=0.0, tangent_y=1.0,
                    depth=abs(dx),
                    mass_normal=self._joint_effective_mass(rigid_a, rigid_b),
                    mass_tangent=0.0,
                    restitution=0.0, friction=0.0,
                    bias=dx * joint.joint_stiffness / max(delta_time, 1e-6),
                    is_bilateral=True,
                )
                constraints.append(c_x)
                # Constraint in Y
                dy = transform_b.y - transform_a.y
                c_y = ContactConstraint2D(
                    entity_a_id=int(entity.id),
                    entity_b_id=int(other.id),
                    normal_x=0.0, normal_y=1.0,
                    tangent_x=-1.0, tangent_y=0.0,
                    depth=abs(dy),
                    mass_normal=self._joint_effective_mass(rigid_a, rigid_b),
                    mass_tangent=0.0,
                    restitution=0.0, friction=0.0,
                    bias=dy * joint.joint_stiffness / max(delta_time, 1e-6),
                    is_bilateral=True,
                )
                constraints.append(c_y)

            elif joint.joint_type == "distance":
                dx = transform_b.x - transform_a.x
                dy = transform_b.y - transform_a.y
                dist = math.hypot(dx, dy)
                if dist < 0.0001:
                    continue
                nx = dx / dist
                ny = dy / dist
                error = dist - joint.rest_length
                c = ContactConstraint2D(
                    entity_a_id=int(entity.id),
                    entity_b_id=int(other.id),
                    normal_x=nx, normal_y=ny,
                    tangent_x=-ny, tangent_y=nx,
                    depth=abs(error),
                    mass_normal=self._joint_effective_mass(rigid_a, rigid_b),
                    mass_tangent=0.0,
                    restitution=0.0, friction=0.0,
                    bias=error * joint.joint_stiffness / max(delta_time, 1e-6),
                    is_bilateral=True,
                )
                constraints.append(c)

            elif joint.joint_type == "pin":
                # Pin joint: constrain positions to same point
                # softness=0 → hard pin (fast correction); softness>0 → soft pin (slow correction)
                pin_stiffness = 1.0 if joint.softness <= 0.0 else max(0.01, 1.0 / (1.0 + joint.softness * 10.0))
                # Constraint in X
                dx = transform_b.x - transform_a.x
                c_x = ContactConstraint2D(
                    entity_a_id=int(entity.id),
                    entity_b_id=int(other.id),
                    normal_x=1.0, normal_y=0.0,
                    tangent_x=0.0, tangent_y=1.0,
                    depth=abs(dx),
                    mass_normal=self._joint_effective_mass(rigid_a, rigid_b),
                    mass_tangent=0.0,
                    restitution=0.0, friction=0.0,
                    bias=dx * pin_stiffness / max(delta_time, 1e-6),
                    is_bilateral=True,
                )
                constraints.append(c_x)
                # Constraint in Y
                dy = transform_b.y - transform_a.y
                c_y = ContactConstraint2D(
                    entity_a_id=int(entity.id),
                    entity_b_id=int(other.id),
                    normal_x=0.0, normal_y=1.0,
                    tangent_x=-1.0, tangent_y=0.0,
                    depth=abs(dy),
                    mass_normal=self._joint_effective_mass(rigid_a, rigid_b),
                    mass_tangent=0.0,
                    restitution=0.0, friction=0.0,
                    bias=dy * pin_stiffness / max(delta_time, 1e-6),
                    is_bilateral=True,
                )
                constraints.append(c_y)

        return constraints

    @staticmethod
    def _joint_effective_mass(
        rigid_a: RigidBody | None,
        rigid_b: RigidBody | None,
    ) -> float:
        """Compute effective mass for a joint constraint (linear only)."""
        inv_a = 1.0 / rigid_a.mass if (rigid_a and rigid_a.body_type == "dynamic" and rigid_a.mass > 0.0) else 0.0
        inv_b = 1.0 / rigid_b.mass if (rigid_b and rigid_b.body_type == "dynamic" and rigid_b.mass > 0.0) else 0.0
        total = inv_a + inv_b
        return 1.0 / total if total > 1e-10 else 0.0

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
        joint: Joint2D,
    ) -> None:
        """Distance joint: maintain a fixed distance between two bodies via position correction."""
        dx = trans_b.x - trans_a.x
        dy = trans_b.y - trans_a.y
        dist = math.hypot(dx, dy)
        if dist < 0.0001:
            return

        # Direction normal from A to B
        nx = dx / dist
        ny = dy / dist

        # Distance error (positive = too far, negative = too close)
        error = dist - joint.rest_length

        # Mass-weighted position correction
        inv_mass_a = 1.0 / rigid_a.mass if (rigid_a and rigid_a.body_type == "dynamic" and rigid_a.mass > 0.0) else 0.0
        inv_mass_b = 1.0 / rigid_b.mass if (rigid_b and rigid_b.body_type == "dynamic" and rigid_b.mass > 0.0) else 0.0
        total_inv = inv_mass_a + inv_mass_b
        if total_inv <= 0.0:
            return

        correction = error * joint.joint_stiffness / total_inv
        if rigid_a and rigid_a.body_type == "dynamic":
            trans_a.x += nx * correction * inv_mass_a
            trans_a.y += ny * correction * inv_mass_a
        if rigid_b and rigid_b.body_type == "dynamic":
            trans_b.x -= nx * correction * inv_mass_b
            trans_b.y -= ny * correction * inv_mass_b

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
