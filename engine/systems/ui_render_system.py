"""
engine/systems/ui_render_system.py - Render overlay para Canvas/Text/Button/Image.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pyray as rl

from engine.assets.asset_reference import normalize_asset_reference, reference_has_identity
from engine.assets.asset_service import AssetService
from engine.components.uibutton import UIButton
from engine.components.uiimage import UIImage
from engine.components.uitext import UIText
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.resources.texture_manager import TextureManager
from engine.systems.ui_system import UISystem


class UIRenderSystem:
    """Dibuja la UI en overlay usando el layout calculado por UISystem."""

    def __init__(self) -> None:
        self._texture_manager: TextureManager = TextureManager()
        self._project_service: Any = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None

    def set_project_service(self, project_service: Any) -> None:
        self._project_service = project_service
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def reset_project_resources(self) -> None:
        self._texture_manager.unload_all()

    def cleanup(self) -> None:
        self._texture_manager.unload_all()

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
        image = entity.get_component(UIImage)
        if image is not None and image.enabled:
            self._render_ui_image(layout, image)

        button = entity.get_component(UIButton)
        if button is not None and button.enabled:
            state = ui_system.get_button_state(entity)
            rect = self._button_rect(layout, button, state)
            rendered_sprite = False
            if button.has_sprite_visuals():
                visual = self._resolve_button_visual(button, state)
                rendered_sprite = self._draw_ui_sprite(
                    rect=rect,
                    asset_ref=visual["asset_ref"],
                    slice_name=visual["slice_name"],
                    tint=visual["tint"],
                    preserve_aspect=visual["preserve_aspect"],
                )
            if not rendered_sprite:
                color = self._resolve_button_color(button, state)
                rl.draw_rectangle_rounded(rect, 0.18, 8, rl.Color(*color))
                rl.draw_rectangle_rounded_lines_ex(rect, 0.18, 8, 2.0, rl.Color(18, 18, 18, 220))

            if button.label and entity.get_component(UIText) is None:
                self._draw_label(button.label, rect, 24, rl.WHITE, "center", False)

        text = entity.get_component(UIText)
        if text is not None and text.enabled:
            self._draw_label(
                text.text,
                rl.Rectangle(layout["x"], layout["y"], layout["width"], layout["height"]),
                text.font_size,
                rl.Color(*text.color),
                text.alignment,
                text.wrap,
            )

    def _render_ui_image(self, layout: dict[str, Any], image: UIImage) -> None:
        if not image.has_sprite():
            return
        rect = rl.Rectangle(float(layout["x"]), float(layout["y"]), float(layout["width"]), float(layout["height"]))
        self._draw_ui_sprite(
            rect=rect,
            asset_ref=image.sprite,
            slice_name=image.slice_name,
            tint=image.tint,
            preserve_aspect=image.preserve_aspect,
        )

    def _resolve_button_color(self, button: UIButton, state: dict[str, bool]) -> tuple[int, int, int, int]:
        if not button.interactable:
            return button.disabled_color
        if state.get("pressed"):
            return button.pressed_color
        if state.get("hovered"):
            return button.hover_color
        return button.normal_color

    def _resolve_button_visual(self, button: UIButton, state: dict[str, bool]) -> dict[str, Any]:
        disabled = not button.interactable
        hovered = bool(state.get("hovered"))
        pressed = bool(state.get("pressed"))
        if disabled:
            asset_ref = button.disabled_sprite if reference_has_identity(button.disabled_sprite) else button.normal_sprite
            return {
                "asset_ref": asset_ref,
                "slice_name": button.disabled_slice or button.normal_slice,
                "tint": button.image_tint if reference_has_identity(button.disabled_sprite) else self._dim_tint(button.image_tint),
                "preserve_aspect": button.preserve_aspect,
            }
        if pressed:
            return {
                "asset_ref": self._first_asset_reference(button.pressed_sprite, button.hover_sprite, button.normal_sprite),
                "slice_name": button.pressed_slice or button.hover_slice or button.normal_slice,
                "tint": button.image_tint,
                "preserve_aspect": button.preserve_aspect,
            }
        if hovered:
            return {
                "asset_ref": self._first_asset_reference(button.hover_sprite, button.normal_sprite),
                "slice_name": button.hover_slice or button.normal_slice,
                "tint": button.image_tint,
                "preserve_aspect": button.preserve_aspect,
            }
        return {
            "asset_ref": button.normal_sprite,
            "slice_name": button.normal_slice,
            "tint": button.image_tint,
            "preserve_aspect": button.preserve_aspect,
        }

    def _draw_ui_sprite(
        self,
        *,
        rect: rl.Rectangle,
        asset_ref: Any,
        slice_name: str,
        tint: tuple[int, int, int, int],
        preserve_aspect: bool,
    ) -> bool:
        if not reference_has_identity(asset_ref):
            return False
        texture = self._load_texture(asset_ref)
        if getattr(texture, "id", 0) == 0:
            return False
        source_rect = self._resolve_source_rect(asset_ref, slice_name, texture)
        dest_rect = rect
        if preserve_aspect:
            dest_rect = self._fit_rect_preserving_aspect(rect, abs(float(source_rect.width)), abs(float(source_rect.height)))
        rl.draw_texture_pro(texture, source_rect, dest_rect, rl.Vector2(0, 0), 0.0, rl.Color(*tint))
        return True

    def _load_texture(self, reference: Any) -> Any:
        normalized_ref = normalize_asset_reference(reference)
        if not reference_has_identity(normalized_ref):
            return SimpleNamespace(id=0, width=0, height=0)
        entry = self._asset_resolver.resolve_entry(normalized_ref) if self._asset_resolver is not None else None
        if entry is not None:
            return self._texture_manager.load(entry["absolute_path"], cache_key=entry.get("guid") or entry.get("path"))
        path = normalized_ref.get("path", "")
        if self._project_service is not None and path:
            path = self._project_service.resolve_path(path).as_posix()
        if not path:
            return SimpleNamespace(id=0, width=0, height=0)
        return self._texture_manager.load(path, cache_key=path)

    def _resolve_source_rect(self, asset_ref: Any, slice_name: str, texture: Any) -> rl.Rectangle:
        if self._asset_service is not None and slice_name:
            slice_rect = self._asset_service.get_slice_rect(asset_ref, slice_name)
            if slice_rect is not None:
                return rl.Rectangle(
                    float(slice_rect["x"]),
                    float(slice_rect["y"]),
                    float(slice_rect["width"]),
                    float(slice_rect["height"]),
                )
        return rl.Rectangle(0.0, 0.0, float(texture.width), float(texture.height))

    def _fit_rect_preserving_aspect(self, outer: rl.Rectangle, source_width: float, source_height: float) -> rl.Rectangle:
        if source_width <= 0.0 or source_height <= 0.0 or outer.width <= 0.0 or outer.height <= 0.0:
            return outer
        scale = min(outer.width / source_width, outer.height / source_height)
        width = source_width * scale
        height = source_height * scale
        return rl.Rectangle(
            outer.x + (outer.width - width) * 0.5,
            outer.y + (outer.height - height) * 0.5,
            width,
            height,
        )

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

    def _first_asset_reference(self, *references: Any) -> dict[str, str]:
        for reference in references:
            normalized = normalize_asset_reference(reference)
            if reference_has_identity(normalized):
                return normalized
        return normalize_asset_reference(None)

    def _dim_tint(self, tint: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return (
            max(0, min(255, int(tint[0] * 0.7))),
            max(0, min(255, int(tint[1] * 0.7))),
            max(0, min(255, int(tint[2] * 0.7))),
            max(0, min(255, int(tint[3] * 0.86))),
        )
