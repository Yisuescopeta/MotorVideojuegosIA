"""
engine/components/canvas_modulate.py - Componente CanvasModulate adaptado de Godot.

Aplica un multiply de color sobre todo el canvas.
"""

from __future__ import annotations

from typing import Any, Tuple

from engine.ecs.component import Component


class CanvasModulate(Component):
    """Applies a color multiply to the entire canvas (Godot CanvasModulate)."""

    def __init__(self, color: Tuple[int, int, int, int] = (255, 255, 255, 255)) -> None:
        self.enabled: bool = True
        self.color: Tuple[int, int, int, int] = self._clamp_color(color)

    @staticmethod
    def _clamp_color(value: Tuple[int, ...]) -> Tuple[int, int, int, int]:
        seq = list(value)
        while len(seq) < 4:
            seq.append(255)
        seq = seq[:4]
        return (
            max(0, min(255, int(seq[0]))),
            max(0, min(255, int(seq[1]))),
            max(0, min(255, int(seq[2]))),
            max(0, min(255, int(seq[3]))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "color": list(self.color),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanvasModulate":
        color_data = data.get("color", [255, 255, 255, 255])
        if isinstance(color_data, (list, tuple)):
            color = tuple(int(v) for v in color_data)
        else:
            color = (255, 255, 255, 255)
        component = cls(color=color)
        component.enabled = bool(data.get("enabled", True))
        return component
