"""
tests/test_tween.py - Tests del componente Tween.
"""

import unittest

from engine.components.tween import Tween, TweenTransition, TweenEase


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
        tween = Tween(property_path="Transform.x", duration=2.0)
        tween.start()
        self.assertEqual(tween.progress, 0.0)
        tween._elapsed = 1.0
        self.assertEqual(tween.progress, 0.5)
        tween._elapsed = 2.0
        self.assertEqual(tween.progress, 1.0)
        tween._elapsed = 3.0
        self.assertEqual(tween.progress, 1.0)

    def test_start_stop(self) -> None:
        tween = Tween(property_path="Transform.x")
        tween.start()
        self.assertTrue(tween.is_running)
        self.assertFalse(tween.is_finished)
        tween.stop()
        self.assertFalse(tween.is_running)

    def test_transition_coercion(self) -> None:
        tween = Tween(property_path="Transform.x", transition="invalid_transition")
        self.assertEqual(tween.transition, "linear")
        tween2 = Tween(property_path="Transform.x", transition="  quad_in  ")
        self.assertEqual(tween2.transition, "quad")

    def test_duration_minimo(self) -> None:
        tween = Tween(property_path="Transform.x", duration=0.0)
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
        # New format has steps array
        self.assertIn("steps", data)
        self.assertEqual(len(data["steps"]), 1)
        step = data["steps"][0]
        self.assertEqual(step["property_path"], "Transform.x")
        self.assertEqual(step["from_value"], 0.0)
        self.assertEqual(step["to_value"], 100.0)
        self.assertEqual(step["duration"], 2.5)
        self.assertEqual(step["transition"], "quad")
        self.assertEqual(step["ease"], "ease_out")

        restored = Tween.from_dict(data)
        self.assertEqual(restored.property_path, "Transform.x")
        self.assertEqual(restored.from_value, 0.0)
        self.assertEqual(restored.to_value, 100.0)
        self.assertEqual(restored.duration, 2.5)
        self.assertTrue(restored.autostart)
        self.assertFalse(restored.one_shot)
        self.assertEqual(restored.transition, "quad")
        self.assertTrue(restored.enabled is False)

    def test_legacy_from_dict_round_trip(self) -> None:
        """from_dict debe aceptar el formato legacy y convertirlo."""
        legacy_data = {
            "enabled": True,
            "property_path": "Transform.y",
            "from_value": 10.0,
            "to_value": 50.0,
            "duration": 1.5,
            "autostart": True,
            "one_shot": False,
            "transition": "sine_in_out",
        }
        tween = Tween.from_dict(legacy_data)
        self.assertEqual(tween.property_path, "Transform.y")
        self.assertEqual(tween.from_value, 10.0)
        self.assertEqual(tween.to_value, 50.0)
        self.assertEqual(tween.duration, 1.5)
        self.assertTrue(tween.autostart)
        self.assertEqual(len(tween.steps), 1)
        self.assertEqual(tween.steps[0].transition, TweenTransition.SINE)
        self.assertEqual(tween.steps[0].ease, TweenEase.EASE_IN_OUT)

    def test_tween_property_builder(self) -> None:
        tween = Tween()
        tween.tween_property("Player", "Transform", "Transform.x", 100.0, 2.0)
        tween.set_trans("cubic")
        tween.set_ease("ease_in")
        tween.set_delay(0.5)
        self.assertEqual(len(tween.steps), 1)
        step = tween.steps[0]
        self.assertEqual(step.target_entity, "Player")
        self.assertEqual(step.to_value, 100.0)
        self.assertEqual(step.transition, TweenTransition.CUBIC)
        self.assertEqual(step.ease, TweenEase.EASE_IN)
        self.assertAlmostEqual(step.delay, 0.5)

    def test_chain_and_parallel_flags(self) -> None:
        tween = Tween()
        self.assertFalse(tween.parallel)
        tween.chain()
        self.assertFalse(tween.parallel)
        tween.set_parallel(True)
        self.assertTrue(tween.parallel)

    def test_default_transition_ease(self) -> None:
        tween = Tween()
        tween.default_transition = TweenTransition.BOUNCE
        tween.default_ease = TweenEase.EASE_OUT_IN
        tween.tween_property("A", "T", "T.x", 50.0, 1.0)
        self.assertEqual(tween.steps[0].transition, TweenTransition.BOUNCE)
        self.assertEqual(tween.steps[0].ease, TweenEase.EASE_OUT_IN)


if __name__ == "__main__":
    unittest.main()
