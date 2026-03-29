import unittest
from unittest.mock import patch

import pyray as rl

from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.rendering.render_targets import RenderTargetPool
from engine.systems.render_system import RenderSystem


class RenderTargetsTests(unittest.TestCase):
    def test_render_target_pool_supports_dry_run_lifecycle_without_window(self) -> None:
        pool = RenderTargetPool()
        pool.begin_frame()
        handle = pool.begin("preview", 128, 96, rl.Color(0, 0, 0, 0))
        self.assertEqual(handle.name, "preview")
        pool.end()
        pool.compose("preview", rl.Rectangle(0, 0, 128, 96))

        metrics = pool.get_frame_metrics()
        self.assertEqual(metrics["passes"], 1)
        self.assertEqual(metrics["composites"], 1)

    def test_profile_world_reports_additional_target_passes_for_debug_and_minimap(self) -> None:
        world = World()
        world.feature_metadata = {
            "render_2d": {
                "sorting_layers": ["Default", "Gameplay"],
                "minimap": {"enabled": True, "width": 160, "height": 100, "margin": 10},
            }
        }
        entity = world.create_entity("Player")
        entity.add_component(Transform(x=24.0, y=36.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Sprite(texture_path="assets/player.png", width=32, height=32))
        entity.add_component(RenderOrder2D(sorting_layer="Gameplay", order_in_layer=0, render_pass="World"))
        world.selected_entity_name = "Player"

        render_system = RenderSystem()
        stats = render_system.profile_world(world, viewport_size=(320.0, 180.0))

        self.assertEqual(stats["render_target_passes"], 2)
        self.assertEqual(stats["render_target_composites"], 2)
        self.assertEqual(stats["render_entities"], 1)

    def test_render_without_render_targets_skips_overlay_composites(self) -> None:
        world = World()
        entity = world.create_entity("Player")
        entity.add_component(Transform(x=24.0, y=36.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Sprite(texture_path="assets/player.png", width=32, height=32))
        entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))
        world.selected_entity_name = "Player"

        render_system = RenderSystem()
        with patch("pyray.begin_mode_2d"), patch("pyray.end_mode_2d"):
            render_system.render(
                world,
                override_camera=rl.Camera2D(),
                use_world_camera=False,
                viewport_size=(320.0, 180.0),
                allow_render_targets=False,
            )

        stats = render_system.get_last_render_stats()
        self.assertEqual(stats["render_target_passes"], 0)
        self.assertEqual(stats["render_target_composites"], 0)


if __name__ == "__main__":
    unittest.main()
