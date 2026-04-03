"""
engine/api/engine_api.py - Fachada publica del motor
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from engine.api._assets_project_api import AssetsProjectAPI
from engine.api._authoring_api import AuthoringAPI
from engine.api._context import EngineAPIContext
from engine.api._debug_api import DebugAPI
from engine.api._runtime_api import RuntimeAPI
from engine.api._scene_workspace_api import SceneWorkspaceAPI
from engine.api._ui_api import UIAPI
from engine.api.errors import InvalidOperationError
from engine.api.types import ActionResult
from engine.events.event_bus import EventBus
from engine.levels.component_registry import create_default_registry
from engine.physics.box2d_backend import Box2DPhysicsBackend
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager

if TYPE_CHECKING:
    from cli.headless_game import HeadlessGame
    from engine.assets.asset_service import AssetService


class EngineAPI:
    """
    API publica para controlar el motor y editar el contenido sin usar internals.
    """

    def __init__(
        self,
        project_root: str | None = None,
        global_state_dir: str | None = None,
        sandbox_paths: bool = False,
    ) -> None:
        self.game: Optional[HeadlessGame] = None
        self.scene_manager: Optional[SceneManager] = None
        self.project_service: Optional[ProjectService] = None
        self.asset_service: Optional[AssetService] = None
        self._registry = create_default_registry()
        self._project_root = project_root or os.getcwd()
        self._global_state_dir = global_state_dir
        self._sandbox_paths = bool(sandbox_paths)
        self._context = EngineAPIContext(self)
        self._initialize_engine()
        self._initialize_collaborators()

    def _initialize_engine(self) -> None:
        from cli.headless_game import HeadlessGame
        from engine.assets.asset_service import AssetService
        from engine.inspector.inspector_system import InspectorSystem
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

        self.game = HeadlessGame()
        self.scene_manager = SceneManager(self._registry)
        self.project_service = ProjectService(self._project_root, global_state_dir=self._global_state_dir)
        self.asset_service = AssetService(self.project_service)

        event_bus = EventBus()  # type: ignore
        self.game.set_scene_manager(self.scene_manager)
        self.game.set_project_service(self.project_service)
        self.game.set_render_system(RenderSystem())
        self.game.set_physics_system(PhysicsSystem(gravity=600))
        self.game.set_collision_system(CollisionSystem(event_bus))
        self.game.set_animation_system(AnimationSystem(event_bus))
        self.game.set_inspector_system(InspectorSystem())
        self.game.set_selection_system(SelectionSystem())
        self.game.set_event_bus(event_bus)
        self.game.set_input_system(InputSystem())
        self.game.set_character_controller_system(CharacterControllerSystem())
        self.game.set_player_controller_system(PlayerControllerSystem())
        self.game.set_script_behaviour_system(ScriptBehaviourSystem())
        self.game.set_audio_system(AudioSystem())
        self.game.set_ui_system(UISystem())
        self.game.set_ui_render_system(UIRenderSystem())
        self._register_optional_box2d_backend()

    def _initialize_collaborators(self) -> None:
        self._runtime_api = RuntimeAPI(self._context)
        self._authoring_api = AuthoringAPI(self._context)
        self._scene_workspace_api = SceneWorkspaceAPI(self._context)
        self._assets_project_api = AssetsProjectAPI(self._context)
        self._debug_api = DebugAPI(self._context)
        self._ui_api = UIAPI(self._context)
        self._delegates = (
            self._runtime_api,
            self._debug_api,
            self._authoring_api,
            self._scene_workspace_api,
            self._assets_project_api,
            self._ui_api,
        )

    def _register_optional_box2d_backend(self) -> None:
        if self.game is None or self.game.physics_system is None or self.game.event_bus is None:
            return
        try:
            self.game.set_physics_backend(
                Box2DPhysicsBackend(gravity=self.game.physics_system.gravity, event_bus=self.game.event_bus),
                backend_name="box2d",
            )
        except Exception as exc:
            self.game.set_physics_backend_unavailable("box2d", str(exc))
            print(f"[WARNING] Box2D backend unavailable: {exc}")

    def attach_runtime(self, game: Any, scene_manager: SceneManager, project_service: ProjectService) -> None:
        from engine.assets.asset_service import AssetService

        self.game = game
        self.scene_manager = scene_manager
        self.project_service = project_service
        self.asset_service = AssetService(project_service)
        if hasattr(self.game, "set_project_service"):
            self.game.set_project_service(project_service)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        for delegate in getattr(self, "_delegates", ()):
            if hasattr(delegate, name):
                return getattr(delegate, name)
        raise AttributeError(f"{type(self).__name__!s} object has no attribute {name!r}")

    def __dir__(self) -> list[str]:
        names = set(super().__dir__())
        for delegate in getattr(self, "_delegates", ()):
            names.update(name for name in dir(delegate) if not name.startswith("_"))
        return sorted(names)

    def _ensure_edit_mode(self) -> None:
        if self.game is not None and not self.game.is_edit_mode:
            raise InvalidOperationError("Cannot edit in PLAY mode")

    def _ok(self, message: str, data: Any = None) -> ActionResult:
        return {"success": True, "message": message, "data": data}

    def _fail(self, message: str) -> ActionResult:
        return {"success": False, "message": message, "data": None}

    def _resolve_scene_reference(self, key_or_path: str) -> str:
        if not key_or_path:
            return ""
        value = str(key_or_path)
        if self.project_service is None:
            return value
        if value.endswith(".json") or "/" in value or "\\" in value:
            return self.project_service.resolve_path(value).as_posix()
        return value

    def _resolve_api_path(self, path: str | os.PathLike[str], *, purpose: str) -> Path:
        candidate = Path(path)
        if self.project_service is not None:
            resolved = self.project_service.resolve_path(candidate)
            project_root = self.project_service.project_root
        else:
            resolved = candidate.expanduser().resolve()
            project_root = Path(self._project_root).resolve()
        if not self._sandbox_paths:
            return resolved
        try:
            resolved.relative_to(project_root)
        except ValueError as exc:
            raise InvalidOperationError(f"Sandbox blocked path outside project root during {purpose}: {resolved.as_posix()}") from exc
        return resolved
