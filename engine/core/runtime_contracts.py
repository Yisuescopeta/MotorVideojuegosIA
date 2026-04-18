from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.core.engine_state import EngineState
from engine.physics.registry import PhysicsBackendRegistry
from engine.scenes.contracts import SceneRuntimePort

if TYPE_CHECKING:
    from engine.ecs.world import World


@dataclass(frozen=True)
class RuntimeControllerContext:
    get_state: Callable[[], EngineState]
    set_state: Callable[[EngineState], None]
    get_world: Callable[[], Optional["World"]]
    set_world: Callable[[Optional["World"]], None]
    get_scene_runtime: Callable[[], Optional[SceneRuntimePort]]
    get_rule_system: Callable[[], Any]
    get_script_behaviour_system: Callable[[], Any]
    get_event_bus: Callable[[], Any]
    get_animation_system: Callable[[], Any]
    get_input_system: Callable[[], Any]
    get_player_controller_system: Callable[[], Any]
    get_character_controller_system: Callable[[], Any]
    get_physics_system: Callable[[], Any]
    get_collision_system: Callable[[], Any]
    get_audio_system: Callable[[], Any]
    get_scene_transition_controller: Callable[[], Any]
    get_physics_backend_registry: Callable[[], PhysicsBackendRegistry]
    reset_profiler: Callable[..., None]
    set_physics_backend: Callable[[Any, str], None]
    edit_animation_speed: float
