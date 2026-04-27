"""
engine/editor/sprite_editor_modal.py - Modal reutilizable para grid slicing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import pyray as rl
from engine.assets.asset_service import AssetService
from engine.resources.texture_manager import TextureManager


class SpriteEditorModal:
    BG_OVERLAY = rl.Color(0, 0, 0, 170)
    PANEL_BG = rl.Color(38, 38, 38, 255)
    CARD_BG = rl.Color(48, 48, 48, 255)
    BORDER = rl.Color(20, 20, 20, 255)
    TEXT = rl.Color(220, 220, 220, 255)
    DIM = rl.Color(150, 150, 150, 255)
    ACCENT = rl.Color(58, 121, 187, 255)

    def __init__(self) -> None:
        self._project_service: Any = None
        self._asset_service: Optional[AssetService] = None
        self._texture_manager = TextureManager()

        self.is_open: bool = False
        self.asset_path: str = ""
        self.import_mode: str = "grid"
        self.cell_width: int = 32
        self.cell_height: int = 32
        self.margin: int = 0
        self.spacing: int = 0
        self.pivot_x: float = 0.5
        self.pivot_y: float = 0.5
        self.naming_prefix: str = ""
        self.last_saved_metadata: Optional[dict] = None
        self.status_message: str = ""
        self.manual_slices: list[dict] = []
        self._manual_drag_start: Optional[tuple[int, int]] = None
        self._manual_drag_current: Optional[tuple[int, int]] = None

    def set_project_service(self, project_service: Any) -> None:
        self._project_service = project_service
        self._asset_service = AssetService(project_service) if project_service is not None else None

    def set_history_manager(self, history_manager: Any) -> None:
        if self._asset_service is not None:
            self._asset_service.set_history_manager(history_manager)

    def open(self, asset_path: str) -> bool:
        if self._asset_service is None or not asset_path:
            return False
        self.asset_path = asset_path
        metadata = self._asset_service.get_sprite_metadata(asset_path)
        image_width, image_height = self._asset_service.get_sprite_image_size(asset_path)
        grid = metadata.get("grid", {})
        self.import_mode = str(metadata.get("import_mode", "grid") or "grid")
        self.cell_width = max(1, int(grid.get("cell_width") or image_width or 32))
        self.cell_height = max(1, int(grid.get("cell_height") or image_height or 32))
        self.margin = max(0, int(grid.get("margin") or 0))
        self.spacing = max(0, int(grid.get("spacing") or 0))
        self.pivot_x = float(grid.get("pivot_x", 0.5))
        self.pivot_y = float(grid.get("pivot_y", 0.5))
        self.naming_prefix = str(grid.get("naming_prefix") or Path(asset_path).stem)
        self.last_saved_metadata = metadata if metadata.get("slices") else None
        self.manual_slices = [
            {
                "name": str(item.get("name", "")),
                "x": int(item.get("x", 0)),
                "y": int(item.get("y", 0)),
                "width": int(item.get("width", 1)),
                "height": int(item.get("height", 1)),
                "pivot_x": float(item.get("pivot_x", self.pivot_x)),
                "pivot_y": float(item.get("pivot_y", self.pivot_y)),
            }
            for item in metadata.get("slices", [])
        ] if self.import_mode == "manual" else []
        self._manual_drag_start = None
        self._manual_drag_current = None
        self.status_message = ""
        self.is_open = True
        return True

    def close(self) -> None:
        self.is_open = False
        self.status_message = ""
        self._manual_drag_start = None
        self._manual_drag_current = None

    def save_grid_slices(self) -> Optional[dict]:
        if self._asset_service is None or not self.asset_path:
            return None
        metadata = self._asset_service.generate_sprite_grid_slices(
            self.asset_path,
            cell_width=max(1, int(self.cell_width)),
            cell_height=max(1, int(self.cell_height)),
            margin=max(0, int(self.margin)),
            spacing=max(0, int(self.spacing)),
            pivot_x=float(self.pivot_x),
            pivot_y=float(self.pivot_y),
            naming_prefix=self.naming_prefix.strip() or None,
        )
        self.last_saved_metadata = metadata
        self.status_message = f"{len(metadata.get('slices', []))} slices generated"
        return metadata

    def save_automatic_slices(self) -> Optional[dict]:
        if self._asset_service is None or not self.asset_path:
            return None
        metadata = self._asset_service.generate_sprite_auto_slices(
            self.asset_path,
            pivot_x=float(self.pivot_x),
            pivot_y=float(self.pivot_y),
            naming_prefix=self.naming_prefix.strip() or None,
        )
        self.import_mode = "automatic"
        self.last_saved_metadata = metadata
        self.status_message = f"{len(metadata.get('slices', []))} sprites detected"
        return metadata

    def save_manual_slices(self) -> Optional[dict]:
        if self._asset_service is None or not self.asset_path:
            return None
        metadata = self._asset_service.save_sprite_manual_slices(
            self.asset_path,
            self.manual_slices,
            pivot_x=float(self.pivot_x),
            pivot_y=float(self.pivot_y),
            naming_prefix=self.naming_prefix.strip() or None,
        )
        self.import_mode = "manual"
        self.last_saved_metadata = metadata
        self.status_message = f"{len(metadata.get('slices', []))} manual slices saved"
        return metadata

    def import_image(self, source_path: str, target_folder: str = "") -> Optional[str]:
        if self._asset_service is None or self._project_service is None:
            return None
        imported_path = self._asset_service.import_sprite_asset(source_path, target_folder=target_folder)
        self.open(imported_path)
        return imported_path

    def browse_and_import_image(self) -> Optional[str]:
        if self._project_service is None:
            return None
        try:
            import tkinter
            from tkinter import filedialog

            root = tkinter.Tk()
            root.withdraw()
            source_path = filedialog.askopenfilename(
                initialdir=os.getcwd(),
                title="Import Sprite Sheet",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")],
            )
            root.destroy()
            if not source_path:
                return None
            return self.import_image(source_path)
        except Exception as exc:
            self.status_message = f"Import failed: {exc}"
            return None

    def render(self, screen_width: int, screen_height: int) -> None:
        if not self.is_open:
            return

        rl.draw_rectangle(0, 0, screen_width, screen_height, self.BG_OVERLAY)
        modal = rl.Rectangle(screen_width / 2 - 360, screen_height / 2 - 220, 720, 440)
        rl.draw_rectangle_rec(modal, self.PANEL_BG)
        rl.draw_rectangle_lines_ex(modal, 1, self.BORDER)

        rl.draw_text("Sprite Editor", int(modal.x + 16), int(modal.y + 14), 18, self.TEXT)
        rl.draw_text(self.asset_path or "No asset selected", int(modal.x + 16), int(modal.y + 40), 11, self.DIM)

        import_rect = rl.Rectangle(modal.x + modal.width - 106, modal.y + 12, 90, 24)
        if rl.gui_button(import_rect, "Import"):
            self.browse_and_import_image()

        if self._asset_service is None or self._project_service is None or not self.asset_path:
            rl.draw_text("Asset service unavailable.", int(modal.x + 16), int(modal.y + 68), 11, self.DIM)
            close_rect = rl.Rectangle(modal.x + modal.width - 96, modal.y + modal.height - 36, 80, 22)
            if rl.gui_button(close_rect, "Close"):
                self.close()
            return

        image_width, image_height = self._asset_service.get_sprite_image_size(self.asset_path)
        rl.draw_text(f"Image: {image_width}x{image_height}", int(modal.x + 16), int(modal.y + 68), 11, self.TEXT)
        mode_grid_rect = rl.Rectangle(modal.x + 118, modal.y + 62, 70, 24)
        mode_auto_rect = rl.Rectangle(modal.x + 194, modal.y + 62, 88, 24)
        mode_manual_rect = rl.Rectangle(modal.x + 288, modal.y + 62, 80, 24)
        if rl.gui_button(mode_grid_rect, f"{'* ' if self.import_mode == 'grid' else ''}Grid"):
            self.import_mode = "grid"
        if rl.gui_button(mode_auto_rect, f"{'* ' if self.import_mode == 'automatic' else ''}Automatic"):
            self.import_mode = "automatic"
        if rl.gui_button(mode_manual_rect, f"{'* ' if self.import_mode == 'manual' else ''}Manual"):
            self.import_mode = "manual"

        left = rl.Rectangle(modal.x + 16, modal.y + 96, 264, 286)
        right = rl.Rectangle(modal.x + 296, modal.y + 96, 408, 286)
        rl.draw_rectangle_rec(left, self.CARD_BG)
        rl.draw_rectangle_rec(right, self.CARD_BG)
        rl.draw_rectangle_lines_ex(left, 1, self.BORDER)
        rl.draw_rectangle_lines_ex(right, 1, self.BORDER)

        current_y = int(left.y + 12)
        if self.import_mode == "grid":
            current_y = self._draw_int_stepper(left, current_y, "Cell Width", self.cell_width, lambda v: setattr(self, "cell_width", max(1, v)))
            current_y = self._draw_int_stepper(left, current_y, "Cell Height", self.cell_height, lambda v: setattr(self, "cell_height", max(1, v)))
            current_y = self._draw_int_stepper(left, current_y, "Margin", self.margin, lambda v: setattr(self, "margin", max(0, v)))
            current_y = self._draw_int_stepper(left, current_y, "Spacing", self.spacing, lambda v: setattr(self, "spacing", max(0, v)))
        elif self.import_mode == "automatic":
            rl.draw_text("Automatic detects", int(left.x + 12), current_y + 4, 10, self.TEXT)
            current_y += 18
            rl.draw_text("opaque regions like", int(left.x + 12), current_y + 4, 10, self.TEXT)
            current_y += 18
            rl.draw_text("Unity auto slicing.", int(left.x + 12), current_y + 4, 10, self.TEXT)
            current_y += 24
        else:
            rl.draw_text("Draw rectangles over", int(left.x + 12), current_y + 4, 10, self.TEXT)
            current_y += 18
            rl.draw_text("the preview with the", int(left.x + 12), current_y + 4, 10, self.TEXT)
            current_y += 18
            rl.draw_text("left mouse button.", int(left.x + 12), current_y + 4, 10, self.TEXT)
            current_y += 24
        current_y = self._draw_float_stepper(left, current_y, "Pivot X", self.pivot_x, lambda v: setattr(self, "pivot_x", max(0.0, min(1.0, v))))
        current_y = self._draw_float_stepper(left, current_y, "Pivot Y", self.pivot_y, lambda v: setattr(self, "pivot_y", max(0.0, min(1.0, v))))

        rl.draw_text("Name Prefix", int(left.x + 12), current_y + 5, 10, self.TEXT)
        prefix_rect = rl.Rectangle(left.x + 110, current_y, 130, 22)
        rl.draw_rectangle_rec(prefix_rect, rl.Color(32, 32, 32, 255))
        rl.draw_text(self.naming_prefix or "-", int(prefix_rect.x + 6), int(prefix_rect.y + 6), 10, self.TEXT)
        prev_prefix = rl.Rectangle(left.x + 244, current_y, 22, 22)
        next_prefix = rl.Rectangle(left.x + 270, current_y, 22, 22)
        if rl.gui_button(prev_prefix, "<"):
            self.naming_prefix = Path(self.asset_path).stem
        if rl.gui_button(next_prefix, "R"):
            self.naming_prefix = f"{Path(self.asset_path).stem}_slice"

        if self.import_mode == "manual":
            clear_rect = rl.Rectangle(left.x + 12, current_y + 32, 88, 22)
            undo_rect = rl.Rectangle(left.x + 106, current_y + 32, 88, 22)
            if rl.gui_button(clear_rect, "Clear All"):
                self.manual_slices = []
            if rl.gui_button(undo_rect, "Undo Rect"):
                if self.manual_slices:
                    self.manual_slices.pop()
            current_y += 60

        preview = self._build_preview_metadata()
        texture = self._texture_manager.load(self._project_service.resolve_path(self.asset_path).as_posix())
        preview_rect = rl.Rectangle(right.x + 12, right.y + 12, right.width - 24, 180)
        rl.draw_rectangle_rec(preview_rect, rl.Color(30, 30, 30, 255))
        rl.draw_rectangle_lines_ex(preview_rect, 1, self.BORDER)
        if texture.id != 0:
            scale = min(preview_rect.width / max(1, texture.width), preview_rect.height / max(1, texture.height))
            dest_w = texture.width * scale
            dest_h = texture.height * scale
            dest = rl.Rectangle(preview_rect.x + (preview_rect.width - dest_w) / 2, preview_rect.y + (preview_rect.height - dest_h) / 2, dest_w, dest_h)
            rl.draw_texture_pro(texture, rl.Rectangle(0, 0, texture.width, texture.height), dest, rl.Vector2(0, 0), 0.0, rl.WHITE)
            self._handle_manual_input(dest, texture.width, texture.height)
            self._draw_slice_overlay(dest, texture.width, texture.height, preview.get("slices", []))

        rl.draw_text(f"Preview slices: {len(preview.get('slices', []))}", int(right.x + 12), int(right.y + 206), 11, self.TEXT)
        for index, slice_info in enumerate(preview.get("slices", [])[:4]):
            rl.draw_text(
                f"{slice_info['name']} [{slice_info['x']},{slice_info['y']},{slice_info['width']}x{slice_info['height']}]",
                int(right.x + 12),
                int(right.y + 228 + index * 16),
                10,
                self.DIM,
            )

        if self.status_message:
            rl.draw_text(self.status_message, int(modal.x + 16), int(modal.y + modal.height - 32), 10, self.ACCENT)

        cancel_rect = rl.Rectangle(modal.x + modal.width - 266, modal.y + modal.height - 36, 80, 22)
        save_rect = rl.Rectangle(modal.x + modal.width - 178, modal.y + modal.height - 36, 80, 22)
        close_rect = rl.Rectangle(modal.x + modal.width - 90, modal.y + modal.height - 36, 74, 22)
        if rl.gui_button(cancel_rect, "Cancel"):
            self.close()
        if rl.gui_button(save_rect, "Generate"):
            if self.import_mode == "automatic":
                self.save_automatic_slices()
            elif self.import_mode == "manual":
                self.save_manual_slices()
            else:
                self.save_grid_slices()
        if rl.gui_button(close_rect, "Close"):
            self.close()

    def _build_preview_metadata(self) -> dict:
        if self._asset_service is None or not self.asset_path:
            return {"slices": []}
        width, height = self._asset_service.get_sprite_image_size(self.asset_path)
        if width <= 0 or height <= 0:
            return {"slices": []}
        try:
            if self.import_mode == "automatic":
                return {"slices": self._asset_service.preview_auto_slices(
                    self.asset_path,
                    pivot_x=float(self.pivot_x),
                    pivot_y=float(self.pivot_y),
                    naming_prefix=self.naming_prefix.strip() or None,
                )}
            if self.import_mode == "manual":
                return {"slices": self._normalized_manual_slices()}
            return self._preview_grid(width, height)
        except Exception:
            return {"slices": []}

    def _preview_grid(self, image_width: int, image_height: int) -> dict:
        slices = []
        prefix = self.naming_prefix.strip() or Path(self.asset_path).stem or "slice"
        index = 0
        y = max(0, int(self.margin))
        cell_width = max(1, int(self.cell_width))
        cell_height = max(1, int(self.cell_height))
        spacing = max(0, int(self.spacing))
        margin = max(0, int(self.margin))
        while y + cell_height <= image_height - margin:
            x = margin
            while x + cell_width <= image_width - margin:
                slices.append(
                    {
                        "name": f"{prefix}_{index}",
                        "x": x,
                        "y": y,
                        "width": cell_width,
                        "height": cell_height,
                    }
                )
                index += 1
                x += cell_width + spacing
            y += cell_height + spacing
        return {"slices": slices}

    def _normalized_manual_slices(self) -> list[dict]:
        prefix = self.naming_prefix.strip() or Path(self.asset_path).stem or "slice"
        normalized = []
        for index, item in enumerate(self.manual_slices):
            normalized.append(
                {
                    "name": str(item.get("name") or f"{prefix}_{index}"),
                    "x": int(item.get("x", 0)),
                    "y": int(item.get("y", 0)),
                    "width": max(1, int(item.get("width", 1))),
                    "height": max(1, int(item.get("height", 1))),
                    "pivot_x": float(item.get("pivot_x", self.pivot_x)),
                    "pivot_y": float(item.get("pivot_y", self.pivot_y)),
                }
            )
        return normalized

    def _handle_manual_input(self, dest_rect: rl.Rectangle, image_width: int, image_height: int) -> None:
        if self.import_mode != "manual":
            self._manual_drag_start = None
            self._manual_drag_current = None
            return
        mouse = rl.get_mouse_position()
        inside = rl.check_collision_point_rec(mouse, dest_rect)
        if inside and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            point = self._screen_to_image_point(mouse, dest_rect, image_width, image_height)
            if point is not None:
                self._manual_drag_start = point
                self._manual_drag_current = point
        elif self._manual_drag_start is not None and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
            point = self._screen_to_image_point(mouse, dest_rect, image_width, image_height)
            if point is not None:
                self._manual_drag_current = point
        elif self._manual_drag_start is not None and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            point = self._screen_to_image_point(mouse, dest_rect, image_width, image_height) or self._manual_drag_current
            if point is not None:
                self._manual_drag_current = point
                slice_rect = self._drag_rect_to_slice(self._manual_drag_start, self._manual_drag_current)
                if slice_rect is not None:
                    prefix = self.naming_prefix.strip() or Path(self.asset_path).stem or "slice"
                    slice_rect["name"] = f"{prefix}_{len(self.manual_slices)}"
                    slice_rect["pivot_x"] = self.pivot_x
                    slice_rect["pivot_y"] = self.pivot_y
                    self.manual_slices.append(slice_rect)
            self._manual_drag_start = None
            self._manual_drag_current = None

    def _screen_to_image_point(
        self,
        mouse: rl.Vector2,
        dest_rect: rl.Rectangle,
        image_width: int,
        image_height: int,
    ) -> Optional[tuple[int, int]]:
        if image_width <= 0 or image_height <= 0 or not rl.check_collision_point_rec(mouse, dest_rect):
            return None
        rel_x = (mouse.x - dest_rect.x) / max(1.0, dest_rect.width)
        rel_y = (mouse.y - dest_rect.y) / max(1.0, dest_rect.height)
        px = max(0, min(image_width - 1, int(rel_x * image_width)))
        py = max(0, min(image_height - 1, int(rel_y * image_height)))
        return (px, py)

    def _drag_rect_to_slice(self, start: tuple[int, int], end: tuple[int, int]) -> Optional[dict]:
        min_x = min(start[0], end[0])
        min_y = min(start[1], end[1])
        max_x = max(start[0], end[0])
        max_y = max(start[1], end[1])
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        if width <= 1 or height <= 1:
            return None
        return {"x": min_x, "y": min_y, "width": width, "height": height}

    def _draw_slice_overlay(self, dest_rect: rl.Rectangle, image_width: int, image_height: int, slices: list[dict]) -> None:
        if image_width <= 0 or image_height <= 0:
            return
        scale_x = dest_rect.width / max(1, image_width)
        scale_y = dest_rect.height / max(1, image_height)
        for slice_info in slices:
            rect = rl.Rectangle(
                dest_rect.x + float(slice_info.get("x", 0)) * scale_x,
                dest_rect.y + float(slice_info.get("y", 0)) * scale_y,
                float(slice_info.get("width", 1)) * scale_x,
                float(slice_info.get("height", 1)) * scale_y,
            )
            rl.draw_rectangle_lines_ex(rect, 1, self.ACCENT)
        if self._manual_drag_start is not None and self._manual_drag_current is not None:
            temp = self._drag_rect_to_slice(self._manual_drag_start, self._manual_drag_current)
            if temp is not None:
                rect = rl.Rectangle(
                    dest_rect.x + temp["x"] * scale_x,
                    dest_rect.y + temp["y"] * scale_y,
                    temp["width"] * scale_x,
                    temp["height"] * scale_y,
                )
                rl.draw_rectangle_lines_ex(rect, 1, rl.YELLOW)

    def _draw_int_stepper(self, rect: rl.Rectangle, y: int, label: str, value: int, setter: Any) -> int:
        rl.draw_text(label, int(rect.x + 12), y + 5, 10, self.TEXT)
        value_rect = rl.Rectangle(rect.x + 110, y, 58, 22)
        minus_rect = rl.Rectangle(rect.x + 174, y, 22, 22)
        plus_rect = rl.Rectangle(rect.x + 200, y, 22, 22)
        rl.draw_rectangle_rec(value_rect, rl.Color(32, 32, 32, 255))
        rl.draw_text(str(value), int(value_rect.x + 6), int(value_rect.y + 6), 10, self.TEXT)
        if rl.gui_button(minus_rect, "-"):
            setter(value - 1)
        if rl.gui_button(plus_rect, "+"):
            setter(value + 1)
        return y + 28

    def _draw_float_stepper(self, rect: rl.Rectangle, y: int, label: str, value: float, setter: Any) -> int:
        rl.draw_text(label, int(rect.x + 12), y + 5, 10, self.TEXT)
        value_rect = rl.Rectangle(rect.x + 110, y, 58, 22)
        minus_rect = rl.Rectangle(rect.x + 174, y, 22, 22)
        plus_rect = rl.Rectangle(rect.x + 200, y, 22, 22)
        rl.draw_rectangle_rec(value_rect, rl.Color(32, 32, 32, 255))
        rl.draw_text(f"{value:.1f}", int(value_rect.x + 6), int(value_rect.y + 6), 10, self.TEXT)
        if rl.gui_button(minus_rect, "-"):
            setter(round(value - 0.1, 2))
        if rl.gui_button(plus_rect, "+"):
            setter(round(value + 0.1, 2))
        return y + 28

    def cleanup(self) -> None:
        self._texture_manager.unload_all()
