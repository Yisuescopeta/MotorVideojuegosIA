"""
engine/components/canvas_item_2d.py - Componente de primitivas de dibujo 2D (adaptado de Godot CanvasItem).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component

VALID_SHAPES = {"rect", "circle", "line"}


class CanvasItem2D(Component):
    """Componente que define primitivas de dibujo 2D (adaptado de Godot CanvasItem).

    Los draw_commands son declaraciones serializables de qué dibujar.
    El sistema CanvasItemSystem las ejecuta cada frame.
    """

    def __init__(
        self,
        draw_commands: list[dict[str, Any]] | None = None,
        z_index: int = 0,
        enabled: bool = True,
        visibility_layer: int = 1,
    ) -> None:
        self.enabled: bool = enabled
        self.z_index: int = z_index
        self.visibility_layer: int = int(visibility_layer)
        self.draw_commands: list[dict[str, Any]] = list(draw_commands) if draw_commands else []

    def add_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        filled: bool = True,
    ) -> None:
        self.draw_commands.append({
            "shape": "rect",
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "color": list(color),
            "filled": filled,
        })

    def add_circle(
        self,
        cx: float,
        cy: float,
        radius: float,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        filled: bool = True,
    ) -> None:
        self.draw_commands.append({
            "shape": "circle",
            "cx": cx,
            "cy": cy,
            "radius": radius,
            "color": list(color),
            "filled": filled,
        })

    def add_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        thickness: float = 1.0,
    ) -> None:
        self.draw_commands.append({
            "shape": "line",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "color": list(color),
            "thickness": thickness,
        })

    def clear_commands(self) -> None:
        self.draw_commands.clear()

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "z_index": self.z_index,
            "visibility_layer": self.visibility_layer,
            "draw_commands": self.draw_commands,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "CanvasItem2D":
        component = cls(
            draw_commands=data.get("draw_commands", []),
            z_index=data.get("z_index", 0),
            visibility_layer=data.get("visibility_layer", 1),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
