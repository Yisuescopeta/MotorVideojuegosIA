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
from enum import Enum, auto
from typing import Optional, Tuple

from engine.ecs.world import World
from engine.components.transform import Transform
from engine.ecs.entity import Entity

class GizmoMode(Enum):
    NONE = auto()
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()

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
    
    def __init__(self) -> None:
        self.active_mode: GizmoMode = GizmoMode.NONE
        self.hover_mode: GizmoMode = GizmoMode.NONE
        self.drag_start_mouse: Tuple[float, float] = (0.0, 0.0)
        self.drag_start_pos: Tuple[float, float] = (0.0, 0.0)
        self.is_dragging: bool = False
        
    def update(self, world: "World", mouse_world_pos: rl.Vector2) -> None:
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
        self.hover_mode = self._check_intersection(mouse_x, mouse_y, origin_x, origin_y)
        
        if self.hover_mode != GizmoMode.NONE and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self._start_drag(transform, mouse_x, mouse_y, self.hover_mode)

    def render(self, world: "World") -> None:
        """Dibuja el grid y los gizmos."""
        self._draw_grid()
        
        selected_entity = self._get_selected_entity(world)
        if selected_entity:
            transform = selected_entity.get_component(Transform)
            if transform:
                self._draw_gizmo(transform.x, transform.y)

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

    def _draw_gizmo(self, x: float, y: float) -> None:
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

    def _check_intersection(self, mx: float, my: float, ox: float, oy: float) -> GizmoMode:
        """Verifica si el mouse está sobre algún eje."""
        # Tolerancia para click
        tol_thickness = 10
        tol_length = self.AXIS_LENGTH + self.ARROW_HEAD_SIZE
        
        # Bounding box Eje X (desde origen a derecha)
        if (ox <= mx <= ox + tol_length) and (oy - tol_thickness/2 <= my <= oy + tol_thickness/2):
            return GizmoMode.TRANSLATE_X
            
        # Bounding box Eje Y (desde origen a arriba -Y)
        if (ox - tol_thickness/2 <= mx <= ox + tol_thickness/2) and (oy - tol_length <= my <= oy):
            return GizmoMode.TRANSLATE_Y
            
        return GizmoMode.NONE

    def _start_drag(self, transform: Transform, mx: float, my: float, mode: GizmoMode) -> None:
        self.is_dragging = True
        self.active_mode = mode
        self.drag_start_mouse = (mx, my)
        self.drag_start_pos = (transform.x, transform.y) # Guardamos posición global inicial

    def _handle_drag(self, transform: Transform, mx: float, my: float) -> None:
        start_mx, start_my = self.drag_start_mouse
        start_px, start_py = self.drag_start_pos
        
        dx = mx - start_mx
        dy = my - start_my
        
        if self.active_mode == GizmoMode.TRANSLATE_X:
            # Solo modificamos X
            transform.x = start_px + dx
            # Mantenemos Y original para evitar drift
            transform.y = start_py 
            
        elif self.active_mode == GizmoMode.TRANSLATE_Y:
            # Solo modificamos Y
            transform.y = start_py + dy
            # Mantenemos X original
            transform.x = start_px

    def _end_drag(self) -> None:
        self.is_dragging = False
        self.active_mode = GizmoMode.NONE
