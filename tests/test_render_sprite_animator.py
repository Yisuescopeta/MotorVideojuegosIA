"""
tests/test_render_sprite_animator.py - Tests for RenderSystem sprite+animator draw dispatch.

Covers:
- Bug 3.7: Sprite drawn when Animator also present
- Sprite-only / Animator-only / polygon-only / placeholder fallback
- Bug 2.1: Sprite source_slice → slice rect lookup behavior (unit-level)
"""

import unittest
from unittest.mock import MagicMock, patch

from engine.components.animator import Animator
from engine.components.camera2d import Camera2D
from engine.components.polygon2d import Polygon2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.systems.render_system import RenderSystem


class FakeTexture:
    """Minimal texture stub with id, width, height."""
    def __init__(self, id: int = 1, width: int = 64, height: int = 64):
        self.id = id
        self.width = width
        self.height = height

    def __bool__(self) -> bool:
        return self.id != 0


class _DrawTracker:
    """Captures which draw method was called on a mock RenderSystem."""
    def __init__(self):
        self.drew_sprite = False
        self.drew_animator = False
        self.drew_polygon = False
        self.drew_placeholder = False

    def reset(self):
        self.drew_sprite = False
        self.drew_animator = False
        self.drew_polygon = False
        self.drew_placeholder = False


def _make_entity(name: str) -> Entity:
    entity = Entity(name)
    entity.add_component(Transform(x=100, y=200))
    return entity


class RenderSpriteAnimatorDispatchTests(unittest.TestCase):
    """Tests for RenderSystem._render_entity draw dispatch (Bug 3.7)."""

    def setUp(self):
        self.rs = RenderSystem()
        self.tracker = _DrawTracker()

        def fake_draw_sprite(transform, sprite):
            self.tracker.drew_sprite = True

        def fake_draw_animator(transform, animator):
            self.tracker.drew_animator = True

        def fake_draw_polygon(transform, polygon):
            self.tracker.drew_polygon = True

        def fake_draw_placeholder(name, transform):
            self.tracker.drew_placeholder = True

        self.rs._draw_sprite = fake_draw_sprite  # type: ignore[method-assign]
        self.rs._draw_animated_sprite = fake_draw_animator  # type: ignore[method-assign]
        self.rs._draw_polygon = fake_draw_polygon  # type: ignore[method-assign]
        self.rs._draw_placeholder = fake_draw_placeholder  # type: ignore[method-assign]

    # --- Bug 3.7: both Sprite + Animator ---

    def test_both_sprite_and_animator_draw_both(self):
        """When both Sprite and Animator exist/enabled, both should draw."""
        entity = _make_entity("Player")
        entity.add_component(Sprite(texture_path="hero.png"))
        entity.add_component(Animator(sprite_sheet="hero.png"))

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertTrue(self.tracker.drew_sprite, "Sprite should be drawn when Animator also exists")
        self.assertTrue(self.tracker.drew_animator, "Animator should be drawn when Sprite also exists")

    def test_animator_without_sprite_sheet_does_not_draw(self):
        """Animator without sprite_sheet should not trigger animated draw."""
        entity = _make_entity("Player")
        entity.add_component(Sprite(texture_path="hero.png"))
        entity.add_component(Animator(sprite_sheet=""))

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertTrue(self.tracker.drew_sprite)
        self.assertFalse(self.tracker.drew_animator)

    # --- Sprite-only ---

    def test_sprite_only_draws_sprite(self):
        entity = _make_entity("Item")
        entity.add_component(Sprite(texture_path="item.png"))

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertTrue(self.tracker.drew_sprite)
        self.assertFalse(self.tracker.drew_animator)
        self.assertFalse(self.tracker.drew_polygon)
        self.assertFalse(self.tracker.drew_placeholder)

    def test_disabled_sprite_falls_through_to_placeholder(self):
        entity = _make_entity("Item")
        sprite = Sprite(texture_path="item.png")
        sprite.enabled = False
        entity.add_component(sprite)

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertFalse(self.tracker.drew_sprite)
        self.assertFalse(self.tracker.drew_animator)
        self.assertTrue(self.tracker.drew_placeholder)

    def test_sprite_no_texture_path_falls_through_to_placeholder(self):
        entity = _make_entity("Item")
        entity.add_component(Sprite(texture_path=""))

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertFalse(self.tracker.drew_sprite)
        self.assertTrue(self.tracker.drew_placeholder)

    # --- Animator-only ---

    def test_animator_only_draws_animator(self):
        entity = _make_entity("Hero")
        entity.add_component(Animator(sprite_sheet="spritesheet.png"))

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertTrue(self.tracker.drew_animator)
        self.assertFalse(self.tracker.drew_sprite)

    def test_disabled_animator_falls_through_to_placeholder(self):
        entity = _make_entity("Hero")
        anim = Animator(sprite_sheet="spritesheet.png")
        anim.enabled = False
        entity.add_component(anim)

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertFalse(self.tracker.drew_animator)
        self.assertTrue(self.tracker.drew_placeholder)

    # --- Polygon fallback ---

    def test_polygon_only_draws_polygon(self):
        entity = _make_entity("Shape")
        poly = Polygon2D(points=[[0, 0], [50, 0], [25, 50]])
        entity.add_component(poly)

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertTrue(self.tracker.drew_polygon)
        self.assertFalse(self.tracker.drew_placeholder)

    # --- Placeholder ---

    def test_no_drawable_draws_placeholder(self):
        entity = _make_entity("Ghost")

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertTrue(self.tracker.drew_placeholder)

    def test_camera_without_drawable_skips_placeholder(self):
        entity = _make_entity("MainCamera")
        entity.add_component(Camera2D())

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertFalse(self.tracker.drew_sprite)
        self.assertFalse(self.tracker.drew_animator)
        self.assertFalse(self.tracker.drew_polygon)
        self.assertFalse(self.tracker.drew_placeholder)

    # --- Tile collider skip ---

    def test_tile_collider_is_skipped(self):
        entity = _make_entity("__tilecollider__0")
        entity.add_component(Sprite(texture_path="col.png"))

        self.rs._render_entity(entity, entity.get_component(Transform))

        self.assertFalse(self.tracker.drew_sprite)
        self.assertFalse(self.tracker.drew_placeholder)


class SpriteSourceSliceRenderTests(unittest.TestCase):
    """Tests for Sprite.source_slice in _draw_sprite (Bug 2.1)."""

    def setUp(self):
        self.rs = RenderSystem()

    def test_source_slice_calls_get_slice_rect_when_set(self):
        """When source_slice is non-empty, get_slice_rect is invoked."""
        sprite = Sprite(texture_path="atlas.png", source_slice="hero_head")

        fake_service = MagicMock()
        fake_service.get_slice_rect.return_value = {"x": 10, "y": 20, "width": 32, "height": 32}
        self.rs._asset_service = fake_service

        # Mock _load_texture to return a valid texture
        with patch.object(self.rs, "_load_texture", return_value=FakeTexture(1, 128, 128)):
            with patch("pyray.draw_texture_pro") as mock_draw:
                self.rs._draw_sprite(Transform(x=0, y=0), sprite)
                fake_service.get_slice_rect.assert_called_once()
                # Verify source rect uses slice coordinates
                args = mock_draw.call_args[0]
                source_rect = args[1]  # Rectangle
                self.assertEqual(source_rect.x, 10)
                self.assertEqual(source_rect.y, 20)
                self.assertEqual(source_rect.width, 32)
                self.assertEqual(source_rect.height, 32)

    def test_source_slice_empty_uses_full_texture(self):
        """When source_slice is empty, full texture dimensions are used."""
        sprite = Sprite(texture_path="atlas.png", source_slice="")

        # Even if asset_service exists, it should not be called
        fake_service = MagicMock()
        self.rs._asset_service = fake_service

        with patch.object(self.rs, "_load_texture", return_value=FakeTexture(1, 128, 64)):
            with patch("pyray.draw_texture_pro") as mock_draw:
                self.rs._draw_sprite(Transform(x=0, y=0), sprite)
                fake_service.get_slice_rect.assert_not_called()
                args = mock_draw.call_args[0]
                source_rect = args[1]
                self.assertEqual(source_rect.x, 0)
                self.assertEqual(source_rect.y, 0)
                self.assertEqual(source_rect.width, 128)
                self.assertEqual(source_rect.height, 64)

    def test_source_slice_lookup_fails_uses_full_texture(self):
        """When get_slice_rect returns None, fall back to full texture."""
        sprite = Sprite(texture_path="atlas.png", source_slice="missing")

        fake_service = MagicMock()
        fake_service.get_slice_rect.return_value = None
        self.rs._asset_service = fake_service

        with patch.object(self.rs, "_load_texture", return_value=FakeTexture(1, 128, 64)):
            with patch("pyray.draw_texture_pro") as mock_draw:
                self.rs._draw_sprite(Transform(x=0, y=0), sprite)
                fake_service.get_slice_rect.assert_called_once()
                args = mock_draw.call_args[0]
                source_rect = args[1]
                self.assertEqual(source_rect.x, 0)
                self.assertEqual(source_rect.y, 0)
                self.assertEqual(source_rect.width, 128)
                self.assertEqual(source_rect.height, 64)

    def test_source_slice_no_asset_service_uses_full_texture(self):
        """When asset_service is None, fall back to full texture."""
        sprite = Sprite(texture_path="atlas.png", source_slice="hero_head")
        self.rs._asset_service = None

        with patch.object(self.rs, "_load_texture", return_value=FakeTexture(1, 128, 64)):
            with patch("pyray.draw_texture_pro") as mock_draw:
                self.rs._draw_sprite(Transform(x=0, y=0), sprite)
                args = mock_draw.call_args[0]
                source_rect = args[1]
                self.assertEqual(source_rect.x, 0)
                self.assertEqual(source_rect.y, 0)
                self.assertEqual(source_rect.width, 128)
                self.assertEqual(source_rect.height, 64)

    def test_sprite_width_height_override_slice_dimensions(self):
        """When sprite.width>0, it overrides slice dimensions for destination."""
        sprite = Sprite(texture_path="atlas.png", source_slice="hero_head", width=100, height=80)

        fake_service = MagicMock()
        fake_service.get_slice_rect.return_value = {"x": 10, "y": 20, "width": 32, "height": 32}
        self.rs._asset_service = fake_service

        with patch.object(self.rs, "_load_texture", return_value=FakeTexture(1, 256, 256)):
            with patch("pyray.draw_texture_pro") as mock_draw:
                self.rs._draw_sprite(Transform(x=0, y=0, scale_x=1.0, scale_y=1.0), sprite)
                args = mock_draw.call_args[0]
                source_rect = args[1]
                dest_rect = args[2]
                # Source still from slice
                self.assertEqual(source_rect.width, 32)
                self.assertEqual(source_rect.height, 32)
                # Destination uses sprite.width/height
                self.assertEqual(dest_rect.width, 100)
                self.assertEqual(dest_rect.height, 80)


if __name__ == "__main__":
    unittest.main()
