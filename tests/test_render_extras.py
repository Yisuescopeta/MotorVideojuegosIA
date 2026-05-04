"""
tests/test_render_extras.py - Tests for DirectionalLight2D, ColorRect, ParallaxLayer, Canvas, BackBufferCopy, PostProcess.
"""
from __future__ import annotations

import unittest

from engine.components.backbuffer_copy import BackBufferCopy
from engine.components.canvas import Canvas
from engine.components.colorrect import ColorRect
from engine.components.directional_light_2d import DirectionalLight2D
from engine.components.parallax_layer import ParallaxLayer
from engine.ecs.component import Component
from engine.levels.component_registry import create_default_registry
from engine.rendering.post_process import BlurEffect, ColorCorrectEffect, PostProcessEffect


class TestDirectionalLight2D(unittest.TestCase):

    def test_defaults(self):
        light = DirectionalLight2D()
        self.assertTrue(light.enabled)
        self.assertEqual(light.color_r, 255)
        self.assertEqual(light.color_g, 255)
        self.assertEqual(light.color_b, 255)
        self.assertEqual(light.color_a, 255)
        self.assertEqual(light.energy, 1.0)
        self.assertEqual(light.max_distance, 500.0)
        self.assertEqual(light.direction_x, 0.0)
        self.assertEqual(light.direction_y, -1.0)
        self.assertEqual(light.blend_mode, "add")
        self.assertFalse(light.shadow_enabled)
        self.assertEqual(light.shadow_smooth, 0.0)
        self.assertEqual(light.z_min, -1024.0)
        self.assertEqual(light.z_max, 1024.0)

    def test_custom_values(self):
        light = DirectionalLight2D(
            color_r=128, color_g=64, color_b=32, color_a=200,
            energy=2.5, max_distance=300.0,
            direction_x=1.0, direction_y=0.5,
            blend_mode="sub", shadow_enabled=True,
            shadow_color_r=10, shadow_color_g=10, shadow_color_b=10, shadow_color_a=80,
            shadow_smooth=0.5, z_min=-500.0, z_max=500.0,
        )
        self.assertEqual(light.color_r, 128)
        self.assertEqual(light.energy, 2.5)
        self.assertEqual(light.max_distance, 300.0)
        self.assertEqual(light.direction_x, 1.0)
        self.assertEqual(light.blend_mode, "sub")
        self.assertTrue(light.shadow_enabled)
        self.assertEqual(light.shadow_color_r, 10)
        self.assertEqual(light.shadow_smooth, 0.5)
        self.assertEqual(light.z_min, -500.0)

    def test_clamped_values(self):
        light = DirectionalLight2D(color_r=300, energy=-1.0, max_distance=0.0, shadow_smooth=-0.5)
        self.assertEqual(light.color_r, 255)
        self.assertEqual(light.energy, 0.0)
        self.assertEqual(light.max_distance, 1.0)
        self.assertEqual(light.shadow_smooth, 0.0)

    def test_to_dict(self):
        light = DirectionalLight2D(energy=2.0, direction_x=0.5)
        data = light.to_dict()
        self.assertEqual(data["energy"], 2.0)
        self.assertEqual(data["direction_x"], 0.5)
        self.assertTrue(data["enabled"])

    def test_from_dict(self):
        data = {"enabled": False, "max_distance": 200.0, "blend_mode": "mix"}
        light = DirectionalLight2D.from_dict(data)
        self.assertFalse(light.enabled)
        self.assertEqual(light.max_distance, 200.0)
        self.assertEqual(light.blend_mode, "mix")

    def test_is_component(self):
        self.assertIsInstance(DirectionalLight2D(), Component)

    def test_serialization_roundtrip(self):
        original = DirectionalLight2D(direction_y=0.7, max_distance=400.0, shadow_enabled=True)
        restored = DirectionalLight2D.from_dict(original.to_dict())
        self.assertEqual(restored.direction_y, 0.7)
        self.assertEqual(restored.max_distance, 400.0)
        self.assertTrue(restored.shadow_enabled)
        self.assertEqual(restored.energy, original.energy)


class TestColorRect(unittest.TestCase):

    def test_defaults(self):
        rect = ColorRect()
        self.assertTrue(rect.enabled)
        self.assertEqual(rect.width, 100.0)
        self.assertEqual(rect.height, 100.0)
        self.assertEqual(rect.color, (255, 255, 255, 255))

    def test_custom_color(self):
        rect = ColorRect(width=200.0, height=50.0, color_r=255, color_g=0, color_b=0, color_a=128)
        self.assertEqual(rect.width, 200.0)
        self.assertEqual(rect.height, 50.0)
        self.assertEqual(rect.color, (255, 0, 0, 128))

    def test_to_dict(self):
        rect = ColorRect(width=64.0, height=64.0, color_r=0, color_g=255, color_b=0, color_a=200)
        data = rect.to_dict()
        self.assertEqual(data["width"], 64.0)
        self.assertEqual(data["color_r"], 0)
        self.assertEqual(data["color_g"], 255)

    def test_from_dict(self):
        data = {"enabled": False, "width": 128.0, "height": 256.0, "color_r": 0, "color_g": 0, "color_b": 255, "color_a": 255}
        rect = ColorRect.from_dict(data)
        self.assertFalse(rect.enabled)
        self.assertEqual(rect.width, 128.0)
        self.assertEqual(rect.color, (0, 0, 255, 255))

    def test_is_component(self):
        self.assertIsInstance(ColorRect(), Component)

    def test_serialization_roundtrip(self):
        original = ColorRect(width=50.0, height=30.0, color_r=100, color_g=200, color_b=50, color_a=180)
        restored = ColorRect.from_dict(original.to_dict())
        self.assertEqual(restored.width, 50.0)
        self.assertEqual(restored.color, (100, 200, 50, 180))


class TestParallaxLayerExtras(unittest.TestCase):

    def test_defaults_include_new_fields(self):
        layer = ParallaxLayer()
        self.assertEqual(layer.repeat_size_x, 0.0)
        self.assertEqual(layer.repeat_size_y, 0.0)
        self.assertEqual(layer.repeat_times, 1)

    def test_repeat_fields_in_to_dict(self):
        layer = ParallaxLayer(repeat_size_x=500.0, repeat_size_y=300.0, repeat_times=3)
        data = layer.to_dict()
        self.assertEqual(data["repeat_size_x"], 500.0)
        self.assertEqual(data["repeat_size_y"], 300.0)
        self.assertEqual(data["repeat_times"], 3)

    def test_repeat_fields_from_dict(self):
        data = {"repeat_size_x": 200.0, "repeat_size_y": 150.0, "repeat_times": 5}
        layer = ParallaxLayer.from_dict(data)
        self.assertEqual(layer.repeat_size_x, 200.0)
        self.assertEqual(layer.repeat_size_y, 150.0)
        self.assertEqual(layer.repeat_times, 5)

    def test_old_fields_still_work(self):
        layer = ParallaxLayer(motion_scale_x=0.5, autoscroll_x=2.0)
        data = layer.to_dict()
        self.assertEqual(data["motion_scale_x"], 0.5)
        self.assertEqual(data["autoscroll_x"], 2.0)

    def test_backward_compatible_from_dict(self):
        data = {"motion_scale_x": 0.3, "motion_scale_y": 0.6}
        layer = ParallaxLayer.from_dict(data)
        self.assertEqual(layer.motion_scale_x, 0.3)
        self.assertEqual(layer.repeat_size_x, 0.0)  # default for missing fields


class TestCanvasExtras(unittest.TestCase):

    def test_defaults_include_new_fields(self):
        canvas = Canvas()
        self.assertTrue(canvas.follow_viewport)
        self.assertEqual(canvas.follow_viewport_scale, 1.0)
        self.assertEqual(canvas.layer_transform_x, 0.0)
        self.assertEqual(canvas.layer_transform_y, 0.0)
        self.assertEqual(canvas.layer_rotation, 0.0)
        self.assertEqual(canvas.layer_scale_x, 1.0)
        self.assertEqual(canvas.layer_scale_y, 1.0)

    def test_new_fields_in_to_dict(self):
        canvas = Canvas(follow_viewport=False, layer_rotation=45.0,
                        layer_scale_x=2.0, layer_scale_y=0.5)
        data = canvas.to_dict()
        self.assertFalse(data["follow_viewport"])
        self.assertEqual(data["layer_rotation"], 45.0)
        self.assertEqual(data["layer_scale_x"], 2.0)
        self.assertEqual(data["layer_scale_y"], 0.5)

    def test_new_fields_from_dict(self):
        data = {"follow_viewport": False, "follow_viewport_scale": 0.5,
                "layer_transform_x": 100.0, "layer_transform_y": 200.0,
                "layer_rotation": 30.0}
        canvas = Canvas.from_dict(data)
        self.assertFalse(canvas.follow_viewport)
        self.assertEqual(canvas.follow_viewport_scale, 0.5)
        self.assertEqual(canvas.layer_transform_x, 100.0)
        self.assertEqual(canvas.layer_transform_y, 200.0)
        self.assertEqual(canvas.layer_rotation, 30.0)

    def test_backward_compatible_from_dict(self):
        data = {"render_mode": "world_space", "reference_width": 1024}
        canvas = Canvas.from_dict(data)
        self.assertEqual(canvas.render_mode, "world_space")
        self.assertEqual(canvas.follow_viewport, True)  # default


class TestBackBufferCopy(unittest.TestCase):

    def test_defaults(self):
        bb = BackBufferCopy()
        self.assertTrue(bb.enabled)
        self.assertEqual(bb.copy_mode, "rect")
        self.assertEqual(bb.rect_x, 0.0)
        self.assertEqual(bb.rect_y, 0.0)
        self.assertEqual(bb.rect_w, 128.0)
        self.assertEqual(bb.rect_h, 128.0)

    def test_viewport_mode(self):
        bb = BackBufferCopy(copy_mode="viewport")
        self.assertEqual(bb.copy_mode, "viewport")

    def test_custom_rect(self):
        bb = BackBufferCopy(rect_x=10.0, rect_y=20.0, rect_w=256.0, rect_h=512.0)
        self.assertEqual(bb.rect_x, 10.0)
        self.assertEqual(bb.rect_w, 256.0)

    def test_to_dict(self):
        bb = BackBufferCopy(copy_mode="viewport", rect_w=64.0)
        data = bb.to_dict()
        self.assertEqual(data["copy_mode"], "viewport")
        self.assertEqual(data["rect_w"], 64.0)

    def test_from_dict(self):
        data = {"enabled": False, "copy_mode": "rect", "rect_x": 5.0, "rect_y": 5.0, "rect_w": 32.0, "rect_h": 32.0}
        bb = BackBufferCopy.from_dict(data)
        self.assertFalse(bb.enabled)
        self.assertEqual(bb.rect_x, 5.0)
        self.assertEqual(bb.rect_h, 32.0)

    def test_is_component(self):
        self.assertIsInstance(BackBufferCopy(), Component)


class TestPostProcessEffect(unittest.TestCase):

    def test_base_effect(self):
        effect = PostProcessEffect(name="Test", enabled=True)
        self.assertEqual(effect.name, "Test")
        self.assertTrue(effect.enabled)
        data = effect.to_dict()
        self.assertEqual(data["type"], "PostProcessEffect")

    def test_blur_defaults(self):
        blur = BlurEffect()
        self.assertEqual(blur.name, "Blur")
        self.assertEqual(blur.radius, 4.0)
        self.assertTrue(blur.enabled)

    def test_blur_custom(self):
        blur = BlurEffect(radius=8.0, name="HeavyBlur", enabled=False)
        self.assertEqual(blur.radius, 8.0)
        self.assertEqual(blur.name, "HeavyBlur")
        self.assertFalse(blur.enabled)

    def test_blur_to_dict(self):
        blur = BlurEffect(radius=2.5)
        data = blur.to_dict()
        self.assertEqual(data["type"], "BlurEffect")
        self.assertEqual(data["radius"], 2.5)

    def test_blur_from_dict(self):
        data = {"radius": 6.0, "name": "Custom", "enabled": False}
        blur = BlurEffect.from_dict(data)
        self.assertEqual(blur.radius, 6.0)
        self.assertEqual(blur.name, "Custom")

    def test_color_correct_defaults(self):
        cc = ColorCorrectEffect()
        self.assertEqual(cc.name, "ColorCorrect")
        self.assertEqual(cc.brightness, 1.0)
        self.assertEqual(cc.contrast, 1.0)
        self.assertEqual(cc.saturation, 1.0)

    def test_color_correct_custom(self):
        cc = ColorCorrectEffect(brightness=1.2, contrast=0.8, saturation=1.5)
        self.assertEqual(cc.brightness, 1.2)
        self.assertEqual(cc.contrast, 0.8)
        self.assertEqual(cc.saturation, 1.5)

    def test_color_correct_to_dict(self):
        cc = ColorCorrectEffect(brightness=1.1, contrast=1.3)
        data = cc.to_dict()
        self.assertEqual(data["type"], "ColorCorrectEffect")
        self.assertEqual(data["brightness"], 1.1)
        self.assertEqual(data["contrast"], 1.3)

    def test_color_correct_from_dict(self):
        data = {"brightness": 0.9, "contrast": 1.1, "saturation": 1.4, "enabled": False}
        cc = ColorCorrectEffect.from_dict(data)
        self.assertEqual(cc.brightness, 0.9)
        self.assertEqual(cc.saturation, 1.4)
        self.assertFalse(cc.enabled)


class TestComponentRegistryIntegration(unittest.TestCase):

    def setUp(self):
        self.registry = create_default_registry()

    def test_directional_light_registered(self):
        cls = self.registry.get("DirectionalLight2D")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, DirectionalLight2D)

    def test_color_rect_registered(self):
        cls = self.registry.get("ColorRect")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, ColorRect)

    def test_backbuffer_copy_registered(self):
        cls = self.registry.get("BackBufferCopy")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, BackBufferCopy)

    def test_directional_light_create(self):
        data = {"enabled": True, "energy": 3.0, "max_distance": 150.0}
        instance = self.registry.create("DirectionalLight2D", data)
        self.assertIsInstance(instance, DirectionalLight2D)
        self.assertEqual(instance.energy, 3.0)

    def test_color_rect_create(self):
        data = {"width": 50.0, "height": 50.0, "color_r": 255, "color_g": 0, "color_b": 0, "color_a": 255}
        instance = self.registry.create("ColorRect", data)
        self.assertIsInstance(instance, ColorRect)
        self.assertEqual(instance.color, (255, 0, 0, 255))

    def test_backbuffer_copy_create(self):
        data = {"copy_mode": "viewport", "rect_w": 256.0}
        instance = self.registry.create("BackBufferCopy", data)
        self.assertIsInstance(instance, BackBufferCopy)
        self.assertEqual(instance.copy_mode, "viewport")

    def test_parallax_descriptor_includes_new_fields(self):
        descriptor = self.registry.get_descriptor("ParallaxLayer")
        self.assertIsNotNone(descriptor)
        payload = descriptor.default_payload
        self.assertIn("repeat_size_x", payload)
        self.assertIn("repeat_times", payload)


if __name__ == "__main__":
    unittest.main()
