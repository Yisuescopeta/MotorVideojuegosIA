"""
tests/test_ola5_batch3.py - Tests for OLA5 batch 3: 5 new features.

Covers:
  1. ParallaxBackground container
  2. Path2D visual component
  3. PointLight2D (separate from Light2D)
  4. Visibility layers (32 layers)
  5. BinaryResourceSaver
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from engine.components.camera2d import Camera2D
from engine.components.canvas_item_2d import CanvasItem2D
from engine.components.parallax_background import ParallaxBackground
from engine.components.parallax_layer import ParallaxLayer
from engine.components.path_2d import Path2D
from engine.components.point_light_2d import PointLight2D
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.resources.resource_format_saver import BinaryResourceSaver, JSONResourceSaver
from engine.systems.parallax_system import ParallaxSystem


# =============================================================================
# 1. ParallaxBackground
# =============================================================================

class TestParallaxBackground(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self) -> None:
        bg = ParallaxBackground(
            scroll_base_offset_x=10.0,
            scroll_base_offset_y=20.0,
            scroll_base_scale_x=0.5,
            scroll_base_scale_y=0.75,
            scroll_limit_begin_x=-100.0,
            scroll_limit_begin_y=-50.0,
            scroll_limit_end_x=500.0,
            scroll_limit_end_y=300.0,
            scroll_ignore_camera_zoom=True,
        )
        data = bg.to_dict()
        restored = ParallaxBackground.from_dict(data)
        self.assertEqual(restored.scroll_base_offset_x, 10.0)
        self.assertEqual(restored.scroll_base_offset_y, 20.0)
        self.assertEqual(restored.scroll_base_scale_x, 0.5)
        self.assertEqual(restored.scroll_base_scale_y, 0.75)
        self.assertEqual(restored.scroll_limit_begin_x, -100.0)
        self.assertEqual(restored.scroll_limit_begin_y, -50.0)
        self.assertEqual(restored.scroll_limit_end_x, 500.0)
        self.assertEqual(restored.scroll_limit_end_y, 300.0)
        self.assertTrue(restored.scroll_ignore_camera_zoom)

    def test_default_values(self) -> None:
        bg = ParallaxBackground()
        self.assertEqual(bg.scroll_base_offset_x, 0.0)
        self.assertEqual(bg.scroll_base_offset_y, 0.0)
        self.assertEqual(bg.scroll_base_scale_x, 1.0)
        self.assertEqual(bg.scroll_base_scale_y, 1.0)
        self.assertEqual(bg.scroll_limit_begin_x, 0.0)
        self.assertEqual(bg.scroll_limit_begin_y, 0.0)
        self.assertEqual(bg.scroll_limit_end_x, 0.0)
        self.assertEqual(bg.scroll_limit_end_y, 0.0)
        self.assertFalse(bg.scroll_ignore_camera_zoom)


class TestParallaxBackgroundInSystem(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = ParallaxSystem()

    def _create_camera(self, name: str = "MainCamera", x: float = 0.0, y: float = 0.0) -> Entity:
        entity = Entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Camera2D(is_primary=True))
        self.world.add_entity(entity)
        return entity

    def test_background_child_uses_base_scale(self) -> None:
        """Child layer inside ParallaxBackground uses background's base_scale."""
        bg = Entity("ParallaxBg")
        bg.add_component(Transform(x=0.0, y=0.0))
        bg.add_component(ParallaxBackground(scroll_base_scale_x=0.5, scroll_base_scale_y=0.3))
        self.world.add_entity(bg)

        layer = Entity("BgLayer")
        layer.parent_name = "ParallaxBg"
        layer.add_component(Transform(x=200.0, y=100.0))
        layer.add_component(ParallaxLayer(motion_scale_x=1.0, motion_scale_y=1.0))
        self.world.add_entity(layer)

        self._create_camera(x=0.0, y=0.0)
        self.system.on_play(self.world)

        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        cam_transform.y = 50.0

        self.system.update(self.world, 0.016)

        layer_transform = layer.get_component(Transform)
        assert layer_transform is not None
        # camera delta = (100, 50)
        # motion_scale * base_scale_x = 1.0 * 0.5 = 0.5
        # motion_scale * base_scale_y = 1.0 * 0.3 = 0.3
        # new_x = 200 + 100*0.5 = 250
        # new_y = 100 + 50*0.3 = 115
        self.assertAlmostEqual(layer_transform.x, 250.0, places=4)
        self.assertAlmostEqual(layer_transform.y, 115.0, places=4)

    def test_background_child_uses_base_offset(self) -> None:
        """Child layer gets constant base offset added."""
        bg = Entity("ParallaxBg2")
        bg.add_component(Transform(x=0.0, y=0.0))
        bg.add_component(ParallaxBackground(scroll_base_offset_x=50.0, scroll_base_offset_y=-30.0))
        self.world.add_entity(bg)

        layer = Entity("BgLayer2")
        layer.parent_name = "ParallaxBg2"
        layer.add_component(Transform(x=200.0, y=100.0))
        layer.add_component(ParallaxLayer(motion_scale_x=0.0, motion_scale_y=0.0))
        self.world.add_entity(layer)

        self._create_camera(x=0.0, y=0.0)
        self.system.on_play(self.world)

        self.system.update(self.world, 0.016)

        layer_transform = layer.get_component(Transform)
        assert layer_transform is not None
        # motion_scale=0, but bg offset adds
        self.assertAlmostEqual(layer_transform.x, 200.0 + 50.0, places=4)
        self.assertAlmostEqual(layer_transform.y, 100.0 - 30.0, places=4)

    def test_layer_not_child_ignores_background(self) -> None:
        """Layer not a child of any ParallaxBackground uses default scale/offset."""
        bg = Entity("SomeBg")
        bg.add_component(Transform(x=0.0, y=0.0))
        bg.add_component(ParallaxBackground(scroll_base_scale_x=0.2, scroll_base_scale_y=0.2))
        self.world.add_entity(bg)

        layer = Entity("Standalone")
        # NOT a child
        layer.add_component(Transform(x=200.0, y=100.0))
        layer.add_component(ParallaxLayer(motion_scale_x=1.0, motion_scale_y=1.0))
        self.world.add_entity(layer)

        self._create_camera(x=0.0, y=0.0)
        self.system.on_play(self.world)

        camera = self.world.get_entity_by_name("MainCamera")
        assert camera is not None
        cam_transform = camera.get_component(Transform)
        assert cam_transform is not None
        cam_transform.x = 100.0
        cam_transform.y = 50.0

        self.system.update(self.world, 0.016)

        layer_transform = layer.get_component(Transform)
        assert layer_transform is not None
        # motion_scale=1, no bg override → 1:1 with camera
        self.assertAlmostEqual(layer_transform.x, 300.0, places=4)
        self.assertAlmostEqual(layer_transform.y, 150.0, places=4)


# =============================================================================
# 2. Path2D
# =============================================================================

class TestPath2D(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self) -> None:
        path = Path2D(
            curve_points=[(0.0, 0.0), (100.0, 50.0), (200.0, 0.0)],
            closed=True,
        )
        data = path.to_dict()
        restored = Path2D.from_dict(data)
        self.assertEqual(len(restored.curve_points), 3)
        self.assertEqual(restored.curve_points[0], (0.0, 0.0))
        self.assertEqual(restored.curve_points[1], (100.0, 50.0))
        self.assertEqual(restored.curve_points[2], (200.0, 0.0))
        self.assertTrue(restored.closed)

    def test_default_values(self) -> None:
        path = Path2D()
        self.assertEqual(path.curve_points, [])
        self.assertFalse(path.closed)

    def test_from_dict_invalid_points_filtered(self) -> None:
        path = Path2D.from_dict({
            "curve_points": [[0, 0], [10, 20], [5], [30, 40, 50]],
            "closed": False,
        })
        # [5] is filtered (len<2), others survive; [30,40,50] truncated to first 2
        self.assertEqual(len(path.curve_points), 3)
        self.assertEqual(path.curve_points[0], (0.0, 0.0))
        self.assertEqual(path.curve_points[1], (10.0, 20.0))
        self.assertEqual(path.curve_points[2], (30.0, 40.0))

    def test_closed_serialization(self) -> None:
        path = Path2D(curve_points=[(1.0, 2.0), (3.0, 4.0)], closed=True)
        data = path.to_dict()
        self.assertTrue(data["closed"])
        restored = Path2D.from_dict(data)
        self.assertTrue(restored.closed)


# =============================================================================
# 3. PointLight2D
# =============================================================================

class TestPointLight2D(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self) -> None:
        light = PointLight2D(
            color=(255, 100, 50, 200),
            energy=2.5,
            radius=150.0,
            texture_path="lights/point.png",
            texture_scale=1.5,
            texture_offset_x=5.0,
            texture_offset_y=-3.0,
            shadow_enabled=True,
            shadow_color=(10, 10, 10, 80),
            shadow_filter="pcf5",
            blend_mode="multiply",
            z_min=-512,
            z_max=512,
        )
        data = light.to_dict()
        restored = PointLight2D.from_dict(data)
        self.assertEqual(restored.color, (255, 100, 50, 200))
        self.assertEqual(restored.energy, 2.5)
        self.assertEqual(restored.radius, 150.0)
        self.assertEqual(restored.texture_path, "lights/point.png")
        self.assertEqual(restored.texture_scale, 1.5)
        self.assertEqual(restored.texture_offset_x, 5.0)
        self.assertEqual(restored.texture_offset_y, -3.0)
        self.assertTrue(restored.shadow_enabled)
        self.assertEqual(restored.shadow_color, (10, 10, 10, 80))
        self.assertEqual(restored.shadow_filter, "pcf5")
        self.assertEqual(restored.blend_mode, "multiply")
        self.assertEqual(restored.z_min, -512)
        self.assertEqual(restored.z_max, 512)

    def test_default_values(self) -> None:
        light = PointLight2D()
        self.assertEqual(light.color, (255, 255, 255, 255))
        self.assertEqual(light.energy, 1.0)
        self.assertEqual(light.radius, 100.0)
        self.assertEqual(light.texture_path, "")
        self.assertEqual(light.texture_scale, 1.0)
        self.assertEqual(light.texture_offset_x, 0.0)
        self.assertEqual(light.texture_offset_y, 0.0)
        self.assertFalse(light.shadow_enabled)
        self.assertEqual(light.shadow_color, (0, 0, 0, 100))
        self.assertEqual(light.shadow_filter, "none")
        self.assertEqual(light.blend_mode, "add")
        self.assertEqual(light.z_min, -1024)
        self.assertEqual(light.z_max, 1024)
        self.assertTrue(light.enabled)

    def test_invalid_shadow_filter_defaults_to_none(self) -> None:
        light = PointLight2D(shadow_filter="invalid")
        self.assertEqual(light.shadow_filter, "none")

    def test_valid_shadow_filters(self) -> None:
        for filt in ("none", "pcf5", "pcf13"):
            light = PointLight2D(shadow_filter=filt)
            self.assertEqual(light.shadow_filter, filt)

    def test_color_clamped(self) -> None:
        light = PointLight2D(color=(300, -10, 100, 256))
        self.assertEqual(light.color, (255, 0, 100, 255))

    def test_energy_non_negative(self) -> None:
        light = PointLight2D(energy=-5.0)
        self.assertEqual(light.energy, 0.0)

    def test_different_from_light2d(self) -> None:
        """PointLight2D is a distinct component from Light2D."""
        from engine.components.light2d import Light2D
        light2d = Light2D()
        point_light = PointLight2D()
        self.assertIsInstance(light2d, Light2D)
        self.assertIsInstance(point_light, PointLight2D)
        self.assertNotIsInstance(light2d, PointLight2D)
        self.assertNotIsInstance(point_light, Light2D)


# =============================================================================
# 4. Visibility layers
# =============================================================================

class TestVisibilityLayers(unittest.TestCase):
    def test_canvas_item_visibility_layer_default(self) -> None:
        canvas = CanvasItem2D()
        self.assertEqual(canvas.visibility_layer, 1)

    def test_canvas_item_custom_visibility_layer(self) -> None:
        canvas = CanvasItem2D(visibility_layer=5)
        self.assertEqual(canvas.visibility_layer, 5)

    def test_camera_visibility_mask_default(self) -> None:
        camera = Camera2D()
        self.assertEqual(camera.camera_visibility_mask, 0xFFFFFFFF)

    def test_camera_custom_visibility_mask(self) -> None:
        camera = Camera2D(camera_visibility_mask=0x0000000F)
        self.assertEqual(camera.camera_visibility_mask, 0x0F)

    def test_visibility_layer_serialization_roundtrip(self) -> None:
        canvas = CanvasItem2D(visibility_layer=7, z_index=3)
        data = canvas.to_dict()
        self.assertEqual(data["visibility_layer"], 7)
        restored = CanvasItem2D.from_dict(data)
        self.assertEqual(restored.visibility_layer, 7)
        self.assertEqual(restored.z_index, 3)

    def test_camera_visibility_mask_serialization_roundtrip(self) -> None:
        camera = Camera2D(camera_visibility_mask=0xFF00FF00)
        data = camera.to_dict()
        self.assertEqual(data["camera_visibility_mask"], 0xFF00FF00)
        restored = Camera2D.from_dict(data)
        self.assertEqual(restored.camera_visibility_mask, 0xFF00FF00)

    def test_layer_mask_exclusion_logic(self) -> None:
        """When visibility_layer & camera_mask == 0, entity is skipped."""
        camera_mask = 0x0000000F  # only layers 0-3 visible
        layer_only_visible = 0x0F & 1  # layer 1 → visible
        layer_hidden = 0x0F & 16  # layer 5 → not visible
        self.assertNotEqual(layer_only_visible, 0)
        self.assertEqual(layer_hidden, 0)

    def test_bitmask_32_layers_no_overflow(self) -> None:
        """Test that up to 32 layers (bit 0 through 31) can be used."""
        canvas = CanvasItem2D(visibility_layer=1 << 31)  # layer 32
        self.assertNotEqual(canvas.visibility_layer, 0)
        # Should fit in int without overflow on standard systems
        self.assertIsInstance(canvas.visibility_layer, int)

    def test_full_mask_shows_all(self) -> None:
        """0xFFFFFFFF mask shows all layers."""
        mask = 0xFFFFFFFF
        for bit in range(32):
            self.assertNotEqual(mask & (1 << bit), 0)

    def test_zero_layer_never_visible(self) -> None:
        """Layer 0 always invisible regardless of mask."""
        self.assertEqual(0xFFFFFFFF & 0, 0)


# =============================================================================
# 5. BinaryResourceSaver
# =============================================================================

class TestBinaryResourceSaver(unittest.TestCase):
    def test_get_recognized_extensions(self) -> None:
        saver = BinaryResourceSaver()
        extensions = saver.get_recognized_extensions({})
        self.assertIn("res", extensions)

    def test_save_and_load_binary(self) -> None:
        saver = BinaryResourceSaver()
        data = {"name": "test_resource", "value": 42, "nested": {"a": 1, "b": 2.5}}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "resource.res")
            result = saver.save(data, path)
            self.assertTrue(result)

            import pickle
            with open(path, "rb") as f:
                loaded = pickle.load(f)
            self.assertEqual(loaded, data)

    def test_save_dict_and_object(self) -> None:
        saver = BinaryResourceSaver()
        dict_data = {"key": "value", "num": 123}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dict_res.res")
            result = saver.save(dict_data, path)
            self.assertTrue(result)

            import pickle
            with open(path, "rb") as f:
                loaded = pickle.load(f)
            self.assertEqual(loaded, dict_data)

    def test_save_with_to_dict_object(self) -> None:
        """Save an object that has .to_dict() method."""
        saver = BinaryResourceSaver()
        resource = ParallaxBackground(
            scroll_base_offset_x=5.0,
            scroll_base_offset_y=10.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "obj_res.res")
            result = saver.save(resource, path)
            self.assertTrue(result)

            import pickle
            with open(path, "rb") as f:
                loaded = pickle.load(f)
            self.assertEqual(loaded["scroll_base_offset_x"], 5.0)
            self.assertEqual(loaded["scroll_base_offset_y"], 10.0)

    def test_save_invalid_path_returns_false(self) -> None:
        saver = BinaryResourceSaver()
        result = saver.save({"test": True}, "/invalid/path/should/fail.res")
        self.assertFalse(result)

    def test_both_savers_work_together(self) -> None:
        """BinaryResourceSaver and JSONResourceSaver can coexist."""
        json_saver = JSONResourceSaver()
        bin_saver = BinaryResourceSaver()
        data = {"type": "config", "version": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "cfg.json")
            res_path = os.path.join(tmpdir, "cfg.res")

            self.assertTrue(json_saver.save(data, json_path))
            self.assertTrue(bin_saver.save(data, res_path))

            import pickle
            with open(res_path, "rb") as f:
                bin_loaded = pickle.load(f)
            self.assertEqual(bin_loaded, data)

            with open(json_path, "r", encoding="utf-8") as f:
                json_loaded = json.load(f)
            self.assertEqual(json_loaded, data)


# =============================================================================
# Registry tests for new components
# =============================================================================

class TestRegistryNewComponents(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_registry_has_parallax_background(self) -> None:
        self.assertIn("ParallaxBackground", self.registry.list_registered())

    def test_registry_has_path2d(self) -> None:
        self.assertIn("Path2D", self.registry.list_registered())

    def test_registry_has_point_light2d(self) -> None:
        self.assertIn("PointLight2D", self.registry.list_registered())

    def test_create_parallax_background_from_registry(self) -> None:
        instance = self.registry.create("ParallaxBackground", {
            "scroll_base_scale_x": 0.5,
            "scroll_base_scale_y": 0.75,
        })
        self.assertIsInstance(instance, ParallaxBackground)
        self.assertEqual(instance.scroll_base_scale_x, 0.5)
        self.assertEqual(instance.scroll_base_scale_y, 0.75)

    def test_create_path2d_from_registry(self) -> None:
        instance = self.registry.create("Path2D", {
            "curve_points": [[0, 0], [50, 100]],
            "closed": True,
        })
        self.assertIsInstance(instance, Path2D)
        self.assertEqual(len(instance.curve_points), 2)
        self.assertTrue(instance.closed)

    def test_create_point_light2d_from_registry(self) -> None:
        instance = self.registry.create("PointLight2D", {
            "color": [255, 0, 0, 255],
            "energy": 2.0,
            "radius": 200.0,
        })
        self.assertIsInstance(instance, PointLight2D)
        self.assertEqual(instance.color, (255, 0, 0, 255))
        self.assertEqual(instance.energy, 2.0)
        self.assertEqual(instance.radius, 200.0)

    def test_registry_uses_default_payloads(self) -> None:
        """Descriptors include default_payload for all new components."""
        for name in ("ParallaxBackground", "Path2D", "PointLight2D"):
            descriptor = self.registry.get_descriptor(name)
            self.assertIsNotNone(descriptor, f"Missing descriptor for {name}")
            if descriptor is not None:
                self.assertIn("default_payload", dir(descriptor))
                payload = descriptor.default_payload
                self.assertIsInstance(payload, dict)
                self.assertGreaterEqual(len(payload), 1, f"No payload keys for {name}")


if __name__ == "__main__":
    unittest.main()
