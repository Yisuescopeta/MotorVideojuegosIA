"""
tests/test_parallax_layer.py - Tests de ParallaxLayer y ParallaxSystem.
"""
import unittest

from engine.components.camera2d import Camera2D
from engine.components.parallax_layer import ParallaxLayer
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.parallax_system import ParallaxSystem


class ParallaxLayerTests(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self) -> None:
        layer = ParallaxLayer(
            motion_scale_x=0.5,
            motion_scale_y=0.3,
            scroll_offset_x=10.0,
            scroll_offset_y=20.0,
            mirror_x=100.0,
            mirror_y=0.0,
            follow_viewport=False,
            autoscroll_x=5.0,
            autoscroll_y=2.0,
        )
        layer.enabled = False
        data = layer.to_dict()
        restored = ParallaxLayer.from_dict(data)
        self.assertEqual(restored.motion_scale_x, 0.5)
        self.assertEqual(restored.motion_scale_y, 0.3)
        self.assertEqual(restored.scroll_offset_x, 10.0)
        self.assertEqual(restored.scroll_offset_y, 20.0)
        self.assertEqual(restored.mirror_x, 100.0)
        self.assertEqual(restored.mirror_y, 0.0)
        self.assertFalse(restored.follow_viewport)
        self.assertEqual(restored.autoscroll_x, 5.0)
        self.assertEqual(restored.autoscroll_y, 2.0)
        self.assertFalse(restored.enabled)

    def test_default_values(self) -> None:
        layer = ParallaxLayer()
        self.assertEqual(layer.motion_scale_x, 1.0)
        self.assertEqual(layer.motion_scale_y, 1.0)
        self.assertEqual(layer.scroll_offset_x, 0.0)
        self.assertEqual(layer.scroll_offset_y, 0.0)
        self.assertEqual(layer.mirror_x, 0.0)
        self.assertEqual(layer.mirror_y, 0.0)
        self.assertTrue(layer.follow_viewport)
        self.assertEqual(layer.autoscroll_x, 0.0)
        self.assertEqual(layer.autoscroll_y, 0.0)
        self.assertTrue(layer.enabled)

    def test_serialization_excludes_runtime_fields(self) -> None:
        layer = ParallaxLayer()
        layer._rest_x = 999.0
        layer._rest_y = 888.0
        layer._rest_captured = True
        data = layer.to_dict()
        self.assertNotIn("_rest_x", data)
        self.assertNotIn("_rest_y", data)
        self.assertNotIn("_autoscroll_accum_x", data)
        self.assertNotIn("_rest_captured", data)


class ParallaxSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = ParallaxSystem()

    def _create_entity(
        self,
        name: str,
        x: float = 0.0,
        y: float = 0.0,
        **parallax_kwargs: object,
    ) -> Entity:
        entity = Entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(ParallaxLayer(**parallax_kwargs))
        self.world.add_entity(entity)
        return entity

    def _create_camera(self, name: str = "MainCamera", x: float = 0.0, y: float = 0.0) -> Entity:
        entity = Entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Camera2D(is_primary=True))
        self.world.add_entity(entity)
        return entity

    def test_on_play_captures_rest_positions(self) -> None:
        entity = self._create_entity("BgLayer", x=100.0, y=50.0)
        self._create_camera(x=0.0, y=0.0)
        self.system.on_play(self.world)
        parallax = entity.get_component(ParallaxLayer)
        assert parallax is not None
        self.assertEqual(parallax._rest_x, 100.0)
        self.assertEqual(parallax._rest_y, 50.0)
        self.assertTrue(parallax._rest_captured)

    def test_motion_scale_zero_static(self) -> None:
        """motion_scale=0: entity does NOT follow camera (remains at rest)."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity("BgFar", x=200.0, y=100.0, motion_scale_x=0.0, motion_scale_y=0.0)
        self.system.on_play(self.world)
        # Mover cámara
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        cam_transform.y = 50.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        # motion_scale=0 → entity stays at rest (no camera follow)
        self.assertAlmostEqual(transform.x, 200.0, places=4)
        self.assertAlmostEqual(transform.y, 100.0, places=4)

    def test_motion_scale_one_follows(self) -> None:
        """motion_scale=1: entity follows camera 1:1."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity("FgLayer", x=200.0, y=100.0, motion_scale_x=1.0, motion_scale_y=1.0)
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        cam_transform.y = 50.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 300.0, places=4)
        self.assertAlmostEqual(transform.y, 150.0, places=4)

    def test_motion_scale_half(self) -> None:
        """motion_scale=0.5: entity follows camera at half speed."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity("BgMid", x=200.0, y=100.0, motion_scale_x=0.5, motion_scale_y=0.5)
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        cam_transform.y = 100.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 250.0, places=4)
        self.assertAlmostEqual(transform.y, 150.0, places=4)

    def test_scroll_offset_adds_constant(self) -> None:
        """scroll_offset adds a constant positional offset."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity(
            "BgScrolled",
            x=200.0, y=100.0,
            motion_scale_x=0.0, motion_scale_y=0.0,
            scroll_offset_x=50.0, scroll_offset_y=-30.0,
        )
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        # motion_scale=0, but scroll_offset adds
        self.assertAlmostEqual(transform.x, 200.0 + 50.0, places=4)
        self.assertAlmostEqual(transform.y, 100.0 - 30.0, places=4)

    def test_autoscroll_accumulates(self) -> None:
        """autoscroll accumulates over time."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity(
            "AutoBg",
            x=200.0, y=100.0,
            motion_scale_x=0.0, motion_scale_y=0.0,
            autoscroll_x=100.0, autoscroll_y=50.0,
        )
        self.system.on_play(self.world)
        # 3 frames at 0.016 each: autoscroll = 100*0.048 = 4.8, 50*0.048 = 2.4
        for _ in range(3):
            self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 200.0 + 100.0 * 0.048, places=4)
        self.assertAlmostEqual(transform.y, 100.0 + 50.0 * 0.048, places=4)

    def test_mirror_wraps(self) -> None:
        """mirror wraps the offset when exceeding mirror value."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity(
            "BgMirror",
            x=200.0, y=100.0,
            motion_scale_x=1.0, motion_scale_y=0.0,
            mirror_x=300.0, mirror_y=0.0,
        )
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        # Move camera 500: delta=500, motion_scale_x=1 → offset=500
        # mirror_x=300 → wrapped offset = 500 % 300 = 200
        cam_transform.x = 500.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 200.0 + (500 % 300), places=4)

    def test_follow_viewport_false_stays(self) -> None:
        """follow_viewport=False ignores camera movement."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity(
            "StaticBg",
            x=200.0, y=100.0,
            motion_scale_x=1.0, motion_scale_y=1.0,
            follow_viewport=False,
        )
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 200.0)
        self.assertAlmostEqual(transform.y, 100.0)

    def test_disabled_restores_rest(self) -> None:
        """Disabled entity restores to rest position."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity("DisabledBg", x=200.0, y=100.0, motion_scale_x=1.0, motion_scale_y=1.0)
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        # Moved with camera
        self.assertAlmostEqual(transform.x, 300.0)
        # Now disable
        parallax = entity.get_component(ParallaxLayer)
        assert parallax is not None
        parallax.enabled = False
        cam_transform.x = 200.0
        self.system.update(self.world, 0.016)
        # Should be back at rest
        self.assertAlmostEqual(transform.x, 200.0)
        self.assertAlmostEqual(transform.y, 100.0)

    def test_no_camera_noop(self) -> None:
        """No camera in world: system does nothing."""
        entity = self._create_entity("NoCam", x=200.0, y=100.0, motion_scale_x=1.0, motion_scale_y=1.0)
        self.system.on_play(self.world)
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 200.0)
        self.assertAlmostEqual(transform.y, 100.0)

    def test_on_stop_restores(self) -> None:
        """on_stop restores all entities to rest positions and clears state."""
        self._create_camera(x=0.0, y=0.0)
        entity = self._create_entity("Bg", x=200.0, y=100.0, motion_scale_x=1.0, motion_scale_y=1.0)
        self.system.on_play(self.world)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        self.system.update(self.world, 0.016)
        # Entity was moved
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 300.0)
        # Stop & restore
        self.system.on_stop(self.world)
        self.assertAlmostEqual(transform.x, 200.0)
        self.assertAlmostEqual(transform.y, 100.0)
        parallax = entity.get_component(ParallaxLayer)
        assert parallax is not None
        self.assertFalse(parallax._rest_captured)

    def test_entity_added_during_play_captured(self) -> None:
        """Entity added after on_play gets rest captured on first update."""
        self._create_camera(x=0.0, y=0.0)
        self.system.on_play(self.world)
        # Add entity after on_play
        entity = self._create_entity("LateBg", x=300.0, y=150.0, motion_scale_x=1.0, motion_scale_y=1.0)
        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 50.0
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        parallax = entity.get_component(ParallaxLayer)
        assert parallax is not None
        self.assertTrue(parallax._rest_captured)
        self.assertEqual(parallax._rest_x, 300.0)
        # Should have moved with camera since motion_scale=1
        self.assertAlmostEqual(transform.x, 350.0)

    def test_camera_origin_not_zero(self) -> None:
        """Camera starting at non-zero position: deltas calculated from origin."""
        cam = self._create_camera(x=500.0, y=300.0)
        entity = self._create_entity("Bg", x=200.0, y=100.0, motion_scale_x=0.5, motion_scale_y=0.5)
        self.system.on_play(self.world)
        # Camera origin captured at (500,300)
        cam_transform = cam.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 600.0  # delta = +100
        cam_transform.y = 340.0  # delta = +40
        self.system.update(self.world, 0.016)
        transform = entity.get_component(Transform)
        assert transform is not None
        # motion_scale=0.5 → 200 + 100*0.5 = 250, 100 + 40*0.5 = 120
        self.assertAlmostEqual(transform.x, 250.0, places=4)
        self.assertAlmostEqual(transform.y, 120.0, places=4)


if __name__ == "__main__":
    unittest.main()
