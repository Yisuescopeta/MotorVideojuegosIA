import unittest

from engine.editor.ui.colors import int_to_rgba, is_dark_theme, lerp_color, rgba, rgba_to_hex, rgba_to_int, with_alpha


class EditorUIColorTests(unittest.TestCase):
    def test_rgba_clamps_channels(self) -> None:
        self.assertEqual(rgba(-1, 128, 300, 999), (0, 128, 255, 255))

    def test_with_alpha_replaces_alpha(self) -> None:
        self.assertEqual(with_alpha((1, 2, 3, 4), 9), (1, 2, 3, 9))

    def test_lerp_color_interpolates_and_clamps_t(self) -> None:
        self.assertEqual(lerp_color((0, 0, 0, 0), (10, 20, 30, 40), 0.5), (5, 10, 15, 20))
        self.assertEqual(lerp_color((1, 1, 1, 1), (9, 9, 9, 9), 2), (9, 9, 9, 9))

    def test_dark_theme_detection_uses_luminance(self) -> None:
        self.assertTrue(is_dark_theme((32, 32, 32, 255)))
        self.assertFalse(is_dark_theme((240, 240, 240, 255)))

    def test_int_roundtrip_matches_raygui_packing(self) -> None:
        color = (1, 2, 3, 4)
        self.assertEqual(rgba_to_int(color), 0x01020304)
        self.assertEqual(int_to_rgba(0x01020304), color)

    def test_rgba_to_hex(self) -> None:
        self.assertEqual(rgba_to_hex((1, 2, 255, 4)), "#0102FF04")
        self.assertEqual(rgba_to_hex((1, 2, 255, 4), include_alpha=False), "#0102FF")


if __name__ == "__main__":
    unittest.main()
