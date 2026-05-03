"""
tests/test_polygon2d.py - Tests del componente Polygon2D.
"""

import unittest

from engine.components.polygon2d import Polygon2D


class Polygon2DComponentTests(unittest.TestCase):
    def test_default_values(self) -> None:
        poly = Polygon2D()
        self.assertTrue(poly.enabled)
        self.assertEqual(poly.points, [])
        self.assertEqual(poly.color, (255, 255, 255, 255))
        self.assertEqual(poly.texture_path, "")
        self.assertEqual(poly.offset_x, 0.0)
        self.assertEqual(poly.offset_y, 0.0)

    def test_color_clamps_short_sequence(self) -> None:
        poly = Polygon2D()
        poly.color = (100, 200)
        self.assertEqual(poly.color, (100, 200, 255, 255))

    def test_color_clamps_excess_elements(self) -> None:
        poly = Polygon2D()
        poly.color = (1, 2, 3, 4, 5)
        self.assertEqual(poly.color, (1, 2, 3, 4))

    def test_color_clamps_out_of_range(self) -> None:
        poly = Polygon2D()
        poly.color = (-10, 300, 128, 0)
        self.assertEqual(poly.color, (0, 255, 128, 0))

    def test_color_invalid_type_falls_back(self) -> None:
        poly = Polygon2D()
        poly.color = "not-a-tuple"
        self.assertEqual(poly.color, (255, 255, 255, 255))

    def test_to_dict_from_dict_roundtrip(self) -> None:
        poly = Polygon2D(
            points=[[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]],
            color=(255, 128, 0, 200),
            texture_path="img.png",
            offset_x=5.0,
            offset_y=15.0,
        )
        data = poly.to_dict()
        restored = Polygon2D.from_dict(data)
        self.assertEqual(restored.enabled, poly.enabled)
        self.assertEqual(restored.points, poly.points)
        self.assertEqual(restored.color, poly.color)
        self.assertEqual(restored.texture_path, poly.texture_path)
        self.assertEqual(restored.offset_x, poly.offset_x)
        self.assertEqual(restored.offset_y, poly.offset_y)

    def test_from_dict_restores_color(self) -> None:
        data = {
            "enabled": True,
            "points": [[0.0, 0.0], [10.0, 10.0], [20.0, 0.0]],
            "color": [10, 20, 30, 40],
            "texture": {"path": "img.png"},
            "texture_path": "img.png",
            "offset_x": 0.0,
            "offset_y": 0.0,
        }
        poly = Polygon2D.from_dict(data)
        self.assertEqual(poly.color, (10, 20, 30, 40))

    def test_from_dict_invalid_color_gets_clamped(self) -> None:
        data = {
            "enabled": True,
            "points": [[0.0, 0.0]],
            "color": ["bad"],
            "texture": {},
            "texture_path": "",
            "offset_x": 0.0,
            "offset_y": 0.0,
        }
        poly = Polygon2D.from_dict(data)
        self.assertEqual(poly.color, (255, 255, 255, 255))

    def test_asset_reference(self) -> None:
        poly = Polygon2D(texture_path="assets/terrain.png")
        ref = poly.get_texture_reference()
        self.assertEqual(ref["path"], "assets/terrain.png")
        self.assertEqual(ref["guid"], "")

    def test_sync_texture_reference(self) -> None:
        poly = Polygon2D()
        poly.sync_texture_reference({"path": "new_texture.png", "guid": "abc123"})
        self.assertEqual(poly.texture_path, "new_texture.png")
        ref = poly.get_texture_reference()
        self.assertEqual(ref["guid"], "abc123")

    def test_to_dict_serializes_color_as_list(self) -> None:
        poly = Polygon2D(color=(1, 2, 3, 4))
        data = poly.to_dict()
        self.assertEqual(data["color"], [1, 2, 3, 4])

    def test_to_dict_serializes_points(self) -> None:
        poly = Polygon2D(points=[[1.0, 2.0], [3.0, 4.0]])
        data = poly.to_dict()
        self.assertEqual(data["points"], [[1.0, 2.0], [3.0, 4.0]])

    def test_invalid_points_filtered_in_from_dict(self) -> None:
        data = {
            "enabled": True,
            "points": [[1.0, 2.0], "not-a-point", [3.0, 4.0], [5.0]],
            "color": [255, 255, 255, 255],
            "texture": {},
            "texture_path": "",
            "offset_x": 0.0,
            "offset_y": 0.0,
        }
        poly = Polygon2D.from_dict(data)
        self.assertEqual(poly.points, [[1.0, 2.0], [3.0, 4.0]])


if __name__ == "__main__":
    unittest.main()
