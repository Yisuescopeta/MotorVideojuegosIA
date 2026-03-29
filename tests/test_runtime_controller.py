import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.append(os.getcwd())

from engine.app.runtime_controller import RuntimeController
from engine.core.engine_state import EngineState


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
        self.physics_backends: dict[str, object] = {}
        self.reset_profiler = Mock()
        self.set_physics_backend = Mock()
        self.controller = RuntimeController(
            get_state=lambda: self.state["value"],
            set_state=lambda value: self.state.__setitem__("value", value),
            get_world=lambda: self.world_holder["world"],
            set_world=lambda world: self.world_holder.__setitem__("world", world),
            get_scene_manager=lambda: self.scene_manager,
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
            get_physics_backends=lambda: self.physics_backends,
            get_physics_backend_name=lambda: "legacy_aabb",
            reset_profiler=self.reset_profiler,
            set_physics_backend=self.set_physics_backend,
            edit_animation_speed=0.35,
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
        self.script_behaviour_system.on_play.assert_called_once_with(runtime_world)
        self.event_bus.emit.assert_called_once_with("on_play", {})
        self.assertEqual(self.state["value"], EngineState.PLAY)

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

    def test_update_gameplay_prefers_registered_backend(self) -> None:
        backend = Mock()
        world = SimpleNamespace(feature_metadata={"physics_2d": {"backend": "box2d"}})
        self.physics_backends["box2d"] = backend
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

    def test_update_gameplay_falls_back_to_legacy_physics_and_collision(self) -> None:
        world = SimpleNamespace(feature_metadata={"physics_2d": {"backend": "box2d"}})
        self.state["value"] = EngineState.PLAY

        self.controller.update_gameplay(world, 0.1)

        self.physics_system.update.assert_called_once_with(world, 0.1)
        self.collision_system.update.assert_called_once_with(world)
        self.audio_system.update.assert_called_once_with(world)

    def test_update_animation_uses_preview_speed_in_edit_mode(self) -> None:
        world = SimpleNamespace(feature_metadata={})
        self.state["value"] = EngineState.EDIT

        self.controller.update_animation(world, 2.0)

        self.animation_system.update.assert_called_once_with(world, 0.7)

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
            get_state=lambda: self.state["value"],
            set_state=lambda value: self.state.__setitem__("value", value),
            get_world=lambda: self.world_holder["world"],
            set_world=lambda world: self.world_holder.__setitem__("world", world),
            get_scene_manager=lambda: self.scene_manager,
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
            get_physics_backends=lambda: self.physics_backends,
            get_physics_backend_name=lambda: "legacy_aabb",
            reset_profiler=self.reset_profiler,
            set_physics_backend=self.set_physics_backend,
            edit_animation_speed=0.35,
        )

        with patch("engine.app.runtime_controller.LegacyAABBPhysicsBackend") as backend_class:
            controller.refresh_default_physics_backend()

        backend_class.assert_not_called()
        self.set_physics_backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
