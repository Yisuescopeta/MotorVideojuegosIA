import unittest

from engine.editor.raygui_theme import (
    UNITY_BG,
    UNITY_BLUE,
    UNITY_BLUE_HOVER,
    UNITY_BORDER,
    UNITY_BUTTON,
    UNITY_BUTTON_HOVER,
    UNITY_PANEL,
    UNITY_TEXT,
    UNITY_TEXT_DIM,
    color_to_int,
)
from engine.editor.raygui_theme import (
    UNITY_DARK as RAYGUI_UNITY_DARK,
)
from engine.editor.ui.theme import (
    BACKGROUND_COLOR,
    BUTTON,
    CHECKBOX,
    DEFAULT,
    LISTVIEW,
    SCROLLBAR,
    SLIDER,
    TEXTBOX,
    TOGGLE,
    UNITY_DARK,
    EditorTheme,
    theme_to_raygui_map,
)


class EditorUIThemeTests(unittest.TestCase):
    def test_unity_dark_theme_exposes_editor_colors(self) -> None:
        self.assertIsInstance(UNITY_DARK, EditorTheme)
        self.assertEqual(UNITY_DARK.bg, (56, 56, 56, 255))

    def test_theme_to_raygui_map_is_pure_int_mapping(self) -> None:
        mapping = theme_to_raygui_map(UNITY_DARK)
        self.assertEqual(mapping[(DEFAULT, BACKGROUND_COLOR)], color_to_int(45, 45, 45))
        self.assertTrue(all(isinstance(key, tuple) and len(key) == 2 for key in mapping))
        self.assertTrue(all(isinstance(value, int) for value in mapping.values()))

    def test_theme_to_raygui_map_covers_expected_controls(self) -> None:
        mapping = theme_to_raygui_map(UNITY_DARK)
        controls = {control for control, _ in mapping}
        self.assertTrue(
            {
                DEFAULT,
                BUTTON,
                TOGGLE,
                SLIDER,
                CHECKBOX,
                TEXTBOX,
                LISTVIEW,
                SCROLLBAR,
            }.issubset(controls)
        )
        self.assertTrue(all(isinstance(value, int) for value in mapping.values()))

    def test_raygui_theme_keeps_compatibility_constants(self) -> None:
        self.assertEqual(UNITY_BG, color_to_int(56, 56, 56))
        self.assertEqual(UNITY_PANEL, color_to_int(45, 45, 45))
        self.assertEqual(RAYGUI_UNITY_DARK, color_to_int(32, 32, 32))
        self.assertEqual(UNITY_BORDER, color_to_int(30, 30, 30))
        self.assertEqual(UNITY_TEXT, color_to_int(200, 200, 200))
        self.assertEqual(UNITY_TEXT_DIM, color_to_int(140, 140, 140))
        self.assertEqual(UNITY_BLUE, color_to_int(44, 93, 135))
        self.assertEqual(UNITY_BLUE_HOVER, color_to_int(60, 110, 160))
        self.assertEqual(UNITY_BUTTON, color_to_int(65, 65, 65))
        self.assertEqual(UNITY_BUTTON_HOVER, color_to_int(80, 80, 80))


if __name__ == "__main__":
    unittest.main()
