"""
engine/components/uipanel.py - Panel UI con fondo de color o textura (adaptado Godot Panel).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class UIPanel(Component):
    """Panel UI con fondo de color o textura."""

    def __init__(
        self,
        enabled: bool = True,
        color: tuple[int, int, int, int] = (40, 40, 40, 255),
        border_color: tuple[int, int, int, int] = (60, 60, 60, 255),
        border_width: int = 0,
        corner_radius: int = 0,
        texture_path: str = "",
    ) -> None:
        self.enabled = enabled
        self.color = _color_tuple(color)
        self.border_color = _color_tuple(border_color)
        self.border_width = int(border_width)
        self.corner_radius = int(corner_radius)
        self.texture_path = str(texture_path or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "color": list(self.color),
            "border_color": list(self.border_color),
            "border_width": self.border_width,
            "corner_radius": self.corner_radius,
            "texture_path": self.texture_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIPanel":
        return cls(
            enabled=data.get("enabled", True),
            color=tuple(data.get("color", [40, 40, 40, 255])),  # type: ignore[arg-type]
            border_color=tuple(data.get("border_color", [60, 60, 60, 255])),  # type: ignore[arg-type]
            border_width=data.get("border_width", 0),
            corner_radius=data.get("corner_radius", 0),
            texture_path=data.get("texture_path", ""),
        )
