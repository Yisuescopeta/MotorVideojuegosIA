"""
engine/editor/project_panel.py - Explorador de assets del proyecto.

Mantiene la navegacion simple existente y añade busqueda, filtro, detalle de
asset y estado del pipeline de sprites apoyado en AssetService.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import pyray as rl

from engine.assets.asset_service import AssetService
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.render_safety import editor_scissor
from engine.project.project_service import ProjectService


class ProjectPanel:
    UNITY_BG_DARK = rl.Color(42, 42, 42, 255)
    UNITY_HEADER = rl.Color(56, 56, 56, 255)
    UNITY_BORDER = rl.Color(25, 25, 25, 255)
    UNITY_SELECTED = rl.Color(44, 93, 135, 255)
    UNITY_HOVER = rl.Color(60, 60, 60, 255)
    UNITY_TEXT = rl.Color(200, 200, 200, 255)
    UNITY_TEXT_DIM = rl.Color(128, 128, 128, 255)
    UNITY_TAB_LINE = rl.Color(58, 121, 187, 255)
    UNITY_FOLDER_ICON = rl.Color(220, 200, 100, 255)
    UNITY_IMAGE_ICON = rl.Color(118, 158, 223, 255)

    SIDEBAR_WIDTH: int = 180
    ITEM_HEIGHT: int = 18
    MENU_WIDTH: int = 140
    HEADER_HEIGHT: int = 52
    DETAIL_HEIGHT: int = 88
    FILTER_ORDER: tuple[str, ...] = ("all", "images", "scenes", "prefabs", "scripts")
    FILTER_LABELS: Dict[str, str] = {
        "all": "All",
        "images": "Images",
        "scenes": "Scenes",
        "prefabs": "Prefabs",
        "scripts": "Scripts",
    }
    IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".bmp")

    def __init__(self, root_path: str = ".") -> None:
        self.root_path = os.path.abspath(root_path)
        self.current_path = self.root_path
        self.items: List[Tuple[str, str]] = []
        self.project_service: Optional[ProjectService] = None
        self.asset_service: Optional[AssetService] = None
        self.selected_file: Optional[str] = None
        self.request_open_sprite_editor_for: Optional[str] = None
        self.request_open_scene_for: Optional[str] = None
        self.show_context_menu: bool = False
        self.context_menu_pos: Optional[rl.Vector2] = None

        self.scroll_offset: float = 0.0
        self.sidebar_scroll: float = 0.0
        self.dragging_file: Optional[str] = None
        self.drag_start_pos: Optional[rl.Vector2] = None

        self.search_text: str = ""
        self.search_focused: bool = False
        self.asset_filter: str = "all"

        self.expanded_folders: set[str] = {self.root_path}
        self._item_display_cache: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._visible_entries: List[Dict[str, Any]] = []
        self._selected_asset_detail: Optional[Dict[str, Any]] = None
        self._breadcrumb_cache: List[tuple[str, int]] = []
        self._cursor_interactive_rects: List[rl.Rectangle] = []
        self._search_rect: rl.Rectangle = rl.Rectangle(0, 0, 0, 0)

        self.refresh()

    def set_project_service(self, project_service: ProjectService) -> None:
        self.project_service = project_service
        self.asset_service = AssetService(project_service)
        self.asset_service.refresh_catalog()
        self.root_path = project_service.project_root_display.as_posix()
        self.current_path = self.root_path
        self.selected_file = None
        self.request_open_sprite_editor_for = None
        self.request_open_scene_for = None
        self.show_context_menu = False
        self.context_menu_pos = None
        self.scroll_offset = 0.0
        self.sidebar_scroll = 0.0
        self.dragging_file = None
        self.drag_start_pos = None
        self.search_text = ""
        self.search_focused = False
        self.asset_filter = "all"
        self.expanded_folders = {self.root_path}
        self.refresh()

    def refresh_asset_catalog(self) -> None:
        if self.asset_service is not None:
            self.asset_service.refresh_catalog()
        self.refresh()

    def refresh(self) -> None:
        try:
            self.items = []
            if self.current_path != self.root_path:
                self.items.append(("..", "dir"))

            entries = sorted(os.listdir(self.current_path))
            for entry in entries:
                if entry.startswith(".") or entry == "__pycache__":
                    continue
                full_path = os.path.join(self.current_path, entry)
                if os.path.isdir(full_path):
                    self.items.append((entry, "dir"))
                elif not entry.endswith(".pyc") and not entry.endswith(".meta.json"):
                    self.items.append((entry, "file"))
            self._rebuild_display_cache()
        except Exception:
            self.items = []
            self._item_display_cache = {}
            self._visible_entries = []
            self._selected_asset_detail = None
            self._breadcrumb_cache = []

    def create_folder(self, base_name: str = "New Folder") -> str:
        target_dir = self.current_path
        candidate = os.path.join(target_dir, base_name)
        suffix = 1
        while os.path.exists(candidate):
            candidate = os.path.join(target_dir, f"{base_name} {suffix}")
            suffix += 1
        os.makedirs(candidate, exist_ok=True)
        self.refresh()
        return candidate

    def set_search_text(self, text: str) -> None:
        self.search_text = str(text)
        self.scroll_offset = 0.0
        self._rebuild_display_cache()

    def set_asset_filter(self, filter_name: str) -> None:
        value = str(filter_name or "all").strip().lower()
        self.asset_filter = value if value in self.FILTER_ORDER else "all"
        self.scroll_offset = 0.0
        self._rebuild_display_cache()

    def get_visible_entries(self) -> List[Dict[str, Any]]:
        return [dict(item) for item in self._visible_entries]

    def get_selected_asset_detail(self) -> Optional[Dict[str, Any]]:
        return dict(self._selected_asset_detail) if self._selected_asset_detail is not None else None

    def select_asset(self, locator: str) -> bool:
        absolute_path = self._absolute_file_path(locator)
        if not absolute_path:
            self.selected_file = None
            self._selected_asset_detail = None
            return False
        self.selected_file = absolute_path
        self._selected_asset_detail = self._build_selected_asset_detail(absolute_path)
        return self._selected_asset_detail is not None

    def open_selected_sprite_editor(self) -> bool:
        detail = self.get_selected_asset_detail()
        if not detail or not detail.get("is_image", False):
            return False
        self.request_open_sprite_editor_for = str(detail.get("relative_path", "") or detail.get("absolute_path", ""))
        return bool(self.request_open_sprite_editor_for)

    def open_selected_scene(self) -> bool:
        detail = self.get_selected_asset_detail()
        if not detail or not detail.get("is_scene", False):
            return False
        self.request_open_scene_for = str(detail.get("relative_path", "") or detail.get("absolute_path", ""))
        return bool(self.request_open_scene_for)

    def render(self, x: int, y: int, width: int, height: int) -> None:
        self._cursor_interactive_rects = []
        self._handle_search_input()

        header_y = y
        rl.draw_rectangle(x, header_y, width, self.HEADER_HEIGHT, self.UNITY_BG_DARK)
        rl.draw_line(x, header_y + self.HEADER_HEIGHT - 1, x + width, header_y + self.HEADER_HEIGHT - 1, self.UNITY_BORDER)
        self._render_header(x, header_y, width)

        main_y = header_y + self.HEADER_HEIGHT
        main_h = height - self.HEADER_HEIGHT

        sidebar_rect = rl.Rectangle(x, main_y, self.SIDEBAR_WIDTH, main_h)
        rl.draw_rectangle_rec(sidebar_rect, self.UNITY_BG_DARK)
        rl.draw_line(int(x + self.SIDEBAR_WIDTH), main_y, int(x + self.SIDEBAR_WIDTH), main_y + main_h, self.UNITY_BORDER)
        self._render_sidebar(x, main_y, self.SIDEBAR_WIDTH, main_h)

        content_x = x + self.SIDEBAR_WIDTH + 1
        content_w = width - self.SIDEBAR_WIDTH - 1
        content_h = max(0, main_h - self.DETAIL_HEIGHT)
        detail_y = main_y + content_h
        rl.draw_rectangle(content_x, main_y, content_w, content_h, rl.Color(32, 32, 32, 255))
        rl.draw_rectangle(content_x, detail_y, content_w, self.DETAIL_HEIGHT, self.UNITY_BG_DARK)
        rl.draw_line(content_x, detail_y, content_x + content_w, detail_y, self.UNITY_BORDER)

        self._render_content(content_x, main_y, content_w, content_h)
        self._render_detail_panel(content_x, detail_y, content_w, self.DETAIL_HEIGHT)
        self._render_context_menu(content_x, main_y, content_w, content_h)

    def _render_header(self, x: int, y: int, width: int) -> None:
        search_rect = rl.Rectangle(x + 10, y + 6, max(120, width - 330), 18)
        self._search_rect = search_rect
        self._register_cursor_rect(search_rect)
        self._draw_text_input(search_rect, self.search_text, "Search assets", self.search_focused)

        refresh_rect = rl.Rectangle(x + width - 116, y + 5, 106, 20)
        self._register_cursor_rect(refresh_rect)
        if rl.gui_button(refresh_rect, "Refresh Assets"):
            self.refresh_asset_catalog()

        filter_x = x + 10
        filter_y = y + 29
        for key in self.FILTER_ORDER:
            label = self.FILTER_LABELS[key]
            button_width = 56 if key != "prefabs" else 62
            button_rect = rl.Rectangle(filter_x, filter_y, float(button_width), 18.0)
            self._register_cursor_rect(button_rect)
            button_label = f"* {label}" if self.asset_filter == key else label
            if rl.gui_button(button_rect, button_label):
                self.set_asset_filter(key)
            filter_x += button_width + 6

        breadcrumb_x = x + 360
        for text, text_width in self._breadcrumb_cache:
            if breadcrumb_x + text_width >= x + width - 124:
                break
            rl.draw_text(text, breadcrumb_x, y + 32, 10, self.UNITY_TEXT_DIM)
            breadcrumb_x += text_width + 4

    def _render_sidebar(self, x: int, y: int, width: int, height: int) -> None:
        with editor_scissor(rl.Rectangle(x, y, width, height)):
            root_rect = rl.Rectangle(x, y + 5, width, self.ITEM_HEIGHT)
            self._register_cursor_rect(root_rect)
            is_hover = rl.check_collision_point_rec(rl.get_mouse_position(), root_rect)

            if self.current_path == self.root_path:
                rl.draw_rectangle_rec(root_rect, self.UNITY_SELECTED)
            elif is_hover:
                rl.draw_rectangle_rec(root_rect, self.UNITY_HOVER)

            rl.draw_text("v", int(x + 5), int(y + 8), 10, self.UNITY_TEXT)
            rl.draw_text("Project", int(x + 20), int(y + 9), 10, self.UNITY_TEXT)
            if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.current_path = self.root_path
                self.scroll_offset = 0.0
                self.refresh()

    def _render_content(self, x: int, y: int, width: int, height: int) -> None:
        with editor_scissor(rl.Rectangle(x, y, width, height)):
            mouse_pos = rl.get_mouse_position()
            content_rect = rl.Rectangle(x, y, width, height)
            is_mouse_in = rl.check_collision_point_rec(mouse_pos, content_rect)

            if is_mouse_in:
                self.scroll_offset = max(0.0, self.scroll_offset - rl.get_mouse_wheel_move() * 20.0)
                if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT):
                    self.show_context_menu = True
                    self.context_menu_pos = rl.get_mouse_position()

            icon_w, icon_h = 88, 72
            padding = 10
            cols = max(1, int(width // (icon_w + padding)))

            for index, item in enumerate(self._visible_entries):
                row = index // cols
                col = index % cols
                ix = x + padding + col * (icon_w + padding)
                iy = y + padding + row * (icon_h + padding) - int(self.scroll_offset)
                if iy + icon_h < y:
                    continue
                if iy > y + height:
                    break

                rect = rl.Rectangle(ix, iy, icon_w, icon_h)
                self._register_cursor_rect(rect)
                is_hover = rl.check_collision_point_rec(mouse_pos, rect) and is_mouse_in
                is_selected = self.selected_file == item.get("absolute_path")
                if is_selected:
                    rl.draw_rectangle_rec(rect, self.UNITY_SELECTED)
                elif is_hover:
                    rl.draw_rectangle_rec(rect, self.UNITY_HOVER)

                if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                    if item["entry_type"] == "dir":
                        self.current_path = str(item["absolute_path"])
                        self.scroll_offset = 0.0
                        self.refresh()
                    else:
                        self.select_asset(str(item["absolute_path"]))
                        self.drag_start_pos = mouse_pos

                icon_rect = rl.Rectangle(ix + 24, iy + 6, 40, 34)
                self._draw_item_icon(icon_rect, item)

                trunc_name = str(item.get("trunc_name", item["name"]))
                text_w = int(item.get("text_width", rl.measure_text(trunc_name, 10)))
                rl.draw_text(trunc_name, int(ix + (icon_w - text_w) / 2), int(iy + 46), 10, self.UNITY_TEXT)
                meta = str(item.get("meta", ""))
                if meta:
                    rl.draw_text(meta, int(ix + 4), int(iy + 58), 8, self.UNITY_TEXT_DIM)

                if item["entry_type"] == "file" and self.drag_start_pos and is_hover:
                    if rl.vector2_distance(self.drag_start_pos, mouse_pos) > 5:
                        self.dragging_file = str(item["absolute_path"])

            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self.drag_start_pos = None
                self.dragging_file = None

            if not self._visible_entries:
                message = "No assets match the current search/filter" if self.search_text.strip() else "This folder is empty"
                rl.draw_text(message, int(x + 14), int(y + 14), 10, self.UNITY_TEXT_DIM)

    def _render_detail_panel(self, x: int, y: int, width: int, height: int) -> None:
        detail = self._selected_asset_detail
        if detail is None:
            rl.draw_text("Select an asset to inspect it.", int(x + 12), int(y + 10), 11, self.UNITY_TEXT_DIM)
            return

        rl.draw_text(str(detail.get("name", "")), int(x + 12), int(y + 8), 12, self.UNITY_TEXT)
        rl.draw_text(str(detail.get("relative_path", detail.get("absolute_path", ""))), int(x + 12), int(y + 24), 10, self.UNITY_TEXT_DIM)
        rl.draw_text(
            f"{detail.get('asset_kind', 'unknown')} / {detail.get('importer', 'unknown')} / {detail.get('guid_short', '-')}",
            int(x + 12),
            int(y + 40),
            10,
            self.UNITY_TEXT_DIM,
        )

        status_text = f"Pipeline: {detail.get('pipeline_detail', 'n/a')}"
        rl.draw_text(status_text, int(x + 12), int(y + 56), 10, self.UNITY_TEXT)

        if detail.get("is_image", False):
            rl.draw_text(
                f"Image: {detail.get('image_width', 0)}x{detail.get('image_height', 0)} | slices: {detail.get('slice_count', 0)}",
                int(x + 230),
                int(y + 56),
                10,
                self.UNITY_TEXT_DIM,
            )

        button_x = x + width - 132
        if detail.get("is_image", False):
            button_rect = rl.Rectangle(button_x, y + 10, 120, 22)
            self._register_cursor_rect(button_rect)
            if rl.gui_button(button_rect, "Open Sprite Editor"):
                self.open_selected_sprite_editor()
            button_x -= 128

        if detail.get("is_scene", False):
            scene_rect = rl.Rectangle(button_x, y + 10, 120, 22)
            self._register_cursor_rect(scene_rect)
            if rl.gui_button(scene_rect, "Open Scene"):
                self.open_selected_scene()

    def _draw_item_icon(self, rect: rl.Rectangle, item: Dict[str, Any]) -> None:
        if item["entry_type"] == "dir":
            rl.draw_rectangle_rec(rect, self.UNITY_FOLDER_ICON)
            rl.draw_rectangle(int(rect.x), int(rect.y), 15, 5, self.UNITY_FOLDER_ICON)
            return
        color = self.UNITY_IMAGE_ICON if item.get("is_image", False) else rl.Color(160, 160, 160, 255)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_rectangle_lines_ex(rect, 1, rl.Color(100, 100, 100, 255))

    def _draw_text_input(self, rect: rl.Rectangle, value: str, placeholder: str, focused: bool) -> None:
        background = rl.Color(46, 46, 46, 255) if focused else rl.Color(38, 38, 38, 255)
        border = self.UNITY_TAB_LINE if focused else self.UNITY_BORDER
        rl.draw_rectangle_rec(rect, background)
        rl.draw_rectangle_lines_ex(rect, 1, border)
        text = value if value else placeholder
        color = self.UNITY_TEXT if value else self.UNITY_TEXT_DIM
        rl.draw_text(text, int(rect.x + 6), int(rect.y + 5), 10, color)

    def _handle_search_input(self) -> None:
        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.search_focused = rl.check_collision_point_rec(mouse, self._search_rect)
        if not self.search_focused:
            return
        if rl.is_key_pressed(rl.KEY_BACKSPACE) and self.search_text:
            self.set_search_text(self.search_text[:-1])
        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (10, 13):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable() and len(self.search_text) < 64:
                self.set_search_text(self.search_text + char)

    def _render_context_menu(self, x: int, y: int, width: int, height: int) -> None:
        if not self.show_context_menu or self.context_menu_pos is None:
            return

        menu_x = int(min(self.context_menu_pos.x, x + width - self.MENU_WIDTH - 4))
        menu_y = int(min(self.context_menu_pos.y, y + height - 78))
        menu_rect = rl.Rectangle(menu_x, menu_y, self.MENU_WIDTH, 52)
        self._register_cursor_rect(menu_rect)
        rl.draw_rectangle_rec(menu_rect, self.UNITY_HEADER)
        rl.draw_rectangle_lines_ex(menu_rect, 1, self.UNITY_BORDER)

        create_rect = rl.Rectangle(menu_rect.x + 4, menu_rect.y + 4, menu_rect.width - 8, 20)
        refresh_rect = rl.Rectangle(menu_rect.x + 4, menu_rect.y + 28, menu_rect.width - 8, 20)
        self._register_cursor_rect(create_rect)
        self._register_cursor_rect(refresh_rect)
        if rl.gui_button(create_rect, "Create Folder"):
            self.create_folder()
            self.show_context_menu = False
            self.context_menu_pos = None
            return
        if rl.gui_button(refresh_rect, "Refresh Assets"):
            self.refresh_asset_catalog()
            self.show_context_menu = False
            self.context_menu_pos = None
            return

        mouse_pos = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and not rl.check_collision_point_rec(mouse_pos, menu_rect):
            self.show_context_menu = False
            self.context_menu_pos = None

    def _rebuild_display_cache(self) -> None:
        self._item_display_cache = {}
        rel_path = os.path.relpath(self.current_path, self.root_path)
        parts = ["Project"] + [part for part in rel_path.split(os.sep) if part and part != "."]
        self._breadcrumb_cache = []
        for part in parts:
            text = part + " >"
            self._breadcrumb_cache.append((text, rl.measure_text(text, 10)))
        self._visible_entries = self._build_visible_entries()
        self._sync_selection_with_visible_entries()

    def _build_visible_entries(self) -> List[Dict[str, Any]]:
        if self.search_text.strip():
            return self._build_search_entries()
        result: List[Dict[str, Any]] = []
        for name, entry_type in self.items:
            absolute_path = os.path.join(self.current_path, name) if name != ".." else os.path.dirname(self.current_path)
            if entry_type == "dir":
                item = self._build_directory_entry(name, absolute_path)
                result.append(item)
                self._item_display_cache[(name, entry_type)] = item
                continue
            item = self._build_file_entry(absolute_path)
            if item is None or not self._matches_filter(item):
                continue
            result.append(item)
            self._item_display_cache[(name, entry_type)] = item
        return result

    def _build_search_entries(self) -> List[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        assets = self.asset_service.find_assets(search=self.search_text.strip())
        result: List[Dict[str, Any]] = []
        for entry in assets:
            item = self._build_file_entry_from_entry(entry)
            if item is None or not self._matches_filter(item):
                continue
            result.append(item)
        return result

    def _build_directory_entry(self, name: str, absolute_path: str) -> Dict[str, Any]:
        label = name if len(name) < 14 else name[:11] + "..."
        return {
            "name": name,
            "entry_type": "dir",
            "absolute_path": os.path.abspath(absolute_path),
            "relative_path": "",
            "asset_kind": "folder",
            "importer": "",
            "guid_short": "",
            "has_meta": False,
            "meta": "folder",
            "trunc_name": label,
            "text_width": rl.measure_text(label, 10),
            "pipeline_status": "",
            "pipeline_detail": "",
            "slice_count": 0,
            "image_width": 0,
            "image_height": 0,
            "is_image": False,
            "is_scene": False,
        }

    def _build_file_entry(self, absolute_path: str) -> Optional[Dict[str, Any]]:
        relative_path = self._to_relative_path(absolute_path)
        entry = self.asset_service.get_asset_entry(relative_path) if (self.asset_service is not None and relative_path) else None
        if entry is not None:
            return self._build_file_entry_from_entry(entry)
        if not os.path.isfile(absolute_path):
            return None
        return self._build_file_entry_from_entry(
            {
                "name": os.path.basename(absolute_path),
                "path": relative_path,
                "absolute_path": os.path.abspath(absolute_path),
                "asset_kind": "unknown",
                "importer": "unknown",
                "guid_short": "",
                "has_meta": False,
            }
        )

    def _build_file_entry_from_entry(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        relative_path = str(entry.get("path", "") or "")
        absolute_path = self._absolute_file_path(relative_path) or str(entry.get("absolute_path", "") or "")
        if not absolute_path:
            return None
        name = str(entry.get("name", "") or os.path.basename(absolute_path))
        asset_kind = str(entry.get("asset_kind", "unknown"))
        importer = str(entry.get("importer", "unknown"))
        guid_short = str(entry.get("guid_short", ""))
        has_meta = bool(entry.get("has_meta", False))
        is_image = asset_kind == "texture" or absolute_path.lower().endswith(self.IMAGE_EXTENSIONS)
        is_scene = asset_kind == "scene_data" or self._is_scene_path(absolute_path)
        pipeline_status = ""
        pipeline_detail = ""
        slice_count = 0
        image_width = 0
        image_height = 0
        if is_image and self.asset_service is not None and relative_path:
            summary = self.asset_service.get_sprite_asset_summary(relative_path)
            guid_short = str(summary.get("guid_short", guid_short) or guid_short)
            has_meta = bool(summary.get("has_metadata", has_meta))
            pipeline_status = str(summary.get("pipeline_status", "") or "")
            pipeline_detail = str(summary.get("pipeline_label", "") or "")
            slice_count = int(summary.get("slice_count", 0) or 0)
            image_width, image_height = tuple(summary.get("image_size", (0, 0)))
        meta_chunks = [asset_kind]
        if guid_short:
            meta_chunks.append(guid_short)
        if pipeline_status:
            meta_chunks.append(pipeline_status)
        meta_label = " ".join(meta_chunks)[:24]
        trunc_name = name if len(name) < 15 else name[:12] + "..."
        return {
            "name": name,
            "entry_type": "file",
            "absolute_path": os.path.abspath(absolute_path),
            "relative_path": relative_path,
            "asset_kind": asset_kind,
            "importer": importer,
            "guid_short": guid_short,
            "has_meta": has_meta,
            "meta": meta_label,
            "trunc_name": trunc_name,
            "text_width": rl.measure_text(trunc_name, 10),
            "pipeline_status": pipeline_status,
            "pipeline_detail": pipeline_detail,
            "slice_count": slice_count,
            "image_width": image_width,
            "image_height": image_height,
            "is_image": is_image,
            "is_scene": is_scene,
        }

    def _matches_filter(self, item: Dict[str, Any]) -> bool:
        if item["entry_type"] == "dir":
            return True
        if self.asset_filter == "all":
            return True
        if self.asset_filter == "images":
            return bool(item.get("is_image", False))
        if self.asset_filter == "scenes":
            return bool(item.get("is_scene", False))
        if self.asset_filter == "prefabs":
            return item.get("asset_kind") == "prefab"
        if self.asset_filter == "scripts":
            return item.get("asset_kind") == "script"
        return True

    def _sync_selection_with_visible_entries(self) -> None:
        if self.selected_file and not os.path.exists(self.selected_file):
            self.selected_file = None
            self._selected_asset_detail = None
            return
        if self.selected_file is None:
            self._selected_asset_detail = None
            return
        self._selected_asset_detail = self._build_selected_asset_detail(self.selected_file)

    def _build_selected_asset_detail(self, absolute_path: str) -> Optional[Dict[str, Any]]:
        absolute = self._absolute_file_path(absolute_path)
        if not absolute or not os.path.isfile(absolute):
            return None
        item = self._build_file_entry(absolute)
        if item is None:
            return None
        detail = dict(item)
        detail["can_open_sprite_editor"] = bool(detail.get("is_image", False))
        detail["can_open_scene"] = bool(detail.get("is_scene", False))
        return detail

    def _absolute_file_path(self, locator: str) -> str:
        value = str(locator or "").strip()
        if not value:
            return ""
        if os.path.isabs(value):
            return value if os.path.isfile(value) else ""
        if self.project_service is not None:
            resolved = self.project_service.resolve_path(value)
            return resolved.as_posix() if resolved.exists() else ""
        candidate = os.path.abspath(os.path.join(self.root_path, value))
        return candidate if os.path.isfile(candidate) else ""

    def _to_relative_path(self, absolute_path: str) -> str:
        if not absolute_path:
            return ""
        if self.project_service is not None:
            return self.project_service.to_relative_path(absolute_path)
        try:
            return os.path.relpath(absolute_path, self.root_path).replace("\\", "/")
        except Exception:
            return absolute_path.replace("\\", "/")

    def _is_scene_file(self, file_path: str) -> bool:
        return self._is_scene_path(self._absolute_file_path(file_path) or file_path)

    def _is_scene_path(self, file_path: str) -> bool:
        if self.project_service is None or not str(file_path).lower().endswith(".json"):
            return False
        levels_root = self.project_service.get_project_path("levels").as_posix()
        try:
            return os.path.commonpath([os.path.abspath(file_path), levels_root]) == os.path.abspath(levels_root)
        except ValueError:
            return False

    def get_cursor_intent(self, mouse_pos: Optional[rl.Vector2] = None) -> CursorVisualState:
        mouse = rl.get_mouse_position() if mouse_pos is None else mouse_pos
        if rl.check_collision_point_rec(mouse, self._search_rect):
            return CursorVisualState.TEXT
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))
