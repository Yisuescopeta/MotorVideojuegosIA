from __future__ import annotations

import os
from typing import Any, Callable, Optional

from engine.core.engine_state import EngineState


class SceneWorkflowController:
    """Owns scene save/load/autosave and scene tab workflow."""

    def __init__(
        self,
        *,
        get_scene_manager: Callable[[], Any],
        get_project_service: Callable[[], Any],
        get_editor_layout: Callable[[], Any],
        get_state: Callable[[], EngineState],
        stop_runtime: Callable[[], None],
        capture_active_scene_view_state: Callable[[], None],
        sync_scene_workspace_ui: Callable[[bool], None],
        refresh_project_scene_entries: Callable[[], None],
        clear_rules_and_events: Callable[[], None],
        set_world: Callable[[Any], None],
        set_project_loaded: Callable[[bool], None],
        get_scene_flow: Callable[[], dict[str, str]],
        play_runtime: Callable[[], None],
        get_level_loader: Callable[[], Any],
    ) -> None:
        self._get_scene_manager = get_scene_manager
        self._get_project_service = get_project_service
        self._get_editor_layout = get_editor_layout
        self._get_state = get_state
        self._stop_runtime = stop_runtime
        self._capture_active_scene_view_state = capture_active_scene_view_state
        self._sync_scene_workspace_ui = sync_scene_workspace_ui
        self._refresh_project_scene_entries = refresh_project_scene_entries
        self._clear_rules_and_events = clear_rules_and_events
        self._set_world = set_world
        self._set_project_loaded = set_project_loaded
        self._get_scene_flow = get_scene_flow
        self._play_runtime = play_runtime
        self._get_level_loader = get_level_loader

    def sync_current_scene_path(self) -> str:
        scene_manager = self._get_scene_manager()
        if scene_manager is None or scene_manager.current_scene is None:
            return ""
        source_path = scene_manager.current_scene.source_path
        return str(source_path or "")

    def prompt_scene_save_path(self, scene_name: str) -> str:
        try:
            import tkinter
            from tkinter import filedialog

            root = tkinter.Tk()
            root.withdraw()
            project_service = self._get_project_service()
            suggested_name = f"{scene_name.strip() or 'scene'}.json".replace("/", "_").replace("\\", "_")
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Scene Files", "*.json"), ("All Files", "*.*")],
                initialfile=suggested_name,
                initialdir=project_service.get_project_path("levels").as_posix() if project_service is not None else os.getcwd(),
                title="Save Scene As",
            )
            root.destroy()
            return str(path or "")
        except Exception as exc:
            print(f"[ERROR] Save Dialog failed: {exc}")
            return ""

    def save_scene_entry(self, key: Optional[str] = None, prompt_if_needed: bool = True) -> bool:
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
            return False
        entry = scene_manager._resolve_entry(key)  # type: ignore[attr-defined]
        if entry is None:
            return False
        path = entry.source_path
        if not path and prompt_if_needed:
            path = self.prompt_scene_save_path(entry.scene.name)
        if not path:
            return False
        if entry.key == scene_manager.active_scene_key:
            self._capture_active_scene_view_state()
        success = scene_manager.save_scene_to_file(path, key=entry.key)
        if success:
            self._sync_scene_workspace_ui(False)
            print(f"[INFO] Guardado completado: {path}")
        return success

    def save_all_dirty_scenes(self) -> bool:
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
            return True
        dirty_entries = [scene["key"] for scene in scene_manager.list_open_scenes() if scene.get("dirty")]
        for key in dirty_entries:
            if not self.save_scene_entry(key, prompt_if_needed=True):
                return False
        return True

    def autosave_dirty_scenes(self) -> None:
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
            return
        dirty_entries = [scene for scene in scene_manager.list_open_scenes() if scene.get("dirty")]
        for scene in dirty_entries:
            path = str(scene.get("path", "") or "")
            key = str(scene.get("key", "") or "")
            if not path or not key:
                continue
            if key == scene_manager.active_scene_key:
                self._capture_active_scene_view_state()
            if scene_manager.save_scene_to_file(path, key=key):
                self._sync_scene_workspace_ui(False)

    def create_scene(self, scene_name: str) -> bool:
        scene_manager = self._get_scene_manager()
        project_service = self._get_project_service()
        editor_layout = self._get_editor_layout()
        if scene_manager is None or project_service is None or not project_service.has_project:
            return False
        normalized_name = str(scene_name or "").strip()
        if not normalized_name:
            return False
        if self._get_state() in (EngineState.PLAY, EngineState.PAUSED):
            self._stop_runtime()
        self._capture_active_scene_view_state()
        target_path = project_service.build_scene_file_path(normalized_name).as_posix()
        self._set_world(scene_manager.create_new_scene(normalized_name, activate=True))
        if not scene_manager.save_scene_to_file(target_path):
            return False
        self._set_project_loaded(True)
        self._sync_scene_workspace_ui(True)
        self._refresh_project_scene_entries()
        if editor_layout is not None:
            editor_layout.active_tab = "SCENE"
        return True

    def activate_scene_workspace_tab(self, key_or_path: str) -> bool:
        scene_manager = self._get_scene_manager()
        editor_layout = self._get_editor_layout()
        if scene_manager is None:
            return False
        if self._get_state() in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
            self._stop_runtime()
        self._capture_active_scene_view_state()
        world = scene_manager.activate_scene(key_or_path)
        if world is None:
            return False
        self._clear_rules_and_events()
        self._sync_scene_workspace_ui(True)
        if editor_layout is not None:
            editor_layout.active_tab = "SCENE"
        return True

    def close_scene_workspace_tab(self, key_or_path: str, discard_changes: bool = False) -> bool:
        scene_manager = self._get_scene_manager()
        if scene_manager is None:
            return False
        entry = scene_manager._resolve_entry(key_or_path)  # type: ignore[attr-defined]
        if entry is None:
            return False
        if entry.key == scene_manager.active_scene_key:
            self._capture_active_scene_view_state()
            if self._get_state() in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
                self._stop_runtime()
        if not scene_manager.close_scene(entry.key, discard_changes=discard_changes):
            return False
        self._sync_scene_workspace_ui(True)
        return True

    def load_scene_by_path(self, path: str) -> bool:
        scene_manager = self._get_scene_manager()
        project_service = self._get_project_service()
        editor_layout = self._get_editor_layout()
        if scene_manager is None or project_service is None or not project_service.has_project:
            return False
        if self._get_state() in (EngineState.PLAY, EngineState.PAUSED):
            self._stop_runtime()

        resolved_path = project_service.resolve_path(path).as_posix()
        self._capture_active_scene_view_state()
        world = scene_manager.load_scene_from_file(resolved_path, activate=True)
        if world is None:
            return False

        self._set_world(world)
        self._clear_rules_and_events()
        self._set_project_loaded(True)
        self._sync_scene_workspace_ui(True)
        if editor_layout is not None:
            editor_layout.active_tab = "SCENE"
        return True

    def save_current_scene(self) -> None:
        if self._get_scene_manager() is None:
            print("[ERROR] No hay SceneManager activo, no se puede guardar.")
            return
        if not self.save_scene_entry(prompt_if_needed=True):
            print("[ERROR] Fallo al guardar.")

    def reload_scene(self) -> None:
        print("[INFO] Recargando escena...")
        self._clear_rules_and_events()
        scene_manager = self._get_scene_manager()
        if scene_manager is not None:
            self._set_world(scene_manager.reload_scene())
            return
        level_loader = self._get_level_loader()
        current_world = getattr(level_loader, "_world", None) if level_loader is not None else None
        if level_loader is not None and current_world is not None:
            level_loader.reload(current_world)

    def load_scene_flow_target(self, key: str) -> bool:
        scene_flow = self._get_scene_flow()
        target = str(scene_flow.get(key, "")).strip()
        if not target:
            return False
        return self.load_scene_by_path(target)

    def load_scene_flow_target_from_script(self, key: str) -> bool:
        was_running = self._get_state() in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING)
        success = self.load_scene_flow_target(key)
        if success and was_running and self._get_state() == EngineState.EDIT:
            self._play_runtime()
        return success

    def handle_scene_tab_requests(self) -> None:
        scene_manager = self._get_scene_manager()
        editor_layout = self._get_editor_layout()
        if scene_manager is None or editor_layout is None:
            return

        if editor_layout.request_activate_scene_key:
            target_key = editor_layout.request_activate_scene_key
            editor_layout.request_activate_scene_key = ""
            self.activate_scene_workspace_tab(target_key)

        if editor_layout.request_close_scene_key:
            target_key = editor_layout.request_close_scene_key
            editor_layout.request_close_scene_key = ""
            entry = scene_manager._resolve_entry(target_key)  # type: ignore[attr-defined]
            if entry is not None:
                if entry.dirty:
                    editor_layout.pending_scene_close_key = entry.key
                    editor_layout.dirty_modal_context = "close_scene"
                    editor_layout.show_project_dirty_modal = True
                else:
                    self.close_scene_workspace_tab(entry.key, discard_changes=True)

    def handle_scene_ui_requests(self) -> None:
        scene_manager = self._get_scene_manager()
        editor_layout = self._get_editor_layout()
        project_service = self._get_project_service()
        if scene_manager is None or editor_layout is None:
            return

        if editor_layout.project_switch_decision and editor_layout.dirty_modal_context == "close_scene":
            decision = editor_layout.project_switch_decision
            editor_layout.project_switch_decision = ""
            editor_layout.dirty_modal_context = ""
            target_scene_close_key = editor_layout.pending_scene_close_key
            editor_layout.pending_scene_close_key = ""
            if decision == "save":
                if self.save_scene_entry(target_scene_close_key, prompt_if_needed=True):
                    self.close_scene_workspace_tab(target_scene_close_key, discard_changes=True)
            elif decision == "discard":
                self.close_scene_workspace_tab(target_scene_close_key, discard_changes=True)

        if editor_layout.request_new_scene:
            editor_layout.request_new_scene = False
            editor_layout.active_tab = "SCENE"
            editor_layout.show_create_scene_modal = True
            editor_layout.scene_create_name = "New Scene"
            editor_layout.scene_create_name_focused = True

        if editor_layout.request_create_scene:
            editor_layout.request_create_scene = False
            scene_name = editor_layout.scene_create_name.strip()
            if self.create_scene(scene_name):
                editor_layout.show_create_scene_modal = False
                editor_layout.scene_create_name_focused = False
                print(f"[GUI] Scene created: {scene_name}")

        if editor_layout.request_save_scene:
            editor_layout.request_save_scene = False
            self.save_current_scene()

        if editor_layout.request_load_scene:
            editor_layout.request_load_scene = False
            self._refresh_project_scene_entries()
            editor_layout.pending_scene_open_path = ""
            editor_layout.show_scene_browser_modal = True

        if editor_layout.pending_scene_open_path:
            target_scene_path = editor_layout.pending_scene_open_path
            editor_layout.pending_scene_open_path = ""
            self.load_scene_by_path(target_scene_path)

        if editor_layout.request_browse_scene_file:
            editor_layout.request_browse_scene_file = False
            try:
                import tkinter
                from tkinter import filedialog

                root = tkinter.Tk()
                root.withdraw()
                path = filedialog.askopenfilename(
                    filetypes=[("Scene Files", "*.json"), ("All Files", "*.*")],
                    initialdir=project_service.get_project_path("levels").as_posix() if project_service is not None else os.getcwd(),
                    title="Add Scene",
                )
                root.destroy()
                if path:
                    self.load_scene_by_path(path)
            except Exception as exc:
                print(f"[ERROR] Load Dialog failed: {exc}")
