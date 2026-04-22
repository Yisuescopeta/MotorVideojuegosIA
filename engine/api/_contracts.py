from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Protocol, cast

from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection
from engine.scenes.contracts import SceneAuthoringPort, SceneWorkspacePort

if TYPE_CHECKING:
    from engine.api.engine_api import EngineAPI
    from engine.assets.asset_service import AssetService
    from engine.ecs.world import World
    from engine.project.project_service import ProjectService


class EngineRuntimePort(Protocol):
    @property
    def world(self) -> Optional["World"]:
        ...

    @property
    def state(self) -> Any:
        ...

    @property
    def time(self) -> Any:
        ...

    @property
    def random_seed(self) -> int | None:
        ...

    @property
    def event_bus(self) -> Any:
        ...

    @property
    def input_system(self) -> Any:
        ...

    @property
    def audio_system(self) -> Any:
        ...

    @property
    def render_system(self) -> Any:
        ...

    @property
    def width(self) -> int:
        ...

    @property
    def height(self) -> int:
        ...

    @property
    def current_scene_path(self) -> str:
        ...

    @current_scene_path.setter
    def current_scene_path(self, value: str) -> None:
        ...

    @property
    def debug_draw_colliders(self) -> bool:
        ...

    @debug_draw_colliders.setter
    def debug_draw_colliders(self, value: bool) -> None:
        ...

    @property
    def debug_draw_labels(self) -> bool:
        ...

    @debug_draw_labels.setter
    def debug_draw_labels(self, value: bool) -> None:
        ...

    def play(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def set_seed(self, seed: int | None) -> None:
        ...

    def undo(self) -> bool:
        ...

    def redo(self) -> bool:
        ...

    def step(self) -> None:
        ...

    def step_frame(self, dt: float = 1.0 / 60.0) -> None:
        ...

    def reset_profiler(self, run_label: str = "default") -> None:
        ...

    def get_profiler_report(self) -> dict[str, Any]:
        ...

    def activate_scene_workspace_tab(self, key_or_path: str) -> bool:
        ...

    def close_scene_workspace_tab(self, key_or_path: str, discard_changes: bool = False) -> bool:
        ...

    def sync_scene_workspace(self, apply_view_state: bool = False) -> None:
        ...

    def load_scene_by_path(self, path: str) -> bool:
        ...

    def create_scene(self, scene_name: str) -> bool:
        ...

    def load_scene_flow_target(self, key: str) -> bool:
        ...

    def knows_physics_backend(self, backend_name: str) -> bool:
        ...

    def refresh_runtime_physics_backend(self) -> None:
        ...

    def query_physics_aabb(self, left: float, top: float, right: float, bottom: float) -> list[dict[str, Any]]:
        ...

    def query_physics_ray(
        self,
        origin_x: float,
        origin_y: float,
        direction_x: float,
        direction_y: float,
        max_distance: float,
    ) -> list[dict[str, Any]]:
        ...

    def list_physics_backends(self) -> list[PhysicsBackendInfo]:
        ...

    def get_physics_backend_selection(self, world: Optional["World"] = None) -> PhysicsBackendSelection:
        ...

    def get_ui_entity_screen_rect(
        self,
        entity_name: str,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> Optional[dict[str, float]]:
        ...

    def click_ui_entity(
        self,
        entity_name: str,
        viewport_size: Optional[tuple[float, float]] = None,
    ) -> bool:
        ...

    def set_world(self, world: "World") -> None:
        ...

    @property
    def signal_runtime(self) -> Any:
        ...

    @property
    def callable_resolver(self) -> Any:
        ...

    @property
    def group_operations(self) -> Any:
        ...

    @property
    def servicios(self) -> Any:
        ...

    def request_shutdown(self) -> None:
        ...


@dataclass(frozen=True)
class EngineAPIContracts:
    runtime: Optional[EngineRuntimePort]
    scene_authoring: Optional[SceneAuthoringPort]
    scene_workspace: Optional[SceneWorkspacePort]
    project_service: Optional["ProjectService"]
    asset_service: Optional["AssetService"]


def build_engine_api_contracts(api: "EngineAPI") -> EngineAPIContracts:
    scene_manager = api.scene_manager
    return EngineAPIContracts(
        runtime=cast(Optional[EngineRuntimePort], api.game),
        scene_authoring=scene_manager.authoring_port if scene_manager is not None else None,
        scene_workspace=scene_manager.workspace_port if scene_manager is not None else None,
        project_service=api.project_service,
        asset_service=api.asset_service,
    )
