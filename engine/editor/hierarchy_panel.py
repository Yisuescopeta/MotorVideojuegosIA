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
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.editor_selection import EditorSelectionState
from engine.editor.render_safety import editor_scissor

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
    
    def __init__(self, selection_state: Optional[EditorSelectionState] = None) -> None:
        self.visible: bool = True
        self.scroll_offset: int = 0
        self.expanded_ids: Set[int] = set()
        self.panel_width: int = 200
        self._scene_manager = None
        self._selection_state: Optional[EditorSelectionState] = selection_state
        self._cached_world_id: int = -1
        self._cached_world_version: int = -1
        self._cached_roots: List[Entity] = []
        
        # Context Menu State
        self.context_menu_active: bool = False
        self.context_menu_pos = rl.Vector2(0, 0)
        self.context_target_id: Optional[int] = None
        self.hovered_entity_id: Optional[int] = None
        self._cursor_interactive_rects: List[rl.Rectangle] = []
        self._input_blocked: bool = False

        # Drag-and-drop reparenting state
        self._drag_entity_id: Optional[int] = None
        self._drag_start_y: float = 0.0
        self._is_dragging_entity: bool = False
        self._drop_target_name: Optional[str] = None
        self._drop_as_root: bool = False
        self._DRAG_THRESHOLD: int = 5

    def set_scene_manager(self, manager: object) -> None:
        """Permite que la UI use el mismo camino serializable que la API."""
        self._scene_manager = manager

    def set_selection_state(self, selection_state: Optional[EditorSelectionState]) -> None:
        self._selection_state = selection_state

    def _get_selected_entity_name(self, world: "World") -> Optional[str]:
        world_selected = EditorSelectionState.normalize(getattr(world, "selected_entity_name", None))
        if self._selection_state is None:
            return world_selected
        if world_selected != self._selection_state.entity_name:
            self._selection_state.set(world_selected)
        return self._selection_state.entity_name

    def _set_selected_entity(self, world: "World", entity_name: Optional[str]) -> Optional[str]:
        normalized = EditorSelectionState.normalize(entity_name)
        if self._selection_state is not None:
            normalized = self._selection_state.set(normalized)
        if self._scene_manager is not None:
            self._scene_manager.set_selected_entity(normalized)
        else:
            world.selected_entity_name = normalized
        if self._selection_state is not None:
            self._selection_state.apply_to_world(world)
        return normalized

    def render(self, world: "World", x: int, y: int, width: int, height: int, input_blocked: bool = False) -> None:
        """Renderiza el panel de jerarquía estilo Unity.

        Args:
            input_blocked: Si True, dibuja el panel pero ignora todos los clicks de ratón.
                           Usar cuando hay un dropdown/modal sobre el panel.
        """
        if not self.visible:
            return
        self._cursor_interactive_rects = []
        self._input_blocked = input_blocked

        self.panel_width = width

        # Input: Close menu if clicking elsewhere (logic inside _draw_context_menu handles its own clicks)
        if self.context_menu_active and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            mouse = rl.get_mouse_position()
            # Simple check: if not in menu (evaluated later), close. 
            # Actually, let's defer closing to _draw_context_menu to check collision properly.
            pass

        # Reset hover frame state
        self.hovered_entity_id = None

        with editor_scissor(rl.Rectangle(x, y, width, height)):
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
            self._register_cursor_rect(plus_rect)
            is_hover_plus = rl.check_collision_point_rec(rl.get_mouse_position(), plus_rect)
            plus_color = self.UNITY_HOVER if is_hover_plus else self.UNITY_HEADER
            rl.draw_rectangle_rec(plus_rect, plus_color)
            rl.draw_text("+", int(x + width - 17), int(y + 4), 14, self.UNITY_TEXT)
            
            if is_hover_plus and not self._input_blocked and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                new_name = f"New Entity {world.entity_count()}"
                if self._scene_manager is not None and self._scene_manager.create_entity(new_name):
                    self._set_selected_entity(world, new_name)
                else:
                    new_entity = world.create_entity(new_name)
                    new_entity.add_component(Transform())
                    self._set_selected_entity(world, new_entity.name)
            
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
            roots = self._get_root_entities(world)
            
            # Reset drop target each frame
            self._drop_target_name = None
            self._drop_as_root = False

            # Renderizar árbol
            for entity in roots:
                content_y = self._render_node(entity, 0, x, content_y, world, content_y_start, content_height)

            # Drag-and-drop reparenting logic
            mouse_pos = rl.get_mouse_position()
            if self._drag_entity_id is not None and not self._is_dragging_entity:
                if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT) and abs(mouse_pos.y - self._drag_start_y) > self._DRAG_THRESHOLD:
                    self._is_dragging_entity = True

            if self._is_dragging_entity:
                # If not hovering over any entity, drop as root (unparent)
                in_content = (x <= mouse_pos.x <= x + width and
                              content_y_start <= mouse_pos.y <= y + height)
                if in_content and self._drop_target_name is None:
                    self._drop_as_root = True
                    rl.draw_line(x + 4, int(mouse_pos.y), x + width - 4, int(mouse_pos.y), rl.Color(58, 121, 187, 200))

                # Draw drag label near cursor
                drag_entity = world.get_entity(self._drag_entity_id) if self._drag_entity_id is not None else None
                if drag_entity is not None:
                    label = drag_entity.name
                    rl.draw_rectangle(int(mouse_pos.x + 12), int(mouse_pos.y - 8), len(label) * 7 + 8, 18, rl.Color(50, 50, 50, 200))
                    rl.draw_text(label, int(mouse_pos.x + 16), int(mouse_pos.y - 5), 10, self.UNITY_TEXT)

                if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                    self._complete_hierarchy_drag(world)

            if not rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                self._drag_entity_id = None
                self._is_dragging_entity = False

        # Context Menu Logic (After scissor to draw on top)
        self._handle_context_input(world, x, y, width, height)

        if self.context_menu_active:
             self._draw_context_menu(world)
            
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
        if y + row_height >= panel_y and y <= panel_y + panel_h:
            self._register_cursor_rect(rl.Rectangle(panel_x, y, self.panel_width, row_height))
            
        if is_hover:
            self.hovered_entity_id = entity.id
            if not self._is_dragging_entity:
                rl.draw_rectangle(panel_x, y, self.panel_width, row_height, self.UNITY_HOVER)

            # Drag-and-drop: track potential drag start
            if not self._input_blocked and not self._is_dragging_entity and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._drag_entity_id = entity.id
                self._drag_start_y = mouse_pos.y

            if not self._input_blocked and not self._is_dragging_entity and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                # Normal click (no drag occurred)
                if self._drag_entity_id == entity.id:
                    self._set_selected_entity(world, entity.name)
                    if has_children:
                        if entity.id in self.expanded_ids:
                            self.expanded_ids.remove(entity.id)
                        else:
                            self.expanded_ids.add(entity.id)
                self._drag_entity_id = None

        # During drag: highlight drop targets
        if self._is_dragging_entity and is_hover:
            drag_entity = world.get_entity(self._drag_entity_id) if self._drag_entity_id is not None else None
            if drag_entity is not None and entity.id != self._drag_entity_id:
                self._drop_target_name = entity.name
                self._drop_as_root = False
                rl.draw_rectangle(panel_x, y, self.panel_width, row_height, rl.Color(44, 93, 135, 100))

        # Highlight Selection
        if self._get_selected_entity_name(world) == entity.name:
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
        return world.get_entity_by_component_instance(transform)

    def _get_root_entities(self, world: "World") -> List[Entity]:
        world_id = id(world)
        world_version = int(getattr(world, "version", -1))
        if self._cached_world_id == world_id and self._cached_world_version == world_version:
            return self._cached_roots

        roots: List[Entity] = []
        for entity in world.iter_all_entities():
            transform = entity.get_component(Transform)
            if transform is None or transform.parent is None:
                roots.append(entity)
        roots.sort(key=lambda item: item.id)

        self._cached_world_id = world_id
        self._cached_world_version = world_version
        self._cached_roots = roots
        return roots

    def _complete_hierarchy_drag(self, world: "World") -> None:
        """Finish a drag-and-drop reparenting operation."""
        drag_entity = world.get_entity(self._drag_entity_id) if self._drag_entity_id is not None else None
        if drag_entity is None or self._scene_manager is None:
            self._is_dragging_entity = False
            self._drag_entity_id = None
            return

        if self._drop_target_name is not None and self._drop_target_name != drag_entity.name:
            self._scene_manager.set_entity_parent(drag_entity.name, self._drop_target_name)
            # Auto-expand the drop target so user sees the child
            target = world.get_entity_by_name(self._drop_target_name)
            if target is not None:
                self.expanded_ids.add(target.id)
        elif self._drop_as_root and drag_entity.parent_name is not None:
            self._scene_manager.set_entity_parent(drag_entity.name, None)

        self._is_dragging_entity = False
        self._drag_entity_id = None
        self._drop_target_name = None
        self._drop_as_root = False

    def _handle_context_input(self, world: "World", x: int, y: int, w: int, h: int) -> None:
        """Maneja el input para abrir el menú contextual en el panel."""
        mouse = rl.get_mouse_position()
        in_panel = rl.check_collision_point_rec(mouse, rl.Rectangle(x, y, w, h))
        
        if in_panel and not self._input_blocked and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT):
            self.context_menu_active = True
            self.context_menu_pos = mouse
            self.context_target_id = self.hovered_entity_id
            
    def _draw_context_menu(self, world: "World") -> None:
        """Dibuja el menú contextual y procesa sus opciones."""
        
        # Options
        options = ["Create Entity"]
        if self.context_target_id is not None:
             options.append("Create Child Entity")
             options.append("Delete Entity")
             options.append("Duplicate Entity")
             entity = world.get_entity(self.context_target_id)
             if entity is not None and entity.parent_name is not None:
                 options.append("Unparent")
             options.append("Save as Prefab")
             
        item_height = 24
        menu_width = 140
        menu_height = len(options) * item_height
        
        mx = int(self.context_menu_pos.x)
        my = int(self.context_menu_pos.y)
        
        # Keep in screen
        if mx + menu_width > rl.get_screen_width(): mx -= menu_width
        if my + menu_height > rl.get_screen_height(): my -= menu_height
        
        menu_rect = rl.Rectangle(mx, my, menu_width, menu_height)
        self._register_cursor_rect(menu_rect)
        
        # Check close (Click outside)
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if not rl.check_collision_point_rec(rl.get_mouse_position(), menu_rect):
                self.context_menu_active = False
                return

        # Draw Menu Background
        rl.draw_rectangle_rec(menu_rect, self.UNITY_BG)
        rl.draw_rectangle_lines_ex(menu_rect, 1, self.UNITY_BORDER)
        
        # Draw Items
        mouse = rl.get_mouse_position()
        
        for i, option in enumerate(options):
            item_y = my + (i * item_height)
            item_rect = rl.Rectangle(mx, item_y, menu_width, item_height)
            self._register_cursor_rect(item_rect)
            
            is_hover = rl.check_collision_point_rec(mouse, item_rect)
            
            if is_hover:
                rl.draw_rectangle_rec(item_rect, self.UNITY_HOVER)
                
            rl.draw_text(option, mx + 10, item_y + 6, 10, self.UNITY_TEXT)
            
            # Click Handler
            if is_hover and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self._execute_context_action(world, option)
                self.context_menu_active = False
                
    def _execute_context_action(self, world: "World", action: str) -> None:
        if action == "Create Entity":
            new_name = f"New Entity {world.entity_count()}"
            if self._scene_manager is not None and self._scene_manager.create_entity(new_name):
                self._set_selected_entity(world, new_name)
            else:
                new_ent = world.create_entity(new_name)
                new_ent.add_component(Transform())
                self._set_selected_entity(world, new_ent.name)
            
        elif action == "Delete Entity" and self.context_target_id is not None:
            entity = world.get_entity(self.context_target_id)
            if entity:
                if self._scene_manager is not None:
                    self._scene_manager.remove_entity(entity.name)
                else:
                    world.destroy_entity(entity.id)
                # Si era el seleccionado, deseleccionar
                if self._get_selected_entity_name(world) == entity.name:
                    self._set_selected_entity(world, None)
                    
        elif action == "Create Child Entity" and self.context_target_id is not None:
            parent_entity = world.get_entity(self.context_target_id)
            if parent_entity is not None and self._scene_manager is not None:
                child_name = f"New Child {world.entity_count()}"
                if self._scene_manager.create_child_entity(parent_entity.name, child_name):
                    self._set_selected_entity(world, child_name)
                    self.expanded_ids.add(self.context_target_id)

        elif action == "Unparent" and self.context_target_id is not None:
            entity = world.get_entity(self.context_target_id)
            if entity is not None and self._scene_manager is not None:
                self._scene_manager.set_entity_parent(entity.name, None)

        elif action == "Duplicate Entity" and self.context_target_id is not None:
            entity = world.get_entity(self.context_target_id)
            if entity is not None and self._scene_manager is not None:
                self._scene_manager.duplicate_entity_subtree(entity.name)

        elif action == "Save as Prefab" and self.context_target_id is not None:
            entity = world.get_entity(self.context_target_id)
            if entity:
                # Use tkinter for dialog (local scope)
                import tkinter as tk
                from tkinter import filedialog
                try:
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes('-topmost', True)
                    path = filedialog.asksaveasfilename(
                        defaultextension=".prefab",
                        filetypes=[("Prefab Files", "*.prefab"), ("All Files", "*.*")],
                        title="Save Entity as Prefab"
                    )
                    root.destroy()
                    
                    if path and self._scene_manager is not None:
                        self._scene_manager.create_prefab(entity.name, path)
                except Exception as e:
                    print(f"[ERROR] Save Prefab dialog failed: {e}")

    def get_cursor_intent(self, mouse_pos: Optional[rl.Vector2] = None) -> CursorVisualState:
        mouse = rl.get_mouse_position() if mouse_pos is None else mouse_pos
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))
