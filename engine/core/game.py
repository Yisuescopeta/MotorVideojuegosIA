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

import random
import time
from typing import TYPE_CHECKING, Any, Optional

import pyray as rl

from engine.app import (
    DebugToolsController,
    EditorInteractionController,
    ProjectWorkspaceController,
    RuntimeController,
    SceneTransitionController,
    SceneWorkflowController,
)
from engine.components.canvas import Canvas
from engine.config import EDIT_ANIMATION_SPEED, ENGINE_VERSION, SCRIPTS_DIRECTORY, TIMELINE_CAPACITY
from engine.core.engine_state import EngineState
from engine.core.hot_reload import HotReloadManager
from engine.core.time_manager import TimeManager
from engine.debug.profiler import EngineProfiler
from engine.debug.timeline import Timeline
from engine.editor.animator_panel import AnimatorPanel
from engine.editor.cursor_manager import CustomCursorRenderer
from engine.editor.editor_layout import EditorLayout
from engine.editor.editor_tools import EditorTool, PivotMode, TransformSpace
from engine.editor.gizmo_system import GizmoSystem
from engine.editor.hierarchy_panel import HierarchyPanel
from engine.editor.console_panel import log_err, log_warn
from engine.editor.raygui_theme import apply_unity_dark_theme
from engine.editor.render_safety import safe_reset_clip_state
from engine.editor.sprite_editor_modal import SpriteEditorModal
from engine.editor.terminal_panel import TerminalPanel
from engine.editor.undo_redo import UndoRedoManager
from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection
from engine.physics.registry import PhysicsBackendRegistry
from engine.project.project_service import ProjectService

if TYPE_CHECKING:
    from cli.script_executor import ScriptExecutor
    from engine.ecs.world import World
    from engine.events.event_bus import EventBus
    from engine.events.rule_system import RuleSystem
    from engine.inspector.inspector_system import InspectorSystem
    from engine.levels.level_loader import LevelLoader
    from engine.scenes.scene_manager import SceneManager
    from engine.systems.animation_system import AnimationSystem
    from engine.systems.audio_system import AudioSystem
    from engine.systems.character_controller_system import CharacterControllerSystem
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.input_system import InputSystem
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.player_controller_system import PlayerControllerSystem
    from engine.systems.render_system import RenderSystem
    from engine.systems.script_behaviour_system import ScriptBehaviourSystem
    from engine.systems.selection_system import SelectionSystem
    from engine.systems.ui_render_system import UIRenderSystem
    from engine.systems.ui_system import UISystem


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
        self._physics_backend_registry: PhysicsBackendRegistry = PhysicsBackendRegistry(default_backend_name="legacy_aabb")
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
        self.terminal_panel: Optional["TerminalPanel"] = TerminalPanel()
        self.gizmo_system: Optional["GizmoSystem"] = GizmoSystem()
        self.editor_layout: Optional["EditorLayout"] = None
        self._cursor_renderer: CustomCursorRenderer = CustomCursorRenderer()
        
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
        self._profiler: EngineProfiler = EngineProfiler()
        self.debug_draw_colliders: bool = False
        self.debug_draw_labels: bool = False
        self.random_seed: int | None = None
        self._scene_transition_controller = SceneTransitionController(
            get_state=lambda: self._state,
            get_world=lambda: self.world,
            get_scene_manager=lambda: self._scene_manager,
            get_physics_backend_registry=lambda: self._physics_backend_registry,
            load_scene_by_path=self._load_runtime_scene_from_ui,
            play_runtime=self.play,
        )
        self._runtime_controller = RuntimeController(
            get_state=lambda: self._state,
            set_state=lambda value: setattr(self, "_state", value),
            get_world=lambda: self.world,
            set_world=self.set_world,
            get_scene_manager=lambda: self._scene_manager,
            get_rule_system=lambda: self._rule_system,
            get_script_behaviour_system=lambda: self._script_behaviour_system,
            get_event_bus=lambda: self._event_bus,
            get_animation_system=lambda: self._animation_system,
            get_input_system=lambda: self._input_system,
            get_player_controller_system=lambda: self._player_controller_system,
            get_character_controller_system=lambda: self._character_controller_system,
            get_physics_system=lambda: self._physics_system,
            get_collision_system=lambda: self._collision_system,
            get_audio_system=lambda: self._audio_system,
            get_scene_transition_controller=lambda: self._scene_transition_controller,
            get_physics_backend_registry=lambda: self._physics_backend_registry,
            reset_profiler=self.reset_profiler,
            set_physics_backend=self.set_physics_backend,
            edit_animation_speed=self.EDIT_ANIMATION_SPEED,
        )
        self._debug_tools_controller = DebugToolsController(
            time_manager=self.time,
            timeline=self.timeline,
            profiler=self._profiler,
            hot_reload_manager=self.hot_reload_manager,
            perf_stats=self._perf_stats,
            perf_counters=self._perf_counters,
            get_state=lambda: self._state,
            get_world=lambda: self.world,
            set_world=self.set_world,
            get_scene_manager=lambda: self._scene_manager,
            get_level_loader=lambda: self._level_loader,
            get_rule_system=lambda: self._rule_system,
            get_collision_system=lambda: self._collision_system,
            get_render_system=lambda: self._render_system,
            get_physics_backend_registry=lambda: self._physics_backend_registry,
            get_width=lambda: self.width,
            get_show_performance_overlay=lambda: self.show_performance_overlay,
            set_show_performance_overlay=lambda value: setattr(self, "show_performance_overlay", value),
            get_debug_draw_colliders=lambda: self.debug_draw_colliders,
            set_debug_draw_colliders=lambda value: setattr(self, "debug_draw_colliders", value),
            get_debug_draw_labels=lambda: self.debug_draw_labels,
            set_debug_draw_labels=lambda value: setattr(self, "debug_draw_labels", value),
        )
        self._scene_workflow_controller = SceneWorkflowController(
            get_scene_manager=lambda: self._scene_manager,
            get_project_service=lambda: self._project_service,
            get_editor_layout=lambda: self.editor_layout,
            get_state=lambda: self._state,
            stop_runtime=self._stop_runtime_flow,
            capture_active_scene_view_state=self._capture_active_scene_view_state,
            sync_scene_workspace_ui=self._sync_scene_workspace_ui,
            refresh_project_scene_entries=self._refresh_project_scene_entries,
            clear_rules_and_events=self._clear_rules_and_events,
            set_world=self.set_world,
            set_project_loaded=lambda value: setattr(self, "_project_loaded", value),
            get_scene_flow=self.get_scene_flow,
            play_runtime=self.play,
            get_level_loader=lambda: self._level_loader,
        )
        self._project_workspace_controller = ProjectWorkspaceController(
            get_project_service=lambda: self._project_service,
            get_scene_manager=lambda: self._scene_manager,
            get_editor_layout=lambda: self.editor_layout,
            get_state=lambda: self._state,
            get_current_scene_path=lambda: self.current_scene_path,
            set_current_scene_path=lambda value: setattr(self, "current_scene_path", value),
            is_project_loaded=lambda: self._project_loaded,
            set_project_loaded=lambda value: setattr(self, "_project_loaded", value),
            set_world=self.set_world,
            terminal_panel=self.terminal_panel,
            animator_panel=self.animator_panel,
            sprite_editor_modal=self.sprite_editor_modal,
            history_manager=self._history_manager,
            hot_reload_manager=self.hot_reload_manager,
            timeline=self.timeline,
            get_render_system=lambda: self._render_system,
            get_audio_system=lambda: self._audio_system,
            get_script_behaviour_system=lambda: self._script_behaviour_system,
            get_rule_system=lambda: self._rule_system,
            get_event_bus=lambda: self._event_bus,
            load_scene_by_path=self.load_scene_by_path,
            sync_scene_workspace_ui=self._sync_scene_workspace_ui,
            save_all_dirty_scenes=self._save_all_dirty_scenes,
            save_scene_entry=self._save_scene_entry,
            close_scene_workspace_tab=self._close_scene_workspace_tab,
            stop_runtime=self._stop_runtime_flow,
            set_running=lambda value: setattr(self, "running", value),
        )
        self._editor_interaction_controller = EditorInteractionController(
            get_state=lambda: self._state,
            get_editor_layout=lambda: self.editor_layout,
            get_scene_manager=lambda: self._scene_manager,
            get_selection_system=lambda: self._selection_system,
            get_gizmo_system=lambda: self.gizmo_system,
            get_ui_system=lambda: self._ui_system,
            get_hierarchy_panel=lambda: self.hierarchy_panel,
            get_inspector_system=lambda: self._inspector_system,
            get_history_manager=lambda: self._history_manager,
            get_current_scene_viewport_size=self._current_scene_viewport_size,
            get_current_viewport_size=self._current_viewport_size,
        )
    
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
    def event_bus(self) -> Optional["EventBus"]:
        return self._event_bus

    @property
    def physics_system(self) -> Optional["PhysicsSystem"]:
        return self._physics_system

    @property
    def render_system(self) -> Optional["RenderSystem"]:
        return self._render_system

    @property
    def input_system(self) -> Optional["InputSystem"]:
        return self._input_system

    @property
    def project_service(self) -> Optional[ProjectService]:
        return self._project_service

    @property
    def has_project_loaded(self) -> bool:
        return self._project_loaded

    def _stop_runtime_flow(self) -> None:
        self.stop()

    def _toggle_fullscreen(self) -> None:
        current = rl.is_window_fullscreen()
        if not current:
            display = rl.get_current_monitor()
            rl.set_window_size(rl.get_monitor_width(display), rl.get_monitor_height(display))
            rl.toggle_fullscreen()
        else:
            rl.toggle_fullscreen()
            rl.set_window_size(self.width, self.height)

    def _clear_rules_and_events(self) -> None:
        if self._rule_system is not None:
            self._rule_system.clear_rules()
        if self._event_bus is not None:
            self._event_bus.clear_history()
    
    # === MÉTODOS DE CONTROL DE ESTADO ===
    
    def play(self) -> None:
        self._runtime_controller.play()
    
    def pause(self) -> None:
        self._runtime_controller.pause()
    
    def stop(self) -> None:
        self._runtime_controller.stop()

    def reset_profiler(self, run_label: str = "default") -> None:
        self._debug_tools_controller.reset_profiler(run_label=run_label)

    def get_profiler_report(self) -> dict[str, Any]:
        return self._debug_tools_controller.get_profiler_report()
    
    # === SETTERS ===
    
    def set_world(self, world: "World") -> None:
        self._world = world
    
    def set_render_system(self, system: "RenderSystem") -> None:
        self._render_system = system
        if self._project_service is not None:
            self._render_system.set_project_service(self._project_service)
        self._debug_tools_controller.apply_render_debug_options(self._render_system)
    
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
        if self._event_bus is not None and hasattr(self._character_controller_system, "set_event_bus"):
            self._character_controller_system.set_event_bus(self._event_bus)

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
        for backend in self._physics_backend_registry.iter_available_backends():
            backend.set_event_bus(event_bus)
        if self._character_controller_system is not None and hasattr(self._character_controller_system, "set_event_bus"):
            self._character_controller_system.set_event_bus(event_bus)
        if self._ui_system is not None:
            self._ui_system.set_event_bus(event_bus)
        self._scene_transition_controller.set_event_bus(event_bus)

    def set_physics_backend(self, backend: Any, backend_name: str = "legacy_aabb") -> None:
        normalized_name = str(backend_name or "legacy_aabb")
        self._physics_backend_registry.register_backend(backend, backend_name=normalized_name)
        backend.set_event_bus(self._event_bus)

    def set_physics_backend_unavailable(self, backend_name: str, reason: str) -> None:
        self._physics_backend_registry.mark_backend_unavailable(backend_name, reason=reason)
    
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
            if getattr(self.editor_layout, "flow_panel", None) is not None:
                self.editor_layout.flow_panel.set_scene_manager(manager)
            if getattr(self.editor_layout, "flow_workspace_panel", None) is not None:
                self.editor_layout.flow_workspace_panel.set_scene_manager(manager)
            self.editor_layout.set_scene_tabs(manager.list_open_scenes(), manager.active_scene_key)
            
    def set_selection_system(self, system: "SelectionSystem") -> None:
        self._selection_system = system

    def set_ui_system(self, system: "UISystem") -> None:
        self._ui_system = system
        self._ui_system.set_scene_loader(self.load_scene_by_path)
        self._ui_system.set_runtime_scene_loader(self._load_runtime_scene_from_ui)
        self._ui_system.set_scene_flow_loader(self._load_scene_flow_target_from_script)
        self._ui_system.set_scene_transition_runner(self._run_scene_transition)
        self._ui_system.set_interaction_enabled_resolver(self._is_runtime_ui_interaction_enabled)
        if self._event_bus is not None:
            self._ui_system.set_event_bus(self._event_bus)

    def _run_scene_transition(self, entity_name: str) -> bool:
        return self._scene_transition_controller.run_transition_for_entity(entity_name)

    def _load_runtime_scene_from_ui(self, path: str) -> bool:
        return self._scene_workflow_controller.load_scene_by_path_runtime(path)

    def set_ui_render_system(self, system: "UIRenderSystem") -> None:
        self._ui_render_system = system
        
    def set_script_executor(self, executor: "ScriptExecutor") -> None:
        """Asigna un ejecutor de scripts para automatización visual."""
        self.script_executor = executor

    def set_project_service(self, service: ProjectService) -> None:
        self._project_service = service
        self._project_workspace_controller.set_project_service(service)

    def _refresh_project_scene_entries(self) -> None:
        self._project_workspace_controller.refresh_project_scene_entries()

    def _persist_editor_preferences(self) -> None:
        if self.editor_layout is None or not self.editor_layout.consume_editor_preferences_dirty():
            return
        self._project_workspace_controller.persist_editor_preferences()

    def _sync_current_scene_path(self) -> None:
        self.current_scene_path = self._scene_workflow_controller.sync_current_scene_path()

    def _capture_active_scene_view_state(self) -> None:
        self._project_workspace_controller.capture_active_scene_view_state()

    def _apply_active_scene_view_state(self) -> None:
        self._project_workspace_controller.apply_active_scene_view_state()

    def _persist_workspace_state(self) -> None:
        self._project_workspace_controller.persist_workspace_state()

    def _sync_scene_workspace_ui(self, apply_view_state: bool = False) -> None:
        if self._scene_manager is None:
            return
        self._world = self._scene_manager.active_world
        self._sync_current_scene_path()
        if self.editor_layout is not None:
            self.editor_layout.set_scene_tabs(self._scene_manager.list_open_scenes(), self._scene_manager.active_scene_key)
            if getattr(self.editor_layout, "flow_panel", None) is not None:
                self.editor_layout.flow_panel.refresh(force=True)
            if getattr(self.editor_layout, "flow_workspace_panel", None) is not None:
                self.editor_layout.flow_workspace_panel.refresh(force=True)
        if apply_view_state:
            self._apply_active_scene_view_state()
        self._persist_workspace_state()

    def _save_scene_entry(self, key: Optional[str] = None, prompt_if_needed: bool = True) -> bool:
        return self._scene_workflow_controller.save_scene_entry(key, prompt_if_needed)

    def _save_all_dirty_scenes(self) -> bool:
        return self._scene_workflow_controller.save_all_dirty_scenes()

    def _autosave_dirty_scenes(self) -> None:
        self._scene_workflow_controller.autosave_dirty_scenes()

    def create_scene(self, scene_name: str) -> bool:
        return self._scene_workflow_controller.create_scene(scene_name)

    def activate_scene_workspace_tab(self, key_or_path: str) -> bool:
        return self._scene_workflow_controller.activate_scene_workspace_tab(key_or_path)

    def _activate_scene_workspace_tab(self, key_or_path: str) -> bool:
        return self.activate_scene_workspace_tab(key_or_path)

    def close_scene_workspace_tab(self, key_or_path: str, discard_changes: bool = False) -> bool:
        return self._scene_workflow_controller.close_scene_workspace_tab(key_or_path, discard_changes)

    def _close_scene_workspace_tab(self, key_or_path: str, discard_changes: bool = False) -> bool:
        return self.close_scene_workspace_tab(key_or_path, discard_changes)

    def sync_scene_workspace(self, apply_view_state: bool = False) -> None:
        self._sync_scene_workspace_ui(apply_view_state=apply_view_state)

    def load_scene_by_path(self, path: str) -> bool:
        return self._scene_workflow_controller.load_scene_by_path(path)

    def get_scene_flow(self) -> dict:
        if self._scene_manager is None:
            return {}
        metadata = self._scene_manager.get_feature_metadata()
        scene_flow = metadata.get("scene_flow", {})
        return dict(scene_flow) if isinstance(scene_flow, dict) else {}

    def load_scene_flow_target(self, key: str) -> bool:
        return self._scene_workflow_controller.load_scene_flow_target(key)

    def _load_scene_flow_target_from_script(self, key: str) -> bool:
        """Carga una escena desde script y conserva PLAY cuando aplica."""
        return self._scene_workflow_controller.load_scene_flow_target_from_script(key)

    def open_project(self, path: str) -> bool:
        return self._project_workspace_controller.open_project(path)

    def has_physics_backend(self, backend_name: str) -> bool:
        return self._physics_backend_registry.has_available_backend(backend_name)

    def knows_physics_backend(self, backend_name: str) -> bool:
        return self._physics_backend_registry.knows_backend(backend_name)

    def list_physics_backends(self) -> list[PhysicsBackendInfo]:
        return self._physics_backend_registry.list_backends()

    def get_physics_backend_selection(self, world: Optional["World"] = None) -> PhysicsBackendSelection:
        target_world = self.world if world is None else world
        return self._physics_backend_registry.resolve(
            target_world,
            default_backend_name=self._physics_backend_name,
        ).selection

    def refresh_runtime_physics_backend(self) -> None:
        self._refresh_default_physics_backend()

    def query_physics_aabb(self, left: float, top: float, right: float, bottom: float) -> list[dict[str, Any]]:
        active_world = self.world
        if active_world is None:
            return []
        resolved_backend = self._physics_backend_registry.resolve(
            active_world,
            default_backend_name=self._physics_backend_name,
        )
        if resolved_backend.backend is None:
            return []
        return resolved_backend.backend.query_aabb(active_world, (left, top, right, bottom))

    def query_physics_ray(
        self,
        origin_x: float,
        origin_y: float,
        direction_x: float,
        direction_y: float,
        max_distance: float,
    ) -> list[dict[str, Any]]:
        active_world = self.world
        if active_world is None:
            return []
        resolved_backend = self._physics_backend_registry.resolve(
            active_world,
            default_backend_name=self._physics_backend_name,
        )
        if resolved_backend.backend is None:
            return []
        return resolved_backend.backend.query_ray(
            active_world,
            (origin_x, origin_y),
            (direction_x, direction_y),
            max_distance,
        )

    def refresh_ui_layout(self, viewport_size: Optional[tuple[float, float]] = None) -> bool:
        active_world = self.world
        if self._ui_system is None or active_world is None:
            return False
        target_viewport = viewport_size or (float(self.width), float(self.height))
        self._update_ui_overlay(active_world, target_viewport)
        return True

    def get_ui_entity_screen_rect(
        self,
        entity_name: str,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> Optional[dict[str, float]]:
        if not self.refresh_ui_layout(viewport_size):
            return None
        return self._ui_system.get_entity_screen_rect(entity_name) if self._ui_system is not None else None

    def click_ui_entity(
        self,
        entity_name: str,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> bool:
        active_world = self.world
        if self._ui_system is None or active_world is None:
            return False
        target_viewport = viewport_size or (float(self.width), float(self.height))
        return self._ui_system.click_entity(active_world, entity_name, target_viewport)

    def request_shutdown(self) -> None:
        self.running = False
    
    # === GAME LOOP ===
    
    def run(self) -> None:
        "Inicia el game loop."
        rl.init_window(self.width, self.height, f"{self.title}  —  v{ENGINE_VERSION}")
        rl.set_target_fps(self.target_fps)

        # Comprobación de actualizaciones (no bloquea el arranque)
        from engine.update_checker import start_update_check
        start_update_check()
        # Título de barra oscuro (Windows 11) para coherencia visual con el tema dark
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass
        self._cursor_renderer.hide_system_cursor()
        
        # Aplicar tema Raygui
        apply_unity_dark_theme()
        
        # Crear EditorLayout (necesita ventana Raylib inicializada)
        if self.editor_layout is None:
            self.editor_layout = EditorLayout(self.width, self.height)
            self.editor_layout.terminal_panel = self.terminal_panel
            if self._project_service is not None:
                self._project_workspace_controller.refresh_launcher_projects()
                if self._project_service.has_project:
                    self.editor_layout.project_panel.set_project_service(self._project_service)
                    if getattr(self.editor_layout, "flow_panel", None) is not None:
                        self.editor_layout.flow_panel.set_project_service(self._project_service)
                    if getattr(self.editor_layout, "flow_workspace_panel", None) is not None:
                        self.editor_layout.flow_workspace_panel.set_project_service(self._project_service)
                else:
                    self.editor_layout.show_project_launcher = True
            if self._scene_manager is not None:
                if getattr(self.editor_layout, "flow_panel", None) is not None:
                    self.editor_layout.flow_panel.set_scene_manager(self._scene_manager)
                if getattr(self.editor_layout, "flow_workspace_panel", None) is not None:
                    self.editor_layout.flow_workspace_panel.set_scene_manager(self._scene_manager)
                self.editor_layout.set_scene_tabs(self._scene_manager.list_open_scenes(), self._scene_manager.active_scene_key)
        
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
                    self._cursor_renderer.render(rl.get_mouse_position(), self.editor_layout.get_cursor_intent())
                finally:
                    rl.end_drawing()
                continue
            
            # World activo
            active_world = self.world
            
            terminal_captures_keyboard = (
                self.terminal_panel is not None
                and self.editor_layout is not None
                and self.editor_layout.active_bottom_tab == "TERMINAL"
                and self.terminal_panel.captures_keyboard()
            )
            if not terminal_captures_keyboard:
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

                if self.sprite_editor_modal is None or not self.sprite_editor_modal.is_open:
                    self.editor_layout.update_input()
                    if self.terminal_panel is not None:
                        self.terminal_panel.update_input(self.editor_layout.active_bottom_tab == "TERMINAL")
                    self._persist_editor_preferences()
                if self.animator_panel is not None and active_world is not None:
                    self.animator_panel.update(active_world, dt)
                
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
                
                self._editor_interaction_controller.handle_scene_view_drag_drop(active_world)

            # 2. Gizmos & Selection (Only if interaction enabled)
            selection_gizmo_start = time.perf_counter()
            if enable_scene_interaction:
                self._editor_interaction_controller.handle_selection_and_gizmos(active_world)
            self._perf_stats["selection_gizmo"] = (time.perf_counter() - selection_gizmo_start) * 1000.0

            # Update Animation (Only in Play/Step mode)
            if self._state.allows_gameplay():
                animation_start = time.perf_counter()
                try:
                    self._update_animation(active_world, dt)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"Animation error: {e}")
                self._perf_stats["animation"] = (time.perf_counter() - animation_start) * 1000.0
            
            # Actualización de gameplay (Física, Colisiones, Reglas)
            if self._state.allows_physics() or self._state.allows_gameplay():
                gameplay_start = time.perf_counter()
                try:
                    self._update_gameplay(active_world, dt)
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"Gameplay error: {e}")
                self._perf_stats["gameplay"] = (time.perf_counter() - gameplay_start) * 1000.0

            scripts_start = time.perf_counter()
            if self._state == EngineState.EDIT and active_world is not None and self._script_behaviour_system is not None:
                try:
                    ran_edit_scripts = self._script_behaviour_system.update(active_world, dt, is_edit_mode=True)
                    if ran_edit_scripts and self._scene_manager is not None:
                        self._scene_manager.mark_edit_world_dirty(reason="legacy_authoring")
                except Exception as e:
                    from engine.editor.console_panel import log_err
                    log_err(f"ScriptBehaviour error: {e}")
            self._perf_stats["scripts"] = (time.perf_counter() - scripts_start) * 1000.0

            ui_start = time.perf_counter()
            active_tab = self.editor_layout.active_tab if self.editor_layout is not None else "SCENE"
            if active_world is not None and active_tab in ("SCENE", "GAME"):
                try:
                    self._update_ui_overlay(active_world, self._ui_viewport_size_for_tab(active_tab), active_tab=active_tab)
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
            self._record_profiler_frame(active_world)
        
        self._cleanup()
    
    def _update_animation(self, world: Optional["World"], dt: float) -> None:
        self._runtime_controller.update_animation(world, dt)

    def _update_ui_overlay(
        self,
        world: Optional["World"],
        viewport_size: tuple[float, float],
        *,
        active_tab: Optional[str] = None,
    ) -> None:
        if self._ui_system is None or world is None:
            return
        tab = active_tab or (self.editor_layout.active_tab if self.editor_layout is not None else "GAME")
        if self.editor_layout is not None and tab in ("SCENE", "GAME"):
            mouse = rl.get_mouse_position()
            view_rect = self.editor_layout.get_center_view_rect()
            self._ui_system.inject_pointer_state(
                float(mouse.x - view_rect.x),
                float(mouse.y - view_rect.y),
                bool(rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT)),
                bool(rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)),
                bool(rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT)),
            )
        self._ui_system.update(world, viewport_size, allow_interaction=self._is_runtime_ui_interaction_enabled(active_tab=tab))

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

    def _ui_viewport_size_for_tab(self, active_tab: Optional[str] = None) -> tuple[float, float]:
        tab = active_tab or (self.editor_layout.active_tab if self.editor_layout is not None else "GAME")
        if tab == "SCENE":
            return self._current_scene_viewport_size()
        return self._current_viewport_size()

    def _is_runtime_ui_interaction_enabled(self, *, active_tab: Optional[str] = None) -> bool:
        tab = active_tab or (self.editor_layout.active_tab if self.editor_layout is not None else "GAME")
        if tab != "GAME":
            return False
        return self._state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING)

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
        self._debug_tools_controller.handle_debug_shortcuts(
            step_callback=self.step,
            toggle_fullscreen_callback=self._toggle_fullscreen,
        )
        
        # Ctrl+S: Save
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_S):
            self.save_current_scene()
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_Z):
            self._history_manager.undo()
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_key_pressed(rl.KEY_Y):
            self._history_manager.redo()
            
    def save_current_scene(self) -> None:
        """Guarda la escena actual a disco."""
        self._scene_workflow_controller.save_current_scene()
    
    def _update_gameplay(self, world: "World", dt: float) -> None:
        """Actualiza la lógica del juego (Física, Colisiones, Reglas)."""
        self._runtime_controller.update_gameplay(world, dt)

    def _resolve_physics_backend_name(self, world: Optional["World"]) -> str:
        return self._runtime_controller.resolve_physics_backend_name(world)

    def _refresh_default_physics_backend(self) -> None:
        self._runtime_controller.refresh_default_physics_backend()
            
    def step(self) -> None:
        self._runtime_controller.step()
        
    def save_snapshot(self) -> None:
        """Guarda un snapshot del estado actual."""
        self._debug_tools_controller.save_snapshot()
        
    def load_last_snapshot(self) -> None:
        """Carga el último snapshot guardado."""
        self._debug_tools_controller.load_last_snapshot()
    
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
        self._debug_tools_controller.draw_debug_info()

    def _update_perf_counters(self, active_world: Optional["World"]) -> None:
        self._debug_tools_controller.update_perf_counters(active_world)

    def _approximate_memory_counters(self, active_world: Optional["World"]) -> dict[str, float]:
        return self._debug_tools_controller.approximate_memory_counters(active_world)

    def _record_profiler_frame(self, active_world: Optional["World"], *, frame_time_ms: float | None = None) -> None:
        self._debug_tools_controller.record_profiler_frame(active_world, frame_time_ms=frame_time_ms)

    def _draw_performance_overlay(self) -> None:
        self._debug_tools_controller.draw_performance_overlay()
        
    def _render_frame(self, active_world: "World") -> None:
        """Renderiza un frame completo de la aplicación (Scene, Game, UI)."""
        rl.begin_drawing()
        rl.clear_background(rl.DARKGRAY)
        self._perf_stats["inspector"] = 0.0
        self._perf_stats["hierarchy"] = 0.0
        
        try:
            editor_world = self._scene_manager.get_edit_world() if self._scene_manager is not None else None
            overlay_world = active_world
            if overlay_world is None and editor_world is not None:
                overlay_world = editor_world
            elif self.is_edit_mode and editor_world is not None:
                overlay_world = editor_world
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
                scene_viewport_size = self._current_scene_viewport_size()
                self.editor_layout.begin_scene_camera_pass(draw_grid=True)
                self.editor_layout.end_scene_camera_pass()
                if self._render_system is not None and active_world is not None:
                    self._render_system.render(
                        active_world,
                        override_camera=self.editor_layout.editor_camera,
                        use_world_camera=False,
                        viewport_size=scene_viewport_size,
                        allow_render_targets=False,
                    )

                # Render Gizmos
                if self.gizmo_system is not None and active_world is not None:
                    active_tool = self.editor_layout.active_tool if self.editor_layout else EditorTool.MOVE
                    transform_space = self.editor_layout.transform_space if self.editor_layout else TransformSpace.WORLD
                    pivot_mode = self.editor_layout.pivot_mode if self.editor_layout else PivotMode.PIVOT
                    self.editor_layout.begin_scene_camera_pass()
                    self.gizmo_system.render(active_world, active_tool, transform_space, pivot_mode)
                    self.editor_layout.end_scene_camera_pass()

                self.editor_layout.end_scene_render()
                should_render_scene_ui = bool(
                    self._ui_system is not None
                    and active_world is not None
                    and self._ui_system.should_render_scene_view_ui(
                        active_world,
                        allow_runtime=self._state.allows_gameplay(),
                    )
                )
                if should_render_scene_ui and self.editor_layout.scene_texture is not None:
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
                safe_reset_clip_state()
                try:
                    self.editor_layout.draw_layout(is_playing)
                except Exception as exc:
                    safe_reset_clip_state()
                    log_err(f"Editor layout render error: {exc}")
                    self.editor_layout.draw_bottom_tabs()
            else:
                 # Fallback
                 if self._render_system is not None and active_world is not None:
                    self._render_system.render(active_world)

            # Inspector Render (Overlay on Layout)
            if self._inspector_system is not None and overlay_world is not None:
                if self.editor_layout:
                    safe_reset_clip_state()
                    rect = self.editor_layout.inspector_rect
                    inspector_start = time.perf_counter()
                    try:
                        self._inspector_system.render(
                            overlay_world, 
                            int(rect.x), int(rect.y), 
                            int(rect.width), int(rect.height),
                            is_edit_mode=self.is_edit_mode
                        )
                    except Exception as exc:
                        safe_reset_clip_state()
                        log_err(f"Inspector render error: {exc}")
                    self._perf_stats["inspector"] = (time.perf_counter() - inspector_start) * 1000.0

            if self.animator_panel is not None and active_world is not None and self.editor_layout and self.editor_layout.active_tab == "ANIMATOR":
                safe_reset_clip_state()
                rect = self.editor_layout.get_center_view_rect()
                self.animator_panel.render(
                    active_world,
                    int(rect.x),
                    int(rect.y),
                    int(rect.width),
                    int(rect.height),
                )

            if self.editor_layout is not None and self.editor_layout.active_tab == "FLOW":
                flow_workspace_panel = getattr(self.editor_layout, "flow_workspace_panel", None)
                if flow_workspace_panel is not None:
                    safe_reset_clip_state()
                    rect = self.editor_layout.get_center_view_rect()
                    try:
                        flow_workspace_panel.render(
                            int(rect.x),
                            int(rect.y),
                            int(rect.width),
                            int(rect.height),
                        )
                    except Exception as exc:
                        safe_reset_clip_state()
                        log_err(f"Flow workspace render error: {exc}")

            if self.sprite_editor_modal is not None and self.sprite_editor_modal.is_open:
                self.sprite_editor_modal.render(self.width, self.height)

            self._draw_debug_info()
            self._draw_performance_overlay()
            
            # Hierachy Panel Overlay
            if self.hierarchy_panel is not None and overlay_world is not None:
                safe_reset_clip_state()
                hierarchy_start = time.perf_counter()
                dropdown_open = self.editor_layout.dropdown_active if self.editor_layout else False
                try:
                    if self.editor_layout:
                        rect = self.editor_layout.hierarchy_rect
                        self.hierarchy_panel.render(overlay_world, int(rect.x), int(rect.y), int(rect.width), int(rect.height), input_blocked=dropdown_open)
                    else:
                        self.hierarchy_panel.render(overlay_world, 0, 0, 200, self.height)
                except Exception as exc:
                    safe_reset_clip_state()
                    log_err(f"Hierarchy render error: {exc}")
                self._perf_stats["hierarchy"] = (time.perf_counter() - hierarchy_start) * 1000.0

            # Dropdowns de menú y toolbar — siempre encima de todo (incluyendo hierarchy e inspector)
            if self.editor_layout:
                safe_reset_clip_state()
                self.editor_layout.draw_top_dropdowns()

            try:
                cursor_state = self._editor_interaction_controller.resolve_cursor_state(overlay_world)
                self._cursor_renderer.render(rl.get_mouse_position(), cursor_state)
            except Exception as exc:
                self._cursor_renderer.show_system_cursor()
                log_err(f"Cursor render error: {exc}")

        finally:
            rl.end_drawing()

    def _cleanup(self) -> None:
        self.running = False
        self._cursor_renderer.show_system_cursor()
        if self.terminal_panel is not None:
            self.terminal_panel.shutdown()
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

    def _consume_asset_open_requests(self) -> None:
        if self.editor_layout is not None and self.editor_layout.project_panel is not None:
            if self.editor_layout.project_panel.request_open_sprite_editor_for:
                target_asset = self.editor_layout.project_panel.request_open_sprite_editor_for
                self.editor_layout.project_panel.request_open_sprite_editor_for = None
                self._open_sprite_editor(target_asset)
            if self.editor_layout.project_panel.request_open_scene_for:
                target_scene = self.editor_layout.project_panel.request_open_scene_for
                self.editor_layout.project_panel.request_open_scene_for = None
                self.load_scene_by_path(target_scene)
            for panel_name in ("flow_panel", "flow_workspace_panel"):
                flow_panel = getattr(self.editor_layout, panel_name, None)
                request_open_source = getattr(flow_panel, "request_open_source", None) if flow_panel is not None else None
                if isinstance(request_open_source, dict) and request_open_source:
                    request = dict(request_open_source)
                    flow_panel.request_open_source = None
                    self._open_flow_source(request)
                request_open_target = getattr(flow_panel, "request_open_target", None) if flow_panel is not None else None
                if isinstance(request_open_target, dict) and request_open_target:
                    request = dict(request_open_target)
                    flow_panel.request_open_target = None
                    self._open_flow_target(request)

        if self.animator_panel is not None and self.animator_panel.request_open_sprite_editor_for:
            target_asset = self.animator_panel.request_open_sprite_editor_for
            self.animator_panel.request_open_sprite_editor_for = None
            self._open_sprite_editor(target_asset)

        if self._inspector_system is not None and self._inspector_system.request_open_sprite_editor_for:
            target_asset = self._inspector_system.request_open_sprite_editor_for
            self._inspector_system.request_open_sprite_editor_for = None
            self._open_sprite_editor(target_asset)

    def _open_flow_source(self, request: dict[str, str]) -> None:
        if self._scene_manager is None:
            return
        scene_ref = str(request.get("scene_ref", "") or "").strip()
        entity_name = str(request.get("entity_name", "") or "").strip()
        if not scene_ref:
            return
        opened = self.activate_scene_workspace_tab(scene_ref)
        if not opened and scene_ref.endswith(".json"):
            opened = self.load_scene_by_path(scene_ref)
        if not opened:
            return
        if entity_name and not self._scene_manager.set_selected_entity(entity_name):
            log_warn(f"Scene Flow: entity '{entity_name}' was not found after opening '{scene_ref}'")

    def _open_flow_target(self, request: dict[str, str]) -> None:
        scene_ref = str(request.get("scene_ref", "") or "").strip()
        if not scene_ref:
            return
        opened = self.activate_scene_workspace_tab(scene_ref)
        if not opened and scene_ref.endswith(".json"):
            self.load_scene_by_path(scene_ref)

    def _resolve_default_ui_parent(self, active_world: Optional["World"]) -> Optional[str]:
        if active_world is None:
            return None
        if active_world.selected_entity_name:
            return active_world.selected_entity_name
        for entity in active_world.get_all_entities():
            if entity.has_component(Canvas):
                return entity.name
        return None

    def _handle_local_ui_authoring_requests(self, default_ui_parent: Optional[str]) -> None:
        if self.editor_layout is None or self._scene_manager is None:
            return

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
    
    def _process_ui_requests(self) -> None:
        """Procesa peticiones de UI (Escenas, Menús de archivo)."""
        if self._scene_manager is None:
            return

        self._consume_asset_open_requests()

        if self.editor_layout is None:
            return

        self._scene_workflow_controller.handle_scene_tab_requests()
        should_exit_launcher = self._project_workspace_controller.handle_project_launcher_requests()
        if should_exit_launcher:
            return

        active_world = self.world
        default_ui_parent = self._resolve_default_ui_parent(active_world)

        self._handle_local_ui_authoring_requests(default_ui_parent)
        self._project_workspace_controller.handle_project_switch_requests()
        self._scene_workflow_controller.handle_scene_ui_requests()

        # EXIT
        if self.editor_layout.request_exit:
            self.editor_layout.request_exit = False
            self.running = False
            return

        # UNDO / REDO
        if self.editor_layout.request_undo:
            self.editor_layout.request_undo = False
            self.undo()

        if self.editor_layout.request_redo:
            self.editor_layout.request_redo = False
            self.redo()

        # DUPLICATE ENTITY
        if self.editor_layout.request_duplicate_entity:
            self.editor_layout.request_duplicate_entity = False
            active_world = self.world
            if active_world is not None and active_world.selected_entity_name:
                self._scene_manager.duplicate_entity_subtree(active_world.selected_entity_name)

        # DELETE ENTITY
        if self.editor_layout.request_delete_entity:
            self.editor_layout.request_delete_entity = False
            active_world = self.world
            if active_world is not None and active_world.selected_entity_name:
                self._scene_manager.remove_entity(active_world.selected_entity_name)

        # CREATE EMPTY ENTITY
        if self.editor_layout.request_create_entity:
            self.editor_layout.request_create_entity = False
            from engine.components.transform import Transform
            active_world = self.world
            if active_world is not None:
                name = "New Entity"
                base = name
                idx = 1
                while active_world.get_entity(name) is not None:
                    name = f"{base} ({idx})"
                    idx += 1
                if self._scene_manager is not None:
                    self._scene_manager.create_entity(name, components={"Transform": {}})
                    self._scene_manager.set_selected_entity(name)
                else:
                    e = active_world.create_entity(name)
                    e.add_component(Transform())
                    active_world.selected_entity_name = name
