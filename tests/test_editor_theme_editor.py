from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine.editor.theme import set_active_theme
from engine.editor.theme.theme_editor import ThemeEditorPanel, ThemeEditorState


def _mock_rl():
    rl = MagicMock()
    rl.draw_text = MagicMock()
    rl.draw_rectangle = MagicMock()
    rl.draw_rectangle_lines = MagicMock()
    rl.Color = lambda r, g, b, a: (r, g, b, a)
    return rl


class TestThemeEditorPanel(unittest.TestCase):
    def setUp(self):
        set_active_theme("unity_dark")
        self._rl_patcher = patch("engine.editor.theme.theme_editor._rl", _mock_rl)
        self._rl_patcher.start()

    def tearDown(self):
        self._rl_patcher.stop()

    def test_instantiation(self):
        panel = ThemeEditorPanel()
        self.assertIsInstance(panel.state, ThemeEditorState)
        self.assertIsNone(panel.state.selected_color)

    def test_render_returns_dict(self):
        panel = ThemeEditorPanel()
        result = panel.render((0, 0, 300, 400))
        self.assertIsInstance(result, dict)

    def test_select_color(self):
        panel = ThemeEditorPanel()
        panel._select_color("accent")
        self.assertEqual(panel.state.selected_color, "accent")
        self.assertGreater(panel.state.r, 0)

    def test_select_invalid_color_does_nothing(self):
        panel = ThemeEditorPanel()
        panel._select_color("nonexistent")
        self.assertIsNone(panel.state.selected_color)

    def test_save_and_load_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "editor_state.json"
            panel = ThemeEditorPanel()
            panel._select_color("accent")
            panel._state.r = 100
            panel._state.g = 150
            panel._state.b = 200
            panel._apply_color()
            panel.save_state(str(state_path))

            self.assertTrue(state_path.exists())
            data = json.loads(state_path.read_text(encoding="utf-8"))
            prefs = data.get("preferences", {})
            self.assertIn("custom_theme_colors", prefs)
            custom = prefs["custom_theme_colors"]
            self.assertEqual(custom["name"], "unity_dark")
            accent = custom["colors"]["accent"]
            self.assertEqual(accent, [100, 150, 200, 255])

    def test_load_state_missing_file_no_crash(self):
        panel = ThemeEditorPanel()
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "nonexistent.json")
            try:
                panel.load_state(path)
            except Exception as e:
                self.fail(f"load_state on missing file crashed: {e}")


if __name__ == "__main__":
    unittest.main()
