"""
engine/systems/ui_render_system.py - Render overlay para Canvas/Text/Button/Image.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pyray as rl
from engine.assets.asset_reference import normalize_asset_reference, reference_has_identity
from engine.assets.asset_service import AssetService
from engine.components.colorrect import ColorRect
from engine.components.rich_text_label import RichTextLabel
from engine.components.uibutton import UIButton
from engine.components.uicheckbox import CheckBox
from engine.components.uiimage import UIImage
from engine.components.uilabel import Label
from engine.components.uilineedit import LineEdit
from engine.components.uipanel import UIPanel
from engine.components.ui_popup import UIPopup, UIPopupMenu, UIWindow
from engine.components.uiprogressbar import ProgressBar
from engine.components.uislider import Slider
from engine.components.uispinbox import SpinBox
from engine.components.uitext import UIText
from engine.components.uitextedit import TextEdit
from engine.components.ui_tree import UITree
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.resources.texture_manager import TextureManager
from engine.systems.ui_system import UISystem
from engine.systems.ui_popup_system import UIPopupSystem


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

        panel = entity.get_component(UIPanel)
        if panel is not None and panel.enabled:
            self._render_ui_panel(layout, panel)

        color_rect = entity.get_component(ColorRect)
        if color_rect is not None and color_rect.enabled:
            self._render_color_rect(layout, color_rect)

        line_edit = entity.get_component(LineEdit)
        if line_edit is not None and line_edit.enabled:
            self._render_line_edit(layout, line_edit)

        slider = entity.get_component(Slider)
        if slider is not None and slider.enabled:
            self._render_slider(layout, slider)

        progress = entity.get_component(ProgressBar)
        if progress is not None and progress.enabled:
            self._render_progress_bar(layout, progress)

        checkbox = entity.get_component(CheckBox)
        if checkbox is not None and checkbox.enabled:
            self._render_checkbox(layout, checkbox)

        spinbox = entity.get_component(SpinBox)
        if spinbox is not None and spinbox.enabled:
            self._render_spinbox(layout, spinbox)

        label = entity.get_component(Label)
        if label is not None and label.enabled:
            self._render_label(layout, label)

        text_edit = entity.get_component(TextEdit)
        if text_edit is not None and text_edit.enabled:
            self._render_text_edit(layout, text_edit)

        rich_label = entity.get_component(RichTextLabel)
        if rich_label is not None and rich_label.enabled:
            self._render_rich_text_label(layout, rich_label)

        popup = entity.get_component(UIPopup)
        if popup is not None and popup.visible:
            self._render_popup(layout, popup)

        popup_menu = entity.get_component(UIPopupMenu)
        if popup_menu is not None and popup_menu.visible:
            self._render_popup_menu(layout, popup_menu)

        window = entity.get_component(UIWindow)
        if window is not None and window.visible:
            self._render_window(layout, window)

        tree = entity.get_component(UITree)
        if tree is not None and tree.enabled:
            self._render_ui_tree(layout, tree)

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

    # ── new UI controls ──

    def _render_ui_panel(self, layout: dict[str, Any], panel: UIPanel) -> None:
        rect = rl.Rectangle(float(layout["x"]), float(layout["y"]), float(layout["width"]), float(layout["height"]))
        if panel.corner_radius > 0:
            rl.draw_rectangle_rounded(rect, max(0.0, min(1.0, panel.corner_radius / min(rect.width, rect.height))), 8, rl.Color(*panel.color))
            if panel.border_width > 0:
                rl.draw_rectangle_rounded_lines(rect, max(0.0, min(1.0, panel.corner_radius / min(rect.width, rect.height))), 8, float(panel.border_width), rl.Color(*panel.border_color))
        else:
            rl.draw_rectangle_rec(rect, rl.Color(*panel.color))
            if panel.border_width > 0:
                rl.draw_rectangle_lines_ex(rect, float(panel.border_width), rl.Color(*panel.border_color))

    def _render_color_rect(self, layout: dict[str, Any], color_rect: ColorRect) -> None:
        rect = rl.Rectangle(float(layout["x"]), float(layout["y"]), float(layout["width"]), float(layout["height"]))
        rl.draw_rectangle_rec(rect, rl.Color(*color_rect.color))

    def _render_line_edit(self, layout: dict[str, Any], line_edit: LineEdit) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        # Background
        bg = rl.Color(30, 30, 30, 255) if line_edit.focused else rl.Color(20, 20, 20, 255)
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), bg)
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 2.0, rl.Color(80, 200, 255, 255) if line_edit.focused else rl.Color(60, 60, 60, 255))
        # Text or placeholder
        display = line_edit.text
        color = rl.Color(*line_edit.color)
        if not display and line_edit.placeholder:
            display = line_edit.placeholder
            color = rl.Color(*line_edit.placeholder_color)
        if line_edit.secret and line_edit.text:
            display = "*" * len(line_edit.text)
        text_x = x + 6
        text_y = y + max(0.0, (h - line_edit.font_size) * 0.5)
        rl.draw_text(display, int(text_x), int(text_y), line_edit.font_size, color)
        # Cursor
        if line_edit.focused:
            cursor_x = text_x + rl.measure_text(display[:line_edit.cursor_position], line_edit.font_size)
            rl.draw_rectangle_rec(rl.Rectangle(cursor_x, text_y, 2.0, float(line_edit.font_size)), rl.Color(*line_edit.color))

    def _render_slider(self, layout: dict[str, Any], slider: Slider) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        is_h = slider.horizontal
        # Track
        track = rl.Rectangle(x, y + h * 0.4, w, h * 0.2) if is_h else rl.Rectangle(x + w * 0.4, y, w * 0.2, h)
        rl.draw_rectangle_rec(track, rl.Color(70, 70, 70, 255))
        # Thumb
        ratio = slider.ratio
        thumb_size = min(w, h) * 0.8
        if is_h:
            thumb = rl.Rectangle(x + (w - thumb_size) * ratio, y + (h - thumb_size) * 0.5, thumb_size, thumb_size)
        else:
            thumb = rl.Rectangle(x + (w - thumb_size) * 0.5, y + (h - thumb_size) * (1.0 - ratio), thumb_size, thumb_size)
        rl.draw_rectangle_rec(thumb, rl.Color(90, 170, 255, 255))
        rl.draw_rectangle_lines_ex(thumb, 1.0, rl.Color(40, 120, 220, 255))

    def _render_progress_bar(self, layout: dict[str, Any], progress: ProgressBar) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        is_h = progress.horizontal
        # Background
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), rl.Color(*progress.bg_color))
        # Fill
        ratio = progress.ratio
        fill_rect = rl.Rectangle(x, y, w * ratio, h) if is_h else rl.Rectangle(x, y + h * (1.0 - ratio), w, h * ratio)
        rl.draw_rectangle_rec(fill_rect, rl.Color(*progress.fill_color))
        # Border
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.0, rl.Color(100, 100, 100, 255))
        # Percent text
        if progress.percent_visible:
            pct_text = f"{int(progress.percent)}%"
            text_w = rl.measure_text(pct_text, 16)
            rl.draw_text(pct_text, int(x + (w - text_w) * 0.5), int(y + (h - 16) * 0.5), 16, rl.WHITE)

    def _render_checkbox(self, layout: dict[str, Any], checkbox: CheckBox) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        h = float(layout["height"])
        box_size = min(h, 20.0)
        box = rl.Rectangle(x, y + (h - box_size) * 0.5, box_size, box_size)
        # Box background
        rl.draw_rectangle_rec(box, rl.Color(50, 50, 50, 255))
        rl.draw_rectangle_lines_ex(box, 2.0, rl.Color(150, 150, 150, 255))
        # Checkmark
        if checkbox.checked:
            pad = 3
            cx = box.x + pad
            cy = box.y + pad
            cw = box.width - pad * 2
            ch = box.height - pad * 2
            rl.draw_line(int(cx), int(cy + ch * 0.5), int(cx + cw * 0.4), int(cy + ch), rl.Color(0, 200, 0, 255))
            rl.draw_line(int(cx + cw * 0.4), int(cy + ch), int(cx + cw), int(cy), rl.Color(0, 200, 0, 255))
        # Label
        if checkbox.text:
            label_x = x + box_size + 6
            label_y = y + max(0.0, (h - 16) * 0.5)
            rl.draw_text(checkbox.text, int(label_x), int(label_y), 16, rl.WHITE)

    def _render_spinbox(self, layout: dict[str, Any], spinbox: SpinBox) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        arrow_w = min(24.0, w * 0.3)
        # Background
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), rl.Color(30, 30, 30, 255))
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.0, rl.Color(80, 80, 80, 255))
        # Value
        val_text = spinbox.display_text
        text_w = rl.measure_text(val_text, 16)
        rl.draw_text(val_text, int(x + (w - text_w) * 0.5), int(y + (h - 16) * 0.5), 16, rl.WHITE)
        # Up arrow
        up_rect = rl.Rectangle(x + w - arrow_w, y, arrow_w, h * 0.5)
        rl.draw_rectangle_rec(up_rect, rl.Color(60, 60, 60, 255))
        rl.draw_rectangle_lines_ex(up_rect, 1.0, rl.Color(100, 100, 100, 255))
        rl.draw_text("+", int(up_rect.x + up_rect.width * 0.3), int(up_rect.y), 14, rl.WHITE)
        # Down arrow
        down_rect = rl.Rectangle(x + w - arrow_w, y + h * 0.5, arrow_w, h * 0.5)
        rl.draw_rectangle_rec(down_rect, rl.Color(60, 60, 60, 255))
        rl.draw_rectangle_lines_ex(down_rect, 1.0, rl.Color(100, 100, 100, 255))
        rl.draw_text("-", int(down_rect.x + down_rect.width * 0.3), int(down_rect.y), 14, rl.WHITE)

    def _render_label(self, layout: dict[str, Any], label: Label) -> None:
        self._draw_label(
            label.text,
            rl.Rectangle(float(layout["x"]), float(layout["y"]), float(layout["width"]), float(layout["height"])),
            label.font_size,
            rl.Color(*label.color),
            label.alignment,
            label.autowrap,
        )

    def _render_text_edit(self, layout: dict[str, Any], text_edit: TextEdit) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        # Background
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), rl.Color(20, 20, 20, 255))
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.0, rl.Color(80, 80, 80, 255))
        # Start scissor to clip text
        rl.begin_scissor_mode(int(x), int(y), int(w), int(h))
        # Draw text lines
        lines = text_edit.text.split("\n")
        line_h = text_edit.font_size + 4
        offset = text_edit.scroll_y
        for i, line in enumerate(lines):
            ly = y + 4 + i * line_h - offset
            if ly + line_h < y or ly > y + h:
                continue
            rl.draw_text(line, int(x + 4), int(ly), text_edit.font_size, rl.Color(220, 220, 220, 255))
        # Cursor if focused
        if text_edit.focused:
            cy = y + 4 + text_edit.cursor_line * line_h - offset
            cursor_text = ""
            if text_edit.cursor_line < len(lines):
                cursor_text = lines[text_edit.cursor_line][:text_edit.cursor_column]
            cx = x + 4 + rl.measure_text(cursor_text, text_edit.font_size)
            rl.draw_rectangle_rec(rl.Rectangle(cx, cy, 2.0, float(text_edit.font_size)), rl.Color(255, 255, 255, 255))
        rl.end_scissor_mode()

    # ── UI Tree ──

    def _render_ui_tree(self, layout: dict[str, Any], tree: UITree) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), rl.Color(28, 28, 28, 255))
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.0, rl.Color(60, 60, 60, 255))

        row_h = 24
        indent_w = 20
        col_widths = [max(100, (w - tree.columns * 10) / tree.columns) for _ in range(max(1, tree.columns))]

        def _flatten(item: UITreeItem, depth: int = 0) -> list[tuple[UITreeItem, int]]:
            result: list[tuple[UITreeItem, int]] = [(item, depth)]
            if item.expanded and item.expandable:
                for child in item.children:
                    result.extend(_flatten(child, depth + 1))
            return result

        items: list[tuple[UITreeItem, int]] = []
        if tree.hide_root:
            for child in tree.root.children:
                items.extend(_flatten(child, 0))
        else:
            items = _flatten(tree.root, 0)

        # Clipping
        rl.begin_scissor_mode(int(x), int(y), int(w), int(h))

        visible_start = int(tree._scroll_y / row_h)
        visible_count = int(h / row_h) + 2
        visible_items = items[max(0, visible_start):max(0, visible_start) + visible_count]

        for vi, (item, depth) in enumerate(visible_items):
            ry = y + vi * row_h - (tree._scroll_y % row_h)
            indent = depth * indent_w

            # Selection highlight
            if item.selected:
                rl.draw_rectangle_rec(
                    rl.Rectangle(x + indent, ry, w - indent, row_h),
                    rl.Color(50, 90, 180, 220),
                )

            # Expand arrow
            arrow_x = int(x + indent + 2)
            arrow_y = int(ry + row_h * 0.5)
            if item.expandable:
                arrow_text = "v" if item.expanded else ">"
                rl.draw_text(arrow_text, arrow_x, int(ry + 4), 14, rl.Color(180, 180, 180, 255))

            cell_x = int(x + indent + (16 if item.expandable else 4))

            # Checkbox
            if item.checkable:
                box_x = float(cell_x)
                box_y = ry + (row_h - 14) * 0.5
                box_size = 14.0
                rl.draw_rectangle_rec(rl.Rectangle(box_x, box_y, box_size, box_size), rl.Color(50, 50, 50, 255))
                rl.draw_rectangle_lines_ex(rl.Rectangle(box_x, box_y, box_size, box_size), 1.5, rl.Color(140, 140, 140, 255))
                if item.checked:
                    pad = 2
                    rl.draw_line(
                        int(box_x + pad), int(box_y + box_size * 0.5),
                        int(box_x + box_size * 0.4), int(box_y + box_size - pad),
                        rl.Color(0, 200, 0, 255),
                    )
                    rl.draw_line(
                        int(box_x + box_size * 0.4), int(box_y + box_size - pad),
                        int(box_x + box_size - pad), int(box_y + pad),
                        rl.Color(0, 200, 0, 255),
                    )
                cell_x += 18

            # Column text
            for col in range(tree.columns):
                col_x = float(x + col * col_widths[col]) if col > 0 else float(cell_x)
                col_text = item.text if col == 0 else str(item.metadata.get(f"col_{col}", ""))
                col_color = rl.Color(160, 160, 160, 255) if item.disabled else rl.Color(220, 220, 220, 255)
                rl.draw_text(col_text, int(col_x), int(ry + 4), 14, col_color)

        rl.end_scissor_mode()

        # Column headers
        if tree.column_titles:
            header_h = 22
            rl.draw_rectangle_rec(rl.Rectangle(x, y - header_h, w, header_h), rl.Color(40, 40, 40, 255))
            for ci, title in enumerate(tree.column_titles):
                rl.draw_text(title, int(x + ci * col_widths[ci] + 4), int(y - header_h + 4), 12, rl.Color(180, 180, 180, 255))

    # ── RichTextLabel ──

    def _render_rich_text_label(self, layout: dict[str, Any], rtl: RichTextLabel) -> None:
        import re
        from dataclasses import dataclass

        @dataclass
        class _StyledSpan:
            text: str
            bold: bool = False
            italic: bool = False
            color: tuple[int, int, int, int] | None = None
            font_size: int = 0

        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])

        original_text = rtl.text
        default_size = rtl.font_size
        default_color = rtl.default_color

        # Parse BBCode tags — match [b], [/b], [i], [/i], [color=#RRGGBB]...[/color], [font size=N]...[/font]
        raw_spans: list[_StyledSpan] = []
        bold_active = False
        italic_active = False
        pos = 0

        # Simple sequential parser
        i = 0
        text_len = len(original_text)
        current_plain = ""

        def _flush_plain() -> None:
            nonlocal current_plain
            if current_plain:
                raw_spans.append(_StyledSpan(
                    text=current_plain,
                    bold=bold_active,
                    italic=italic_active,
                    color=default_color,
                    font_size=default_size,
                ))
                current_plain = ""

        while i < text_len:
            c = original_text[i]
            if c == "[":
                # Check for tags
                if original_text[i:i + 3] == "[b]":
                    _flush_plain()
                    bold_active = True
                    i += 3
                    continue
                if original_text[i:i + 4] == "[/b]":
                    _flush_plain()
                    bold_active = False
                    i += 4
                    continue
                if original_text[i:i + 3] == "[i]":
                    _flush_plain()
                    italic_active = True
                    i += 3
                    continue
                if original_text[i:i + 4] == "[/i]":
                    _flush_plain()
                    italic_active = False
                    i += 4
                    continue

                # [color=#RRGGBB]...[/color]
                color_match = re.match(r"\[color=#([0-9a-fA-F]{6})\](.*?)\[/color\]", original_text[i:], re.DOTALL)
                if color_match:
                    _flush_plain()
                    hex_str = color_match.group(1)
                    inner_text = color_match.group(2)
                    rv = int(hex_str[0:2], 16)
                    gv = int(hex_str[2:4], 16)
                    bv = int(hex_str[4:6], 16)
                    raw_spans.append(_StyledSpan(
                        text=inner_text,
                        bold=bold_active,
                        italic=italic_active,
                        color=(rv, gv, bv, 255),
                        font_size=default_size,
                    ))
                    i += len(color_match.group(0))
                    continue

                # [font size=N]...[/font]
                size_match = re.match(r"\[font size=(\d+)\](.*?)\[/font\]", original_text[i:], re.DOTALL)
                if size_match:
                    _flush_plain()
                    fs = max(8, int(size_match.group(1)))
                    inner_text = size_match.group(2)
                    raw_spans.append(_StyledSpan(
                        text=inner_text,
                        bold=bold_active,
                        italic=italic_active,
                        color=default_color,
                        font_size=fs,
                    ))
                    i += len(size_match.group(0))
                    continue

                current_plain += c
                i += 1
            else:
                current_plain += c
                i += 1

        _flush_plain()

        if not raw_spans and original_text:
            raw_spans = [_StyledSpan(text=original_text, color=default_color, font_size=default_size)]

        # Visible characters reveal effect
        total_chars = sum(len(s.text) for s in raw_spans)
        visible_count = total_chars
        if rtl.visible_characters > 0:
            visible_count = min(total_chars, rtl.visible_characters)
        elif rtl.percent_visible < 1.0:
            visible_count = int(total_chars * rtl.percent_visible)

        # Word-wrap into lines of styled spans
        wrapped_lines: list[list[_StyledSpan]] = []
        current_line: list[_StyledSpan] = []
        line_width = 0.0
        inner_pad = max(10.0, w - 8.0)
        char_consumed = 0

        for span in raw_spans:
            fs = span.font_size or default_size
            for char in span.text:
                if char_consumed >= visible_count:
                    break
                char_width = float(rl.measure_text(char, fs))

                if line_width + char_width > inner_pad and current_line:
                    wrapped_lines.append(current_line)
                    current_line = []
                    line_width = 0.0

                if current_line and (
                    current_line[-1].bold == span.bold
                    and current_line[-1].italic == span.italic
                    and current_line[-1].color == span.color
                    and current_line[-1].font_size == fs
                ):
                    current_line[-1].text += char
                else:
                    current_line.append(_StyledSpan(
                        text=char,
                        bold=span.bold,
                        italic=span.italic,
                        color=span.color,
                        font_size=fs,
                    ))
                line_width += char_width
                char_consumed += 1
            if char_consumed >= visible_count:
                break

        if current_line:
            wrapped_lines.append(current_line)

        # Max line height
        max_line_h = float(default_size + 4)
        for line in wrapped_lines:
            for span in line:
                max_line_h = max(max_line_h, float((span.font_size or default_size) + 4))

        total_height = max_line_h * len(wrapped_lines)
        rtl._max_scroll = max(0.0, total_height - h) if rtl.scroll_active else 0.0
        if rtl._scroll_offset > rtl._max_scroll:
            rtl._scroll_offset = rtl._max_scroll

        rl.begin_scissor_mode(int(x), int(y), int(w), int(h))

        draw_y = y + 4 - rtl._scroll_offset
        for line in wrapped_lines:
            draw_x = x + 4
            for span in line:
                if not span.text:
                    continue
                fs = span.font_size or default_size
                rv, gv, bv, av = span.color or default_color
                color = rl.Color(rv, gv, bv, av)
                rl.draw_text(span.text, int(draw_x), int(draw_y), fs, color)
                draw_x += float(rl.measure_text(span.text, fs))
            draw_y += max_line_h

        rl.end_scissor_mode()

    # ── Popup / PopupMenu / Window ──

    def _render_popup(self, layout: dict[str, Any], popup: UIPopup) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        if not popup.transparent_background:
            rl.draw_rectangle_rec(
                rl.Rectangle(x, y, w, h),
                rl.Color(*popup._overlay_color),
            )
        # Content area
        pad = 4.0
        rl.draw_rectangle_rec(
            rl.Rectangle(x + pad, y + pad, w - pad * 2, h - pad * 2),
            rl.Color(35, 35, 38, 255),
        )
        rl.draw_rectangle_lines_ex(
            rl.Rectangle(x + pad, y + pad, w - pad * 2, h - pad * 2),
            1.0,
            rl.Color(70, 70, 74, 255),
        )

    def _render_popup_menu(self, layout: dict[str, Any], popup_menu: UIPopupMenu) -> None:
        x = float(layout["x"]) + popup_menu.popup_position_x
        y = float(layout["y"]) + popup_menu.popup_position_y
        w = float(layout["width"])

        total_h = 0.0
        for item in popup_menu.items:
            total_h += 4.0 if item.get("separator") else popup_menu._item_height

        if total_h <= 0.0:
            total_h = popup_menu._item_height

        # Background
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, total_h), rl.Color(40, 40, 44, 255))
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, total_h), 1.0, rl.Color(80, 80, 84, 255))

        item_y = y
        for i, item in enumerate(popup_menu.items):
            if item.get("separator"):
                sep_y = item_y + 1.0
                rl.draw_line(int(x + 6), int(sep_y), int(x + w - 6), int(sep_y), rl.Color(100, 100, 104, 255))
                item_y += 4.0
                continue

            bg_color = rl.Color(55, 55, 60, 255)
            if i == popup_menu._hovered_index:
                bg_color = rl.Color(70, 120, 215, 255)
            rl.draw_rectangle_rec(rl.Rectangle(x, item_y, w, popup_menu._item_height), bg_color)

            item_text = item.get("text", "")
            text_x = int(x + 8)
            text_y = int(item_y + max(0.0, (popup_menu._item_height - 14) * 0.5))
            rl.draw_text(item_text, text_x, text_y, 14, rl.WHITE)
            item_y += popup_menu._item_height

    def _render_window(self, layout: dict[str, Any], window: UIWindow) -> None:
        x = float(layout["x"])
        y = float(layout["y"])
        w = float(layout["width"])
        h = float(layout["height"])
        tb_h = window._title_bar_height

        # Background
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), rl.Color(45, 45, 50, 250))
        rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.5, rl.Color(100, 100, 105, 255))

        # Title bar
        rl.draw_rectangle_rec(rl.Rectangle(x, y, w, tb_h), rl.Color(60, 60, 65, 255))
        title_text = window.title
        rl.draw_text(title_text, int(x + 6), int(y + max(0.0, (tb_h - 16) * 0.5)), 16, rl.Color(220, 220, 220, 255))

        # Close button
        cb_w = window._close_button_width
        cb_x = x + w - cb_w
        rl.draw_rectangle_rec(rl.Rectangle(cb_x, y, cb_w, tb_h), rl.Color(180, 45, 45, 255))
        close_text = "X"
        cw = rl.measure_text(close_text, 14)
        rl.draw_text(close_text, int(cb_x + (cb_w - cw) * 0.5), int(y + max(0.0, (tb_h - 14) * 0.5)), 14, rl.WHITE)

        # Content area border
        content_y = y + tb_h
        rl.draw_rectangle_lines_ex(
            rl.Rectangle(x, content_y, w, h - tb_h), 0.5, rl.Color(80, 80, 85, 255)
        )
