from __future__ import annotations

import math
from typing import Any, Optional

from engine.components.animatable_body_2d import AnimatableBody2D
from engine.components.collider import Collider
from engine.components.collision_filter_2d import CollisionFilter2D
from engine.components.collision_polygon_2d import CollisionPolygon2D
from engine.components.collision_shape_2d import CollisionShape2D
from engine.components.collision_shape_set_2d import CollisionShapeSet2D
from engine.components.rigidbody import RigidBody
from engine.components.static_body_2d import StaticBody2D
from engine.components.transform import Transform
from engine.physics.backend import (
    MotionResult2D,
    MoveResult2D,
    PhysicsAABBHit,
    PhysicsBackend,
    PhysicsContact,
    PhysicsRayHit,
    PhysicsShapeCastHit,
)
from engine.physics.shapes import ShapeFactory


class LegacyAABBPhysicsBackend(PhysicsBackend):
    """Adapta PhysicsSystem + CollisionSystem existentes al contrato pluggable."""

    backend_name = "legacy_aabb"

    def __init__(self, physics_system: Any, collision_system: Any, event_bus: Optional[Any] = None) -> None:
        self._physics_system = physics_system
        self._collision_system = collision_system
        self._event_bus = event_bus
        self._registered_bodies: set[int] = set()
        self._registered_shapes: set[int] = set()
        self._latest_contacts: list[PhysicsContact] = []
        self._synced_world_id: int | None = None
        self._synced_structure_version: int | None = None

    def set_event_bus(self, event_bus: Optional[Any]) -> None:
        self._event_bus = event_bus
        if self._collision_system is not None and hasattr(self._collision_system, "set_event_bus") and event_bus is not None:
            self._collision_system.set_event_bus(event_bus)

    def create_body(self, entity: Any) -> None:
        self._registered_bodies.add(int(entity.id))
        self._invalidate_sync_cache()

    def destroy_body(self, entity_id: int) -> None:
        self._registered_bodies.discard(int(entity_id))
        self._registered_shapes.discard(int(entity_id))
        self._invalidate_sync_cache()

    def create_shape(self, entity: Any) -> None:
        self._registered_shapes.add(int(entity.id))
        self._invalidate_sync_cache()

    def sync_world(self, world: Any) -> None:
        world_id = id(world)
        structure_version = self._get_structure_version(world)
        if (
            structure_version is not None
            and self._synced_world_id == world_id
            and self._synced_structure_version == structure_version
        ):
            return

        registered_bodies: set[int] = set()
        registered_shapes: set[int] = set()
        for entity in world.get_all_entities():
            if entity.get_component(Transform) is None:
                continue
            entity_id = int(entity.id)
            if entity.get_component(Collider) is not None:
                registered_shapes.add(entity_id)
            if entity.get_component(RigidBody) is not None:
                registered_bodies.add(entity_id)

        self._registered_bodies = registered_bodies
        self._registered_shapes = registered_shapes
        self._synced_world_id = world_id if structure_version is not None else None
        self._synced_structure_version = structure_version

    def step(self, world: Any, dt: float) -> None:
        self.sync_world(world)
        self._latest_contacts = []
        if self._physics_system is not None:
            self._physics_system.update(world, dt)
        if self._collision_system is not None:
            self._collision_system.update(world)
        self._latest_contacts.extend(self._build_overlap_contacts())
        self._append_swept_contacts(world)

    def query_ray(
        self,
        world: Any,
        origin: tuple[float, float],
        direction: tuple[float, float],
        max_distance: float,
    ) -> list[PhysicsRayHit]:
        ox, oy = float(origin[0]), float(origin[1])
        dx, dy = float(direction[0]), float(direction[1])
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return []
        dx /= length
        dy /= length
        hits: list[PhysicsRayHit] = []
        for entity in world.get_all_entities() if hasattr(world, "get_all_entities") else []:
            transform = entity.get_component(Transform) if hasattr(entity, "get_component") else None
            if transform is None:
                continue
            if not self._entity_has_query_shapes(entity):
                continue
            for _shape_idx, shape_inst, is_trigger in self._get_entity_query_shapes(entity, transform):
                aabb = shape_inst.get_aabb() if hasattr(shape_inst, "get_aabb") else (transform.x - 8, transform.y - 8, transform.x + 8, transform.y + 8)
                left, top, right, bottom = aabb
                result = self._ray_aabb_distance(ox, oy, dx, dy, left, top, right, bottom, max_distance)
                if result is None:
                    continue
                distance, normal = result
                hits.append(
                    {
                        "entity": entity.name if hasattr(entity, "name") else "",
                        "entity_id": entity.id if hasattr(entity, "id") else 0,
                        "distance": distance,
                        "point": {"x": ox + dx * distance, "y": oy + dy * distance},
                        "normal": {"x": normal[0], "y": normal[1]},
                        "is_trigger": bool(is_trigger),
                    }
                )
        return sorted(hits, key=lambda item: (float(item["distance"]), int(item["entity_id"])))

    def query_aabb(self, world: Any, bounds: tuple[float, float, float, float]) -> list[PhysicsAABBHit]:
        left, top, right, bottom = [float(value) for value in bounds]
        hits: list[PhysicsAABBHit] = []
        for entity in world.get_all_entities() if hasattr(world, "get_all_entities") else []:
            transform = entity.get_component(Transform) if hasattr(entity, "get_component") else None
            if transform is None:
                continue
            if not self._entity_has_query_shapes(entity):
                continue
            for _shape_idx, shape_inst, is_trigger in self._get_entity_query_shapes(entity, transform):
                aabb = shape_inst.get_aabb() if hasattr(shape_inst, "get_aabb") else (transform.x - 8, transform.y - 8, transform.x + 8, transform.y + 8)
                e_left, e_top, e_right, e_bottom = aabb
                if left < e_right and right > e_left and top < e_bottom and bottom > e_top:
                    hits.append(
                        {
                            "entity": entity.name if hasattr(entity, "name") else "",
                            "entity_id": entity.id if hasattr(entity, "id") else 0,
                            "is_trigger": bool(is_trigger),
                        }
                    )
        return hits

    def query_shape_cast(
        self,
        world: Any,
        shape_type: str,
        shape_size: tuple[float, float],
        origin: tuple[float, float],
        direction: tuple[float, float],
        max_distance: float,
        shape_params: Optional[dict] = None,
    ) -> list[PhysicsShapeCastHit]:
        ox, oy = float(origin[0]), float(origin[1])
        dx, dy = float(direction[0]), float(direction[1])

        # Build sweep shape params from shape_size or explicit shape_params
        if shape_params is not None:
            params = dict(shape_params)
            if shape_type == "polygon":
                verts = params.get("vertices")
                if not isinstance(verts, list) or len(verts) < 3:
                    raise ValueError(
                        f"shape_cast with shape_type='polygon' requires shape_params "
                        f"with 'vertices' list of at least 3 points; got {verts!r}"
                    )
        else:
            sw, sh = float(shape_size[0]), float(shape_size[1])
            if shape_type in ("circle",):
                params = {"radius": sw / 2.0}
            elif shape_type in ("capsule",):
                params = {"radius": sw / 2.0, "height": sh}
            elif shape_type in ("polygon",):
                hw, hh = sw / 2.0, sh / 2.0
                params = {"vertices": [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]}
            else:
                params = {"width": sw, "height": sh}

        best_hit: Optional[dict] = None
        best_fraction = float("inf")

        # Broad-phase: union AABB of sweep at t=0 and t=max
        sweep_origin = ShapeFactory.build_from_params(shape_type, ox, oy, **params)
        sweep_end = ShapeFactory.build_from_params(
            shape_type, ox + dx * max_distance, oy + dy * max_distance, **params
        )
        so_aabb = sweep_origin.get_aabb()
        se_aabb = sweep_end.get_aabb()
        sweep_left = min(so_aabb[0], se_aabb[0])
        sweep_top = min(so_aabb[1], se_aabb[1])
        sweep_right = max(so_aabb[2], se_aabb[2])
        sweep_bottom = max(so_aabb[3], se_aabb[3])

        for entity in world.get_all_entities() if hasattr(world, "get_all_entities") else []:
            transform = entity.get_component(Transform) if hasattr(entity, "get_component") else None
            if transform is None:
                continue
            if not self._entity_has_query_shapes(entity):
                continue
            for _shape_idx, shape_inst, is_trigger in self._get_entity_query_shapes(entity, transform):
                # Broad-phase AABB test
                aabb = shape_inst.get_aabb() if hasattr(shape_inst, "get_aabb") else (transform.x - 8, transform.y - 8, transform.x + 8, transform.y + 8)
                c_left, c_top, c_right, c_bottom = aabb
                if not (
                    sweep_left < c_right
                    and sweep_right > c_left
                    and sweep_top < c_bottom
                    and sweep_bottom > c_top
                ):
                    continue

                target_info = {
                    "entity": entity.name if hasattr(entity, "name") else "",
                    "entity_id": int(entity.id) if hasattr(entity, "id") else 0,
                    "is_trigger": bool(is_trigger),
                }

                result = self._swept_toi(
                    shape_type=shape_type,
                    shape_params=params,
                    origin=(ox, oy),
                    direction=(dx, dy),
                    max_distance=max_distance,
                    target_shape=shape_inst,
                    target_info=target_info,
                )

                if result is not None and result["fraction"] < best_fraction:
                    best_fraction = result["fraction"]
                    best_hit = {
                        "entity": str(result["entity"]),
                        "entity_id": int(result["entity_id"]),
                        "position": {"x": float(result["position"]["x"]), "y": float(result["position"]["y"])},
                        "normal": {"x": float(result["normal"]["x"]), "y": float(result["normal"]["y"])},
                        "fraction": float(result["fraction"]),
                        "is_trigger": bool(result.get("is_trigger", False)),
                    }

        return [best_hit] if best_hit is not None else []

    def _swept_toi(
        self,
        shape_type: str,
        shape_params: dict[str, float],
        origin: tuple[float, float],
        direction: tuple[float, float],
        max_distance: float,
        target_shape: Any,
        target_info: dict,
    ) -> Optional[dict]:
        """Binary-search TOI for a single target shape. Delegates to swept_collision."""
        from engine.physics.swept_collision import swept_shape_toi

        return swept_shape_toi(
            shape_type=shape_type,
            shape_params=shape_params,
            origin=origin,
            direction=direction,
            max_distance=max_distance,
            target_shape=target_shape,
            target_info=target_info,
            epsilon=0.001,
            max_iter=64,
        )

    @staticmethod
    def _motion_result_no_hit(mx: float, my: float) -> MotionResult2D:
        """Return MotionResult2D for no collision (full travel)."""
        return MotionResult2D(
            travel_x=mx,
            travel_y=my,
            remainder_x=0.0,
            remainder_y=0.0,
            collision_safe_fraction=1.0,
        )

    @staticmethod
    def _slide_remainder(
        remainder_x: float, remainder_y: float,
        normal_x: float, normal_y: float,
    ) -> tuple[float, float]:
        """Slide remainder vector along collision normal (Godot Vector2.slide)."""
        dot = remainder_x * normal_x + remainder_y * normal_y
        return (remainder_x - dot * normal_x, remainder_y - dot * normal_y)

    @staticmethod
    def _is_one_way_ignorable(
        motion_x: float, motion_y: float,
        normal_x: float, normal_y: float,
        target_entity: Any,
    ) -> bool:
        """Check if a one-way collision should be ignored.

        Godot algorithm: pass through when collision normal opposes
        the one-way direction (body is on the back side of the platform).
        dot(normal, one_way_direction) < 0 → pass through.
        """
        collider_check = target_entity.get_component(Collider) if hasattr(target_entity, "get_component") else None
        if collider_check is None or not collider_check.one_way_collision:
            return False
        ow_dir_x = float(getattr(collider_check, "one_way_collision_direction_x", 0.0))
        ow_dir_y = float(getattr(collider_check, "one_way_collision_direction_y", -1.0))
        # If collision normal opposes one-way direction, body is on pass-through side
        dot = normal_x * ow_dir_x + normal_y * ow_dir_y
        return dot < 0.0

    def _get_motion_body_shapes(self, entity: Any, transform: Any) -> list[tuple[int, str, Any]]:
        """Return list of (shape_index, shape_type, ShapeInstance) for the moving entity."""
        shapes: list[tuple[int, str, Any]] = []
        shape_set = entity.get_component(CollisionShapeSet2D) if hasattr(entity, "get_component") else None
        if shape_set is not None:
            for i, shape_def in enumerate(shape_set.shapes):
                if shape_def.disabled:
                    continue
                try:
                    shape_inst = ShapeFactory.build_from_def(shape_def, transform.x, transform.y)
                    shapes.append((i, shape_def.shape_type, shape_inst))
                except (ValueError, TypeError):
                    continue
            if shapes:
                return shapes
        collider = entity.get_component(Collider) if hasattr(entity, "get_component") else None
        if collider is not None and collider.enabled:
            shape_inst = ShapeFactory.build(collider, transform.x, transform.y)
            shapes.append((0, collider.shape_type, shape_inst))
        return shapes

    def _collect_motion_targets(
        self, world: Any, entity: Any, transform: Any,
        mx: float, my: float, margin: float,
        exclude_set: set[int], collision_mask: int,
        collide_with_bodies: bool, collide_with_areas: bool,
    ) -> list[tuple[int, Any, Any, Any]]:
        """Collect (target_shape_index, ShapeInstance, Transform, Entity) for all potential collision targets."""
        targets: list[tuple[int, Any, Any, Any]] = []
        self_id = int(entity.id) if hasattr(entity, "id") else -1

        for other in world.get_all_entities() if hasattr(world, "get_all_entities") else []:
            other_id = int(other.id) if hasattr(other, "id") else -1
            if other_id == self_id or other_id in exclude_set:
                continue
            if not self._can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform) if hasattr(other, "get_component") else None
            if other_transform is None:
                continue

            # Check body components for body vs area discrimination
            rb = other.get_component(RigidBody) if hasattr(other, "get_component") else None
            anim = other.get_component(AnimatableBody2D) if hasattr(other, "get_component") else None
            sb = other.get_component(StaticBody2D) if hasattr(other, "get_component") else None
            shape_set_check = other.get_component(CollisionShapeSet2D) if hasattr(other, "get_component") else None

            has_body_component = rb is not None or anim is not None or sb is not None or shape_set_check is not None

            is_area_like = False
            if not has_body_component:
                collider_check = other.get_component(Collider) if hasattr(other, "get_component") else None
                if collider_check is None or collider_check.is_trigger:
                    is_area_like = True
            else:
                # Has a body component — only area-like if trigger collider
                collider_check = other.get_component(Collider) if hasattr(other, "get_component") else None
                if collider_check is not None and collider_check.is_trigger:
                    # But check if CollisionShapeSet2D has non-trigger shapes
                    if shape_set_check is not None:
                        non_trigger_shapes = shape_set_check.get_enabled_non_trigger_shapes()
                        is_area_like = len(non_trigger_shapes) == 0
                    else:
                        is_area_like = True

            if is_area_like and not collide_with_areas:
                continue
            if not is_area_like and not collide_with_bodies:
                continue

            # collision_mask filtering: check target's layer against mask
            if collision_mask != 0xFFFFFFFF:
                target_filter = other.get_component(CollisionFilter2D) if hasattr(other, "get_component") else None
                target_layer_val = target_filter.collision_layer if target_filter is not None else 1
                if (collision_mask & target_layer_val) == 0:
                    continue

            for t_idx, t_shape in self._get_target_shapes(other, other_transform):
                targets.append((t_idx, t_shape, other_transform, other))
        return targets

    @staticmethod
    def _get_target_shapes(entity: Any, transform: Any) -> list[tuple[int, Any]]:
        """Yield (shape_index, ShapeInstance) for a target entity."""
        shapes: list[tuple[int, Any]] = []
        shape_set = entity.get_component(CollisionShapeSet2D) if hasattr(entity, "get_component") else None
        if shape_set is not None:
            for i, shape_def in enumerate(shape_set.shapes):
                if shape_def.disabled or shape_def.is_trigger:
                    continue
                try:
                    shape_inst = ShapeFactory.build_from_def(shape_def, transform.x, transform.y)
                    shapes.append((i, shape_inst))
                except (ValueError, TypeError):
                    continue
            if shapes:
                return shapes
        collider = entity.get_component(Collider) if hasattr(entity, "get_component") else None
        if collider is not None and collider.enabled and not collider.is_trigger:
            shape_inst = ShapeFactory.build(collider, transform.x, transform.y)
            shapes.append((0, shape_inst))
        return shapes

    @staticmethod
    def _get_entity_query_shapes(entity: Any, transform: Any) -> list[tuple[int, Any, bool]]:
        """Return list of (shape_index, ShapeInstance, is_trigger) for query purposes.

        Covers: CollisionShapeSet2D, CollisionShape2D, CollisionPolygon2D, Collider.
        Returns empty list if entity has no collision geometry.
        """
        shapes: list[tuple[int, Any, bool]] = []
        shape_set = entity.get_component(CollisionShapeSet2D) if hasattr(entity, "get_component") else None
        if shape_set is not None:
            for i, shape_def in enumerate(shape_set.shapes):
                if shape_def.disabled:
                    continue
                try:
                    shape_inst = ShapeFactory.build_from_def(shape_def, transform.x, transform.y)
                    shapes.append((i, shape_inst, shape_def.is_trigger))
                except (ValueError, TypeError):
                    continue
            if shapes:
                return shapes

        # Check CollisionShape2D
        shape_2d = entity.get_component(CollisionShape2D) if hasattr(entity, "get_component") else None
        if shape_2d is not None and not shape_2d.disabled:
            bounds = shape_2d.get_bounds(transform.x, transform.y)
            from engine.physics.shapes import AABBShape
            aabb_shape = AABBShape(bounds[0], bounds[1], bounds[2], bounds[3])
            shapes.append((0, aabb_shape, False))
            if shapes:
                return shapes

        # Check CollisionPolygon2D
        poly_2d = entity.get_component(CollisionPolygon2D) if hasattr(entity, "get_component") else None
        if poly_2d is not None and not poly_2d.disabled:
            bounds = poly_2d.get_bounds(transform.x, transform.y)
            from engine.physics.shapes import AABBShape
            aabb_shape = AABBShape(bounds[0], bounds[1], bounds[2], bounds[3])
            shapes.append((0, aabb_shape, False))
            if shapes:
                return shapes

        # Fallback to Collider
        collider = entity.get_component(Collider) if hasattr(entity, "get_component") else None
        if collider is not None and collider.enabled:
            shape_inst = ShapeFactory.build(collider, transform.x, transform.y)
            shapes.append((0, shape_inst, collider.is_trigger))
        return shapes

    @staticmethod
    def _entity_has_query_shapes(entity: Any) -> bool:
        """Check if entity has any collision geometry for query purposes."""
        if not hasattr(entity, "get_component"):
            return False
        shape_set = entity.get_component(CollisionShapeSet2D)
        if shape_set is not None:
            enabled = shape_set.get_enabled_non_trigger_shapes() if hasattr(shape_set, "get_enabled_non_trigger_shapes") else shape_set.shapes
            if enabled:
                return True
        shape_2d = entity.get_component(CollisionShape2D)
        if shape_2d is not None and not shape_2d.disabled:
            return True
        poly_2d = entity.get_component(CollisionPolygon2D)
        if poly_2d is not None and not poly_2d.disabled:
            return True
        collider = entity.get_component(Collider)
        return collider is not None and collider.enabled

    @staticmethod
    def _get_entity_velocity(entity: Any) -> tuple[float, float]:
        """Extract velocity from entity's RigidBody or AnimatableBody2D."""
        if entity is None:
            return (0.0, 0.0)
        rb = entity.get_component(RigidBody) if hasattr(entity, "get_component") else None
        if rb is not None:
            return (float(rb.velocity_x), float(rb.velocity_y))
        anim = entity.get_component(AnimatableBody2D) if hasattr(entity, "get_component") else None
        if anim is not None:
            return (0.0, 0.0)
        sb = entity.get_component(StaticBody2D) if hasattr(entity, "get_component") else None
        if sb is not None:
            return (float(sb.constant_linear_velocity_x), float(sb.constant_linear_velocity_y))
        return (0.0, 0.0)

    @staticmethod
    def _find_motion_target_entity(
        targets: list[tuple[int, Any, Any, Any]], entity_id: int,
    ) -> Any:
        for _t_idx, _t_shape, _t_transform, t_entity in targets:
            if hasattr(t_entity, "id") and int(t_entity.id) == entity_id:
                return t_entity
        return None

    @staticmethod
    def _shape_instance_to_params(shape: Any, shape_type: str) -> dict[str, Any]:
        """Convert a ShapeInstance to params dict for swept_shape_toi."""
        if shape_type == "box":
            return {"width": getattr(shape, "width", shape.half_w * 2), "height": getattr(shape, "height", shape.half_h * 2)}
        elif shape_type == "circle":
            return {"radius": shape.radius}
        elif shape_type == "capsule":
            return {"radius": shape.radius, "height": getattr(shape, "height", getattr(shape, "capsule_height", 32.0))}
        elif shape_type == "polygon":
            return {"vertices": [list(p) for p in shape.vertices]} if hasattr(shape, "vertices") else {"width": getattr(shape, "width", shape.half_w * 2), "height": getattr(shape, "height", shape.half_h * 2)}
        return {"width": getattr(shape, "width", shape.half_w * 2), "height": getattr(shape, "height", shape.half_h * 2)}

    @staticmethod
    def _motion_sweep_aabb(shape: Any, ox: float, oy: float, mx: float, my: float, margin: float = 0.08) -> tuple[float, float, float, float]:
        """Compute union AABB of shape at origin and at origin+motion, expanded by margin."""
        if hasattr(shape, "get_aabb"):
            s_aabb = shape.get_aabb()
            left_start, top_start, right_start, bottom_start = s_aabb
            left_end = left_start + mx
            right_end = right_start + mx
            top_end = top_start + my
            bottom_end = bottom_start + my
            return (
                min(left_start, left_end) - margin,
                min(top_start, top_end) - margin,
                max(right_start, right_end) + margin,
                max(bottom_start, bottom_end) + margin,
            )
        return (ox - margin, oy - margin, ox + mx + margin, oy + my + margin)

    @staticmethod
    def _shape_aabb(shape: Any, tx: float, ty: float) -> tuple[float, float, float, float]:
        """Get AABB for a shape instance."""
        if hasattr(shape, "get_aabb"):
            aabb = shape.get_aabb()
            return aabb
        return (tx - 8, ty - 8, tx + 8, ty + 8)

    @staticmethod
    def _aabbs_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    def collect_contacts(self, world: Any) -> list[PhysicsContact]:
        del world
        return list(self._latest_contacts)

    def get_step_metrics(self) -> dict[str, float]:
        if self._physics_system is not None and hasattr(self._physics_system, "get_step_metrics"):
            return dict(self._physics_system.get_step_metrics())
        return {"ccd_bodies": 0, "swept_checks": 0}

    # ------------------------------------------------------------------
    # body_test_motion
    # ------------------------------------------------------------------

    def body_test_motion(
        self,
        world: Any,
        entity: Any,
        motion: tuple[float, float],
        margin: float = 0.08,
        recovery_as_collision: bool = False,
        exclude_ids: Optional[list[int]] = None,
        collision_mask: int = 0xFFFFFFFF,
        collide_with_bodies: bool = True,
        collide_with_areas: bool = False,
    ) -> MotionResult2D:
        """Non-mutating swept motion test. Equivalent to Godot body_test_motion.

        Sweeps the entity along motion vector and returns the first collision
        found. Does NOT modify the entity's Transform.
        """
        transform = entity.get_component(Transform) if hasattr(entity, "get_component") else None
        if transform is None:
            return self._motion_result_no_hit(float(motion[0]), float(motion[1]))

        mx, my = float(motion[0]), float(motion[1])
        exclude_set: set[int] = set(exclude_ids) if exclude_ids else set()
        exclude_set.discard(int(entity.id) if hasattr(entity, "id") else -1)

        # Build moving body shapes
        local_shapes = self._get_motion_body_shapes(entity, transform)

        # Build target list
        targets = self._collect_motion_targets(
            world, entity, transform, mx, my, margin, exclude_set,
            collision_mask, collide_with_bodies, collide_with_areas,
        )

        # Recovery check: if entity starts overlapping, report as collision
        if recovery_as_collision:
            for shape_idx, _shape_type, moving_shape in local_shapes:
                self_shape_aabb = moving_shape.get_aabb()
                for t_idx, t_shape, t_transform, t_entity in targets:
                    t_aabb = self._shape_aabb(t_shape, t_transform.x, t_transform.y)
                    if self._aabbs_overlap(self_shape_aabb, t_aabb):
                        cvx, cvy = self._get_entity_velocity(t_entity)
                        return MotionResult2D(
                            travel_x=0.0,
                            travel_y=0.0,
                            remainder_x=mx,
                            remainder_y=my,
                            collision_point_x=float(transform.x),
                            collision_point_y=float(transform.y),
                            collision_normal_x=0.0,
                            collision_normal_y=0.0,
                            collider_velocity_x=cvx,
                            collider_velocity_y=cvy,
                            collision_depth=0.0,
                            collision_safe_fraction=0.0,
                            collision_unsafe_fraction=1.0,
                            collision_local_shape=shape_idx,
                            collider_id=int(t_entity.id) if hasattr(t_entity, "id") else 0,
                            collider_entity_name=str(t_entity.name) if hasattr(t_entity, "name") else "",
                            collider_shape=t_idx,
                        )

        best_hit: Optional[dict] = None
        best_fraction = float("inf")
        best_moving_shape_idx = -1
        best_target_shape_idx: int = -1

        for shape_idx, shape_type, moving_shape in local_shapes:
            shape_params = self._shape_instance_to_params(moving_shape, shape_type)
            ox, oy = float(transform.x), float(transform.y)

            # AABB of swept shape for broad phase
            sweep_aabb = self._motion_sweep_aabb(moving_shape, ox, oy, mx, my, margin)

            for target_idx, target_shape, target_transform, target_entity in targets:
                # Broad phase
                t_aabb = self._shape_aabb(target_shape, target_transform.x, target_transform.y)
                if not self._aabbs_overlap(sweep_aabb, t_aabb):
                    continue

                target_info = {
                    "entity": target_entity.name if hasattr(target_entity, "name") else "",
                    "entity_id": int(target_entity.id) if hasattr(target_entity, "id") else 0,
                    "is_trigger": False,
                }

                distance = math.hypot(mx, my)
                if distance <= 1e-9:
                    continue

                dx, dy = mx / distance, my / distance

                hit = self._swept_toi(
                    shape_type=shape_type,
                    shape_params=shape_params,
                    origin=(ox, oy),
                    direction=(dx, dy),
                    max_distance=distance,
                    target_shape=target_shape,
                    target_info=target_info,
                )

                if hit is not None and hit.get("fraction", 1.0) < best_fraction:
                    best_fraction = float(hit["fraction"])
                    best_hit = hit
                    best_moving_shape_idx = shape_idx
                    best_target_shape_idx = target_idx

        if best_hit is not None and best_fraction < 1.0:
            fraction = best_fraction
            # travel = fraction of motion
            travel_x = mx * fraction
            travel_y = my * fraction
            # remainder = what's left
            remainder_x = mx * (1.0 - fraction)
            remainder_y = my * (1.0 - fraction)

            # Get collider velocity
            hit_entity_id = best_hit.get("entity_id", 0)
            hit_entity = self._find_motion_target_entity(targets, hit_entity_id)
            cvx, cvy = self._get_entity_velocity(hit_entity) if hit_entity is not None else (0.0, 0.0)

            pos = best_hit.get("position", {"x": 0.0, "y": 0.0})
            nrm = best_hit.get("normal", {"x": 0.0, "y": 0.0})

            return MotionResult2D(
                travel_x=travel_x,
                travel_y=travel_y,
                remainder_x=remainder_x,
                remainder_y=remainder_y,
                collision_point_x=float(pos["x"]),
                collision_point_y=float(pos["y"]),
                collision_normal_x=float(nrm["x"]),
                collision_normal_y=float(nrm["y"]),
                collider_velocity_x=cvx,
                collider_velocity_y=cvy,
                collision_depth=0.0,
                collision_safe_fraction=fraction,
                collision_unsafe_fraction=1.0 - fraction,
                collision_local_shape=best_moving_shape_idx,
                collider_id=int(hit_entity_id),
                collider_entity_name=str(best_hit.get("entity", "")),
                collider_shape=best_target_shape_idx,
            )

        # No collision — full travel
        return self._motion_result_no_hit(mx, my)

    # ------------------------------------------------------------------
    # move_and_slide / move_and_collide
    # ------------------------------------------------------------------

    def _recover_from_penetration(
        self,
        world: Any,
        entity: Any,
        transform: Any,
        collider: Collider,
        solids: list[Any],
        max_attempts: int = 4,
        margin: float = 0.08,
        recovery_factor: float = 0.6,
    ) -> bool:
        """Recovery phase: push entity out of overlapping solids before main sweep.

        Godot equivalent: test_body_motion STEP 1 — FREE BODY IF STUCK.
        Uses sequential resolution: each iteration finds the deepest penetration
        and pushes out on that axis, then recomputes. This prevents push
        cancellation when squeezed between multiple solids.

        Args:
            world: Current World (for collision filter checks).
            entity: The moving entity.
            transform: Entity's Transform.
            collider: Entity's Collider.
            solids: List of solid entities (with Transform + Collider).
            max_attempts: Max recovery iterations (Godot uses 4).
            margin: Minimum contact depth to maintain.
            recovery_factor: Fraction of penetration to resolve per iteration.

        Returns:
            True if any recovery was applied.
        """
        recovered = False

        for _attempt in range(max_attempts):
            e_left, e_top, e_right, e_bottom = collider.get_bounds(transform.x, transform.y)

            best_pen = 0.0
            best_axis = ""  # "left", "right", "top", "bottom"

            for other in solids:
                if int(other.id) == int(entity.id):
                    continue
                other_transform = other.get_component(Transform)
                other_collider = other.get_component(Collider)
                if other_transform is None or other_collider is None or not other_collider.enabled:
                    continue
                if other_collider.is_trigger:
                    continue
                # Respect collision filter
                if not self._can_collide(world, entity, other):
                    continue

                o_left, o_top, o_right, o_bottom = other_collider.get_bounds(
                    other_transform.x, other_transform.y
                )

                # Penetration depths (positive = overlapping)
                pen_left = o_right - e_left
                pen_right = e_right - o_left
                pen_top = o_bottom - e_top
                pen_bottom = e_bottom - o_top

                if pen_left <= 0.0 or pen_right <= 0.0 or pen_top <= 0.0 or pen_bottom <= 0.0:
                    continue

                # Skip one-way collisions in the wrong direction
                one_way = bool(getattr(other_collider, "one_way_collision", False))
                if one_way:
                    ow_dir_y = float(getattr(other_collider, "one_way_collision_direction_y", 1.0))
                    ow_margin = float(getattr(other_collider, "one_way_collision_margin", 1.0))
                    # Skip if penetration depth is within margin
                    if pen_bottom <= ow_margin and ow_dir_y < 0.0:
                        continue
                    if pen_top <= ow_margin and ow_dir_y > 0.0:
                        continue
                    # Direction-based skip
                    if ow_dir_y > 0.0 and pen_bottom < pen_top:
                        # One-way facing down, entity pushing from below → skip
                        continue
                    if ow_dir_y < 0.0 and pen_top < pen_bottom:
                        # One-way facing up, entity pushing from above → skip
                        continue

                # Find minimum-penetration axis (standard SAT MTV direction)
                pen_x = min(pen_left, pen_right)
                pen_y = min(pen_top, pen_bottom)

                if pen_x <= pen_y:
                    overlap_depth = pen_x
                    axis = "right" if pen_left <= pen_right else "left"
                else:
                    overlap_depth = pen_y
                    axis = "bottom" if pen_top <= pen_bottom else "top"

                # Pick the most deeply embedded solid (largest min penetration)
                if overlap_depth > best_pen:
                    best_pen = overlap_depth
                    best_axis = axis

            if best_pen <= margin:
                break

            depth = best_pen - margin
            push = depth * recovery_factor

            if best_axis == "left":
                transform.x -= push
            elif best_axis == "right":
                transform.x += push
            elif best_axis == "top":
                transform.y -= push
            elif best_axis == "bottom":
                transform.y += push

            recovered = True

        return recovered

    def move_and_slide(
        self,
        world: Any,
        entity: Any,
        velocity: tuple[float, float],
        delta_time: float,
        floor_max_angle: float = 0.785398,
        floor_snap_distance: float = 2.0,
        up_direction: tuple[float, float] = (0.0, -1.0),
        wall_min_slide_angle: float = 0.261799,
        floor_stop_on_slope: bool = False,
        max_slides: int = 4,
    ) -> MoveResult2D:
        """Movimiento de personaje con detección AABB y deslizamiento multi-iteración.

        Realiza barrido horizontal + vertical por eje en cada iteración,
        recalculando el remainder entre iteraciones hasta consumir todo el
        movimiento o alcanzar max_slides. Antes del barrido ejecuta una fase
        de unstuck/recovery para liberar el cuerpo si está penetrando sólidos.
        Incluye floor snap posterior
        y clasificación de colisiones (floor/wall/ceiling) via dot product
        contra up_direction.

        Args:
            world: World actual con las entidades y sólidos.
            entity: Entity con Transform + Collider.
            velocity: (vx, vy) en unidades/s. Ya incluye gravedad aplicada.
            delta_time: Delta time del frame en segundos.
            floor_max_angle: Ángulo máximo (rad) para considerar suelo.
            floor_snap_distance: Distancia de snap al suelo al perder contacto.
            up_direction: Vector up para clasificación de colisiones.
            wall_min_slide_angle: Ángulo mínimo para considerar pared.
            max_slides: Máximo de iteraciones de deslizamiento (default 4).

        Returns:
            MoveResult2D con posición final, velocidad ajustada, flags de estado
            y slide_count real.
        """
        transform = entity.get_component(Transform) if hasattr(entity, "get_component") else None
        collider: Collider | None = entity.get_component(Collider) if hasattr(entity, "get_component") else None
        if transform is None or collider is None:
            vx, vy = float(velocity[0]), float(velocity[1])
            return MoveResult2D(
                position_x=transform.x if transform else 0.0,
                position_y=transform.y if transform else 0.0,
                velocity_x=vx,
                velocity_y=vy,
                slide_count=0,
            )

        up_x, up_y = float(up_direction[0]), float(up_direction[1])
        vx, vy = float(velocity[0]), float(velocity[1])
        was_on_floor = getattr(entity, "_move_slide_was_on_floor", False)

        if world is None:
            transform.x += vx * delta_time
            transform.y += vy * delta_time
            return MoveResult2D(
                position_x=transform.x,
                position_y=transform.y,
                velocity_x=vx,
                velocity_y=vy,
                slide_count=0,
            )

        # --- Recovery (unstuck) ---
        solids: list[Any] = []
        for other in world.get_all_entities():
            if int(other.id) == int(entity.id):
                continue
            if not self._can_collide(world, entity, other):
                continue
            other_transform = other.get_component(Transform) if hasattr(other, "get_component") else None
            other_collider = other.get_component(Collider) if hasattr(other, "get_component") else None
            if other_transform is not None and other_collider is not None and other_collider.enabled and not other_collider.is_trigger:
                solids.append(other)

        self._recover_from_penetration(
            world=world,
            entity=entity,
            transform=transform,
            collider=collider,
            solids=solids,
        )

        motion_x = vx * delta_time
        motion_y = vy * delta_time

        on_floor = False
        on_wall = False
        on_ceiling = False
        collision_nx = 0.0
        collision_ny = 0.0
        contacts: list[PhysicsContact] = []
        slide_count = 0
        exclude_list: list[int] = []
        platform_eid: int = 0
        platform_vx: float = 0.0
        platform_vy: float = 0.0

        # --- Slide loop via body_test_motion ---
        for _iteration in range(max_slides):
            if abs(motion_x) < 1e-6 and abs(motion_y) < 1e-6:
                break

            result = self.body_test_motion(
                world=world,
                entity=entity,
                motion=(motion_x, motion_y),
                margin=0.08,
                recovery_as_collision=False,
                exclude_ids=exclude_list if exclude_list else None,
                collide_with_bodies=True,
                collide_with_areas=False,
            )

            if result.collision_safe_fraction >= 1.0:
                # No collision — apply full travel
                transform.x += result.travel_x
                transform.y += result.travel_y
                motion_x -= result.travel_x
                motion_y -= result.travel_y
                break

            # Collision detected — apply safe travel
            transform.x += result.travel_x
            transform.y += result.travel_y

            # Cache hit entity lookup
            hit_entity = None
            if result.collider_id > 0:
                hit_entity = self._find_entity(world, result.collider_id)

            nx = result.collision_normal_x
            ny = result.collision_normal_y

            # Skip t≈0 collisions where motion isn't pushing into the normal
            if result.collision_safe_fraction < 1e-6:
                motion_into = motion_x * nx + motion_y * ny
                if motion_into >= 0.0:
                    exclude_list.append(int(result.collider_id))
                    continue

            collision_type = self._classify_collision_static(
                nx, ny, up_x, up_y, floor_max_angle, wall_min_slide_angle,
            )

            # One-way collision check
            if hit_entity is not None and self._is_one_way_ignorable(
                motion_x, motion_y, nx, ny, hit_entity,
            ):
                exclude_list.append(int(result.collider_id))
                continue

            # Update state
            if collision_type == "floor":
                on_floor = True
                collision_ny = ny
                if hit_entity is not None:
                    platform_eid = int(hit_entity.id) if hasattr(hit_entity, "id") else 0
                    platform_vx, platform_vy = self._get_entity_velocity(hit_entity)
            elif collision_type == "wall":
                on_wall = True
                collision_nx = nx
            elif collision_type == "ceiling":
                on_ceiling = True
                collision_ny = ny

            slide_count += 1

            # Record contact
            if hit_entity is not None:
                self._add_contact(contacts, entity, hit_entity)

            # floor_stop_on_slope: stop immediately on floor contact
            if floor_stop_on_slope and collision_type == "floor":
                vx = 0.0
                vy = 0.0
                break

            # Compute new motion from remainder via slide along normal
            remainder_x = motion_x - result.travel_x
            remainder_y = motion_y - result.travel_y

            new_mx, new_my = self._slide_remainder(remainder_x, remainder_y, nx, ny)

            # Stop if sliding goes backwards relative to original velocity
            dot = new_mx * vx + new_my * vy
            if dot <= 0.0:
                vx = 0.0
                vy = 0.0
                break

            motion_x = new_mx
            motion_y = new_my

        # --- Velocity adjustment ---
        if on_wall:
            vx = 0.0
        if on_floor or on_ceiling:
            vy = 0.0

        # --- Floor snap ---
        if was_on_floor and not on_floor and floor_snap_distance > 0.0:
            # Use body_test_motion for snap
            snap_result = self.body_test_motion(
                world=world,
                entity=entity,
                motion=(-up_x * floor_snap_distance, -up_y * floor_snap_distance),
                margin=0.0,
                collide_with_bodies=True,
                collide_with_areas=False,
            )
            if snap_result.collision_safe_fraction < 1.0:
                transform.x += snap_result.travel_x
                transform.y += snap_result.travel_y
                collision_type = self._classify_collision_static(
                    snap_result.collision_normal_x, snap_result.collision_normal_y,
                    up_x, up_y, floor_max_angle, wall_min_slide_angle,
                )
                if collision_type == "floor":
                    on_floor = True

        # Persist floor state
        if hasattr(entity, "__dict__"):
            entity._move_slide_was_on_floor = on_floor  # type: ignore[attr-defined]

        return MoveResult2D(
            position_x=transform.x,
            position_y=transform.y,
            velocity_x=vx,
            velocity_y=vy,
            on_floor=on_floor,
            on_wall=on_wall,
            on_ceiling=on_ceiling,
            collision_normal_x=collision_nx,
            collision_normal_y=collision_ny,
            contacts=contacts,
            slide_count=slide_count,
            floor_angle=0.0,
            platform_entity_id=platform_eid,
            platform_velocity_x=platform_vx,
            platform_velocity_y=platform_vy,
        )

    def move_and_collide(
        self,
        world: Any,
        entity: Any,
        velocity: tuple[float, float],
        delta_time: float,
        max_collisions: int = 1,
    ) -> MoveResult2D:
        del max_collisions
        return self.move_and_slide(world, entity, velocity, delta_time, max_slides=1)

    def supports_kinematic_move(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Sweep helpers
    # ------------------------------------------------------------------

    def _sweep_axis(
        self,
        world: Any,
        entity: Any,
        transform: Transform,
        collider: Collider,
        solids: list[Any],
        delta: float,
        axis: str,
        contacts: list[PhysicsContact],
    ) -> float:
        if abs(delta) <= 1e-6:
            return 0.0
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        safe_delta = delta
        hit_entity: Any = None
        for other_solid in solids:
            if other_solid is entity:
                continue
            if not self._can_collide(world, entity, other_solid):
                continue
            other_transform = other_solid.get_component(Transform)
            other_collider = other_solid.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            if axis == "x" and other_collider.one_way_collision:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(
                other_transform.x, other_transform.y
            )
            if axis == "x":
                if not (top < o_bottom and bottom > o_top):
                    continue
            else:
                if not (left < o_right and right > o_left):
                    continue
                if other_collider.one_way_collision:
                    if delta < 0:
                        direction_check = other_collider.one_way_collision_direction_y
                        if direction_check < 0:
                            continue
            if delta > 0:
                gap = (o_left - right) if axis == "x" else (o_top - bottom)
                if 0.0 <= gap <= safe_delta:
                    # Narrow-phase: verificar intersección real en el punto de colisión
                    if collider.shape_type != "box" or other_collider.shape_type != "box":
                        new_x = transform.x + (gap if axis == "x" else 0.0)
                        new_y = transform.y + (gap if axis == "y" else 0.0)
                        self_shape = ShapeFactory.build(collider, new_x, new_y)
                        other_shape = ShapeFactory.build(other_collider, other_transform.x, other_transform.y)
                        if not self_shape.intersects_shape(other_shape):
                            continue
                    safe_delta = max(0.0, gap)
                    hit_entity = other_solid
            else:
                gap = (o_right - left) if axis == "x" else (o_bottom - top)
                if safe_delta <= gap <= 0.0:
                    if collider.shape_type != "box" or other_collider.shape_type != "box":
                        new_x = transform.x + (gap if axis == "x" else 0.0)
                        new_y = transform.y + (gap if axis == "y" else 0.0)
                        self_shape = ShapeFactory.build(collider, new_x, new_y)
                        other_shape = ShapeFactory.build(other_collider, other_transform.x, other_transform.y)
                        if not self_shape.intersects_shape(other_shape):
                            continue
                    safe_delta = min(0.0, gap)
                    hit_entity = other_solid
        if hit_entity is not None:
            self._add_contact(contacts, entity, hit_entity)
        return safe_delta

    def _floor_snap(
        self,
        world: Any,
        entity: Any,
        transform: Transform,
        collider: Collider,
        solids: list[Any],
        snap_distance: float,
        contacts: list[PhysicsContact],
    ) -> float | None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        snap_limit = max(0.0, snap_distance)
        best_snap: float | None = None
        best_other: Any = None
        for other_solid in solids:
            if other_solid is entity:
                continue
            if not self._can_collide(world, entity, other_solid):
                continue
            other_transform = other_solid.get_component(Transform)
            other_collider = other_solid.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(
                other_transform.x, other_transform.y
            )
            if not (left < o_right and right > o_left):
                continue
            gap = o_top - bottom
            if 0.0 <= gap <= snap_limit and (best_snap is None or gap < best_snap):
                best_snap = gap
                best_other = other_solid
        if best_other is not None:
            self._add_contact(contacts, entity, best_other)
        return best_snap

    def _can_collide(self, world: Any, entity: Any, other_entity: Any) -> bool:
        cc_filter = entity.get_component(CollisionFilter2D) if hasattr(entity, "get_component") else None
        other_filter = other_entity.get_component(CollisionFilter2D) if hasattr(other_entity, "get_component") else None
        if cc_filter is not None or other_filter is not None:
            if not CollisionFilter2D.should_collide(cc_filter, other_filter):
                return False
        matrix = getattr(world, "feature_metadata", {}).get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        entity_layer = getattr(entity, "layer", "Default")
        other_layer = getattr(other_entity, "layer", "Default")
        return bool(matrix.get(f"{entity_layer}|{other_layer}", True))

    @staticmethod
    def _classify_collision_static(
        nx: float, ny: float, up_x: float, up_y: float,
        floor_max_angle: float, wall_min_slide_angle: float,
    ) -> str:
        dot = nx * up_x + ny * up_y
        angle = math.acos(max(-1.0, min(1.0, abs(dot))))
        if angle <= floor_max_angle:
            return "floor" if dot >= 0 else "ceiling"
        elif angle >= (math.pi / 2 - wall_min_slide_angle):
            return "wall"
        else:
            return "ceiling" if dot > 0 else "wall"

    def _add_contact(
        self, contacts: list[PhysicsContact], entity: Any, other: Any,
    ) -> None:
        entity_id = int(getattr(entity, "id", 0))
        other_id = int(getattr(other, "id", 0))
        for c in contacts:
            if {c.entity_a_id, c.entity_b_id} == {entity_id, other_id}:
                return
        contacts.append(
            PhysicsContact(
                entity_a=getattr(entity, "name", str(entity_id)),
                entity_b=getattr(other, "name", str(other_id)),
                entity_a_id=entity_id,
                entity_b_id=other_id,
                is_trigger=False,
            )
        )

    def _get_structure_version(self, world: Any) -> int | None:
        try:
            return int(world.structure_version)
        except (AttributeError, TypeError, ValueError):
            return None

    def _invalidate_sync_cache(self) -> None:
        self._synced_world_id = None
        self._synced_structure_version = None

    def _build_overlap_contacts(self) -> list[PhysicsContact]:
        if self._collision_system is None:
            return []
        contacts: list[PhysicsContact] = []
        for collision in self._collision_system.get_collisions():
            contacts.append(
                PhysicsContact(
                    entity_a=collision.entity_a.name,
                    entity_b=collision.entity_b.name,
                    entity_a_id=collision.entity_a.id,
                    entity_b_id=collision.entity_b.id,
                    is_trigger=bool(collision.is_trigger),
                )
            )
        return contacts

    def _append_swept_contacts(self, world: Any) -> None:
        if self._physics_system is None or not hasattr(self._physics_system, "consume_swept_contacts"):
            return
        existing_pairs = {
            tuple(sorted((contact.entity_a_id, contact.entity_b_id)))
            for contact in self._latest_contacts
        }
        for entity_a_id, entity_b_id in self._physics_system.consume_swept_contacts():
            pair = tuple(sorted((int(entity_a_id), int(entity_b_id))))
            if pair in existing_pairs:
                continue
            entity_a = self._find_entity(world, entity_a_id)
            entity_b = self._find_entity(world, entity_b_id)
            if entity_a is None or entity_b is None:
                continue
            contact = PhysicsContact(
                entity_a=entity_a.name,
                entity_b=entity_b.name,
                entity_a_id=int(entity_a.id),
                entity_b_id=int(entity_b.id),
                is_trigger=False,
            )
            self._latest_contacts.append(contact)
            existing_pairs.add(pair)
            if self._event_bus is not None:
                self._event_bus.emit(
                    "on_collision",
                    {
                        "entity_a": contact.entity_a,
                        "entity_b": contact.entity_b,
                        "entity_a_id": contact.entity_a_id,
                        "entity_b_id": contact.entity_b_id,
                        "is_trigger": False,
                    },
                )

    def _find_entity(self, world: Any, entity_id: int) -> Any:
        normalized_id = int(entity_id)
        get_entity = getattr(world, "get_entity", None)
        if get_entity is not None:
            entity = get_entity(normalized_id)
            if entity is not None:
                return entity
        for entity in world.get_all_entities():
            if int(entity.id) == normalized_id:
                return entity
        return None

    def _ray_capsule_distance(
        self,
        ox: float,
        oy: float,
        dx: float,
        dy: float,
        collider: Collider,
        pos_x: float,
        pos_y: float,
        max_distance: float,
    ) -> tuple[float, tuple[float, float]] | None:
        """Ray-capsule intersection: ray vs vertical segment + radius. Returns (distance, normal)."""
        cx = pos_x + collider.offset_x
        cy = pos_y + collider.offset_y
        r = collider.radius
        half_h = collider.capsule_height / 2
        y_top = cy - half_h
        y_bot = cy + half_h

        def _ray_circle(ccx: float, ccy: float, cr: float) -> float | None:
            """Ray vs circle: solve |O + t*D - C|^2 = r^2."""
            ocx = ox - ccx
            ocy = oy - ccy
            a = dx * dx + dy * dy
            b = 2.0 * (ocx * dx + ocy * dy)
            c_val = ocx * ocx + ocy * ocy - cr * cr
            disc = b * b - 4.0 * a * c_val
            if disc < 0.0:
                return None
            sqrt_disc = math.sqrt(disc)
            t1 = (-b - sqrt_disc) / (2.0 * a)
            t2 = (-b + sqrt_disc) / (2.0 * a)
            if t1 > t2:
                t1, t2 = t2, t1
            if 0.0 <= t1 <= max_distance:
                return t1
            if 0.0 <= t2 <= max_distance:
                return t2
            return None

        def _ray_slab(t_min: float, t_max: float, origin: float, direction: float, low: float, high: float) -> tuple[float, float] | None:
            """Slab intersection for one axis."""
            if abs(direction) <= 1e-8:
                if origin < low or origin > high:
                    return None
                return (t_min, t_max)
            inv = 1.0 / direction
            t1 = (low - origin) * inv
            t2 = (high - origin) * inv
            near = min(t1, t2)
            far = max(t1, t2)
            return (max(t_min, near), min(t_max, far))

        best_t = float("inf")
        best_normal: tuple[float, float] = (0.0, 0.0)

        # Top cap: circle at (cx, y_top)
        t_top = _ray_circle(cx, y_top, r)
        if t_top is not None and t_top < best_t:
            hx = ox + dx * t_top
            hy = oy + dy * t_top
            n_len = math.hypot(hx - cx, hy - y_top)
            if n_len > 1e-8:
                best_normal = ((hx - cx) / n_len, (hy - y_top) / n_len)
            else:
                best_normal = (-dx, -dy)
            best_t = t_top

        # Bottom cap: circle at (cx, y_bot)
        t_bot = _ray_circle(cx, y_bot, r)
        if t_bot is not None and t_bot < best_t:
            hx = ox + dx * t_bot
            hy = oy + dy * t_bot
            n_len = math.hypot(hx - cx, hy - y_bot)
            if n_len > 1e-8:
                best_normal = ((hx - cx) / n_len, (hy - y_bot) / n_len)
            else:
                best_normal = (-dx, -dy)
            best_t = t_bot

        # Rectangular body: [cx - r, cx + r] x [y_top, y_bot]
        body_left = cx - r
        body_right = cx + r
        body_top = y_top
        body_bottom = y_bot
        result = _ray_slab(0.0, max_distance, ox, dx, body_left, body_right)
        if result is not None:
            t_min_x, t_max_x = result
            if t_min_x <= t_max_x:
                result_y = _ray_slab(t_min_x, t_max_x, oy, dy, body_top, body_bottom)
                if result_y is not None:
                    ty_min, ty_max = result_y
                    if ty_min <= ty_max and ty_min >= 0.0 and ty_min < best_t:
                        hx = ox + dx * ty_min
                        hy = oy + dy * ty_min
                        eps = 1e-4
                        if abs(hx - body_left) < eps:
                            best_normal = (-1.0, 0.0)
                        elif abs(hx - body_right) < eps:
                            best_normal = (1.0, 0.0)
                        elif abs(hy - body_top) < eps:
                            best_normal = (0.0, -1.0)
                        elif abs(hy - body_bottom) < eps:
                            best_normal = (0.0, 1.0)
                        else:
                            best_normal = (-dx, -dy)
                        best_t = ty_min

        if math.isfinite(best_t):
            return (best_t, best_normal)
        return None

    def _ray_aabb_distance(
        self,
        ox: float,
        oy: float,
        dx: float,
        dy: float,
        left: float,
        top: float,
        right: float,
        bottom: float,
        max_distance: float,
    ) -> tuple[float, tuple[float, float]] | None:
        t_min = 0.0
        t_max = float(max_distance)
        for origin, direction, minimum, maximum in (
            (ox, dx, left, right),
            (oy, dy, top, bottom),
        ):
            if abs(direction) <= 1e-8:
                if origin < minimum or origin > maximum:
                    return None
                continue
            inv = 1.0 / direction
            t1 = (minimum - origin) * inv
            t2 = (maximum - origin) * inv
            near = min(t1, t2)
            far = max(t1, t2)
            t_min = max(t_min, near)
            t_max = min(t_max, far)
            if t_min > t_max:
                return None
        if 0.0 <= t_min <= max_distance:
            hx = ox + dx * t_min
            hy = oy + dy * t_min
            eps = 1e-4
            if abs(hx - left) < eps:
                nx, ny = -1.0, 0.0
            elif abs(hx - right) < eps:
                nx, ny = 1.0, 0.0
            elif abs(hy - top) < eps:
                nx, ny = 0.0, -1.0
            elif abs(hy - bottom) < eps:
                nx, ny = 0.0, 1.0
            else:
                # Ray starts inside AABB; direction-based fallback
                nx, ny = -dx, -dy
            return (t_min, (nx, ny))
        return None
