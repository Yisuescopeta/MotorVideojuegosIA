from __future__ import annotations

from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EntityData
from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.uibutton import UIButton
from engine.components.uitext import UIText


class UIAPI(EngineAPIComponent):
    """Declarative UI authoring and runtime UI helpers exposed by EngineAPI."""

    def create_canvas(
        self,
        name: str = "Canvas",
        reference_width: int = 800,
        reference_height: int = 600,
        sort_order: int = 0,
        initial_focus_entity_id: str = "",
    ) -> ActionResult:
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "Canvas": {
                "enabled": True,
                "render_mode": "screen_space_overlay",
                "reference_width": reference_width,
                "reference_height": reference_height,
                "match_mode": "stretch",
                "sort_order": sort_order,
                "initial_focus_entity_id": str(initial_focus_entity_id or "").strip(),
            },
            "RectTransform": {
                "enabled": True,
                "anchor_min_x": 0.0,
                "anchor_min_y": 0.0,
                "anchor_max_x": 1.0,
                "anchor_max_y": 1.0,
                "pivot_x": 0.0,
                "pivot_y": 0.0,
                "anchored_x": 0.0,
                "anchored_y": 0.0,
                "width": 0.0,
                "height": 0.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
        }
        return self.api.create_entity(name, components=components)

    def create_ui_element(
        self,
        name: str,
        parent: str,
        rect_transform: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Any]] = {
            "RectTransform": {
                "enabled": True,
                "anchor_min_x": 0.5,
                "anchor_min_y": 0.5,
                "anchor_max_x": 0.5,
                "anchor_max_y": 0.5,
                "pivot_x": 0.5,
                "pivot_y": 0.5,
                "anchored_x": 0.0,
                "anchored_y": 0.0,
                "width": 100.0,
                "height": 40.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            }
        }
        if rect_transform:
            components["RectTransform"].update(rect_transform)
        return self.api.create_child_entity(parent, name, components=components)

    def set_rect_transform(self, entity_name: str, properties: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        for property_name, value in properties.items():
            result = self.api.edit_component(entity_name, "RectTransform", property_name, value)
            if not result["success"]:
                return result
        return self.ok("RectTransform updated", {"entity": entity_name})

    def create_ui_text(
        self,
        name: str,
        text: str,
        parent: str,
        rect_transform: Optional[Dict[str, Any]] = None,
        font_size: int = 24,
        alignment: str = "center",
    ) -> ActionResult:
        self.ensure_edit_mode()
        result = self.create_ui_element(name=name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.api.add_component(
            name,
            "UIText",
            {
                "enabled": True,
                "text": text,
                "font_size": font_size,
                "color": [255, 255, 255, 255],
                "alignment": alignment,
                "wrap": False,
            },
        )
        return add_result if not add_result["success"] else self.ok("UIText created", {"entity": name})

    def create_ui_button(
        self,
        name: str,
        label: str,
        parent: str,
        rect_transform: Optional[Dict[str, Any]] = None,
        on_click: Optional[Dict[str, Any]] = None,
        *,
        focusable: bool = True,
        nav_up: str = "",
        nav_down: str = "",
        nav_left: str = "",
        nav_right: str = "",
    ) -> ActionResult:
        self.ensure_edit_mode()
        result = self.create_ui_element(name=name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.api.add_component(
            name,
            "UIButton",
            {
                "enabled": True,
                "interactable": True,
                "label": label,
                "normal_color": [72, 72, 72, 255],
                "hover_color": [92, 92, 92, 255],
                "pressed_color": [56, 56, 56, 255],
                "disabled_color": [48, 48, 48, 200],
                "transition_scale_pressed": 0.96,
                "on_click": on_click or {"type": "emit_event", "name": "ui.button_clicked"},
                "focusable": bool(focusable),
                "nav_up": str(nav_up or "").strip(),
                "nav_down": str(nav_down or "").strip(),
                "nav_left": str(nav_left or "").strip(),
                "nav_right": str(nav_right or "").strip(),
            },
        )
        return add_result if not add_result["success"] else self.ok("UIButton created", {"entity": name})

    def set_button_on_click(self, entity_name: str, on_click: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        return self.api.edit_component(entity_name, "UIButton", "on_click", on_click)

    def set_canvas_initial_focus(self, entity_name: str, initial_focus_entity_id: str) -> ActionResult:
        self.ensure_edit_mode()
        return self.api.edit_component(entity_name, "Canvas", "initial_focus_entity_id", str(initial_focus_entity_id or "").strip())

    def set_button_navigation(
        self,
        entity_name: str,
        *,
        focusable: Optional[bool] = None,
        nav_up: Optional[str] = None,
        nav_down: Optional[str] = None,
        nav_left: Optional[str] = None,
        nav_right: Optional[str] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        updates = {
            "focusable": focusable,
            "nav_up": nav_up,
            "nav_down": nav_down,
            "nav_left": nav_left,
            "nav_right": nav_right,
        }
        for property_name, value in updates.items():
            if value is None:
                continue
            result = self.api.edit_component(entity_name, "UIButton", property_name, value)
            if not result["success"]:
                return result
        return self.ok("UIButton navigation updated", {"entity": entity_name})

    def list_ui_nodes(self) -> list[EntityData]:
        if self.game is None or self.game.world is None:
            return []
        nodes: list[EntityData] = []
        for entity in self.game.world.get_all_entities():
            if any(entity.has_component(component) for component in (Canvas, RectTransform, UIText, UIButton)):
                nodes.append(self.api.get_entity(entity.name))
        return nodes

    def get_ui_layout(self, entity_name: str) -> Dict[str, Any]:
        if self.game is None:
            return {}
        return self.game.get_ui_entity_screen_rect(
            entity_name,
            viewport_size=(float(self.game.width), float(self.game.height)),
        ) or {}

    def click_ui_button(self, entity_name: str) -> ActionResult:
        if self.game is None:
            return self.fail("UI system not ready")
        clicked = self.game.click_ui_entity(
            entity_name,
            viewport_size=(float(self.game.width), float(self.game.height)),
        )
        return self.ok("UIButton clicked", {"entity": entity_name}) if clicked else self.fail("UIButton click failed")

    def get_ui_focus(self) -> Dict[str, Any]:
        if self.game is None or self.game.world is None or self.game._ui_system is None:
            return {
                "active_canvas": None,
                "focused_entity": None,
                "focused_button": None,
                "has_focus": False,
                "canvas_focus": {},
            }
        viewport_size = (float(self.game.width), float(self.game.height))
        self.game._ui_system.ensure_layout_cache(self.game.world, viewport_size)
        self.game._ui_system.update(self.game.world, viewport_size, allow_interaction=False)
        active_canvas = self.game._ui_system.get_active_canvas_name()
        focused_entity = self.game._ui_system.get_focused_entity_name(active_canvas) if active_canvas else self.game._ui_system.get_focused_entity_name()
        focused_button = None
        if focused_entity:
            entity = self.game.world.get_entity_by_name(focused_entity)
            button = entity.get_component(UIButton) if entity is not None else None
            if button is not None:
                layout = self.game._ui_system.get_layout_entry(focused_entity)
                focused_button = {
                    "entity": focused_entity,
                    "canvas": active_canvas,
                    "label": button.label,
                    "interactable": button.interactable,
                    "focusable": button.focusable,
                    "navigation": {
                        "up": button.nav_up,
                        "down": button.nav_down,
                        "left": button.nav_left,
                        "right": button.nav_right,
                    },
                    "layout": layout,
                }
        return {
            "active_canvas": active_canvas,
            "focused_entity": focused_entity,
            "focused_button": focused_button,
            "has_focus": focused_entity is not None,
            "canvas_focus": self.game._ui_system.get_focus_snapshot(),
        }

    def move_ui_focus(self, direction: str) -> ActionResult:
        if self.game is None:
            return self.fail("UI system not ready")
        focused = self.game.move_ui_focus(direction, viewport_size=(float(self.game.width), float(self.game.height)))
        return self.ok("UI focus moved", {"direction": direction, "focused_entity": focused}) if focused else self.fail("UI focus move failed")

    def submit_ui_focus(self) -> ActionResult:
        if self.game is None:
            return self.fail("UI system not ready")
        success = self.game.submit_ui_focus(viewport_size=(float(self.game.width), float(self.game.height)))
        return self.ok("Focused UI submitted") if success else self.fail("Focused UI submit failed")

    def cancel_ui_focus(self) -> ActionResult:
        if self.game is None or self.game.world is None or self.game._ui_system is None:
            return self.fail("UI system not ready")
        cancelled_canvas = self.game._ui_system.cancel_active_focus(
            self.game.world,
            (float(self.game.width), float(self.game.height)),
        )
        return (
            self.ok("Focused UI cancelled", {"active_canvas": cancelled_canvas})
            if cancelled_canvas is not None
            else self.fail("Focused UI cancel failed")
        )

    def set_ui_focus(self, entity_name: str, canvas_name: Optional[str] = None) -> ActionResult:
        if self.game is None or self.game.world is None or self.game._ui_system is None:
            return self.fail("UI system not ready")
        focused = self.game._ui_system.set_focus(
            self.game.world,
            (float(self.game.width), float(self.game.height)),
            entity_name,
            canvas_name=canvas_name,
        )
        return (
            self.ok("UI focus set", {"focused_entity": focused, "active_canvas": self.game._ui_system.get_active_canvas_name()})
            if focused is not None
            else self.fail("UI focus set failed")
        )

    def focus_entity(self, entity_name: str, canvas_name: Optional[str] = None) -> ActionResult:
        return self.set_ui_focus(entity_name, canvas_name=canvas_name)

    def ui_move_focus(self, direction: str) -> ActionResult:
        return self.move_ui_focus(direction)

    def ui_submit(self) -> ActionResult:
        return self.submit_ui_focus()

    def ui_cancel(self) -> ActionResult:
        return self.cancel_ui_focus()

    def inject_ui_navigation(
        self,
        *,
        move_x: int = 0,
        move_y: int = 0,
        submit: bool = False,
        cancel: bool = False,
        frames: int = 1,
    ) -> ActionResult:
        if self.game is None:
            return self.fail("UI system not ready")
        injected = self.game.inject_ui_navigation(
            move_x=move_x,
            move_y=move_y,
            submit=submit,
            cancel=cancel,
            frames=frames,
        )
        return (
            self.ok(
                "UI navigation injected",
                {"move_x": move_x, "move_y": move_y, "submit": submit, "cancel": cancel, "frames": frames},
            )
            if injected
            else self.fail("UI navigation injection failed")
        )
