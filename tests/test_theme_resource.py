"""
tests/test_theme_resource.py — Tests for StyleBoxResource and ThemeResource.
"""

from __future__ import annotations

import unittest

from engine.resources.stylebox_resource import StyleBoxResource
from engine.resources.theme_resource import ThemeResource
from engine.components.canvas import Canvas


class TestStyleBoxResource(unittest.TestCase):
    def test_create_stylebox(self) -> None:
        sb = StyleBoxResource(resource_id="box1", name="DefaultBox")
        self.assertEqual(sb.resource_id, "box1")
        self.assertEqual(sb.name, "DefaultBox")
        self.assertEqual(sb.style_type, "flat")
        self.assertEqual(sb.bg_color, (40, 40, 40, 255))

    def test_stylebox_serialization(self) -> None:
        sb = StyleBoxResource(
            resource_id="box_round",
            name="RoundedPanel",
            corner_radius=8,
            border_width=2,
        )
        d = sb.to_dict()
        sb2 = StyleBoxResource.from_dict(d)
        self.assertEqual(sb2.resource_id, sb.resource_id)
        self.assertEqual(sb2.name, sb.name)
        self.assertEqual(sb2.corner_radius, sb.corner_radius)
        self.assertEqual(sb2.border_width, sb.border_width)
        self.assertEqual(sb2.bg_color, sb.bg_color)
        self.assertEqual(sb2.border_color, sb.border_color)

    def test_stylebox_ninepatch(self) -> None:
        sb = StyleBoxResource(
            resource_id="np1",
            name="ButtonNinePatch",
            style_type="ninepatch",
            margin_left=12,
            margin_right=12,
            margin_top=8,
            margin_bottom=8,
            content_margin_left=6,
            content_margin_right=6,
            content_margin_top=4,
            content_margin_bottom=4,
        )
        d = sb.to_dict()
        sb2 = StyleBoxResource.from_dict(d)
        self.assertEqual(sb2.style_type, "ninepatch")
        self.assertEqual(sb2.margin_left, 12)
        self.assertEqual(sb2.margin_right, 12)
        self.assertEqual(sb2.margin_top, 8)
        self.assertEqual(sb2.margin_bottom, 8)
        self.assertEqual(sb2.content_margin_left, 6)
        self.assertEqual(sb2.content_margin_right, 6)
        self.assertEqual(sb2.content_margin_top, 4)
        self.assertEqual(sb2.content_margin_bottom, 4)


class TestThemeResource(unittest.TestCase):
    def test_create_theme(self) -> None:
        theme = ThemeResource(resource_id="t1", name="DarkTheme")
        self.assertEqual(theme.resource_id, "t1")
        self.assertEqual(theme.name, "DarkTheme")
        self.assertEqual(theme.default_font_size, 16)
        self.assertEqual(theme.default_font_color, (255, 255, 255, 255))
        self.assertEqual(len(theme.styleboxes), 0)
        self.assertEqual(len(theme.colors), 0)

    def test_theme_serialization(self) -> None:
        theme = ThemeResource(
            resource_id="t_ser",
            name="SerialTheme",
            default_font_size=14,
            colors={"Panel/bg_color": [20, 20, 40, 255]},
            fonts={"default": "fonts/main.otf"},
        )
        d = theme.to_dict()
        theme2 = ThemeResource.from_dict(d)
        self.assertEqual(theme2.resource_id, theme.resource_id)
        self.assertEqual(theme2.name, theme.name)
        self.assertEqual(theme2.default_font_size, theme.default_font_size)
        self.assertEqual(theme2.default_font_color, theme.default_font_color)
        self.assertEqual(theme2.colors["Panel/bg_color"], [20, 20, 40, 255])
        self.assertEqual(theme2.fonts["default"], "fonts/main.otf")

    def test_theme_stylebox(self) -> None:
        theme = ThemeResource(resource_id="t2", name="UITheme")
        sb = StyleBoxResource(resource_id="box_panel", name="PanelBg")
        theme.set_stylebox("Panel", sb)

        retrieved = theme.get_stylebox("Panel")
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.resource_id, "box_panel")
        self.assertEqual(retrieved.name, "PanelBg")

        missing = theme.get_stylebox("Button")
        self.assertIsNone(missing)

    def test_theme_colors(self) -> None:
        theme = ThemeResource(resource_id="t_color", name="ColorTheme")
        theme.set_color("Panel/bg_color", (10, 10, 30, 255))
        theme.set_color("Button/font_color", (255, 200, 0, 255))

        c1 = theme.get_color("Panel/bg_color")
        self.assertEqual(c1, (10, 10, 30, 255))

        c2 = theme.get_color("Button/font_color")
        self.assertEqual(c2, (255, 200, 0, 255))

        missing = theme.get_color("Nonexistent/key")
        self.assertIsNone(missing)


class TestCanvasThemeRef(unittest.TestCase):
    def test_canvas_theme_ref(self) -> None:
        canvas = Canvas(theme_resource_path="res://themes/dark_theme.json")
        self.assertEqual(canvas.theme_resource_path, "res://themes/dark_theme.json")

        d = canvas.to_dict()
        self.assertIn("theme_resource_path", d)
        self.assertEqual(d["theme_resource_path"], "res://themes/dark_theme.json")

        canvas2 = Canvas.from_dict(d)
        self.assertEqual(canvas2.theme_resource_path, "res://themes/dark_theme.json")

        # Default canvas has empty theme path
        canvas_default = Canvas()
        self.assertEqual(canvas_default.theme_resource_path, "")
        dd = canvas_default.to_dict()
        self.assertEqual(dd["theme_resource_path"], "")


if __name__ == "__main__":
    unittest.main()
