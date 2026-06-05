from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from engine.editor.ui import icon_provider


class IconProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        icon_provider.reset_cache()

    def tearDown(self) -> None:
        icon_provider.reset_cache()

    def test_icon_exists_recognizes_manifest_alias_and_direct_name(self) -> None:
        self.assertTrue(icon_provider.icon_exists("play"))
        self.assertTrue(icon_provider.icon_exists("image"))
        self.assertTrue(icon_provider.icon_exists("step_forward"))
        self.assertFalse(icon_provider.icon_exists("not_real"))

    def test_icon_exists_in_pack_recognizes_godot_alias(self) -> None:
        self.assertTrue(icon_provider.icon_exists_in_pack("godot_hierarchy", "entity"))
        self.assertTrue(icon_provider.icon_exists_in_pack("godot_hierarchy", "light"))
        self.assertFalse(icon_provider.icon_exists_in_pack("godot_hierarchy", "play"))

    def test_draw_icon_returns_false_without_window_ready(self) -> None:
        with patch("engine.editor.ui.icon_provider._load_texture_for_pack", return_value=None):
            self.assertFalse(
                icon_provider.draw_icon("play", (0.0, 0.0, 16.0, 16.0), (255, 255, 255, 255), size=16)
            )
            self.assertFalse(
                icon_provider.draw_icon_from_pack(
                    "godot_hierarchy",
                    "entity",
                    (0.0, 0.0, 16.0, 16.0),
                    (255, 255, 255, 255),
                    size=16,
                )
            )

    def test_draw_icon_uses_lucide_atlas_when_texture_is_ready(self) -> None:
        fake_texture = MagicMock()
        fake_rl = MagicMock()
        fake_rl.Rectangle.side_effect = lambda x, y, w, h: MagicMock(x=x, y=y, width=w, height=h)
        fake_rl.Vector2.side_effect = lambda x, y: (x, y)
        requested_color = (12, 34, 56, 255)
        ray_color = MagicMock()

        with patch("engine.editor.ui.icon_provider._rl", return_value=fake_rl), patch(
            "engine.editor.ui.icon_provider._load_texture_for_pack", return_value=fake_texture
        ), patch("engine.editor.ui.icon_provider.to_ray_color", return_value=ray_color) as to_ray_color:
            drawn = icon_provider.draw_icon("play", (0.0, 0.0, 24.0, 24.0), requested_color, size=24)

        self.assertTrue(drawn)
        fake_rl.draw_texture_pro.assert_called_once()
        to_ray_color.assert_called_once_with(requested_color)
        self.assertIs(fake_rl.draw_texture_pro.call_args[0][-1], ray_color)

    def test_draw_icon_uses_godot_atlas_when_texture_is_ready(self) -> None:
        fake_texture = MagicMock()
        fake_rl = MagicMock()
        fake_rl.Rectangle.side_effect = lambda x, y, w, h: MagicMock(x=x, y=y, width=w, height=h)
        fake_rl.Vector2.side_effect = lambda x, y: (x, y)

        with patch("engine.editor.ui.icon_provider._rl", return_value=fake_rl), patch(
            "engine.editor.ui.icon_provider._load_texture_for_pack", return_value=fake_texture
        ), patch("engine.editor.ui.icon_provider.to_ray_color", return_value=MagicMock()):
            drawn = icon_provider.draw_icon_from_pack(
                "godot_hierarchy",
                "entity",
                (0.0, 0.0, 24.0, 24.0),
                (255, 255, 255, 255),
                size=24,
            )

        self.assertTrue(drawn)
        fake_rl.draw_texture_pro.assert_called_once()

    def test_reset_cache_unloads_texture_when_present(self) -> None:
        fake_lucide_texture = object()
        fake_godot_texture = object()
        fake_rl = MagicMock()
        with patch("engine.editor.ui.icon_provider._rl", return_value=fake_rl):
            icon_provider._texture_cache["lucide"] = fake_lucide_texture
            icon_provider._texture_cache["godot_hierarchy"] = fake_godot_texture
            icon_provider.reset_cache()

        self.assertEqual(fake_rl.unload_texture.call_count, 2)

    def test_generated_lucide_play_icon_pixels_are_white(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads((root / "engine/editor/resources/icons/lucide_atlas.json").read_text(encoding="utf-8"))
        frame = metadata["icons"]["play"]["24"]
        atlas = Image.open(root / "engine/editor/resources/icons/lucide_atlas.png").convert("RGBA")

        non_transparent_pixels = []
        for y in range(frame["y"], frame["y"] + frame["h"]):
            for x in range(frame["x"], frame["x"] + frame["w"]):
                pixel = atlas.getpixel((x, y))
                if pixel[3] > 0:
                    non_transparent_pixels.append(pixel)
                    if len(non_transparent_pixels) >= 8:
                        break
            if len(non_transparent_pixels) >= 8:
                break

        self.assertTrue(non_transparent_pixels)
        for red, green, blue, _alpha in non_transparent_pixels:
            self.assertEqual((red, green, blue), (255, 255, 255))

    def test_generated_godot_camera_icon_pixels_preserve_color(self) -> None:
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads(
            (root / "engine/editor/resources/icons/godot/godot_hierarchy_atlas.json").read_text(encoding="utf-8")
        )
        frame = metadata["icons"]["camera"]["24"]
        atlas = Image.open(root / "engine/editor/resources/icons/godot/godot_hierarchy_atlas.png").convert("RGBA")

        non_transparent_pixels = []
        for y in range(frame["y"], frame["y"] + frame["h"]):
            for x in range(frame["x"], frame["x"] + frame["w"]):
                pixel = atlas.getpixel((x, y))
                if pixel[3] > 0:
                    non_transparent_pixels.append(pixel)
                    if len(non_transparent_pixels) >= 8:
                        break
            if len(non_transparent_pixels) >= 8:
                break

        self.assertTrue(non_transparent_pixels)
        self.assertTrue(any((red, green, blue) != (255, 255, 255) for red, green, blue, _alpha in non_transparent_pixels))


if __name__ == "__main__":
    unittest.main()
