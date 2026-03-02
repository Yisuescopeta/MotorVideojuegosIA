"""
engine/inspector/inspector_system.py - Inspector V2.0 (Unity-Style)

PROPÓSITO:
    Renderiza el panel de propiedades de la entidad seleccionada.
    Soporta edición avanzada con:
    - Draggable Number Fields (Arrastrar label para ajustar valor)
    - Checkboxes para booleanos
    - Headers colapsables
"""

import pyray as rl
from typing import Any, List, Optional, Tuple, Set, Dict
import math

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.ecs.component import Component
from engine.levels.component_registry import create_default_registry

class InspectorSystem:
    """
    Inspector visual avanzado con widgets interactivos.
    """
    
    # Configuración Visual
    BG_COLOR = rl.Color(30, 30, 30, 255)
    HEADER_COLOR = rl.Color(50, 50, 50, 255)
    FIELD_BG_COLOR = rl.Color(20, 20, 20, 255)
    TEXT_COLOR = rl.Color(220, 220, 220, 255)
    LABEL_COLOR = rl.Color(180, 180, 180, 255)
    HIGHLIGHT_COLOR = rl.Color(60, 100, 150, 255)
    
    FONT_SIZE: int = 10
    LINE_HEIGHT: int = 18
    MARGIN: int = 4
    LABEL_WIDTH: int = 80
    
    def __init__(self) -> None:
        self.expanded_components: Set[str] = set() # Nombres de componentes expandidos
        self._scene_manager: Any = None
        
        # Estado de interacción
        self.dragging_field: Optional[str] = None # "EntityID:CompName:PropName"
        self.potential_drag_field: Optional[str] = None # Para distinguir click vs drag
        self.drag_start_mouse: Tuple[float, float] = (0,0)
        self.drag_start_value: float = 0.0
        
        self.editing_text_field: Optional[str] = None
        self.text_buffer: bytearray = bytearray(64) # Buffer para Raygui
        
        # Add Component Menu
        self.show_add_menu: bool = False
        self.registry = create_default_registry()

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager

    def update(self, dt: float, world: "World", is_edit_mode: bool) -> None:
        """Maneja lógica de input (text input, drags, etc)."""
        if not is_edit_mode:
            return
            
        # Finalizar drag si soltamos click
        if self.dragging_field and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            self.dragging_field = None
            rl.show_cursor() # Restaurar cursor
            

            
        # Global Commit/Cancel triggers (Escape)
        if self.editing_text_field:
            if rl.is_key_pressed(rl.KEY_ESCAPE):
                self.editing_text_field = None
            
            # Note: Enter key is handled by gui_text_box return value in render()

    def _commit_text_edit(self, world: "World") -> None:
        """Alica el valor del buffer al componente."""
        if not self.editing_text_field: return
        
        try:
            # Parsear "EntityID:CompName:PropName"
            parts = self.editing_text_field.split(":")
            # Format: "{entity_id}:{comp_name}:{prop_name}"
            
            if len(parts) >= 3:
                entity_id = int(parts[0])
                comp_name = parts[1]
                prop_name = parts[2]
                
                # Buscar entidad y componente
                entity = world.get_entity(entity_id)
                if entity:
                    for comp in entity.get_all_components():
                        if type(comp).__name__ == comp_name:
                            # Parse value
                            # Raygui modifies buffer in C. decoding...
                            val_str = self.text_buffer.decode('utf-8').rstrip('\x00')
                            # Handle empty string
                            if not val_str: val_str = "0.0"
                            new_val = float(val_str)
                            setattr(comp, prop_name, new_val)
                            break
        except Exception as e:
            print(f"Error commiting text edit: {e}")
            pass

    def render(self, world: "World", x: int, y: int, width: int, height: int, is_edit_mode: bool) -> None:
        """Dibuja el inspector estilo Unity."""
        panel_x = x
        panel_y = y
        panel_w = width
        panel_h = height
        
        # Unity Colors
        UNITY_HEADER = rl.Color(56, 56, 56, 255)
        UNITY_TAB_BG = rl.Color(42, 42, 42, 255)
        UNITY_TAB_LINE = rl.Color(58, 121, 187, 255)
        UNITY_TEXT = rl.Color(200, 200, 200, 255)
        UNITY_BORDER = rl.Color(25, 25, 25, 255)
        HEADER_HEIGHT = 22
        
        # Scissors
        rl.begin_scissor_mode(panel_x, panel_y, panel_w, panel_h)
        
        # Fondo del panel
        rl.draw_rectangle(panel_x, panel_y, panel_w, panel_h, self.BG_COLOR)
        
        # ========================================
        # Header con Tab "Inspector"
        # ========================================
        header_rect = rl.Rectangle(panel_x, panel_y, panel_w, HEADER_HEIGHT)
        rl.draw_rectangle_rec(header_rect, UNITY_HEADER)
        
        # Tab "Inspector"
        tab_width = 65
        tab_rect = rl.Rectangle(panel_x + 2, panel_y + 2, tab_width, HEADER_HEIGHT - 4)
        rl.draw_rectangle_rec(tab_rect, UNITY_TAB_BG)
        rl.draw_rectangle(int(panel_x + 2), int(panel_y + HEADER_HEIGHT - 2), tab_width, 2, UNITY_TAB_LINE)
        rl.draw_text("Inspector", int(panel_x + 10), int(panel_y + 6), 10, UNITY_TEXT)
        
        # Línea separadora
        rl.draw_line(panel_x, int(panel_y + HEADER_HEIGHT), panel_x + panel_w, int(panel_y + HEADER_HEIGHT), UNITY_BORDER)
        
        content_y = panel_y + HEADER_HEIGHT + 5
        
        selected_name = world.selected_entity_name
        if not selected_name:
            rl.draw_text("No selection", int(panel_x + 10), int(content_y + 10), 10, rl.Color(128, 128, 128, 255))
            rl.end_scissor_mode()
            return

        entity = world.get_entity_by_name(selected_name)
        if not entity:
            rl.end_scissor_mode()
            return
        
        # ========================================
        # Entity Header (Active checkbox + Nombre)
        # ========================================
        # Active checkbox
        active_rect = rl.Rectangle(panel_x + 10, content_y, 14, 14)
        rl.draw_rectangle_rec(active_rect, rl.Color(42, 42, 42, 255))
        rl.draw_rectangle_lines_ex(active_rect, 1, rl.Color(80, 80, 80, 255))
        rl.draw_rectangle(int(panel_x + 13), int(content_y + 3), 8, 8, rl.Color(70, 130, 200, 255))
        
        # Nombre de la entidad  
        rl.draw_text(entity.name, int(panel_x + 32), int(content_y + 2), 12, rl.Color(230, 230, 230, 255))
        
        content_y += 22
        
        # Separador
        rl.draw_line(panel_x, int(content_y), panel_x + panel_w, int(content_y), UNITY_BORDER)
        content_y += 5
        
        # ========================================
        # Componentes
        # ========================================
        components = entity.get_all_components()
        for comp in components:
            content_y = self._draw_component(comp, entity.id, panel_x, content_y, panel_w, is_edit_mode, world)
            content_y += 5
            
        for comp in components:
            content_y = self._draw_component(comp, entity.id, panel_x, content_y, panel_w, is_edit_mode, world)
            content_y += 5
            
        # Add Component Button
        add_btn_rect = rl.Rectangle(panel_x + 10, content_y + 10, panel_w - 20, 24)
        if rl.gui_button(add_btn_rect, "Add Component"):
            self.show_add_menu = not self.show_add_menu
            
        rl.end_scissor_mode()
        
        # Draw Menu Overlay (Outside Scissor)
        if self.show_add_menu:
             self._draw_add_menu(world, entity, int(panel_x + 10), int(content_y + 35))

    def _draw_component(self, component: Component, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        """Dibuja un componente con header colapsable estilo Unity."""
        comp_name = type(component).__name__
        unique_id = f"{entity_id}:{comp_name}"
        
        is_expanded = unique_id in self.expanded_components
        header_rect = rl.Rectangle(x + 2, y, width - 4, 20)
        
        # Header manual (sin gui_toggle que requiere punteros)
        mouse_pos = rl.get_mouse_position()
        is_hover = rl.check_collision_point_rec(mouse_pos, header_rect)
        
        # Fondo del header
        bg_color = rl.Color(70, 70, 70, 255) if is_hover else rl.Color(60, 60, 60, 255)
        rl.draw_rectangle_rec(header_rect, bg_color)
        
        # Icono de expansión
        arrow = "v" if is_expanded else ">"
        rl.draw_text(arrow, int(x + 8), int(y + 5), 10, rl.Color(200, 200, 200, 255))
        
        # Nombre del componente
        rl.draw_text(comp_name, int(x + 22), int(y + 5), 10, rl.Color(220, 220, 220, 255))
        
        # Click para toggle
        if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            # Check if clicked on remove button (defined below)
            # Actually, standard toggle logic occupies most of header.
            # We'll put remove button at right.
            pass

        # Remove Button (X)
        if comp_name != "Transform":
            remove_rect = rl.Rectangle(x + width - 20, y + 2, 16, 16)
            is_hover_remove = rl.check_collision_point_rec(mouse_pos, remove_rect)
            
            remove_color = rl.Color(200, 60, 60, 255) if is_hover_remove else rl.Color(150, 80, 80, 255)
            rl.draw_rectangle_rec(remove_rect, remove_color)
            rl.draw_text("x", int(x + width - 15), int(y + 3), 10, rl.WHITE)
            
            if is_hover_remove and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                entity = world.get_entity(entity_id)
                if entity:
                    entity.remove_component(type(component))
                    print(f"[INSPECTOR] Removed {comp_name} from {entity.name}")
                    return y + 20 # Return early, component removed
        
        # Toggle Logic (if not clicking remove)
        if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            # Avoid clicking remove button
            if comp_name == "Transform" or not rl.check_collision_point_rec(mouse_pos, rl.Rectangle(x + width - 20, y + 2, 16, 16)):
                if is_expanded:
                    self.expanded_components.discard(unique_id)
                else:
                    self.expanded_components.add(unique_id)
                is_expanded = not is_expanded
        
        current_y = y + 22
        
        if is_expanded:
            # Propiedades
            props = self._get_properties(component)
            for prop_name, value in props:
                full_prop_id = f"{unique_id}:{prop_name}"
                current_y = self._draw_property(prop_name, value, full_prop_id, component, x, current_y, width, is_edit, world)
                
        return current_y

    def _draw_property(self, label: str, value: Any, prop_id: str, component: Any, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        """Dibuja propiedad usando Raygui widgets."""
        row_height = self.LINE_HEIGHT
        padding = 5
        
        # Label
        rl.gui_label(rl.Rectangle(x + padding, y, self.LABEL_WIDTH, row_height), label)
        
        # Field area
        field_x = x + self.LABEL_WIDTH + padding
        field_w = width - self.LABEL_WIDTH - (padding * 2)
        
        # IMPORTANT: Check bool BEFORE int, because isinstance(True, int) is True in Python
        # IMPORTANT: Check bool BEFORE int, because isinstance(True, int) is True in Python
        if isinstance(value, bool):
            self._draw_bool_field(value, prop_id, component, label, field_x, y, field_w, row_height, is_edit)
        elif isinstance(value, (float, int)):
            # LABEL DRAG LOGIC
            if is_edit:
                label_rect = rl.Rectangle(x + padding, y, self.LABEL_WIDTH, row_height)
                mouse_pos = rl.get_mouse_position()
                
                # Check Hover/Drag on Label
                is_hover_label = rl.check_collision_point_rec(mouse_pos, label_rect) or self.dragging_field == prop_id
                
                if is_hover_label:
                    rl.set_mouse_cursor(rl.MOUSE_CURSOR_RESIZE_EW)
                    
                    if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                        self.dragging_field = prop_id
                        self.drag_start_value = float(value)
                        self.drag_start_mouse = (mouse_pos.x, mouse_pos.y)
                        rl.hide_cursor()
                
                # Update Drag
                if self.dragging_field == prop_id:
                    delta_x = mouse_pos.x - self.drag_start_mouse[0]
                    # Sensibilidad: 0.1 per pixel? Adjust based on Shift key?
                    # Unity uses pixel delta. 
                    new_value = self.drag_start_value + (delta_x * 0.05)
                    setattr(component, prop_id.split(":")[-1], new_value)
                    
            self._draw_float_field(float(value), prop_id, component, label, field_x, y, field_w, row_height, is_edit, world)
        elif isinstance(value, str):
            rl.gui_label(rl.Rectangle(field_x, y, field_w, row_height), value)
        else:
            rl.gui_label(rl.Rectangle(field_x, y, field_w, row_height), str(value))
            
        return y + row_height

    def _draw_float_field(self, value: float, prop_id: str, component: Any, prop_name: str, x: int, y: int, w: int, h: int, is_edit: bool, world: "World") -> None:
        """Campo numérico con Drag y Edición de Texto."""
        val_rect = rl.Rectangle(x, y + 1, w, h - 2)
        
        # MODO EDICIÓN DE TEXTO
        if self.editing_text_field == prop_id:
            # Custom Manual Input Implementation (Fixes flickering & allows clear-on-click)
            
            # Fondo y Borde (Highlight)
            rl.draw_rectangle_rec(val_rect, rl.Color(30, 30, 30, 255))
            rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(0, 200, 255, 255))
            
            # Texto Actual
            current_text = self.text_buffer.decode('utf-8').rstrip('\x00')
            rl.draw_text(current_text + "_", int(x + 5), int(y + 4), 10, rl.WHITE)
            
            # Input Handling
            key = rl.get_char_pressed()
            while key > 0:
                if (key >= 32 and key <= 125) and len(current_text) < 63:
                    # Append char to buffer
                    self.text_buffer[len(current_text)] = key
                    current_text += chr(key)
                key = rl.get_char_pressed()
                
            if rl.is_key_pressed(rl.KEY_BACKSPACE):
                length = len(current_text)
                if length > 0:
                    self.text_buffer[length - 1] = 0
            
            # Commit on Enter
            if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
                self._commit_text_edit(world)
                self.editing_text_field = None
                
            # Click Outside Logic
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                mouse_pos = rl.get_mouse_position()
                if not rl.check_collision_point_rec(mouse_pos, val_rect):
                    self._commit_text_edit(world)
                    self.editing_text_field = None
            return

        # MODO DRAG / VIEW
        # Fondo
        rl.draw_rectangle_rec(val_rect, rl.Color(42, 42, 42, 255))
        
        # Texto
        value_text = f"{value:.2f}"
        rl.draw_text(value_text, int(x + 5), int(y + 4), 10, rl.Color(200, 200, 200, 255))
        
        if is_edit:
            mouse_pos = rl.get_mouse_position()
            is_hover = rl.check_collision_point_rec(mouse_pos, val_rect)
            
            if is_hover:
                rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(70, 130, 200, 255))
                rl.set_mouse_cursor(rl.MOUSE_CURSOR_IBEAM) # Cursor de texto
                
                # Click to Edit
                if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                     self.editing_text_field = prop_id
                     # Init buffer
                     self.text_buffer[:] = b'\x00' * len(self.text_buffer)

    def _draw_bool_field(self, value: bool, prop_id: str, component: Any, prop_name: str, x: int, y: int, w: int, h: int, is_edit: bool) -> None:
        """Checkbox manual estilo Unity."""
        check_rect = rl.Rectangle(x, y + 2, 14, 14)
        
        # Fondo
        rl.draw_rectangle_rec(check_rect, rl.Color(42, 42, 42, 255))
        rl.draw_rectangle_lines_ex(check_rect, 1, rl.Color(80, 80, 80, 255))
        
        # Check mark
        if value:
            inner = rl.Rectangle(x + 3, y + 5, 8, 8)
            rl.draw_rectangle_rec(inner, rl.Color(70, 130, 200, 255))
        
        if is_edit:
            mouse_pos = rl.get_mouse_position()
            if rl.check_collision_point_rec(mouse_pos, check_rect):
                rl.draw_rectangle_lines_ex(check_rect, 1, rl.Color(100, 150, 220, 255))
                if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                    setattr(component, prop_name, not value)



    def _get_properties(self, component: Any) -> List[Tuple[str, Any]]:
        """Introspección simple para obtener propiedades públicas."""
        props = []
        # Preferir to_dict keys si existe para orden
        if hasattr(component, "to_dict"):
            try:
                data = component.to_dict()
                # Pero necesitamos los valores actuales del objeto, no del dict serializado
                for k in data.keys():
                    if hasattr(component, k):
                         # Evitar props como 'children' o listas complejas por ahora en MVP
                        val = getattr(component, k)
                        if isinstance(val, (int, float, bool, str)):
                            props.append((k, val))
                return props
            except:
                pass
                
        # Fallback dir
        for attr in dir(component):
            if not attr.startswith("_") and not callable(getattr(component, attr)):
                val = getattr(component, attr)
                if isinstance(val, (int, float, bool, str)):
                    props.append((attr, val))
        return props
        return props

    def _draw_add_menu(self, world: "World", entity: Entity, x: int, y: int) -> None:
        """Dibuja menú flotante para agregar componentes."""
        # Get available components (not present in entity)
        all_comps = self.registry.list_registered()
        available = []
        for name in all_comps:
             # Check if entity has it
             # Limitation: Entity.has_component assumes we know the class
             # Registry.get(name) returns the class
             comp_cls = self.registry.get(name)
             if comp_cls and not entity.has_component(comp_cls):
                 available.append(name)
                 
        item_height = 24
        menu_w = 160
        menu_h = len(available) * item_height
        
        # Keep on screen
        if y + menu_h > rl.get_screen_height(): y -= menu_h + 30
        
        menu_rect = rl.Rectangle(x, y, menu_w, menu_h)
        
        # Draw Background
        rl.draw_rectangle_rec(menu_rect, rl.Color(40, 40, 40, 255))
        rl.draw_rectangle_lines_ex(menu_rect, 1, rl.Color(80, 80, 80, 255))
        
        mouse = rl.get_mouse_position()
        
        # Close if clicked outside
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            # Checking if click was inside is harder because we execute after button logic
            # For now, simplistic toggle closing is handled by button.
            # Here we check if we clicked OUTSIDE menu
             if not rl.check_collision_point_rec(mouse, menu_rect) and not rl.check_collision_point_rec(mouse, rl.Rectangle(x, y-25, 100, 25)):
                 self.show_add_menu = False
                 return

        for i, name in enumerate(available):
            rect = rl.Rectangle(x, y + i * item_height, menu_w, item_height)
            is_hover = rl.check_collision_point_rec(mouse, rect)
            
            if is_hover:
                rl.draw_rectangle_rec(rect, rl.Color(60, 60, 60, 255))
                if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                    # Add Component
                    comp_cls = self.registry.get(name)
                    if comp_cls:
                        # Instantiate defaults
                        # We use registry.create with empty dict
                        new_comp = self.registry.create(name, {})
                        if new_comp:
                            entity.add_component(new_comp)
                            print(f"[INSPECTOR] Component {name} added to {entity.name}")
                    self.show_add_menu = False
            
            rl.draw_text(name, int(x + 10), int(y + i * item_height + 6), 10, rl.Color(200, 200, 200, 255))
