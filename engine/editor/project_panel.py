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
from typing import List, Tuple, Optional

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
    
    HEADER_HEIGHT: int = 22
    SIDEBAR_WIDTH: int = 180
    ITEM_HEIGHT: int = 18
    
    def __init__(self, root_path: str = ".") -> None:
        self.root_path = os.path.abspath(root_path)
        self.current_path = self.root_path
        self.items: List[Tuple[str, str]] = [] # (name, type: 'dir'|'file')
        self.project_service: Optional[ProjectService] = None
        self.selected_file: Optional[str] = None
        self.request_open_sprite_editor_for: Optional[str] = None
        
        self.scroll_offset: float = 0
        self.sidebar_scroll: float = 0
        
        # Drag & Drop State
        self.dragging_file: Optional[str] = None
        self.drag_start_pos: Optional[rl.Vector2] = None
        
        # Folder tree state
        from typing import Set
        self.expanded_folders: Set[str] = {self.root_path}
        
        self.refresh()

    def set_project_service(self, project_service: ProjectService) -> None:
        self.project_service = project_service
        self.root_path = project_service.get_project_path("assets").as_posix()
        self.current_path = self.root_path
        self.selected_file = None
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
                    if not entry.endswith(".pyc"):
                        self.items.append((entry, "file"))
                        
        except Exception:
            self.items = []

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Renderiza el panel de proyecto estilo Unity."""
        
        # ========================================
        # 1. Header (Solo el fondo, tabs las dibuja EditorLayout)
        # ========================================
        header_rect = rl.Rectangle(x, y, width, self.HEADER_HEIGHT)
        rl.draw_rectangle_rec(header_rect, self.UNITY_HEADER)
        
        # Breadcrumb area / Search
        breadcrumb_y = y + self.HEADER_HEIGHT
        breadcrumb_h = 24
        rl.draw_rectangle(x, breadcrumb_y, width, breadcrumb_h, self.UNITY_BG_DARK)
        rl.draw_line(x, breadcrumb_y + breadcrumb_h - 1, x + width, breadcrumb_y + breadcrumb_h - 1, self.UNITY_BORDER)
        
        # Breadcrumbs
        rel_path = os.path.relpath(self.current_path, self.root_path)
        path_parts = ["Assets"] + ([p for p in rel_path.split(os.sep) if p and p != "."])
        bc_x = x + 10
        for part in path_parts:
            text = part + " >"
            rl.draw_text(text, bc_x, int(breadcrumb_y + 6), 10, self.UNITY_TEXT_DIM)
            bc_x += rl.measure_text(text, 10) + 5
            
        # ========================================
        # 2. Main Area (Split into Sidebar and Content)
        # ========================================
        main_y = breadcrumb_y + breadcrumb_h
        main_h = height - (self.HEADER_HEIGHT + breadcrumb_h)
        
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

    def _render_sidebar(self, x: int, y: int, width: int, height: int) -> None:
        """Dibuja el árbol de carpetas lateral."""
        rl.begin_scissor_mode(x, y, width, height)
        # Por ahora solo mostramos "Assets" como raíz
        root_rect = rl.Rectangle(x, y + 5, width, self.ITEM_HEIGHT)
        is_hover = rl.check_collision_point_rec(rl.get_mouse_position(), root_rect)
        
        if self.current_path == self.root_path:
            rl.draw_rectangle_rec(root_rect, self.UNITY_SELECTED)
        elif is_hover:
            rl.draw_rectangle_rec(root_rect, self.UNITY_HOVER)
            
        rl.draw_text("v", int(x + 5), int(y + 8), 10, self.UNITY_TEXT) 
        rl.draw_text("Assets", int(x + 20), int(y + 9), 10, self.UNITY_TEXT)
        
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
            
        # Layout de iconos (Unity style grid)
        icon_w, icon_h = 60, 70
        padding = 10
        cols = max(1, width // (icon_w + padding))
        
        for i, (name, entry_type) in enumerate(self.items):
            row = i // cols
            col = i % cols
            
            ix = x + padding + col * (icon_w + padding)
            iy = y + padding + row * (icon_h + padding) - int(self.scroll_offset)
            
            # Culling
            if iy + icon_h < y: continue
            if iy > y + height: break
            
            rect = rl.Rectangle(ix, iy, icon_w, icon_h)
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
            trunc_name = name if len(name) < 10 else name[:7] + "..."
            text_w = rl.measure_text(trunc_name, 10)
            rl.draw_text(trunc_name, int(ix + (icon_w - text_w)//2), int(iy + 50), 10, self.UNITY_TEXT)
            
            # Drag logic
            if entry_type == "file" and self.drag_start_pos and is_hover:
                if rl.vector2_distance(self.drag_start_pos, mouse_pos) > 5:
                    self.dragging_file = os.path.join(self.current_path, name)

        if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            self.drag_start_pos = None
            self.dragging_file = None

        if self.selected_file and self.selected_file.lower().endswith(".png"):
            button_rect = rl.Rectangle(x + width - 140, y + 6, 120, 20)
            if rl.gui_button(button_rect, "Sprite Editor"):
                if self.project_service is not None:
                    self.request_open_sprite_editor_for = self.project_service.to_relative_path(self.selected_file)
                else:
                    self.request_open_sprite_editor_for = self.selected_file

        rl.end_scissor_mode()
