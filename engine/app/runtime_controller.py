from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.core.engine_state import EngineState
from engine.core.runtime_contracts import RuntimeControllerContext
from engine.core.runtime_loop import RuntimeLoopState, RuntimePhase, RuntimeTickPlan
from engine.editor.console_panel import log_info
from engine.physics.backend import PhysicsBackendSelection
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.tilemap.collision_builder import bake_tilemap_colliders

if TYPE_CHECKING:
    from engine.ecs.world import World


class RuntimeController:
    """Owns runtime state transitions, gameplay updates, and backend selection."""

    def __init__(
        self,
        context: RuntimeControllerContext,
        *,
        update_ui_overlay: Optional[Callable[[Any, tuple[float, float], Optional[str]], None]] = None,
        phase_observer: Optional[Callable[[RuntimePhase, RuntimeTickPlan], None]] = None,
    ) -> None:
        self._context = context
        self._get_state = context.get_state
        self._set_state = context.set_state
        self._get_world = context.get_world
        self._set_world = context.set_world
        self._get_scene_runtime = context.get_scene_runtime
        self._get_rule_system = context.get_rule_system
        self._get_script_behaviour_system = context.get_script_behaviour_system
        self._get_event_bus = context.get_event_bus
        self._get_animation_system = context.get_animation_system
        self._get_input_system = context.get_input_system
        self._get_player_controller_system = context.get_player_controller_system
        self._get_character_controller_system = context.get_character_controller_system
        self._get_physics_system = context.get_physics_system
        self._get_collision_system = context.get_collision_system
        self._get_audio_system = context.get_audio_system
        self._get_scene_transition_controller = context.get_scene_transition_controller
        self._get_physics_backend_registry = context.get_physics_backend_registry
        self._reset_profiler = context.reset_profiler
        self._set_physics_backend = context.set_physics_backend
        self._edit_animation_speed = float(context.edit_animation_speed)
        self._update_ui_overlay = update_ui_overlay
        self._phase_observer = phase_observer
        self._loop_state = RuntimeLoopState()

    @property
    def loop_state(self) -> RuntimeLoopState:
        return self._loop_state

    def _emit_phase(self, phase: RuntimePhase, plan: RuntimeTickPlan) -> None:
        if self._phase_observer is not None:
            self._phase_observer(phase, plan)

    def begin_runtime_session(self) -> None:
        self._loop_state.reset()

    def end_runtime_session(self) -> None:
        self._loop_state.reset()

    def build_tick_plan(self, dt: float, *, should_render_like: bool = True) -> RuntimeTickPlan:
        frame_dt = max(0.0, float(dt))
        state = self._get_state()
        is_stepping = state == EngineState.STEPPING
        fixed_dt = self._loop_state.fixed_dt
        fixed_steps = 0

        if is_stepping:
            self._loop_state.accumulator = 0.0
            fixed_steps = 1
        elif state.allows_physics() or state.allows_gameplay():
            self._loop_state.accumulator += frame_dt
            requested_steps = int(self._loop_state.accumulator / fixed_dt) if fixed_dt > 0 else 0
            fixed_steps = min(requested_steps, self._loop_state.max_fixed_steps_per_frame)
            if fixed_steps > 0:
                self._loop_state.accumulator -= fixed_steps * fixed_dt
            if requested_steps > self._loop_state.max_fixed_steps_per_frame:
                self._loop_state.accumulator = 0.0

        return RuntimeTickPlan(
            frame_dt=frame_dt,
            fixed_dt=fixed_dt,
            fixed_steps=fixed_steps,
            is_stepping=is_stepping,
            should_render_like=bool(should_render_like),
        )
    def play(self) -> None:
        """Inicia el juego (EDIT -> PLAY)."""
        if self._get_state() != EngineState.EDIT:
            return

        log_info("Estado: EDIT -> PLAY")
        self._reset_profiler(run_label="play_session")

        scene_runtime = self._get_scene_runtime()
        if scene_runtime is not None:
            runtime_world = scene_runtime.enter_play()
            if runtime_world is None:
                return
            self._set_world(runtime_world)
            bake_tilemap_colliders(runtime_world, merge_shapes=True)

            rule_system = self._get_rule_system()
            if rule_system is not None:
                rule_system.set_world(runtime_world)
                scene = scene_runtime.current_scene
                if scene is not None:
                    rule_system.load_rules(scene.rules_data)

            script_behaviour_system = self._get_script_behaviour_system()
            if script_behaviour_system is not None:
                script_behaviour_system.on_play(runtime_world)

        self.begin_runtime_session()
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

        scene_runtime = self._get_scene_runtime()
        if scene_runtime is not None:
            edit_world = scene_runtime.exit_play()
            if edit_world is not None:
                self._set_world(edit_world)

        self.end_runtime_session()
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

    def run_fixed_update(self, world: Optional["World"], fixed_dt: float, plan: RuntimeTickPlan) -> None:
        if world is None:
            return
        self._emit_phase(RuntimePhase.FIXED_UPDATE, plan)
        self.update_gameplay(world, fixed_dt)

    def run_update(self, world: Optional["World"], dt: float, plan: RuntimeTickPlan) -> bool:
        self._emit_phase(RuntimePhase.UPDATE, plan)
        self.update_animation(world, dt)

        if self._get_state() != EngineState.EDIT or world is None:
            return False

        script_behaviour_system = self._get_script_behaviour_system()
        if script_behaviour_system is None:
            return False
        return bool(script_behaviour_system.update(world, dt, is_edit_mode=True))

    def run_post_update(
        self,
        world: Optional["World"],
        plan: RuntimeTickPlan,
        *,
        viewport_size: Optional[tuple[float, float]] = None,
        active_tab: Optional[str] = None,
    ) -> None:
        self._emit_phase(RuntimePhase.POST_UPDATE, plan)

        if (
            world is not None
            and plan.should_render_like
            and viewport_size is not None
            and self._update_ui_overlay is not None
        ):
            self._update_ui_overlay(world, viewport_size, active_tab)

        if plan.is_stepping and self._get_state() == EngineState.STEPPING:
            self._set_state(EngineState.PAUSED)

    def begin_render_phase(self, plan: RuntimeTickPlan) -> None:
        self._emit_phase(RuntimePhase.RENDER, plan)

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
