from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.editor.agent_panel import AgentPanel
from engine.editor.console_panel import ConsolePanel
from engine.editor.project_panel import ProjectPanel
from engine.editor.scene_flow_panel import SceneFlowPanel


@dataclass(slots=True)
class EditorPanelSlots:
    """Composable editor panels mounted into the shell layout."""

    project_panel: Any = field(default_factory=lambda: ProjectPanel("assets"))
    flow_panel: Any = field(default_factory=SceneFlowPanel)
    flow_workspace_panel: Any = field(default_factory=SceneFlowPanel)
    console_panel: Any = field(default_factory=ConsolePanel)
    terminal_panel: Any = None
    agent_panel: Any = field(default_factory=AgentPanel)


@dataclass(slots=True)
class EditorShellState:
    """Serializable-in-spirit UI shell state for the editor surface."""

    active_tab: str = "SCENE"
    active_bottom_tab: str = "PROJECT"
    request_play: bool = False
    request_stop: bool = False
    request_pause: bool = False
    request_step: bool = False
    request_new_scene: bool = False
    request_create_scene: bool = False
    request_save_scene: bool = False
    request_load_scene: bool = False
    request_browse_scene_file: bool = False
    request_activate_scene_key: str = ""
    request_close_scene_key: str = ""
    request_open_project: bool = False
    request_browse_project: bool = False
    request_create_project: bool = False
    request_exit_launcher: bool = False
    request_remove_project_path: str = ""
    request_create_canvas: bool = False
    request_create_ui_text: bool = False
    request_create_ui_button: bool = False
    request_exit: bool = False
    request_undo: bool = False
    request_redo: bool = False
    request_duplicate_entity: bool = False
    request_delete_entity: bool = False
    request_create_entity: bool = False
    show_about_modal: bool = False
    recent_projects: list[dict[str, Any]] = field(default_factory=list)
    show_project_modal: bool = False
    show_project_launcher: bool = False
    show_create_project_modal: bool = False
    show_create_scene_modal: bool = False
    show_scene_browser_modal: bool = False
    show_project_dirty_modal: bool = False
    dirty_modal_context: str = ""
    pending_project_path: str = ""
    pending_scene_open_path: str = ""
    pending_scene_close_key: str = ""
    project_switch_decision: str = ""
    launcher_search_text: str = ""
    launcher_search_focused: bool = False
    launcher_scroll_offset: float = 0.0
    launcher_feedback_text: str = ""
    launcher_feedback_is_error: bool = False
    launcher_create_name: str = "NewProject"
    launcher_create_name_focused: bool = False
    scene_create_name: str = "New Scene"
    scene_create_name_focused: bool = False
    project_scene_entries: list[dict[str, Any]] = field(default_factory=list)
    scene_browser_scroll_offset: float = 0.0
    scene_tabs: list[dict[str, Any]] = field(default_factory=list)
    active_scene_tab_key: str = ""
