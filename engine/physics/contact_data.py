"""
engine/physics/contact_data.py - Datos de contacto enriquecidos para colisiones.

Adaptado del KinematicCollision2D de Godot: normal, profundidad de penetracion,
impulso, velocidad relativa y puntos de contacto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContactPoint2D:
    """Un punto de contacto individual entre dos colisionadores."""

    point_x: float = 0.0
    point_y: float = 0.0
    normal_x: float = 0.0
    normal_y: float = 0.0
    depth: float = 0.0  # Profundidad de penetración

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_x": self.point_x,
            "point_y": self.point_y,
            "normal_x": self.normal_x,
            "normal_y": self.normal_y,
            "depth": self.depth,
        }


@dataclass
class ContactManifold2D:
    """Manifold de contacto entre dos colisionadores (Godot KinematicCollision2D adaptado)."""

    entity_a_id: int = 0
    entity_b_id: int = 0
    entity_a_name: str = ""
    entity_b_name: str = ""
    normal_x: float = 0.0  # Normal de colision (apunta de A hacia B)
    normal_y: float = 0.0
    depth: float = 0.0  # Profundidad maxima de penetracion
    impulse_x: float = 0.0  # Impulso aplicado en la resolucion
    impulse_y: float = 0.0
    relative_velocity_x: float = 0.0  # Velocidad relativa en el punto de contacto
    relative_velocity_y: float = 0.0
    contact_count: int = 0  # Numero de puntos de contacto
    contacts: list[ContactPoint2D] = field(default_factory=list)  # Lista de ContactPoint2D
    is_trigger: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_a_id": self.entity_a_id,
            "entity_b_id": self.entity_b_id,
            "entity_a_name": self.entity_a_name,
            "entity_b_name": self.entity_b_name,
            "normal_x": self.normal_x,
            "normal_y": self.normal_y,
            "depth": self.depth,
            "impulse_x": self.impulse_x,
            "impulse_y": self.impulse_y,
            "relative_velocity_x": self.relative_velocity_x,
            "relative_velocity_y": self.relative_velocity_y,
            "contact_count": self.contact_count,
            "contacts": [c.to_dict() for c in self.contacts],
            "is_trigger": self.is_trigger,
        }
