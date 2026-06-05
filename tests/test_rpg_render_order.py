from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRpgRenderOrder(unittest.TestCase):
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

    def test_player_and_slimes_sort_after_ground_tiles(self):
        from engine.systems.render_system import RenderSystem

        runtime = self._make_runtime()
        try:
            ordered = [entity.name for entity in RenderSystem()._sorted_render_entities(runtime.world)]
            order_index = {name: index for index, name in enumerate(ordered)}

            ground_names = [name for name in ordered if name.startswith("Ground_")]
            self.assertTrue(ground_names)

            last_ground_index = max(order_index[name] for name in ground_names)
            for actor_name in ("Player", "Slime_0", "Slime_1", "Slime_2"):
                self.assertIn(actor_name, order_index)
                self.assertGreater(order_index[actor_name], last_ground_index)
        finally:
            runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
