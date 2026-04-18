import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from cli.headless_game import HeadlessGame
from engine.core.engine_state import EngineState
from engine.core.runtime_loop import RuntimePhase


class HeadlessRuntimeLoopFoundationTests(unittest.TestCase):
    def test_headless_runtime_uses_shared_phase_sequence_and_consumes_single_step(self) -> None:
        game = HeadlessGame()
        phase_events: list[RuntimePhase] = []
        game._runtime_controller._phase_observer = lambda phase, plan: phase_events.append(phase)

        world = SimpleNamespace(feature_metadata={})
        game.set_world(world)
        game.set_animation_system(Mock())
        game.set_input_system(Mock())
        game.set_player_controller_system(Mock())
        game.set_character_controller_system(Mock())
        game.set_script_behaviour_system(Mock())
        game.set_audio_system(Mock())
        game._scene_transition_controller = Mock()
        game._runtime_controller._get_scene_transition_controller = lambda: game._scene_transition_controller
        game._state = EngineState.STEPPING

        game.update_headless(1.0 / 60.0)

        self.assertEqual(
            phase_events,
            [RuntimePhase.FIXED_UPDATE, RuntimePhase.UPDATE, RuntimePhase.POST_UPDATE],
        )
        self.assertEqual(game.state, EngineState.PAUSED)
        self.assertEqual(game.time.frame_count, 1)


if __name__ == "__main__":
    unittest.main()
