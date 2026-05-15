import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.editor.theme_serializer import ThemeSerializer
from engine.editor.ui import widgets
from engine.editor.ui.theme import (
    THEME_REGISTRY,
    UNITY_DARK,
    UNITY_LIGHT,
    EditorTheme,
    ThemeRegistry,
    get_active_theme,
    set_active_theme,
    theme_to_raygui_map,
)


class EditorUINamedThemeTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_active_theme("unity_dark")

    def test_theme_serializes_name_colors_fonts_and_metrics(self) -> None:
        payload = UNITY_DARK.to_dict()

        self.assertEqual(payload["name"], "unity_dark")
        self.assertIn("bg", payload["colors"])
        self.assertIn("font_size_sm", payload["fonts"])
        self.assertIn("button_radius", payload["metrics"])

        restored = EditorTheme.from_dict(json.loads(json.dumps(payload)))
        self.assertEqual(restored, UNITY_DARK)

    def test_registry_switches_active_builtin_themes(self) -> None:
        self.assertIn("unity_dark", THEME_REGISTRY.names())
        self.assertIn("unity_light", THEME_REGISTRY.names())

        active = set_active_theme("unity_light")

        self.assertEqual(active.name, "unity_light")
        self.assertEqual(get_active_theme(), UNITY_LIGHT)
        self.assertEqual(theme_to_raygui_map(None), theme_to_raygui_map(UNITY_LIGHT))

    def test_serializer_saves_and_loads_active_theme_name(self) -> None:
        registry = ThemeRegistry([UNITY_DARK, UNITY_LIGHT])
        registry.set_active("unity_light")
        serializer = ThemeSerializer(registry)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "editor-state" / "theme.json"
            serializer.save(path)
            registry.set_active("unity_dark")

            loaded = serializer.load(path)

        self.assertEqual(loaded, "unity_light")
        self.assertEqual(registry.active_name, "unity_light")

    def test_widget_helpers_resolve_active_theme_when_none(self) -> None:
        set_active_theme("unity_light")

        with patch.object(widgets.ui_input, "is_hovered", return_value=False), patch.object(
            widgets.ui_input, "is_pressed", return_value=False
        ), patch.object(widgets.ui_input, "is_clicked", return_value=False), patch.object(
            widgets.ui_input, "is_right_clicked", return_value=False
        ), patch.object(widgets, "draw_rounded_rect") as draw_rect, patch.object(
            widgets, "draw_border"
        ), patch.object(
            widgets, "draw_text_clipped"
        ):
            result = widgets.editor_button((0, 0, 40, 20), "Play", theme=None)

        self.assertEqual(result.value, "Play")
        draw_rect.assert_called_once()
        self.assertEqual(draw_rect.call_args.args[1], UNITY_LIGHT.button)


if __name__ == "__main__":
    unittest.main()
