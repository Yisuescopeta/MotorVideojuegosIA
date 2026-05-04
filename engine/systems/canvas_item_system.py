"""
engine/systems/canvas_item_system.py - Sistema de renderizado para CanvasItem2D draw commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyray as rl

from engine.components.canvas_item_2d import CanvasItem2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World


class CanvasItemSystem:
    """Renderiza los draw_commands de CanvasItem2D usando pyray."""

    def render(self, world: "World") -> None:
        if not hasattr(rl, "is_window_ready") or not rl.is_window_ready():
            return

        entities = world.get_entities_with(CanvasItem2D, Transform)
        items: list[tuple[int, CanvasItem2D, Transform]] = []
        for entity in entities:
            canvas = entity.get_component(CanvasItem2D)
            transform = entity.get_component(Transform)
            if canvas is None or transform is None or not canvas.enabled:
                continue
            items.append((canvas.z_index, canvas, transform))

        items.sort(key=lambda item: item[0])

        for _, canvas, transform in items:
            for cmd in canvas.draw_commands:
                shape = cmd.get("shape", "rect")
                color = cmd.get("color", [255, 255, 255, 255])
                rl_color = rl.Color(
                    int(color[0]), int(color[1]), int(color[2]), int(color[3])
                )

                tx = transform.x + float(cmd.get("x", 0))
                ty = transform.y + float(cmd.get("y", 0))

                if shape == "rect":
                    filled = cmd.get("filled", True)
                    w_val = float(cmd.get("w", 32))
                    h_val = float(cmd.get("h", 32))
                    if filled:
                        rl.draw_rectangle(int(tx), int(ty), int(w_val), int(h_val), rl_color)
                    else:
                        rl.draw_rectangle_lines(int(tx), int(ty), int(w_val), int(h_val), rl_color)
                elif shape == "circle":
                    cx_val = tx + float(cmd.get("cx", 0))
                    cy_val = ty + float(cmd.get("cy", 0))
                    radius = float(cmd.get("radius", 16))
                    filled = cmd.get("filled", True)
                    if filled:
                        rl.draw_circle(int(cx_val), int(cy_val), radius, rl_color)
                    else:
                        rl.draw_circle_lines(int(cx_val), int(cy_val), radius, rl_color)
                elif shape == "line":
                    x1_val = tx + float(cmd.get("x1", 0))
                    y1_val = ty + float(cmd.get("y1", 0))
                    x2_val = tx + float(cmd.get("x2", 0))
                    y2_val = ty + float(cmd.get("y2", 0))
                    rl.draw_line(
                        int(x1_val), int(y1_val), int(x2_val), int(y2_val), rl_color
                    )
