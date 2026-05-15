"""
engine/editor/asset_browser.py - Asset Browser Panel (Unity-style).
"""

from __future__ import annotations

import os
from typing import Any, Optional

import pyray as rl
from engine.assets.asset_service import AssetService
from engine.editor.theme import get_active_theme
from engine.editor.ui.dropdown_render import process_dropdown_pointer, render_dropdown
from engine.editor.ui.text_input_render import process_text_input, render_text_input
from engine.editor.ui_core.controls.context_menu import ContextMenuItem, ContextMenuModel
from engine.editor.ui_core.controls.dropdown import DropdownModel, DropdownOption
from engine.editor.ui_core.controls.text_input import TextInput
from engine.project.project_service import ProjectService

FILTER_OPTIONS = [
    DropdownOption(id="all", label="All"),
    DropdownOption(id="images", label="Images"),
    DropdownOption(id="scenes", label="Scenes"),
    DropdownOption(id="prefabs", label="Prefabs"),
    DropdownOption(id="scripts", label="Scripts"),
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga"}
SCENE_EXTENSIONS = {".json"}
PREFAB_EXTENSIONS = {".prefab"}
SCRIPT_EXTENSIONS = {".py"}


class AssetBrowserPanel:
    """Bottom-panel asset browser with filter, search, grid view and context menu."""

    BG = rl.Color(42, 42, 42, 255)
    HEADER = rl.Color(56, 56, 56, 255)
    BORDER = rl.Color(25, 25, 25, 255)
    TEXT = rl.Color(200, 200, 200, 255)
    TEXT_DIM = rl.Color(128, 128, 128, 255)
    SELECTED = rl.Color(44, 93, 135, 255)
    HOVER = rl.Color(60, 60, 60, 255)
    TOOLBAR_H = 28
    GRID_CELL = 80
    GRID_PAD = 8

    def __init__(self, layout: Any = None) -> None:
        self._layout = layout
        self._project_service: Optional[ProjectService] = None
        self._asset_service: Optional[AssetService] = None
        self._assets: list[dict[str, Any]] = []
        self._filtered: list[dict[str, Any]] = []
        self._selected_path: Optional[str] = None
        self._scroll_offset: float = 0.0
        self._hovered_idx: int = -1

        self.filter_dropdown = DropdownModel(
            id="asset_filter",
            options=list(FILTER_OPTIONS),
            selected_id="all",
        )
        self.search_input = TextInput(placeholder="Search assets...", max_length=64, font_size=10)

    def set_project_service(self, service: ProjectService) -> None:
        self._project_service = service

    def set_asset_service(self, service: AssetService) -> None:
        self._asset_service = service

    def refresh(self) -> None:
        """Refresh asset list from asset directory."""
        self._assets = []
        if self._asset_service:
            try:
                assets_dir = self._asset_service.assets_dir
                if os.path.isdir(assets_dir):
                    for root, dirs, files in os.walk(assets_dir):
                        for f in files:
                            path = os.path.join(root, f)
                            rel = os.path.relpath(path, assets_dir)
                            ext = os.path.splitext(f)[1].lower()
                            size = os.path.getsize(path)
                            self._assets.append({
                                "name": f,
                                "path": path,
                                "rel_path": rel,
                                "ext": ext,
                                "size": size,
                            })
            except Exception:
                pass
        self._apply_filter()

    def _apply_filter(self) -> None:
        selected = self.filter_dropdown.selected_id
        search = self.search_input.text.lower()
        result = self._assets
        if selected and selected != "all":
            ext_map = {
                "images": IMAGE_EXTENSIONS,
                "scenes": SCENE_EXTENSIONS,
                "prefabs": PREFAB_EXTENSIONS,
                "scripts": SCRIPT_EXTENSIONS,
            }
            allowed = ext_map.get(selected, set())
            result = [a for a in result if a["ext"] in allowed]
        if search:
            result = [a for a in result if search in a["name"].lower()]
        self._filtered = result

    def _resolve_colors(self) -> dict:
        """Resolve colors from the active editor theme."""
        try:
            theme = get_active_theme()
            return {
                "BG": rl.Color(*theme.panel),
                "HEADER": rl.Color(*theme.panel_header),
                "BORDER": rl.Color(*theme.border),
                "TEXT": rl.Color(*theme.text),
                "TEXT_DIM": rl.Color(*theme.text_muted),
                "SELECTED": rl.Color(*theme.accent),
                "HOVER": rl.Color(*theme.border_hover),
            }
        except Exception:
            return {
                "BG": self.BG,
                "HEADER": self.HEADER,
                "BORDER": self.BORDER,
                "TEXT": self.TEXT,
                "TEXT_DIM": self.TEXT_DIM,
                "SELECTED": self.SELECTED,
                "HOVER": self.HOVER,
            }

    def render(self, x: int, y: int, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return

        colors = self._resolve_colors()

        # Panel background
        rl.draw_rectangle_rec(rl.Rectangle(float(x), float(y), float(width), float(height)), colors["BG"])
        rl.draw_rectangle_lines_ex(rl.Rectangle(float(x), float(y), float(width), float(height)), 1.0, colors["BORDER"])

        # Toolbar
        toolbar_y = y + 2
        rl.draw_rectangle_rec(rl.Rectangle(float(x), float(y), float(width), float(self.TOOLBAR_H)), colors["HEADER"])

        # Filter dropdown
        dd_x = x + 8
        self.filter_dropdown.arrange((float(dd_x), float(toolbar_y), 80.0, 20.0))
        render_dropdown(self.filter_dropdown, self.filter_dropdown.global_rect)

        # Search input
        search_x = dd_x + 90
        search_w = min(160.0, width - search_x - 170)
        self.search_input.arrange((float(search_x), float(toolbar_y), search_w, 20.0))
        render_text_input(self.search_input, self.search_input.focused)

        # Import / Refresh buttons
        btn_x = x + width - 140
        if rl.gui_button(rl.Rectangle(float(btn_x), float(toolbar_y), 60.0, 20.0), "Refresh"):
            self.refresh()
        if rl.gui_button(rl.Rectangle(float(btn_x + 65), float(toolbar_y), 60.0, 20.0), "Import"):
            pass  # Import handled externally

        # Content area
        content_y = y + self.TOOLBAR_H + 4
        content_h = height - self.TOOLBAR_H - 8

        # Apply filter
        self._apply_filter()

        # Grid layout
        cols = max(1, int((width - 16) / (self.GRID_CELL + self.GRID_PAD)))
        rows = max(1, (len(self._filtered) + cols - 1) // cols)
        total_h = rows * (self.GRID_CELL + self.GRID_PAD)

        # Scroll
        max_scroll = max(0.0, total_h - content_h)
        self._scroll_offset = min(max_scroll, max(0.0, self._scroll_offset))

        mouse = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse, rl.Rectangle(float(x), float(content_y), float(width), float(content_h))):
            self._scroll_offset -= rl.get_mouse_wheel_move() * 40
            self._scroll_offset = min(max_scroll, max(0.0, self._scroll_offset))

        rl.begin_scissor_mode(int(x), int(content_y), int(width), int(content_h))
        self._hovered_idx = -1

        for i, asset in enumerate(self._filtered):
            col = i % cols
            row = i // cols
            cx = x + 8 + col * (self.GRID_CELL + self.GRID_PAD)
            cy = content_y + row * (self.GRID_CELL + self.GRID_PAD) - self._scroll_offset

            if cy + self.GRID_CELL < content_y or cy > content_y + content_h:
                continue

            cell_rect = rl.Rectangle(float(cx), float(cy), float(self.GRID_CELL), float(self.GRID_CELL))

            # Hover
            is_hovered = rl.check_collision_point_rec(mouse, cell_rect)
            is_selected = asset["path"] == self._selected_path

            bg_color = colors["SELECTED"] if is_selected else (colors["HOVER"] if is_hovered else colors["BG"])
            rl.draw_rectangle_rec(cell_rect, bg_color)
            rl.draw_rectangle_lines_ex(cell_rect, 1.0, colors["BORDER"] if not is_selected else rl.Color(100, 150, 200, 255))

            # Icon based on type
            icon_color = self._icon_color(asset["ext"])
            icon_rect = rl.Rectangle(float(cx + 4), float(cy + 4), float(self.GRID_CELL - 8), float(self.GRID_CELL - 24))
            rl.draw_rectangle_rec(icon_rect, icon_color)
            rl.draw_rectangle_lines_ex(icon_rect, 1.0, colors["BORDER"])

            # Extension label
            rl.draw_text(asset["ext"] or "?", int(cx + 8), int(cy + 4), 10, colors["TEXT"])

            # Name (truncated)
            name = asset["name"]
            if len(name) > 10:
                name = name[:9] + "..."
            text_w = rl.measure_text(name, 10)
            rl.draw_text(name, int(cx + (self.GRID_CELL - text_w) / 2), int(cy + self.GRID_CELL - 18), 10, colors["TEXT"])

            if is_hovered:
                self._hovered_idx = i

        rl.end_scissor_mode()

        # Process dropdown + search input
        process_dropdown_pointer(self.filter_dropdown)
        if self.filter_dropdown.selected_id != getattr(self, "_last_filter", ""):
            self._last_filter = self.filter_dropdown.selected_id
            self._apply_filter()

        # Focus handling for search
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if rl.check_collision_point_rec(mouse, rl.Rectangle(float(search_x), float(toolbar_y), search_w, 20.0)):
                self.search_input._focused = True
            else:
                self.search_input._focused = False
        if self.search_input.focused:
            process_text_input(self.search_input)

    def handle_context_menu(self) -> Optional[str]:
        """Check for right-click and show context menu. Call from parent after render."""
        if self._hovered_idx < 0 or self._hovered_idx >= len(self._filtered):
            return None
        if not rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT):
            return None
        asset = self._filtered[self._hovered_idx]
        self._selected_path = asset["path"]
        if self._layout and hasattr(self._layout, "show_context_menu"):
            menu = ContextMenuModel(id="asset_menu", items=[
                ContextMenuItem(id="delete", label="Delete"),
                ContextMenuItem(id="rename", label="Rename"),
                ContextMenuItem(id="show_explorer", label="Show in Explorer"),
            ])
            mouse = rl.get_mouse_position()
            self._layout.show_context_menu(menu, mouse.x, mouse.y)
            return "opened"
        return None

    def _icon_color(self, ext: str) -> rl.Color:
        if ext in IMAGE_EXTENSIONS:
            return rl.Color(118, 158, 223, 180)
        elif ext in SCENE_EXTENSIONS:
            return rl.Color(160, 200, 140, 180)
        elif ext in PREFAB_EXTENSIONS:
            return rl.Color(200, 160, 120, 180)
        elif ext in SCRIPT_EXTENSIONS:
            return rl.Color(180, 140, 200, 180)
        return rl.Color(100, 100, 100, 180)
