"""PhysicsMaterial — friction, bounce, and surface properties.

Adaptado de Godot PhysicsMaterial. Define propiedades de interacción entre
superficies: fricción (friction), rebote (bounce), rugosidad (rough) y
absorción (absorbent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PhysicsMaterial:
    """Physics material defining surface interaction properties.

    Attributes:
        resource_id: Unique identifier for the resource.
        resource_name: Human-readable name.
        friction: Surface friction (0 = ice, 1 = normal).
        bounce: Restitution coefficient (0 = no bounce, 1 = perfect bounce).
        rough: If True, friction becomes infinite (never slide).
        absorbent: If True, bounce is always 0 regardless of bounce value.
    """

    resource_id: str = ""
    resource_name: str = "default"

    friction: float = 1.0
    bounce: float = 0.0
    rough: bool = False
    absorbent: bool = False

    def get_effective_friction(self) -> float:
        """Return effective friction: infinite if rough, else friction value."""
        if self.rough:
            return float('inf')
        return self.friction

    def get_effective_bounce(self) -> float:
        """Return effective bounce: 0 if absorbent, else bounce value."""
        if self.absorbent:
            return 0.0
        return self.bounce

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "friction": self.friction,
            "bounce": self.bounce,
            "rough": self.rough,
            "absorbent": self.absorbent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicsMaterial:
        return cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "default")),
            friction=float(data.get("friction", 1.0)),
            bounce=float(data.get("bounce", 0.0)),
            rough=bool(data.get("rough", False)),
            absorbent=bool(data.get("absorbent", False)),
        )
