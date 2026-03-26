"""
engine/editor/editor_layout.py - Gestión del layout del editor

PROPÓSITO:
    Divide la ventana en áreas rectangulares para los distintos paneles:
    - Left: Hierarchy (Resizable)
    - Right: Inspector (Resizable)
    - Center: Scene View / Game View (Tabs)
    - Bottom: Toolbar/Status

FUNCIONALIDADES:
    - Cálculo de rectángulos de UI dinámicos.
    - Splitters para redimensionar paneles.
    - Gestión de la Cámara de Editor (Pan/Zoom).
    - Transformación de coordenadas Mouse -> World.
    - Sistema de Pestañas (SCENE / GAME).
"""

from datetime import datetime, timezone
import pyray as rl
import os
from typing import Optional
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.project_panel import ProjectPanel
from engine.editor.console_panel import ConsolePanel
from engine.editor.editor_tools import EditorTool, PivotMode, SnapSettings, TransformSpace

class EditorLayout:
    
    # ========================================
    # Layout Dimensions (Unity-style)
    # ========================================
    MENU_HEIGHT: int = 20          # Barra de menú superior
    TOOLBAR_HEIGHT: int = 32       # Toolbar con herramientas + Play/Pause
    TAB_HEIGHT: int = 22           # Altura de tabs
    BOTTOM_HEIGHT: int = 180       # Panel inferior (Project + Console)
    SPLITTER_WIDTH: int = 4        # Separadores
    MIN_PANEL_WIDTH: int = 150
    MIN_BOTTOM_HEIGHT: int = 120
    MAX_BOTTOM_HEIGHT_MARGIN: int = 120
    
    # ========================================
    # Unity Colors (Exactos)
    # ========================================
    # Fondos
    UNITY_BG_DARKEST = rl.Color(30, 30, 30, 255)    # #1E1E1E - Más oscuro
    UNITY_BG_DARK = rl.Color(42, 42, 42, 255)       # #2A2A2A - Paneles
    UNITY_BG_MID = rl.Color(56, 56, 56, 255)        # #383838 - Toolbar
    UNITY_BG_LIGHT = rl.Color(64, 64, 64, 255)      # #404040 - Hover
    
    # Bordes y separadores
    UNITY_BORDER = rl.Color(25, 25, 25, 255)        # #191919
    UNITY_SPLITTER = rl.Color(35, 35, 35, 255)
    UNITY_SPLITTER_HOVER = rl.Color(70, 130, 200, 255)
    
    # Texto
    UNITY_TEXT = rl.Color(200, 200, 200, 255)       # Texto principal
    UNITY_TEXT_DIM = rl.Color(128, 128, 128, 255)   # Texto secundario
    UNITY_TEXT_BRIGHT = rl.Color(230, 230, 230, 255)
    
    # Acentos
    UNITY_BLUE = rl.Color(44, 93, 135, 255)         # Selección
    UNITY_BLUE_HOVER = rl.Color(62, 114, 160, 255)
    UNITY_TAB_ACTIVE = rl.Color(60, 60, 60, 255)    # Tab activo
    UNITY_TAB_INACTIVE = rl.Color(42, 42, 42, 255)  # Tab inactivo
    UNITY_TAB_LINE = rl.Color(58, 121, 187, 255)    # Línea azul bajo tab activo
    UNITY_DIRTY_BADGE = rl.Color(205, 133, 63, 255)
    UNITY_INVALID_BADGE = rl.Color(176, 64, 64, 255)
    UNITY_NATIVE_COMPONENT = rl.Color(79, 152, 209, 255)
    UNITY_AI_COMPONENT = rl.Color(206, 142, 58, 255)
    
    # Botones
    UNITY_BUTTON = rl.Color(72, 72, 72, 255)
    UNITY_BUTTON_HOVER = rl.Color(88, 88, 88, 255)
    UNITY_BUTTON_PRESSED = rl.Color(50, 50, 50, 255)
    
    # Aliases para compatibilidad
    BG_COLOR = UNITY_BG_MID
    PANEL_BG_COLOR = UNITY_BG_DARK
    VIEW_BG_COLOR = UNITY_BG_DARKEST
    BORDER_COLOR = UNITY_BORDER
    SPLITTER_COLOR = UNITY_SPLITTER
    SPLITTER_HOVER_COLOR = UNITY_SPLITTER_HOVER
    TAB_ACTIVE_COLOR = UNITY_TAB_ACTIVE
    TAB_INACTIVE_COLOR = UNITY_TAB_INACTIVE
    MENU_BAR_COLOR = UNITY_BG_DARK
    TEXT_COLOR = UNITY_TEXT
    
    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Tabs
        self.active_tab: str = "SCENE" # "SCENE" | "GAME" | "ANIMATOR"
        self.active_bottom_tab: str = "PROJECT" # "PROJECT" | "CONSOLE" | "TERMINAL"
        
        # Requests (Game.py lee esto)
        self.request_play: bool = False
        self.request_stop: bool = False
        self.request_pause: bool = False
        self.request_step: bool = False
        
        # Requests (Scene)
        self.request_new_scene: bool = False
        self.request_create_scene: bool = False
        self.request_save_scene: bool = False
        self.request_load_scene: bool = False
        self.request_browse_scene_file: bool = False
        self.request_activate_scene_key: str = ""
        self.request_close_scene_key: str = ""
        self.request_open_project: bool = False
        self.request_browse_project: bool = False
        self.request_create_project: bool = False
        self.request_exit_launcher: bool = False
        self.request_remove_project_path: str = ""
        self.request_create_canvas: bool = False
        self.request_create_ui_text: bool = False
        self.request_create_ui_button: bool = False
        
        # Tool selection
        self.active_tool: EditorTool = EditorTool.MOVE
        self.transform_space: TransformSpace = TransformSpace.WORLD
        self.pivot_mode: PivotMode = PivotMode.PIVOT
        self.snap_settings: SnapSettings = SnapSettings()
        self._editor_preferences_dirty: bool = False
        self.recent_projects: list[dict] = []
        self.show_project_modal: bool = False
        self.show_project_launcher: bool = False
        self.show_create_project_modal: bool = False
        self.show_create_scene_modal: bool = False
        self.show_scene_browser_modal: bool = False
        self.show_project_dirty_modal: bool = False
        self.dirty_modal_context: str = ""
        self.pending_project_path: str = ""
        self.pending_scene_open_path: str = ""
        self.pending_scene_close_key: str = ""
        self.project_switch_decision: str = ""
        self.launcher_search_text: str = ""
        self.launcher_search_focused: bool = False
        self.launcher_scroll_offset: float = 0.0
        self.launcher_feedback_text: str = ""
        self.launcher_feedback_is_error: bool = False
        self.launcher_create_name: str = "NewProject"
        self.launcher_create_name_focused: bool = False
        self.scene_create_name: str = "New Scene"
        self.scene_create_name_focused: bool = False
        self.project_scene_entries: list[dict] = []
        self.scene_browser_scroll_offset: float = 0.0
        self.scene_tabs: list[dict] = []
        self.active_scene_tab_key: str = ""
        
        # Anchos dinámicos
        self.hierarchy_width = 200
        self.inspector_width = 280
        # Estado de Resize/Drag
        self.dragging_splitter: Optional[str] = None 
        self.is_panning = False
        self.last_mouse_pos = rl.Vector2(0, 0)
        self.bottom_height = self.BOTTOM_HEIGHT
        
        # Render texture (Shared or Scene specific)
        self.scene_texture: Optional[rl.RenderTexture] = None
        # Game texture (podría ser la misma si no necesitamos ver ambas a la vez,
        # pero para transiciones suaves mejor tenerla)
        self.game_texture: Optional[rl.RenderTexture] = None
        
        # Cámara Editor
        self.editor_camera = rl.Camera2D()
        self.editor_camera.zoom = 1.0
        self.editor_camera.offset = rl.Vector2(0, 0)
        self.editor_camera.target = rl.Vector2(0, 0)
        
        # Rects
        self.hierarchy_rect = rl.Rectangle(0,0,0,0)
        self.inspector_rect = rl.Rectangle(0,0,0,0)
        self.center_rect = rl.Rectangle(0,0,0,0) # Scene/Game container
        self.bottom_rect = rl.Rectangle(0,0,0,0)
        self.bottom_header_rect = rl.Rectangle(0,0,0,0)
        self.bottom_content_rect = rl.Rectangle(0,0,0,0)
        self.bottom_splitter_rect = rl.Rectangle(0,0,0,0)
        self.splitter_left_rect = rl.Rectangle(0,0,0,0)
        self.splitter_right_rect = rl.Rectangle(0,0,0,0)
        
        # Tab Rects
        self.tab_scene_rect = rl.Rectangle(0,0,0,0)
        self.tab_game_rect = rl.Rectangle(0,0,0,0)
        self.tab_animator_rect = rl.Rectangle(0,0,0,0)
        self.btn_play_rect = rl.Rectangle(0,0,0,0)
        
        self.tab_game_rect = rl.Rectangle(0,0,0,0)
        self.btn_play_rect = rl.Rectangle(0,0,0,0)
        
        # Project / Console Panel
        self.project_panel = ProjectPanel("assets") 
        self.console_panel = ConsolePanel()
        self.terminal_panel = None
        self._text_measure_cache: dict[tuple[str, int], int] = {}
        self.launcher_search_rect = rl.Rectangle(0, 0, 0, 0)
        self.launcher_table_rect = rl.Rectangle(0, 0, 0, 0)
        self.launcher_create_name_rect = rl.Rectangle(0, 0, 0, 0)
        self.scene_create_name_rect = rl.Rectangle(0, 0, 0, 0)
        self.scene_browser_list_rect = rl.Rectangle(0, 0, 0, 0)
        self._cursor_interactive_rects: list[rl.Rectangle] = []
        self._cursor_text_rects: list[rl.Rectangle] = []
        
        self.update_layout(screen_width, screen_height)

    @property
    def current_tool(self) -> str:
        return self.active_tool.value

    @current_tool.setter
    def current_tool(self, value: str) -> None:
        self.set_active_tool(EditorTool.from_value(value))

    def set_recent_projects(self, recent_projects: list[dict]) -> None:
        self.recent_projects = list(recent_projects)
        self._clamp_launcher_scroll()

    def set_project_scene_entries(self, scene_entries: list[dict]) -> None:
        self.project_scene_entries = [dict(item) for item in scene_entries]
        self._clamp_scene_browser_scroll()

    def set_launcher_feedback(self, message: str, is_error: bool = False) -> None:
        self.launcher_feedback_text = str(message or "")
        self.launcher_feedback_is_error = bool(is_error)

    def set_scene_tabs(self, scene_tabs: list[dict], active_scene_key: str) -> None:
        self.scene_tabs = [dict(item) for item in scene_tabs]
        self.active_scene_tab_key = active_scene_key

    def set_active_tool(self, tool: EditorTool | str) -> None:
        resolved = EditorTool.from_value(tool)
        if resolved == self.active_tool:
            return
        self.active_tool = resolved
        self._editor_preferences_dirty = True

    def set_transform_space(self, space: TransformSpace | str) -> None:
        resolved = TransformSpace.from_value(space)
        if resolved == self.transform_space:
            return
        self.transform_space = resolved
        self._editor_preferences_dirty = True

    def set_pivot_mode(self, pivot_mode: PivotMode | str) -> None:
        resolved = PivotMode.from_value(pivot_mode)
        if resolved == self.pivot_mode:
            return
        self.pivot_mode = resolved
        self._editor_preferences_dirty = True

    def apply_editor_preferences(self, preferences: dict[str, object]) -> None:
        self.active_tool = EditorTool.from_value(preferences.get("editor_active_tool", EditorTool.MOVE.value))
        self.transform_space = TransformSpace.from_value(preferences.get("editor_transform_space", TransformSpace.WORLD.value))
        self.pivot_mode = PivotMode.from_value(preferences.get("editor_pivot_mode", PivotMode.PIVOT.value))
        self.snap_settings = SnapSettings.from_preferences(preferences)
        self.bottom_height = int(preferences.get("editor_bottom_panel_height", self.BOTTOM_HEIGHT) or self.BOTTOM_HEIGHT)
        self.bottom_height = self._clamp_bottom_height(self.bottom_height)
        self._editor_preferences_dirty = False

    def export_editor_preferences(self) -> dict[str, object]:
        data: dict[str, object] = {
            "editor_active_tool": self.active_tool.value,
            "editor_transform_space": self.transform_space.value,
            "editor_pivot_mode": self.pivot_mode.value,
            "editor_bottom_panel_height": int(self.bottom_height),
        }
        data.update(self.snap_settings.to_preferences())
        return data

    def consume_editor_preferences_dirty(self) -> bool:
        dirty = self._editor_preferences_dirty
        self._editor_preferences_dirty = False
        return dirty

    def update_layout(self, width: int, height: int, update_texture: bool = True) -> None:
        """Recalcula layout."""
        self.screen_width = width
        self.screen_height = height
        
        # Menu Bar takes top space (24px)
        # Toolbar is below Menu Bar
        
        top_offset = self.MENU_HEIGHT + self.TOOLBAR_HEIGHT
        bottom_height = self._clamp_bottom_height(self.bottom_height, screen_height=height)
        self.bottom_height = bottom_height
        content_height = height - top_offset - bottom_height
        
        # 1. Hierarchy (Left) - Starts below Toolbar
        self.hierarchy_rect = rl.Rectangle(
            0, top_offset,
            self.hierarchy_width, content_height
        )
        
        # Splitter Left
        self.splitter_left_rect = rl.Rectangle(
            self.hierarchy_width, top_offset,
            self.SPLITTER_WIDTH, content_height
        )
        
        # 2. Inspector (Right)
        self.inspector_rect = rl.Rectangle(
            width - self.inspector_width, top_offset,
            self.inspector_width, content_height
        )
        
        # Splitter Right
        self.splitter_right_rect = rl.Rectangle(
            width - self.inspector_width - self.SPLITTER_WIDTH, top_offset,
            self.SPLITTER_WIDTH, content_height
        )
        
        # 3. Center View (Reference for Scene and Game)
        center_x = self.hierarchy_width + self.SPLITTER_WIDTH
        center_right = width - self.inspector_width - self.SPLITTER_WIDTH
        center_width = center_right - center_x
        
        self.center_rect = rl.Rectangle(
            center_x, top_offset,
            center_width, content_height
        )

        # Center header layout: fixed view tabs + scene workspace tabs.
        tab_y = top_offset + 2
        tab_h = self.TAB_HEIGHT - 4
        tab_x = center_x + 4
        self.tab_scene_rect = rl.Rectangle(tab_x, tab_y, 74, tab_h)
        self.tab_game_rect = rl.Rectangle(tab_x + 78, tab_y, 74, tab_h)
        self.tab_animator_rect = rl.Rectangle(tab_x + 156, tab_y, 92, tab_h)
        # Play is handled directly by toolbar buttons; keep this rect inert.
        self.btn_play_rect = rl.Rectangle(0, 0, 0, 0)
        
        # 4. Bottom
        self.bottom_rect = rl.Rectangle(
            0, height - bottom_height,
            width, bottom_height
        )
        self.bottom_header_rect = rl.Rectangle(
            0, height - bottom_height,
            width, self.TAB_HEIGHT
        )
        self.bottom_content_rect = rl.Rectangle(
            0, self.bottom_header_rect.y + self.bottom_header_rect.height,
            width, bottom_height - self.TAB_HEIGHT
        )
        self.bottom_splitter_rect = rl.Rectangle(
            0, self.bottom_rect.y - self.SPLITTER_WIDTH,
            width, self.SPLITTER_WIDTH
        )

        self._sync_editor_camera_offset()

        if update_texture:
            view_rect = self.get_center_view_rect()
            self._resize_render_textures(int(view_rect.width), int(view_rect.height))

    def update_input(self) -> None:
        """Procesa input general (Tabs, Splitters, Camara)."""
        if self.show_project_launcher:
            self._handle_launcher_input()
            return
        if self.show_create_scene_modal:
            self._handle_create_scene_input()
            return
        if self.show_scene_browser_modal:
            self._handle_scene_browser_input()
            return
        if self.project_panel:
             pass
        self._handle_tool_shortcuts()
        mouse_pos = rl.get_mouse_position()
        
        # Guard: Skip toolbar/tab processing if mouse is in inspector or hierarchy
        mouse_in_inspector = rl.check_collision_point_rec(mouse_pos, self.inspector_rect)
        mouse_in_hierarchy = rl.check_collision_point_rec(mouse_pos, self.hierarchy_rect)
        mouse_in_bottom = rl.check_collision_point_rec(mouse_pos, self.bottom_rect)
        self.handle_bottom_tab_input(mouse_pos)
        
        # A. Toolbar / Tabs interaction (only if NOT clicking in panels)
        if not mouse_in_inspector and not mouse_in_hierarchy and not mouse_in_bottom:
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if rl.check_collision_point_rec(mouse_pos, self.tab_scene_rect):
                    self.active_tab = "SCENE"
                elif rl.check_collision_point_rec(mouse_pos, self.tab_game_rect):
                    self.active_tab = "GAME"
                elif rl.check_collision_point_rec(mouse_pos, self.tab_animator_rect):
                    self.active_tab = "ANIMATOR"
                elif rl.check_collision_point_rec(mouse_pos, self.btn_play_rect):
                    self.request_play = True
        
        # B. Splitter Logic
        # Si ya estamos arrastrando, continuar
        if self.dragging_splitter:
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self.dragging_splitter = None
            else:
                if self.dragging_splitter == 'left':
                    new_width = mouse_pos.x
                    if new_width < self.MIN_PANEL_WIDTH: new_width = self.MIN_PANEL_WIDTH
                    if new_width > self.screen_width - self.inspector_width - 100: new_width = self.screen_width - self.inspector_width - 100
                    self.hierarchy_width = int(new_width)
                    
                elif self.dragging_splitter == 'right':
                    new_width = self.screen_width - mouse_pos.x
                    if new_width < self.MIN_PANEL_WIDTH: new_width = self.MIN_PANEL_WIDTH
                    if new_width > self.screen_width - self.hierarchy_width - 100: new_width = self.screen_width - self.hierarchy_width - 100
                    self.inspector_width = int(new_width)
                elif self.dragging_splitter == 'bottom':
                    new_height = self.screen_height - mouse_pos.y
                    self.bottom_height = self._clamp_bottom_height(int(new_height))
                    self._editor_preferences_dirty = True
                    
                self.update_layout(self.screen_width, self.screen_height, update_texture=True)
                return 

        hover_left = rl.check_collision_point_rec(mouse_pos, self.splitter_left_rect)
        hover_right = rl.check_collision_point_rec(mouse_pos, self.splitter_right_rect)
        hover_bottom = rl.check_collision_point_rec(mouse_pos, self.bottom_splitter_rect)
        
        if (hover_left or hover_right or hover_bottom) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if hover_bottom:
                self.dragging_splitter = 'bottom'
            else:
                self.dragging_splitter = 'left' if hover_left else 'right'
            return

        # C. Camera Logic (Only if SCENE tab active)
        if self.active_tab == "SCENE":
            is_hover_view = rl.check_collision_point_rec(mouse_pos, self.get_center_view_rect())
            
            if is_hover_view or self.is_panning:
                wheel = rl.get_mouse_wheel_move()
                if wheel != 0:
                    zoom_speed = 0.1
                    self.editor_camera.zoom += wheel * zoom_speed
                    if self.editor_camera.zoom < 0.1: self.editor_camera.zoom = 0.1
                    if self.editor_camera.zoom > 5.0: self.editor_camera.zoom = 5.0

                hand_pan_pressed = self.active_tool == EditorTool.HAND and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
                if hand_pan_pressed or rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT) or rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_MIDDLE):
                    self.is_panning = True
                    self.last_mouse_pos = mouse_pos
                    
                if self.is_panning:
                    hand_pan_active = self.active_tool == EditorTool.HAND and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT)
                    if hand_pan_active or rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT) or rl.is_mouse_button_down(rl.MOUSE_BUTTON_MIDDLE):
                        delta_x = mouse_pos.x - self.last_mouse_pos.x
                        delta_y = mouse_pos.y - self.last_mouse_pos.y
                        
                        self.editor_camera.target.x -= delta_x * (1.0/self.editor_camera.zoom)
                        self.editor_camera.target.y -= delta_y * (1.0/self.editor_camera.zoom)
                        
                        self.last_mouse_pos = mouse_pos
                    else:
                        self.is_panning = False

    def _handle_tool_shortcuts(self) -> None:
        if rl.is_key_pressed(rl.KEY_Q):
            self.set_active_tool(EditorTool.HAND)
        if rl.is_key_pressed(rl.KEY_W):
            self.set_active_tool(EditorTool.MOVE)
        if rl.is_key_pressed(rl.KEY_E):
            self.set_active_tool(EditorTool.ROTATE)
        if rl.is_key_pressed(rl.KEY_R):
            self.set_active_tool(EditorTool.SCALE)
        if rl.is_key_pressed(rl.KEY_T):
            self.set_active_tool(EditorTool.TRANSFORM)

    def _handle_launcher_input(self) -> None:
        mouse = rl.get_mouse_position()

        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.launcher_search_focused = rl.check_collision_point_rec(mouse, self.launcher_search_rect)
            if self.show_create_project_modal:
                self.launcher_create_name_focused = rl.check_collision_point_rec(mouse, self.launcher_create_name_rect)
            else:
                self.launcher_create_name_focused = False

        if rl.check_collision_point_rec(mouse, self.launcher_table_rect):
            self.launcher_scroll_offset -= rl.get_mouse_wheel_move() * 28
            self._clamp_launcher_scroll()

        if self.show_create_project_modal:
            if rl.is_key_pressed(rl.KEY_ESCAPE):
                self.show_create_project_modal = False
                self.launcher_create_name_focused = False
                return
            if self.launcher_create_name_focused:
                if rl.is_key_pressed(rl.KEY_BACKSPACE) and self.launcher_create_name:
                    self.launcher_create_name = self.launcher_create_name[:-1]
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
                    if char.isprintable() and len(self.launcher_create_name) < 64:
                        self.launcher_create_name += char
                if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
                    self.request_create_project = True
            return

        if self.launcher_search_focused:
            if rl.is_key_pressed(rl.KEY_BACKSPACE) and self.launcher_search_text:
                self.launcher_search_text = self.launcher_search_text[:-1]
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
                if char.isprintable() and len(self.launcher_search_text) < 64:
                    self.launcher_search_text += char
            self.launcher_scroll_offset = 0.0
            self._clamp_launcher_scroll()

    def _handle_scene_browser_input(self) -> None:
        mouse = rl.get_mouse_position()
        if rl.is_key_pressed(rl.KEY_ESCAPE):
            self.show_scene_browser_modal = False
            self.pending_scene_open_path = ""
            return
        if rl.check_collision_point_rec(mouse, self.scene_browser_list_rect):
            self.scene_browser_scroll_offset -= rl.get_mouse_wheel_move() * 28
            self._clamp_scene_browser_scroll()

    def _handle_create_scene_input(self) -> None:
        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.scene_create_name_focused = rl.check_collision_point_rec(mouse, self.scene_create_name_rect)
        if rl.is_key_pressed(rl.KEY_ESCAPE):
            self.show_create_scene_modal = False
            self.scene_create_name_focused = False
            return
        if not self.scene_create_name_focused:
            return
        if rl.is_key_pressed(rl.KEY_BACKSPACE) and self.scene_create_name:
            self.scene_create_name = self.scene_create_name[:-1]
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
            if char.isprintable() and len(self.scene_create_name) < 64:
                self.scene_create_name += char
        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self.request_create_scene = True

    # Alias para compatibilidad con código anterior que llamaba update_camera_input
    def update_camera_input(self) -> None:
        self.update_input()

    def get_scene_mouse_pos(self) -> rl.Vector2:
        screen_mouse = rl.get_mouse_position()
        view_rect = self.get_center_view_rect()
        local_pos = rl.Vector2(
            screen_mouse.x - view_rect.x,
            screen_mouse.y - view_rect.y
        )
        return rl.get_screen_to_world_2d(local_pos, self.editor_camera)

    def get_scene_overlay_mouse_pos(self) -> rl.Vector2:
        screen_mouse = rl.get_mouse_position()
        view_rect = self.get_center_view_rect()
        return rl.Vector2(
            screen_mouse.x - view_rect.x,
            screen_mouse.y - view_rect.y,
        )

    def is_mouse_in_scene_view(self) -> bool:
        if self.active_tab != "SCENE":
            return False
        mouse = rl.get_mouse_position()
        return rl.check_collision_point_rec(mouse, self.get_center_view_rect())
    
    def is_mouse_in_inspector(self) -> bool:
        """Returns True if the mouse is over the inspector panel."""
        return rl.check_collision_point_rec(rl.get_mouse_position(), self.inspector_rect)

    def _resize_render_textures(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0: return
        
        # Scene Texture
        should_resize = True
        if self.scene_texture and self.scene_texture.texture.width == width and self.scene_texture.texture.height == height:
            should_resize = False
            
        if should_resize:
            if self.scene_texture: rl.unload_render_texture(self.scene_texture)
            self.scene_texture = rl.load_render_texture(width, height)
            
            if self.game_texture: rl.unload_render_texture(self.game_texture)
            self.game_texture = rl.load_render_texture(width, height)

    def begin_scene_render(self) -> None:
        if self.scene_texture:
            rl.begin_texture_mode(self.scene_texture)
            rl.clear_background(self.VIEW_BG_COLOR)

    def end_scene_render(self) -> None:
        if self.scene_texture:
            rl.end_texture_mode()

    def begin_scene_camera_pass(self, draw_grid: bool = False) -> None:
        if self.scene_texture:
            rl.begin_mode_2d(self.editor_camera)
            if draw_grid:
                self._draw_grid_2d()

    def end_scene_camera_pass(self) -> None:
        if self.scene_texture:
            rl.end_mode_2d()

    def begin_game_render(self) -> None:
        if self.game_texture:
            rl.begin_texture_mode(self.game_texture)
            rl.clear_background(rl.BLACK)
            # No configuramos cámara aquí, el RenderSystem del juego usará su propia cámara lógica
            # o podemos establecer una cámara de juego por defecto

    def end_game_render(self) -> None:
        if self.game_texture:
            rl.end_texture_mode()

    def draw_layout(self, is_playing: bool) -> None:
        """Dibuja el layout completo del editor."""
        self._reset_cursor_regions()
        rl.clear_background(self.UNITY_BG_DARKEST)
        
        # ========================================
        # 1. Menu Bar (Top)
        # ========================================
        self._draw_menu_bar()
        
        # ========================================
        # 2. Toolbar (Below Menu)
        # ========================================
        self._draw_toolbar(is_playing)
        
        # ========================================
        # 3. Panel Backgrounds
        # ========================================
        # Hierarchy panel background
        rl.draw_rectangle_rec(self.hierarchy_rect, self.UNITY_BG_DARK)
        rl.draw_line(int(self.hierarchy_rect.x + self.hierarchy_rect.width), 
                     int(self.hierarchy_rect.y),
                     int(self.hierarchy_rect.x + self.hierarchy_rect.width),
                     int(self.hierarchy_rect.y + self.hierarchy_rect.height),
                     self.UNITY_BORDER)
        
        # Inspector panel background
        rl.draw_rectangle_rec(self.inspector_rect, self.UNITY_BG_DARK)
        rl.draw_line(int(self.inspector_rect.x), 
                     int(self.inspector_rect.y),
                     int(self.inspector_rect.x),
                     int(self.inspector_rect.y + self.inspector_rect.height),
                     self.UNITY_BORDER)
        
        # ========================================
        # 4. Scene Workspace Tabs
        # ========================================
        tab_bar_y = self.MENU_HEIGHT + self.TOOLBAR_HEIGHT
        tab_bar_height = self.TAB_HEIGHT
        
        # Tab bar background
        tab_bar_x = int(self.center_rect.x)
        tab_bar_width = int(self.center_rect.width)
        rl.draw_rectangle(tab_bar_x, tab_bar_y, tab_bar_width, tab_bar_height, self.UNITY_BG_DARK)
        
        workspace_tab_x = self._draw_center_view_tabs(tab_bar_x, tab_bar_y, tab_bar_height)
        self._draw_scene_workspace_tabs(workspace_tab_x, tab_bar_y, tab_bar_height, tab_bar_x + tab_bar_width - 8)
        
        # ========================================
        # 5. Scene/Game View Content
        # ========================================
        # Adjust center_rect to account for tabs
        view_rect = rl.Rectangle(
            self.center_rect.x,
            self.center_rect.y + self.TAB_HEIGHT,
            self.center_rect.width,
            self.center_rect.height - self.TAB_HEIGHT
        )
        
        target_tex = None
        if self.active_tab == "SCENE":
            target_tex = self.scene_texture
        elif self.active_tab == "GAME":
            target_tex = self.game_texture

        if target_tex:
            source = rl.Rectangle(0, 0, target_tex.texture.width, -target_tex.texture.height)
            rl.draw_texture_pro(target_tex.texture, source, view_rect, rl.Vector2(0,0), 0.0, rl.WHITE)
        else:
            rl.draw_rectangle_rec(view_rect, self.VIEW_BG_COLOR)
        
        rl.draw_rectangle_lines_ex(view_rect, 1, self.UNITY_BORDER)
        
        # ========================================
        # 6. Splitters
        # ========================================
        self._draw_splitters()
        
        # ========================================
        # 7. Bottom Area (Project / Console / Terminal)
        # ========================================
        rl.draw_rectangle_rec(self.bottom_rect, self.UNITY_BG_DARK)
        rl.draw_line(0, int(self.bottom_rect.y), self.screen_width, int(self.bottom_rect.y), self.UNITY_BORDER)
        
        # Draw Content
        if self.active_bottom_tab == "PROJECT" and self.project_panel:
            self.project_panel.render(
                int(self.bottom_content_rect.x), 
                int(self.bottom_content_rect.y), 
                int(self.bottom_content_rect.width), 
                int(self.bottom_content_rect.height)
            )
            # Drag Ghost
            if self.project_panel.dragging_file:
                mouse = rl.get_mouse_position()
                rl.draw_rectangle(int(mouse.x), int(mouse.y), 20, 20, rl.Color(255, 255, 255, 128))
                rl.draw_text(
                    os.path.basename(self.project_panel.dragging_file), 
                    int(mouse.x + 25), int(mouse.y), 10, rl.WHITE
                )
        elif self.active_bottom_tab == "CONSOLE" and self.console_panel:
            self.console_panel.render(
                int(self.bottom_content_rect.x), 
                int(self.bottom_content_rect.y), 
                int(self.bottom_content_rect.width), 
                int(self.bottom_content_rect.height)
            )
        elif self.active_bottom_tab == "TERMINAL" and self.terminal_panel is not None:
            self.terminal_panel.render(
                int(self.bottom_content_rect.x),
                int(self.bottom_content_rect.y),
                int(self.bottom_content_rect.width),
                int(self.bottom_content_rect.height),
            )

        self.draw_bottom_tabs()

        if self.show_project_modal:
            self._draw_project_modal()
        if self.show_create_scene_modal:
            self._draw_create_scene_modal()
        if self.show_scene_browser_modal:
            self._draw_scene_browser_modal()
        if self.show_project_dirty_modal:
            self._draw_project_dirty_modal()

    def draw_project_launcher(self) -> None:
        self._reset_cursor_regions()
        rl.clear_background(self.UNITY_BG_DARKEST)
        padding = 24
        top_y = 28

        rl.draw_text("Projects", padding, top_y, 28, self.UNITY_TEXT_BRIGHT)
        rl.draw_text(
            "Busca, registra o crea proyectos para entrar al editor",
            padding,
            top_y + 34,
            10,
            self.UNITY_TEXT_DIM,
        )

        search_w = 280
        search_rect = rl.Rectangle(float(self.screen_width - padding - 540), float(top_y - 2), float(search_w), 32.0)
        add_rect = rl.Rectangle(float(self.screen_width - padding - 244), float(top_y - 2), 92.0, 32.0)
        new_rect = rl.Rectangle(float(self.screen_width - padding - 144), float(top_y - 2), 144.0, 32.0)
        self.launcher_search_rect = search_rect

        self._draw_launcher_text_input(search_rect, self.launcher_search_text, "Search", self.launcher_search_focused)

        if self._draw_launcher_button(add_rect, "Add", self.UNITY_BUTTON, self.UNITY_BUTTON_HOVER):
            self.request_browse_project = True
        if self._draw_launcher_button(new_rect, "+ New project", self.UNITY_BLUE, self.UNITY_BLUE_HOVER):
            self.show_create_project_modal = True
            self.launcher_create_name = "NewProject"
            self.launcher_create_name_focused = True
            self.launcher_feedback_text = ""

        if self.launcher_feedback_text:
            feedback_color = self.UNITY_INVALID_BADGE if self.launcher_feedback_is_error else self.UNITY_TEXT
            rl.draw_text(self.launcher_feedback_text, padding, top_y + 58, 10, feedback_color)

        panel_y = 96
        panel_h = self.screen_height - panel_y - 24
        panel = rl.Rectangle(float(padding), float(panel_y), float(self.screen_width - padding * 2), float(panel_h))
        rl.draw_rectangle_rec(panel, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(panel, 1, self.UNITY_BORDER)

        header_h = 40
        rl.draw_rectangle(int(panel.x), int(panel.y), int(panel.width), header_h, self.UNITY_BG_MID)
        name_x = int(panel.x + 18)
        path_x = int(panel.x + panel.width * 0.42)
        activity_x = int(panel.x + panel.width * 0.78)
        version_x = int(panel.x + panel.width * 0.90)
        rl.draw_text("Name", name_x, int(panel.y + 12), 12, self.UNITY_TEXT_BRIGHT)
        rl.draw_text("Path", path_x, int(panel.y + 12), 12, self.UNITY_TEXT_BRIGHT)
        rl.draw_text("Activity", activity_x, int(panel.y + 12), 12, self.UNITY_TEXT_BRIGHT)
        rl.draw_text("Editor version", version_x, int(panel.y + 12), 12, self.UNITY_TEXT_BRIGHT)

        table_rect = rl.Rectangle(panel.x + 1, panel.y + header_h, panel.width - 2, panel.height - header_h - 1)
        self.launcher_table_rect = table_rect
        row_h = 54
        filtered = self._filtered_launcher_projects()
        self._clamp_launcher_scroll()
        max_scroll = max(0.0, len(filtered) * row_h - table_rect.height)
        if self.launcher_scroll_offset > max_scroll:
            self.launcher_scroll_offset = max_scroll
        start_index = int(self.launcher_scroll_offset // row_h)
        offset_y = self.launcher_scroll_offset % row_h
        row_y = table_rect.y - offset_y
        mouse = rl.get_mouse_position()

        if not filtered:
            empty_message = "No projects match the current search" if self.launcher_search_text.strip() else "No projects registered yet"
            rl.draw_text(empty_message, int(table_rect.x + 18), int(table_rect.y + 20), 12, self.UNITY_TEXT_DIM)

        for index in range(start_index, len(filtered)):
            item = filtered[index]
            if row_y >= table_rect.y + table_rect.height:
                break
            if row_y + row_h <= table_rect.y:
                row_y += row_h
                continue

            row_rect = rl.Rectangle(table_rect.x, row_y, table_rect.width, float(row_h))
            self._register_cursor_rect(row_rect)
            hover = rl.check_collision_point_rec(mouse, row_rect)
            bg = self.UNITY_BG_LIGHT if hover else self.UNITY_BG_DARK
            rl.draw_rectangle_rec(row_rect, bg)
            rl.draw_line(int(row_rect.x), int(row_rect.y + row_rect.height - 1), int(row_rect.x + row_rect.width), int(row_rect.y + row_rect.height - 1), self.UNITY_BORDER)

            name = str(item.get("name", "Project"))
            path = str(item.get("path", ""))
            status = str(item.get("status", "valid"))
            activity = self._format_launcher_activity(str(item.get("activity_utc", "")))
            version = str(item.get("engine_version", ""))
            rl.draw_text(name, int(row_rect.x + 18), int(row_rect.y + 9), 14, self.UNITY_TEXT_BRIGHT)
            rl.draw_text(path, int(path_x), int(row_rect.y + 19), 10, self.UNITY_TEXT_DIM)
            rl.draw_text(activity, int(activity_x), int(row_rect.y + 19), 10, self.UNITY_TEXT)
            rl.draw_text(version, int(version_x), int(row_rect.y + 19), 10, self.UNITY_TEXT)

            row_action_consumed = False
            if status != "valid":
                badge_color = self.UNITY_INVALID_BADGE
                badge_rect = rl.Rectangle(row_rect.x + 18, row_rect.y + 30, 74, 16)
                rl.draw_rectangle_rec(badge_rect, badge_color)
                rl.draw_text(status.upper(), int(badge_rect.x + 6), int(badge_rect.y + 3), 10, self.UNITY_TEXT_BRIGHT)
                remove_rect = rl.Rectangle(row_rect.x + row_rect.width - 82, row_rect.y + 14, 64, 24)
                if self._draw_launcher_button(remove_rect, "Remove", self.UNITY_BUTTON, self.UNITY_BUTTON_HOVER):
                    self.request_remove_project_path = path
                    row_action_consumed = True

            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and not row_action_consumed and status == "valid":
                self.pending_project_path = path

            row_y += row_h

        footer_y = int(self.screen_height - 34)
        if self._draw_launcher_button(rl.Rectangle(float(padding), float(footer_y), 82.0, 28.0), "Exit", self.UNITY_BUTTON, self.UNITY_BUTTON_HOVER):
            self.request_exit_launcher = True

        if self.show_create_project_modal:
            self._draw_create_project_modal()

    def _filtered_launcher_projects(self) -> list[dict]:
        query = self.launcher_search_text.strip().lower()
        if not query:
            return list(self.recent_projects)
        return [item for item in self.recent_projects if query in str(item.get("name", "")).lower()]

    def _clamp_launcher_scroll(self) -> None:
        total_rows = len(self._filtered_launcher_projects())
        row_height = 54.0
        max_scroll = max(0.0, total_rows * row_height - self.launcher_table_rect.height)
        self.launcher_scroll_offset = max(0.0, min(self.launcher_scroll_offset, max_scroll))

    def _clamp_scene_browser_scroll(self) -> None:
        total_rows = len(self.project_scene_entries)
        row_height = 48.0
        max_scroll = max(0.0, total_rows * row_height - self.scene_browser_list_rect.height)
        self.scene_browser_scroll_offset = max(0.0, min(self.scene_browser_scroll_offset, max_scroll))

    def _draw_launcher_button(self, rect: rl.Rectangle, label: str, bg: rl.Color, hover_bg: rl.Color) -> bool:
        self._register_cursor_rect(rect)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), rect)
        rl.draw_rectangle_rec(rect, hover_bg if hover else bg)
        rl.draw_rectangle_lines_ex(rect, 1, self.UNITY_BORDER)
        text_w = self._measure_text(label, 10)
        rl.draw_text(label, int(rect.x + (rect.width - text_w) / 2), int(rect.y + 10), 10, self.UNITY_TEXT_BRIGHT)
        return hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)

    def _draw_launcher_text_input(self, rect: rl.Rectangle, value: str, placeholder: str, focused: bool) -> None:
        self._register_text_rect(rect)
        border = self.UNITY_BLUE_HOVER if focused else self.UNITY_BORDER
        rl.draw_rectangle_rec(rect, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(rect, 1, border)
        text = value if value else placeholder
        color = self.UNITY_TEXT if value else self.UNITY_TEXT_DIM
        rl.draw_text(text, int(rect.x + 10), int(rect.y + 10), 10, color)
        if focused:
            cursor_x = int(rect.x + 10 + self._measure_text(value, 10))
            rl.draw_text("_", cursor_x, int(rect.y + 10), 10, self.UNITY_TEXT_BRIGHT)

    def _format_launcher_activity(self, value: str) -> str:
        if not value:
            return "-"
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return value
        now = datetime.now(timezone.utc)
        delta = now - timestamp.astimezone(timezone.utc)
        days = max(0, delta.days)
        if days == 0:
            return "today"
        if days == 1:
            return "1 day ago"
        if days < 30:
            return f"{days} days ago"
        months = max(1, days // 30)
        if months == 1:
            return "1 month ago"
        return f"{months} months ago"

    def _draw_create_project_modal(self) -> None:
        rl.draw_rectangle(0, 0, self.screen_width, self.screen_height, rl.Color(0, 0, 0, 165))
        modal = rl.Rectangle(self.screen_width / 2 - 250, self.screen_height / 2 - 120, 500, 240)
        rl.draw_rectangle_rec(modal, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(modal, 1, self.UNITY_BORDER)
        rl.draw_text("Create New Project", int(modal.x + 18), int(modal.y + 16), 18, self.UNITY_TEXT_BRIGHT)

        rl.draw_text("Project name", int(modal.x + 18), int(modal.y + 62), 10, self.UNITY_TEXT)
        name_rect = rl.Rectangle(modal.x + 18, modal.y + 82, modal.width - 36, 32)
        self.launcher_create_name_rect = name_rect
        self._draw_launcher_text_input(name_rect, self.launcher_create_name, "NewProject", self.launcher_create_name_focused)

        rl.draw_text("Template", int(modal.x + 18), int(modal.y + 126), 10, self.UNITY_TEXT)
        rl.draw_text("Empty", int(modal.x + 120), int(modal.y + 126), 10, self.UNITY_TEXT_BRIGHT)

        preview_name = self.launcher_create_name.strip() or "NewProject"
        preview_name = preview_name.replace("\\", "").replace("/", "")
        rl.draw_text("Location", int(modal.x + 18), int(modal.y + 150), 10, self.UNITY_TEXT)
        rl.draw_text(f"projects/{preview_name}", int(modal.x + 120), int(modal.y + 150), 10, self.UNITY_TEXT_DIM)

        cancel_rect = rl.Rectangle(modal.x + modal.width - 196, modal.y + modal.height - 42, 84, 26)
        create_rect = rl.Rectangle(modal.x + modal.width - 102, modal.y + modal.height - 42, 84, 26)
        if self._draw_launcher_button(cancel_rect, "Cancel", self.UNITY_BUTTON, self.UNITY_BUTTON_HOVER):
            self.show_create_project_modal = False
            self.launcher_create_name_focused = False
        if self._draw_launcher_button(create_rect, "Create", self.UNITY_BLUE, self.UNITY_BLUE_HOVER):
            self.request_create_project = True

    def _draw_create_scene_modal(self) -> None:
        rl.draw_rectangle(0, 0, self.screen_width, self.screen_height, rl.Color(0, 0, 0, 165))
        modal = rl.Rectangle(self.screen_width / 2 - 220, self.screen_height / 2 - 110, 440, 220)
        rl.draw_rectangle_rec(modal, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(modal, 1, self.UNITY_BORDER)
        rl.draw_text("Create Scene", int(modal.x + 18), int(modal.y + 16), 18, self.UNITY_TEXT_BRIGHT)

        rl.draw_text("Scene name", int(modal.x + 18), int(modal.y + 62), 10, self.UNITY_TEXT)
        name_rect = rl.Rectangle(modal.x + 18, modal.y + 82, modal.width - 36, 32)
        self.scene_create_name_rect = name_rect
        self._draw_launcher_text_input(name_rect, self.scene_create_name, "New Scene", self.scene_create_name_focused)

        rl.draw_text("The file will be created inside levels/", int(modal.x + 18), int(modal.y + 126), 10, self.UNITY_TEXT_DIM)

        cancel_rect = rl.Rectangle(modal.x + modal.width - 196, modal.y + modal.height - 42, 84, 26)
        create_rect = rl.Rectangle(modal.x + modal.width - 102, modal.y + modal.height - 42, 84, 26)
        if self._draw_launcher_button(cancel_rect, "Cancel", self.UNITY_BUTTON, self.UNITY_BUTTON_HOVER):
            self.show_create_scene_modal = False
            self.scene_create_name_focused = False
        if self._draw_launcher_button(create_rect, "Create", self.UNITY_BLUE, self.UNITY_BLUE_HOVER):
            self.request_create_scene = True

    def _draw_scene_browser_modal(self) -> None:
        rl.draw_rectangle(0, 0, self.screen_width, self.screen_height, rl.Color(0, 0, 0, 165))
        modal = rl.Rectangle(self.screen_width / 2 - 280, self.screen_height / 2 - 190, 560, 380)
        rl.draw_rectangle_rec(modal, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(modal, 1, self.UNITY_BORDER)
        rl.draw_text("Open Scene", int(modal.x + 16), int(modal.y + 16), 18, self.UNITY_TEXT_BRIGHT)
        rl.draw_text("Scenes in the current project", int(modal.x + 16), int(modal.y + 42), 10, self.UNITY_TEXT_DIM)

        list_rect = rl.Rectangle(modal.x + 16, modal.y + 74, modal.width - 32, modal.height - 132)
        self.scene_browser_list_rect = list_rect
        rl.draw_rectangle_rec(list_rect, self.UNITY_BG_MID)
        rl.draw_rectangle_lines_ex(list_rect, 1, self.UNITY_BORDER)

        row_h = 48
        mouse = rl.get_mouse_position()
        self._clamp_scene_browser_scroll()
        row_y = int(list_rect.y - self.scene_browser_scroll_offset)
        visible_bottom = int(list_rect.y + list_rect.height)

        if not self.project_scene_entries:
            rl.draw_text("No scenes found in this project", int(list_rect.x + 12), int(list_rect.y + 14), 10, self.UNITY_TEXT_DIM)

        for scene in self.project_scene_entries:
            row_rect = rl.Rectangle(list_rect.x + 6, float(row_y), list_rect.width - 12, float(row_h - 4))
            if row_rect.y + row_rect.height < list_rect.y:
                row_y += row_h
                continue
            if row_rect.y > visible_bottom:
                break
            self._register_cursor_rect(row_rect)
            hover = rl.check_collision_point_rec(mouse, row_rect)
            rl.draw_rectangle_rec(row_rect, self.UNITY_BG_LIGHT if hover else self.UNITY_BG_DARK)
            rl.draw_text(str(scene.get("name", "Scene")), int(row_rect.x + 10), int(row_rect.y + 8), 12, self.UNITY_TEXT_BRIGHT)
            rl.draw_text(str(scene.get("path", "")), int(row_rect.x + 10), int(row_rect.y + 24), 10, self.UNITY_TEXT_DIM)
            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.pending_scene_open_path = str(scene.get("path", ""))
                self.show_scene_browser_modal = False
            row_y += row_h

        add_rect = rl.Rectangle(modal.x + 16, modal.y + modal.height - 40, 110, 24)
        close_rect = rl.Rectangle(modal.x + modal.width - 92, modal.y + modal.height - 40, 76, 24)
        self._register_cursor_rect(add_rect)
        self._register_cursor_rect(close_rect)
        if rl.gui_button(add_rect, "Add Scene"):
            self.request_browse_scene_file = True
            self.show_scene_browser_modal = False
        if rl.gui_button(close_rect, "Close"):
            self.show_scene_browser_modal = False

    def _draw_splitters(self) -> None:
        self._register_cursor_rect(self.splitter_left_rect)
        self._register_cursor_rect(self.splitter_right_rect)
        self._register_cursor_rect(self.bottom_splitter_rect)
        mouse_pos = rl.get_mouse_position()
        hover_left = rl.check_collision_point_rec(mouse_pos, self.splitter_left_rect)
        hover_right = rl.check_collision_point_rec(mouse_pos, self.splitter_right_rect)
        hover_bottom = rl.check_collision_point_rec(mouse_pos, self.bottom_splitter_rect)
        
        col_left = self.SPLITTER_HOVER_COLOR if hover_left or self.dragging_splitter == 'left' else self.SPLITTER_COLOR
        col_right = self.SPLITTER_HOVER_COLOR if hover_right or self.dragging_splitter == 'right' else self.SPLITTER_COLOR
        col_bottom = self.SPLITTER_HOVER_COLOR if hover_bottom or self.dragging_splitter == 'bottom' else self.SPLITTER_COLOR
        
        rl.draw_rectangle_rec(self.splitter_left_rect, col_left)
        rl.draw_rectangle_rec(self.splitter_right_rect, col_right)
        rl.draw_rectangle_rec(self.bottom_splitter_rect, col_bottom)

    def _draw_toolbar(self, is_playing: bool) -> None:
        """Dibuja el toolbar estilo Unity con herramientas y controles de play."""
        toolbar_y = self.MENU_HEIGHT
        
        # Fondo del toolbar
        rl.draw_rectangle(0, toolbar_y, self.screen_width, self.TOOLBAR_HEIGHT, self.UNITY_BG_MID)
        rl.draw_line(0, toolbar_y + self.TOOLBAR_HEIGHT - 1, self.screen_width, 
                     toolbar_y + self.TOOLBAR_HEIGHT - 1, self.UNITY_BORDER)
        
        # ========================================
        # IZQUIERDA: Herramientas de transformación
        # ========================================
        tool_x = 8
        tool_y = toolbar_y + 4
        tool_size = 24
        tool_spacing = 2
        
        tools = [
            ("Q", EditorTool.HAND),
            ("W", EditorTool.MOVE),
            ("E", EditorTool.ROTATE),
            ("R", EditorTool.SCALE),
            ("T", EditorTool.TRANSFORM),
        ]
        
        for shortcut, tool in tools:
            rect = rl.Rectangle(tool_x, tool_y, tool_size, tool_size)
            self._register_cursor_rect(rect)
            is_active = self.active_tool == tool
            
            # Toggle manual (sin punteros)
            mouse_pos = rl.get_mouse_position()
            is_hover = rl.check_collision_point_rec(mouse_pos, rect)
            
            # Colores
            if is_active:
                bg_color = self.UNITY_BLUE
            elif is_hover:
                bg_color = self.UNITY_BUTTON_HOVER
            else:
                bg_color = self.UNITY_BUTTON
            
            rl.draw_rectangle_rec(rect, bg_color)
            
            # Texto centrado
            text_w = self._measure_text(shortcut, 10)
            text_x = int(tool_x + (tool_size - text_w) // 2)
            text_y = int(tool_y + (tool_size - 10) // 2)
            rl.draw_text(shortcut, text_x, text_y, 10, self.UNITY_TEXT)
            
            # Click
            if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.set_active_tool(tool)
            
            tool_x += tool_size + tool_spacing

        toggle_x = tool_x + 10
        toggle_y = tool_y + 2
        toggle_h = 20
        toggle_gap = 4
        toggle_x = self._draw_toolbar_toggle(toggle_x, toggle_y, "World", self.transform_space == TransformSpace.WORLD, lambda: self.set_transform_space(TransformSpace.WORLD), height=toggle_h)
        toggle_x += toggle_gap
        toggle_x = self._draw_toolbar_toggle(toggle_x, toggle_y, "Local", self.transform_space == TransformSpace.LOCAL, lambda: self.set_transform_space(TransformSpace.LOCAL), height=toggle_h)
        toggle_x += 12
        toggle_x = self._draw_toolbar_toggle(toggle_x, toggle_y, "Pivot", self.pivot_mode == PivotMode.PIVOT, lambda: self.set_pivot_mode(PivotMode.PIVOT), height=toggle_h)
        toggle_x += toggle_gap
        self._draw_toolbar_toggle(toggle_x, toggle_y, "Center", self.pivot_mode == PivotMode.CENTER, lambda: self.set_pivot_mode(PivotMode.CENTER), height=toggle_h)
        
        # ========================================
        # CENTRO: Play / Pause / Step
        # ========================================
        center_x = self.screen_width // 2
        btn_width = 32
        btn_height = 24
        play_y = toolbar_y + 4
        
        # Play button
        play_rect = rl.Rectangle(center_x - btn_width - 20, play_y, btn_width, btn_height)
        self._register_cursor_rect(play_rect)
        play_text = "||" if is_playing else ">"  # Pause o Play symbol
        if rl.gui_button(play_rect, play_text):
            self.request_play = True
        
        # Pause button (solo visible durante play)
        pause_rect = rl.Rectangle(center_x - btn_width//2, play_y, btn_width, btn_height)
        self._register_cursor_rect(pause_rect)
        if rl.gui_button(pause_rect, "||"):
            self.request_pause = True
        
        # Step button
        step_rect = rl.Rectangle(center_x + 20, play_y, btn_width, btn_height)
        self._register_cursor_rect(step_rect)
        if rl.gui_button(step_rect, ">|"):
            self.request_step = True
        
        # ========================================
        # DERECHA: Opciones
        # ========================================
        right_x = self.screen_width - 200
        
        # Layers dropdown (placeholder)
        rl.gui_label(rl.Rectangle(right_x, play_y, 50, btn_height), "Layers")
        right_x += 55
        
        # Layout dropdown (placeholder)
        rl.gui_label(rl.Rectangle(right_x, play_y, 50, btn_height), "Default")
        
        # ========================================
        # SCENE FILE BUTTONS (Right Side)
        # ========================================
        # New / Open / Save
        file_btn_w = 40
        file_x = center_x + 100
        
        if rl.gui_button(rl.Rectangle(file_x, play_y, file_btn_w, btn_height), "New"):
            self.show_create_scene_modal = True
            self.scene_create_name = "New Scene"
            self.scene_create_name_focused = True
            
        file_x += file_btn_w + 5
        if rl.gui_button(rl.Rectangle(file_x, play_y, file_btn_w, btn_height), "Open"):
            self.request_load_scene = True
            
        file_x += file_btn_w + 5
        if rl.gui_button(rl.Rectangle(file_x, play_y, file_btn_w, btn_height), "Save"):
            self.request_save_scene = True

        file_x += file_btn_w + 5
        if rl.gui_button(rl.Rectangle(file_x, play_y, 52, btn_height), "Project"):
            self.show_project_modal = True
        file_x += 57
        if rl.gui_button(rl.Rectangle(file_x, play_y, 52, btn_height), "Canvas"):
            self.request_create_canvas = True
        file_x += 57
        if rl.gui_button(rl.Rectangle(file_x, play_y, 44, btn_height), "Text"):
            self.request_create_ui_text = True
        file_x += 49
        if rl.gui_button(rl.Rectangle(file_x, play_y, 56, btn_height), "Button"):
            self.request_create_ui_button = True

    def _draw_toolbar_toggle(self, x: int, y: int, label: str, is_active: bool, on_click, height: int = 20) -> int:
        width = self._measure_text(label, 10) + 16
        rect = rl.Rectangle(x, y, width, height)
        self._register_cursor_rect(rect)
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), rect)
        bg_color = self.UNITY_BLUE if is_active else (self.UNITY_BUTTON_HOVER if hover else self.UNITY_BUTTON)
        rl.draw_rectangle_rec(rect, bg_color)
        rl.draw_rectangle_lines_ex(rect, 1, self.UNITY_BORDER)
        rl.draw_text(label, int(rect.x + 8), int(rect.y + (rect.height - 10) / 2), 10, self.UNITY_TEXT)
        if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            on_click()
        return int(x + width)
        
    def _draw_menu_bar(self) -> None:
        """Dibuja la barra de menú estilo Unity."""
        # Fondo
        rl.draw_rectangle(0, 0, self.screen_width, self.MENU_HEIGHT, self.UNITY_BG_DARK)
        rl.draw_line(0, self.MENU_HEIGHT - 1, self.screen_width, self.MENU_HEIGHT - 1, self.UNITY_BORDER)
        
        # Items de menú
        items = ["File", "Edit", "Assets", "GameObject", "Component", "Window", "Help"]
        x = 8
        
        for item in items:
            text_width = self._measure_text(item, 10)
            item_width = text_width + 12
            rect = rl.Rectangle(x, 1, item_width, self.MENU_HEIGHT - 2)
            self._register_cursor_rect(rect)
            
            # Hover detection
            mouse = rl.get_mouse_position()
            is_hover = rl.check_collision_point_rec(mouse, rect)
            
            if is_hover:
                rl.draw_rectangle_rec(rect, self.UNITY_BG_LIGHT)
            
            # Texto centrado
            text_x = x + (item_width - text_width) // 2
            rl.draw_text(item, int(text_x), 5, 10, self.UNITY_TEXT)
            
            x += item_width + 2
        
    def _draw_tab(self, text: str, rect: rl.Rectangle, is_active: bool) -> None:
        """Dibuja un tab estilo Unity con línea azul inferior si está activo."""
        # Fondo del tab
        self._register_cursor_rect(rect)
        bg_color = self.UNITY_TAB_ACTIVE if is_active else self.UNITY_TAB_INACTIVE
        rl.draw_rectangle_rec(rect, bg_color)
        
        # Línea azul inferior si está activo
        if is_active:
            line_rect = rl.Rectangle(rect.x, rect.y + rect.height - 2, rect.width, 2)
            rl.draw_rectangle_rec(line_rect, self.UNITY_TAB_LINE)
        
        # Texto centrado
        text_width = self._measure_text(text, 10)
        text_x = rect.x + (rect.width - text_width) // 2
        text_y = rect.y + (rect.height - 10) // 2
        rl.draw_text(text, int(text_x), int(text_y), 10, self.UNITY_TEXT)

    def get_bottom_content_rect(self) -> rl.Rectangle:
        return self.bottom_content_rect

    def handle_bottom_tab_input(self, mouse_pos: rl.Vector2) -> None:
        if not rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            return
        if not rl.check_collision_point_rec(mouse_pos, self.bottom_header_rect):
            return

        bottom_tab_y = int(self.bottom_header_rect.y) + 2
        bottom_tab_h = self.TAB_HEIGHT - 4
        proj_tab_rect = rl.Rectangle(self.bottom_header_rect.x + 2, bottom_tab_y, 70, bottom_tab_h)
        cons_tab_rect = rl.Rectangle(self.bottom_header_rect.x + 75, bottom_tab_y, 70, bottom_tab_h)
        term_tab_rect = rl.Rectangle(self.bottom_header_rect.x + 148, bottom_tab_y, 70, bottom_tab_h)
        self._register_cursor_rect(proj_tab_rect)
        self._register_cursor_rect(cons_tab_rect)
        self._register_cursor_rect(term_tab_rect)

        if rl.check_collision_point_rec(mouse_pos, proj_tab_rect):
            self.active_bottom_tab = "PROJECT"
        elif rl.check_collision_point_rec(mouse_pos, cons_tab_rect):
            self.active_bottom_tab = "CONSOLE"
        elif rl.check_collision_point_rec(mouse_pos, term_tab_rect):
            self.active_bottom_tab = "TERMINAL"

    def draw_bottom_tabs(self) -> None:
        rl.draw_rectangle_rec(self.bottom_header_rect, self.UNITY_BG_DARK)
        rl.draw_line(
            int(self.bottom_header_rect.x),
            int(self.bottom_header_rect.y + self.bottom_header_rect.height - 1),
            int(self.bottom_header_rect.x + self.bottom_header_rect.width),
            int(self.bottom_header_rect.y + self.bottom_header_rect.height - 1),
            self.UNITY_BORDER,
        )

        bottom_tab_y = int(self.bottom_header_rect.y) + 2
        bottom_tab_h = self.TAB_HEIGHT - 4
        proj_tab_rect = rl.Rectangle(self.bottom_header_rect.x + 2, bottom_tab_y, 70, bottom_tab_h)
        cons_tab_rect = rl.Rectangle(self.bottom_header_rect.x + 75, bottom_tab_y, 70, bottom_tab_h)
        term_tab_rect = rl.Rectangle(self.bottom_header_rect.x + 148, bottom_tab_y, 70, bottom_tab_h)

        self._draw_tab("Project", proj_tab_rect, self.active_bottom_tab == "PROJECT")
        self._draw_tab("Console", cons_tab_rect, self.active_bottom_tab == "CONSOLE")
        self._draw_tab("Terminal", term_tab_rect, self.active_bottom_tab == "TERMINAL")

    def _clamp_bottom_height(self, value: int, screen_height: int | None = None) -> int:
        height = self.screen_height if screen_height is None else int(screen_height)
        max_height = max(self.MIN_BOTTOM_HEIGHT, height - self.MENU_HEIGHT - self.TOOLBAR_HEIGHT - self.MAX_BOTTOM_HEIGHT_MARGIN)
        return max(self.MIN_BOTTOM_HEIGHT, min(int(value), max_height))

    def _draw_center_view_tabs(self, x: int, y: int, height: int) -> int:
        self._draw_tab("Scene", self.tab_scene_rect, self.active_tab == "SCENE")
        self._draw_tab("Game", self.tab_game_rect, self.active_tab == "GAME")
        self._draw_tab("Animator", self.tab_animator_rect, self.active_tab == "ANIMATOR")
        separator_x = int(self.tab_animator_rect.x + self.tab_animator_rect.width + 6)
        rl.draw_line(separator_x, y + 3, separator_x, y + height - 3, self.UNITY_BORDER)
        return separator_x + 6

    def _draw_scene_workspace_tabs(self, x: int, y: int, height: int, max_x: int) -> None:
        mouse = rl.get_mouse_position()
        tab_x = x
        tab_h = height - 4

        if not self.scene_tabs:
            rl.draw_text("No scenes open", x + 6, y + 6, 10, self.UNITY_TEXT_DIM)
            return

        for scene_tab in self.scene_tabs:
            label = str(scene_tab.get("name", "Scene"))
            key = str(scene_tab.get("key", ""))
            is_active = key == self.active_scene_tab_key
            has_invalid_links = bool(scene_tab.get("has_invalid_links", False))
            is_dirty = bool(scene_tab.get("dirty", False))
            text_width = self._measure_text(label, 10)
            tab_w = max(88, min(190, text_width + 54))
            rect = rl.Rectangle(tab_x, y + 2, tab_w, tab_h)
            self._draw_tab(label, rect, is_active)

            badge_x = rect.x + rect.width - 34
            if is_dirty:
                rl.draw_circle(int(badge_x), int(rect.y + rect.height / 2), 4, self.UNITY_DIRTY_BADGE)
                badge_x -= 12
            if has_invalid_links:
                rl.draw_circle(int(badge_x), int(rect.y + rect.height / 2), 4, self.UNITY_INVALID_BADGE)

            close_rect = rl.Rectangle(rect.x + rect.width - 16, rect.y + 3, 12, rect.height - 6)
            self._register_cursor_rect(close_rect)
            close_hover = rl.check_collision_point_rec(mouse, close_rect)
            rl.draw_text("x", int(close_rect.x + 2), int(close_rect.y + 1), 10, self.UNITY_TEXT_BRIGHT if close_hover else self.UNITY_TEXT_DIM)

            if rl.check_collision_point_rec(mouse, rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if close_hover:
                    self.request_close_scene_key = key
                else:
                    self.request_activate_scene_key = key
                    self.active_scene_tab_key = key

            tab_x += int(tab_w + 4)
            if tab_x > max_x - 110:
                break

    def _measure_text(self, text: str, size: int) -> int:
        cache_key = (str(text), int(size))
        cached = self._text_measure_cache.get(cache_key)
        if cached is not None:
            return cached
        measured = rl.measure_text(str(text), int(size))
        self._text_measure_cache[cache_key] = int(measured)
        return int(measured)

    def get_cursor_intent(self) -> CursorVisualState:
        mouse = rl.get_mouse_position()
        if (
            rl.check_collision_point_rec(mouse, self.launcher_search_rect)
            or rl.check_collision_point_rec(mouse, self.launcher_create_name_rect)
            or rl.check_collision_point_rec(mouse, self.scene_create_name_rect)
        ):
            return CursorVisualState.TEXT
        for rect in self._cursor_text_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.TEXT
        static_interactive = (
            self.tab_scene_rect,
            self.tab_game_rect,
            self.tab_animator_rect,
            self.btn_play_rect,
            self.splitter_left_rect,
            self.splitter_right_rect,
            self.bottom_splitter_rect,
        )
        for rect in static_interactive:
            if rect.width > 0 and rect.height > 0 and rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _reset_cursor_regions(self) -> None:
        self._cursor_interactive_rects = []
        self._cursor_text_rects = []

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))

    def _register_text_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_text_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))

    def get_center_view_rect(self) -> rl.Rectangle:
        return rl.Rectangle(
            self.center_rect.x,
            self.center_rect.y + self.TAB_HEIGHT,
            self.center_rect.width,
            self.center_rect.height - self.TAB_HEIGHT
        )

    def _sync_editor_camera_offset(self) -> None:
        view_rect = self.get_center_view_rect()
        self.editor_camera.offset = rl.Vector2(view_rect.width / 2, view_rect.height / 2)

    def _draw_project_modal(self) -> None:
        rl.draw_rectangle(0, 0, self.screen_width, self.screen_height, rl.Color(0, 0, 0, 150))
        modal = rl.Rectangle(self.screen_width / 2 - 260, self.screen_height / 2 - 180, 520, 360)
        rl.draw_rectangle_rec(modal, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(modal, 1, self.UNITY_BORDER)
        rl.draw_text("Open Project", int(modal.x + 12), int(modal.y + 12), 14, self.UNITY_TEXT_BRIGHT)

        item_y = int(modal.y + 44)
        valid_projects = [item for item in self.recent_projects if str(item.get("status", "valid")) == "valid"]
        if not valid_projects:
            rl.draw_text("No recent projects", int(modal.x + 12), item_y, 10, self.UNITY_TEXT_DIM)

        for item in valid_projects[:7]:
            path = str(item.get("path", ""))
            name = str(item.get("name", "Project"))
            version = str(item.get("engine_version", ""))
            row_rect = rl.Rectangle(modal.x + 12, item_y, modal.width - 24, 40)
            self._register_cursor_rect(row_rect)
            hover = rl.check_collision_point_rec(rl.get_mouse_position(), row_rect)
            rl.draw_rectangle_rec(row_rect, self.UNITY_BG_LIGHT if hover else self.UNITY_BG_MID)
            rl.draw_text(name, int(row_rect.x + 8), int(row_rect.y + 6), 12, self.UNITY_TEXT)
            rl.draw_text(path, int(row_rect.x + 8), int(row_rect.y + 22), 10, self.UNITY_TEXT_DIM)
            rl.draw_text(version, int(row_rect.x + row_rect.width - 94), int(row_rect.y + 14), 10, self.UNITY_TEXT)
            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.pending_project_path = path
                self.show_project_modal = False
            item_y += 46

        browse_rect = rl.Rectangle(modal.x + 12, modal.y + modal.height - 40, 120, 24)
        close_rect = rl.Rectangle(modal.x + modal.width - 92, modal.y + modal.height - 40, 80, 24)
        self._register_cursor_rect(browse_rect)
        self._register_cursor_rect(close_rect)
        if rl.gui_button(browse_rect, "Add Project"):
            self.request_browse_project = True
            self.show_project_modal = False
        if rl.gui_button(close_rect, "Close"):
            self.show_project_modal = False

    def _draw_project_dirty_modal(self) -> None:
        rl.draw_rectangle(0, 0, self.screen_width, self.screen_height, rl.Color(0, 0, 0, 150))
        modal = rl.Rectangle(self.screen_width / 2 - 180, self.screen_height / 2 - 80, 360, 160)
        rl.draw_rectangle_rec(modal, self.UNITY_BG_DARK)
        rl.draw_rectangle_lines_ex(modal, 1, self.UNITY_BORDER)
        title = "Unsaved changes"
        message = "Save dirty scenes before continuing?"
        if self.dirty_modal_context == "project_switch":
            message = "Save dirty scenes before switching project?"
        elif self.dirty_modal_context == "close_scene":
            message = "Save this scene before closing the tab?"
        rl.draw_text(title, int(modal.x + 12), int(modal.y + 12), 14, self.UNITY_TEXT_BRIGHT)
        rl.draw_text(message, int(modal.x + 12), int(modal.y + 50), 10, self.UNITY_TEXT)

        save_rect = rl.Rectangle(modal.x + 12, modal.y + modal.height - 38, 80, 24)
        discard_rect = rl.Rectangle(modal.x + 102, modal.y + modal.height - 38, 80, 24)
        cancel_rect = rl.Rectangle(modal.x + 192, modal.y + modal.height - 38, 80, 24)
        self._register_cursor_rect(save_rect)
        self._register_cursor_rect(discard_rect)
        self._register_cursor_rect(cancel_rect)
        if rl.gui_button(save_rect, "Save"):
            self.project_switch_decision = "save"
            self.show_project_dirty_modal = False
        if rl.gui_button(discard_rect, "Discard"):
            self.project_switch_decision = "discard"
            self.show_project_dirty_modal = False
        if rl.gui_button(cancel_rect, "Cancel"):
            self.project_switch_decision = "cancel"
            self.show_project_dirty_modal = False

    def _draw_grid_2d(self) -> None:
        # Unity Style Grid
        # Thick lines every 10 units, Thin every 1 unit
        
        # Determine visible range based on camera (Optimization)
        # For now, simplistic large grid
        
        count = 100
        spacing = 100 # pixels per unit ideally match camera zoom
        # But we work in world units.
        
        # Center lines
        rl.draw_line(-10000, 0, 10000, 0, rl.Color(100, 100, 100, 100))
        rl.draw_line(0, -10000, 0, 10000, rl.Color(100, 100, 100, 100))
        
        # Grid
        # Needs to be efficient. With Raylib rlBeginMode2D, grid is world space.
        grid_color = rl.Color(255, 255, 255, 10) # Very faint
        steps = 50
        step_size = 50
        
        for i in range(-steps, steps + 1):
             if i == 0: continue
             pos = i * step_size
             rl.draw_line(pos, -steps*step_size, pos, steps*step_size, grid_color)
             rl.draw_line(-steps*step_size, pos, steps*step_size, pos, grid_color)
