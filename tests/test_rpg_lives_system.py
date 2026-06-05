from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRpgLivesSystem(unittest.TestCase):
    def _make_runtime(self):
        from engine.levels.component_registry import create_default_registry
        from engine.runtime.content_loader import ContentLoader
        from engine.runtime.shared_game_runtime import SharedGameRuntime

        project_root = Path(__file__).parent.parent / "projects" / "RPG"
        runtime = SharedGameRuntime(
            ContentLoader(project_root),
            create_default_registry(),
            window_config={"width": 844, "height": 390, "device_profile": "mobile_landscape"},
        )
        runtime.setup_scripts_path(str(project_root / "scripts"))
        self.assertTrue(runtime.load_scene("levels/main_scene.json"))
        return runtime

    def _player_script(self, runtime):
        from engine.components.scriptbehaviour import ScriptBehaviour

        player = runtime.world.get_entity_by_name("Player")
        self.assertIsNotNone(player)
        assert player is not None
        script = player.get_component(ScriptBehaviour)
        self.assertIsNotNone(script)
        assert script is not None
        return player, script

    def _set_slime_contact(self, runtime, *, touching: bool) -> None:
        from engine.components.transform import Transform

        player = runtime.world.get_entity_by_name("Player")
        self.assertIsNotNone(player)
        assert player is not None
        player_transform = player.get_component(Transform)
        self.assertIsNotNone(player_transform)
        assert player_transform is not None

        for slime_name in ("Slime_0", "Slime_1", "Slime_2"):
            slime = runtime.world.get_entity_by_name(slime_name)
            self.assertIsNotNone(slime)
            assert slime is not None
            transform = slime.get_component(Transform)
            self.assertIsNotNone(transform)
            assert transform is not None
            if slime_name == "Slime_0" and touching:
                transform.set_position(player_transform.x, player_transform.y)
            else:
                transform.set_position(240.0, 240.0)

    def _advance(self, runtime, frames: int, dt: float = 0.1) -> None:
        for _ in range(frames):
            runtime.run_frame(dt, {})

    def _heart_states(self, runtime) -> list[bool]:
        from engine.components.uiimage import UIImage

        result: list[bool] = []
        for name in ("Heart_1", "Heart_2", "Heart_3"):
            entity = runtime.world.get_entity_by_name(name)
            self.assertIsNotNone(entity)
            assert entity is not None
            image = entity.get_component(UIImage)
            self.assertIsNotNone(image)
            assert image is not None
            result.append(bool(image.enabled))
        return result

    def test_contact_damage_starts_invulnerability_and_blinks(self):
        runtime = self._make_runtime()
        try:
            self._set_slime_contact(runtime, touching=True)
            self._advance(runtime, 1)

            player, script = self._player_script(runtime)
            animator = player.get_component_by_name("Animator")
            self.assertIsNotNone(animator)
            assert animator is not None

            self.assertEqual(script.public_data["lives"], 2)
            self.assertGreater(script.public_data["invulnerable_time_remaining"], 2.8)
            self.assertEqual(self._heart_states(runtime), [True, True, False])

            samples = set()
            for _ in range(8):
                samples.add(bool(animator.enabled))
                self._advance(runtime, 1, dt=0.12)

            self.assertIn(False, samples)
            self.assertIn(True, samples)

            self._advance(runtime, 10)
            self.assertEqual(script.public_data["lives"], 2)
        finally:
            runtime.shutdown()

    def test_player_must_separate_before_taking_damage_again(self):
        runtime = self._make_runtime()
        try:
            self._set_slime_contact(runtime, touching=True)
            self._advance(runtime, 1)

            _player, script = self._player_script(runtime)
            self.assertEqual(script.public_data["lives"], 2)

            self._advance(runtime, 40)
            self.assertEqual(script.public_data["lives"], 2)

            self._set_slime_contact(runtime, touching=False)
            self._advance(runtime, 1)
            self._advance(runtime, 50)

            self._set_slime_contact(runtime, touching=True)
            self._advance(runtime, 1)

            _player, script = self._player_script(runtime)
            self.assertEqual(script.public_data["lives"], 1)
            self.assertEqual(self._heart_states(runtime), [True, False, False])
        finally:
            runtime.shutdown()

    def test_player_reloads_scene_with_three_lives_after_third_hit(self):
        from engine.components.scriptbehaviour import ScriptBehaviour
        from engine.components.transform import Transform

        runtime = self._make_runtime()
        try:
            for hit_index in range(3):
                self._set_slime_contact(runtime, touching=True)
                self._advance(runtime, 1)
                if hit_index < 2:
                    self._set_slime_contact(runtime, touching=False)
                    self._advance(runtime, 1)
                    self._advance(runtime, 50)

            player = runtime.world.get_entity_by_name("Player")
            slime = runtime.world.get_entity_by_name("Slime_0")
            self.assertIsNotNone(player)
            self.assertIsNotNone(slime)
            assert player is not None
            assert slime is not None

            player_script = player.get_component(ScriptBehaviour)
            player_transform = player.get_component(Transform)
            slime_transform = slime.get_component(Transform)
            self.assertIsNotNone(player_script)
            self.assertIsNotNone(player_transform)
            self.assertIsNotNone(slime_transform)
            assert player_script is not None
            assert player_transform is not None
            assert slime_transform is not None

            self.assertEqual(runtime.current_scene_path, "levels/main_scene.json")
            self.assertEqual(player_script.public_data["lives"], 3)
            self.assertAlmostEqual(player_transform.x, 0.0, delta=0.01)
            self.assertAlmostEqual(player_transform.y, 0.0, delta=0.01)
            self.assertAlmostEqual(slime_transform.x, 48.0, delta=0.01)
            self.assertAlmostEqual(slime_transform.y, 0.0, delta=0.01)
            self.assertEqual(self._heart_states(runtime), [True, True, True])
        finally:
            runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
