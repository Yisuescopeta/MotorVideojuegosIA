from __future__ import annotations

from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EntityData
from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.uibutton import UIButton
from engine.components.uiimage import UIImage
from engine.components.uitext import UIText


class UIAPI(EngineAPIComponent):
    """Declarative UI authoring and runtime UI helpers exposed by EngineAPI."""

    def create_canvas(
        self,
        name: str = "Canvas",
        reference_width: int = 800,
        reference_height: int = 600,
        sort_order: int = 0,
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
        normal_sprite: Any = None,
        hover_sprite: Any = None,
        pressed_sprite: Any = None,
        disabled_sprite: Any = None,
        normal_slice: str = "",
        hover_slice: str = "",
        pressed_slice: str = "",
        disabled_slice: str = "",
        preserve_aspect: bool = True,
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
                "normal_sprite": normal_sprite,
                "hover_sprite": hover_sprite,
                "pressed_sprite": pressed_sprite,
                "disabled_sprite": disabled_sprite,
                "normal_slice": normal_slice,
                "hover_slice": hover_slice,
                "pressed_slice": pressed_slice,
                "disabled_slice": disabled_slice,
                "image_tint": [255, 255, 255, 255],
                "preserve_aspect": preserve_aspect,
            },
        )
        return add_result if not add_result["success"] else self.ok("UIButton created", {"entity": name})

    def create_ui_image(
        self,
        name: str,
        parent: str,
        sprite: Any,
        rect_transform: Optional[Dict[str, Any]] = None,
        slice_name: str = "",
        preserve_aspect: bool = True,
        tint: Optional[list[int] | tuple[int, int, int, int]] = None,
    ) -> ActionResult:
        self.ensure_edit_mode()
        result = self.create_ui_element(name=name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.api.add_component(
            name,
            "UIImage",
            {
                "enabled": True,
                "sprite": sprite,
                "slice_name": slice_name,
                "tint": list(tint) if tint is not None else [255, 255, 255, 255],
                "preserve_aspect": preserve_aspect,
            },
        )
        return add_result if not add_result["success"] else self.ok("UIImage created", {"entity": name})

    def set_button_on_click(self, entity_name: str, on_click: Dict[str, Any]) -> ActionResult:
        self.ensure_edit_mode()
        return self.api.edit_component(entity_name, "UIButton", "on_click", on_click)

    def list_ui_nodes(self) -> list[EntityData]:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        nodes: list[EntityData] = []
        for entity in runtime.world.get_all_entities():
            if any(entity.has_component(component) for component in (Canvas, RectTransform, UIText, UIButton, UIImage)):
                nodes.append(self.api.get_entity(entity.name))
        return nodes

    def get_ui_layout(self, entity_name: str) -> Dict[str, Any]:
        runtime = self.runtime
        if runtime is None:
            return {}
        return runtime.get_ui_entity_screen_rect(
            entity_name,
            viewport_size=(float(runtime.width), float(runtime.height)),
        ) or {}

    def click_ui_button(self, entity_name: str) -> ActionResult:
        runtime = self.runtime
        if runtime is None:
            return self.fail("UI system not ready")
        clicked = runtime.click_ui_entity(
            entity_name,
            viewport_size=(float(runtime.width), float(runtime.height)),
        )
        return self.ok("UIButton clicked", {"entity": entity_name}) if clicked else self.fail("UIButton click failed")
