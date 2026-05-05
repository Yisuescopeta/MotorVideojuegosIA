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
    schema_version: int = 1  # Para forward compat

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContactManifold2D:
        contacts_data = data.get("contacts", [])
        contacts = [
            ContactPoint2D(
                point_x=c.get("point_x", 0.0),
                point_y=c.get("point_y", 0.0),
                normal_x=c.get("normal_x", 0.0),
                normal_y=c.get("normal_y", 0.0),
                depth=c.get("depth", 0.0),
            )
            for c in contacts_data
        ]
        return cls(
            entity_a_id=data.get("entity_a_id", 0),
            entity_b_id=data.get("entity_b_id", 0),
            entity_a_name=data.get("entity_a_name", ""),
            entity_b_name=data.get("entity_b_name", ""),
            normal_x=data.get("normal_x", 0.0),
            normal_y=data.get("normal_y", 0.0),
            depth=data.get("depth", 0.0),
            impulse_x=data.get("impulse_x", 0.0),
            impulse_y=data.get("impulse_y", 0.0),
            relative_velocity_x=data.get("relative_velocity_x", 0.0),
            relative_velocity_y=data.get("relative_velocity_y", 0.0),
            contact_count=data.get("contact_count", 0),
            contacts=contacts,
            is_trigger=data.get("is_trigger", False),
            schema_version=data.get("schema_version", 1),
        )
