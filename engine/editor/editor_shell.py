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

    def attach_layout(self, layout: EditorLayout) -> EditorLayout:
        layout.bind_shell(self.state, self.panel_slots)
        self.layout = layout
        return layout

    def ensure_layout(self, screen_width: int, screen_height: int) -> EditorLayout:
        if self.layout is None:
            self.layout = EditorLayout(
                screen_width,
                screen_height,
                state=self.state,
                panel_slots=self.panel_slots,
            )
        else:
            self.layout.bind_shell(self.state, self.panel_slots)
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
        agent_panel = getattr(self.panel_slots, "agent_panel", None)
        if agent_panel is not None and hasattr(agent_panel, "set_project_service"):
            agent_panel.set_project_service(service)

    def bind_terminal_panel(self, panel: Any) -> None:
        self.panel_slots.terminal_panel = panel
        if self.layout is not None:
            self.layout.terminal_panel = panel

    def bind_agent_panel(self, panel: Any) -> None:
        self.panel_slots.agent_panel = panel
        if self.layout is not None:
            self.layout.agent_panel = panel
