from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from engine.editor.ui.icon_provider import reset_cache
from engine.editor.ui.icons import (
    HIERARCHY_ICONS,
    ICON_CAMERA,
    ICON_CHEVRON_LEFT,
    ICON_CHEVRON_RIGHT,
    ICON_CLOSE,
    ICON_ENTITY,
    ICON_FOLDER,
    ICON_PLAY,
    ICON_SEARCH,
    ICON_SPRITE,
    ICON_TILEMAP,
    ICON_TRASH,
    PRIMITIVE_ICONS,
    draw_icon,
    icon_exists,
)


class TestIconsMultisize(unittest.TestCase):
    def setUp(self):
        reset_cache()
        self.rect = (100.0, 100.0, 48.0, 48.0)

    def _mock_rl(self):
        mock = MagicMock()
        mock.Vector2.side_effect = lambda x, y: (float(x), float(y))
        mock.Color.return_value = MagicMock()
        return mock

    def _patchers(self):
        return (
            patch("engine.editor.ui.icons._rl"),
            patch("engine.editor.ui.icons.to_ray_color", return_value=MagicMock()),
            patch("engine.editor.ui.icons._draw_icon_from_pack", return_value=False),
            patch("engine.editor.ui.icons._draw_lucide_icon", return_value=False),
        )

    def test_draw_icon_size_none_does_not_crash(self):
        mock_rl_patch, mock_color_patch, godot_patch, lucide_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch, godot_patch, lucide_patch:
            mock_rl.return_value = self._mock_rl()
            try:
                draw_icon(ICON_PLAY, self.rect)
            except Exception as e:
                self.fail(f"draw_icon with size=None crashed: {e}")

    def test_draw_icon_with_sizes_does_not_crash(self):
        mock_rl_patch, mock_color_patch, godot_patch, lucide_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch, godot_patch, lucide_patch:
            mock_rl.return_value = self._mock_rl()
            for sz in (16, 24, 32, 64):
                try:
                    draw_icon(ICON_PLAY, self.rect, size=sz)
                except Exception as e:
                    self.fail(f"draw_icon with size={sz} crashed: {e}")

    def test_draw_icon_unknown_ignored(self):
        mock_rl_patch, mock_color_patch, godot_patch, lucide_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch, godot_patch, lucide_patch:
            mock_rl.return_value = self._mock_rl()
            try:
                draw_icon("nonexistent_icon", self.rect, size=32)
            except Exception as e:
                self.fail(f"Unknown icon draw should not crash: {e}")

    def test_icon_exists(self):
        self.assertTrue(icon_exists(ICON_PLAY))
        self.assertTrue(icon_exists(ICON_CLOSE))
        self.assertTrue(icon_exists(ICON_CHEVRON_LEFT))
        self.assertTrue(icon_exists(ICON_CHEVRON_RIGHT))
        self.assertTrue(icon_exists(ICON_SEARCH))
        self.assertTrue(icon_exists(ICON_FOLDER))
        self.assertTrue(icon_exists(ICON_TRASH))
        self.assertTrue(icon_exists(ICON_ENTITY))
        self.assertTrue(icon_exists(ICON_SPRITE))
        self.assertTrue(icon_exists(ICON_CAMERA))
        self.assertTrue(icon_exists(ICON_TILEMAP))
        self.assertTrue(icon_exists("pick"))
        self.assertTrue(icon_exists("image"))
        self.assertFalse(icon_exists("bogus"))

    def test_all_primitive_icons_draw_with_size(self):
        mock_rl_patch, mock_color_patch, godot_patch, lucide_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch, godot_patch, lucide_patch:
            mock_rl.return_value = self._mock_rl()
            for name in sorted(PRIMITIVE_ICONS):
                for sz in (16, 32, 64):
                    try:
                        draw_icon(name, self.rect, size=sz)
                    except Exception as e:
                        self.fail(f"draw_icon('{name}', size={sz}) crashed: {e}")

    def test_size_32_uses_scaled_coordinates(self):
        mock_rl_patch, mock_color_patch, godot_patch, lucide_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch, godot_patch, lucide_patch:
            mock = self._mock_rl()
            mock_rl.return_value = mock

            draw_icon(ICON_PLAY, self.rect, size=32)
            mock.draw_triangle.assert_called_once()
            args, _ = mock.draw_triangle.call_args
            v0, v1, v2 = args[0], args[1], args[2]
            self.assertAlmostEqual(v0, (108.0, 108.0))
            self.assertAlmostEqual(v1, (108.0, 140.0))
            self.assertAlmostEqual(v2, (140.0, 124.0))

    def test_size_32_follows_rect_center(self):
        mock_rl_patch, mock_color_patch, godot_patch, lucide_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch, godot_patch, lucide_patch:
            mock = self._mock_rl()
            mock_rl.return_value = mock

            offset_rect = (200.0, 50.0, 60.0, 30.0)
            draw_icon(ICON_CLOSE, offset_rect, size=32)
            self.assertEqual(mock.draw_line.call_count, 2)
            args0 = mock.draw_line.call_args_list[0][0]
            self.assertEqual(args0[:4], (214.0, 49.0, 246.0, 81.0))
            args1 = mock.draw_line.call_args_list[1][0]
            self.assertEqual(args1[:4], (246.0, 49.0, 214.0, 81.0))

    def test_draw_icon_prefers_lucide_when_available(self):
        with patch("engine.editor.ui.icons._draw_icon_from_pack", return_value=False), patch(
            "engine.editor.ui.icons._draw_lucide_icon", return_value=True
        ) as lucide_patch, patch(
            "engine.editor.ui.icons._rl"
        ) as mock_rl, patch("engine.editor.ui.icons.to_ray_color", return_value=MagicMock()):
            mock_rl.return_value = self._mock_rl()
            draw_icon(ICON_PLAY, self.rect, size=16)

        lucide_patch.assert_called_once()
        mock_rl.return_value.draw_triangle.assert_not_called()

    def test_draw_icon_prefers_godot_for_hierarchy_icons(self):
        with patch("engine.editor.ui.icons._draw_icon_from_pack", return_value=True) as godot_patch, patch(
            "engine.editor.ui.icons._draw_lucide_icon", return_value=False
        ) as lucide_patch:
            draw_icon(ICON_ENTITY, self.rect, size=16)

        godot_patch.assert_called_once()
        lucide_patch.assert_not_called()

    def test_draw_icon_falls_back_to_lucide_when_godot_missing(self):
        with patch("engine.editor.ui.icons._draw_icon_from_pack", return_value=False) as godot_patch, patch(
            "engine.editor.ui.icons._draw_lucide_icon", return_value=True
        ) as lucide_patch:
            draw_icon(ICON_ENTITY, self.rect, size=16)

        godot_patch.assert_called_once()
        lucide_patch.assert_called_once()

    def test_hierarchy_icons_set_contains_new_semantic_icons(self):
        self.assertIn(ICON_ENTITY, HIERARCHY_ICONS)
        self.assertIn(ICON_SPRITE, HIERARCHY_ICONS)
        self.assertIn(ICON_CAMERA, HIERARCHY_ICONS)
        self.assertIn(ICON_TILEMAP, HIERARCHY_ICONS)

    def test_draw_icon_can_skip_window_and_not_crash(self):
        with patch(
            "engine.editor.ui.icon_provider._load_atlas_metadata_for_pack",
            return_value={"icons": {"image": {}}, "sizes": [16, 24]},
        ), patch(
            "engine.editor.ui.icon_provider._load_texture_for_pack", return_value=None
        ):
            try:
                draw_icon("image", self.rect, size=16)
            except Exception as e:
                self.fail(f"Lucide draw without ready window crashed: {e}")


if __name__ == "__main__":
    unittest.main()
