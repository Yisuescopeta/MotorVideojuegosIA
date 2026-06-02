"""
tests/test_sprite_component.py - Tests del componente Sprite.
"""

import unittest

from engine.components.sprite import Sprite


class SpriteComponentTests(unittest.TestCase):
    def test_tint_default(self) -> None:
        sprite = Sprite()
        self.assertEqual(sprite.tint, (255, 255, 255, 255))

    def test_tint_clamps_short_sequence(self) -> None:
        sprite = Sprite()
        sprite.tint = (100, 200)
        self.assertEqual(sprite.tint, (100, 200, 255, 255))

    def test_tint_clamps_excess_elements(self) -> None:
        sprite = Sprite()
        sprite.tint = (1, 2, 3, 4, 5)
        self.assertEqual(sprite.tint, (1, 2, 3, 4))

    def test_tint_clamps_out_of_range(self) -> None:
        sprite = Sprite()
        sprite.tint = (-10, 300, 128, 0)
        self.assertEqual(sprite.tint, (0, 255, 128, 0))

    def test_tint_invalid_type_falls_back(self) -> None:
        sprite = Sprite()
        sprite.tint = "not-a-tuple"
        self.assertEqual(sprite.tint, (255, 255, 255, 255))

    def test_tint_invalid_element_type_falls_back(self) -> None:
        sprite = Sprite()
        sprite.tint = ("a", "b", "c", "d")
        self.assertEqual(sprite.tint, (255, 255, 255, 255))

    def test_from_dict_restores_tint(self) -> None:
        data = {
            "enabled": True,
            "texture": {"path": "img.png"},
            "texture_path": "img.png",
            "width": 32,
            "height": 32,
            "origin_x": 0.5,
            "origin_y": 0.5,
            "flip_x": False,
            "flip_y": False,
            "tint": [10, 20, 30, 40],
        }
        sprite = Sprite.from_dict(data)
        self.assertEqual(sprite.tint, (10, 20, 30, 40))

    def test_from_dict_invalid_tint_gets_clamped(self) -> None:
        data = {
            "enabled": True,
            "texture": {"path": "img.png"},
            "texture_path": "img.png",
            "width": 0,
            "height": 0,
            "origin_x": 0.5,
            "origin_y": 0.5,
            "flip_x": False,
            "flip_y": False,
            "tint": ["oops"],
        }
        sprite = Sprite.from_dict(data)
        self.assertEqual(sprite.tint, (255, 255, 255, 255))

    def test_to_dict_serializes_tint_as_list(self) -> None:
        sprite = Sprite(tint=(1, 2, 3, 4))
        d = sprite.to_dict()
        self.assertEqual(d["tint"], [1, 2, 3, 4])

    def test_source_slice_default_empty(self) -> None:
        sprite = Sprite()
        self.assertEqual(sprite.source_slice, "")

    def test_source_slice_constructor(self) -> None:
        sprite = Sprite(source_slice="my_slice")
        self.assertEqual(sprite.source_slice, "my_slice")

    def test_source_slice_serialization(self) -> None:
        sprite = Sprite(source_slice="hero_idle", tint=(1, 2, 3, 4))
        d = sprite.to_dict()
        self.assertEqual(d["source_slice"], "hero_idle")

    def test_source_slice_deserialization(self) -> None:
        data = {
            "enabled": True,
            "texture": {"path": "img.png"},
            "texture_path": "img.png",
            "width": 32,
            "height": 32,
            "origin_x": 0.5,
            "origin_y": 0.5,
            "flip_x": False,
            "flip_y": False,
            "tint": [255, 255, 255, 255],
            "source_slice": "icon_sword",
        }
        sprite = Sprite.from_dict(data)
        self.assertEqual(sprite.source_slice, "icon_sword")

    def test_source_slice_deserialization_missing_defaults_empty(self) -> None:
        data = {
            "enabled": True,
            "texture": {"path": "img.png"},
            "texture_path": "img.png",
            "width": 0,
            "height": 0,
            "origin_x": 0.5,
            "origin_y": 0.5,
            "flip_x": False,
            "flip_y": False,
            "tint": [255, 255, 255, 255],
        }
        sprite = Sprite.from_dict(data)
        self.assertEqual(sprite.source_slice, "")

    def test_full_roundtrip_with_source_slice(self) -> None:
        sprite = Sprite(
            texture_path="spritesheet.png",
            width=64,
            height=64,
            source_slice="walk_01",
            tint=(100, 200, 50, 255),
        )
        data = sprite.to_dict()
        restored = Sprite.from_dict(data)
        self.assertEqual(restored.source_slice, "walk_01")
        self.assertEqual(restored.texture_path, "spritesheet.png")
        self.assertEqual(restored.width, 64)
        self.assertEqual(restored.height, 64)
        self.assertEqual(restored.tint, (100, 200, 50, 255))


if __name__ == "__main__":
    unittest.main()
