"""
engine/editor/hierarchy_panel.py - Panel de Jerarquía estilo Unity

PROPÓSITO:
    Muestra el árbol de entidades de la escena.
    Permite seleccionar entidades y visualizar relaciones padre-hijo.
"""

import pyray as rl
from typing import List, Optional, Tuple, Set

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.components.transform import Transform

class HierarchyPanel:
    """
    Panel lateral izquierdo que muestra la jerarquía de la escena.
    """
    
    # Unity Colors
    UNITY_BG = rl.Color(42, 42, 42, 255)        # Panel background
    UNITY_HEADER = rl.Color(56, 56, 56, 255)    # Header/Tab background
    UNITY_BORDER = rl.Color(25, 25, 25, 255)
    UNITY_SELECTED = rl.Color(44, 93, 135, 255) # Selection blue
    UNITY_HOVER = rl.Color(60, 60, 60, 255)
    UNITY_TEXT = rl.Color(200, 200, 200, 255)
    UNITY_TEXT_DIM = rl.Color(128, 128, 128, 255)
    UNITY_TAB_LINE = rl.Color(58, 121, 187, 255)
    
    HEADER_HEIGHT: int = 22
    FONT_SIZE: int = 10
    LINE_HEIGHT: int = 18
    INDENT_SIZE: int = 14
    
    def __init__(self) -> None:
        self.visible: bool = True
        self.scroll_offset: int = 0
        self.expanded_ids: Set[int] = set()
        self.panel_width: int = 200
        
    def render(self, world: "World", x: int, y: int, width: int, height: int) -> None:
        """Renderiza el panel de jerarquía estilo Unity."""
        if not self.visible:
            return
            
        self.panel_width = width

        # Scissor para no salir del área
        rl.begin_scissor_mode(x, y, width, height)
        
        # ========================================
        # 1. Header Tab
        # ========================================
        header_rect = rl.Rectangle(x, y, width, self.HEADER_HEIGHT)
        rl.draw_rectangle_rec(header_rect, self.UNITY_HEADER)
        
        # Tab "Hierarchy" con línea azul
        tab_width = 70
        tab_rect = rl.Rectangle(x + 2, y + 2, tab_width, self.HEADER_HEIGHT - 4)
        rl.draw_rectangle_rec(tab_rect, self.UNITY_BG)
        # Línea azul inferior
        rl.draw_rectangle(int(x + 2), int(y + self.HEADER_HEIGHT - 2), tab_width, 2, self.UNITY_TAB_LINE)
        # Texto
        rl.draw_text("Hierarchy", int(x + 10), int(y + 6), 10, self.UNITY_TEXT)
        
        # Botón + (crear objeto)
        plus_rect = rl.Rectangle(x + width - 22, y + 2, 18, 18)
        is_hover_plus = rl.check_collision_point_rec(rl.get_mouse_position(), plus_rect)
        plus_color = self.UNITY_HOVER if is_hover_plus else self.UNITY_HEADER
        rl.draw_rectangle_rec(plus_rect, plus_color)
        rl.draw_text("+", int(x + width - 17), int(y + 4), 14, self.UNITY_TEXT)
        
        if is_hover_plus and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            # Crear nueva entidad
            new_entity = world.create_entity(f"New Entity {world.entity_count()}")
            new_entity.add_component(Transform())
            world.selected_entity_name = new_entity.name
        
        # Línea separadora
        rl.draw_line(x, int(y + self.HEADER_HEIGHT), x + width, int(y + self.HEADER_HEIGHT), self.UNITY_BORDER)
        
        # ========================================
        # 2. Content Area
        # ========================================
        content_y_start = y + self.HEADER_HEIGHT + 5
        content_y = content_y_start - self.scroll_offset
        content_height = height - self.HEADER_HEIGHT
        
        # Fondo del contenido
        rl.draw_rectangle(x, int(y + self.HEADER_HEIGHT), width, int(content_height), self.UNITY_BG)
        
        # Obtener entidades raíz
        roots = []
        all_entities = world.get_all_entities()
        
        for entity in all_entities:
            transform = entity.get_component(Transform)
            if transform is None or transform.parent is None:
                roots.append(entity)
                
        roots.sort(key=lambda e: e.id)
        
        # Renderizar árbol
        for entity in roots:
            content_y = self._render_node(entity, 0, x, content_y, world, content_y_start, content_height)
            
        rl.end_scissor_mode()
            
    def _render_node(self, entity: Entity, depth: int, panel_x: int, y: int, world: "World", panel_y: int, panel_h: int) -> int:
        """Renderiza un nodo y sus hijos recursivamente. Retorna la nueva Y."""
        
        transform = entity.get_component(Transform)
        has_children = False
        children = []
        
        if transform:
            valid_children = []
            for child_trans in transform.children:
                child_ent = self._find_entity_by_transform(world, child_trans)
                if child_ent:
                    valid_children.append(child_ent)
            children = valid_children
            has_children = len(children) > 0

        # Dibujar fila
        row_height = self.LINE_HEIGHT
        
        # Culling simple
        if y + row_height < panel_y:
             # Skip draw but must Calc children height if expanded
             pass 
        elif y > panel_y + panel_h:
             return y + row_height # Skip render but stop? Recurse stops too.
        
        # Input Check (Solo si está en pantalla y dentro del panel)
        mouse_pos = rl.get_mouse_position()
        # Verificar si el mouse está dentro del panel globalmente
        is_mouse_in_panel = (panel_x <= mouse_pos.x <= panel_x + self.panel_width and 
                             panel_y <= mouse_pos.y <= panel_y + panel_h)
                             
        is_hover = (panel_x <= mouse_pos.x <= panel_x + self.panel_width and 
                    y <= mouse_pos.y < y + row_height) and is_mouse_in_panel
            
        if is_hover:
            rl.draw_rectangle(panel_x, y, self.panel_width, row_height, self.UNITY_HOVER)
            
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                world.selected_entity_name = entity.name
                if has_children:
                    # Toggle expand
                    if entity.id in self.expanded_ids:
                        self.expanded_ids.remove(entity.id)
                    else:
                        self.expanded_ids.add(entity.id)

        # Highlight Selection
        if world.selected_entity_name == entity.name:
            rl.draw_rectangle(panel_x, y, self.panel_width, row_height, self.UNITY_SELECTED)

        # Indentación
        indent_x = panel_x + 10 + (depth * self.INDENT_SIZE)
        
        # Triángulo de expansión
        if has_children:
            is_expanded = entity.id in self.expanded_ids
            tri_color = rl.GRAY
            tri_x = indent_x - 10
            tri_y = y + 4
            
            if is_expanded:
                # Abajo
                rl.draw_triangle(
                    rl.Vector2(tri_x, tri_y),
                    rl.Vector2(tri_x + 8, tri_y),
                    rl.Vector2(tri_x + 4, tri_y + 8),
                    tri_color
                )
            else:
                # Derecha
                rl.draw_triangle(
                    rl.Vector2(tri_x, tri_y),
                    rl.Vector2(tri_x, tri_y + 8),
                    rl.Vector2(tri_x + 8, tri_y + 4),
                    tri_color
                )
        
        # Nombre
        rl.draw_text(
            f"{entity.name}", 
            int(indent_x), 
            int(y + 4), 
            self.FONT_SIZE, 
            self.UNITY_TEXT
        )
        
        current_y = y + row_height
        
        # Render hijos si está expandido
        if has_children and entity.id in self.expanded_ids:
            for child in children:
                current_y = self._render_node(child, depth + 1, panel_x, current_y, world, panel_y, panel_h)
                
        return current_y

    def _find_entity_by_transform(self, world: "World", transform: Transform) -> Optional[Entity]:
        """Ayuda ineficiente para encontrar entidad dado un transform."""
        # En una implementación real, Component debería tener self.entity
        for ent in world.get_all_entities():
            if ent.get_component(Transform) == transform:
                return ent
        return None
