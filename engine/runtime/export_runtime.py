"""Export runtime: centraliza carga de escenas, World, sistemas y game loop para export.

No usa EngineAPI, Game, RuntimeController, ni módulos de editor/inspector.
No persiste mutaciones runtime como authoring state.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.levels.component_registry import ComponentRegistry
from engine.runtime.content_loader import ContentLoader
from engine.runtime.runtime_project_service import RuntimeProjectService
from engine.scenes.scene import Scene
from engine.systems.animation_system import AnimationSystem
from engine.systems.character_controller_system import CharacterControllerSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.input_system import InputSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.render_system import RenderSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.systems.ui_render_system import UIRenderSystem
from engine.systems.ui_system import UISystem


class ExportRuntime:
    """Runtime exportable que carga escenas, crea Worlds y ejecuta game loop."""

    def __init__(
        self,
        loader: ContentLoader,
        registry: ComponentRegistry,
        *,
        window_config: dict[str, Any] | None = None,
        gravity: float = 600.0,
        render_system: RenderSystem | None = None,
    ) -> None:
        self._loader = loader
        self._registry = registry
        self._window_config = window_config or {}
        self._gravity = gravity
        self._world: World | None = None
        self._event_bus = EventBus()
        self._physics = PhysicsSystem(gravity=gravity)
        self._collision = CollisionSystem(event_bus=self._event_bus)
        self._input = InputSystem()
        self._animation = AnimationSystem(event_bus=self._event_bus)
        self._character_controller = CharacterControllerSystem()
        if self._event_bus is not None and hasattr(self._character_controller, "set_event_bus"):
            self._character_controller.set_event_bus(self._event_bus)
        self._player_controller = PlayerControllerSystem()
        if render_system is not None:
            self._render = render_system
        else:
            self._render = RenderSystem()
            if loader is not None:
                project_service = RuntimeProjectService(loader.base_path)
                self._project_service = project_service
                self._render._project_service = project_service  # type: ignore[assignment]  # duck-typing: set directly to skip AssetService
        # UI systems
        self._ui_system = UISystem()
        self._ui_system.set_event_bus(self._event_bus)
        self._ui_system.set_scene_loader(self.load_scene)
        self._ui_system.set_runtime_scene_loader(self.load_scene)
        # Scene flow and transition runners set to None for now (scripts Phase 7)
        self._ui_render = UIRenderSystem()
        if hasattr(self, '_project_service'):
            self._ui_render.set_project_service(self._project_service)
        elif loader is not None:
            project_service = RuntimeProjectService(loader.base_path)
            self._project_service = project_service
            self._ui_render.set_project_service(self._project_service)
        # Script behaviour system (no hot-reload in export)
        self._script_behaviour = ScriptBehaviourSystem()
        # Set scene_flow_loader to None for now — scripts can use context.load_scene_flow_target
        self._script_behaviour.set_scene_flow_loader(None)
        # Don't set hot_reload_manager — it stays None, and _load_module will use importlib fallback
        self._pointer_state: dict[str, Any] | None = None
        self._current_scene_path: str | None = None
        self._frame_count: int = 0
        self._active: bool = True

    # ── properties ──────────────────────────────────────────────

    @property
    def world(self) -> World | None:
        return self._world

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def current_scene_path(self) -> str | None:
        return self._current_scene_path

    @property
    def active(self) -> bool:
        return self._active

    @property
    def render_system(self) -> Any:
        return self._render

    @property
    def ui_system(self) -> Any:
        return self._ui_system

    # ── scene loading ───────────────────────────────────────────

    def load_scene(self, scene_path: str) -> bool:
        """Carga una escena desde el content pack y crea un World nuevo."""
        scene_data = self._loader.load_scene_json(scene_path)
        if scene_data is None:
            print(f"[ExportRuntime] Scene not found: {scene_path}", file=sys.stderr)
            return False

        scene = Scene(name=scene_path, data=scene_data, source_path=scene_path)
        try:
            self._world = scene.create_world(self._registry)
            self._current_scene_path = scene_path
            self._frame_count = 0
            self._event_bus.reset_frame_dedup()
            self._event_bus.emit("scene_loaded", {"scene_path": scene_path})
            self._script_behaviour.on_play(self._world)
            return True
        except Exception as exc:
            print(f"[ExportRuntime] Failed to create world: {exc}", file=sys.stderr)
            return False

    # ── game loop ───────────────────────────────────────────────

    def run_frame(self, dt: float = 1.0 / 60.0) -> None:
        """Ejecuta un frame de simulación con todos los sistemas canónicos."""
        if not self._active or self._world is None:
            return
        self._event_bus.reset_frame_dedup()
        # Input → scripts → physics-driven controllers → physics → collisions → animation
        self._input.update(self._world)
        self._character_controller.update(self._world, dt, backend=None)
        self._player_controller.update(self._world)
        self._script_behaviour.update(self._world, dt, is_edit_mode=False)
        self._physics.update(self._world, dt)
        self._collision.update(self._world)
        self._animation.update(self._world, dt)
        self._frame_count += 1

    def render(self, viewport_size: tuple[float, float] | None = None) -> None:
        """Render the current world using RenderSystem."""
        if self._world is None or self._render is None:
            return
        if viewport_size is None:
            viewport_size = (
                float(self._window_config.get("width", 1280)),
                float(self._window_config.get("height", 720)),
            )
        self._render.render(self._world, viewport_size=viewport_size)

    # ── input injection (testing / headless) ─────────────────────

    def inject_input(self, entity_name: str, state: dict[str, float], frames: int = 1) -> None:
        """Inyecta estado de input para testing/headless."""
        self._input.inject_state(entity_name, state, frames)

    def inject_pointer_state(
        self, x: float, y: float, *,
        down: bool = False, pressed: bool = False, released: bool = False,
        frames: int = 1,
    ) -> None:
        """Inyecta estado de puntero para testing."""
        self._pointer_state = {
            "x": x, "y": y,
            "down": down, "pressed": pressed, "released": released,
            "frames": frames,
        }

    # ── events ──────────────────────────────────────────────────

    def get_events(self, count: int = 10) -> list[Any]:
        """Devuelve eventos recientes del EventBus."""
        return self._event_bus.get_recent_events(count)

    def get_recent_events(self, count: int = 10) -> list[dict[str, Any]]:
        """Versión JSON-serializable de eventos recientes."""
        events = self._event_bus.get_recent_events(count)
        return [{"name": e.name, "data": e.data} for e in events]

    # ── lifecycle ───────────────────────────────────────────────

    # ── UI ─────────────────────────────────────────────────────

    def update_ui(
        self, viewport_size: tuple[float, float], *,
        mouse_x: float = 0.0, mouse_y: float = 0.0,
        mouse_down: bool = False, mouse_pressed: bool = False,
        mouse_released: bool = False,
    ) -> None:
        """Update UI system with real or injected mouse input."""
        if self._world is None:
            return
        self._ui_system.inject_pointer_state(
            mouse_x, mouse_y,
            down=mouse_down, pressed=mouse_pressed, released=mouse_released,
        )
        self._ui_system.update(self._world, viewport_size, allow_interaction=True)

    def render_ui(self) -> None:
        """Render UI overlay on top of the world."""
        if self._world is None:
            return
        self._ui_render.render(self._world, self._ui_system)

    def setup_scripts_path(self, scripts_dir: str | None = None) -> None:
        """Add scripts directory to sys.path so script modules are importable."""
        if scripts_dir is None:
            scripts_dir = str(self._loader.base_path)
        scripts_path = str(Path(scripts_dir))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

    def shutdown(self) -> None:
        """Apaga el runtime sin persistir estado."""
        self._active = False
        self._event_bus.emit("runtime_shutdown", {})
