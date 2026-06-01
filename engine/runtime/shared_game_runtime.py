"""Shared Game/RuntimeController runtime used by exported games."""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from engine.app.runtime_system_factory import RuntimeSystemBundle, create_runtime_system_bundle
from engine.core.engine_state import EngineState
from engine.core.game import Game
from engine.levels.component_registry import ComponentRegistry
from engine.runtime.content_loader import ContentLoader
from engine.runtime.runtime_project_service import RuntimeProjectService
from engine.scenes.scene_manager import SceneManager

if TYPE_CHECKING:
    from engine.systems.physics_system import PhysicsSystem
    from engine.systems.render_system import RenderSystem


class SharedGameRuntime:
    """Export runtime facade backed by the same Game + RuntimeController path as editor PLAY."""

    def __init__(
        self,
        loader: ContentLoader,
        registry: ComponentRegistry,
        *,
        window_config: dict[str, Any] | None = None,
        gravity: float = 600.0,
        render_system: "RenderSystem | None" = None,
    ) -> None:
        self._loader = loader
        self._registry = registry
        self._project_service = RuntimeProjectService(loader.base_path)
        self._window_config = dict(window_config or {})
        self._frame_count = 0
        self._active = True
        self._current_scene_path = ""
        self._current_scene_data: dict[str, Any] | None = None
        self.systems: RuntimeSystemBundle = create_runtime_system_bundle(gravity=gravity)

        width = int(self._window_config.get("width", 1280))
        height = int(self._window_config.get("height", 720))
        self.game = Game(
            title="Exported Game",
            width=width,
            height=height,
            target_fps=60,
            editor_enabled=False,
            hot_reload_enabled=False,
        )
        self.scene_manager = SceneManager(registry)
        self.event_bus = self.systems.event_bus
        self.rule_system = self.systems.rule_system

        self._configure_game_systems(render_system=render_system)
        self.game.configure_external_scene_loader(self.load_scene, self.load_scene_flow_target)
        self.game._scene_transition_controller.set_external_scene_source(  # runtime wiring, no editor dependency
            self._resolve_scene_reference,
            self._load_scene_payload,
        )

    @property
    def world(self) -> Any:
        return self.game.world

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def current_scene_path(self) -> str | None:
        return self._current_scene_path or None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def resource_preloader_system(self) -> Any:
        return self.systems.resource_preloader_system

    @property
    def render_system(self) -> Any:
        return self.game.render_system

    @property
    def ui_system(self) -> Any:
        return self.game._ui_system

    def _configure_game_systems(self, *, render_system: RenderSystem | None) -> None:
        if render_system is not None:
            self.systems.render_system = render_system
        self.systems.install(
            self.game,
            project_service=self._project_service,
            scene_manager=self.scene_manager,
        )
        self._register_optional_box2d_backend(self.systems.physics_system)

    def _register_optional_box2d_backend(self, physics_system: PhysicsSystem) -> None:
        from engine.physics.box2d_backend import Box2DDependencyUnavailable, Box2DPhysicsBackend

        try:
            backend = Box2DPhysicsBackend(gravity=physics_system.gravity, event_bus=self.event_bus)
            self.game.set_physics_backend(backend, backend_name="box2d")
        except Box2DDependencyUnavailable as exc:
            self.game.set_physics_backend_unavailable("box2d", str(exc))
        except Exception as exc:
            self.game.set_physics_backend_unavailable("box2d", str(exc))

    def setup_scripts_path(self, scripts_dir: str | None = None) -> None:
        candidates: list[Path] = []
        if scripts_dir is not None:
            candidates.append(Path(scripts_dir))
        else:
            packed_scripts = self._project_service.extract_packed_scripts()
            if packed_scripts is not None:
                candidates.append(packed_scripts)
            base_path = Path(self._loader.base_path)
            candidates.extend(
                [
                    base_path / "content" / "scripts",
                    base_path / "scripts",
                    base_path,
                ]
            )

        for candidate in reversed(candidates):
            if scripts_dir is None and not candidate.exists():
                continue
            scripts_path = str(candidate.resolve())
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)

    def load_scene(self, scene_path: str, *, enter_play: bool = True) -> bool:
        resolved_scene_path = self._resolve_scene_reference(scene_path, self._current_scene_path or None)
        if not resolved_scene_path:
            print(f"[ExportRuntime] Scene not found: {scene_path}", file=sys.stderr)
            return False
        scene_data = self._load_scene_payload(resolved_scene_path)
        if scene_data is None:
            print(f"[ExportRuntime] Scene not found: {scene_path}", file=sys.stderr)
            return False
        try:
            if not self.game.load_scene_from_data(resolved_scene_path, scene_data, enter_play=enter_play):
                return False
            self._current_scene_path = resolved_scene_path
            self._current_scene_data = scene_data
            self._frame_count = 0
            return True
        except Exception as exc:
            print(f"[ExportRuntime] Failed to load scene: {exc}", file=sys.stderr)
            return False

    def load_scene_flow_target(self, target: str) -> bool:
        scene_data = self._current_scene_data
        if scene_data is None and self.scene_manager.current_scene is not None:
            scene_data = self.scene_manager.current_scene.to_dict()
        if not isinstance(scene_data, dict):
            print(f"[ExportRuntime] No current scene data for scene flow target: {target}", file=sys.stderr)
            return False
        metadata = scene_data.get("feature_metadata", {})
        scene_flow = metadata.get("scene_flow", {}) if isinstance(metadata, dict) else {}
        if not isinstance(scene_flow, dict):
            scene_flow = {}
        path = scene_flow.get(target)
        if not path:
            print(f"[ExportRuntime] Scene flow target not found: {target}", file=sys.stderr)
            return False
        return self.load_scene(str(path))

    def run_frame(self, dt: float = 1.0 / 60.0, pointer_state: dict[str, Any] | None = None) -> None:
        if not self._active or self.world is None:
            return
        self.game.step_runtime_frame(dt, self._viewport_size(), pointer_state=pointer_state)
        self._frame_count += 1

    def play_runtime(self, *, preload_resources: bool = True) -> None:
        if self.game._runtime_controller is not None:
            self.game._runtime_controller.play(preload_resources=preload_resources)

    def render(self, viewport_size: tuple[float, float] | None = None) -> None:
        self.game.render_runtime_frame(viewport_size or self._viewport_size())

    def inject_input(self, entity_name: str, state: dict[str, float], frames: int = 1) -> None:
        input_system = self.game.input_system
        if input_system is not None:
            input_system.inject_state(entity_name, state, frames)

    def inject_pointer_state(
        self,
        x: float,
        y: float,
        *,
        down: bool = False,
        pressed: bool = False,
        released: bool = False,
        frames: int = 1,
    ) -> None:
        if self.game._ui_system is not None:
            self.game._ui_system.inject_pointer_state(x, y, down, pressed, released, frames)

    def update_ui(
        self,
        viewport_size: tuple[float, float],
        *,
        mouse_x: float = 0.0,
        mouse_y: float = 0.0,
        mouse_down: bool = False,
        mouse_pressed: bool = False,
        mouse_released: bool = False,
    ) -> None:
        if self.world is None or self.game._ui_system is None:
            return
        self.game._ui_system.inject_pointer_state(
            mouse_x,
            mouse_y,
            down=mouse_down,
            pressed=mouse_pressed,
            released=mouse_released,
        )
        self.game._ui_system.update(self.world, viewport_size, allow_interaction=True)

    def render_ui(self) -> None:
        if self.world is None or self.game._ui_system is None or self.game._ui_render_system is None:
            return
        self.game._ui_render_system.render(self.world, self.game._ui_system)

    def get_events(self, count: int = 10) -> list[Any]:
        return self.event_bus.get_recent_events(count)

    def get_recent_events(self, count: int = 10) -> list[dict[str, Any]]:
        return [{"name": event.name, "data": event.data} for event in self.event_bus.get_recent_events(count)]

    def shutdown(self) -> None:
        self._active = False
        if self.game.state in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
            self.game.stop()
        self.event_bus.emit("runtime_shutdown", {})
        self._project_service.cleanup()

    def _viewport_size(self) -> tuple[float, float]:
        return (
            float(self._window_config.get("width", self.game.width)),
            float(self._window_config.get("height", self.game.height)),
        )

    def _load_scene_payload(self, scene_path: str) -> dict[str, Any] | None:
        return self._loader.load_scene_json(scene_path)

    def _resolve_scene_reference(self, scene_path: str, source_scene_path: str | None = None) -> str | None:
        normalized = str(scene_path or "").strip().replace("\\", "/")
        if not normalized:
            return None
        if self._loader.load_scene_json(normalized) is not None:
            return normalized
        source = str(source_scene_path or "").strip().replace("\\", "/")
        if source:
            source_dir = PurePosixPath(source).parent
            candidates = [
                (source_dir / normalized).as_posix(),
                (source_dir.parent / normalized).as_posix(),
            ]
            for candidate in candidates:
                if self._loader.load_scene_json(candidate) is not None:
                    return candidate
        return None
