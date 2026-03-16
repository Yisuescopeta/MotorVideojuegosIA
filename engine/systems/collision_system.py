"""
engine/systems/collision_system.py - Sistema de detecciÃ³n de colisiones
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus


@dataclass
class CollisionInfo:
    entity_a: Entity
    entity_b: Entity
    is_trigger: bool


class CollisionSystem:
    """Sistema de detecciÃ³n de colisiones AABB."""

    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
        self._collisions: list[CollisionInfo] = []
        self._event_bus: Optional["EventBus"] = event_bus

    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus

    def update(self, world: World) -> None:
        self._collisions.clear()
        entities = world.get_entities_with(Transform, Collider)
        for index, entity_a in enumerate(entities):
            for entity_b in entities[index + 1:]:
                if not self._check_collision(world, entity_a, entity_b):
                    continue
                collider_a = entity_a.get_component(Collider)
                collider_b = entity_b.get_component(Collider)
                is_trigger = bool(
                    (collider_a is not None and collider_a.is_trigger)
                    or (collider_b is not None and collider_b.is_trigger)
                )
                collision = CollisionInfo(entity_a=entity_a, entity_b=entity_b, is_trigger=is_trigger)
                self._collisions.append(collision)
                self._emit_collision_event(collision)

    def _emit_collision_event(self, collision: CollisionInfo) -> None:
        if self._event_bus is None:
            return
        event_name = "on_trigger_enter" if collision.is_trigger else "on_collision"
        self._event_bus.emit(
            event_name,
            {
                "entity_a": collision.entity_a.name,
                "entity_b": collision.entity_b.name,
                "entity_a_id": collision.entity_a.id,
                "entity_b_id": collision.entity_b.id,
                "is_trigger": collision.is_trigger,
            },
        )

    def _check_collision(self, world: World, entity_a: Entity, entity_b: Entity) -> bool:
        transform_a = entity_a.get_component(Transform)
        transform_b = entity_b.get_component(Transform)
        collider_a = entity_a.get_component(Collider)
        collider_b = entity_b.get_component(Collider)
        rigidbody_a = entity_a.get_component(RigidBody)
        rigidbody_b = entity_b.get_component(RigidBody)
        if None in (transform_a, transform_b, collider_a, collider_b):
            return False
        if not self._layers_can_collide(world, entity_a.layer, entity_b.layer):
            return False
        if not self._is_simulated(rigidbody_a) and not self._is_simulated(rigidbody_b):
            return False
        if not self._allows_contact(rigidbody_a, rigidbody_b):
            return False

        left_a, top_a, right_a, bottom_a = collider_a.get_bounds(transform_a.x, transform_a.y)
        left_b, top_b, right_b, bottom_b = collider_b.get_bounds(transform_b.x, transform_b.y)
        return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b

    def _layers_can_collide(self, world: World, layer_a: str, layer_b: str) -> bool:
        matrix = world.feature_metadata.get("physics_2d", {}).get("layer_matrix", {})
        if not matrix:
            return True
        return bool(matrix.get(f"{layer_a}|{layer_b}", True))

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

    def get_collisions(self) -> list[CollisionInfo]:
        return self._collisions.copy()

    def get_collisions_for(self, entity: Entity) -> list[CollisionInfo]:
        return [col for col in self._collisions if col.entity_a.id == entity.id or col.entity_b.id == entity.id]

    def has_collision(self, entity: Entity) -> bool:
        return len(self.get_collisions_for(entity)) > 0
