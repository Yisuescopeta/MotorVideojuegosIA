import unittest

from engine.editor import ui_core
from engine.editor.ui import tokens


class EditorUITokenTests(unittest.TestCase):
    def test_required_color_tokens_are_rgba(self) -> None:
        names = [
            "EDITOR_BG",
            "EDITOR_PANEL",
            "EDITOR_PANEL_ALT",
            "EDITOR_PANEL_HEADER",
            "EDITOR_BORDER",
            "EDITOR_BORDER_HOVER",
            "EDITOR_TEXT",
            "EDITOR_TEXT_MUTED",
            "EDITOR_TEXT_DISABLED",
            "EDITOR_ACCENT",
            "EDITOR_ACCENT_HOVER",
            "EDITOR_DANGER",
            "EDITOR_WARNING",
            "EDITOR_SUCCESS",
            "BG_RAYGUI_DARK",
        ]
        for name in names:
            value = getattr(tokens, name)
            self.assertEqual(len(value), 4, name)
            self.assertTrue(all(isinstance(channel, int) for channel in value), name)
            self.assertTrue(all(0 <= channel <= 255 for channel in value), name)

    def test_required_metric_tokens_exist(self) -> None:
        for name in [
            "PANEL_RADIUS",
            "BUTTON_RADIUS",
            "ROW_HEIGHT",
            "TOOLBAR_HEIGHT",
            "TAB_HEIGHT",
            "PANEL_PADDING",
            "CONTROL_PADDING_X",
            "CONTROL_PADDING_Y",
            "SPLITTER_WIDTH",
            "ICON_SIZE_SM",
            "ICON_SIZE_MD",
            "FONT_SIZE_SM",
            "FONT_SIZE_MD",
            "FONT_SIZE_LG",
        ]:
            self.assertGreater(getattr(tokens, name), 0, name)

    def test_legacy_token_module_matches_ui_core(self) -> None:
        for name in [
            "EDITOR_BG",
            "EDITOR_PANEL",
            "EDITOR_ACCENT",
            "BG_RAYGUI_DARK",
            "ROW_HEIGHT",
            "PANEL_PADDING",
            "FONT_SIZE_MD",
        ]:
            self.assertEqual(getattr(tokens, name), getattr(ui_core, name), name)


if __name__ == "__main__":
    unittest.main()
