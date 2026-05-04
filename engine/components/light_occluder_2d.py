"""
engine/components/light_occluder_2d.py - Bloqueador de luz 2D serializable (adaptado de Godot LightOccluder2D)
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class LightOccluder2D(Component):
    """Componente que bloquea luz 2D, creando sombras (adaptado de Godot LightOccluder2D).

    MVP: solo soporta forma "box" (rectangulo axis-aligned).
    """

    VALID_SHAPES: set[str] = {"box"}

    def __init__(
        self,
        shape: str = "box",
        enabled: bool = True,
        width: float = 32.0,
        height: float = 32.0,
        points: list[tuple[float, float]] | None = None,
    ) -> None:
        self.enabled: bool = enabled
        self.shape: str = shape if shape in self.VALID_SHAPES else "box"
        self.width: float = float(width)
        self.height: float = float(height)
        self.points: list[tuple[float, float]] = points or []

    def get_bounds(self, transform_x: float = 0.0, transform_y: float = 0.0) -> tuple[float, float, float, float]:
        """Retorna AABB del occluder."""
        if self.shape == "box":
            return (
                transform_x,
                transform_y,
                transform_x + self.width,
                transform_y + self.height,
            )
        return (transform_x, transform_y, transform_x + 32.0, transform_y + 32.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "shape": self.shape,
            "width": self.width,
            "height": self.height,
            "points": self.points,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LightOccluder2D":
        return cls(
            shape=data.get("shape", "box"),
            enabled=data.get("enabled", True),
            width=data.get("width", 32.0),
            height=data.get("height", 32.0),
            points=data.get("points", []),
        )
