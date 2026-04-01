from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.core.engine_state import EngineState
from engine.editor.console_panel import log_info
from engine.physics.backend import PhysicsBackendSelection
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.physics.registry import PhysicsBackendRegistry
from engine.tilemap.collision_builder import bake_tilemap_colliders

if TYPE_CHECKING:
    from engine.ecs.world import World


class RuntimeController:
    """Owns runtime state transitions, gameplay updates, and backend selection."""

    def __init__(
        self,
        *,
        get_state: Callable[[], EngineState],
        set_state: Callable[[EngineState], None],
        get_world: Callable[[], Optional["World"]],
        set_world: Callable[[Optional["World"]], None],
        get_scene_manager: Callable[[], Any],
        get_rule_system: Callable[[], Any],
        get_script_behaviour_system: Callable[[], Any],
        get_event_bus: Callable[[], Any],
        get_animation_system: Callable[[], Any],
        get_input_system: Callable[[], Any],
        get_player_controller_system: Callable[[], Any],
        get_character_controller_system: Callable[[], Any],
        get_physics_system: Callable[[], Any],
        get_collision_system: Callable[[], Any],
        get_audio_system: Callable[[], Any],
        get_scene_transition_controller: Callable[[], Any],
        get_physics_backend_registry: Callable[[], PhysicsBackendRegistry],
        reset_profiler: Callable[..., None],
        set_physics_backend: Callable[[Any, str], None],
        edit_animation_speed: float,
    ) -> None:
        self._get_state = get_state
        self._set_state = set_state
        self._get_world = get_world
        self._set_world = set_world
        self._get_scene_manager = get_scene_manager
        self._get_rule_system = get_rule_system
        self._get_script_behaviour_system = get_script_behaviour_system
        self._get_event_bus = get_event_bus
        self._get_animation_system = get_animation_system
        self._get_input_system = get_input_system
        self._get_player_controller_system = get_player_controller_system
        self._get_character_controller_system = get_character_controller_system
        self._get_physics_system = get_physics_system
        self._get_collision_system = get_collision_system
        self._get_audio_system = get_audio_system
        self._get_scene_transition_controller = get_scene_transition_controller
        self._get_physics_backend_registry = get_physics_backend_registry
        self._reset_profiler = reset_profiler
        self._set_physics_backend = set_physics_backend
        self._edit_animation_speed = float(edit_animation_speed)

    def play(self) -> None:
        """Inicia el juego (EDIT -> PLAY)."""
        if self._get_state() != EngineState.EDIT:
            return

        log_info("Estado: EDIT -> PLAY")
        self._reset_profiler(run_label="play_session")

        scene_manager = self._get_scene_manager()
        if scene_manager is not None:
            runtime_world = scene_manager.enter_play()
            if runtime_world is None:
                return
            self._set_world(runtime_world)
            bake_tilemap_colliders(runtime_world, merge_shapes=True)

            rule_system = self._get_rule_system()
            if rule_system is not None:
                rule_system.set_world(runtime_world)
                scene = scene_manager.current_scene
                if scene is not None:
                    rule_system.load_rules(scene.rules_data)

            script_behaviour_system = self._get_script_behaviour_system()
            if script_behaviour_system is not None:
                script_behaviour_system.on_play(runtime_world)

        self._set_state(EngineState.PLAY)

        event_bus = self._get_event_bus()
        if event_bus is not None:
            event_bus.emit("on_play", {})

    def pause(self) -> None:
        """Pausa/Resume el juego (PLAY <-> PAUSED)."""
        if self._get_state() == EngineState.PLAY:
            log_info("Estado: PLAY -> PAUSED")
            self._set_state(EngineState.PAUSED)
        elif self._get_state() == EngineState.PAUSED:
            log_info("Estado: PAUSED -> PLAY")
            self._set_state(EngineState.PLAY)

    def stop(self) -> None:
        """Detiene el juego y vuelve a edición."""
        if self._get_state() not in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING):
            return

        log_info("Estado: -> EDIT (restaurando escena)")

        rule_system = self._get_rule_system()
        if rule_system is not None:
            rule_system.clear_rules()

        event_bus = self._get_event_bus()
        if event_bus is not None:
            event_bus.clear_history()

        runtime_world = self._get_world()
        script_behaviour_system = self._get_script_behaviour_system()
        if script_behaviour_system is not None and runtime_world is not None:
            script_behaviour_system.on_stop(runtime_world)

        scene_manager = self._get_scene_manager()
        if scene_manager is not None:
            edit_world = scene_manager.exit_play()
            if edit_world is not None:
                self._set_world(edit_world)

        self._set_state(EngineState.EDIT)

    def step(self) -> None:
        """Avanza exactamente un frame de simulación."""
        if self._get_state() == EngineState.EDIT:
            return

        if self._get_state() == EngineState.PLAY:
            self.pause()

        log_info("Step frame")
        self._set_state(EngineState.STEPPING)

    def update_animation(self, world: Optional["World"], dt: float) -> None:
        animation_system = self._get_animation_system()
        if animation_system is None or world is None:
            return

        state = self._get_state()
        if state.allows_animation():
            animation_system.update(world, dt)
        elif state.allows_animation_preview():
            animation_system.update(world, dt * self._edit_animation_speed)

    def update_gameplay(self, world: "World", dt: float) -> None:
        input_system = self._get_input_system()
        if input_system is not None:
            input_system.update(world)

        character_controller_system = self._get_character_controller_system()
        if character_controller_system is not None:
            character_controller_system.update(world, dt)

        player_controller_system = self._get_player_controller_system()
        if player_controller_system is not None:
            player_controller_system.update(world)

        script_behaviour_system = self._get_script_behaviour_system()
        if script_behaviour_system is not None:
            script_behaviour_system.update(world, dt, is_edit_mode=False)

        state = self._get_state()
        backend = self._get_physics_backend_registry().resolve(world).backend
        if backend is not None and state.allows_physics():
            backend.step(world, dt)

        audio_system = self._get_audio_system()
        if audio_system is not None:
            audio_system.update(world)

        scene_transition_controller = self._get_scene_transition_controller()
        if scene_transition_controller is not None:
            scene_transition_controller.update(world)

    def get_physics_backend_selection(self, world: Optional["World"]) -> PhysicsBackendSelection:
        return self._get_physics_backend_registry().resolve(world).selection

    def resolve_physics_backend_name(self, world: Optional["World"]) -> str:
        selection = self.get_physics_backend_selection(world)
        effective_backend = selection.get("effective_backend")
        return str(effective_backend or selection["requested_backend"])

    def refresh_default_physics_backend(self) -> None:
        physics_system = self._get_physics_system()
        collision_system = self._get_collision_system()
        if physics_system is None or collision_system is None:
            return
        self._set_physics_backend(
            LegacyAABBPhysicsBackend(
                physics_system,
                collision_system,
                event_bus=self._get_event_bus(),
            ),
            "legacy_aabb",
        )
