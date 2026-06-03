from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRpgAndroidAnimationRegression(unittest.TestCase):
    def test_rpg_player_animation_stays_valid_on_and_off_wood_floor(self):
        project_root = Path(__file__).parent.parent / "projects" / "RPG"
        scene_path = project_root / "levels" / "main_scene.json"
        if not scene_path.exists():
            self.skipTest("RPG project is not present")

        from engine.components.animator import Animator
        from engine.components.transform import Transform
        from engine.levels.component_registry import create_default_registry
        from engine.runtime.content_loader import ContentLoader
        from engine.runtime.shared_game_runtime import SharedGameRuntime

        runtime = SharedGameRuntime(
            ContentLoader(project_root),
            create_default_registry(),
            window_config={"width": 844, "height": 390, "device_profile": "mobile_landscape"},
        )
        runtime.setup_scripts_path(str(project_root / "scripts"))
        self.assertTrue(runtime.load_scene("levels/main_scene.json"))

        player = runtime.world.get_entity_by_name("Player")
        self.assertIsNotNone(player)
        assert player is not None
        transform = player.get_component(Transform)
        animator = player.get_component(Animator)
        self.assertIsNotNone(transform)
        self.assertIsNotNone(animator)
        assert transform is not None
        assert animator is not None

        samples = []
        for frame in range(150):
            runtime.run_frame(
                1.0 / 60.0,
                {
                    "pointers": [
                        {"id": 1, "x": 52.0, "y": 304.2, "down": True, "pressed": frame == 0, "released": False}
                    ],
                    "x": 52.0,
                    "y": 304.2,
                    "down": True,
                    "pressed": frame == 0,
                    "released": False,
                },
            )
            if frame in (1, 30, 80, 140):
                samples.append((transform.x, animator.current_state, animator.current_frame, animator.flip_x))

        self.assertLess(samples[0][0], 0.0)
        self.assertLess(samples[-1][0], -160.0)
        for _x, state, frame, flip_x in samples:
            self.assertEqual(state, "walk_side")
            self.assertIn(frame, range(6))
            self.assertTrue(flip_x)
