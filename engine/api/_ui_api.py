from __future__ import annotations

from typing import Dict, Optional, Union

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EntityData
from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.uibutton import UIButton
from engine.components.uiimage import UIImage
from engine.components.uipanel import UIPanel
from engine.components.uiscrollcontainer import UIScrollContainer
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

    def create_panel(
        self,
        entity_name: str,
        parent: str,
        color: Optional[tuple[int, int, int, int] | list[int]] = None,
        border_color: Optional[tuple[int, int, int, int] | list[int]] = None,
        border_width: int = 0,
        corner_radius: int = 0,
        texture_path: str = "",
        rect_transform: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
    ) -> ActionResult:
        """Crea un Panel UI con fondo de color o textura.

        Args:
            entity_name: Nombre de la entidad.
            parent: Entidad padre (normalmente un Canvas).
            color: Color de fondo RGBA (default [40, 40, 40, 255]).
            border_color: Color de borde RGBA (default [60, 60, 60, 255]).
            border_width: Ancho del borde en pixeles.
            corner_radius: Radio de esquinas redondeadas.
            texture_path: Ruta opcional a textura de fondo.
            rect_transform: Optional RectTransform overrides.

        Returns:
            ActionResult confirmando la creacion del panel.
        """
        self.ensure_edit_mode()
        result = self.create_ui_element(name=entity_name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.api.add_component(
            entity_name,
            "UIPanel",
            {
                "enabled": True,
                "color": list(color) if color is not None else [40, 40, 40, 255],
                "border_color": list(border_color) if border_color is not None else [60, 60, 60, 255],
                "border_width": border_width,
                "corner_radius": corner_radius,
                "texture_path": texture_path,
            },
        )
        return add_result if not add_result["success"] else self.ok("UIPanel created", {"entity": entity_name})

    def create_scroll_container(
        self,
        entity_name: str,
        parent: str,
        scroll_vertical: bool = True,
        scroll_horizontal: bool = False,
        content_width: float = 200.0,
        content_height: float = 200.0,
        rect_transform: Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]] = None,
    ) -> ActionResult:
        """Crea un ScrollContainer con contenido desplazable.

        Args:
            entity_name: Nombre de la entidad.
            parent: Entidad padre (normalmente un Canvas).
            scroll_vertical: Activar scroll vertical (default True).
            scroll_horizontal: Activar scroll horizontal (default False).
            content_width: Ancho del area de contenido.
            content_height: Alto del area de contenido.
            rect_transform: Optional RectTransform overrides.

        Returns:
            ActionResult confirmando la creacion del scroll container.
        """
        self.ensure_edit_mode()
        result = self.create_ui_element(name=entity_name, parent=parent, rect_transform=rect_transform)
        if not result["success"]:
            return result
        add_result = self.api.add_component(
            entity_name,
            "UIScrollContainer",
            {
                "enabled": True,
                "scroll_horizontal": scroll_horizontal,
                "scroll_vertical": scroll_vertical,
                "content_width": content_width,
                "content_height": content_height,
            },
        )
        return add_result if not add_result["success"] else self.ok("UIScrollContainer created", {"entity": entity_name})

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
        """List all UI-related entities (Canvas, RectTransform, UIText, UIButton, UIImage).

        Returns:
            List of EntityData dictionaries for all UI entities in the scene.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        nodes: list[EntityData] = []
        for entity in runtime.world.iter_all_entities():
            if any(entity.has_component(component) for component in (Canvas, RectTransform, UIText, UIButton, UIImage, UIPanel, UIScrollContainer)):
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

    def set_ui_focus(self, entity_name: str) -> ActionResult:
        """Establece el foco en una entidad UI.

        Args:
            entity_name: Nombre de la entidad UI.

        Returns:
            ActionResult con el ID de la entidad enfocada.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("UI system not ready")
        entity = self.require_entity(entity_name)
        entity_id = runtime.world.get_entity_id(entity)
        if entity_id is None:
            return self.fail(f"Entity '{entity_name}' has no ID")
        if not hasattr(runtime, "set_ui_focus"):
            return self.fail("UIFocusSystem not available")
        runtime.set_ui_focus(entity_id)
        return self.ok("UI focus set", {"entity_id": entity_id})

    def get_ui_focus(self) -> Optional[int]:
        """Retorna el ID de la entidad con foco, o None."""
        runtime = self.runtime
        if runtime is None:
            return None
        if not hasattr(runtime, "get_ui_focus"):
            return None
        return runtime.get_ui_focus()

    def clear_ui_focus(self) -> ActionResult:
        """Quita el foco de cualquier entidad UI."""
        runtime = self.runtime
        if runtime is None:
            return self.fail("UI system not ready")
        if not hasattr(runtime, "clear_ui_focus"):
            return self.fail("UIFocusSystem not available")
        runtime.clear_ui_focus()
        return self.ok("UI focus cleared")
