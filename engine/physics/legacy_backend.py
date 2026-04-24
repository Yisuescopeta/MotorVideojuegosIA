from __future__ import annotations

import math
from typing import Any, Optional

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.physics.backend import PhysicsAABBHit, PhysicsBackend, PhysicsContact, PhysicsRayHit


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
