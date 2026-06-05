from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pyray as rl

from engine.editor.thumbnail_provider import ThumbnailProvider


class ThumbnailProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = ThumbnailProvider()

    def tearDown(self) -> None:
        self.provider.clear()

    def test_icon_info_for_supported_asset_types(self) -> None:
        cases = (
            ("assets", "", "dir", "folder"),
            ("hero.png", "", "file", "image"),
            ("logic.py", "", "file", "script"),
            ("enemy.prefab", "", "file", "prefab"),
            ("levels/intro.json", "", "file", "scene"),
            ("music.ogg", "", "file", "audio"),
            ("wall.material", "", "file", "material"),
            ("readme.txt", "", "file", "unknown"),
        )

        for path, kind, entry_type, expected in cases:
            with self.subTest(path=path):
                info = self.provider.get_thumbnail_info(path, kind, entry_type)
                self.assertEqual(info.icon_type, expected)
                self.assertFalse(info.uses_real_texture)

    def test_image_falls_back_without_ready_window(self) -> None:
        rect = rl.Rectangle(0, 0, 32, 32)
        item = {"absolute_path": "hero.png", "asset_kind": "texture", "entry_type": "file"}

        with patch.object(rl, "is_window_ready", return_value=False, create=True), patch.object(
            rl, "load_texture", create=True
        ) as load_texture, patch.object(rl, "draw_rectangle_rec", create=True), patch.object(
            rl, "draw_rectangle_lines_ex", create=True
        ), patch.object(rl, "draw_text", create=True):
            info = self.provider.draw_item_icon(rect, item)

        self.assertEqual(info.icon_type, "image")
        self.assertFalse(info.uses_real_texture)
        load_texture.assert_not_called()

    def test_mocked_texture_load_cache_and_draw_path(self) -> None:
        rect = rl.Rectangle(0, 0, 32, 32)
        texture = SimpleNamespace(width=16, height=8)
        item = {"absolute_path": "hero.png", "asset_kind": "texture", "entry_type": "file"}

        with patch.object(rl, "is_window_ready", return_value=True, create=True), patch.object(
            rl, "load_texture", return_value=texture, create=True
        ) as load_texture, patch.object(rl, "is_texture_ready", return_value=True, create=True), patch.object(
            rl, "draw_texture_pro", create=True
        ) as draw_texture_pro:
            first = self.provider.draw_item_icon(rect, item)
            second = self.provider.draw_item_icon(rect, item)

        self.assertTrue(first.uses_real_texture)
        self.assertTrue(second.uses_real_texture)
        load_texture.assert_called_once()
        self.assertEqual(draw_texture_pro.call_count, 2)

    def test_clear_unloads_cached_textures(self) -> None:
        rect = rl.Rectangle(0, 0, 32, 32)
        texture = SimpleNamespace(width=16, height=8)
        item = {"absolute_path": "hero.png", "asset_kind": "texture", "entry_type": "file"}

        with patch.object(rl, "is_window_ready", return_value=True, create=True), patch.object(
            rl, "load_texture", return_value=texture, create=True
        ), patch.object(rl, "is_texture_ready", return_value=True, create=True), patch.object(
            rl, "draw_texture_pro", create=True
        ), patch.object(rl, "unload_texture", create=True) as unload_texture:
            self.provider.draw_item_icon(rect, item)
            self.provider.clear()

        unload_texture.assert_called_once_with(texture)

    def test_non_image_asset_uses_draw_icon(self) -> None:
        rect = rl.Rectangle(0, 0, 32, 32)
        item = {"absolute_path": "enemy.prefab", "asset_kind": "prefab", "entry_type": "file"}

        with patch("engine.editor.thumbnail_provider.draw_icon", return_value=None) as draw_icon_mock, patch.object(
            rl, "draw_rectangle_rec", create=True
        ), patch.object(rl, "draw_rectangle_lines_ex", create=True), patch.object(
            rl, "draw_text", create=True
        ):
            info = self.provider.draw_item_icon(rect, item)

        self.assertEqual(info.icon_type, "prefab")
        draw_icon_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
