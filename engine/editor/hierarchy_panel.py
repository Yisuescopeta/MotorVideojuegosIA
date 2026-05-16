"""
engine/editor/hierarchy_panel.py - Panel de Jerarquía estilo Unity

PROPÓSITO:
    Muestra el árbol de entidades de la escena.
    Permite seleccionar entidades y visualizar relaciones padre-hijo.
"""

from typing import Any, List, Optional, Set, Tuple

import pyray as rl
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.editor_selection import EditorSelectionState
from engine.editor.render_safety import editor_scissor
from engine.editor.theme import get_active_theme
from engine.editor.ui.icons import draw_icon
from engine.editor.ui.tree_view import TreeModel, filter_visible_rows, get_type_icon


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

    def __init__(self, selection_state: Optional[EditorSelectionState] = None, layout: Any = None) -> None:
        self.visible: bool = True
        self._layout = layout
        self.scroll_offset: int = 0
        self.expanded_ids: Set[int] = set()
        self.panel_width: int = 200
        self._scene_manager: Any = None
        self._selection_state: Optional[EditorSelectionState] = selection_state
        self._cached_world_id: int = -1
        self._cached_structure_version: int = -1
        self._cached_roots: List[Entity] = []
        self._cached_tree_model: Optional[TreeModel] = None
        self._cached_rows_world_id: int = -1
        self._cached_rows_structure_version: int = -1
        self._cached_rows_expanded_ids: Tuple[int, ...] = ()
        self._cached_rows_search_text: str = ""
        self._cached_visible_rows: List[Tuple[int, int]] = []
        self.search_text: str = ""

        self.hovered_entity_id: Optional[int] = None
        self._context_target_name: Optional[str] = None
        self._cursor_interactive_rects: List[rl.Rectangle] = []
        self._input_blocked: bool = False

        # Drag-and-drop reparenting state
        self._drag_entity_id: Optional[int] = None
        self._drag_entity_scene_id: Optional[str] = None
        self._drag_start_y: float = 0.0
        self._is_dragging_entity: bool = False
        self._drop_target_name: Optional[str] = None
        self._drop_target_scene_id: Optional[str] = None
        self._drop_as_root: bool = False
        self._DRAG_THRESHOLD: int = 5

    def set_scene_manager(self, manager: Any) -> None:
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

    def _resolve_colors(self) -> dict:
        """Resolve colors from the active editor theme."""
        try:
            theme = get_active_theme()
            return {
                "BG": rl.Color(*theme.panel),
                "HEADER": rl.Color(*theme.panel_header),
                "BORDER": rl.Color(*theme.border),
                "SELECTED": rl.Color(*theme.accent),
                "HOVER": rl.Color(*theme.border_hover),
                "TEXT": rl.Color(*theme.text),
                "TEXT_DIM": rl.Color(*theme.text_muted),
                "TAB_LINE": rl.Color(*theme.accent),
            }
        except Exception:
            return {
                "BG": self.UNITY_BG,
                "HEADER": self.UNITY_HEADER,
                "BORDER": self.UNITY_BORDER,
                "SELECTED": self.UNITY_SELECTED,
                "HOVER": self.UNITY_HOVER,
                "TEXT": self.UNITY_TEXT,
                "TEXT_DIM": self.UNITY_TEXT_DIM,
                "TAB_LINE": self.UNITY_TAB_LINE,
            }

    def render(self, world: "World", x: int, y: int, width: int, height: int, input_blocked: bool = False) -> None:
        """Renderiza el panel de jerarquía estilo Unity.

        Args:
            input_blocked: Si True, dibuja el panel pero ignora todos los clicks de ratón.
                           Usar cuando hay un dropdown/modal sobre el panel.
        """
        if not self.visible:
            return
        colors = self._resolve_colors()
        self._cursor_interactive_rects = []
        self._input_blocked = input_blocked

        self.panel_width = width

        # Reset hover frame state
        self.hovered_entity_id = None

        with editor_scissor(rl.Rectangle(x, y, width, height)):
            # ========================================
            # 1. Header Tab
            # ========================================
            header_rect = rl.Rectangle(x, y, width, self.HEADER_HEIGHT)
            rl.draw_rectangle_rec(header_rect, colors["HEADER"])

            # Tab "Hierarchy" con línea azul
            tab_width = 70
            tab_rect = rl.Rectangle(x + 2, y + 2, tab_width, self.HEADER_HEIGHT - 4)
            rl.draw_rectangle_rec(tab_rect, colors["BG"])
            # Línea azul inferior
            rl.draw_rectangle(int(x + 2), int(y + self.HEADER_HEIGHT - 2), tab_width, 2, colors["TAB_LINE"])
            # Texto
            rl.draw_text("Hierarchy", int(x + 10), int(y + 6), 10, colors["TEXT"])

            # Botón + (crear objeto)
            plus_rect = rl.Rectangle(x + width - 22, y + 2, 18, 18)
            self._register_cursor_rect(plus_rect)
            is_hover_plus = rl.check_collision_point_rec(rl.get_mouse_position(), plus_rect)
            plus_color = colors["HOVER"] if is_hover_plus else colors["HEADER"]
            rl.draw_rectangle_rec(plus_rect, plus_color)
            rl.draw_text("+", int(x + width - 17), int(y + 4), 14, colors["TEXT"])

            if is_hover_plus and not self._input_blocked and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                new_name = f"New Entity {world.entity_count()}"
                if self._scene_manager is not None and self._scene_manager.create_entity(new_name):
                    self._set_selected_entity(world, new_name)
                else:
                    new_entity = world.create_entity(new_name)
                    new_entity.add_component(Transform())
                    self._set_selected_entity(world, new_entity.name)

            # Línea separadora
            rl.draw_line(x, int(y + self.HEADER_HEIGHT), x + width, int(y + self.HEADER_HEIGHT), colors["BORDER"])

            # ========================================
            # 2. Content Area
            # ========================================
            search_y = y + self.HEADER_HEIGHT + 4
            search_height = 18
            content_y_start = search_y + search_height + 4
            content_height = height - self.HEADER_HEIGHT - search_height - 4

            # Fondo del contenido
            rl.draw_rectangle(x, int(y + self.HEADER_HEIGHT), width, int(height - self.HEADER_HEIGHT), colors["BG"])
            self._draw_search_field(x, search_y, width, search_height)

            # Obtener entidades raíz
            visible_rows = self._get_visible_rows(world)

            # Reset drop target each frame
            self._drop_target_name = None
            self._drop_target_scene_id = None
            self._drop_as_root = False

            # Renderizar árbol
            row_height = self.LINE_HEIGHT
            first_row = max(0, self.scroll_offset // row_height)
            last_row = min(
                len(visible_rows),
                ((self.scroll_offset + content_height) // row_height) + 2,
            )
            base_y = content_y_start - self.scroll_offset
            for row_index in range(first_row, last_row):
                entity_id, depth = visible_rows[row_index]
                entity = world.get_entity(entity_id)
                if entity is None:
                    continue
                row_y = base_y + (row_index * row_height)
                self._render_row(entity, depth, x, row_y, world, content_y_start, content_height)

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
                    rl.draw_text(label, int(mouse_pos.x + 16), int(mouse_pos.y - 5), 10, colors["TEXT"])

                if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                    self._complete_hierarchy_drag(world)

            if not rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                self._drag_entity_id = None
                self._drag_entity_scene_id = None
                self._is_dragging_entity = False

        # Context Menu Logic (After scissor to draw on top)
        self._handle_context_input(world, x, y, width, height)

        # Process context menu action from global menu
        if self._layout:
            action = self._layout._process_global_context_menu()
            if action:
                self._execute_context_action(world, action)

    def _render_row(self, entity: Entity, depth: int, panel_x: int, y: int, world: "World", panel_y: int, panel_h: int) -> None:
        """Renderiza una fila visible de la jerarquia."""
        colors = self._resolve_colors()
        tree_model = self._get_tree_model(world)
        node = tree_model.node_map.get(entity.id)
        has_children = bool(node.is_expandable) if node is not None else bool(self._get_child_entities(world, entity))

        # Dibujar fila
        row_height = self.LINE_HEIGHT

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
                rl.draw_rectangle(panel_x, y, self.panel_width, row_height, colors["HOVER"])

            # Drag-and-drop: track potential drag start
            if not self._input_blocked and not self._is_dragging_entity and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._drag_entity_id = entity.id
                self._drag_entity_scene_id = self._serialized_entity_id(entity)
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
                self._drop_target_scene_id = self._serialized_entity_id(entity)
                self._drop_as_root = False
                rl.draw_rectangle(panel_x, y, self.panel_width, row_height, rl.Color(44, 93, 135, 100))

        # Highlight Selection
        if self._get_selected_entity_name(world) == entity.name:
            rl.draw_rectangle(panel_x, y, self.panel_width, row_height, colors["SELECTED"])

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

        # Icono + nombre
        text_x = indent_x
        if node is not None:
            draw_icon(get_type_icon(node.entity_type), (int(indent_x), int(y + 3), 12, 12), (180, 180, 180, 255))
            text_x += 15
        rl.draw_text(
            f"{entity.name}",
            int(text_x),
            int(y + 4),
            self.FONT_SIZE,
            colors["TEXT"]
        )

        return None

    def _find_entity_by_transform(self, world: "World", transform: Transform) -> Optional[Entity]:
        return world.get_entity_by_component_instance(transform)

    def _get_world_structure_version(self, world: "World") -> int:
        return int(getattr(world, "structure_version", getattr(world, "version", -1)))

    def _get_root_entities(self, world: "World") -> List[Entity]:
        model = self._get_tree_model(world)
        roots = [world.get_entity(node.id) for node in model.root_nodes]
        return [entity for entity in roots if entity is not None]

    def _get_child_entities(self, world: "World", entity: Entity) -> List[Entity]:
        model = self._get_tree_model(world)
        node = model.node_map.get(entity.id)
        if node is None:
            return []
        children = [world.get_entity(child.id) for child in node.children]
        return [child for child in children if child is not None]

    def _get_tree_model(self, world: "World") -> TreeModel:
        world_id = id(world)
        structure_version = self._get_world_structure_version(world)
        if (
            self._cached_tree_model is not None
            and self._cached_world_id == world_id
            and self._cached_structure_version == structure_version
        ):
            return self._cached_tree_model

        model = TreeModel.build(world)
        self._cached_world_id = world_id
        self._cached_structure_version = structure_version
        self._cached_tree_model = model
        roots: List[Entity] = []
        for node in model.root_nodes:
            entity = world.get_entity(node.id)
            if entity is not None:
                roots.append(entity)
        self._cached_roots = roots
        return model

    def _get_visible_rows(self, world: "World") -> List[Tuple[int, int]]:
        world_id = id(world)
        structure_version = self._get_world_structure_version(world)
        expanded_ids = tuple(sorted(self.expanded_ids))
        search_text = self.search_text.strip().lower()
        if (
            self._cached_rows_world_id == world_id
            and self._cached_rows_structure_version == structure_version
            and self._cached_rows_expanded_ids == expanded_ids
            and self._cached_rows_search_text == search_text
        ):
            return self._cached_visible_rows

        rows = self._build_visible_rows(world, self._get_root_entities(world))
        self._cached_rows_world_id = world_id
        self._cached_rows_structure_version = structure_version
        self._cached_rows_expanded_ids = expanded_ids
        self._cached_rows_search_text = search_text
        self._cached_visible_rows = rows
        return rows

    def _build_visible_rows(self, world: "World", roots: List[Entity]) -> List[Tuple[int, int]]:
        del roots
        model = self._get_tree_model(world)
        return filter_visible_rows(model, self.expanded_ids, self.search_text)

    def _draw_search_field(self, x: int, y: int, width: int, height: int) -> None:
        colors = self._resolve_colors()
        field_rect = rl.Rectangle(x + 6, y, max(0, width - 12), height)
        rl.draw_rectangle_rec(field_rect, rl.Color(35, 35, 35, 255))
        rl.draw_rectangle_lines_ex(field_rect, 1, colors["BORDER"])
        label = self.search_text if self.search_text else "Search"
        color = colors["TEXT"] if self.search_text else colors["TEXT_DIM"]
        rl.draw_text(label[:32], int(field_rect.x + 6), int(field_rect.y + 5), self.FONT_SIZE, color)

    def _complete_hierarchy_drag(self, world: "World") -> None:
        """Finish a drag-and-drop reparenting operation."""
        drag_entity = self._resolve_drag_entity(world)
        if drag_entity is None or self._scene_manager is None:
            self._is_dragging_entity = False
            self._drag_entity_id = None
            self._drag_entity_scene_id = None
            return

        drop_target_name = self._resolve_entity_name_by_serialized_id(world, self._drop_target_scene_id) or self._drop_target_name
        if drop_target_name is not None and drop_target_name != drag_entity.name:
            self._scene_manager.set_entity_parent(drag_entity.name, drop_target_name)
            # Auto-expand the drop target so user sees the child
            target = world.get_entity_by_name(drop_target_name)
            if target is not None:
                self.expanded_ids.add(target.id)
        elif self._drop_as_root and drag_entity.parent_name is not None:
            self._scene_manager.set_entity_parent(drag_entity.name, None)

        self._is_dragging_entity = False
        self._drag_entity_id = None
        self._drag_entity_scene_id = None
        self._drop_target_name = None
        self._drop_target_scene_id = None
        self._drop_as_root = False

    def _resolve_drag_entity(self, world: "World") -> Optional[Entity]:
        entity = self._resolve_entity_by_serialized_id(world, self._drag_entity_scene_id)
        if entity is not None:
            return entity
        return world.get_entity(self._drag_entity_id) if self._drag_entity_id is not None else None

    def _resolve_entity_by_serialized_id(self, world: "World", entity_id: Optional[str]) -> Optional[Entity]:
        if not entity_id:
            return None
        get_by_serialized_id = getattr(world, "get_entity_by_serialized_id", None)
        if callable(get_by_serialized_id):
            return get_by_serialized_id(entity_id)
        for entity in world.iter_all_entities():
            if self._serialized_entity_id(entity) == entity_id:
                return entity
        return None

    def _resolve_entity_name_by_serialized_id(self, world: "World", entity_id: Optional[str]) -> Optional[str]:
        entity = self._resolve_entity_by_serialized_id(world, entity_id)
        return entity.name if entity is not None else None

    @staticmethod
    def _serialized_entity_id(entity: Entity) -> Optional[str]:
        value = getattr(entity, "serialized_id", None)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _handle_context_input(self, world: "World", x: int, y: int, w: int, h: int) -> None:
        """Maneja el input para abrir el menú contextual en el panel."""
        mouse = rl.get_mouse_position()
        in_panel = rl.check_collision_point_rec(mouse, rl.Rectangle(x, y, w, h))

        if in_panel and not self._input_blocked and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT):
            target_entity = world.get_entity(self.hovered_entity_id) if self.hovered_entity_id is not None else None
            self._context_target_name = target_entity.name if target_entity else None
            from engine.editor.ui_core.controls.context_menu import ContextMenuItem, ContextMenuModel
            items = [
                ContextMenuItem(id="create_entity", label="Create Entity"),
            ]
            if self._context_target_name:
                items.extend([
                    ContextMenuItem(id="create_child_entity", label="Create Child Entity"),
                    ContextMenuItem(id="delete_entity", label="Delete Entity"),
                    ContextMenuItem(id="duplicate_entity", label="Duplicate Entity"),
                    ContextMenuItem(id="unparent", label="Unparent"),
                    ContextMenuItem(id="save_prefab", label="Save as Prefab"),
                ])
            menu = ContextMenuModel(id="hierarchy_menu", items=items)
            if self._layout:
                self._layout.show_context_menu(menu, mouse.x, mouse.y)

    def _execute_context_action(self, world: "World", action: str) -> None:
        if action == "create_entity":
            new_name = f"New Entity {world.entity_count()}"
            if self._scene_manager is not None and self._scene_manager.create_entity(new_name):
                self._set_selected_entity(world, new_name)
            else:
                new_ent = world.create_entity(new_name)
                new_ent.add_component(Transform())
                self._set_selected_entity(world, new_ent.name)

        elif action in ("delete_entity", "create_child_entity", "duplicate_entity", "unparent", "save_prefab"):
            target_name = self._context_target_name
            if target_name is None:
                return
            entity = None
            for e in world.iter_all_entities():
                if e.name == target_name:
                    entity = e
                    break
            if entity is None:
                return

            if action == "delete_entity":
                if self._scene_manager is not None:
                    self._scene_manager.remove_entity(entity.name)
                else:
                    world.destroy_entity(entity.id)
                if self._get_selected_entity_name(world) == entity.name:
                    self._set_selected_entity(world, None)

            elif action == "create_child_entity":
                if self._scene_manager is not None:
                    child_name = f"New Child {world.entity_count()}"
                    if self._scene_manager.create_child_entity(entity.name, child_name):
                        self._set_selected_entity(world, child_name)
                        self.expanded_ids.add(entity.id)

            elif action == "unparent":
                if self._scene_manager is not None:
                    self._scene_manager.set_entity_parent(entity.name, None)

            elif action == "duplicate_entity":
                if self._scene_manager is not None:
                    self._scene_manager.duplicate_entity_subtree(entity.name)

            elif action == "save_prefab":
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
