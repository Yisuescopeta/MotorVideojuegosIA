"""
engine/editor/gizmo_system.py - Sistema de manipulación visual (Gizmos)

PROPÓSITO:
    Dibuja herramientas visuales (flechas) sobre la entidad seleccionada
    para permitir moverla arrastrando con el mouse.

FUNCIONALIDADES:
    - Ejes X (Rojo) e Y (Verde).
    - Detección de hover/click en ejes.
    - Transformación de movimiento del mouse a movimiento de la entidad.
    - Grid de fondo.
"""

import pyray as rl
import math
from enum import Enum, auto
from typing import Optional, Tuple

from engine.ecs.world import World
from engine.components.transform import Transform
from engine.ecs.entity import Entity

class GizmoMode(Enum):
    NONE = auto()
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()
    ROTATE_Z = auto()
    SCALE_X = auto()
    SCALE_Y = auto()
    SCALE_UNIFORM = auto()

class GizmoSystem:
    """Sistema encargado de dibujar gizmos y procesar inputs de manipulación."""
    
    # Configuración Visual
    AXIS_LENGTH: int = 50
    AXIS_THICKNESS: int = 3
    ARROW_HEAD_SIZE: int = 10
    AXIS_X_COLOR = rl.Color(220, 60, 60, 255)
    AXIS_Y_COLOR = rl.Color(60, 220, 60, 255)
    HOVER_COLOR = rl.Color(255, 255, 100, 255)
    CENTER_SIZE: int = 6
    GRID_SIZE: int = 50
    GRID_COLOR = rl.Color(60, 60, 70, 100)
    ROTATE_RING_RADIUS: int = 40
    SCALE_HANDLE_SIZE: int = 8
    
    def __init__(self) -> None:
        self.active_mode: GizmoMode = GizmoMode.NONE
        self.hover_mode: GizmoMode = GizmoMode.NONE
        self.drag_start_mouse: Tuple[float, float] = (0.0, 0.0)
        self.drag_start_pos: Tuple[float, float] = (0.0, 0.0)
        self.is_dragging: bool = False
        
    def update(self, world: "World", mouse_world_pos: rl.Vector2, current_tool: str = "Move") -> None:
        """
        Procesa el input del usuario para interactuar con el gizmo.
        Requires transformed world mouse position (from Editor Camera).
        """
        selected_entity = self._get_selected_entity(world)
        if not selected_entity:
            self.active_mode = GizmoMode.NONE
            self.hover_mode = GizmoMode.NONE
            return

        transform = selected_entity.get_component(Transform)
        if not transform:
            return

        # Usar coordenadas world pasadas (ya transformadas por cámara y viewport)
        mouse_x, mouse_y = mouse_world_pos.x, mouse_world_pos.y
        origin_x, origin_y = transform.x, transform.y

        # Lógica de Dragging
        if self.is_dragging:
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self._end_drag()
            else:
                self._handle_drag(transform, mouse_x, mouse_y)
            return

        # Lógica de Detección (Hover/Click)
        self.hover_mode = self._check_intersection(mouse_x, mouse_y, origin_x, origin_y, current_tool)
        
        if self.hover_mode != GizmoMode.NONE and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self._start_drag(transform, mouse_x, mouse_y, self.hover_mode)

    def render(self, world: "World") -> None:
        """Dibuja los gizmos. Grid is drawn by EditorLayout.begin_scene_render()."""
        # NOTE: _draw_grid() was removed because it called begin_mode_2d(reset_camera)
        # which broke the editor camera set by begin_scene_render(). The editor_layout
        # already draws a grid in _draw_grid_2d() during begin_scene_render().
        
        selected_entity = self._get_selected_entity(world)
        if selected_entity:
            transform = selected_entity.get_component(Transform)
            if transform:
                # Dibujar según modo activo o herramienta actual...
                # Pero 'render' no recibe 'current_tool'. Necesitamos guardarlo o pasarlo.
                # Asumimos que update se llama antes y podríamos guardar el tool, 
                # PERO render suele ser independiente. 
                # Simplificación: Render dibuja TODOS los gizmos relevantes o el último usado?
                # Mejor: update guarda self.last_tool o pasamos tool a render tambien.
                # Por ahora, dibujaremos basado en lo que 'update' vio (self.hover_mode p.ej da pistas)
                # O mejor, modificamos update para guardar flags de dibujo
                
                # Para simplificar en este paso, dibujamos el gizmo correspondiente a la herramienta
                # que se usó en update. (Hack temporal)
                
                # Espera, Game.py llama a Gizmo.update Y Gizmo.render.
                # Modificaré render en Game.py para pasar tool? No, render es protocol standard.
                # Guardaré tool en self.current_tool en update.
                pass 
                
    def render_with_tool(self, world: "World", tool: str) -> None:
        selected_entity = self._get_selected_entity(world)
        if selected_entity:
            transform = selected_entity.get_component(Transform)
            if transform:
                if tool == "Move":
                    self._draw_translate_gizmo(transform.x, transform.y)
                elif tool == "Rotate":
                    self._draw_rotate_gizmo(transform.x, transform.y, transform.rotation)
                elif tool == "Scale":
                    self._draw_scale_gizmo(transform.x, transform.y)
                    
    # Alias para compatibilidad, pero usaremos render_with_tool en Game.py
    def render(self, world: "World") -> None:
        self.render_with_tool(world, "Move") # Default

    def _get_selected_entity(self, world: "World") -> Optional[Entity]:
        if not world.selected_entity_name:
            return None
        return world.get_entity_by_name(world.selected_entity_name)

    def _draw_grid(self) -> None:
        """Dibuja una cuadrícula infinita centrada en pantalla."""
        # Simple implementación estática por ahora (0 a screen size)
        width = rl.get_screen_width()
        height = rl.get_screen_height()
        
        rl.begin_mode_2d(rl.Camera2D(rl.Vector2(0,0), rl.Vector2(0,0), 0, 1)) # Reset camera (si hubiera)
        
        for x in range(0, width, self.GRID_SIZE):
            rl.draw_line(x, 0, x, height, self.GRID_COLOR)
            
        for y in range(0, height, self.GRID_SIZE):
            rl.draw_line(0, y, width, y, self.GRID_COLOR)
            
        rl.end_mode_2d()

    def _draw_translate_gizmo(self, x: float, y: float) -> None:
        """Dibuja las flechas de manipulación."""
        origin = rl.Vector2(x, y)
        
        # Color X
        color_x = self.HOVER_COLOR if self.hover_mode == GizmoMode.TRANSLATE_X or self.active_mode == GizmoMode.TRANSLATE_X else self.AXIS_X_COLOR
        # Color Y
        color_y = self.HOVER_COLOR if self.hover_mode == GizmoMode.TRANSLATE_Y or self.active_mode == GizmoMode.TRANSLATE_Y else self.AXIS_Y_COLOR
        
        # Eje X
        rl.draw_line_ex(
            origin, 
            rl.Vector2(x + self.AXIS_LENGTH, y), 
            self.AXIS_THICKNESS, 
            color_x
        )
        # Flecha X
        rl.draw_triangle(
            rl.Vector2(x + self.AXIS_LENGTH + self.ARROW_HEAD_SIZE, y),
            rl.Vector2(x + self.AXIS_LENGTH, y - 5),
            rl.Vector2(x + self.AXIS_LENGTH, y + 5),
            color_x
        )
        
        # Eje Y
        rl.draw_line_ex(
            origin, 
            rl.Vector2(x, y - self.AXIS_LENGTH), # Y crece hacia abajo en Raylib, pero el gizmo suele apuntar "arriba" (-Y) en motores 2D clásicos. 
                                                 # Sin embargo, en Raylib coordenadas, -Y es arriba. 
                                                 # Para ser consistentes con Unity 2D: Y es arriba (Up).
            self.AXIS_THICKNESS, 
            color_y
        )
        # Flecha Y
        rl.draw_triangle(
            rl.Vector2(x, y - self.AXIS_LENGTH - self.ARROW_HEAD_SIZE),
            rl.Vector2(x + 5, y - self.AXIS_LENGTH),
            rl.Vector2(x - 5, y - self.AXIS_LENGTH),
            color_y
        )
        
        # Centro
        rl.draw_rectangle(
            int(x - self.CENTER_SIZE/2), 
            int(y - self.CENTER_SIZE/2), 
            self.CENTER_SIZE, 
            self.CENTER_SIZE, 
            rl.WHITE
        )

    def _draw_rotate_gizmo(self, x: float, y: float, rotation: float) -> None:
        radius = self.ROTATE_RING_RADIUS
        color = self.HOVER_COLOR if self.hover_mode == GizmoMode.ROTATE_Z or self.active_mode == GizmoMode.ROTATE_Z else rl.BLUE
        
        rl.draw_circle_lines(int(x), int(y), radius, color)
        rl.draw_circle(int(x), int(y), 2, rl.WHITE)
        
        # Linea indicadora de rotación actual
        rad = math.radians(rotation)
        end_x = x + math.cos(rad) * radius
        end_y = y + math.sin(rad) * radius
        rl.draw_line(int(x), int(y), int(end_x), int(end_y), rl.Color(255, 255, 255, 128))

    def _draw_scale_gizmo(self, x: float, y: float) -> None:
        # X Axis
        color_x = self.HOVER_COLOR if self.hover_mode == GizmoMode.SCALE_X or self.active_mode == GizmoMode.SCALE_X else self.AXIS_X_COLOR
        rl.draw_line_ex(rl.Vector2(x, y), rl.Vector2(x + self.AXIS_LENGTH, y), 2, color_x)
        rl.draw_rectangle(int(x + self.AXIS_LENGTH), int(y - 4), 8, 8, color_x)
        
        # Y Axis
        color_y = self.HOVER_COLOR if self.hover_mode == GizmoMode.SCALE_Y or self.active_mode == GizmoMode.SCALE_Y else self.AXIS_Y_COLOR
        rl.draw_line_ex(rl.Vector2(x, y), rl.Vector2(x, y - self.AXIS_LENGTH), 2, color_y)
        rl.draw_rectangle(int(x - 4), int(y - self.AXIS_LENGTH - 8), 8, 8, color_y)
        
        # Center (Uniform)
        color_c = self.HOVER_COLOR if self.hover_mode == GizmoMode.SCALE_UNIFORM or self.active_mode == GizmoMode.SCALE_UNIFORM else rl.WHITE
        rl.draw_rectangle(int(x - 6), int(y - 6), 12, 12, color_c)

    def _check_intersection(self, mx: float, my: float, ox: float, oy: float, tool: str) -> GizmoMode:
        if tool == "Move":
            # Tolerancia para click
            tol_thickness = 10
            tol_length = self.AXIS_LENGTH + self.ARROW_HEAD_SIZE
            
            # X Axis
            if (ox <= mx <= ox + tol_length) and (oy - tol_thickness/2 <= my <= oy + tol_thickness/2):
                return GizmoMode.TRANSLATE_X
            # Y Axis
            if (ox - tol_thickness/2 <= mx <= ox + tol_thickness/2) and (oy - tol_length <= my <= oy):
                return GizmoMode.TRANSLATE_Y
                
        elif tool == "Rotate":
            dist = math.sqrt((mx - ox)**2 + (my - oy)**2)
            if abs(dist - self.ROTATE_RING_RADIUS) < 10:
                return GizmoMode.ROTATE_Z
                
        elif tool == "Scale":
            # Scale X Handle
            if (ox + self.AXIS_LENGTH <= mx <= ox + self.AXIS_LENGTH + 8) and (oy - 4 <= my <= oy + 4):
                 return GizmoMode.SCALE_X
            # Scale Y Handle
            if (ox - 4 <= mx <= ox + 4) and (oy - self.AXIS_LENGTH - 8 <= my <= oy - self.AXIS_LENGTH):
                 return GizmoMode.SCALE_Y
            # Center Handle
            if (ox - 6 <= mx <= ox + 6) and (oy - 6 <= my <= oy + 6):
                 return GizmoMode.SCALE_UNIFORM
                 
        return GizmoMode.NONE



    def _start_drag(self, transform: Transform, mx: float, my: float, mode: GizmoMode) -> None:
        self.is_dragging = True
        self.active_mode = mode
        self.drag_start_mouse = (mx, my)
        self.drag_start_pos = (transform.x, transform.y) # Guardamos posición global inicial
        # Store initial rotation/scale too
        self.drag_start_rot = transform.rotation
        self.drag_start_scale = (transform.scale_x, transform.scale_y)

    def _handle_drag(self, transform: Transform, mx: float, my: float) -> None:
        start_mx, start_my = self.drag_start_mouse
        start_px, start_py = self.drag_start_pos
        
        dx = mx - start_mx
        dy = my - start_my
        
        # TRANSLATE
        if self.active_mode == GizmoMode.TRANSLATE_X:
            transform.x = start_px + dx
        elif self.active_mode == GizmoMode.TRANSLATE_Y:
            transform.y = start_py + dy
            
        # ROTATE
        elif self.active_mode == GizmoMode.ROTATE_Z:
            # Calculate angle difference
            # Vector 1: Center -> StartMouse
            # Vector 2: Center -> CurrentMouse
            # Angle = atan2(v2) - atan2(v1)
            cx, cy = start_px, start_py
            angle_start = math.degrees(math.atan2(start_my - cy, start_mx - cx))
            angle_curr = math.degrees(math.atan2(my - cy, mx - cx))
            diff = angle_curr - angle_start
            transform.rotation = self.drag_start_rot + diff
            
        # SCALE
        elif self.active_mode == GizmoMode.SCALE_X:
            # Proyectar dx sobre eje? O simple distance ratio?
            # Simple: 1 px = 0.01 scale
            scale_delta = dx * 0.02
            transform.scale_x = self.drag_start_scale[0] + scale_delta
        elif self.active_mode == GizmoMode.SCALE_Y:
            scale_delta = -dy * 0.02 # Invert Y delta because Y up implies negative screen Y
            transform.scale_y = self.drag_start_scale[1] + scale_delta
        elif self.active_mode == GizmoMode.SCALE_UNIFORM:
             # Avg delta
             avg = (dx - dy) * 0.02
             transform.scale_x = self.drag_start_scale[0] + avg
             transform.scale_y = self.drag_start_scale[1] + avg

    def _end_drag(self) -> None:
        self.is_dragging = False
        self.active_mode = GizmoMode.NONE
