"""
engine/systems/collision_system.py - Sistema de deteccion de colisiones
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from engine.components.collider import Collider
from engine.components.collision_filter_2d import CollisionFilter2D
from engine.components.collision_polygon_2d import CollisionPolygon2D
from engine.components.collision_shape_2d import CollisionShape2D
from engine.components.collision_shape_set_2d import CollisionShape2DDef, CollisionShapeSet2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.contact_data import ContactManifold2D, ContactPoint2D
from engine.physics.shapes import AABBShape, CapsuleShape, CircleShape, PolygonShape, ShapeFactory
from engine.physics.spatial_hash import SpatialHash2D

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus

AABB = tuple[float, float, float, float]


@dataclass
class CollisionInfo:
    entity_a: Entity
    entity_b: Entity
    is_trigger: bool


@dataclass(frozen=True)
class _CollisionEntry:
    entity: Entity
    collider: Optional[Collider]
    rigidbody: Optional[RigidBody]
    aabb: AABB
    shape_defs: tuple = ()
    use_shape_set: bool = False


class CollisionSystem:
    """Sistema de deteccion de colisiones AABB."""

    def __init__(self, event_bus: Optional["EventBus"] = None, *, deterministic_debug: bool = False) -> None:
        self._collisions: list[CollisionInfo] = []
        self._event_bus: Optional["EventBus"] = event_bus
        self._step_metrics: dict[str, int] = {
            "candidate_pairs": 0,
            "narrow_phase_pairs": 0,
            "actual_collisions": 0,
        }
        self._query_buffer: set[int] = set()
        self._spatial_hash_cell_size: float = 128.0
        self.deterministic_debug: bool = bool(deterministic_debug)
        self._grid: SpatialHash2D = SpatialHash2D(cell_size=self._spatial_hash_cell_size)
        self._entries_by_id: dict[int, _CollisionEntry] = {}
        self._checked_pairs: set[int] = set()

    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus

    def update(self, world: World) -> None:
        self._collisions.clear()
        self._reset_step_metrics()
        self._query_buffer.clear()

        # Limpiar contactos runtime para RigidBodies con contact_monitor activo
        self._clear_contact_tracking(world)

        grid = self._prepare_grid()
        entries_by_id = self._entries_by_id
        entries_by_id.clear()

        for entity in world.get_entities_with(Transform, Collider):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            if transform is None or collider is None or not collider.enabled:
                continue
            shape_set = entity.get_component(CollisionShapeSet2D)
            if shape_set is not None:
                # Use composite bounds from shape set, flat shape defs
                bounds = shape_set.get_composite_bounds(transform.x, transform.y)
                shape_defs = tuple(shape_set.shapes)
            else:
                bounds = self._compute_shape_bounds(entity, transform)
                if bounds is None:
                    bounds = collider.get_bounds(transform.x, transform.y)
                shape_defs = (self._collider_to_shape_def(collider),)
            entry = _CollisionEntry(
                entity=entity,
                collider=collider,
                rigidbody=entity.get_component(RigidBody),
                aabb=bounds,
                shape_defs=shape_defs,
                use_shape_set=(shape_set is not None),
            )
            entries_by_id[int(entity.id)] = entry
            grid.insert(entity.id, entry.aabb)

        # Also gather entities with dedicated shape components but no Collider
        for entity in world.get_entities_with(Transform):
            entity_id = int(entity.id)
            if entity_id in entries_by_id:
                continue
            transform = entity.get_component(Transform)
            if transform is None:
                continue
            shape_set = entity.get_component(CollisionShapeSet2D)
            if shape_set is not None:
                bounds = shape_set.get_composite_bounds(transform.x, transform.y)
                shape_defs = tuple(shape_set.shapes)
                entry = _CollisionEntry(
                    entity=entity,
                    collider=None,
                    rigidbody=entity.get_component(RigidBody),
                    aabb=bounds,
                    shape_defs=shape_defs,
                    use_shape_set=True,
                )
                entries_by_id[entity_id] = entry
                grid.insert(entity.id, entry.aabb)
                continue
            if not self._entity_has_collision_shape(entity):
                continue
            bounds = self._compute_shape_bounds(entity, transform)
            if bounds is None:
                continue
            entry = _CollisionEntry(
                entity=entity,
                collider=None,
                rigidbody=entity.get_component(RigidBody),
                aabb=bounds,
            )
            entries_by_id[entity_id] = entry
            grid.insert(entity.id, entry.aabb)

        checked_pairs = self._checked_pairs
        checked_pairs.clear()
        pair_shift = self._pair_shift(entries_by_id)
        entry_items = (
            ((entity_id, entries_by_id[entity_id]) for entity_id in sorted(entries_by_id))
            if self.deterministic_debug
            else entries_by_id.items()
        )
        for entity_id, entry_a in entry_items:
            query_result = grid.query_into(entry_a.aabb, self._query_buffer)
            candidate_ids = sorted(query_result) if self.deterministic_debug else query_result
            for entity_b_id in candidate_ids:
                if entity_b_id <= entity_id:
                    continue
                pair_key = self._pair_key(entity_id, entity_b_id, pair_shift)
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                self._step_metrics["candidate_pairs"] += 1

                entry_b = entries_by_id.get(entity_b_id)
                if entry_b is None or not self._can_check_pair(world, entry_a, entry_b):
                    continue

                self._step_metrics["narrow_phase_pairs"] += 1
                if not self._aabbs_overlap(entry_a.aabb, entry_b.aabb):
                    continue

                # Narrow-phase: check shape pairs
                if not self._narrow_phase_check(entry_a, entry_b):
                    continue

                # is_trigger: True if any shape in the pair is trigger
                is_trigger = self._any_shape_is_trigger(entry_a, entry_b)
                collision = CollisionInfo(
                    entity_a=entry_a.entity,
                    entity_b=entry_b.entity,
                    is_trigger=is_trigger,
                )
                self._collisions.append(collision)
                self._step_metrics["actual_collisions"] += 1
                self._emit_collision_event(collision)

                # Registrar contactos en RigidBodies con contact_monitor activo
                if not collision.is_trigger:
                    a_id = int(collision.entity_a.id)
                    b_id = int(collision.entity_b.id)
                    if entry_a.rigidbody is not None:
                        entry_a.rigidbody._register_contact(b_id)
                    if entry_b.rigidbody is not None:
                        entry_b.rigidbody._register_contact(a_id)

    def _reset_step_metrics(self) -> None:
        self._step_metrics["candidate_pairs"] = 0
        self._step_metrics["narrow_phase_pairs"] = 0
        self._step_metrics["actual_collisions"] = 0

    def _clear_contact_tracking(self, world: World) -> None:
        """Limpia el tracking de contactos para RigidBodies con contact_monitor activo."""
        for entity in world.get_entities_with(Transform):
            rb = entity.get_component(RigidBody)
            if rb is not None and rb.contact_monitor:
                rb._clear_contacts()

    def _prepare_grid(self) -> SpatialHash2D:
        if self._grid.cell_size != max(float(self._spatial_hash_cell_size), 1.0):
            self._grid = SpatialHash2D(cell_size=self._spatial_hash_cell_size)
        else:
            self._grid.clear()
        return self._grid

    def _pair_shift(self, entries_by_id: dict[int, _CollisionEntry]) -> int:
        if not entries_by_id:
            return 1
        return max(1, max(entries_by_id).bit_length())

    def _pair_key(self, entity_a_id: int, entity_b_id: int, pair_shift: int) -> int:
        if entity_a_id > entity_b_id:
            entity_a_id, entity_b_id = entity_b_id, entity_a_id
        return (entity_a_id << pair_shift) | entity_b_id

    def _emit_collision_event(self, collision: CollisionInfo) -> None:
        if self._event_bus is None:
            return
        event_name = "on_trigger_enter" if collision.is_trigger else "on_collision"
        event_data = {
            "entity_a": collision.entity_a.name,
            "entity_b": collision.entity_b.name,
            "entity_a_id": collision.entity_a.id,
            "entity_b_id": collision.entity_b.id,
            "is_trigger": collision.is_trigger,
        }
        self._event_bus.emit(event_name, event_data)

        manifold = self._build_contact_manifold(collision)
        if manifold is not None:
            self._event_bus.emit("collision_contact", manifold.to_dict())

    def _build_contact_manifold(self, collision: CollisionInfo) -> ContactManifold2D | None:
        entry_a = self._entries_by_id.get(int(collision.entity_a.id))
        entry_b = self._entries_by_id.get(int(collision.entity_b.id))
        if entry_a is None or entry_b is None:
            return None

        transform_a = entry_a.entity.get_component(Transform)
        transform_b = entry_b.entity.get_component(Transform)
        if transform_a is None or transform_b is None:
            return None

        defs_a = entry_a.shape_defs if entry_a.shape_defs else (None,)
        defs_b = entry_b.shape_defs if entry_b.shape_defs else (None,)

        best_manifold: ContactManifold2D | None = None
        for def_a in defs_a:
            shape_a = self._build_shape_from_def_or_entry(def_a, entry_a, transform_a)
            if shape_a is None:
                continue
            for def_b in defs_b:
                shape_b = self._build_shape_from_def_or_entry(def_b, entry_b, transform_b)
                if shape_b is None:
                    continue
                manifold = shape_a.collide_shape(shape_b)
                if manifold is not None:
                    if best_manifold is None or manifold.depth > best_manifold.depth:
                        best_manifold = manifold

        if best_manifold is not None:
            best_manifold.entity_a_id = int(collision.entity_a.id)
            best_manifold.entity_b_id = int(collision.entity_b.id)
            best_manifold.entity_a_name = collision.entity_a.name
            best_manifold.entity_b_name = collision.entity_b.name
            best_manifold.is_trigger = collision.is_trigger
            if entry_a.rigidbody is not None and entry_b.rigidbody is not None:
                best_manifold.relative_velocity_x = entry_a.rigidbody.velocity_x - entry_b.rigidbody.velocity_x
                best_manifold.relative_velocity_y = entry_a.rigidbody.velocity_y - entry_b.rigidbody.velocity_y
            return best_manifold

        # Fallback AABB
        aabb_a = entry_a.aabb
        aabb_b = entry_b.aabb

        left_a, top_a, right_a, bottom_a = aabb_a
        left_b, top_b, right_b, bottom_b = aabb_b

        center_x_a = (left_a + right_a) / 2.0
        center_y_a = (top_a + bottom_a) / 2.0
        center_x_b = (left_b + right_b) / 2.0
        center_y_b = (top_b + bottom_b) / 2.0

        overlap_left = right_a - left_b
        overlap_right = right_b - left_a
        overlap_top = bottom_a - top_b
        overlap_bottom = bottom_b - top_a

        overlap_x = min(overlap_left, overlap_right)
        overlap_y = min(overlap_top, overlap_bottom)

        normal_x: float = 0.0
        normal_y: float = 0.0

        if overlap_x < overlap_y:
            if center_x_a < center_x_b:
                normal_x = 1.0
            else:
                normal_x = -1.0
        else:
            if center_y_a < center_y_b:
                normal_y = 1.0
            else:
                normal_y = -1.0

        depth = min(overlap_x, overlap_y)

        contact_point_x = (max(left_a, left_b) + min(right_a, right_b)) / 2.0
        contact_point_y = (max(top_a, top_b) + min(bottom_a, bottom_b)) / 2.0

        rel_vel_x: float = 0.0
        rel_vel_y: float = 0.0
        if entry_a.rigidbody is not None and entry_b.rigidbody is not None:
            rel_vel_x = entry_a.rigidbody.velocity_x - entry_b.rigidbody.velocity_x
            rel_vel_y = entry_a.rigidbody.velocity_y - entry_b.rigidbody.velocity_y

        contact_point = ContactPoint2D(
            point_x=contact_point_x,
            point_y=contact_point_y,
            normal_x=normal_x,
            normal_y=normal_y,
            depth=depth,
        )

        return ContactManifold2D(
            entity_a_id=int(collision.entity_a.id),
            entity_b_id=int(collision.entity_b.id),
            entity_a_name=collision.entity_a.name,
            entity_b_name=collision.entity_b.name,
            normal_x=normal_x,
            normal_y=normal_y,
            depth=depth,
            relative_velocity_x=rel_vel_x,
            relative_velocity_y=rel_vel_y,
            contact_count=1,
            contacts=[contact_point],
            is_trigger=collision.is_trigger,
        )

    def _can_check_pair(self, world: World, entry_a: _CollisionEntry, entry_b: _CollisionEntry) -> bool:
        if not self._layers_can_collide(world, entry_a.entity.layer, entry_b.entity.layer):
            return False
        if not self._filter_allows_collision(entry_a.entity, entry_b.entity):
            return False
        if not self._is_simulated(entry_a.rigidbody) and not self._is_simulated(entry_b.rigidbody):
            return False
        return self._allows_contact(entry_a.rigidbody, entry_b.rigidbody)

    @staticmethod
    def _compute_shape_bounds(entity: Entity, transform: Transform) -> AABB | None:
        """Compute AABB bounds from CollisionShape2D, CollisionPolygon2D, or Collider.

        Precedence: CollisionShape2D > CollisionPolygon2D > Collider.
        Returns None if no valid shape component exists.
        """
        shape = entity.get_component(CollisionShape2D)
        if shape is not None and not shape.disabled:
            return shape.get_bounds(transform.x, transform.y)
        poly = entity.get_component(CollisionPolygon2D)
        if poly is not None and not poly.disabled:
            return poly.get_bounds(transform.x, transform.y)
        collider = entity.get_component(Collider)
        if collider is not None and collider.enabled:
            return collider.get_bounds(transform.x, transform.y)
        return None

    @staticmethod
    def _entity_has_collision_shape(entity: Entity) -> bool:
        """Check if entity has any collision shape component."""
        shape = entity.get_component(CollisionShape2D)
        if shape is not None and not shape.disabled:
            return True
        poly = entity.get_component(CollisionPolygon2D)
        if poly is not None and not poly.disabled:
            return True
        return False

    def _aabbs_overlap(self, aabb_a: AABB, aabb_b: AABB) -> bool:
        left_a, top_a, right_a, bottom_a = aabb_a
        left_b, top_b, right_b, bottom_b = aabb_b
        return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b

    @staticmethod
    def _collider_to_shape_def(collider: Collider) -> CollisionShape2DDef:
        """Convert a legacy Collider into a synthetic CollisionShape2DDef."""
        return CollisionShape2DDef(
            shape_type=collider.shape_type,
            offset_x=collider.offset_x,
            offset_y=collider.offset_y,
            disabled=not collider.enabled,
            is_trigger=collider.is_trigger,
            one_way_collision=collider.one_way_collision,
            one_way_collision_direction_y=collider.one_way_collision_direction_y,
            friction=collider.friction,
            restitution=collider.restitution,
            width=collider.width,
            height=collider.height,
            radius=collider.radius,
            points=collider.points,
            capsule_height=collider.capsule_height,
        )

    @staticmethod
    def _any_shape_is_trigger(entry_a: _CollisionEntry, entry_b: _CollisionEntry) -> bool:
        """True if any shape in either entry is a trigger."""
        for shape in entry_a.shape_defs:
            if shape.is_trigger:
                return True
        for shape in entry_b.shape_defs:
            if shape.is_trigger:
                return True
        if entry_a.collider is not None and entry_a.collider.is_trigger:
            return True
        if entry_b.collider is not None and entry_b.collider.is_trigger:
            return True
        return False

    def _narrow_phase_check(self, entry_a: _CollisionEntry, entry_b: _CollisionEntry) -> bool:
        """Narrow-phase: iterate shape pairs. Early exit on first hit."""
        defs_a = entry_a.shape_defs if entry_a.shape_defs else (None,)
        defs_b = entry_b.shape_defs if entry_b.shape_defs else (None,)
        transform_a = entry_a.entity.get_component(Transform)
        transform_b = entry_b.entity.get_component(Transform)
        if transform_a is None or transform_b is None:
            return True

        for def_a in defs_a:
            shape_a = self._build_shape_from_def_or_entry(def_a, entry_a, transform_a)
            if shape_a is None:
                continue
            for def_b in defs_b:
                shape_b = self._build_shape_from_def_or_entry(def_b, entry_b, transform_b)
                if shape_b is None:
                    continue
                if isinstance(shape_a, AABBShape) and isinstance(shape_b, AABBShape):
                    return True
                if shape_a.intersects_shape(shape_b):
                    return True
        return False

    def _build_shape_from_def_or_entry(self, def_: CollisionShape2DDef | None, entry: _CollisionEntry, transform: Transform):
        """Build ShapeInstance from a CollisionShape2DDef, or fallback to entry."""
        if def_ is not None:
            return ShapeFactory.build_from_def(def_, transform.x, transform.y)
        return self._build_shape_from_entry(entry)

    def _build_shape_from_entry(self, entry: _CollisionEntry):
        """Construye ShapeInstance desde Collider, CollisionShape2D, CollisionPolygon2D o bounds."""
        entity = entry.entity
        transform = entity.get_component(Transform)
        if transform is None:
            return None

        # 1. Collider
        collider = entry.collider
        if collider is not None and collider.enabled:
            return ShapeFactory.build(collider, transform.x, transform.y)

        # 2. CollisionShape2D
        shape2d = entity.get_component(CollisionShape2D)
        if shape2d is not None and not shape2d.disabled:
            cx = transform.x
            cy = transform.y
            st = shape2d.shape_type
            if st == "circle":
                return CircleShape(cx, cy, shape2d.radius)
            if st == "capsule":
                return CapsuleShape(cx, cy, shape2d.radius, shape2d.height)
            if st == "polygon" and shape2d.points:
                world_verts = [(cx + p[0], cy + p[1]) for p in shape2d.points]
                return PolygonShape(world_verts)
            hw = shape2d.width / 2
            hh = shape2d.height / 2
            return AABBShape(cx, cy, hw, hh)

        # 3. CollisionPolygon2D
        poly = entity.get_component(CollisionPolygon2D)
        if poly is not None and not poly.disabled and poly.polygon:
            world_verts = [(transform.x + v[0], transform.y + v[1]) for v in poly.polygon]
            return PolygonShape(world_verts)

        # 4. Fallback: AABB desde bounds calculados
        aabb = entry.aabb
        return AABBShape(
            (aabb[0] + aabb[2]) / 2,
            (aabb[1] + aabb[3]) / 2,
            (aabb[2] - aabb[0]) / 2,
            (aabb[3] - aabb[1]) / 2,
        )

    def _layers_can_collide(self, world: World, layer_a: str, layer_b: str) -> bool:
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{layer_a}|{layer_b}", True))

    def _filter_allows_collision(self, entity_a: Entity, entity_b: Entity) -> bool:
        return CollisionFilter2D.should_collide(
            entity_a.get_component(CollisionFilter2D),
            entity_b.get_component(CollisionFilter2D),
        )

    def _is_simulated(self, rigidbody: Optional[RigidBody]) -> bool:
        if rigidbody is None:
            return True
        return rigidbody.enabled and rigidbody.simulated

    def _allows_contact(self, rigidbody_a: Optional[RigidBody], rigidbody_b: Optional[RigidBody]) -> bool:
        if rigidbody_a is None and rigidbody_b is None:
            return True
        if rigidbody_a is not None and rigidbody_b is None:
            return rigidbody_a.body_type != "kinematic" or rigidbody_a.use_full_kinematic_contacts
        if rigidbody_b is not None and rigidbody_a is None:
            return rigidbody_b.body_type != "kinematic" or rigidbody_b.use_full_kinematic_contacts
        if rigidbody_a is None or rigidbody_b is None:
            return True
        if rigidbody_a.body_type == "kinematic" and rigidbody_b.body_type == "kinematic":
            return rigidbody_a.use_full_kinematic_contacts or rigidbody_b.use_full_kinematic_contacts
        if rigidbody_a.body_type == "kinematic" and rigidbody_b.body_type == "static":
            return rigidbody_a.use_full_kinematic_contacts
        if rigidbody_b.body_type == "kinematic" and rigidbody_a.body_type == "static":
            return rigidbody_b.use_full_kinematic_contacts
        return True

    # --- Legacy capsule narrow-phase methods (fallback, kept commented) ---
    # def _narrow_phase_capsule(self, entry_a: _CollisionEntry, entry_b: _CollisionEntry) -> bool:
    #     """Narrow-phase check when at least one collider is a capsule."""
    #     shape_a = entry_a.collider.shape_type if entry_a.collider is not None else ""
    #     shape_b = entry_b.collider.shape_type if entry_b.collider is not None else ""
    #
    #     if shape_a == "capsule" and shape_b == "capsule":
    #         return self._capsule_vs_capsule(entry_a, entry_b)
    #     if shape_a == "capsule":
    #         return self._capsule_vs_aabb(entry_a, entry_b)
    #     if shape_b == "capsule":
    #         return self._capsule_vs_aabb(entry_b, entry_a)
    #     return True
    #
    # def _capsule_vs_aabb(self, capsule_entry: _CollisionEntry, aabb_entry: _CollisionEntry) -> bool:
    #     """Capsule vs AABB collision. Capsule = vertical segment + radius."""
    #     c = capsule_entry.collider
    #     if c is None:
    #         return True
    #     # Capsule world position
    #     cx = capsule_entry.aabb[0] + c.radius  # left + radius = center x
    #     cy = (capsule_entry.aabb[1] + capsule_entry.aabb[3]) / 2  # center y
    #     cap_half = c.capsule_height / 2
    #     seg_top = cy - cap_half
    #     seg_bot = cy + cap_half
    #
    #     # AABB world bounds
    #     aabb_left = aabb_entry.aabb[0]
    #     aabb_top = aabb_entry.aabb[1]
    #     aabb_right = aabb_entry.aabb[2]
    #     aabb_bottom = aabb_entry.aabb[3]
    #
    #     # Distance from segment to AABB
    #     dx = max(aabb_left - cx, cx - aabb_right, 0.0)
    #     dy = max(aabb_top - seg_bot, seg_top - aabb_bottom, 0.0)
    #
    #     return (dx * dx + dy * dy) < (c.radius * c.radius)
    #
    # def _capsule_vs_capsule(self, entry_a: _CollisionEntry, entry_b: _CollisionEntry) -> bool:
    #     """Capsule vs capsule collision. Checks minimum distance between segments."""
    #     ca = entry_a.collider
    #     cb = entry_b.collider
    #     if ca is None or cb is None:
    #         return True
    #
    #     ax = entry_a.aabb[0] + ca.radius
    #     ay = (entry_a.aabb[1] + entry_a.aabb[3]) / 2
    #     ah = ca.capsule_height / 2
    #
    #     bx = entry_b.aabb[0] + cb.radius
    #     by = (entry_b.aabb[1] + entry_b.aabb[3]) / 2
    #     bh = cb.capsule_height / 2
    #
    #     # Vertical segments: (ax, ay-ah)->(ax, ay+ah) and (bx, by-bh)->(bx, by+bh)
    #     seg_a_top = ay - ah
    #     seg_a_bot = ay + ah
    #     seg_b_top = by - bh
    #     seg_b_bot = by + bh
    #
    #     dx = abs(ax - bx)
    #     dy = max(seg_a_top - seg_b_bot, seg_b_top - seg_a_bot, 0.0)
    #     distance = math.hypot(dx, dy)
    #
    #     return distance < (ca.radius + cb.radius)
    #
    @staticmethod
    def _closest_point_on_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
        """Closest point on segment AB to point P."""
        abx = bx - ax
        aby = by - ay
        if abx == 0.0 and aby == 0.0:
            return (ax, ay)
        t = ((px - ax) * abx + (py - ay) * aby) / (abx * abx + aby * aby)
        t = max(0.0, min(1.0, t))
        return (ax + t * abx, ay + t * aby)

    def get_collisions(self) -> list[CollisionInfo]:
        return self._collisions.copy()

    def get_step_metrics(self) -> dict[str, int]:
        return dict(self._step_metrics)

    def get_collisions_for(self, entity: Entity) -> list[CollisionInfo]:
        return [col for col in self._collisions if col.entity_a.id == entity.id or col.entity_b.id == entity.id]

    def has_collision(self, entity: Entity) -> bool:
        return len(self.get_collisions_for(entity)) > 0
