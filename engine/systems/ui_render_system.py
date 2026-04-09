"""
engine/systems/ui_render_system.py - Render overlay para Canvas/Text/Button.
"""

from __future__ import annotations

from typing import Any

import pyray as rl

from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.uibutton import UIButton
from engine.components.uitext import UIText
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.ui_system import UISystem


class UIRenderSystem:
    """Dibuja la UI en overlay usando el layout calculado por UISystem."""

    def render(self, world: World, ui_system: UISystem) -> None:
        layouts = ui_system.get_layout_snapshot(copy_result=False)
        if not layouts:
            return

        for canvas_name in ui_system.get_canvas_order():
            canvas_entity = world.get_entity_by_name(canvas_name)
            if canvas_entity is None:
                continue
            self._render_subtree(world, canvas_entity, layouts, ui_system)

    def _render_subtree(
        self,
        world: World,
        entity: Entity,
        layouts: dict[str, dict[str, Any]],
        ui_system: UISystem,
    ) -> None:
        layout = layouts.get(entity.name)
        if layout is not None:
            self._render_entity(entity, layout, ui_system)
        for child in world.get_children(entity.name):
            self._render_subtree(world, child, layouts, ui_system)

    def _render_entity(self, entity: Entity, layout: dict[str, Any], ui_system: UISystem) -> None:
        button = entity.get_component(UIButton)
        if button is not None and button.enabled:
            state = ui_system.get_button_state(entity)
            color = button.normal_color
            if not button.interactable:
                color = button.disabled_color
            elif state.get("pressed"):
                color = button.pressed_color
            elif state.get("hovered"):
                color = button.hover_color

            rect = self._button_rect(layout, button, state)
            rl.draw_rectangle_rounded(rect, 0.18, 8, rl.Color(*color))
            rl.draw_rectangle_rounded_lines_ex(rect, 0.18, 8, 2.0, rl.Color(18, 18, 18, 220))
            if state.get("focused") and button.interactable:
                focus_rect = rl.Rectangle(rect.x - 3.0, rect.y - 3.0, rect.width + 6.0, rect.height + 6.0)
                rl.draw_rectangle_rounded_lines_ex(focus_rect, 0.2, 8, 2.0, rl.Color(255, 210, 64, 255))
            if button.label and entity.get_component(UIText) is None:
                self._draw_label(button.label, rect, 24, rl.WHITE, "center", False)

        text = entity.get_component(UIText)
        if text is not None and text.enabled:
            self._draw_label(text.text, rl.Rectangle(layout["x"], layout["y"], layout["width"], layout["height"]), text.font_size, rl.Color(*text.color), text.alignment, text.wrap)

    def _button_rect(self, layout: dict[str, Any], button: UIButton, state: dict[str, bool]) -> rl.Rectangle:
        x = float(layout["x"])
        y = float(layout["y"])
        width = float(layout["width"])
        height = float(layout["height"])
        if state.get("pressed"):
            pressed_scale = max(0.5, min(1.0, float(button.transition_scale_pressed)))
            width *= pressed_scale
            height *= pressed_scale
            x += (float(layout["width"]) - width) * 0.5
            y += (float(layout["height"]) - height) * 0.5
        return rl.Rectangle(x, y, width, height)

    def _draw_label(
        self,
        text: str,
        rect: rl.Rectangle,
        font_size: int,
        color: rl.Color,
        alignment: str,
        wrap: bool,
    ) -> None:
        del wrap
        safe_font_size = max(10, int(font_size))
        text_width = rl.measure_text(text, safe_font_size)
        x = rect.x + 8
        if alignment == "center":
            x = rect.x + max(0.0, (rect.width - text_width) * 0.5)
        elif alignment == "right":
            x = rect.x + max(0.0, rect.width - text_width - 8)
        y = rect.y + max(0.0, (rect.height - safe_font_size) * 0.5)
        rl.draw_text(text, int(x), int(y), safe_font_size, color)
