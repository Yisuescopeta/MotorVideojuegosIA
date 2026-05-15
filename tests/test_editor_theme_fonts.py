from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from engine.editor.theme.fonts import (
    load_font,
    get_default_font,
    unload_all_fonts,
    _FONT_CACHE,
)


class TestEditorThemeFonts(unittest.TestCase):
    def setUp(self):
        _FONT_CACHE.clear()
        self.addCleanup(_FONT_CACHE.clear)

    @patch("engine.editor.theme.fonts._rl")
    def test_get_default_font_returns_font(self, mock_rl):
        mock = MagicMock()
        mock.get_font_default.return_value = "default_font"
        mock_rl.return_value = mock

        result = get_default_font()
        self.assertEqual(result, "default_font")

    @patch("engine.editor.theme.fonts._font_path")
    @patch("engine.editor.theme.fonts._rl")
    def test_load_font_caches_result(self, mock_rl, mock_font_path):
        mock_font_path.return_value = "/fake/path/font.ttf"
        mock = MagicMock()
        mock.load_font_ex.return_value = "cached_font"
        mock_rl.return_value = mock

        f1 = load_font("TestFont", 16)
        f2 = load_font("TestFont", 16)
        self.assertIs(f1, f2)
        mock.load_font_ex.assert_called_once()

    @patch("engine.editor.theme.fonts._font_path")
    @patch("engine.editor.theme.fonts._try_fallbacks")
    @patch("engine.editor.theme.fonts._rl")
    def test_load_font_fallback_on_missing(self, mock_rl, mock_fallbacks, mock_font_path):
        mock_font_path.return_value = None
        mock_fallbacks.return_value = "/fallback/font.ttf"
        mock = MagicMock()
        mock.load_font_ex.return_value = "fallback_font"
        mock_rl.return_value = mock

        font = load_font("MissingFont", 16)
        self.assertEqual(font, "fallback_font")

    @patch("engine.editor.theme.fonts._rl")
    def test_unload_all_clears_cache(self, mock_rl):
        mock_pyray = MagicMock()
        mock_rl.return_value = mock_pyray
        _FONT_CACHE[("a", 16)] = "dummy_a"
        _FONT_CACHE[("b", 24)] = "dummy_b"

        unload_all_fonts()
        self.assertEqual(len(_FONT_CACHE), 0)
        self.assertEqual(mock_pyray.unload_font.call_count, 2)

    @patch("engine.editor.theme.fonts._font_path")
    @patch("engine.editor.theme.fonts._try_fallbacks")
    @patch("engine.editor.theme.fonts._rl")
    def test_load_font_different_sizes_separate_cache(self, mock_rl, mock_fallbacks, mock_font_path):
        mock_font_path.return_value = "/fake/font.ttf"
        mock = MagicMock()
        mock.load_font_ex.side_effect = ["font16", "font24"]
        mock_rl.return_value = mock

        f16 = load_font("TestFont", 16)
        f24 = load_font("TestFont", 24)
        self.assertNotEqual(f16, f24)
        self.assertEqual(mock.load_font_ex.call_count, 2)


if __name__ == "__main__":
    unittest.main()
