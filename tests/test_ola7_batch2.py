"""
tests/test_ola7_batch2.py - Tests for SubViewport, ViewportTexture, ViewportRenderer,
BackBufferCopy capture, PostProcessPipeline.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from engine.components.backbuffer_copy import BackBufferCopy
from engine.components.post_process_effect import PostProcessEffectComp
from engine.components.sprite import Sprite
from engine.components.sub_viewport import SubViewport, ViewportTexture
from engine.components.transform import Transform
from engine.ecs.component import Component
from engine.ecs.world import World
from engine.levels.component_registry import ComponentRegistry, create_default_registry
from engine.rendering.post_process import (
    BlurEffect,
    ColorCorrectEffect,
    PostProcessEffect,
    PostProcessPipeline,
)
from engine.rendering.viewport_renderer import ViewportRenderer


# ---------------------------------------------------------------------------
# SubViewport component tests
# ---------------------------------------------------------------------------

class TestSubViewportComponent(unittest.TestCase):

    def test_defaults(self):
        vp = SubViewport()
        self.assertTrue(vp.enabled)
        self.assertEqual(vp.size_x, 512)
        self.assertEqual(vp.size_y, 512)
        self.assertTrue(vp.transparent_bg)
        self.assertFalse(vp.own_world_2d)
        self.assertEqual(vp.render_target_update_mode, "always")
        self.assertTrue(vp.needs_update)

    def test_custom_values(self):
        vp = SubViewport(
            size_x=256, size_y=128, transparent_bg=False,
            own_world_2d=True, render_target_update_mode="once",
        )
        self.assertEqual(vp.size_x, 256)
        self.assertEqual(vp.size_y, 128)
        self.assertFalse(vp.transparent_bg)
        self.assertTrue(vp.own_world_2d)
        self.assertEqual(vp.render_target_update_mode, "once")
        self.assertTrue(vp.needs_update)

    def test_needs_update_setter(self):
        vp = SubViewport()
        self.assertTrue(vp.needs_update)
        vp.needs_update = False
        self.assertFalse(vp.needs_update)
        vp.needs_update = True
        self.assertTrue(vp.needs_update)

    def test_size_clamp(self):
        vp = SubViewport(size_x=0, size_y=-5)
        self.assertEqual(vp.size_x, 1)
        self.assertEqual(vp.size_y, 1)

    def test_to_dict(self):
        vp = SubViewport(size_x=300, transparent_bg=False)
        data = vp.to_dict()
        self.assertEqual(data["size_x"], 300)
        self.assertEqual(data["size_y"], 512)
        self.assertFalse(data["transparent_bg"])
        self.assertEqual(data["render_target_update_mode"], "always")

    def test_from_dict(self):
        vp = SubViewport.from_dict({"size_x": 200, "size_y": 100, "transparent_bg": False, "render_target_update_mode": "once"})
        self.assertEqual(vp.size_x, 200)
        self.assertEqual(vp.size_y, 100)
        self.assertFalse(vp.transparent_bg)
        self.assertEqual(vp.render_target_update_mode, "once")

    def test_is_component(self):
        vp = SubViewport()
        self.assertIsInstance(vp, Component)


# ---------------------------------------------------------------------------
# ViewportTexture component tests
# ---------------------------------------------------------------------------

class TestViewportTextureComponent(unittest.TestCase):

    def test_defaults(self):
        vt = ViewportTexture()
        self.assertTrue(vt.enabled)
        self.assertEqual(vt.viewport_entity, "")

    def test_custom_viewport_entity(self):
        vt = ViewportTexture(viewport_entity="my_vp")
        self.assertEqual(vt.viewport_entity, "my_vp")

    def test_to_dict(self):
        vt = ViewportTexture(viewport_entity="vp_main")
        data = vt.to_dict()
        self.assertEqual(data["viewport_entity"], "vp_main")
        self.assertTrue(data["enabled"])

    def test_from_dict(self):
        vt = ViewportTexture.from_dict({"viewport_entity": "vp_a", "enabled": False})
        self.assertEqual(vt.viewport_entity, "vp_a")
        self.assertFalse(vt.enabled)

    def test_is_component(self):
        vt = ViewportTexture()
        self.assertIsInstance(vt, Component)


# ---------------------------------------------------------------------------
# ViewportRenderer tests (mocked)
# ---------------------------------------------------------------------------

class TestViewportRenderer(unittest.TestCase):

    def setUp(self):
        self.renderer = ViewportRenderer()

    def tearDown(self):
        self.renderer.cleanup()

    def test_initial_state(self):
        self.assertEqual(self.renderer._viewports, {})
        self.assertEqual(self.renderer._dirty, set())

    def test_get_or_create_texture_no_backend(self):
        tex = self.renderer.get_or_create_texture("test_vp", 320, 240)
        self.assertIsNotNone(tex)
        self.assertIsNone(self.renderer.get_texture("test_vp"))
        self.assertIsNotNone(self.renderer.get_dimensions("test_vp"))
        self.assertEqual(self.renderer.get_dimensions("test_vp"), (320, 240))

    def test_get_or_create_texture_same_dimensions(self):
        t1 = self.renderer.get_or_create_texture("vp1", 400, 300)
        t2 = self.renderer.get_or_create_texture("vp1", 400, 300)
        self.assertIs(t1, t2)

    @patch("pyray.is_window_ready", return_value=True)
    @patch("pyray.load_render_texture")
    def test_get_or_create_texture_with_backend(self, mock_load, mock_ready):
        mock_rt = MagicMock()
        mock_rt.texture.width = 512
        mock_rt.texture.height = 256
        mock_load.return_value = mock_rt

        tex = self.renderer.get_or_create_texture("vp_real", 512, 256)
        mock_load.assert_called_once()
        self.assertIs(tex, mock_rt)

    def test_begin_end_render_no_backend(self):
        self.renderer.get_or_create_texture("v", 100, 100)
        # Should not raise
        self.renderer.begin_render("v")
        self.renderer.end_render("v")

    def test_mark_dirty(self):
        self.renderer.mark_dirty("vp1")
        self.assertTrue(self.renderer.is_dirty("vp1"))
        self.renderer.clear_dirty("vp1")
        self.assertFalse(self.renderer.is_dirty("vp1"))

    def test_remove(self):
        self.renderer.get_or_create_texture("rm_vp", 200, 200)
        self.renderer.remove("rm_vp")
        self.assertIsNone(self.renderer.get_texture("rm_vp"))

    def test_cleanup_clears_all(self):
        self.renderer.get_or_create_texture("a", 10, 10)
        self.renderer.get_or_create_texture("b", 10, 10)
        self.renderer.mark_dirty("a")
        self.renderer.cleanup()
        self.assertEqual(self.renderer._viewports, {})
        self.assertEqual(self.renderer._dirty, set())


# ---------------------------------------------------------------------------
# BackBufferCopy component tests
# ---------------------------------------------------------------------------

class TestBackBufferCopyComponent(unittest.TestCase):

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

    def test_clamp_rect_size(self):
        bb = BackBufferCopy(rect_w=0, rect_h=-5)
        self.assertEqual(bb.rect_w, 1.0)
        self.assertEqual(bb.rect_h, 1.0)

    def test_to_dict(self):
        bb = BackBufferCopy(copy_mode="viewport", rect_w=256)
        data = bb.to_dict()
        self.assertEqual(data["copy_mode"], "viewport")
        self.assertEqual(data["rect_w"], 256.0)

    def test_from_dict(self):
        bb = BackBufferCopy.from_dict({
            "copy_mode": "viewport", "rect_x": 10.0, "rect_y": 20.0,
            "rect_w": 300.0, "rect_h": 200.0, "enabled": False,
        })
        self.assertEqual(bb.copy_mode, "viewport")
        self.assertEqual(bb.rect_x, 10.0)
        self.assertEqual(bb.rect_y, 20.0)
        self.assertEqual(bb.rect_w, 300.0)
        self.assertEqual(bb.rect_h, 200.0)
        self.assertFalse(bb.enabled)

    def test_copy_mode_constants(self):
        self.assertEqual(BackBufferCopy.COPY_MODE_RECT, "rect")
        self.assertEqual(BackBufferCopy.COPY_MODE_VIEWPORT, "viewport")


# ---------------------------------------------------------------------------
# PostProcessEffect tests
# ---------------------------------------------------------------------------

class TestPostProcessEffectBase(unittest.TestCase):

    def test_defaults(self):
        effect = PostProcessEffect(name="Test", enabled=True)
        self.assertEqual(effect.name, "Test")
        self.assertTrue(effect.enabled)

    def test_name_defaults_to_class_name(self):
        effect = PostProcessEffect()
        self.assertEqual(effect.name, "PostProcessEffect")

    def test_to_dict(self):
        effect = PostProcessEffect(name="FX", enabled=False)
        data = effect.to_dict()
        self.assertEqual(data["name"], "FX")
        self.assertFalse(data["enabled"])
        self.assertEqual(data["type"], "PostProcessEffect")

    def test_from_dict(self):
        effect = PostProcessEffect.from_dict({"name": "FX", "enabled": False})
        self.assertEqual(effect.name, "FX")
        self.assertFalse(effect.enabled)


class TestBlurEffect(unittest.TestCase):

    def test_defaults(self):
        blur = BlurEffect()
        self.assertEqual(blur.name, "Blur")
        self.assertEqual(blur.radius, 4.0)
        self.assertTrue(blur.enabled)

    def test_radius_clamp(self):
        blur = BlurEffect(radius=-5.0)
        self.assertEqual(blur.radius, 0.0)

    def test_custom_values(self):
        blur = BlurEffect(radius=8.0, name="HeavyBlur", enabled=False)
        self.assertEqual(blur.radius, 8.0)
        self.assertEqual(blur.name, "HeavyBlur")
        self.assertFalse(blur.enabled)

    def test_to_dict(self):
        blur = BlurEffect(radius=2.5)
        data = blur.to_dict()
        self.assertEqual(data["radius"], 2.5)
        self.assertEqual(data["type"], "BlurEffect")

    def test_from_dict(self):
        blur = BlurEffect.from_dict({"radius": 10.0, "name": "B", "enabled": False})
        self.assertEqual(blur.radius, 10.0)
        self.assertEqual(blur.name, "B")
        self.assertFalse(blur.enabled)


class TestColorCorrectEffect(unittest.TestCase):

    def test_defaults(self):
        cc = ColorCorrectEffect()
        self.assertEqual(cc.name, "ColorCorrect")
        self.assertEqual(cc.brightness, 1.0)
        self.assertEqual(cc.contrast, 1.0)
        self.assertEqual(cc.saturation, 1.0)
        self.assertTrue(cc.enabled)

    def test_clamp(self):
        cc = ColorCorrectEffect(brightness=-1.0)
        self.assertEqual(cc.brightness, 0.0)

    def test_custom_values(self):
        cc = ColorCorrectEffect(brightness=1.2, contrast=0.8, saturation=1.5)
        self.assertEqual(cc.brightness, 1.2)
        self.assertEqual(cc.contrast, 0.8)
        self.assertEqual(cc.saturation, 1.5)

    def test_to_dict(self):
        cc = ColorCorrectEffect(brightness=1.1, contrast=1.3)
        data = cc.to_dict()
        self.assertEqual(data["brightness"], 1.1)
        self.assertEqual(data["contrast"], 1.3)
        self.assertEqual(data["type"], "ColorCorrectEffect")

    def test_from_dict(self):
        cc = ColorCorrectEffect.from_dict({
            "brightness": 1.5, "contrast": 0.5, "saturation": 2.0,
            "name": "CC", "enabled": False,
        })
        self.assertEqual(cc.brightness, 1.5)
        self.assertEqual(cc.contrast, 0.5)
        self.assertEqual(cc.saturation, 2.0)
        self.assertFalse(cc.enabled)


# ---------------------------------------------------------------------------
# PostProcessPipeline tests (mocked raylib)
# ---------------------------------------------------------------------------

class TestPostProcessPipeline(unittest.TestCase):

    def setUp(self):
        self.pipeline = PostProcessPipeline()

    def tearDown(self):
        self.pipeline.cleanup()

    def test_initial_empty(self):
        self.assertEqual(self.pipeline.effects, [])

    def test_add_effect(self):
        blur = BlurEffect(radius=5.0)
        self.pipeline.add_effect(blur)
        self.assertEqual(len(self.pipeline.effects), 1)

    def test_clear_effects(self):
        self.pipeline.add_effect(BlurEffect())
        self.pipeline.clear_effects()
        self.assertEqual(self.pipeline.effects, [])

    def test_process_no_backend(self):
        mock_src = MagicMock()
        result = self.pipeline.process(mock_src, 800, 600)
        self.assertIs(result, mock_src)

    def test_process_no_enabled_effects(self):
        blur = BlurEffect(enabled=False)
        self.pipeline.add_effect(blur)
        mock_src = MagicMock()
        with patch("pyray.is_window_ready", return_value=True):
            result = self.pipeline.process(mock_src, 800, 600)
        self.assertIs(result, mock_src)

    @patch("pyray.is_window_ready", return_value=True)
    @patch("pyray.load_render_texture")
    @patch("pyray.begin_texture_mode")
    @patch("pyray.end_texture_mode")
    @patch("pyray.clear_background")
    @patch("pyray.draw_texture_pro")
    def test_process_with_blur(
        self, mock_draw, mock_clear, mock_end, mock_begin, mock_load, mock_ready,
    ):
        src_tex = MagicMock()
        src_tex.id = 1
        src_tex.width = 800
        src_tex.height = 600

        mock_rt = MagicMock()
        mock_rt.texture = src_tex
        mock_load.return_value = mock_rt

        blur = BlurEffect(radius=2.0)
        self.pipeline.add_effect(blur)

        result = self.pipeline.process(mock_rt, 800, 600)
        self.assertIsNotNone(result)

    @patch("pyray.is_window_ready", return_value=True)
    @patch("pyray.load_render_texture")
    @patch("pyray.begin_texture_mode")
    @patch("pyray.end_texture_mode")
    @patch("pyray.clear_background")
    @patch("pyray.draw_texture_pro")
    def test_process_with_color_correct(
        self, mock_draw, mock_clear, mock_end, mock_begin, mock_load, mock_ready,
    ):
        src_tex = MagicMock()
        src_tex.id = 2
        src_tex.width = 640
        src_tex.height = 480

        mock_rt = MagicMock()
        mock_rt.texture = src_tex
        mock_load.return_value = mock_rt

        cc = ColorCorrectEffect(brightness=1.2, contrast=0.9, saturation=1.3)
        self.pipeline.add_effect(cc)

        result = self.pipeline.process(mock_rt, 640, 480)
        self.assertIsNotNone(result)

    def test_cleanup(self):
        self.pipeline.add_effect(BlurEffect())
        self.pipeline.cleanup()
        self.assertEqual(self.pipeline.effects, [])


# ---------------------------------------------------------------------------
# PostProcessEffectComp tests
# ---------------------------------------------------------------------------

class TestPostProcessEffectComp(unittest.TestCase):

    def test_defaults(self):
        pp = PostProcessEffectComp()
        self.assertTrue(pp.enabled)
        self.assertEqual(pp.effects, [])

    def test_with_effects(self):
        effects = [
            {"type": "BlurEffect", "radius": 4.0, "enabled": True},
            {"type": "ColorCorrectEffect", "brightness": 1.0, "contrast": 1.0, "saturation": 1.0},
        ]
        pp = PostProcessEffectComp(effects=effects)
        self.assertEqual(len(pp.effects), 2)
        self.assertEqual(pp.effects[0]["type"], "BlurEffect")

    def test_add_effect(self):
        pp = PostProcessEffectComp()
        pp.add_effect({"type": "BlurEffect", "radius": 8.0})
        self.assertEqual(len(pp.effects), 1)

    def test_to_dict(self):
        pp = PostProcessEffectComp(effects=[{"type": "BlurEffect", "radius": 2.0}])
        data = pp.to_dict()
        self.assertEqual(len(data["effects"]), 1)
        self.assertEqual(data["effects"][0]["radius"], 2.0)

    def test_from_dict(self):
        pp = PostProcessEffectComp.from_dict({
            "enabled": False,
            "effects": [{"type": "ColorCorrectEffect", "brightness": 1.5}],
        })
        self.assertFalse(pp.enabled)
        self.assertEqual(pp.effects[0]["brightness"], 1.5)

    def test_is_component(self):
        pp = PostProcessEffectComp()
        self.assertIsInstance(pp, Component)


# ---------------------------------------------------------------------------
# Component registry tests
# ---------------------------------------------------------------------------

class TestRegistryOla7Batch2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = create_default_registry()

    def test_sub_viewport_registered(self):
        comp_cls = self.registry.get("SubViewport")
        self.assertIsNotNone(comp_cls)
        self.assertEqual(comp_cls.__name__, "SubViewport")

    def test_viewport_texture_registered(self):
        comp_cls = self.registry.get("ViewportTexture")
        self.assertIsNotNone(comp_cls)
        self.assertEqual(comp_cls.__name__, "ViewportTexture")

    def test_post_process_effect_comp_registered(self):
        comp_cls = self.registry.get("PostProcessEffectComp")
        self.assertIsNotNone(comp_cls)
        self.assertEqual(comp_cls.__name__, "PostProcessEffectComp")

    def test_create_sub_viewport(self):
        vp = self.registry.create("SubViewport", {"size_x": 200, "transparent_bg": False})
        self.assertIsInstance(vp, SubViewport)
        self.assertEqual(vp.size_x, 200)
        self.assertFalse(vp.transparent_bg)

    def test_create_viewport_texture(self):
        vt = self.registry.create("ViewportTexture", {"viewport_entity": "vp1"})
        self.assertIsInstance(vt, ViewportTexture)
        self.assertEqual(vt.viewport_entity, "vp1")

    def test_create_post_process_effect_comp(self):
        pp = self.registry.create("PostProcessEffectComp", {
            "effects": [{"type": "BlurEffect", "radius": 3.0}],
        })
        self.assertIsInstance(pp, PostProcessEffectComp)
        self.assertEqual(len(pp.effects), 1)

    def test_list_registered_contains_new(self):
        names = self.registry.list_registered()
        self.assertIn("SubViewport", names)
        self.assertIn("ViewportTexture", names)
        self.assertIn("PostProcessEffectComp", names)


# ---------------------------------------------------------------------------
# RenderSystem integration tests (mocked)
# ---------------------------------------------------------------------------

class TestRenderSystemSubViewportIntegration(unittest.TestCase):

    @patch("pyray.load_render_texture")
    @patch("pyray.begin_texture_mode")
    @patch("pyray.end_texture_mode")
    @patch("pyray.clear_background")
    @patch("pyray.draw_texture_pro")
    @patch("pyray.is_window_ready", return_value=True)
    def test_render_sub_viewports_integration(
        self, mock_ready, mock_draw, mock_clear, mock_end, mock_begin, mock_load,
    ):
        from engine.systems.render_system import RenderSystem

        mock_load.return_value = MagicMock()

        world = World()
        render_system = RenderSystem()

        vp_entity = world.create_entity("__vp__")
        vp_entity.add_component(SubViewport(size_x=256, size_y=256))
        vp_entity.add_component(Transform(x=0, y=0))

        child = world.create_entity("vp_child")
        child.add_component(Transform(x=10, y=20))
        child.add_component(Sprite(texture_path="test.png"))

        # Patch get_children
        with patch.object(world, "get_children", return_value=["vp_child"]):
            with patch.object(render_system, "_load_texture", return_value=MagicMock(id=1)):
                render_system._render_sub_viewports(world)

        self.assertTrue(render_system._viewport_renderer.is_dirty("__vp__"))

    @patch("pyray.is_window_ready", return_value=True)
    def test_render_sub_viewport_once_mode_skips(self, mock_ready):
        from engine.systems.render_system import RenderSystem

        world = World()
        render_system = RenderSystem()

        vp_entity = world.create_entity("__vp2__")
        vp = SubViewport(size_x=100, size_y=100, render_target_update_mode="once")
        vp.needs_update = False
        vp_entity.add_component(vp)
        vp_entity.add_component(Transform())

        with patch.object(world, "get_children", return_value=[]):
            render_system._render_sub_viewports(world)

        self.assertFalse(render_system._viewport_renderer.is_dirty("__vp2__"))


class TestRenderSystemBackBufferCopyIntegration(unittest.TestCase):

    @patch("pyray.load_render_texture")
    @patch("pyray.begin_texture_mode")
    @patch("pyray.end_texture_mode")
    @patch("pyray.clear_background")
    @patch("pyray.draw_texture_rec")
    @patch("pyray.is_window_ready", return_value=True)
    def test_capture_backbuffer_rect_mode(
        self, mock_ready, mock_draw_rec, mock_clear, mock_end, mock_begin, mock_load,
    ):
        from engine.systems.render_system import RenderSystem

        mock_load.return_value = MagicMock()

        world = World()
        render_system = RenderSystem()

        bb = world.create_entity("__bb__")
        bb.add_component(BackBufferCopy(copy_mode="rect", rect_w=200, rect_h=150))
        bb.add_component(Transform())

        render_system._capture_backbuffer(world, viewport_size=(800, 600))

    @patch("pyray.is_window_ready", return_value=True)
    def test_capture_backbuffer_viewport_mode(self, mock_ready):
        from engine.systems.render_system import RenderSystem

        world = World()
        render_system = RenderSystem()

        bb = world.create_entity("__bb_vp__")
        bb.add_component(BackBufferCopy(copy_mode="viewport"))
        bb.add_component(Transform())

        with patch("pyray.load_render_texture"), patch("pyray.begin_texture_mode"), \
             patch("pyray.end_texture_mode"), patch("pyray.clear_background"), \
             patch("pyray.draw_texture_rec"):
            render_system._capture_backbuffer(world, viewport_size=(800, 600))

    @patch("pyray.is_window_ready", return_value=True)
    def test_capture_backbuffer_no_entities(self, mock_ready):
        from engine.systems.render_system import RenderSystem

        world = World()
        render_system = RenderSystem()
        # Should not raise
        render_system._capture_backbuffer(world)


if __name__ == "__main__":
    unittest.main()
