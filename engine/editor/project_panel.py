"""
engine/editor/project_panel.py - Explorador de Archivos (Project Browser)

PROPÓSITO:
    Muestra los archivos del proyecto para permitir navegar y seleccionar recursos.
    Fundamental para el futuro Drag & Drop.

FUNCIONALIDADES:
    - Listar contenido de directorio actual.
    - Navegar entre carpetas.
    - Renderizar iconos simples (Folder/File).
"""

import os
import pyray as rl
from typing import Any, Dict, List, Tuple, Optional

from engine.assets.asset_service import AssetService
from engine.editor.cursor_manager import CursorVisualState
from engine.project.project_service import ProjectService

class ProjectPanel:
    
    # Unity Colors (Exactos)
    UNITY_BG_DARK = rl.Color(42, 42, 42, 255)       # Panel background
    UNITY_HEADER = rl.Color(56, 56, 56, 255)        # Header/Tab background
    UNITY_BORDER = rl.Color(25, 25, 25, 255)
    UNITY_SELECTED = rl.Color(44, 93, 135, 255)     # Selection blue
    UNITY_HOVER = rl.Color(60, 60, 60, 255)
    UNITY_TEXT = rl.Color(200, 200, 200, 255)
    UNITY_TEXT_DIM = rl.Color(128, 128, 128, 255)
    UNITY_TAB_LINE = rl.Color(58, 121, 187, 255)
    UNITY_FOLDER_ICON = rl.Color(220, 200, 100, 255)
    
    SIDEBAR_WIDTH: int = 180
    ITEM_HEIGHT: int = 18
    MENU_WIDTH: int = 140
    
    def __init__(self, root_path: str = ".") -> None:
        self.root_path = os.path.abspath(root_path)
        self.current_path = self.root_path
        self.items: List[Tuple[str, str]] = [] # (name, type: 'dir'|'file')
        self.project_service: Optional[ProjectService] = None
        self.asset_service: Optional[AssetService] = None
        self.selected_file: Optional[str] = None
        self.request_open_sprite_editor_for: Optional[str] = None
        self.request_open_scene_for: Optional[str] = None
        self.show_context_menu: bool = False
        self.context_menu_pos: Optional[rl.Vector2] = None
        
        self.scroll_offset: float = 0
        self.sidebar_scroll: float = 0
        
        # Drag & Drop State
        self.dragging_file: Optional[str] = None
        self.drag_start_pos: Optional[rl.Vector2] = None
        
        # Folder tree state
        from typing import Set
        self.expanded_folders: Set[str] = {self.root_path}
        self._item_display_cache: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._breadcrumb_cache: List[tuple[str, int]] = []
        self._cursor_interactive_rects: List[rl.Rectangle] = []
        
        self.refresh()

    def set_project_service(self, project_service: ProjectService) -> None:
        self.project_service = project_service
        self.asset_service = AssetService(project_service)
        self.asset_service.refresh_catalog()
        self.root_path = project_service.project_root.as_posix()
        self.current_path = self.root_path
        self.selected_file = None
        self.request_open_sprite_editor_for = None
        self.request_open_scene_for = None
        self.show_context_menu = False
        self.context_menu_pos = None
        self.scroll_offset = 0
        self.sidebar_scroll = 0
        self.dragging_file = None
        self.drag_start_pos = None
        self.expanded_folders = {self.root_path}
        self.refresh()

    def refresh_asset_catalog(self) -> None:
        if self.asset_service is not None:
            self.asset_service.refresh_catalog()
        self.refresh()
        
    def refresh(self) -> None:
        """Recarga la lista de archivos del directorio actual."""
        try:
            self.items = []
            
            # Botón ".." para subir
            if self.current_path != self.root_path:
                 self.items.append(("..", "dir"))
            
            # Listar
            entries = os.listdir(self.current_path)
            entries.sort()
            
            for entry in entries:
                if entry.startswith(".") or entry == "__pycache__": continue
                full_path = os.path.join(self.current_path, entry)
                if os.path.isdir(full_path):
                    self.items.append((entry, "dir"))
                else:
                    if not entry.endswith(".pyc") and not entry.endswith(".meta.json"):
                        self.items.append((entry, "file"))
            self._rebuild_display_cache()
                        
        except Exception:
            self.items = []
            self._item_display_cache = {}
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

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Renderiza el panel de proyecto estilo Unity."""
        self._cursor_interactive_rects = []

        # Breadcrumb area / Search
        breadcrumb_y = y
        breadcrumb_h = 24
        rl.draw_rectangle(x, breadcrumb_y, width, breadcrumb_h, self.UNITY_BG_DARK)
        rl.draw_line(x, breadcrumb_y + breadcrumb_h - 1, x + width, breadcrumb_y + breadcrumb_h - 1, self.UNITY_BORDER)
        
        # Breadcrumbs
        bc_x = x + 10
        for text, text_width in self._breadcrumb_cache:
            rl.draw_text(text, bc_x, int(breadcrumb_y + 6), 10, self.UNITY_TEXT_DIM)
            bc_x += text_width + 5
            
        # ========================================
        # 2. Main Area (Split into Sidebar and Content)
        # ========================================
        main_y = breadcrumb_y + breadcrumb_h
        main_h = height - breadcrumb_h
        
        # Sidebar (Folder Tree)
        sidebar_rect = rl.Rectangle(x, main_y, self.SIDEBAR_WIDTH, main_h)
        rl.draw_rectangle_rec(sidebar_rect, self.UNITY_BG_DARK)
        rl.draw_line(int(x + self.SIDEBAR_WIDTH), main_y, int(x + self.SIDEBAR_WIDTH), main_y + main_h, self.UNITY_BORDER)
        
        self._render_sidebar(x, main_y, self.SIDEBAR_WIDTH, main_h)
        
        # Content View (File Grid)
        content_x = x + self.SIDEBAR_WIDTH + 1
        content_w = width - self.SIDEBAR_WIDTH - 1
        rl.draw_rectangle(content_x, main_y, content_w, main_h, rl.Color(32, 32, 32, 255))
        
        self._render_content(content_x, main_y, content_w, main_h)
        self._render_context_menu(content_x, main_y, content_w, main_h)

    def _render_sidebar(self, x: int, y: int, width: int, height: int) -> None:
        """Dibuja el árbol de carpetas lateral."""
        rl.begin_scissor_mode(x, y, width, height)
        # Por ahora solo mostramos "Assets" como raíz
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
            self.refresh()
            
        rl.end_scissor_mode()

    def _render_content(self, x: int, y: int, width: int, height: int) -> None:
        """Dibuja la vista de contenido (iconos de archivos)."""
        rl.begin_scissor_mode(x, y, width, height)
        
        mouse_pos = rl.get_mouse_position()
        is_mouse_in = rl.check_collision_point_rec(mouse_pos, rl.Rectangle(x, y, width, height))
        
        # Scroll
        if is_mouse_in:
            self.scroll_offset -= rl.get_mouse_wheel_move() * 20
            self.scroll_offset = max(0, self.scroll_offset)
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT):
                self.show_context_menu = True
                self.context_menu_pos = rl.get_mouse_position()
            
        # Layout de iconos (Unity style grid)
        icon_w, icon_h = 60, 70
        padding = 10
        cols = max(1, width // (icon_w + padding))
        
        for i, (name, entry_type) in enumerate(self.items):
            display = self._item_display_cache.get((name, entry_type), {})
            row = i // cols
            col = i % cols
            
            ix = x + padding + col * (icon_w + padding)
            iy = y + padding + row * (icon_h + padding) - int(self.scroll_offset)
            
            # Culling
            if iy + icon_h < y: continue
            if iy > y + height: break
            
            rect = rl.Rectangle(ix, iy, icon_w, icon_h)
            self._register_cursor_rect(rect)
            is_hover = rl.check_collision_point_rec(mouse_pos, rect) and is_mouse_in
            
            if is_hover:
                rl.draw_rectangle_rec(rect, self.UNITY_HOVER)
                if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                    if entry_type == "dir":
                        if name == "..":
                            self.current_path = os.path.dirname(self.current_path)
                        else:
                            self.current_path = os.path.join(self.current_path, name)
                        self.refresh()
                        self.scroll_offset = 0
                    else:
                        self.selected_file = os.path.join(self.current_path, name)
                        self.drag_start_pos = mouse_pos
            
            # Visuales del Icono
            icon_rect = rl.Rectangle(ix + 10, iy + 5, 40, 40)
            if entry_type == "dir":
                rl.draw_rectangle_rec(icon_rect, self.UNITY_FOLDER_ICON)
                rl.draw_rectangle(int(ix + 10), int(iy + 5), 15, 5, self.UNITY_FOLDER_ICON)
            else:
                rl.draw_rectangle_rec(icon_rect, rl.Color(160, 160, 160, 255))
                rl.draw_rectangle_lines_ex(icon_rect, 1, rl.Color(100, 100, 100, 255))
            
            # Nombre truncado
            trunc_name = str(display.get("trunc_name", name if len(name) < 10 else name[:7] + "..."))
            text_w = int(display.get("text_width", rl.measure_text(trunc_name, 10)))
            rl.draw_text(trunc_name, int(ix + (icon_w - text_w)//2), int(iy + 50), 10, self.UNITY_TEXT)
            meta = str(display.get("meta", ""))
            if meta:
                rl.draw_text(meta, int(ix + 2), int(iy + 61), 8, self.UNITY_TEXT_DIM)
            
            # Drag logic
            if entry_type == "file" and self.drag_start_pos and is_hover:
                if rl.vector2_distance(self.drag_start_pos, mouse_pos) > 5:
                    self.dragging_file = os.path.join(self.current_path, name)

        if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            self.drag_start_pos = None
            self.dragging_file = None

        if self.selected_file:
            button_x = x + width - 140
            if self.selected_file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                button_rect = rl.Rectangle(button_x, y + 6, 120, 20)
                self._register_cursor_rect(button_rect)
                if rl.gui_button(button_rect, "Sprite Editor"):
                    if self.project_service is not None:
                        self.request_open_sprite_editor_for = self.project_service.to_relative_path(self.selected_file)
                    else:
                        self.request_open_sprite_editor_for = self.selected_file
                button_x -= 128

            if self._is_scene_file(self.selected_file):
                scene_rect = rl.Rectangle(button_x, y + 6, 120, 20)
                self._register_cursor_rect(scene_rect)
                if rl.gui_button(scene_rect, "Open Scene"):
                    if self.project_service is not None:
                        self.request_open_scene_for = self.project_service.to_relative_path(self.selected_file)
                    else:
                        self.request_open_scene_for = self.selected_file

        rl.end_scissor_mode()

    def _is_scene_file(self, file_path: str) -> bool:
        if self.project_service is None or not file_path.lower().endswith(".json"):
            return False
        levels_root = self.project_service.get_project_path("levels").as_posix()
        try:
            return os.path.commonpath([os.path.abspath(file_path), levels_root]) == os.path.abspath(levels_root)
        except ValueError:
            return False

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
        path_parts = ["Project"] + ([p for p in rel_path.split(os.sep) if p and p != "."])
        self._breadcrumb_cache = []
        for part in path_parts:
            text = part + " >"
            self._breadcrumb_cache.append((text, rl.measure_text(text, 10)))

        for name, entry_type in self.items:
            trunc_name = name if len(name) < 10 else name[:7] + "..."
            cached: Dict[str, Any] = {
                "trunc_name": trunc_name,
                "text_width": rl.measure_text(trunc_name, 10),
                "meta": "",
            }
            if entry_type == "file" and self.project_service is not None and self.asset_service is not None:
                rel_path = self.project_service.to_relative_path(os.path.join(self.current_path, name))
                entry = self.asset_service.get_asset_entry(rel_path)
            if entry is not None:
                cached["meta"] = f"{entry.get('asset_kind', '?')} {entry.get('guid_short', '')}"[:13]
            self._item_display_cache[(name, entry_type)] = cached

    def get_cursor_intent(self, mouse_pos: Optional[rl.Vector2] = None) -> CursorVisualState:
        mouse = rl.get_mouse_position() if mouse_pos is None else mouse_pos
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))
