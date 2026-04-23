"""
engine/components/marker2d.py - Marcador posicional 2D al estilo Godot.

Punto de referencia nombrado para spawn points, waypoints, etc.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class Marker2D(Component):
    """Marcador posicional 2D para puntos de referencia en escena."""

    def __init__(
        self,
        marker_name: str = "",
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        self.enabled: bool = True
        self.marker_name: str = str(marker_name or "")
        self.offset_x: float = float(offset_x)
        self.offset_y: float = float(offset_y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "marker_name": self.marker_name,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Marker2D":
        component = cls(
            marker_name=data.get("marker_name", ""),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
        )
        component.enabled = data.get("enabled", True)
        return component
