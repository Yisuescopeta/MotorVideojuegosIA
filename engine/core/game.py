"""
engine/core/game.py - Clase principal del juego con gestión de escenas

PROPÓSITO:
    Gestiona ventana, game loop, sistemas, estados y escenas.

ESTADOS:
    - EDIT: Modo edición (usa World desde Scene)
    - PLAY: Modo juego (usa RuntimeWorld - copia)
    - PAUSED: Modo pausado

CONTROLES:
    - ESPACIO: Play (EDIT → PLAY, crea RuntimeWorld)
    - P: Pause/Resume
    - ESC: Stop (→ EDIT, restaura World)
    - R: Recargar escena
    - TAB: Inspector
"""

from typing import TYPE_CHECKING, Any, Optional
import pyray as rl
import os
import random
import time
from pathlib import Path

from engine.core.time_manager import TimeManager
from engine.core.engine_state import EngineState
from engine.core.hot_reload import HotReloadManager
from engine.editor.undo_redo import UndoRedoManager
from engine.project.project_service import ProjectService
from engine.config import EDIT_ANIMATION_SPEED, TIMELINE_CAPACITY, SCRIPTS_DIRECTORY
from engine.editor.console_panel import log_info, log_err

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.components.camera2d import Camera2D
    from engine.systems.render_system import RenderSystem
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.animation_system import AnimationSystem
    from engine.systems.audio_system import AudioSystem
    from engine.systems.input_system import InputSystem
    from engine.systems.player_controller_system import PlayerControllerSystem
    from engine.systems.character_controller_system import CharacterControllerSystem
    from engine.systems.script_behaviour_system import ScriptBehaviourSystem
    from engine.inspector.inspector_system import InspectorSystem
    from engine.levels.level_loader import LevelLoader
    from engine.events.event_bus import EventBus
    from engine.events.rule_system import RuleSystem
    from engine.scenes.scene_manager import SceneManager
    from engine.systems.selection_system import SelectionSystem
    from engine.systems.ui_render_system import UIRenderSystem
    from engine.systems.ui_system import UISystem
    from cli.script_executor import ScriptExecutor

from engine.debug.timeline import Timeline
from engine.components.canvas import Canvas
from engine.components.uibutton import UIButton
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.editor.animator_panel import AnimatorPanel
from engine.editor.hierarchy_panel import HierarchyPanel
from engine.editor.gizmo_system import GizmoSystem
from engine.editor.editor_layout import EditorLayout
from engine.editor.editor_tools import EditorTool, PivotMode, TransformSpace
from engine.editor.assistant_panel import AssistantPanel
from engine.editor.sprite_editor_modal import SpriteEditorModal
from engine.editor.raygui_theme import apply_unity_dark_theme
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend


class Game:
    """Clase principal del motor con gestión de estados y escenas."""
    
    EDIT_ANIMATION_SPEED: float = EDIT_ANIMATION_SPEED
    
    def __init__(
        self,
        title: str = "Motor 2D",
        width: int = 800,
        height: int = 600,
        target_fps: int = 60
    ) -> None:
        self.title = title
        self.width = width
        self.height = height
        self.target_fps = target_fps
        
        self.running: bool = False
        self.time: TimeManager = TimeManager()
        
        # Estado del motor
        self._state: EngineState = EngineState.EDIT
        
        # World activo (cambia según estado)
        self._world: Optional["World"] = None
        
        # Sistemas
        self._render_system: Optional["RenderSystem"] = None
        self._physics_system: Optional["PhysicsSystem"] = None
        self._collision_system: Optional["CollisionSystem"] = None
        self._physics_backends: dict[str, Any] = {}
        self._physics_backend_name: str = "legacy_aabb"
        self._animation_system: Optional["AnimationSystem"] = None
        self._audio_system: Optional["AudioSystem"] = None
        self._input_system: Optional["InputSystem"] = None
        self._player_controller_system: Optional["PlayerControllerSystem"] = None
        self._character_controller_system: Optional["CharacterControllerSystem"] = None
        self._script_behaviour_system: Optional["ScriptBehaviourSystem"] = None
        self._inspector_system: Optional["InspectorSystem"] = None
        self._level_loader: Optional["LevelLoader"] = None
        self._event_bus: Optional["EventBus"] = None
        self._event_bus: Optional["EventBus"] = None
        self._rule_system: Optional["RuleSystem"] = None
        self._selection_system: Optional["SelectionSystem"] = None
        self._ui_system: Optional["UISystem"] = None
        self._ui_render_system: Optional["UIRenderSystem"] = None
        
        self.script_executor: Optional["ScriptExecutor"] = None
        
        # Debug / Timeline
        self.timeline: "Timeline" = Timeline(capacity=TIMELINE_CAPACITY)
        
        # Editor Panels
        self.hierarchy_panel: Optional["HierarchyPanel"] = HierarchyPanel()
        self.animator_panel: Optional["AnimatorPanel"] = AnimatorPanel()
        self.sprite_editor_modal: Optional["SpriteEditorModal"] = SpriteEditorModal()
        self.gizmo_system: Optional["GizmoSystem"] = GizmoSystem()
        self.editor_layout: Optional["EditorLayout"] = None
        self.assistant_panel: Optional[AssistantPanel] = AssistantPanel()
        self.assistant_api: Any = None
        
        # Gestión de escenas
             
        # Gestión de escenas
        # Gestión de escenas
        self._scene_manager: Optional["SceneManager"] = None
        
        # Estado de Persistencia
        self.current_scene_path: str = ""
        self._project_loaded: bool = False
        
        # Hot-Reload
        self.hot_reload_manager: HotReloadManager = HotReloadManager(SCRIPTS_DIRECTORY)
        self.hot_reload_manager.scan_directory()

        self._project_service: Optional[ProjectService] = None
        self._history_manager: UndoRedoManager = UndoRedoManager()
        
        self.autosave_timer: float = 0.0
        self.show_performance_overlay: bool = False
        self._perf_stats: dict[str, float] = {
            "frame": 0.0,
            "render": 0.0,
            "inspector": 0.0,
            "hierarchy": 0.0,
            "ui": 0.0,
            "scripts": 0.0,
            "selection_gizmo": 0.0,
        }
        self._perf_counters: dict[str, int] = {
            "entities": 0,
            "render_entities": 0,
            "canvases": 0,
            "buttons": 0,
            "scripts": 0,
        }
        self.debug_draw_colliders: bool = False
        self.debug_draw_labels: bool = False
        self.random_seed: int | None = None
    
    # === PROPIEDADES ===
    
    @property
    def state(self) -> EngineState:
        return self._state

    def set_seed(self, seed: int | None) -> None:
        self.random_seed = None if seed is None else int(seed)
        if self.random_seed is not None:
            random.seed(self.random_seed)
    
    @property
    def is_edit_mode(self) -> bool:
        return self._state.is_edit()
    
    @property
    def is_play_mode(self) -> bool:
        return self._state.is_play()
    
    @property
    def is_paused(self) -> bool:
        return self._state.is_paused()
    
    @property
    def world(self) -> Optional["World"]:
        """World activo según el estado."""
        if self._scene_manager is not None:
            return self._scene_manager.active_world
        return self._world

    @property
    def audio_system(self) -> Optional["AudioSystem"]:
        return self._audio_system

    @property
    def has_project_loaded(self) -> bool:
        return self._project_loaded
    
    # === MÉTODOS DE CONTROL DE ESTADO ===
    
    def play(self) -> None:
        """Inicia el juego (EDIT -> PLAY)."""
        if self._state != EngineState.EDIT:
            return
        
        print("[INFO] Estado: EDIT -> PLAY")
        
        # Crear RuntimeWorld desde Scene
        if self._scene_manager is not None:
            runtime_world = self._scene_manager.enter_play()
            if runtime_world is not None:
                self._world = runtime_world
                
                # Reconfigurar RuleSystem con nuevo World
                if self._rule_system is not None:
                    self._rule_system.set_world(runtime_world)
                    # Recargar reglas desde Scene
                    scene = self._scene_manager.current_scene
                    if scene is not None:
                        self._rule_system.load_rules(scene.rules_data)
                if self._script_behaviour_system is not None:
                    self._script_behaviour_system.on_play(runtime_world)
        
        self._state = EngineState.PLAY
        
        if self._event_bus is not None:
            self._event_bus.emit("on_play", {})
    
    def pause(self) -> None:
        """Pausa/Resume el juego (PLAY <-> PAUSED)."""
        if self._state == EngineState.PLAY:
            print("[INFO] Estado: PLAY -> PAUSED")
            self._state = EngineState.PAUSED
        elif self._state == EngineState.PAUSED:
            print("[INFO] Estado: PAUSED -> PLAY")
            self._state = EngineState.PLAY
    
    def stop(self) -> None:
        """Detiene el juego y vuelve a edición."""
        if self._state not in (EngineState.PLAY, EngineState.PAUSED):
            return
        
        print("[INFO] Estado: -> EDIT (restaurando escena)")
        
        # Limpiar reglas y eventos
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        if self._script_behaviour_system is not None and self.world is not None:
            self._script_behaviour_system.on_stop(self.world)
        
        # Restaurar World desde Scene
        if self._scene_manager is not None:
            edit_world = self._scene_manager.exit_play()
            if edit_world is not None:
                self._world = edit_world
        
        self._state = EngineState.EDIT
    
    # === SETTERS ===
    
    def set_world(self, world: "World") -> None:
        self._world = world
    
    def set_render_system(self, system: "RenderSystem") -> None:
        self._render_system = system
        if self._project_service is not None:
            self._render_system.set_project_service(self._project_service)
        if hasattr(self._render_system, "set_debug_options"):
            self._render_system.set_debug_options(
                draw_colliders=self.debug_draw_colliders,
                draw_labels=self.debug_draw_labels,
            )
    
    def set_physics_system(self, system: "PhysicsSystem") -> None:
        self._physics_system = system
        self._refresh_default_physics_backend()
    
    def set_collision_system(self, system: "CollisionSystem") -> None:
        self._collision_system = system
        self._refresh_default_physics_backend()
    
    def set_animation_system(self, system: "AnimationSystem") -> None:
        self._animation_system = system

    def set_audio_system(self, system: "AudioSystem") -> None:
        self._audio_system = system
        if self._project_service is not None and hasattr(self._audio_system, "set_project_service"):
            self._audio_system.set_project_service(self._project_service)

    def set_input_system(self, system: "InputSystem") -> None:
        self._input_system = system

    def set_player_controller_system(self, system: "PlayerControllerSystem") -> None:
        self._player_controller_system = system

    def set_character_controller_system(self, system: "CharacterControllerSystem") -> None:
        self._character_controller_system = system

    def set_script_behaviour_system(self, system: "ScriptBehaviourSystem") -> None:
        self._script_behaviour_system = system
        self._script_behaviour_system.set_hot_reload_manager(self.hot_reload_manager)
        self._script_behaviour_system.set_scene_flow_loader(self._load_scene_flow_target_from_script)
        if self._scene_manager is not None:
            self._script_behaviour_system.set_scene_manager(self._scene_manager)
        if self._project_service is not None and hasattr(self._script_behaviour_system, "set_project_service"):
            self._script_behaviour_system.set_project_service(self._project_service)
    
    def set_inspector_system(self, system: "InspectorSystem") -> None:
        self._inspector_system = system
        # Conectar scene_manager si ya existe
        if self._scene_manager is not None:
            self._inspector_system.set_scene_manager(self._scene_manager)
    
    def set_level_loader(self, loader: "LevelLoader") -> None:
        self._level_loader = loader
    
    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus
        for backend in self._physics_backends.values():
            if hasattr(backend, "set_event_bus"):
                backend.set_event_bus(event_bus)
        if self._ui_system is not None:
            self._ui_system.set_event_bus(event_bus)

    def set_physics_backend(self, backend: Any, backend_name: str = "legacy_aabb") -> None:
        normalized_name = str(backend_name or "legacy_aabb")
        self._physics_backends[normalized_name] = backend
        if hasattr(backend, "set_event_bus"):
            backend.set_event_bus(self._event_bus)
    
    def set_rule_system(self, rule_system: "RuleSystem") -> None:
        self._rule_system = rule_system
    
    def set_scene_manager(self, manager: "SceneManager") -> None:
        self._scene_manager = manager
        self._scene_manager.set_history_manager(self._history_manager)
        # Conectar inspector al scene_manager para edición
        if self._inspector_system is not None:
            self._inspector_system.set_scene_manager(manager)
        if self.animator_panel is not None:
            self.animator_panel.set_scene_manager(manager)
        if self.sprite_editor_modal is not None:
            self.sprite_editor_modal.set_history_manager(self._history_manager)
        if self._script_behaviour_system is not None:
            self._script_behaviour_system.set_scene_manager(manager)
        if self.hierarchy_panel is not None:
            self.hierarchy_panel.set_scene_manager(manager)
        if self.editor_layout is not None:
            self.editor_layout.set_scene_tabs(manager.list_open_scenes(), manager.active_scene_key)
            
    def set_selection_system(self, system: "SelectionSystem") -> None:
        self._selection_system = system

    def set_ui_system(self, system: "UISystem") -> None:
        self._ui_system = system
        self._ui_system.set_scene_loader(self.load_scene_by_path)
        self._ui_system.set_scene_flow_loader(self._load_scene_flow_target_from_script)
        if self._event_bus is not None:
            self._ui_system.set_event_bus(self._event_bus)

    def set_ui_render_system(self, system: "UIRenderSystem") -> None:
        self._ui_render_system = system
        
    def set_script_executor(self, executor: "ScriptExecutor") -> None:
        """Asigna un ejecutor de scripts para automatización visual."""
        self.script_executor = executor

    def set_project_service(self, service: ProjectService) -> None:
        self._project_service = service
        if self.editor_layout is not None:
            self.editor_layout.set_recent_projects(service.list_launcher_projects())
            self.editor_layout.set_project_scene_entries(service.list_project_scenes() if service.has_project else [])

        if not service.has_project:
            self._project_loaded = False
            self.current_scene_path = ""
            return

        if self._render_system is not None:
            self._render_system.set_project_service(service)
        if self._audio_system is not None and hasattr(self._audio_system, "set_project_service"):
            self._audio_system.set_project_service(service)
        if self.animator_panel is not None:
            self.animator_panel.set_project_service(service)
        if self.sprite_editor_modal is not None:
            self.sprite_editor_modal.set_project_service(service)
            self.sprite_editor_modal.set_history_manager(self._history_manager)
        self.hot_reload_manager.scripts_dir = service.get_project_path("scripts").as_posix()
        self.hot_reload_manager.scan_directory()
        if self._script_behaviour_system is not None:
            self._script_behaviour_system.set_hot_reload_manager(self.hot_reload_manager)
            if hasattr(self._script_behaviour_system, "set_project_service"):
                self._script_behaviour_system.set_project_service(service)
        if self.editor_layout is not None and self.editor_layout.project_panel is not None:
            self.editor_layout.project_panel.set_project_service(service)
            self.editor_layout.set_recent_projects(service.list_launcher_projects())
            if self._scene_manager is not None:
                self.editor_layout.set_scene_tabs(self._scene_manager.list_open_scenes(), self._scene_manager.active_scene_key)
            self.editor_layout.apply_editor_preferences(service.load_editor_state().get("preferences", {}))
        self._project_loaded = True

    def _refresh_launcher_projects(self) -> None:
        if self._project_service is None or self.editor_layout is None:
            return
        self.editor_layout.set_recent_projects(self._project_service.list_launcher_projects())

    def _refresh_project_scene_entries(self) -> None:
        if self._project_service is None or self.editor_layout is None:
            return
        self.editor_layout.set_project_scene_entries(
            self._project_service.list_project_scenes() if self._project_service.has_project else []
        )

    def _persist_editor_preferences(self) -> None:
        if self._project_service is None or self.editor_layout is None or not self._project_service.has_project:
            return
        if not self.editor_layout.consume_editor_preferences_dirty():
            return
        state = self._project_service.load_editor_state()
        preferences = state.setdefault("preferences", {})
        preferences.update(self.editor_layout.export_editor_preferences())
        self._project_service.save_editor_state(state)

    def _commit_gizmo_drag(self, drag) -> None:
        if self._scene_manager is None:
            return
        active_key = self._scene_manager.active_scene_key
        if not active_key:
            return
        self._scene_manager.sync_from_edit_world(force=True)
        apply_state = self._scene_manager.apply_transform_state
        if getattr(drag, "component_name", "") == "RectTransform":
            apply_state = self._scene_manager.apply_rect_transform_state
        self._history_manager.push(
            label=drag.label,
            undo=lambda key=active_key, entity_name=drag.entity_name, before=drag.before_state, apply_state=apply_state: apply_state(entity_name, before, key_or_path=key, record_history=False),
            redo=lambda key=active_key, entity_name=drag.entity_name, after=drag.after_state, apply_state=apply_state: apply_state(entity_name, after, key_or_path=key, record_history=False),
        )

    def set_assistant_api(self, api: Any) -> None:
        self.assistant_api = api
        if self.assistant_panel is not None:
            self.assistant_panel.set_api(api)

    def _sync_assistant_panel_layout(self, force: bool = False) -> None:
        if self.editor_layout is None or self.assistant_panel is None:
            return
        desired_minimized = bool(getattr(self.assistant_panel, "is_minimized", False))
        if not force and getattr(self.editor_layout, "assistant_minimized", False) == desired_minimized:
            return
        self.editor_layout.set_assistant_minimized(desired_minimized)
        self.editor_layout.update_layout(rl.get_screen_width(), rl.get_screen_height())
        self.width = rl.get_screen_width()
        self.height = rl.get_screen_height()

    def _reset_project_bound_state(self) -> None:
        if self._state == EngineState.STEPPING:
            self._state = EngineState.PAUSED
        if self._state in (EngineState.PLAY, EngineState.PAUSED):
            self.stop()
        if self.animator_panel is not None:
            self.animator_panel.reset()
        if self.sprite_editor_modal is not None:
            self.sprite_editor_modal.close()
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        if self._render_system is not None and hasattr(self._render_system, "reset_project_resources"):
            self._render_system.reset_project_resources()
        self.timeline.clear()

    def _sync_current_scene_path(self) -> None:
        if self._scene_manager is None or self._scene_manager.current_scene is None:
            self.current_scene_path = ""
            return
        source_path = self._scene_manager.current_scene.source_path
        self.current_scene_path = str(source_path or "")

    def _capture_active_scene_view_state(self) -> None:
        if self._scene_manager is None or self.editor_layout is None:
            return
        active_key = self._scene_manager.active_scene_key
        if not active_key:
            return
        active_world = self._scene_manager.get_edit_world()
        selected_entity = active_world.selected_entity_name if active_world is not None else None
        self._scene_manager.set_scene_view_state(
            active_key,
            {
                "selected_entity": selected_entity,
                "camera_target": {
                    "x": float(self.editor_layout.editor_camera.target.x),
                    "y": float(self.editor_layout.editor_camera.target.y),
                },
                "camera_zoom": float(self.editor_layout.editor_camera.zoom),
            },
        )

    def _apply_active_scene_view_state(self) -> None:
        if self._scene_manager is None or self.editor_layout is None:
            return
        view_state = self._scene_manager.get_scene_view_state()
        camera_target = view_state.get("camera_target", {})
        if isinstance(camera_target, dict):
            self.editor_layout.editor_camera.target = rl.Vector2(
                float(camera_target.get("x", 0.0)),
                float(camera_target.get("y", 0.0)),
            )
        self.editor_layout.editor_camera.zoom = max(0.1, float(view_state.get("camera_zoom", 1.0) or 1.0))
        selected_entity = view_state.get("selected_entity")
        self._scene_manager.set_selected_entity(str(selected_entity) if selected_entity else None)

    def _persist_workspace_state(self) -> None:
        if self._project_service is None or self._scene_manager is None or not self._project_service.has_project:
            return
        state = self._project_service.load_editor_state()
        workspace_state = self._scene_manager.get_workspace_state()
        state["open_scenes"] = [
            self._project_service.to_relative_path(scene_ref) if str(scene_ref).endswith(".json") else str(scene_ref)
            for scene_ref in workspace_state.get("open_scenes", [])
        ]
        active_scene = str(workspace_state.get("active_scene", "") or "")
        state["active_scene"] = self._project_service.to_relative_path(active_scene) if active_scene.endswith(".json") else active_scene
        scene_view_states = {}
        for scene_ref, view_state in dict(workspace_state.get("scene_view_states", {})).items():
            normalized_ref = self._project_service.to_relative_path(scene_ref) if str(scene_ref).endswith(".json") else str(scene_ref)
            scene_view_states[normalized_ref] = dict(view_state)
        state["scene_view_states"] = scene_view_states
        state["last_scene"] = self._project_service.to_relative_path(self.current_scene_path) if self.current_scene_path else ""
        self._project_service.save_editor_state(state)

    def _sync_scene_workspace_ui(self, apply_view_state: bool = False) -> None:
        if self._scene_manager is None:
            return
        self._world = self._scene_manager.active_world
        self._sync_current_scene_path()
        if self.editor_layout is not None:
            self.editor_layout.set_scene_tabs(self._scene_manager.list_open_scenes(), self._scene_manager.active_scene_key)
        if apply_view_state:
            self._apply_active_scene_view_state()
        self._persist_workspace_state()

    def _prompt_scene_save_path(self, scene_name: str) -> str:
        try:
            import tkinter
            from tkinter import filedialog

            root = tkinter.Tk()
            root.withdraw()
            suggested_name = f"{scene_name.strip() or 'scene'}.json".replace("/", "_").replace("\\", "_")
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Scene Files", "*.json"), ("All Files", "*.*")],
                initialfile=suggested_name,
                initialdir=self._project_service.get_project_path("levels").as_posix() if self._project_service is not None else os.getcwd(),
                title="Save Scene As",
            )
            root.destroy()
            return str(path or "")
        except Exception as exc:
            print(f"[ERROR] Save Dialog failed: {exc}")
            return ""

    def _save_scene_entry(self, key: Optional[str] = None, prompt_if_needed: bool = True) -> bool:
        if self._scene_manager is None:
            return False
        entry = self._scene_manager._resolve_entry(key)  # type: ignore[attr-defined]
        if entry is None:
            return False
        path = entry.source_path
        if not path and prompt_if_needed:
            path = self._prompt_scene_save_path(entry.scene.name)
        if not path:
            return False
        success = self._scene_manager.save_scene_to_file(path, key=entry.key)
        if success:
            self._sync_scene_workspace_ui(apply_view_state=True)
            print(f"[INFO] Guardado completado: {path}")
        return success

    def _save_all_dirty_scenes(self) -> bool:
        if self._scene_manager is None:
            return True
        dirty_entries = [scene["key"] for scene in self._scene_manager.list_open_scenes() if scene.get("dirty")]
        for key in dirty_entries:
            if not self._save_scene_entry(key, prompt_if_needed=True):
                return False
        return True

    def _autosave_dirty_scenes(self) -> None:
        if self._scene_manager is None:
            return
        dirty_entries = [scene for scene in self._scene_manager.list_open_scenes() if scene.get("dirty")]
        for scene in dirty_entries:
            path = str(scene.get("path", "") or "")
            key = str(scene.get("key", "") or "")
            if not path or not key:
                continue
            if self._scene_manager.save_scene_to_file(path, key=key):
                self._sync_scene_workspace_ui(apply_view_state=True)

    def create_scene(self, scene_name: str) -> bool:
        if self._scene_manager is None or self._project_service is None or not self._project_service.has_project:
            return False
        normalized_name = str(scene_name or "").strip()
        if not normalized_name:
            return False
        if self._state in (EngineState.PLAY, EngineState.PAUSED):
            self.stop()
        self._capture_active_scene_view_state()
        target_path = self._project_service.build_scene_file_path(normalized_name).as_posix()
        self._world = self._scene_manager.create_new_scene(normalized_name, activate=True)
        if not self._scene_manager.save_scene_to_file(target_path):
            return False
        self._project_loaded = True
        self._sync_scene_workspace_ui(apply_view_state=True)
        self._refresh_project_scene_entries()
        if self.editor_layout is not None:
            self.editor_layout.active_tab = "SCENE"
        return True

    def _restore_workspace_from_project_state(self) -> bool:
        if self._project_service is None or self._scene_manager is None or not self._project_service.has_project:
            return False
        state = self._project_service.load_editor_state()
        open_scenes = list(state.get("open_scenes", []))
        scene_view_states = dict(state.get("scene_view_states", {}))
        for scene_ref in open_scenes:
            resolved_path = self._project_service.resolve_path(scene_ref).as_posix()
            if not os.path.exists(resolved_path):
                continue
            world = self._scene_manager.load_scene_from_file(resolved_path, activate=False)
            if world is None:
                continue
            saved_state = scene_view_states.get(scene_ref) or scene_view_states.get(resolved_path)
            if isinstance(saved_state, dict):
                self._scene_manager.set_scene_view_state(resolved_path, saved_state)

        desired_active = str(state.get("active_scene", "") or "").strip()
        if desired_active:
            desired_active = self._project_service.resolve_path(desired_active).as_posix()
        elif self._project_service.get_last_scene():
            desired_active = self._project_service.resolve_path(self._project_service.get_last_scene()).as_posix()

        if desired_active and os.path.exists(desired_active):
            self._scene_manager.load_scene_from_file(desired_active, activate=False)

        open_entries = self._scene_manager.list_open_scenes()
        if not open_entries:
            return False

        target_key = desired_active if desired_active else str(open_entries[0].get("key", ""))
        self._scene_manager.activate_scene(target_key)
        self._sync_scene_workspace_ui(apply_view_state=True)
        return True

    def _activate_scene_workspace_tab(self, key_or_path: str) -> bool:
        if self._scene_manager is None:
            return False
        if self._state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
            self.stop()
        self._capture_active_scene_view_state()
        world = self._scene_manager.activate_scene(key_or_path)
        if world is None:
            return False
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        self._sync_scene_workspace_ui(apply_view_state=True)
        if self.editor_layout is not None:
            self.editor_layout.active_tab = "SCENE"
        return True

    def _close_scene_workspace_tab(self, key_or_path: str, discard_changes: bool = False) -> bool:
        if self._scene_manager is None:
            return False
        entry = self._scene_manager._resolve_entry(key_or_path)  # type: ignore[attr-defined]
        if entry is None:
            return False
        if entry.key == self._scene_manager.active_scene_key:
            self._capture_active_scene_view_state()
            if self._state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
                self.stop()
        if not self._scene_manager.close_scene(entry.key, discard_changes=discard_changes):
            return False
        self._sync_scene_workspace_ui(apply_view_state=True)
        return True

    def _pick_initial_scene_path(self) -> str:
        if self._project_service is None or not self._project_service.has_project:
            return ""
        levels_root = self._project_service.get_project_path("levels")
        startup_scene = str(self._project_service.load_project_settings().get("startup_scene", "")).strip()
        if startup_scene:
            startup_path = self._project_service.resolve_path(startup_scene).as_posix()
            if os.path.exists(startup_path):
                return startup_path
        last_scene = self._project_service.get_last_scene()
        scene_path = self._project_service.resolve_path(last_scene).as_posix() if last_scene else ""
        if scene_path and os.path.exists(scene_path):
            return scene_path
        candidates = sorted(levels_root.rglob("*.json"))
        return candidates[0].as_posix() if candidates else ""

    def load_scene_by_path(self, path: str) -> bool:
        if self._scene_manager is None or self._project_service is None or not self._project_service.has_project:
            return False
        if self._state in (EngineState.PLAY, EngineState.PAUSED):
            self.stop()

        resolved_path = self._project_service.resolve_path(path).as_posix()
        self._capture_active_scene_view_state()
        world = self._scene_manager.load_scene_from_file(resolved_path, activate=True)
        if world is None:
            return False

        self._world = world
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        self._project_loaded = True
        self._sync_scene_workspace_ui(apply_view_state=True)
        if self.editor_layout is not None:
            self.editor_layout.active_tab = "SCENE"
        return True

    def get_scene_flow(self) -> dict:
        if self._scene_manager is None or self._scene_manager.current_scene is None:
            return {}
        metadata = self._scene_manager.current_scene.feature_metadata
        scene_flow = metadata.get("scene_flow", {})
        return dict(scene_flow) if isinstance(scene_flow, dict) else {}

    def load_scene_flow_target(self, key: str) -> bool:
        scene_flow = self.get_scene_flow()
        target = str(scene_flow.get(key, "")).strip()
        if not target:
            return False
        return self.load_scene_by_path(target)

    def _load_scene_flow_target_from_script(self, key: str) -> bool:
        """Carga una escena desde script y conserva PLAY cuando aplica."""
        was_running = self._state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING)
        success = self.load_scene_flow_target(key)
        if success and was_running and self._state == EngineState.EDIT:
            self.play()
        return success

    def open_project(self, path: str) -> bool:
        if self._project_service is None or self._scene_manager is None:
            return False
        try:
            manifest = self._project_service.open_project(path)
        except Exception as exc:
            log_err(f"Open Project failed: {exc}")
            return False

        self._history_manager.clear()
        self._reset_project_bound_state()
        self._scene_manager.reset_workspace()
        self.set_project_service(self._project_service)
        if not self._restore_workspace_from_project_state():
            scene_path = self._pick_initial_scene_path()
            if scene_path and self.load_scene_by_path(scene_path):
                pass
            else:
                self._world = self._scene_manager.create_new_scene(manifest.name)
                self.current_scene_path = ""
                self._project_loaded = True
                self._sync_scene_workspace_ui(apply_view_state=True)
        if self._scene_manager.current_scene is None:
            self._world = self._scene_manager.create_new_scene(manifest.name)
            self._project_loaded = True
            self._sync_scene_workspace_ui(apply_view_state=True)

        if self.editor_layout is not None:
            self.editor_layout.active_tab = "SCENE"
            self.editor_layout.project_panel.set_project_service(self._project_service)
            self._refresh_launcher_projects()
            self.editor_layout.show_project_launcher = False
        log_info(f"Proyecto activo: {manifest.name}")
        return True
    
    # === GAME LOOP ===
    
    def run(self) -> None:
        "Inicia el game loop."
        rl.init_window(self.width, self.height, self.title)
        rl.set_target_fps(self.target_fps)
        
        # Aplicar tema Raygui
        apply_unity_dark_theme()
        
        # Crear EditorLayout (necesita ventana Raylib inicializada)
        if self.editor_layout is None:
            self.editor_layout = EditorLayout(self.width, self.height)
            if self._project_service is not None:
                self._refresh_launcher_projects()
                if self._project_service.has_project:
                    self.editor_layout.project_panel.set_project_service(self._project_service)
                else:
                    self.editor_layout.show_project_launcher = True
            if self._scene_manager is not None:
                self.editor_layout.set_scene_tabs(self._scene_manager.list_open_scenes(), self._scene_manager.active_scene_key)
        self._sync_assistant_panel_layout(force=True)
        
        self.running = True
        print(f"[INFO] Motor iniciado en modo: {self._state}")
        
        while self.running and not rl.window_should_close():
            frame_start = time.perf_counter()
            self.time.update()
            dt = self.time.delta_time

            if self.editor_layout is not None and self.editor_layout.show_project_launcher and not self._project_loaded:
                if rl.is_window_resized():
                    self.editor_layout.update_layout(rl.get_screen_width(), rl.get_screen_height())
                    self.width = rl.get_screen_width()
                    self.height = rl.get_screen_height()
                self.editor_layout.update_input()
                self._process_ui_requests()
                rl.begin_drawing()
                try:
                    rl.clear_background(rl.DARKGRAY)
                    self.editor_layout.draw_project_launcher()
                finally:
                    rl.end_drawing()
                continue
            
            # World activo
            active_world = self.world
            
            self._process_input()
            
            # Script Update (Visual Automation)
            if self.script_executor:
                running = self.script_executor.update()
                if not running:
                    print("[INFO] Script finalizado.")

            # Sistemas de edición (Layout, Gizmos, Selection)
            # Permite interacción si está en EDIT O si está en PLAY pero viendo la escena
            enable_scene_interaction = self._state.is_edit() or (self.editor_layout and self.editor_layout.active_tab == "SCENE")
            
            # 1. Update Layout Input (Always, for toolbar/tabs)
            if self.editor_layout:
                if rl.is_window_resized():
                     self.editor_layout.update_layout(rl.get_screen_width(), rl.get_screen_height())
                     self.width = rl.get_screen_width()
                     self.height = rl.get_screen_height()

                self._sync_assistant_panel_layout()

                if self.sprite_editor_modal is None or not self.sprite_editor_modal.is_open:
                    self.editor_layout.update_input()
                    self._persist_editor_preferences()
                if self.animator_panel is not None and active_world is not None:
                    self.animator_panel.update(active_world, dt)
                if self.assistant_panel is not None:
                    self.assistant_panel.update(self.editor_layout.assistant_rect)
                
                # Procesar requests de UI
                if self.editor_layout.request_play:
                    self.editor_layout.request_play = False
                    if self._state == EngineState.EDIT:
                        self.play()
                        self.editor_layout.active_tab = "GAME"
                    else:
                        self.stop()
                        self.editor_layout.active_tab = "SCENE"
                
                if self.editor_layout.request_pause:
                    self.editor_layout.request_pause = False
                    if self._state in (EngineState.PLAY, EngineState.PAUSED):
                        self.pause()
                
                # --- SCENE UI REQUESTS ---
                self._process_ui_requests()

                if self.editor_layout.request_step:
                    self.editor_layout.request_step = False
                    if self._state in (EngineState.PLAY, EngineState.PAUSED):
                        self.step()
                
                # --- DRAG & DROP LOGIC ---
                if self._state.is_edit() and self.editor_layout.project_panel and self.editor_layout.project_panel.dragging_file:
                    if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                        if self.editor_layout.is_mouse_in_scene_view() and active_world is not None:
                            file_path = self.editor_layout.project_panel.dragging_file
                            drop_pos = self.editor_layout.get_scene_mouse_pos()
                            
                            filename = os.path.basename(file_path)
                            name, ext = os.path.splitext(filename)
                            
                            if ext.lower() == ".prefab":
                                # Instantiate Prefab
                                print(f"[DROP] Instantiating Prefab '{name}' from {file_path}")
                                from engine.assets.prefab import PrefabManager
                                prefab_data = PrefabManager.load_prefab_data(file_path)
                                if prefab_data and self._scene_manager is not None:
                                    unique_name = name
                                    count = 1
                                    while active_world.get_entity_by_name(unique_name):
                                        unique_name = f"{name}_{count}"
                                        count += 1
                                    if self._scene_manager.instantiate_prefab(
                                        unique_name,
                                        prefab_path=file_path,
                                        overrides={"": {"components": {"Transform": {"x": drop_pos.x, "y": drop_pos.y}}}},
                                        root_name=prefab_data.get("root_name", unique_name),
                                    ):
                                        self._scene_manager.set_selected_entity(unique_name)
                            else:
                                # Default: Create Sprite Entity
                                base_name = name
                                count = 1
                                while active_world.get_entity_by_name(name):
                                    name = f"{base_name}_{count}"
                                    count += 1
                                    
                                print(f"[DROP] Creating Sprite Entity '{name}' from {file_path}")
                                if self._scene_manager is not None:
                                    created = self._scene_manager.create_entity(
                                        name,
                                        {
                                            "Transform": {
                                                "enabled": True,
                                                "x": drop_pos.x,
                                                "y": drop_pos.y,
                                                "rotation": 0.0,
                                                "scale_x": 1.0,
                                                "scale_y": 1.0,
                                            },
                                            "Sprite": {
                                                "enabled": True,
                                                "texture_path": file_path,
                                                "width": 0,
                                                "height": 0,
                                                "origin_x": 0.5,
                                                "origin_y": 0.5,
                                                "flip_x": False,
                                                "flip_y": False,
                                                "tint": [255, 255, 255, 255],
                                            },
                                            "Collider": {
                                                "enabled": True,
                                                "width": 32,
                                                "height": 32,
                                                "offset_x": 0.0,
                                                "offset_y": 0.0,
                                                "is_trigger": False,
                                            },
                                        },
                                    )
                                    if created:
                                        active_world.selected_entity_name = name
                                else:
                                    new_ent = active_world.create_entity(name)
                                    from engine.components.transform import Transform
                                    from engine.components.sprite import Sprite
                                    from engine.components.collider import Collider
                                    new_ent.add_component(Transform(drop_pos.x, drop_pos.y))
                                    new_ent.add_component(Sprite(file_path)) 
                                    new_ent.add_component(Collider(32, 32)) 
                                    active_world.selected_entity_name = name

            # 2. Gizmos & Selection (Only if interaction enabled)
            selection_gizmo_start = time.perf_counter()
            if enable_scene_interaction:
                mouse_world = rl.Vector2(0, 0)
                mouse_ui = rl.Vector2(0, 0)
                mouse_in_scene = False
                scene_viewport_size = self._current_scene_viewport_size()
                if self.editor_layout:
                    mouse_world = self.editor_layout.get_scene_mouse_pos()
                    mouse_ui = self.editor_layout.get_scene_overlay_mouse_pos()
                    mouse_in_scene = self.editor_layout.is_mouse_in_scene_view()
                    # CRITICAL: Prevent scene interaction (selection/gizmo) if mouse is over Inspector
                    if self.editor_layout.is_mouse_in_inspector() or self.editor_layout.is_mouse_in_assistant_panel():
                        mouse_in_scene = False
                if self._ui_system is not None and active_world is not None:
                    self._ui_system.ensure_layout_cache(active_world, scene_viewport_size)

                # Gizmos
                if self.gizmo_system is not None and active_world is not None:
                    if self.gizmo_system.is_dragging or mouse_in_scene:
                        was_dragging = self.gizmo_system.is_dragging
                        active_tool = self.editor_layout.active_tool if self.editor_layout else EditorTool.MOVE
                        transform_space = self.editor_layout.transform_space if self.editor_layout else TransformSpace.WORLD
                        pivot_mode = self.editor_layout.pivot_mode if self.editor_layout else PivotMode.PIVOT
                        snap_settings = self.editor_layout.snap_settings if self.editor_layout else None
                        self.gizmo_system.update(
                            active_world,
                            mouse_world,
                            active_tool,
                            transform_space,
                            pivot_mode,
                            snap_settings,
                            ui_system=self._ui_system,
                            ui_mouse_pos=mouse_ui,
                            ui_viewport_size=scene_viewport_size,
                        )
                        if (was_dragging or self.gizmo_system.is_dragging) and self._scene_manager is not None:
                            self._scene_manager.mark_edit_world_dirty()
                        drag = self.gizmo_system.consume_completed_drag()
                        if drag is not None:
                            self._commit_gizmo_drag(drag)

                if self._selection_system is not None and active_world is not None:
                    gizmo_active = self.gizmo_system.is_hot() if self.gizmo_system else False
                    hand_tool_active = self.editor_layout is not None and self.editor_layout.active_tool == EditorTool.HAND
                    if not hand_tool_active and not gizmo_active and mouse_in_scene and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                        ui_hit = None
                        if self._ui_system is not None:
                            ui_hit = self._ui_system.find_topmost_entity_at_point(
                                active_world,
                                float(mouse_ui.x),
                                float(mouse_ui.y),
                                scene_viewport_size,
                            )
                        if ui_hit is not None:
                            if self._scene_manager is not None:
                                self._scene_manager.set_selected_entity(ui_hit.name)
                            else:
                                active_world.selected_entity_name = ui_hit.name
                        else:
                            self._selection_system.update(active_world, mouse_world)
            self._perf_stats["selection_gizmo"] = (time.perf_counter() - selection_gizmo_start) * 1000.0

            # Update Animation (Only in Play/Step mode)
            if self._state.allows_gameplay():
                try:
                    self._update_animation(active_world, dt)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"Animation error: {e}")
            
            # Actualización de gameplay (Física, Colisiones, Reglas)
            if self._state.allows_physics() or self._state.allows_gameplay():
                try:
                    self._update_gameplay(active_world, dt)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"Gameplay error: {e}")

            scripts_start = time.perf_counter()
            if self._state == EngineState.EDIT and active_world is not None and self._script_behaviour_system is not None:
                try:
                    ran_edit_scripts = self._script_behaviour_system.update(active_world, dt, is_edit_mode=True)
                    if ran_edit_scripts and self._scene_manager is not None:
                        self._scene_manager.mark_edit_world_dirty()
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"ScriptBehaviour error: {e}")
            self._perf_stats["scripts"] = (time.perf_counter() - scripts_start) * 1000.0

            ui_start = time.perf_counter()
            active_tab = self.editor_layout.active_tab if self.editor_layout is not None else "SCENE"
            if active_world is not None and active_tab in ("SCENE", "GAME"):
                try:
                    self._update_ui_overlay(active_world, self._current_viewport_size())
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"UI error: {e}")
            self._perf_stats["ui"] = (time.perf_counter() - ui_start) * 1000.0
            
            # Si estábamos en STEPPING, volvemos a PAUSED después de un frame
            if self._state == EngineState.EDIT:
                self._autosave_dirty_scenes()
            if self._state == EngineState.STEPPING:
                self._state = EngineState.PAUSED

            # Renderizar FRAME (Safe)
            try:
                render_start = time.perf_counter()
                self._render_frame(active_world)
                self._perf_stats["render"] = (time.perf_counter() - render_start) * 1000.0
            except Exception as e:
                from engine.editor.console_panel import log_err
                log_err(f"CRITICAL RENDER ERROR: {e}")
            self._perf_stats["frame"] = (time.perf_counter() - frame_start) * 1000.0
            self._update_perf_counters(active_world)
        
        self._cleanup()
    
    def _update_animation(self, world: Optional["World"], dt: float) -> None:
        if self._animation_system is None or world is None:
            return
        
        if self._state.allows_animation():
            self._animation_system.update(world, dt)
        elif self._state.allows_animation_preview():
            self._animation_system.update(world, dt * self.EDIT_ANIMATION_SPEED)

    def _update_ui_overlay(self, world: Optional["World"], viewport_size: tuple[float, float]) -> None:
        if self._ui_system is None or world is None:
            return
        self._ui_system.update(world, viewport_size)

    def _current_viewport_size(self) -> tuple[float, float]:
        if self.editor_layout is not None and self.editor_layout.game_texture is not None:
            texture = self.editor_layout.game_texture.texture
            return (float(texture.width), float(texture.height))
        return (float(self.width), float(self.height))

    def _current_scene_viewport_size(self) -> tuple[float, float]:
        if self.editor_layout is not None and self.editor_layout.scene_texture is not None:
            texture = self.editor_layout.scene_texture.texture
            return (float(texture.width), float(texture.height))
        return (float(self.width), float(self.height))

    def _render_ui_to_texture(self, world: Optional["World"], texture: Any, *, render_editor_overlay: bool = False) -> None:
        if self._ui_render_system is None or self._ui_system is None or world is None or texture is None:
            return
        rl.begin_texture_mode(texture)
        try:
            self._ui_render_system.render(world, self._ui_system)
            if render_editor_overlay and self.gizmo_system is not None and self.editor_layout is not None:
                self.gizmo_system.render_ui_overlay(
                    world,
                    self._ui_system,
                    self.editor_layout.active_tool,
                    self.editor_layout.transform_space,
                    self._current_scene_viewport_size(),
                )
        finally:
            rl.end_texture_mode()
    
    def _process_input(self) -> None:
        # Controles de Debug (solo en PAUSE/PLAY)
        if self._state in (EngineState.PAUSED, EngineState.PLAY):
            # F10: Step
            if rl.is_key_pressed(rl.KEY_F10):
                self.step()
            
            # F5: Quick Save Snapshot
            if rl.is_key_pressed(rl.KEY_F5):
                self.save_snapshot()
            
            # F6: Quick Load Last Snapshot
            if rl.is_key_pressed(rl.KEY_F6):
                self.load_last_snapshot()
        
        # F11: Fullscreen
        if rl.is_key_pressed(rl.KEY_F11):
            # Toggle Fullscreen
            # Nota: En Raylib a veces es mejor usar ToggleBorderlessWindowed para evitar cambios de resolución
            current = rl.is_window_fullscreen()
            if not current:
                # Maximizar antes de fullscreen ayuda en algunos OS
                display = rl.get_current_monitor()
                rl.set_window_size(rl.get_monitor_width(display), rl.get_monitor_height(display))
                rl.toggle_fullscreen()
            else:
                rl.toggle_fullscreen()
                rl.set_window_size(self.width, self.height) # Restaurar (aunque deberíamos guardar el tamaño previo)
    
        # F8: Hot-Reload Scripts
        if rl.is_key_pressed(rl.KEY_F8):
            reloaded = self.hot_reload_manager.check_for_changes()
            if reloaded:
                for mod_name in reloaded:
                    log_info(f"Hot-reload: {mod_name} recargado")
            else:
                log_info("Hot-reload: Sin cambios detectados")
            # Log errors if any
            for err in self.hot_reload_manager.get_errors():
                log_err(err)

        if rl.is_key_pressed(rl.KEY_F9):
            self.show_performance_overlay = not self.show_performance_overlay
            log_info(f"Performance overlay: {'ON' if self.show_performance_overlay else 'OFF'}")

        if rl.is_key_pressed(rl.KEY_F7) and not rl.is_key_down(rl.KEY_LEFT_CONTROL) and not rl.is_key_down(rl.KEY_RIGHT_CONTROL):
            self.debug_draw_colliders = not self.debug_draw_colliders
            if self._render_system is not None and hasattr(self._render_system, "set_debug_options"):
                self._render_system.set_debug_options(draw_colliders=self.debug_draw_colliders)
            log_info(f"Collider overlay: {'ON' if self.debug_draw_colliders else 'OFF'}")

        if (rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL)) and rl.is_key_pressed(rl.KEY_F7):
            self.debug_draw_labels = not self.debug_draw_labels
            if self._render_system is not None and hasattr(self._render_system, "set_debug_options"):
                self._render_system.set_debug_options(draw_labels=self.debug_draw_labels)
            log_info(f"Debug labels: {'ON' if self.debug_draw_labels else 'OFF'}")
        
        # Ctrl+S: Save
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_S):
            self.save_current_scene()
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_Z):
            self._history_manager.undo()
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_Y):
            self._history_manager.redo()
            
    def save_current_scene(self) -> None:
        """Guarda la escena actual a disco."""
        if self._scene_manager is None:
            print("[ERROR] No hay SceneManager activo, no se puede guardar.")
            return
        if not self._save_scene_entry(prompt_if_needed=True):
            print("[ERROR] Fallo al guardar.")
    
    def _reload_scene(self) -> None:
        """Recarga la escena actual."""
        print("[INFO] Recargando escena...")
        
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
        
        if self._scene_manager is not None:
            self._world = self._scene_manager.reload_scene()
        elif self._level_loader is not None and self._world is not None:
            self._level_loader.reload(self._world)

    def _update_gameplay(self, world: "World", dt: float) -> None:
        """Actualiza la lógica del juego (Física, Colisiones, Reglas)."""
        if self._input_system is not None:
            self._input_system.update(world)
        if self._character_controller_system is not None:
            self._character_controller_system.update(world, dt)
        if self._player_controller_system is not None:
            self._player_controller_system.update(world)
        if self._script_behaviour_system is not None:
            self._script_behaviour_system.update(world, dt, is_edit_mode=False)
        backend_name = self._resolve_physics_backend_name(world)
        backend = self._physics_backends.get(backend_name)
        if backend is not None and self._state.allows_physics():
            backend.step(world, dt)
        else:
            if self._physics_system is not None and self._state.allows_physics():
                self._physics_system.update(world, dt)
            if self._collision_system is not None and self._state.allows_gameplay():
                self._collision_system.update(world)
        if self._audio_system is not None:
            self._audio_system.update(world)

    def _resolve_physics_backend_name(self, world: Optional["World"]) -> str:
        metadata = world.feature_metadata if world is not None else {}
        physics_2d = metadata.get("physics_2d", {}) if isinstance(metadata, dict) else {}
        return str(physics_2d.get("backend", self._physics_backend_name or "legacy_aabb"))

    def _refresh_default_physics_backend(self) -> None:
        if self._physics_system is None or self._collision_system is None:
            return
        self.set_physics_backend(
            LegacyAABBPhysicsBackend(self._physics_system, self._collision_system, event_bus=self._event_bus),
            backend_name="legacy_aabb",
        )
            
    def step(self) -> None:
        """Avanza exactamente un frame de simulación."""
        if self._state == EngineState.EDIT:
            return
            
        # Si estamos en PLAY, pausamos primero
        if self._state == EngineState.PLAY:
            self.pause()
            
        # Cambiamos a STEPPING para permitir un update
        print("[DEBUG] Step frame")
        self._state = EngineState.STEPPING
        
    def save_snapshot(self) -> None:
        """Guarda un snapshot del estado actual."""
        if self.world is None:
            return
        
        self.timeline.add_snapshot(self.world, self.time.frame_count, self.time.time)
        print(f"[DEBUG] Snapshot saved. Total: {self.timeline.count()}")
        
    def load_last_snapshot(self) -> None:
        """Carga el último snapshot guardado."""
        snapshot = self.timeline.get_latest_snapshot()
        if snapshot is None:
            print("[DEBUG] No snapshots available")
            return
            
        # Restaurar estado
        if self._scene_manager is not None:
            # Reemplazar el mundo activo en scene_manager
            self._scene_manager.restore_world(snapshot.restore())
            # Actualizar referencia local
            self._world = self._scene_manager.active_world
            
            # Reconfigurar sistemas
            if self._rule_system is not None and self._world is not None:
                self._rule_system.set_world(self._world)
                
            print(f"[DEBUG] Snapshot loaded. Frame: {snapshot.frame}")
    
    def undo(self) -> bool:
        """Revierte el ultimo cambio de authoring en modo edicion."""
        if self._state != EngineState.EDIT:
            return False
        return self._history_manager.undo()

    def redo(self) -> bool:
        """Reaplica el ultimo cambio revertido en modo edicion."""
        if self._state != EngineState.EDIT:
            return False
        return self._history_manager.redo()

    def _draw_debug_info(self) -> None:
        # Estado
        state_color = {
            EngineState.EDIT: rl.SKYBLUE,
            EngineState.PLAY: rl.GREEN,
            EngineState.PAUSED: rl.ORANGE
        }
        rl.draw_text(
            f"[{self._state}]",
            self.width // 2 - 40, 10, 20,
            state_color.get(self._state, rl.WHITE)
        )
        
        rl.draw_text(f"FPS: {self.time.fps}", 10, 10, 20, rl.GREEN)
        
        active_world = self.world
        if active_world is not None:
            rl.draw_text(f"Entities: {active_world.entity_count()}", 10, 35, 16, rl.LIGHTGRAY)
        
        if self._collision_system is not None and self._state == EngineState.PLAY:
            collisions = len(self._collision_system.get_collisions())
            color = rl.YELLOW if collisions > 0 else rl.LIGHTGRAY
            rl.draw_text(f"Collisions: {collisions}", 10, 55, 16, color)
        
        if self._scene_manager is not None:
            rl.draw_text(f"Scene: {self._scene_manager.scene_name}", 10, 75, 14, rl.SKYBLUE)
        elif self._level_loader is not None:
            rl.draw_text(f"Level: {self._level_loader.current_level_name}", 10, 75, 14, rl.SKYBLUE)
        
        if self._rule_system is not None and self._state == EngineState.PLAY:
            rl.draw_text(
                f"Rules: {self._rule_system.rules_count} | Exec: {self._rule_system.rules_executed_count}",
                10, 95, 12, rl.ORANGE
            )

    def _update_perf_counters(self, active_world: Optional["World"]) -> None:
        if active_world is None:
            self._perf_counters = {
                "entities": 0,
                "render_entities": 0,
                "draw_calls": 0,
                "batches": 0,
                "render_target_passes": 0,
                "physics_ccd_bodies": 0,
                "canvases": 0,
                "buttons": 0,
                "scripts": 0,
            }
            return

        render_entities = 0
        draw_calls = 0
        batches = 0
        render_target_passes = 0
        physics_ccd_bodies = 0
        if self._render_system is not None and hasattr(self._render_system, "get_last_render_stats"):
            render_stats = self._render_system.get_last_render_stats()
            render_entities = int(render_stats.get("render_entities", 0))
            draw_calls = int(render_stats.get("draw_calls", 0))
            batches = int(render_stats.get("batches", 0))
            render_target_passes = int(render_stats.get("render_target_passes", 0))
        backend_name = self._resolve_physics_backend_name(active_world)
        backend = self._physics_backends.get(backend_name)
        if backend is not None and hasattr(backend, "get_step_metrics"):
            physics_ccd_bodies = int(backend.get_step_metrics().get("ccd_bodies", 0))

        self._perf_counters = {
            "entities": active_world.entity_count(),
            "render_entities": render_entities,
            "draw_calls": draw_calls,
            "batches": batches,
            "render_target_passes": render_target_passes,
            "physics_ccd_bodies": physics_ccd_bodies,
            "canvases": len(active_world.get_entities_with(Canvas)),
            "buttons": len(active_world.get_entities_with(UIButton)),
            "scripts": len(active_world.get_entities_with(ScriptBehaviour)),
        }

    def _draw_performance_overlay(self) -> None:
        if not self.show_performance_overlay:
            return

        panel_width = 260
        panel_height = 246
        panel_x = self.width - panel_width - 12
        panel_y = 12
        panel_rect = rl.Rectangle(panel_x, panel_y, panel_width, panel_height)
        rl.draw_rectangle_rec(panel_rect, rl.Color(15, 18, 22, 220))
        rl.draw_rectangle_lines_ex(panel_rect, 1, rl.Color(80, 120, 160, 255))
        rl.draw_text("Performance", panel_x + 10, panel_y + 8, 14, rl.RAYWHITE)

        rows = [
            ("frame", self._perf_stats.get("frame", 0.0)),
            ("render", self._perf_stats.get("render", 0.0)),
            ("inspector", self._perf_stats.get("inspector", 0.0)),
            ("hierarchy", self._perf_stats.get("hierarchy", 0.0)),
            ("ui", self._perf_stats.get("ui", 0.0)),
            ("scripts", self._perf_stats.get("scripts", 0.0)),
            ("selection", self._perf_stats.get("selection_gizmo", 0.0)),
        ]
        text_y = panel_y + 32
        for label, value in rows:
            color = rl.ORANGE if value > 8.0 else rl.LIGHTGRAY
            rl.draw_text(f"{label:>10}: {value:5.2f} ms", panel_x + 10, text_y, 10, color)
            text_y += 16

        text_y += 4
        rl.draw_text(f"entities: {self._perf_counters.get('entities', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"drawables: {self._perf_counters.get('render_entities', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"draws/batches: {self._perf_counters.get('draw_calls', 0)}/{self._perf_counters.get('batches', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"rt passes: {self._perf_counters.get('render_target_passes', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"ccd bodies: {self._perf_counters.get('physics_ccd_bodies', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"canvases/buttons: {self._perf_counters.get('canvases', 0)}/{self._perf_counters.get('buttons', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 14
        rl.draw_text(f"scripts: {self._perf_counters.get('scripts', 0)}", panel_x + 10, text_y, 10, rl.SKYBLUE)
        text_y += 16
        rl.draw_text(
            f"F7 colliders: {'ON' if self.debug_draw_colliders else 'OFF'} | Ctrl+F7 labels: {'ON' if self.debug_draw_labels else 'OFF'}",
            panel_x + 10,
            text_y,
            10,
            rl.GRAY,
        )
        
    def _render_frame(self, active_world: "World") -> None:
        """Renderiza un frame completo de la aplicación (Scene, Game, UI)."""
        rl.begin_drawing()
        rl.clear_background(rl.DARKGRAY)
        self._perf_stats["inspector"] = 0.0
        self._perf_stats["hierarchy"] = 0.0
        
        try:
            # --- WINDOW RESIZE HANDLING ---
            if rl.is_window_resized():
                self.width = rl.get_screen_width()
                self.height = rl.get_screen_height()
                if self.editor_layout:
                    self.editor_layout.update_layout(self.width, self.height)

            # --- SCENE VIEW RENDER ---
            # Renderizar Scene siempre que la pestaña esté activa (Edit o Play)
            if self.editor_layout and self.editor_layout.active_tab == "SCENE":
                self.editor_layout.begin_scene_render()
                
                # Render World (Editor Camera)
                if self._render_system is not None and active_world is not None:
                     self._render_system.render(active_world, use_world_camera=False)

                # Render Gizmos
                if self.gizmo_system is not None and active_world is not None:
                    active_tool = self.editor_layout.active_tool if self.editor_layout else EditorTool.MOVE
                    transform_space = self.editor_layout.transform_space if self.editor_layout else TransformSpace.WORLD
                    pivot_mode = self.editor_layout.pivot_mode if self.editor_layout else PivotMode.PIVOT
                    self.gizmo_system.render(active_world, active_tool, transform_space, pivot_mode)
                    
                self.editor_layout.end_scene_render()
                if active_world is not None and self.editor_layout.scene_texture is not None:
                    self._render_ui_to_texture(active_world, self.editor_layout.scene_texture, render_editor_overlay=True)
            
            # --- GAME VIEW RENDER ---
            if self.editor_layout and self.editor_layout.active_tab == "GAME":
                target_world = self.world if self._state == EngineState.PLAY or self._state == EngineState.PAUSED else None
                
                self.editor_layout.begin_game_render()
                if target_world and self._render_system:
                    texture = self.editor_layout.game_texture.texture
                    viewport_size = (float(texture.width), float(texture.height))
                    self._render_system.render(target_world, viewport_size=viewport_size)
                else:
                    rl.draw_text("Press PLAY to start", 10, 10, 20, rl.GRAY)
                    
                self.editor_layout.end_game_render()
                if target_world is not None and self.editor_layout.game_texture is not None:
                    self._render_ui_to_texture(target_world, self.editor_layout.game_texture)
            
            if self.editor_layout and self.editor_layout.active_tab == "ANIMATOR":
                pass
            
            # --- MAIN SCREEN RENDER (LAYOUT & OVERLAYS) ---
            if self.editor_layout:
                is_playing = (self._state == EngineState.PLAY or self._state == EngineState.PAUSED)
                self.editor_layout.draw_layout(is_playing)
            else:
                 # Fallback
                 if self._render_system is not None and active_world is not None:
                    self._render_system.render(active_world)

            # Inspector Render (Overlay on Layout)
            if self._inspector_system is not None and active_world is not None:
                if self.editor_layout:
                    rect = self.editor_layout.inspector_rect
                    inspector_start = time.perf_counter()
                    self._inspector_system.render(
                        active_world, 
                        int(rect.x), int(rect.y), 
                        int(rect.width), int(rect.height),
                        is_edit_mode=self.is_edit_mode
                    )
                    self._perf_stats["inspector"] = (time.perf_counter() - inspector_start) * 1000.0

            if self.assistant_panel is not None and self.editor_layout is not None:
                rect = self.editor_layout.assistant_rect
                self.assistant_panel.render(int(rect.x), int(rect.y), int(rect.width), int(rect.height))

            if self.animator_panel is not None and active_world is not None and self.editor_layout and self.editor_layout.active_tab == "ANIMATOR":
                rect = self.editor_layout.get_center_view_rect()
                self.animator_panel.render(
                    active_world,
                    int(rect.x),
                    int(rect.y),
                    int(rect.width),
                    int(rect.height),
                )

            if self.sprite_editor_modal is not None and self.sprite_editor_modal.is_open:
                self.sprite_editor_modal.render(self.width, self.height)

            self._draw_debug_info()
            self._draw_performance_overlay()
            
            # Hierachy Panel Overlay
            if self.hierarchy_panel is not None and active_world is not None:
                hierarchy_start = time.perf_counter()
                if self.editor_layout:
                    rect = self.editor_layout.hierarchy_rect
                    self.hierarchy_panel.render(active_world, int(rect.x), int(rect.y), int(rect.width), int(rect.height))
                else:
                    self.hierarchy_panel.render(active_world, 0, 0, 200, self.height)
                self._perf_stats["hierarchy"] = (time.perf_counter() - hierarchy_start) * 1000.0

        finally:
            rl.end_drawing()

    def _cleanup(self) -> None:
        self.running = False
        if self._render_system is not None:
            self._render_system.cleanup()
        if self.animator_panel is not None:
            self.animator_panel.cleanup()
        if self.sprite_editor_modal is not None:
            self.sprite_editor_modal.cleanup()
        rl.close_window()

    def _open_sprite_editor(self, asset_path: str) -> None:
        if self.sprite_editor_modal is None or not asset_path:
            return
        self.sprite_editor_modal.open(asset_path)
    
    def _process_ui_requests(self) -> None:
        """Procesa peticiones de UI (Escenas, Menús de archivo)."""
        if self._scene_manager is None:
            return

        if self.editor_layout is not None and self.editor_layout.project_panel and self.editor_layout.project_panel.request_open_sprite_editor_for:
            target_asset = self.editor_layout.project_panel.request_open_sprite_editor_for
            self.editor_layout.project_panel.request_open_sprite_editor_for = None
            self._open_sprite_editor(target_asset)
        if self.editor_layout is not None and self.editor_layout.project_panel and self.editor_layout.project_panel.request_open_scene_for:
            target_scene = self.editor_layout.project_panel.request_open_scene_for
            self.editor_layout.project_panel.request_open_scene_for = None
            self.load_scene_by_path(target_scene)

        if self.animator_panel is not None and self.animator_panel.request_open_sprite_editor_for:
            target_asset = self.animator_panel.request_open_sprite_editor_for
            self.animator_panel.request_open_sprite_editor_for = None
            self._open_sprite_editor(target_asset)

        if self._inspector_system is not None and self._inspector_system.request_open_sprite_editor_for:
            target_asset = self._inspector_system.request_open_sprite_editor_for
            self._inspector_system.request_open_sprite_editor_for = None
            self._open_sprite_editor(target_asset)

        if self.editor_layout is None:
            return

        if self.editor_layout.request_activate_scene_key:
            target_key = self.editor_layout.request_activate_scene_key
            self.editor_layout.request_activate_scene_key = ""
            self._activate_scene_workspace_tab(target_key)

        if self.editor_layout.request_close_scene_key:
            target_key = self.editor_layout.request_close_scene_key
            self.editor_layout.request_close_scene_key = ""
            entry = self._scene_manager._resolve_entry(target_key)  # type: ignore[attr-defined]
            if entry is not None:
                if entry.dirty:
                    self.editor_layout.pending_scene_close_key = entry.key
                    self.editor_layout.dirty_modal_context = "close_scene"
                    self.editor_layout.show_project_dirty_modal = True
                else:
                    self._close_scene_workspace_tab(entry.key, discard_changes=True)

        if self.editor_layout.request_browse_project:
            self.editor_layout.request_browse_project = False
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw()
                initial_dir = self._project_service.editor_root.as_posix() if self._project_service is not None else os.getcwd()
                path = filedialog.askdirectory(initialdir=initial_dir, title="Add Existing Project")
                root.destroy()
                if path and self._project_service is not None:
                    self._project_service.register_project(path)
                    self._refresh_launcher_projects()
                    self.editor_layout.set_launcher_feedback("Project added to launcher")
            except Exception as e:
                if self.editor_layout is not None:
                    self.editor_layout.set_launcher_feedback(f"Add project failed: {e}", is_error=True)
                print(f"[ERROR] Open Project browse failed: {e}")

        if self.editor_layout.request_exit_launcher:
            self.editor_layout.request_exit_launcher = False
            self.running = False
            return

        if self.editor_layout.request_create_project:
            self.editor_layout.request_create_project = False
            try:
                project_name = self.editor_layout.launcher_create_name.strip()
                if not project_name:
                    raise ValueError("Project name is required")
                if self._project_service is None:
                    raise RuntimeError("Project service not ready")
                project_root = self._project_service.build_internal_project_path(project_name)
                self._project_service.create_project(project_root, name=project_name)
                self._refresh_launcher_projects()
                self.editor_layout.show_create_project_modal = False
                self.editor_layout.launcher_create_name_focused = False
                self.editor_layout.set_launcher_feedback("Project created")
                self.editor_layout.pending_project_path = project_root.as_posix()
            except Exception as e:
                self.editor_layout.set_launcher_feedback(f"Create project failed: {e}", is_error=True)
                print(f"[ERROR] Create Project failed: {e}")

        if self.editor_layout.request_remove_project_path:
            path = self.editor_layout.request_remove_project_path
            self.editor_layout.request_remove_project_path = ""
            if self._project_service is not None:
                self._project_service.remove_registered_project(path)
                self._refresh_launcher_projects()
                self.editor_layout.set_launcher_feedback("Project removed from launcher")

        if self.editor_layout.request_create_canvas:
            self.editor_layout.request_create_canvas = False
            self._scene_manager.create_entity(
                "Canvas",
                components={
                    "Canvas": {
                        "enabled": True,
                        "render_mode": "screen_space_overlay",
                        "reference_width": 800,
                        "reference_height": 600,
                        "match_mode": "stretch",
                        "sort_order": 0,
                    },
                    "RectTransform": {
                        "enabled": True,
                        "anchor_min_x": 0.0,
                        "anchor_min_y": 0.0,
                        "anchor_max_x": 1.0,
                        "anchor_max_y": 1.0,
                        "pivot_x": 0.0,
                        "pivot_y": 0.0,
                        "anchored_x": 0.0,
                        "anchored_y": 0.0,
                        "width": 0.0,
                        "height": 0.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    },
                },
            )

        active_world = self.world
        default_ui_parent = active_world.selected_entity_name if active_world is not None else None
        if not default_ui_parent and active_world is not None:
            from engine.components.canvas import Canvas

            for entity in active_world.get_all_entities():
                if entity.has_component(Canvas):
                    default_ui_parent = entity.name
                    break

        if self.editor_layout.request_create_ui_text:
            self.editor_layout.request_create_ui_text = False
            if default_ui_parent:
                self._scene_manager.create_child_entity(
                    default_ui_parent,
                    "Text",
                    components={
                        "RectTransform": {
                            "enabled": True,
                            "anchor_min_x": 0.5,
                            "anchor_min_y": 0.5,
                            "anchor_max_x": 0.5,
                            "anchor_max_y": 0.5,
                            "pivot_x": 0.5,
                            "pivot_y": 0.5,
                            "anchored_x": 0.0,
                            "anchored_y": 0.0,
                            "width": 260.0,
                            "height": 64.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        },
                        "UIText": {
                            "enabled": True,
                            "text": "New Text",
                            "font_size": 28,
                            "color": [255, 255, 255, 255],
                            "alignment": "center",
                            "wrap": False,
                        },
                    },
                )

        if self.editor_layout.request_create_ui_button:
            self.editor_layout.request_create_ui_button = False
            if default_ui_parent:
                self._scene_manager.create_child_entity(
                    default_ui_parent,
                    "Button",
                    components={
                        "RectTransform": {
                            "enabled": True,
                            "anchor_min_x": 0.5,
                            "anchor_min_y": 0.5,
                            "anchor_max_x": 0.5,
                            "anchor_max_y": 0.5,
                            "pivot_x": 0.5,
                            "pivot_y": 0.5,
                            "anchored_x": 0.0,
                            "anchored_y": 0.0,
                            "width": 280.0,
                            "height": 76.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        },
                        "UIButton": {
                            "enabled": True,
                            "interactable": True,
                            "label": "Button",
                            "normal_color": [72, 72, 72, 255],
                            "hover_color": [92, 92, 92, 255],
                            "pressed_color": [56, 56, 56, 255],
                            "disabled_color": [48, 48, 48, 200],
                            "transition_scale_pressed": 0.96,
                            "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                        },
                    },
                )

        if self.editor_layout.pending_project_path and not self.editor_layout.show_project_dirty_modal:
            target_project = self.editor_layout.pending_project_path
            if self._project_loaded and self._scene_manager.has_unsaved_scenes:
                self.editor_layout.dirty_modal_context = "project_switch"
                self.editor_layout.show_project_dirty_modal = True
            else:
                self.editor_layout.pending_project_path = ""
                self.open_project(target_project)

        if self.editor_layout.project_switch_decision:
            decision = self.editor_layout.project_switch_decision
            self.editor_layout.project_switch_decision = ""
            context = self.editor_layout.dirty_modal_context
            self.editor_layout.dirty_modal_context = ""
            target_project = self.editor_layout.pending_project_path
            target_scene_close_key = self.editor_layout.pending_scene_close_key
            if context == "close_scene":
                self.editor_layout.pending_scene_close_key = ""
                if decision == "save":
                    if self._save_scene_entry(target_scene_close_key, prompt_if_needed=True):
                        self._close_scene_workspace_tab(target_scene_close_key, discard_changes=True)
                elif decision == "discard":
                    self._close_scene_workspace_tab(target_scene_close_key, discard_changes=True)
            elif context == "project_switch":
                if decision == "save":
                    if self._save_all_dirty_scenes() and target_project:
                        self.editor_layout.pending_project_path = ""
                        self.open_project(target_project)
                elif decision == "discard":
                    self._scene_manager.clear_all_dirty()
                    if target_project:
                        self.editor_layout.pending_project_path = ""
                        self.open_project(target_project)
                else:
                    self.editor_layout.pending_project_path = ""
            else:
                self.editor_layout.pending_project_path = ""
                self.editor_layout.pending_scene_close_key = ""

        # NEW SCENE
        if self.editor_layout.request_new_scene:
            self.editor_layout.request_new_scene = False
            self.editor_layout.active_tab = "SCENE"
            self.editor_layout.show_create_scene_modal = True
            self.editor_layout.scene_create_name = "New Scene"
            self.editor_layout.scene_create_name_focused = True
        if self.editor_layout.request_create_scene:
            self.editor_layout.request_create_scene = False
            scene_name = self.editor_layout.scene_create_name.strip()
            if self.create_scene(scene_name):
                self.editor_layout.show_create_scene_modal = False
                self.editor_layout.scene_create_name_focused = False
                print(f"[GUI] Scene created: {scene_name}")

        # SAVE SCENE
        if self.editor_layout.request_save_scene:
            self.editor_layout.request_save_scene = False
            self.save_current_scene()

        # LOAD SCENE
        if self.editor_layout.request_load_scene:
            self.editor_layout.request_load_scene = False
            self._refresh_project_scene_entries()
            self.editor_layout.pending_scene_open_path = ""
            self.editor_layout.show_scene_browser_modal = True

        if self.editor_layout.pending_scene_open_path:
            target_scene_path = self.editor_layout.pending_scene_open_path
            self.editor_layout.pending_scene_open_path = ""
            self.load_scene_by_path(target_scene_path)

        if self.editor_layout.request_browse_scene_file:
            self.editor_layout.request_browse_scene_file = False
            try:
                import tkinter
                from tkinter import filedialog
                root = tkinter.Tk()
                root.withdraw()
                path = filedialog.askopenfilename(
                    filetypes=[("Scene Files", "*.json"), ("All Files", "*.*")],
                    initialdir=self._project_service.get_project_path("levels").as_posix() if self._project_service is not None else os.getcwd(),
                    title="Add Scene"
                )
                root.destroy()
                if path:
                    self.load_scene_by_path(path)
            except Exception as e:
                print(f"[ERROR] Load Dialog failed: {e}")
