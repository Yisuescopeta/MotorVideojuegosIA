from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from engine.editor.ui.icons import (
    ICON_CLOSE,
    ICON_FOLDER,
    ICON_PLAY,
    ICON_SEARCH,
    KNOWN_ICONS,
    draw_icon,
    icon_exists,
)


class TestIconsMultisize(unittest.TestCase):
    def setUp(self):
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
        )

    def test_draw_icon_size_none_does_not_crash(self):
        mock_rl_patch, mock_color_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch:
            mock_rl.return_value = self._mock_rl()
            try:
                draw_icon(ICON_PLAY, self.rect)
            except Exception as e:
                self.fail(f"draw_icon with size=None crashed: {e}")

    def test_draw_icon_with_sizes_does_not_crash(self):
        mock_rl_patch, mock_color_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch:
            mock_rl.return_value = self._mock_rl()
            for sz in (16, 24, 32, 64):
                try:
                    draw_icon(ICON_PLAY, self.rect, size=sz)
                except Exception as e:
                    self.fail(f"draw_icon with size={sz} crashed: {e}")

    def test_draw_icon_unknown_ignored(self):
        mock_rl_patch, mock_color_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch:
            mock_rl.return_value = self._mock_rl()
            try:
                draw_icon("nonexistent_icon", self.rect, size=32)
            except Exception as e:
                self.fail(f"Unknown icon draw should not crash: {e}")

    def test_icon_exists(self):
        self.assertTrue(icon_exists(ICON_PLAY))
        self.assertTrue(icon_exists(ICON_CLOSE))
        self.assertTrue(icon_exists(ICON_SEARCH))
        self.assertTrue(icon_exists(ICON_FOLDER))
        self.assertFalse(icon_exists("bogus"))

    def test_all_icons_draw_with_size(self):
        mock_rl_patch, mock_color_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch:
            mock_rl.return_value = self._mock_rl()
            for name in sorted(KNOWN_ICONS):
                for sz in (16, 32, 64):
                    try:
                        draw_icon(name, self.rect, size=sz)
                    except Exception as e:
                        self.fail(f"draw_icon('{name}', size={sz}) crashed: {e}")

    def test_size_32_uses_scaled_coordinates(self):
        mock_rl_patch, mock_color_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch:
            mock = self._mock_rl()
            mock_rl.return_value = mock

            draw_icon(ICON_PLAY, self.rect, size=32)
            mock.draw_triangle.assert_called_once()
            args, _ = mock.draw_triangle.call_args
            # ICON_PLAY: draw_triangle((left,top), (left,bottom), (right,cy))
            # cx=124, cy=124, half=16 → left=108, right=140, top=108, bottom=140
            v0, v1, v2 = args[0], args[1], args[2]
            self.assertAlmostEqual(v0, (108.0, 108.0))
            self.assertAlmostEqual(v1, (108.0, 140.0))
            self.assertAlmostEqual(v2, (140.0, 124.0))

    def test_size_32_follows_rect_center(self):
        mock_rl_patch, mock_color_patch = self._patchers()
        with mock_rl_patch as mock_rl, mock_color_patch:
            mock = self._mock_rl()
            mock_rl.return_value = mock

            offset_rect = (200.0, 50.0, 60.0, 30.0)
            draw_icon(ICON_CLOSE, offset_rect, size=32)
            self.assertEqual(mock.draw_line.call_count, 2)
            # cx=200+60/2=230, cy=50+30/2=65, half=16
            # left=214, right=246, top=49, bottom=81
            # ICON_CLOSE: draw_line(left,top,right,bottom), draw_line(right,top,left,bottom)
            args0 = mock.draw_line.call_args_list[0][0]
            self.assertEqual(args0[:4], (214.0, 49.0, 246.0, 81.0))
            args1 = mock.draw_line.call_args_list[1][0]
            self.assertEqual(args1[:4], (246.0, 49.0, 214.0, 81.0))


if __name__ == "__main__":
    unittest.main()
