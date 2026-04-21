import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from engine.app.runtime_controller import RuntimeController
from engine.core.engine_state import EngineState
from engine.core.runtime_contracts import RuntimeControllerContext
from engine.core.runtime_loop import RuntimePhase
from engine.physics.registry import PhysicsBackendRegistry
from engine.services.registro_servicios import RegistroServicios


class RuntimeControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {"value": EngineState.EDIT}
        self.world_holder = {"world": None}
        self.scene_manager = Mock()
        self.scene_manager.current_scene = SimpleNamespace(rules_data=[{"event": "tick"}])
        self.rule_system = Mock()
        self.script_behaviour_system = Mock()
        self.event_bus = Mock()
        self.animation_system = Mock()
        self.input_system = Mock()
        self.player_controller_system = Mock()
        self.character_controller_system = Mock()
        self.physics_system = Mock()
        self.collision_system = Mock()
        self.audio_system = Mock()
        self.scene_transition_controller = Mock()
        self.physics_backend_registry = PhysicsBackendRegistry()
        self.reset_profiler = Mock()
        self.set_physics_backend = Mock()
        self.update_ui_overlay = Mock()
        self.phase_events: list[RuntimePhase] = []
        self.controller = RuntimeController(
            RuntimeControllerContext(
                get_state=lambda: self.state["value"],
                set_state=lambda value: self.state.__setitem__("value", value),
                get_world=lambda: self.world_holder["world"],
                set_world=lambda world: self.world_holder.__setitem__("world", world),
                get_scene_runtime=lambda: self.scene_manager,
                get_rule_system=lambda: self.rule_system,
                get_script_behaviour_system=lambda: self.script_behaviour_system,
                get_event_bus=lambda: self.event_bus,
                get_animation_system=lambda: self.animation_system,
                get_input_system=lambda: self.input_system,
                get_player_controller_system=lambda: self.player_controller_system,
                get_character_controller_system=lambda: self.character_controller_system,
                get_physics_system=lambda: self.physics_system,
                get_collision_system=lambda: self.collision_system,
                get_audio_system=lambda: self.audio_system,
                get_scene_transition_controller=lambda: self.scene_transition_controller,
                get_physics_backend_registry=lambda: self.physics_backend_registry,
                reset_profiler=self.reset_profiler,
                set_physics_backend=self.set_physics_backend,
                edit_animation_speed=0.35,
            ),
            update_ui_overlay=lambda world, viewport_size, active_tab=None: self.update_ui_overlay(
                world,
                viewport_size,
                active_tab,
            ),
            phase_observer=lambda phase, plan: self.phase_events.append(phase),
        )

    def test_play_enters_runtime_and_emits_on_play(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        self.scene_manager.enter_play.return_value = runtime_world

        with patch("engine.app.runtime_controller.bake_tilemap_colliders") as bake_tilemap_colliders:
            self.controller.play()

        self.reset_profiler.assert_called_once_with(run_label="play_session")
        self.scene_manager.enter_play.assert_called_once_with()
        self.assertIs(self.world_holder["world"], runtime_world)
        bake_tilemap_colliders.assert_called_once_with(runtime_world, merge_shapes=True)
        self.rule_system.set_world.assert_called_once_with(runtime_world)
        self.rule_system.load_rules.assert_called_once_with(self.scene_manager.current_scene.rules_data)
        self.assertEqual(
            self.rule_system.method_calls[:2],
            [
                call.set_world(runtime_world),
                call.load_rules(self.scene_manager.current_scene.rules_data),
            ],
        )
        self.script_behaviour_system.on_play.assert_called_once_with(runtime_world)
        self.event_bus.emit.assert_called_once_with("on_play", {})
        self.assertEqual(self.state["value"], EngineState.PLAY)

    def test_play_aborts_when_runtime_world_cannot_be_created(self) -> None:
        self.scene_manager.enter_play.return_value = None

        with patch("engine.app.runtime_controller.bake_tilemap_colliders") as bake_tilemap_colliders:
            self.controller.play()

        bake_tilemap_colliders.assert_not_called()
        self.rule_system.set_world.assert_not_called()
        self.script_behaviour_system.on_play.assert_not_called()
        self.event_bus.emit.assert_not_called()
        self.assertEqual(self.state["value"], EngineState.EDIT)

    def test_stop_restores_edit_world_and_clears_runtime_state(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.PLAY
        self.world_holder["world"] = runtime_world
        self.scene_manager.exit_play.return_value = edit_world

        self.controller.stop()

        self.rule_system.clear_rules.assert_called_once_with()
        self.event_bus.clear_history.assert_called_once_with()
        self.script_behaviour_system.on_stop.assert_called_once_with(runtime_world)
        self.scene_manager.exit_play.assert_called_once_with()
        self.assertIs(self.world_holder["world"], edit_world)
        self.assertEqual(self.state["value"], EngineState.EDIT)

    def test_play_then_stop_round_trip_switches_between_runtime_and_edit_worlds(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.scene_manager.enter_play.return_value = runtime_world
        self.scene_manager.exit_play.return_value = edit_world

        with patch("engine.app.runtime_controller.bake_tilemap_colliders"):
            self.controller.play()

        self.assertIs(self.world_holder["world"], runtime_world)
        self.assertEqual(self.state["value"], EngineState.PLAY)

        self.controller.stop()

        self.scene_manager.enter_play.assert_called_once_with()
        self.scene_manager.exit_play.assert_called_once_with()
        self.assertIs(self.world_holder["world"], edit_world)
        self.assertEqual(self.state["value"], EngineState.EDIT)

    def test_stop_from_stepping_restores_edit_state(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.STEPPING
        self.world_holder["world"] = runtime_world
        self.scene_manager.exit_play.return_value = edit_world

        self.controller.stop()

        self.assertEqual(self.state["value"], EngineState.EDIT)
        self.assertIs(self.world_holder["world"], edit_world)

    def test_step_pauses_play_and_enters_stepping(self) -> None:
        self.state["value"] = EngineState.PLAY

        with patch.object(self.controller, "pause", wraps=self.controller.pause) as pause:
            self.controller.step()

        pause.assert_called_once_with()
        self.assertEqual(self.state["value"], EngineState.STEPPING)

    def test_step_is_noop_in_edit_mode(self) -> None:
        self.state["value"] = EngineState.EDIT

        self.controller.step()

        self.assertEqual(self.state["value"], EngineState.EDIT)

    def test_build_tick_plan_accumulates_partial_fixed_steps(self) -> None:
        self.state["value"] = EngineState.PLAY

        first = self.controller.build_tick_plan(0.01)
        second = self.controller.build_tick_plan(0.01)

        self.assertEqual(first.fixed_steps, 0)
        self.assertEqual(second.fixed_steps, 1)
        self.assertGreater(self.controller.loop_state.accumulator, 0.0)
        self.assertLess(self.controller.loop_state.accumulator, self.controller.loop_state.fixed_dt)

    def test_build_tick_plan_caps_fixed_steps_and_discards_overflow(self) -> None:
        self.state["value"] = EngineState.PLAY
        self.controller.loop_state.max_fixed_steps_per_frame = 2

        plan = self.controller.build_tick_plan(0.2)

        self.assertEqual(plan.fixed_steps, 2)
        self.assertEqual(self.controller.loop_state.accumulator, 0.0)

    def test_build_tick_plan_stepping_forces_single_fixed_step(self) -> None:
        self.state["value"] = EngineState.STEPPING
        self.controller.loop_state.accumulator = 0.5

        plan = self.controller.build_tick_plan(0.0)

        self.assertTrue(plan.is_stepping)
        self.assertEqual(plan.fixed_steps, 1)
        self.assertEqual(self.controller.loop_state.accumulator, 0.0)

    def test_update_gameplay_prefers_registered_backend(self) -> None:
        backend = Mock()
        backend.backend_name = "box2d"
        world = SimpleNamespace(feature_metadata={"physics_2d": {"backend": "box2d"}})
        self.physics_backend_registry.register_backend(backend, backend_name="box2d")
        self.state["value"] = EngineState.PLAY

        self.controller.update_gameplay(world, 0.25)

        self.input_system.update.assert_called_once_with(world)
        self.character_controller_system.update.assert_called_once_with(world, 0.25)
        self.player_controller_system.update.assert_called_once_with(world)
        self.script_behaviour_system.update.assert_called_once_with(world, 0.25, is_edit_mode=False)
        backend.step.assert_called_once_with(world, 0.25)
        self.physics_system.update.assert_not_called()
        self.collision_system.update.assert_not_called()
        self.audio_system.update.assert_called_once_with(world)
        self.scene_transition_controller.update.assert_called_once_with(world)

    def test_update_gameplay_falls_back_to_registered_legacy_backend(self) -> None:
        legacy_backend = Mock()
        legacy_backend.backend_name = "legacy_aabb"
        world = SimpleNamespace(feature_metadata={"physics_2d": {"backend": "box2d"}})
        self.physics_backend_registry.register_backend(legacy_backend, backend_name="legacy_aabb")
        self.state["value"] = EngineState.PLAY

        self.controller.update_gameplay(world, 0.1)

        legacy_backend.step.assert_called_once_with(world, 0.1)
        self.physics_system.update.assert_not_called()
        self.collision_system.update.assert_not_called()
        self.audio_system.update.assert_called_once_with(world)
        self.scene_transition_controller.update.assert_called_once_with(world)

    def test_update_gameplay_is_noop_when_no_effective_backend_exists(self) -> None:
        world = SimpleNamespace(feature_metadata={"physics_2d": {"backend": "box2d"}})
        self.state["value"] = EngineState.PLAY

        self.controller.update_gameplay(world, 0.1)

        self.physics_system.update.assert_not_called()
        self.collision_system.update.assert_not_called()
        self.audio_system.update.assert_called_once_with(world)
        self.scene_transition_controller.update.assert_called_once_with(world)

    def test_get_physics_backend_selection_reports_fallback(self) -> None:
        legacy_backend = Mock()
        legacy_backend.backend_name = "legacy_aabb"
        world = SimpleNamespace(feature_metadata={"physics_2d": {"backend": "box2d"}})
        self.physics_backend_registry.register_backend(legacy_backend, backend_name="legacy_aabb")

        selection = self.controller.get_physics_backend_selection(world)

        self.assertEqual(selection["requested_backend"], "box2d")
        self.assertEqual(selection["effective_backend"], "legacy_aabb")
        self.assertTrue(selection["used_fallback"])

    def test_update_animation_uses_preview_speed_in_edit_mode(self) -> None:
        world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.EDIT

        self.controller.update_animation(world, 2.0)

        self.animation_system.update.assert_called_once_with(world, 0.7)

    def test_run_update_in_edit_mode_keeps_preview_and_edit_scripts_outside_fixed_step(self) -> None:
        world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.EDIT
        plan = self.controller.build_tick_plan(0.2)
        self.script_behaviour_system.update.return_value = True

        ran_edit_scripts = self.controller.run_update(world, 0.2, plan)

        self.assertEqual(plan.fixed_steps, 0)
        self.assertTrue(ran_edit_scripts)
        self.animation_system.update.assert_called_once()
        animation_args = self.animation_system.update.call_args.args
        self.assertIs(animation_args[0], world)
        self.assertAlmostEqual(animation_args[1], 0.07)
        self.script_behaviour_system.update.assert_called_once_with(world, 0.2, is_edit_mode=True)
        self.assertEqual(self.phase_events, [RuntimePhase.UPDATE])

    def test_run_post_update_pauses_after_single_step_and_updates_render_like_state(self) -> None:
        world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.STEPPING
        plan = self.controller.build_tick_plan(0.0, should_render_like=True)

        self.controller.run_fixed_update(world, plan.fixed_dt, plan)
        self.controller.run_update(world, plan.frame_dt, plan)
        self.controller.run_post_update(world, plan, viewport_size=(320.0, 180.0), active_tab="GAME")

        self.assertEqual(
            self.phase_events,
            [RuntimePhase.FIXED_UPDATE, RuntimePhase.UPDATE, RuntimePhase.POST_UPDATE],
        )
        self.update_ui_overlay.assert_called_once_with(world, (320.0, 180.0), "GAME")
        self.assertEqual(self.state["value"], EngineState.PAUSED)

    def test_run_post_update_flushes_deferred_queue_before_overlay(self) -> None:
        world = SimpleNamespace(feature_metadata={})
        plan = self.controller.build_tick_plan(0.0, should_render_like=True)
        orden: list[str] = []

        self.controller.deferred_queue.enqueue(lambda: orden.append("deferred"), description="prueba_post_update")
        self.update_ui_overlay.side_effect = lambda *_args, **_kwargs: orden.append("overlay")

        self.controller.run_post_update(world, plan, viewport_size=(320.0, 180.0), active_tab="GAME")

        self.assertEqual(orden, ["deferred", "overlay"])
        self.assertEqual(self.controller.deferred_queue.size, 0)

    def test_play_and_stop_reset_runtime_loop_state(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.scene_manager.enter_play.return_value = runtime_world
        self.scene_manager.exit_play.return_value = edit_world
        self.controller.loop_state.accumulator = 0.25

        with patch("engine.app.runtime_controller.bake_tilemap_colliders"):
            self.controller.play()

        self.assertEqual(self.controller.loop_state.accumulator, 0.0)
        self.controller.loop_state.accumulator = 0.5
        self.world_holder["world"] = runtime_world
        self.controller.stop()
        self.assertEqual(self.controller.loop_state.accumulator, 0.0)

    def test_stop_clears_signal_runtime_and_deferred_queue(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.PLAY
        self.world_holder["world"] = runtime_world
        self.scene_manager.exit_play.return_value = edit_world

        connection_id = self.controller.signal_runtime.connect("Emitter", "tick", lambda: None)
        self.controller.deferred_queue.enqueue(lambda: None, description="cleanup_test")

        self.controller.stop()

        self.assertFalse(self.controller.signal_runtime.is_connected(connection_id))
        self.assertEqual(self.controller.deferred_queue.size, 0)

    def test_refresh_default_physics_backend_registers_legacy_backend_when_ready(self) -> None:
        with patch("engine.app.runtime_controller.LegacyAABBPhysicsBackend", return_value="legacy-backend") as backend_class:
            self.controller.refresh_default_physics_backend()

        backend_class.assert_called_once_with(
            self.physics_system,
            self.collision_system,
            event_bus=self.event_bus,
        )
        self.set_physics_backend.assert_called_once_with("legacy-backend", "legacy_aabb")

    def test_refresh_default_physics_backend_skips_when_dependencies_missing(self) -> None:
        controller = RuntimeController(
            RuntimeControllerContext(
                get_state=lambda: self.state["value"],
                set_state=lambda value: self.state.__setitem__("value", value),
                get_world=lambda: self.world_holder["world"],
                set_world=lambda world: self.world_holder.__setitem__("world", world),
                get_scene_runtime=lambda: self.scene_manager,
                get_rule_system=lambda: self.rule_system,
                get_script_behaviour_system=lambda: self.script_behaviour_system,
                get_event_bus=lambda: self.event_bus,
                get_animation_system=lambda: self.animation_system,
                get_input_system=lambda: self.input_system,
                get_player_controller_system=lambda: self.player_controller_system,
                get_character_controller_system=lambda: self.character_controller_system,
                get_physics_system=lambda: None,
                get_collision_system=lambda: self.collision_system,
                get_audio_system=lambda: self.audio_system,
                get_scene_transition_controller=lambda: self.scene_transition_controller,
                get_physics_backend_registry=lambda: self.physics_backend_registry,
                reset_profiler=self.reset_profiler,
                set_physics_backend=self.set_physics_backend,
                edit_animation_speed=0.35,
            )
        )

        with patch("engine.app.runtime_controller.LegacyAABBPhysicsBackend") as backend_class:
            controller.refresh_default_physics_backend()

        backend_class.assert_not_called()
        self.set_physics_backend.assert_not_called()

    def test_runtime_controller_exposes_service_registry(self) -> None:
        self.assertIsInstance(self.controller.servicios, RegistroServicios)

    def test_play_clears_runtime_services_but_keeps_builtins(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.scene_manager.enter_play.return_value = runtime_world
        self.scene_manager.exit_play.return_value = edit_world

        self.controller.servicios.registrar_builtin("GlobalConfig", {"version": 1})
        self.controller.servicios.registrar("SessionTemp", {"session_id": 42})

        with patch("engine.app.runtime_controller.bake_tilemap_colliders"):
            self.controller.play()

        self.assertTrue(self.controller.servicios.tiene("GlobalConfig"))
        self.assertFalse(self.controller.servicios.tiene("SessionTemp"))

    def test_stop_clears_runtime_services_but_keeps_builtins(self) -> None:
        runtime_world = SimpleNamespace(feature_metadata={})
        edit_world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.PLAY
        self.world_holder["world"] = runtime_world
        self.scene_manager.exit_play.return_value = edit_world

        self.controller.servicios.registrar_builtin("GlobalConfig", {"version": 1})
        self.controller.servicios.registrar("SessionTemp", {"session_id": 42})

        self.controller.stop()

        self.assertTrue(self.controller.servicios.tiene("GlobalConfig"))
        self.assertFalse(self.controller.servicios.tiene("SessionTemp"))


if __name__ == "__main__":
    unittest.main()
