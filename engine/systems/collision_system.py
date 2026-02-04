"""
engine/systems/collision_system.py - Sistema de detección de colisiones

PROPÓSITO:
    Detecta colisiones AABB entre entidades con Collider.
    Emite eventos on_collision y on_trigger_enter al EventBus.

EVENTOS EMITIDOS:
    - on_collision: Colisión entre dos entidades sólidas
    - on_trigger_enter: Una entidad entra en un trigger
"""

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.components.transform import Transform
from engine.components.collider import Collider

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus


@dataclass
class CollisionInfo:
    """Información sobre una colisión detectada."""
    entity_a: Entity
    entity_b: Entity
    is_trigger: bool


class CollisionSystem:
    """Sistema de detección de colisiones AABB."""
    
    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
        """
        Inicializa el sistema.
        
        Args:
            event_bus: Bus de eventos para emitir colisiones (opcional)
        """
        self._collisions: List[CollisionInfo] = []
        self._event_bus: Optional["EventBus"] = event_bus
    
    def set_event_bus(self, event_bus: "EventBus") -> None:
        """Asigna el bus de eventos."""
        self._event_bus = event_bus
    
    def update(self, world: World) -> None:
        """Detecta colisiones entre todas las entidades."""
        self._collisions.clear()
        
        entities = world.get_entities_with(Transform, Collider)
        
        for i, entity_a in enumerate(entities):
            for entity_b in entities[i + 1:]:
                if self._check_collision(entity_a, entity_b):
                    collider_a = entity_a.get_component(Collider)
                    collider_b = entity_b.get_component(Collider)
                    is_trigger = (
                        (collider_a is not None and collider_a.is_trigger) or
                        (collider_b is not None and collider_b.is_trigger)
                    )
                    
                    collision = CollisionInfo(
                        entity_a=entity_a,
                        entity_b=entity_b,
                        is_trigger=is_trigger
                    )
                    self._collisions.append(collision)
                    
                    # Emitir evento
                    self._emit_collision_event(collision)
    
    def _emit_collision_event(self, collision: CollisionInfo) -> None:
        """Emite evento de colisión al EventBus."""
        if self._event_bus is None:
            return
        
        event_name = "on_trigger_enter" if collision.is_trigger else "on_collision"
        
        self._event_bus.emit(event_name, {
            "entity_a": collision.entity_a.name,
            "entity_b": collision.entity_b.name,
            "entity_a_id": collision.entity_a.id,
            "entity_b_id": collision.entity_b.id,
            "is_trigger": collision.is_trigger
        })
    
    def _check_collision(self, entity_a: Entity, entity_b: Entity) -> bool:
        """Verifica si dos entidades están colisionando (AABB)."""
        transform_a = entity_a.get_component(Transform)
        transform_b = entity_b.get_component(Transform)
        collider_a = entity_a.get_component(Collider)
        collider_b = entity_b.get_component(Collider)
        
        if None in (transform_a, transform_b, collider_a, collider_b):
            return False
        
        left_a, top_a, right_a, bottom_a = collider_a.get_bounds(transform_a.x, transform_a.y)
        left_b, top_b, right_b, bottom_b = collider_b.get_bounds(transform_b.x, transform_b.y)
        
        return (
            left_a < right_b and
            right_a > left_b and
            top_a < bottom_b and
            bottom_a > top_b
        )
    
    def get_collisions(self) -> List[CollisionInfo]:
        """Retorna la lista de colisiones detectadas."""
        return self._collisions.copy()
    
    def get_collisions_for(self, entity: Entity) -> List[CollisionInfo]:
        """Retorna las colisiones que involucran a una entidad."""
        return [
            col for col in self._collisions
            if col.entity_a.id == entity.id or col.entity_b.id == entity.id
        ]
    
    def has_collision(self, entity: Entity) -> bool:
        """Verifica si una entidad tiene alguna colisión."""
        return len(self.get_collisions_for(entity)) > 0
