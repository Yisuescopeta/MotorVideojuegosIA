from __future__ import annotations

from typing import Any, Optional

import pyray as rl

from engine.editor.editor_layout import EditorLayout
from engine.editor.editor_selection import EditorSelectionState
from engine.editor.editor_shell_state import EditorPanelSlots, EditorShellState
from engine.editor.hierarchy_panel import HierarchyPanel


class EditorShell:
    """Composes the editor shell without redefining authoring contracts."""

    def __init__(
        self,
        screen_width: Optional[int] = None,
        screen_height: Optional[int] = None,
        *,
        state: Optional[EditorShellState] = None,
        panel_slots: Optional[EditorPanelSlots] = None,
        selection_state: Optional[EditorSelectionState] = None,
        hierarchy_panel: Optional[HierarchyPanel] = None,
        layout: Optional[EditorLayout] = None,
    ) -> None:
        existing_layout = layout
        self.state = state if state is not None else (
            existing_layout.shell_state if existing_layout is not None else EditorShellState()
        )
        self.panel_slots = panel_slots if panel_slots is not None else (
            existing_layout.panel_slots if existing_layout is not None else EditorPanelSlots()
        )
        self.selection_state = selection_state if selection_state is not None else EditorSelectionState()
        self.hierarchy_panel = hierarchy_panel if hierarchy_panel is not None else HierarchyPanel()
        self.hierarchy_panel.set_selection_state(self.selection_state)
        self.layout: Optional[EditorLayout] = None

        if existing_layout is not None:
            self.attach_layout(existing_layout)
        elif screen_width is not None and screen_height is not None:
            self.layout = EditorLayout(
                screen_width,
                screen_height,
                state=self.state,
                panel_slots=self.panel_slots,
            )
            self._wire_hierarchy_layout(self.layout)

    def attach_layout(self, layout: EditorLayout) -> EditorLayout:
        layout.bind_shell(self.state, self.panel_slots)
        self.layout = layout
        self._wire_hierarchy_layout(layout)
        return layout

    def _wire_hierarchy_layout(self, layout: EditorLayout) -> None:
        """Attach the Hierarchy panel to the active layout and overlay menu renderer."""
        # HierarchyPanel opens its context menu through self._layout.show_context_menu(...).
        # The panel is created before EditorLayout exists, so keep the reference in sync here.
        self.hierarchy_panel._layout = layout
        self._ensure_context_menu_overlay(layout)
        self._ensure_hierarchy_context_actions()
        self._ensure_hierarchy_clipboard_shortcuts()

    def _ensure_context_menu_overlay(self, layout: EditorLayout) -> None:
        if bool(getattr(layout, "_hierarchy_context_menu_overlay_bound", False)):
            return

        original_draw_top_dropdowns = getattr(layout, "draw_top_dropdowns", None)
        if not callable(original_draw_top_dropdowns):
            return

        def draw_top_dropdowns_with_context_menu(*args: Any, **kwargs: Any) -> Any:
            result = original_draw_top_dropdowns(*args, **kwargs)
            render_context_menu = getattr(layout, "_render_global_context_menu", None)
            if callable(render_context_menu):
                render_context_menu()
            return result

        layout.draw_top_dropdowns = draw_top_dropdowns_with_context_menu
        layout._hierarchy_context_menu_overlay_bound = True

    def _ensure_hierarchy_context_actions(self) -> None:
        panel = self.hierarchy_panel
        if bool(getattr(panel, "_hierarchy_copy_paste_actions_bound", False)):
            return

        original_execute_context_action = panel._execute_context_action

        def handle_context_input(world: Any, x: int, y: int, w: int, h: int) -> None:
            mouse = rl.get_mouse_position()
            in_panel = rl.check_collision_point_rec(mouse, rl.Rectangle(x, y, w, h))
            if not in_panel or bool(getattr(panel, "_input_blocked", False)):
                return
            if not rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_RIGHT):
                return

            target_entity = world.get_entity(panel.hovered_entity_id) if panel.hovered_entity_id is not None else None
            panel._context_target_name = target_entity.name if target_entity is not None else None
            if target_entity is not None:
                panel._set_selected_entity(world, target_entity.name)

            from engine.editor.ui_core.controls.context_menu import ContextMenuItem, ContextMenuModel

            items = [ContextMenuItem(id="create_entity", label="Create Entity")]
            if panel._context_target_name:
                items.extend(
                    [
                        ContextMenuItem(id="create_child_entity", label="Create Child Entity"),
                        ContextMenuItem(id="copy_entity", label="Copy Entity"),
                        ContextMenuItem(id="paste_entity", label="Paste Entity"),
                        ContextMenuItem(id="duplicate_entity", label="Duplicate Entity"),
                        ContextMenuItem(id="delete_entity", label="Delete Entity"),
                        ContextMenuItem(id="unparent", label="Unparent"),
                        ContextMenuItem(id="save_prefab", label="Save as Prefab"),
                    ]
                )
            else:
                items.append(ContextMenuItem(id="paste_entity", label="Paste Entity"))

            if panel._layout is not None:
                panel._layout.show_context_menu(ContextMenuModel(items=items), mouse.x, mouse.y)

        def execute_context_action(world: Any, action: str) -> None:
            if action == "copy_entity":
                target_name = getattr(panel, "_context_target_name", None)
                if target_name:
                    self._copy_hierarchy_entity(str(target_name))
                return
            if action == "paste_entity":
                self._paste_hierarchy_entity(world)
                return
            original_execute_context_action(world, action)

        panel._handle_context_input = handle_context_input
        panel._execute_context_action = execute_context_action
        panel._hierarchy_copy_paste_actions_bound = True

    def _ensure_hierarchy_clipboard_shortcuts(self) -> None:
        panel = self.hierarchy_panel
        if bool(getattr(panel, "_hierarchy_clipboard_shortcuts_bound", False)):
            return

        original_render = panel.render

        def render_with_clipboard_shortcuts(
            world: Any,
            x: int,
            y: int,
            width: int,
            height: int,
            input_blocked: bool = False,
        ) -> None:
            original_render(world, x, y, width, height, input_blocked)
            self._handle_hierarchy_clipboard_shortcuts(world, x, y, width, height, input_blocked)

        panel.render = render_with_clipboard_shortcuts
        panel._hierarchy_clipboard_shortcuts_bound = True

    def _handle_hierarchy_clipboard_shortcuts(
        self,
        world: Any,
        x: int,
        y: int,
        width: int,
        height: int,
        input_blocked: bool,
    ) -> None:
        if input_blocked or self._keyboard_is_captured_by_bottom_panel():
            return
        mouse = rl.get_mouse_position()
        if not rl.check_collision_point_rec(mouse, rl.Rectangle(x, y, width, height)):
            return
        ctrl_down = rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL)
        if not ctrl_down:
            return
        if rl.is_key_pressed(rl.KEY_C):
            selected_name = self.selection_state.entity_name or getattr(world, "selected_entity_name", None)
            if selected_name:
                self._copy_hierarchy_entity(str(selected_name))
        if rl.is_key_pressed(rl.KEY_V):
            self._paste_hierarchy_entity(world)

    def _keyboard_is_captured_by_bottom_panel(self) -> bool:
        layout = self.layout
        if layout is None:
            return False
        if getattr(layout, "active_bottom_tab", "") == "TERMINAL":
            panel = self.panel_slots.terminal_panel
            return bool(panel is not None and hasattr(panel, "captures_keyboard") and panel.captures_keyboard())
        if getattr(layout, "active_bottom_tab", "") == "AGENT":
            panel = self.panel_slots.agent_panel
            return bool(panel is not None and hasattr(panel, "captures_keyboard") and panel.captures_keyboard())
        return False

    def _copy_hierarchy_entity(self, entity_name: str) -> bool:
        manager = getattr(self.hierarchy_panel, "_scene_manager", None)
        copy_entity_subtree = getattr(manager, "copy_entity_subtree", None) if manager is not None else None
        return bool(entity_name and callable(copy_entity_subtree) and copy_entity_subtree(entity_name))

    def _paste_hierarchy_entity(self, world: Any) -> bool:
        manager = getattr(self.hierarchy_panel, "_scene_manager", None)
        paste_copied_entities = getattr(manager, "paste_copied_entities", None) if manager is not None else None
        if not callable(paste_copied_entities):
            return False

        before_names = set(self._collect_world_entity_names(world))
        if not paste_copied_entities():
            return False

        active_world = getattr(manager, "active_world", None) or world
        for entity_name in self._collect_world_entity_names(active_world):
            if entity_name not in before_names:
                self.hierarchy_panel._set_selected_entity(active_world, entity_name)
                break
        return True

    @staticmethod
    def _collect_world_entity_names(world: Any) -> list[str]:
        if world is None or not hasattr(world, "iter_all_entities"):
            return []
        return [str(entity.name) for entity in world.iter_all_entities() if getattr(entity, "name", None)]

    def ensure_layout(self, screen_width: int, screen_height: int) -> EditorLayout:
        if self.layout is None:
            self.layout = EditorLayout(
                screen_width,
                screen_height,
                state=self.state,
                panel_slots=self.panel_slots,
            )
            self._wire_hierarchy_layout(self.layout)
        else:
            self.layout.bind_shell(self.state, self.panel_slots)
            self._wire_hierarchy_layout(self.layout)
        return self.layout

    def bind_scene_manager(self, manager: Any) -> None:
        self.hierarchy_panel.set_scene_manager(manager)
        for panel_name in ("flow_panel", "flow_workspace_panel"):
            panel = getattr(self.panel_slots, panel_name, None)
            if panel is not None and hasattr(panel, "set_scene_manager"):
                panel.set_scene_manager(manager)

    def bind_project_service(self, service: Any) -> None:
        project_panel = self.panel_slots.project_panel
        if project_panel is not None and hasattr(project_panel, "set_project_service"):
            project_panel.set_project_service(service)
        for panel_name in ("flow_panel", "flow_workspace_panel"):
            panel = getattr(self.panel_slots, panel_name, None)
            if panel is not None and hasattr(panel, "set_project_service"):
                panel.set_project_service(service)

    def bind_terminal_panel(self, panel: Any) -> None:
        self.panel_slots.terminal_panel = panel
        if self.layout is not None:
            self.layout.terminal_panel = panel

    def bind_agent_panel(self, panel: Any) -> None:
        self.panel_slots.agent_panel = panel
        if self.layout is not None:
            self.layout.agent_panel = panel

    def bind_export_panel(self, panel: Any) -> None:
        self.panel_slots.export_panel = panel
        if self.layout is not None:
            self.layout.export_panel = panel
