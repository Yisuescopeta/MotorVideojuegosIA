"""
engine/ecs/ - Sistema Entity-Component-System

PROPÓSITO:
    Implementación simple de ECS donde:
    - Entity: Solo un ID con nombre y lista de componentes
    - Component: Clase base con datos, sin lógica
    - World: Contenedor de todas las entidades

MÓDULOS:
    - entity: Clase Entity
    - component: Clase base Component
    - world: Registro y gestión de entidades
"""

from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.ecs.world import World

__all__ = [
    "Entity",
    "Component",
    "World",
]
