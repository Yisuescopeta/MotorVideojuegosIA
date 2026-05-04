"""
engine/components/colorrect.py - Rectangulo de color simple para UI/debug.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class ColorRect(Component):
    """Simple colored rectangle for UI/debug backgrounds."""

    def __init__(
        self,
        width: float = 100.0,
        height: float = 100.0,
        color_r: int = 255,
        color_g: int = 255,
        color_b: int = 255,
        color_a: int = 255,
    ) -> None:
        self.enabled: bool = True
        self.width: float = max(1.0, float(width))
        self.height: float = max(1.0, float(height))
        self.color_r: int = max(0, min(255, color_r))
        self.color_g: int = max(0, min(255, color_g))
        self.color_b: int = max(0, min(255, color_b))
        self.color_a: int = max(0, min(255, color_a))

    @property
    def color(self) -> tuple[int, int, int, int]:
        return (self.color_r, self.color_g, self.color_b, self.color_a)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "width": self.width,
            "height": self.height,
            "color_r": self.color_r,
            "color_g": self.color_g,
            "color_b": self.color_b,
            "color_a": self.color_a,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColorRect":
        component = cls(
            width=data.get("width", 100.0),
            height=data.get("height", 100.0),
            color_r=data.get("color_r", 255),
            color_g=data.get("color_g", 255),
            color_b=data.get("color_b", 255),
            color_a=data.get("color_a", 255),
        )
        component.enabled = data.get("enabled", True)
        return component
