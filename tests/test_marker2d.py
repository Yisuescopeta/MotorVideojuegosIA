"""
tests/test_marker2d.py - Tests del componente Marker2D.
"""

import unittest

from engine.components.marker2d import Marker2D


class Marker2DTests(unittest.TestCase):
    def test_valores_por_defecto(self) -> None:
        marker = Marker2D()
        self.assertEqual(marker.marker_name, "")
        self.assertEqual(marker.offset_x, 0.0)
        self.assertEqual(marker.offset_y, 0.0)
        self.assertTrue(marker.enabled)

    def test_construccion_con_parametros(self) -> None:
        marker = Marker2D(marker_name="SpawnPlayer", offset_x=10.5, offset_y=-3.2)
        self.assertEqual(marker.marker_name, "SpawnPlayer")
        self.assertEqual(marker.offset_x, 10.5)
        self.assertEqual(marker.offset_y, -3.2)

    def test_serialization_round_trip(self) -> None:
        marker = Marker2D(marker_name="Checkpoint1", offset_x=100.0, offset_y=200.0)
        marker.enabled = False
        data = marker.to_dict()
        restored = Marker2D.from_dict(data)
        self.assertEqual(restored.marker_name, "Checkpoint1")
        self.assertEqual(restored.offset_x, 100.0)
        self.assertEqual(restored.offset_y, 200.0)
        self.assertFalse(restored.enabled)

    def test_nombre_vacío_por_defecto(self) -> None:
        marker = Marker2D()
        self.assertEqual(marker.marker_name, "")
        data = marker.to_dict()
        self.assertEqual(data["marker_name"], "")


if __name__ == "__main__":
    unittest.main()
