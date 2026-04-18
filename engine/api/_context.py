from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

from engine.api._contracts import EngineAPIContracts, EngineRuntimePort
from engine.api.errors import EntityNotFoundError
from engine.api.types import ActionResult
from engine.components.renderorder2d import RenderOrder2D
from engine.scenes.contracts import SceneAuthoringPort, SceneWorkspacePort

if TYPE_CHECKING:
    from engine.api.engine_api import EngineAPI
    from engine.assets.asset_service import AssetService
    from engine.ecs.entity import Entity
    from engine.project.project_service import ProjectService
    from engine.scenes.scene_manager import SceneManager


class EngineAPIContext:
    """Shared runtime context for internal EngineAPI collaborators."""

    def __init__(self, api: "EngineAPI") -> None:
        self.api = api

    @property
    def game(self) -> Any:
        return self.api.game

    @property
    def contracts(self) -> EngineAPIContracts:
        contracts = getattr(self.api, "_contracts", None)
        if contracts is None:
            return self.api._refresh_contracts()
        return contracts

    @property
    def runtime(self) -> Optional[EngineRuntimePort]:
        game = self.api.game
        if game is None:
            return None
        runtime = self.contracts.runtime
        if runtime is game:
            return runtime
        return cast(EngineRuntimePort, game)

    @property
    def scene_manager(self) -> Optional["SceneManager"]:
        return self.api.scene_manager

    @property
    def scene_authoring(self) -> Optional[SceneAuthoringPort]:
        scene_manager = self.api.scene_manager
        if scene_manager is None:
            return None
        authoring = self.contracts.scene_authoring
        if authoring is not None:
            return authoring
        return scene_manager.authoring_port

    @property
    def scene_workspace(self) -> Optional[SceneWorkspacePort]:
        scene_manager = self.api.scene_manager
        if scene_manager is None:
            return None
        workspace = self.contracts.scene_workspace
        if workspace is not None:
            return workspace
        return scene_manager.workspace_port

    @property
    def project_service(self) -> Optional["ProjectService"]:
        return self.contracts.project_service

    @property
    def asset_service(self) -> Optional["AssetService"]:
        return self.contracts.asset_service

    @property
    def project_root(self) -> str:
        return self.api._project_root

    @property
    def global_state_dir(self) -> str | None:
        return self.api._global_state_dir

    @property
    def sandbox_paths(self) -> bool:
        return self.api._sandbox_paths

    def ok(self, message: str, data: Any = None) -> ActionResult:
        return self.api._ok(message, data)

    def fail(self, message: str) -> ActionResult:
        return self.api._fail(message)

    def ensure_edit_mode(self) -> None:
        self.api._ensure_edit_mode()

    def resolve_api_path(self, path: str | Path, *, purpose: str) -> Path:
        return self.api._resolve_api_path(path, purpose=purpose)

    def resolve_scene_reference(self, key_or_path: str) -> str:
        return self.api._resolve_scene_reference(key_or_path)

    def require_entity(self, name: str) -> "Entity":
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            raise RuntimeError("No world loaded")
        entity = runtime.world.get_entity_by_name(name)
        if entity is None:
            raise EntityNotFoundError(f"Entity '{name}' not found")
        return entity

    def load_component_payload(self, entity_name: str, component_name: str) -> Optional[dict[str, Any]]:
        authoring = self.scene_authoring
        if authoring is None:
            return None
        return authoring.get_component_data(entity_name, component_name)

    def normalize_sorting_layers(self, order: list[str]) -> list[str]:
        normalized: list[str] = ["Default"]
        seen = {"Default"}
        for entry in order:
            layer_name = str(entry).strip()
            if not layer_name or layer_name in seen:
                continue
            seen.add(layer_name)
            normalized.append(layer_name)
        return normalized

    def clamp_render_order(self, value: int) -> int:
        return max(RenderOrder2D.MIN_ORDER_IN_LAYER, min(RenderOrder2D.MAX_ORDER_IN_LAYER, int(value)))


class EngineAPIComponent:
    """Base helper for private EngineAPI domain collaborators."""

    def __init__(self, context: EngineAPIContext) -> None:
        self._context = context

    @property
    def api(self) -> "EngineAPI":
        return self._context.api

    @property
    def game(self) -> Any:
        return self._context.game

    @property
    def contracts(self) -> EngineAPIContracts:
        return self._context.contracts

    @property
    def runtime(self) -> Optional[EngineRuntimePort]:
        return self._context.runtime

    @property
    def scene_manager(self) -> Optional["SceneManager"]:
        return self._context.scene_manager

    @property
    def scene_authoring(self) -> Optional[SceneAuthoringPort]:
        return self._context.scene_authoring

    @property
    def scene_workspace(self) -> Optional[SceneWorkspacePort]:
        return self._context.scene_workspace

    @property
    def project_service(self) -> Optional["ProjectService"]:
        return self._context.project_service

    @property
    def asset_service(self) -> Optional["AssetService"]:
        return self._context.asset_service

    def ok(self, message: str, data: Any = None) -> ActionResult:
        return self._context.ok(message, data)

    def fail(self, message: str) -> ActionResult:
        return self._context.fail(message)

    def ensure_edit_mode(self) -> None:
        self._context.ensure_edit_mode()

    def resolve_api_path(self, path: str | Path, *, purpose: str) -> Path:
        return self._context.resolve_api_path(path, purpose=purpose)

    def resolve_scene_reference(self, key_or_path: str) -> str:
        return self._context.resolve_scene_reference(key_or_path)

    def require_entity(self, name: str):
        return self._context.require_entity(name)

    def load_component_payload(self, entity_name: str, component_name: str) -> Optional[dict[str, Any]]:
        return self._context.load_component_payload(entity_name, component_name)

    def normalize_sorting_layers(self, order: list[str]) -> list[str]:
        return self._context.normalize_sorting_layers(order)

    def clamp_render_order(self, value: int) -> int:
        return self._context.clamp_render_order(value)
