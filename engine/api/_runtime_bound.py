from __future__ import annotations

from typing import Any

from engine.api._context import EngineAPIContext
from engine.levels.component_registry import create_default_registry


def create_runtime_bound_engine_api(
    engine_api_cls: type,
    *,
    game: Any,
    scene_manager: Any,
    project_service: Any,
) -> Any:
    """Create an EngineAPI facade for internal editor/tooling over live runtime state."""

    from engine.assets.asset_service import AssetService

    api = engine_api_cls.__new__(engine_api_cls)
    api.game = game
    api.scene_manager = scene_manager
    api.project_service = project_service
    api.asset_service = AssetService(project_service)
    api._registry = getattr(scene_manager, "_registry", create_default_registry())
    api._project_root = project_service.project_root.as_posix()
    api._global_state_dir = getattr(project_service, "global_state_dir", None)
    api._sandbox_paths = False
    api._auto_ensure_project = False
    api._read_only = bool(getattr(project_service, "read_only", False))
    api._context = EngineAPIContext(api)
    api._contracts = None
    api._initialize_collaborators()
    api._refresh_contracts()
    return api
