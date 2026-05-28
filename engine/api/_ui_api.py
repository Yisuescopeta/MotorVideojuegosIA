from __future__ import annotations

from typing import Dict, Optional, Union

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EntityData
from engine.components.canvas import Canvas
from engine.components.mobile_controls_2d import MobileControls2D
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
        """Create a UI Canvas entity with Canvas + RectTransform components.

        The Canvas serves as the root of a UI hierarchy. It uses screen-space
        overlay rendering by default.

        Args:
            name: Entity name (default "Canvas").
            reference_width: Reference resolution width for UI scaling.
            reference_height: Reference resolution height for UI scaling.
            sort_order: Draw order among multiple canvases (higher = on top).

        Returns:
            ActionResult confirming the canvas entity was created.
        """
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Union[str, int, float, bool, list, dict, None]]] = {
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
        rect_transform: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
    ) -> ActionResult:
        """Create a basic UI element with RectTransform as a child of a Canvas.

        Args:
            name: Entity name.
            parent: Parent entity name (typically a Canvas).
            rect_transform: Optional overrides for the RectTransform component.

        Returns:
            ActionResult confirming the UI element was created.
        """
        self.ensure_edit_mode()
        components: Dict[str, Dict[str, Union[str, int, float, bool, list, dict, None]]] = {
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

    def set_rect_transform(self, entity_name: str, properties: Dict[str, Union[str, int, float, bool, list, dict, None]]) -> ActionResult:
        """Update RectTransform properties of a UI element.

        Args:
            entity_name: Name of the UI entity.
            properties: Mapping of RectTransform property names to new values
                (e.g. {"anchored_x": 100.0, "width": 200.0}).

        Returns:
            ActionResult confirming all properties were updated, or failure
            on the first property that fails.
        """
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
        rect_transform: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
        font_size: int = 24,
        alignment: str = "center",
    ) -> ActionResult:
        """Create a UI Text entity as a child of a Canvas or other UI element.

        Args:
            name: Entity name.
            text: Display text string.
            parent: Parent entity name.
            rect_transform: Optional RectTransform overrides.
            font_size: Font size in pixels (default 24).
            alignment: Text alignment: "left", "center", or "right" (default "center").

        Returns:
            ActionResult confirming the UIText entity was created.
        """
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
        rect_transform: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
        on_click: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
        normal_sprite: Optional[Union[str, dict]] = None,
        hover_sprite: Optional[Union[str, dict]] = None,
        pressed_sprite: Optional[Union[str, dict]] = None,
        disabled_sprite: Optional[Union[str, dict]] = None,
        normal_slice: str = "",
        hover_slice: str = "",
        pressed_slice: str = "",
        disabled_slice: str = "",
        preserve_aspect: bool = True,
    ) -> ActionResult:
        """Create a UI Button entity with label, sprites, and click handler.

        Args:
            name: Entity name.
            label: Button text label.
            parent: Parent entity name.
            rect_transform: Optional RectTransform overrides.
            on_click: Click action configuration dict (e.g.
                {"type": "emit_event", "name": "ui.button_clicked"}).
            normal_sprite: Sprite for the normal state.
            hover_sprite: Sprite for the hover state.
            pressed_sprite: Sprite for the pressed state.
            disabled_sprite: Sprite for the disabled state.
            normal_slice: Slice name for normal sprite.
            hover_slice: Slice name for hover sprite.
            pressed_slice: Slice name for pressed sprite.
            disabled_slice: Slice name for disabled sprite.
            preserve_aspect: Whether to preserve sprite aspect ratio.

        Returns:
            ActionResult confirming the UIButton entity was created.
        """
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
        sprite: Optional[Union[str, dict]],
        rect_transform: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
        slice_name: str = "",
        preserve_aspect: bool = True,
        tint: Optional[list[int] | tuple[int, int, int, int]] = None,
    ) -> ActionResult:
        """Create a UI Image entity displaying a sprite.

        Args:
            name: Entity name.
            parent: Parent entity name.
            sprite: Sprite asset reference or identifier.
            rect_transform: Optional RectTransform overrides.
            slice_name: Sprite slice name within a sprite sheet.
            preserve_aspect: Whether to preserve sprite aspect ratio.
            tint: RGBA color tint as [R, G, B, A] or tuple (default white).

        Returns:
            ActionResult confirming the UIImage entity was created.
        """
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

    def create_mobile_controls(
        self,
        target_entity: str = "Player",
        profile: str = "platformer",
        replace: bool = False,
    ) -> ActionResult:
        """Create a serializable mobile controls overlay for a target InputMap."""
        self.ensure_edit_mode()
        target = str(target_entity or "Player").strip() or "Player"
        profile_name = str(profile or "platformer").strip() or "platformer"
        canvas_name = "MobileControlsCanvas"
        overlay_name = "MobileControlsOverlay"

        existing = self._find_mobile_controls_overlay()
        if existing and not replace:
            return self.ok(
                "Mobile controls already exist",
                {"entity": existing, "target_entity": target, "created": False},
            )
        if existing and replace:
            delete_result = self.api.delete_entity(existing)
            if not delete_result["success"]:
                return delete_result

        if not self._entity_exists(canvas_name):
            canvas_result = self.create_canvas(
                name=canvas_name,
                reference_width=1280,
                reference_height=720,
                sort_order=100,
            )
            if not canvas_result["success"]:
                return canvas_result

        result = self.create_ui_element(
            name=overlay_name,
            parent=canvas_name,
            rect_transform={
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
            },
        )
        if not result["success"]:
            return result

        add_result = self.api.add_component(
            overlay_name,
            "MobileControls2D",
            {
                "enabled": True,
                "target_entity": target,
                "profile": profile_name,
                "left_stick_enabled": True,
                "action_1_enabled": True,
                "action_2_enabled": profile_name != "platformer",
            },
        )
        if not add_result["success"]:
            return add_result
        return self.ok(
            "Mobile controls created",
            {"entity": overlay_name, "canvas": canvas_name, "target_entity": target, "profile": profile_name, "created": True},
        )

    def _entity_exists(self, entity_name: str) -> bool:
        try:
            self.api.get_entity(entity_name)
            return True
        except Exception:
            return False

    def _find_mobile_controls_overlay(self) -> str:
        try:
            entities = self.api.list_entities(active=None)
        except Exception:
            return ""
        for entity in entities:
            components = entity.get("components", {}) if isinstance(entity, dict) else {}
            if isinstance(components, dict) and "MobileControls2D" in components:
                return str(entity.get("name", "") or "")
        return ""

    def set_button_on_click(self, entity_name: str, on_click: Dict[str, Union[str, int, float, bool, list, dict, None]]) -> ActionResult:
        """Set the click action handler for a UIButton entity.

        Args:
            entity_name: Name of the UIButton entity.
            on_click: Click action configuration dictionary.

        Returns:
            ActionResult confirming the click handler was updated.
        """
        self.ensure_edit_mode()
        return self.api.edit_component(entity_name, "UIButton", "on_click", on_click)

    def list_ui_nodes(self) -> list[EntityData]:
        """List all UI-related entities (Canvas, RectTransform, UIText, UIButton, UIImage, MobileControls2D).

        Returns:
            List of EntityData dictionaries for all UI entities in the scene.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        nodes: list[EntityData] = []
        for entity in runtime.world.iter_all_entities():
            if any(entity.has_component(component) for component in (Canvas, RectTransform, UIText, UIButton, UIImage, MobileControls2D)):
                nodes.append(self.api.get_entity(entity.name))
        return nodes

    def get_ui_layout(self, entity_name: str) -> dict[str, float]:
        """Get the computed screen-space rectangle for a UI entity.

        Args:
            entity_name: Name of the UI entity.

        Returns:
            Dictionary with screen rectangle data (x, y, width, height, etc.),
            or empty dict if entity not found.
        """
        runtime = self.runtime
        if runtime is None:
            return {}
        return runtime.get_ui_entity_screen_rect(
            entity_name,
            viewport_size=(float(runtime.width), float(runtime.height)),
        ) or {}

    def click_ui_button(self, entity_name: str) -> ActionResult:
        """Programmatically trigger a click on a UIButton entity.

        Args:
            entity_name: Name of the UIButton entity.

        Returns:
            ActionResult confirming the click was processed, or failure if the
            button was not found or not clickable.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("UI system not ready")
        clicked = runtime.click_ui_entity(
            entity_name,
            viewport_size=(float(runtime.width), float(runtime.height)),
        )
        return self.ok("UIButton clicked", {"entity": entity_name}) if clicked else self.fail("UIButton click failed")
