from __future__ import annotations

from typing import Any, Optional

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
