from __future__ import annotations

import math
from typing import Any, Optional

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.physics.backend import PhysicsAABBHit, PhysicsBackend, PhysicsContact, PhysicsRayHit, PhysicsShapeCastHit


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
        for entity in world.get_entities_with(Transform, Collider):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            if transform is None or collider is None or not collider.enabled:
                continue
            if collider.shape_type == "capsule":
                distance = self._ray_capsule_distance(ox, oy, dx, dy, collider, transform.x, transform.y, max_distance)
            else:
                left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
                distance = self._ray_aabb_distance(ox, oy, dx, dy, left, top, right, bottom, max_distance)
            if distance is None:
                continue
            hits.append(
                {
                    "entity": entity.name,
                    "entity_id": entity.id,
                    "distance": distance,
                    "point": {"x": ox + dx * distance, "y": oy + dy * distance},
                    "is_trigger": bool(collider.is_trigger),
                }
            )
        return sorted(hits, key=lambda item: (float(item["distance"]), int(item["entity_id"])))

    def query_aabb(self, world: Any, bounds: tuple[float, float, float, float]) -> list[PhysicsAABBHit]:
        left, top, right, bottom = [float(value) for value in bounds]
        hits: list[PhysicsAABBHit] = []
        for entity in world.get_entities_with(Transform, Collider):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            if transform is None or collider is None or not collider.enabled:
                continue
            e_left, e_top, e_right, e_bottom = collider.get_bounds(transform.x, transform.y)
            if left < e_right and right > e_left and top < e_bottom and bottom > e_top:
                hits.append(
                    {
                        "entity": entity.name,
                        "entity_id": entity.id,
                        "is_trigger": bool(collider.is_trigger),
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
    ) -> list[PhysicsShapeCastHit]:
        steps = 20
        ox, oy = float(origin[0]), float(origin[1])
        dx, dy = float(direction[0]), float(direction[1])
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return []
        dx /= length
        dy /= length
        sw, sh = float(shape_size[0]), float(shape_size[1])
        half_w = sw / 2.0
        half_h = sh / 2.0

        best_hit: PhysicsShapeCastHit | None = None
        best_distance = float("inf")

        for i in range(steps + 1):
            t = max_distance * (i / float(steps))
            px = ox + dx * t
            py = oy + dy * t

            if shape_type == "circle":
                radius = sw / 2.0
                shape_left = px - radius
                shape_top = py - radius
                shape_right = px + radius
                shape_bottom = py + radius
            else:
                shape_left = px - half_w
                shape_top = py - half_h
                shape_right = px + half_w
                shape_bottom = py + half_h

            for entity in world.get_entities_with(Transform, Collider):
                transform = entity.get_component(Transform)
                collider = entity.get_component(Collider)
                if transform is None or collider is None or not collider.enabled:
                    continue
                collider_left, collider_top, collider_right, collider_bottom = collider.get_bounds(
                    transform.x, transform.y
                )

                overlap_left = max(shape_left, collider_left)
                overlap_top = max(shape_top, collider_top)
                overlap_right = min(shape_right, collider_right)
                overlap_bottom = min(shape_bottom, collider_bottom)

                if overlap_left < overlap_right and overlap_top < overlap_bottom:
                    dist = t
                    if dist < best_distance:
                        best_distance = dist
                        fraction = dist / max_distance if max_distance > 0.0 else 0.0
                        # Compute approximate normal from AABB overlap
                        n_ox = overlap_right - overlap_left
                        n_oy = overlap_bottom - overlap_top
                        nx = 0.0
                        ny = 0.0
                        if n_ox <= n_oy:
                            nx = 1.0 if px > (collider_left + collider_right) / 2.0 else -1.0
                        else:
                            ny = 1.0 if py > (collider_top + collider_bottom) / 2.0 else -1.0
                        best_hit = {
                            "entity": entity.name,
                            "entity_id": int(entity.id),
                            "position": {"x": px, "y": py},
                            "normal": {"x": nx, "y": ny},
                            "fraction": fraction,
                            "is_trigger": bool(collider.is_trigger),
                        }
                        break  # first entity that overlaps at this step

            if best_hit is not None and i > 0:
                break  # return earliest hit

        return [best_hit] if best_hit is not None else []

    def collect_contacts(self, world: Any) -> list[PhysicsContact]:
        del world
        return list(self._latest_contacts)

    def get_step_metrics(self) -> dict[str, float]:
        if self._physics_system is not None and hasattr(self._physics_system, "get_step_metrics"):
            return dict(self._physics_system.get_step_metrics())
        return {"ccd_bodies": 0, "swept_checks": 0}

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
    ) -> float | None:
        """Ray-capsule intersection: ray vs vertical segment + radius."""
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

        best = float("inf")

        # Top cap: circle at (cx, y_top)
        t_top = _ray_circle(cx, y_top, r)
        if t_top is not None:
            best = min(best, t_top)

        # Bottom cap: circle at (cx, y_bot)
        t_bot = _ray_circle(cx, y_bot, r)
        if t_bot is not None:
            best = min(best, t_bot)

        # Rectangular body: [cx - r, cx + r] x [y_top, y_bot]
        result = _ray_slab(0.0, max_distance, ox, dx, cx - r, cx + r)
        if result is not None:
            t_min, t_max = result
            if t_min <= t_max:
                result_y = _ray_slab(t_min, t_max, oy, dy, y_top, y_bot)
                if result_y is not None:
                    ty_min, ty_max = result_y
                    if ty_min <= ty_max and ty_min >= 0.0:
                        best = min(best, ty_min)

        if math.isfinite(best):
            return best
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
    ) -> float | None:
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
        return t_min if 0.0 <= t_min <= max_distance else None
