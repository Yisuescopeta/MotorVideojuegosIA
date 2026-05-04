"""
engine/systems/area2d_system.py - Sistema de monitoreo de areas 2D

PROPOSITO:
    Monitorea entidades con Area2D + Collider para detectar cuerpos
    y areas que entran/salen de su zona. Emite eventos via EventBus.

EVENTOS EMITIDOS:
    - body_entered: Un RigidBody entro en el area
    - body_exited: Un RigidBody salio del area
    - area_entered: Otra Area2D entro en el area
    - area_exited: Otra Area2D salio del area

NO procesa colisiones fisicas — solo monitorea overlaps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.components.area2d import Area2D
from engine.components.collider import Collider
from engine.components.collision_filter_2d import CollisionFilter2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.spatial_hash import SpatialHash2D

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus

AABB = tuple[float, float, float, float]


class Area2DSystem:
    """Sistema que monitorea entradas/salidas de cuerpos y areas en zonas Area2D."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus: Optional[EventBus] = event_bus
        self._spatial_hash: SpatialHash2D = SpatialHash2D(cell_size=128.0)
        self._query_buffer: set[int] = set()
        # Map area entity_id -> (entity, collider, aabb)
        self._area_entries: dict[int, tuple[Entity, Collider, AABB]] = {}
        # Map body entity_id -> (entity, collider, aabb) for RigidBody entities
        self._body_entries: dict[int, tuple[Entity, Collider, AABB]] = {}

    def set_event_bus(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def update(self, world: World) -> None:
        self._spatial_hash.clear()
        self._query_buffer.clear()
        self._area_entries.clear()
        self._body_entries.clear()

        # 1. Index all entities with Collider + Transform
        #    Separate into: areas (has Area2D.monitoring) and bodies (has RigidBody)
        for entity in world.get_entities_with(Transform, Collider):
            transform = entity.get_component(Transform)
            collider = entity.get_component(Collider)
            if transform is None or collider is None or not collider.enabled:
                continue

            aabb = collider.get_bounds(transform.x, transform.y)

            area2d = entity.get_component(Area2D)
            if area2d is not None and area2d.enabled and area2d.monitoring:
                self._area_entries[entity.id] = (entity, collider, aabb)
                self._spatial_hash.insert(entity.id, aabb)

            rigidbody = entity.get_component(RigidBody)
            if rigidbody is not None and rigidbody.enabled:
                self._body_entries[entity.id] = (entity, collider, aabb)
                self._spatial_hash.insert(entity.id, aabb)

        # 2. For each monitoring area, find overlapping bodies and areas
        for area_entity_id, (area_entity, area_collider, area_aabb) in self._area_entries.items():
            area2d = area_entity.get_component(Area2D)
            if area2d is None:
                continue

            query_result = self._spatial_hash.query_into(area_aabb, self._query_buffer)

            current_bodies: set[int] = set()
            current_areas: set[int] = set()

            area_filter = area_entity.get_component(CollisionFilter2D)

            for other_id in query_result:
                if other_id == area_entity_id:
                    continue

                # Check body overlap
                if other_id in self._body_entries:
                    other_entity, other_collider, other_aabb = self._body_entries[other_id]
                    if self._aabbs_overlap(area_aabb, other_aabb):
                        other_filter = other_entity.get_component(CollisionFilter2D)
                        if CollisionFilter2D.should_collide(area_filter, other_filter):
                            current_bodies.add(other_id)

                # Check area overlap
                if other_id in self._area_entries:
                    other_entity, other_collider, other_aabb = self._area_entries[other_id]
                    other_area2d = other_entity.get_component(Area2D)
                    if other_area2d is not None and other_area2d.monitorable:
                        if self._aabbs_overlap(area_aabb, other_aabb):
                            other_filter = other_entity.get_component(CollisionFilter2D)
                            if CollisionFilter2D.should_collide(area_filter, other_filter):
                                current_areas.add(other_id)

            prev_bodies = area2d._tracked_bodies
            prev_areas = area2d._tracked_areas

            # Body entered
            for body_id in current_bodies - prev_bodies:
                self._emit("body_entered", area_entity, area_entity_id, body_id, world)

            # Body exited
            for body_id in prev_bodies - current_bodies:
                self._emit("body_exited", area_entity, area_entity_id, body_id, world)

            # Area entered
            for area_id in current_areas - prev_areas:
                self._emit("area_entered", area_entity, area_entity_id, area_id, world)

            # Area exited
            for area_id in prev_areas - current_areas:
                self._emit("area_exited", area_entity, area_entity_id, area_id, world)

            area2d._tracked_bodies = current_bodies
            area2d._tracked_areas = current_areas

    def _emit(
        self,
        event_name: str,
        area_entity: Entity,
        area_entity_id: int,
        other_entity_id: int,
        world: World,
    ) -> None:
        if self._event_bus is None:
            return
        other_entity = world.get_entity(other_entity_id)
        self._event_bus.emit(
            event_name,
            {
                "entity_id": area_entity_id,
                "other_entity_id": other_entity_id,
                "entity_name": area_entity.name,
                "other_entity_name": other_entity.name if other_entity else "unknown",
            },
        )

    @staticmethod
    def _aabbs_overlap(aabb_a: AABB, aabb_b: AABB) -> bool:
        left_a, top_a, right_a, bottom_a = aabb_a
        left_b, top_b, right_b, bottom_b = aabb_b
        return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b
