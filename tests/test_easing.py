"""
tests/test_easing.py - Tests de funciones de interpolacion (easing).
"""

import unittest

from engine.utils.easing import (
    EASING_FUNCTIONS,
    cubic_in,
    cubic_in_out,
    cubic_out,
    expo_in,
    expo_in_out,
    expo_out,
    get_easing,
    linear,
    quad_in,
    quad_in_out,
    quad_out,
    sine_in,
    sine_in_out,
    sine_out,
)


class EasingTests(unittest.TestCase):
    def test_linear(self) -> None:
        self.assertEqual(linear(0.0), 0.0)
        self.assertEqual(linear(0.5), 0.5)
        self.assertEqual(linear(1.0), 1.0)

    def test_sine_boundaries(self) -> None:
        for func in (sine_in, sine_out, sine_in_out):
            self.assertAlmostEqual(func(0.0), 0.0, places=5)
            self.assertAlmostEqual(func(1.0), 1.0, places=5)

    def test_quad_boundaries(self) -> None:
        for func in (quad_in, quad_out, quad_in_out):
            self.assertAlmostEqual(func(0.0), 0.0, places=5)
            self.assertAlmostEqual(func(1.0), 1.0, places=5)

    def test_cubic_boundaries(self) -> None:
        for func in (cubic_in, cubic_out, cubic_in_out):
            self.assertAlmostEqual(func(0.0), 0.0, places=5)
            self.assertAlmostEqual(func(1.0), 1.0, places=5)

    def test_expo_boundaries(self) -> None:
        for func in (expo_in, expo_out, expo_in_out):
            self.assertAlmostEqual(func(0.0), 0.0, places=5)
            self.assertAlmostEqual(func(1.0), 1.0, places=5)

    def test_monotonic_increasing_in_0_1(self) -> None:
        for name, func in EASING_FUNCTIONS.items():
            prev = func(0.0)
            for t in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
                val = func(t)
                self.assertGreaterEqual(
                    val, prev - 1e-6,
                    f"{name} no es monotono creciente en t={t}: {prev} -> {val}"
                )
                prev = val

    def test_get_easing_fallback(self) -> None:
        self.assertIs(get_easing("nonexistent"), linear)
        self.assertIs(get_easing("quad_in"), quad_in)
        self.assertIs(get_easing("  Expo_Out  "), expo_out)


if __name__ == "__main__":
    unittest.main()
