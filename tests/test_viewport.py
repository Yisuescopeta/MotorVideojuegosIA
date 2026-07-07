"""
tests/test_viewport.py - Tests de utilidades de viewport.
"""

import unittest

from engine.components.camera2d import Camera2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.utils.viewport import (
    resolve_effective_camera2d,
    resolve_world_viewport_rect,
    screen_to_viewport,
    viewport_to_world,
)


class ResolveWorldViewportRectTests(unittest.TestCase):
    def test_none_world_returns_none(self) -> None:
        self.assertIsNone(resolve_world_viewport_rect(None))

    def test_no_camera_returns_none(self) -> None:
        world = World()
        world.create_entity()
        self.assertIsNone(resolve_world_viewport_rect(world))

    def test_disabled_camera_skipped(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True)
        cam.enabled = False
        entity.add_component(cam)
        self.assertIsNone(resolve_world_viewport_rect(world))

    def test_non_primary_camera_skipped(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=False)
        cam.enabled = True
        entity.add_component(cam)
        self.assertIsNone(resolve_world_viewport_rect(world))

    def test_primary_camera_returns_rect(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=100, y=200))
        cam = Camera2D(is_primary=True, zoom=1.0)
        cam.enabled = True
        entity.add_component(cam)
        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))
        self.assertIsNotNone(rect)
        assert rect is not None
        left, top, right, bottom = rect
        self.assertEqual(left, 100)
        self.assertEqual(top, 200)
        self.assertEqual(right, 900)
        self.assertEqual(bottom, 800)

    def test_camera_offset_centers_rect_like_runtime_camera(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=100, y=200))
        cam = Camera2D(is_primary=True, zoom=1.0, offset_x=400.0, offset_y=300.0)
        cam.enabled = True
        entity.add_component(cam)

        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))

        self.assertEqual(rect, (-300.0, -100.0, 500.0, 500.0))

    def test_zoom_affects_rect(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True, zoom=2.0)
        cam.enabled = True
        entity.add_component(cam)
        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))
        self.assertIsNotNone(rect)
        assert rect is not None
        left, top, right, bottom = rect
        self.assertEqual(left, 0)
        self.assertEqual(top, 0)
        self.assertEqual(right, 400)
        self.assertEqual(bottom, 300)

    def test_zero_zoom_uses_epsilon(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True, zoom=0.0)
        cam.enabled = True
        entity.add_component(cam)
        rect = resolve_world_viewport_rect(world, viewport_size=(800, 600))
        self.assertIsNotNone(rect)
        assert rect is not None
        left, top, right, bottom = rect
        # With epsilon 1e-4, sizes become enormous but finite.
        self.assertEqual(left, 0.0)
        self.assertEqual(top, 0.0)
        self.assertGreater(right, 1e6)

    def test_effective_camera_applies_profile_offset_and_target(self) -> None:
        world = World()
        entity = world.create_entity()
        entity.add_component(Transform(x=0, y=0))
        cam = Camera2D(is_primary=True, zoom=1.0)
        cam.profile_overrides = {
            "desktop_16_9": {
                "target_x": 100.0,
                "target_y": 50.0,
                "offset_x": 400.0,
                "offset_y": 300.0,
                "zoom": 2.0,
            }
        }
        entity.add_component(cam)

        resolved = resolve_effective_camera2d(world, viewport_size=(800, 600), camera_profile_id="desktop_16_9")

        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual((resolved.target_x, resolved.target_y), (100.0, 50.0))
        self.assertEqual(resolved.rect, (-100.0, -100.0, 300.0, 200.0))

    def test_effective_camera_applies_platformer_follow_framing_and_profile_offset(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=200.0, y=100.0))
        camera_entity = world.create_entity("Camera")
        camera_entity.add_component(Transform(x=0.0, y=0.0))
        camera = Camera2D(is_primary=True, zoom=1.0, follow_entity="Player", framing_mode="platformer")
        camera.profile_overrides = {
            "mobile_portrait": {
                "target_offset_x": 10.0,
                "target_offset_y": -20.0,
            }
        }
        camera_entity.add_component(camera)

        resolved = resolve_effective_camera2d(world, viewport_size=(390.0, 844.0), camera_profile_id="mobile_portrait")

        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.target_x, 210.0)
        self.assertAlmostEqual(resolved.target_y, -21.28, places=2)

    def test_viewport_to_world_uses_1280x720_camera_center(self) -> None:
        world = World()
        entity = world.create_entity("Camera")
        entity.add_component(Transform(x=100.0, y=200.0))
        entity.add_component(Camera2D(is_primary=True, zoom=1.0, offset_x=640.0, offset_y=360.0, framing_mode="locked"))

        self.assertEqual(viewport_to_world(640.0, 360.0, world, viewport_size=(1280.0, 720.0)), (100.0, 200.0))
        self.assertEqual(viewport_to_world(0.0, 0.0, None, viewport_size=(1280.0, 720.0)), (0.0, 0.0))

    def test_screen_to_viewport_scales_letterboxed_rect(self) -> None:
        viewport = screen_to_viewport(
            637.5,
            355.0,
            viewport_rect=(100.0, 50.0, 1075.0, 610.0),
            viewport_size=(1280.0, 720.0),
        )

        self.assertEqual(viewport, (640.0, 360.0))


if __name__ == "__main__":
    unittest.main()
