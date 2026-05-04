"""
tests/test_tween.py - Tests del componente Tween.
"""

import unittest

from engine.components.tween import Tween


class TweenTests(unittest.TestCase):
    def test_valores_por_defecto(self) -> None:
        tween = Tween()
        self.assertEqual(tween.property_path, "")
        self.assertEqual(tween.from_value, 0.0)
        self.assertEqual(tween.to_value, 1.0)
        self.assertEqual(tween.duration, 1.0)
        self.assertFalse(tween.autostart)
        self.assertTrue(tween.one_shot)
        self.assertEqual(tween.transition, "linear")
        self.assertTrue(tween.enabled)

    def test_progress(self) -> None:
        tween = Tween(duration=2.0)
        tween.start()
        self.assertEqual(tween.progress, 0.0)
        tween._elapsed = 1.0
        self.assertEqual(tween.progress, 0.5)
        tween._elapsed = 2.0
        self.assertEqual(tween.progress, 1.0)
        tween._elapsed = 3.0
        self.assertEqual(tween.progress, 1.0)

    def test_start_stop(self) -> None:
        tween = Tween()
        tween.start()
        self.assertTrue(tween.is_running)
        self.assertFalse(tween.is_finished)
        tween.stop()
        self.assertFalse(tween.is_running)

    def test_transition_coercion(self) -> None:
        tween = Tween(transition="invalid_transition")
        self.assertEqual(tween.transition, "linear")
        tween2 = Tween(transition="  quad_in  ")
        self.assertEqual(tween2.transition, "quad_in")

    def test_duration_minimo(self) -> None:
        tween = Tween(duration=0.0)
        self.assertGreater(tween.duration, 0.0)

    def test_serialization_round_trip(self) -> None:
        tween = Tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=100.0,
            duration=2.5,
            autostart=True,
            one_shot=False,
            transition="quad_out",
        )
        tween.enabled = False
        data = tween.to_dict()
        restored = Tween.from_dict(data)
        self.assertEqual(restored.property_path, "Transform.x")
        self.assertEqual(restored.from_value, 0.0)
        self.assertEqual(restored.to_value, 100.0)
        self.assertEqual(restored.duration, 2.5)
        self.assertTrue(restored.autostart)
        self.assertFalse(restored.one_shot)
        self.assertEqual(restored.transition, "quad_out")
        self.assertFalse(restored.enabled)


if __name__ == "__main__":
    unittest.main()
