from __future__ import annotations

import os
from typing import Any, Callable

import pyray as rl

from engine.core.engine_state import EngineState
from engine.editor.console_panel import log_err, log_info


class ProjectWorkspaceController:
    """Owns project activation, workspace persistence, and launcher workflows."""

    def __init__(
        self,
        *,
        get_project_service: Callable[[], Any],
        get_scene_manager: Callable[[], Any],
        get_editor_layout: Callable[[], Any],
        get_editor_selection: Callable[[], Any],
        get_state: Callable[[], EngineState],
        get_current_scene_path: Callable[[], str],
        set_current_scene_path: Callable[[str], None],
        is_project_loaded: Callable[[], bool],
        set_project_loaded: Callable[[bool], None],
        set_world: Callable[[Any], None],
        terminal_panel: Any,
        animator_panel: Any,
        sprite_editor_modal: Any,
        history_manager: Any,
        hot_reload_manager: Any,
        timeline: Any,
        get_render_system: Callable[[], Any],
        get_ui_render_system: Callable[[], Any],
        get_audio_system: Callable[[], Any],
        get_script_behaviour_system: Callable[[], Any],
        get_rule_system: Callable[[], Any],
        get_event_bus: Callable[[], Any],
        load_scene_by_path: Callable[[str], bool],
        sync_scene_workspace_ui: Callable[[bool], None],
        save_all_dirty_scenes: Callable[[], bool],
        save_scene_entry: Callable[[str | None, bool], bool],
        close_scene_workspace_tab: Callable[[str, bool], bool],
        stop_runtime: Callable[[], None],
        set_running: Callable[[bool], None],
    ) -> None:
        self._get_project_service = get_project_service
        self._get_scene_manager = get_scene_manager
        self._get_editor_layout = get_editor_layout
        self._get_editor_selection = get_editor_selection
        self._get_state = get_state
        self._get_current_scene_path = get_current_scene_path
        self._set_current_scene_path = set_current_scene_path
        self._is_project_loaded = is_project_loaded
        self._set_project_loaded = set_project_loaded
        self._set_world = set_world
        self._terminal_panel = terminal_panel
        self._animator_panel = animator_panel
        self._sprite_editor_modal = sprite_editor_modal
        self._history_manager = history_manager
        self._hot_reload_manager = hot_reload_manager
        self._timeline = timeline
        self._get_render_system = get_render_system
        self._get_ui_render_system = get_ui_render_system
        self._get_audio_system = get_audio_system
        self._get_script_behaviour_system = get_script_behaviour_system
        self._get_rule_system = get_rule_system
        self._get_event_bus = get_event_bus
        self._load_scene_by_path = load_scene_by_path
        self._sync_scene_workspace_ui = sync_scene_workspace_ui
        self._save_all_dirty_scenes = save_all_dirty_scenes
        self._save_scene_entry = save_scene_entry
        self._close_scene_workspace_tab = close_scene_workspace_tab
        self._stop_runtime = stop_runtime
        self._set_running = set_running

    def set_project_service(self, service: Any) -> None:
        editor_layout = self._get_editor_layout()
        scene_manager = self._get_scene_manager()
        if self._terminal_panel is not None:
            self._terminal_panel.set_project_service(service)
        if editor_layout is not None:
            editor_layout.terminal_panel = self._terminal_panel
            agent_panel = getattr(editor_layout, "agent_panel", None)
            if agent_panel is not None and hasattr(agent_panel, "set_project_service"):
                agent_panel.set_project_service(service)
            editor_layout.set_recent_projects(service.list_launcher_projects())
            editor_layout.set_project_scene_entries(service.list_project_scenes() if service.has_project else [])
            if getattr(editor_layout, "flow_panel", None) is not None:
                editor_layout.flow_panel.set_project_service(service)
                if scene_manager is not None:
                    editor_layout.flow_panel.set_scene_manager(scene_manager)
            if getattr(editor_layout, "flow_workspace_panel", None) is not None:
                editor_layout.flow_workspace_panel.set_project_service(service)
                if scene_manager is not None:
                    editor_layout.flow_workspace_panel.set_scene_manager(scene_manager)

        if not service.has_project:
            self._set_project_loaded(False)
            self._set_current_scene_path("")
            return

        render_system = self._get_render_system()
        if render_system is not None:
            render_system.set_project_service(service)

        ui_render_system = self._get_ui_render_system()
        if ui_render_system is not None and hasattr(ui_render_system, "set_project_service"):
            ui_render_system.set_project_service(service)

        audio_system = self._get_audio_system()
        if audio_system is not None and hasattr(audio_system, "set_project_service"):
            audio_system.set_project_service(service)

        if self._animator_panel is not None:
            self._animator_panel.set_project_service(service)

        if self._sprite_editor_modal is not None:
            self._sprite_editor_modal.set_project_service(service)
            self._sprite_editor_modal.set_history_manager(self._history_manager)

        self._hot_reload_manager.scripts_dir = service.get_project_path("scripts").as_posix()
        self._hot_reload_manager.scan_directory()

        script_behaviour_system = self._get_script_behaviour_system()
        if script_behaviour_system is not None:
            script_behaviour_system.set_hot_reload_manager(self._hot_reload_manager)
            if hasattr(script_behaviour_system, "set_project_service"):
                script_behaviour_system.set_project_service(service)

        if editor_layout is not None and editor_layout.project_panel is not None:
            editor_layout.project_panel.set_project_service(service)
            editor_layout.set_recent_projects(service.list_launcher_projects())
            if scene_manager is not None:
                editor_layout.set_scene_tabs(scene_manager.list_open_scenes(), scene_manager.active_scene_key)
            editor_layout.apply_editor_preferences(service.load_editor_state().get("preferences", {}))

        self._set_project_loaded(True)

    def refresh_launcher_projects(self) -> None:
        project_service = self._get_project_service()
        editor_layout = self._get_editor_layout()
        if project_service is None or editor_layout is None:
            return
        editor_layout.set_recent_projects(project_service.list_launcher_projects())

    def refresh_project_scene_entries(self) -> None:
        project_service = self._get_project_service()
        editor_layout = self._get_editor_layout()
        if project_service is None or editor_layout is None:
            return
        editor_layout.set_project_scene_entries(
            project_service.list_project_scenes() if project_service.has_project else []
        )
        if getattr(editor_layout, "flow_panel", None) is not None:
            editor_layout.flow_panel.refresh(force=True)
        if getattr(editor_layout, "flow_workspace_panel", None) is not None:
            editor_layout.flow_workspace_panel.refresh(force=True)

    def persist_editor_preferences(self) -> None:
        project_service = self._get_project_service()
        editor_layout = self._get_editor_layout()
        if project_service is None or editor_layout is None or not project_service.has_project:
            return
        state = project_service.load_editor_state()
        state["preferences"] = editor_layout.export_editor_preferences()
        project_service.save_editor_state(state)

    def reset_project_bound_state(self) -> None:
        if self._get_state() in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
            self._stop_runtime()
        if self._animator_panel is not None:
            self._animator_panel.reset()
        if self._sprite_editor_modal is not None:
            self._sprite_editor_modal.close()
        rule_system = self._get_rule_system()
        if rule_system is not None:
            rule_system.clear_rules()
        event_bus = self._get_event_bus()
        if event_bus is not None:
            event_bus.clear_history()
        render_system = self._get_render_system()
        if render_system is not None and hasattr(render_system, "reset_project_resources"):
            render_system.reset_project_resources()
        ui_render_system = self._get_ui_render_system()
        if ui_render_system is not None and hasattr(ui_render_system, "reset_project_resources"):
            ui_render_system.reset_project_resources()
        self._timeline.clear()

    def capture_active_scene_view_state(self) -> None:
        scene_manager = self._get_scene_manager()
        editor_layout = self._get_editor_layout()
        if scene_manager is None or editor_layout is None:
            return
        active_key = scene_manager.active_scene_key
        if not active_key:
            return
        active_world = scene_manager.get_edit_world()
        selection_state = self._get_editor_selection()
        if selection_state is not None:
            selected_entity = selection_state.sync_from_world(active_world)
        else:
            selected_entity = active_world.selected_entity_name if active_world is not None else None
        scene_manager.set_scene_view_state(
            active_key,
            {
                "selected_entity": selected_entity,
                "camera_target": {
                    "x": float(editor_layout.editor_camera.target.x),
                    "y": float(editor_layout.editor_camera.target.y),
                },
                "camera_zoom": float(editor_layout.editor_camera.zoom),
            },
        )

    def apply_active_scene_view_state(self) -> None:
        scene_manager = self._get_scene_manager()
        editor_layout = self._get_editor_layout()
        if scene_manager is None or editor_layout is None:
            return
        view_state = scene_manager.get_scene_view_state()
        camera_target = view_state.get("camera_target", {})
        if isinstance(camera_target, dict):
            editor_layout.editor_camera.target = rl.Vector2(
                float(camera_target.get("x", 0.0)),
                float(camera_target.get("y", 0.0)),
            )
        editor_layout.editor_camera.zoom = max(0.1, float(view_state.get("camera_zoom", 1.0) or 1.0))
        selected_entity = view_state.get("selected_entity")
        selection_state = self._get_editor_selection()
        if selection_state is not None:
            selected_entity = selection_state.set(selected_entity)
        scene_manager.set_selected_entity(str(selected_entity) if selected_entity else None)
        if selection_state is not None:
            selection_state.apply_to_world(scene_manager.get_edit_world())

    def persist_workspace_state(self) -> None:
        project_service = self._get_project_service()
        scene_manager = self._get_scene_manager()
        if project_service is None or scene_manager is None or not project_service.has_project:
            return
        state = project_service.load_editor_state()
        workspace_state = scene_manager.get_workspace_state()
        state["open_scenes"] = [
            project_service.to_relative_path(scene_ref) if str(scene_ref).endswith(".json") else str(scene_ref)
            for scene_ref in workspace_state.get("open_scenes", [])
        ]
        active_scene = str(workspace_state.get("active_scene", "") or "")
        state["active_scene"] = project_service.to_relative_path(active_scene) if active_scene.endswith(".json") else active_scene
        scene_view_states = {}
        for scene_ref, view_state in dict(workspace_state.get("scene_view_states", {})).items():
            normalized_ref = project_service.to_relative_path(scene_ref) if str(scene_ref).endswith(".json") else str(scene_ref)
            scene_view_states[normalized_ref] = dict(view_state)
        state["scene_view_states"] = scene_view_states
        current_scene_path = self._get_current_scene_path()
        state["last_scene"] = project_service.to_relative_path(current_scene_path) if current_scene_path else ""
        project_service.save_editor_state(state)

    def restore_workspace_from_project_state(self) -> bool:
        project_service = self._get_project_service()
        scene_manager = self._get_scene_manager()
        if project_service is None or scene_manager is None or not project_service.has_project:
            return False
        state = project_service.load_editor_state()
        open_scenes = list(state.get("open_scenes", []))
        scene_view_states = dict(state.get("scene_view_states", {}))
        for scene_ref in open_scenes:
            resolved_path = project_service.resolve_path(scene_ref).as_posix()
            if not os.path.exists(resolved_path):
                continue
            world = scene_manager.load_scene_from_file(resolved_path, activate=False)
            if world is None:
                continue
            saved_state = scene_view_states.get(scene_ref) or scene_view_states.get(resolved_path)
            if isinstance(saved_state, dict):
                scene_manager.set_scene_view_state(resolved_path, saved_state)

        desired_active = str(state.get("active_scene", "") or "").strip()
        if desired_active:
            desired_active = project_service.resolve_path(desired_active).as_posix()
        elif project_service.get_last_scene():
            desired_active = project_service.resolve_path(project_service.get_last_scene()).as_posix()

        if desired_active and os.path.exists(desired_active):
            scene_manager.load_scene_from_file(desired_active, activate=False)

        open_entries = scene_manager.list_open_scenes()
        if not open_entries:
            return False

        target_key = desired_active if desired_active else str(open_entries[0].get("key", ""))
        scene_manager.activate_scene(target_key)
        self._sync_scene_workspace_ui(True)
        return True

    def pick_initial_scene_path(self) -> str:
        project_service = self._get_project_service()
        if project_service is None or not project_service.has_project:
            return ""
        levels_root = project_service.get_project_path("levels")
        startup_scene = str(project_service.load_project_settings().get("startup_scene", "")).strip()
        if startup_scene:
            startup_path = project_service.resolve_path(startup_scene).as_posix()
            if os.path.exists(startup_path):
                return startup_path
        last_scene = project_service.get_last_scene()
        scene_path = project_service.resolve_path(last_scene).as_posix() if last_scene else ""
        if scene_path and os.path.exists(scene_path):
            return scene_path
        candidates = sorted(levels_root.rglob("*.json"))
        return candidates[0].as_posix() if candidates else ""

    def open_project(self, path: str) -> bool:
        project_service = self._get_project_service()
        scene_manager = self._get_scene_manager()
        editor_layout = self._get_editor_layout()
        if project_service is None or scene_manager is None:
            return False
        try:
            manifest = project_service.open_project(path)
        except Exception as exc:
            log_err(f"Open Project failed: {exc}")
            return False

        self._history_manager.clear()
        self.reset_project_bound_state()
        scene_manager.reset_workspace()
        self.set_project_service(project_service)
        if not self.restore_workspace_from_project_state():
            scene_path = self.pick_initial_scene_path()
            if scene_path and self._load_scene_by_path(scene_path):
                pass
            else:
                self._set_world(scene_manager.create_new_scene(manifest.name))
                self._set_current_scene_path("")
                self._set_project_loaded(True)
                self._sync_scene_workspace_ui(True)
        if scene_manager.current_scene is None:
            self._set_world(scene_manager.create_new_scene(manifest.name))
            self._set_project_loaded(True)
            self._sync_scene_workspace_ui(True)

        if editor_layout is not None:
            editor_layout.active_tab = "SCENE"
            if editor_layout.project_panel is not None:
                editor_layout.project_panel.set_project_service(project_service)
            self.refresh_launcher_projects()
            editor_layout.show_project_launcher = False
        log_info(f"Proyecto activo: {manifest.name}")
        return True

    def handle_project_launcher_requests(self) -> bool:
        editor_layout = self._get_editor_layout()
        project_service = self._get_project_service()
        if editor_layout is None:
            return False

        if editor_layout.request_browse_project:
            editor_layout.request_browse_project = False
            try:
                import tkinter
                from tkinter import filedialog
            except ImportError:
                log_err("Diálogo de archivo no disponible (tkinter no instalado).")
                editor_layout.set_launcher_feedback("File dialog not available (tkinter missing)", is_error=True)
            else:
                try:
                    root = tkinter.Tk()
                    root.withdraw()
                    initial_dir = project_service.editor_root.as_posix() if project_service is not None else os.getcwd()
                    path = filedialog.askdirectory(initialdir=initial_dir, title="Add Existing Project")
                    root.destroy()
                    if path and project_service is not None:
                        project_service.register_project(path)
                        self.refresh_launcher_projects()
                        editor_layout.set_launcher_feedback("Project added to launcher")
                except Exception as exc:
                    editor_layout.set_launcher_feedback(f"Add project failed: {exc}", is_error=True)
                    log_err(f"Open Project browse failed: {exc}")

        if editor_layout.request_exit_launcher:
            editor_layout.request_exit_launcher = False
            self._set_running(False)
            return True

        if editor_layout.request_create_project:
            editor_layout.request_create_project = False
            try:
                project_name = editor_layout.launcher_create_name.strip()
                if not project_name:
                    raise ValueError("Project name is required")
                if project_service is None:
                    raise RuntimeError("Project service not ready")
                project_root = project_service.build_internal_project_path(project_name)
                project_service.create_project(project_root, name=project_name)
                self.refresh_launcher_projects()
                editor_layout.show_create_project_modal = False
                editor_layout.launcher_create_name_focused = False
                editor_layout.set_launcher_feedback("Project created")
                editor_layout.pending_project_path = project_root.as_posix()
            except Exception as exc:
                editor_layout.set_launcher_feedback(f"Create project failed: {exc}", is_error=True)
                log_err(f"Create Project failed: {exc}")

        if editor_layout.request_remove_project_path:
            path = editor_layout.request_remove_project_path
            editor_layout.request_remove_project_path = ""
            if project_service is not None:
                project_service.remove_registered_project(path)
                self.refresh_launcher_projects()
                editor_layout.set_launcher_feedback("Project removed from launcher")
        return False

    def handle_project_switch_requests(self) -> None:
        editor_layout = self._get_editor_layout()
        scene_manager = self._get_scene_manager()
        if editor_layout is None or scene_manager is None:
            return

        if editor_layout.pending_project_path and not editor_layout.show_project_dirty_modal:
            target_project = editor_layout.pending_project_path
            if self._is_project_loaded() and scene_manager.has_unsaved_scenes:
                editor_layout.dirty_modal_context = "project_switch"
                editor_layout.show_project_dirty_modal = True
            else:
                editor_layout.pending_project_path = ""
                self.open_project(target_project)

        if editor_layout.project_switch_decision and editor_layout.dirty_modal_context == "project_switch":
            decision = editor_layout.project_switch_decision
            editor_layout.project_switch_decision = ""
            editor_layout.dirty_modal_context = ""
            target_project = editor_layout.pending_project_path
            if decision == "save":
                if self._save_all_dirty_scenes() and target_project:
                    editor_layout.pending_project_path = ""
                    self.open_project(target_project)
            elif decision == "discard":
                scene_manager.clear_all_dirty()
                if target_project:
                    editor_layout.pending_project_path = ""
                    self.open_project(target_project)
            else:
                editor_layout.pending_project_path = ""

    def handle_project_ui_requests(self) -> None:
        self.handle_project_launcher_requests()
        self.handle_project_switch_requests()
