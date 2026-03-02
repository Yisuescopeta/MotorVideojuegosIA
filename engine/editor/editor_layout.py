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

import pyray as rl
import os
from typing import Optional
from engine.editor.project_panel import ProjectPanel
from engine.editor.console_panel import ConsolePanel

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
        self.active_tab: str = "SCENE" # "SCENE" | "GAME"
        self.active_bottom_tab: str = "PROJECT" # "PROJECT" | "CONSOLE"
        
        # Requests (Game.py lee esto)
        self.request_play: bool = False
        self.request_stop: bool = False
        self.request_pause: bool = False
        self.request_step: bool = False
        
        # Requests (Scene)
        self.request_new_scene: bool = False
        self.request_save_scene: bool = False
        self.request_load_scene: bool = False
        
        # Tool selection (Q=Hand, W=Move, E=Rotate, R=Scale, T=Rect)
        self.current_tool: str = "Move"
        
        # Anchos dinámicos
        self.hierarchy_width = 200
        self.inspector_width = 280
        
        # Estado de Resize/Drag
        self.dragging_splitter: Optional[str] = None 
        self.is_panning = False
        self.last_mouse_pos = rl.Vector2(0, 0)
        
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
        self.splitter_left_rect = rl.Rectangle(0,0,0,0)
        self.splitter_right_rect = rl.Rectangle(0,0,0,0)
        
        # Tab Rects
        self.tab_scene_rect = rl.Rectangle(0,0,0,0)
        self.tab_game_rect = rl.Rectangle(0,0,0,0)
        self.btn_play_rect = rl.Rectangle(0,0,0,0)
        
        self.tab_game_rect = rl.Rectangle(0,0,0,0)
        self.btn_play_rect = rl.Rectangle(0,0,0,0)
        
        # Project / Console Panel
        self.project_panel = ProjectPanel("assets") 
        self.console_panel = ConsolePanel()
        
        self.update_layout(screen_width, screen_height)

    def update_layout(self, width: int, height: int, update_texture: bool = True) -> None:
        """Recalcula layout."""
        self.screen_width = width
        self.screen_height = height
        
        # Menu Bar takes top space (24px)
        # Toolbar is below Menu Bar
        
        tab_y = self.MENU_HEIGHT + 5
        top_offset = self.MENU_HEIGHT + self.TOOLBAR_HEIGHT
        
        content_height = height - top_offset - self.BOTTOM_HEIGHT
        
        # Toolbar layout (Tabs & Buttons)
        self.tab_scene_rect = rl.Rectangle(width/2 - 100, tab_y, 80, 30)
        self.tab_game_rect = rl.Rectangle(width/2, tab_y, 80, 30)
        self.btn_play_rect = rl.Rectangle(width/2 + 100, tab_y, 60, 30)
        
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
        
        # 4. Bottom
        self.bottom_rect = rl.Rectangle(
            0, height - self.BOTTOM_HEIGHT,
            width, self.BOTTOM_HEIGHT
        )

        if update_texture:
            self._resize_render_textures(int(center_width), int(content_height))

    def update_input(self) -> None:
        """Procesa input general (Tabs, Splitters, Camara)."""
        if self.project_panel:
             pass
             
        mouse_pos = rl.get_mouse_position()
        
        # Guard: Skip toolbar/tab processing if mouse is in inspector or hierarchy
        mouse_in_inspector = rl.check_collision_point_rec(mouse_pos, self.inspector_rect)
        mouse_in_hierarchy = rl.check_collision_point_rec(mouse_pos, self.hierarchy_rect)
        mouse_in_bottom = rl.check_collision_point_rec(mouse_pos, self.bottom_rect)
        
        # A. Toolbar / Tabs interaction (only if NOT clicking in panels)
        if not mouse_in_inspector and not mouse_in_hierarchy and not mouse_in_bottom:
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if rl.check_collision_point_rec(mouse_pos, self.tab_scene_rect):
                    self.active_tab = "SCENE"
                elif rl.check_collision_point_rec(mouse_pos, self.tab_game_rect):
                    self.active_tab = "GAME"
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
                    
                self.update_layout(self.screen_width, self.screen_height, update_texture=True)
                return 

        hover_left = rl.check_collision_point_rec(mouse_pos, self.splitter_left_rect)
        hover_right = rl.check_collision_point_rec(mouse_pos, self.splitter_right_rect)
        
        if (hover_left or hover_right) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.dragging_splitter = 'left' if hover_left else 'right'
            return

        # C. Camera Logic (Only if SCENE tab active)
        if self.active_tab == "SCENE":
            is_hover_view = rl.check_collision_point_rec(mouse_pos, self.center_rect)
            
            if is_hover_view or self.is_panning:
                wheel = rl.get_mouse_wheel_move()
                if wheel != 0:
                    zoom_speed = 0.1
                    self.editor_camera.zoom += wheel * zoom_speed
                    if self.editor_camera.zoom < 0.1: self.editor_camera.zoom = 0.1
                    if self.editor_camera.zoom > 5.0: self.editor_camera.zoom = 5.0

                if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT) or rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_MIDDLE):
                    self.is_panning = True
                    self.last_mouse_pos = mouse_pos
                    
                if self.is_panning:
                    if rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT) or rl.is_mouse_button_down(rl.MOUSE_BUTTON_MIDDLE):
                        delta_x = mouse_pos.x - self.last_mouse_pos.x
                        delta_y = mouse_pos.y - self.last_mouse_pos.y
                        
                        self.editor_camera.target.x -= delta_x * (1.0/self.editor_camera.zoom)
                        self.editor_camera.target.y -= delta_y * (1.0/self.editor_camera.zoom)
                        
                        self.last_mouse_pos = mouse_pos
                    else:
                        self.is_panning = False

    # Alias para compatibilidad con código anterior que llamaba update_camera_input
    def update_camera_input(self) -> None:
        self.update_input()

    def get_scene_mouse_pos(self) -> rl.Vector2:
        screen_mouse = rl.get_mouse_position()
        # The actual scene view starts at center_rect.y + TAB_HEIGHT (tabs are drawn over center_rect)
        local_pos = rl.Vector2(
            screen_mouse.x - self.center_rect.x,
            screen_mouse.y - (self.center_rect.y + self.TAB_HEIGHT)
        )
        return rl.get_screen_to_world_2d(local_pos, self.editor_camera)

    def is_mouse_in_scene_view(self) -> bool:
        if self.active_tab != "SCENE":
            return False
        mouse = rl.get_mouse_position()
        # The actual view area is below the tab bar
        view_rect = rl.Rectangle(
            self.center_rect.x,
            self.center_rect.y + self.TAB_HEIGHT,
            self.center_rect.width,
            self.center_rect.height - self.TAB_HEIGHT
        )
        return rl.check_collision_point_rec(mouse, view_rect)
    
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
            
            if self.editor_camera.offset.x == 0:
                 self.editor_camera.offset = rl.Vector2(width/2, height/2)

    def begin_scene_render(self) -> None:
        if self.scene_texture:
            rl.begin_texture_mode(self.scene_texture)
            rl.clear_background(self.VIEW_BG_COLOR)
            rl.begin_mode_2d(self.editor_camera)
            self._draw_grid_2d()

    def end_scene_render(self) -> None:
        if self.scene_texture:
            rl.end_mode_2d()
            rl.end_texture_mode()

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
        # 4. Scene/Game View Tabs
        # ========================================
        tab_bar_y = self.MENU_HEIGHT + self.TOOLBAR_HEIGHT
        tab_bar_height = self.TAB_HEIGHT
        
        # Tab bar background
        tab_bar_x = int(self.center_rect.x)
        tab_bar_width = int(self.center_rect.width)
        rl.draw_rectangle(tab_bar_x, tab_bar_y, tab_bar_width, tab_bar_height, self.UNITY_BG_DARK)
        
        # Scene Tab
        scene_tab_rect = rl.Rectangle(tab_bar_x + 5, tab_bar_y + 2, 70, tab_bar_height - 4)
        self._draw_tab("Scene", scene_tab_rect, self.active_tab == "SCENE")
        if rl.check_collision_point_rec(rl.get_mouse_position(), scene_tab_rect):
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.active_tab = "SCENE"
        
        # Game Tab
        game_tab_rect = rl.Rectangle(tab_bar_x + 80, tab_bar_y + 2, 70, tab_bar_height - 4)
        self._draw_tab("Game", game_tab_rect, self.active_tab == "GAME")
        if rl.check_collision_point_rec(rl.get_mouse_position(), game_tab_rect):
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.active_tab = "GAME"
        
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
        
        target_tex = self.scene_texture if self.active_tab == "SCENE" else self.game_texture
        
        if target_tex:
            source = rl.Rectangle(0, 0, target_tex.texture.width, -target_tex.texture.height)
            rl.draw_texture_pro(target_tex.texture, source, view_rect, rl.Vector2(0,0), 0.0, rl.WHITE)
        
        rl.draw_rectangle_lines_ex(view_rect, 1, self.UNITY_BORDER)
        
        # ========================================
        # 6. Splitters
        # ========================================
        self._draw_splitters()
        
        # ========================================
        # 7. Bottom Area (Project / Console)
        # ========================================
        rl.draw_rectangle_rec(self.bottom_rect, self.UNITY_BG_DARK)
        rl.draw_line(0, int(self.bottom_rect.y), self.screen_width, int(self.bottom_rect.y), self.UNITY_BORDER)
        
        # Tabs for Bottom Area (drawn over the panel header)
        bottom_tab_y = int(self.bottom_rect.y) + 2
        bottom_tab_h = self.TAB_HEIGHT - 4
        
        # Project Tab
        proj_tab_rect = rl.Rectangle(self.bottom_rect.x + 2, bottom_tab_y, 70, bottom_tab_h)
        self._draw_tab("Project", proj_tab_rect, self.active_bottom_tab == "PROJECT")
        if rl.check_collision_point_rec(rl.get_mouse_position(), proj_tab_rect):
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.active_bottom_tab = "PROJECT"
                
        # Console Tab
        cons_tab_rect = rl.Rectangle(self.bottom_rect.x + 75, bottom_tab_y, 70, bottom_tab_h)
        self._draw_tab("Console", cons_tab_rect, self.active_bottom_tab == "CONSOLE")
        if rl.check_collision_point_rec(rl.get_mouse_position(), cons_tab_rect):
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.active_bottom_tab = "CONSOLE"
        
        # Draw Content
        if self.active_bottom_tab == "PROJECT" and self.project_panel:
            self.project_panel.render(
                int(self.bottom_rect.x), 
                int(self.bottom_rect.y), 
                int(self.bottom_rect.width), 
                int(self.bottom_rect.height)
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
                int(self.bottom_rect.x), 
                int(self.bottom_rect.y), 
                int(self.bottom_rect.width), 
                int(self.bottom_rect.height)
            )

    def _draw_splitters(self) -> None:
        mouse_pos = rl.get_mouse_position()
        hover_left = rl.check_collision_point_rec(mouse_pos, self.splitter_left_rect)
        hover_right = rl.check_collision_point_rec(mouse_pos, self.splitter_right_rect)
        
        col_left = self.SPLITTER_HOVER_COLOR if hover_left or self.dragging_splitter == 'left' else self.SPLITTER_COLOR
        col_right = self.SPLITTER_HOVER_COLOR if hover_right or self.dragging_splitter == 'right' else self.SPLITTER_COLOR
        
        rl.draw_rectangle_rec(self.splitter_left_rect, col_left)
        rl.draw_rectangle_rec(self.splitter_right_rect, col_right)

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
            ("Q", "Hand"),      # Pan/Navigate
            ("W", "Move"),      # Translate
            ("E", "Rotate"),    # Rotate
            ("R", "Scale"),     # Scale
            ("T", "Rect"),      # Rect Transform
        ]
        
        for shortcut, name in tools:
            rect = rl.Rectangle(tool_x, tool_y, tool_size, tool_size)
            is_active = getattr(self, 'current_tool', 'Move') == name
            
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
            text_w = rl.measure_text(shortcut, 10)
            text_x = int(tool_x + (tool_size - text_w) // 2)
            text_y = int(tool_y + (tool_size - 10) // 2)
            rl.draw_text(shortcut, text_x, text_y, 10, self.UNITY_TEXT)
            
            # Click
            if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.current_tool = name
            
            tool_x += tool_size + tool_spacing
        
        # ========================================
        # CENTRO: Play / Pause / Step
        # ========================================
        center_x = self.screen_width // 2
        btn_width = 32
        btn_height = 24
        play_y = toolbar_y + 4
        
        # Play button
        play_rect = rl.Rectangle(center_x - btn_width - 20, play_y, btn_width, btn_height)
        play_text = "||" if is_playing else ">"  # Pause o Play symbol
        if rl.gui_button(play_rect, play_text):
            self.request_play = True
        
        # Pause button (solo visible durante play)
        pause_rect = rl.Rectangle(center_x - btn_width//2, play_y, btn_width, btn_height)
        if rl.gui_button(pause_rect, "||"):
            self.request_pause = True
        
        # Step button
        step_rect = rl.Rectangle(center_x + 20, play_y, btn_width, btn_height)
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
            self.request_new_scene = True
            
        file_x += file_btn_w + 5
        if rl.gui_button(rl.Rectangle(file_x, play_y, file_btn_w, btn_height), "Open"):
            self.request_load_scene = True
            
        file_x += file_btn_w + 5
        if rl.gui_button(rl.Rectangle(file_x, play_y, file_btn_w, btn_height), "Save"):
            self.request_save_scene = True
        
    def _draw_menu_bar(self) -> None:
        """Dibuja la barra de menú estilo Unity."""
        # Fondo
        rl.draw_rectangle(0, 0, self.screen_width, self.MENU_HEIGHT, self.UNITY_BG_DARK)
        rl.draw_line(0, self.MENU_HEIGHT - 1, self.screen_width, self.MENU_HEIGHT - 1, self.UNITY_BORDER)
        
        # Items de menú
        items = ["File", "Edit", "Assets", "GameObject", "Component", "Window", "Help"]
        x = 8
        
        for item in items:
            item_width = rl.measure_text(item, 10) + 12
            rect = rl.Rectangle(x, 1, item_width, self.MENU_HEIGHT - 2)
            
            # Hover detection
            mouse = rl.get_mouse_position()
            is_hover = rl.check_collision_point_rec(mouse, rect)
            
            if is_hover:
                rl.draw_rectangle_rec(rect, self.UNITY_BG_LIGHT)
            
            # Texto centrado
            text_x = x + (item_width - rl.measure_text(item, 10)) // 2
            rl.draw_text(item, int(text_x), 5, 10, self.UNITY_TEXT)
            
            x += item_width + 2
        
    def _draw_tab(self, text: str, rect: rl.Rectangle, is_active: bool) -> None:
        """Dibuja un tab estilo Unity con línea azul inferior si está activo."""
        # Fondo del tab
        bg_color = self.UNITY_TAB_ACTIVE if is_active else self.UNITY_TAB_INACTIVE
        rl.draw_rectangle_rec(rect, bg_color)
        
        # Línea azul inferior si está activo
        if is_active:
            line_rect = rl.Rectangle(rect.x, rect.y + rect.height - 2, rect.width, 2)
            rl.draw_rectangle_rec(line_rect, self.UNITY_TAB_LINE)
        
        # Texto centrado
        text_width = rl.measure_text(text, 10)
        text_x = rect.x + (rect.width - text_width) // 2
        text_y = rect.y + (rect.height - 10) // 2
        rl.draw_text(text, int(text_x), int(text_y), 10, self.UNITY_TEXT)

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
