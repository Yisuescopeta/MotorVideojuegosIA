"""
tests/test_timer.py - Tests del componente Timer.
"""

import unittest

from engine.components.timer import Timer


class TimerTests(unittest.TestCase):
    def test_valores_por_defecto(self) -> None:
        timer = Timer()
        self.assertEqual(timer.wait_time, 1.0)
        self.assertFalse(timer.one_shot)
        self.assertFalse(timer.autostart)
        self.assertFalse(timer.paused)
        self.assertFalse(timer.ignore_time_scale)
        self.assertTrue(timer.enabled)
        self.assertTrue(timer.is_stopped)
        self.assertFalse(timer.is_running)
        self.assertEqual(timer.time_left, 0.0)

    def test_start_inicia_temporizador(self) -> None:
        timer = Timer(wait_time=2.0)
        timer.start()
        self.assertFalse(timer.is_stopped)
        self.assertTrue(timer.is_running)
        self.assertEqual(timer.time_left, 2.0)

    def test_start_con_tiempo_personalizado(self) -> None:
        timer = Timer(wait_time=1.0)
        timer.start(5.0)
        self.assertEqual(timer.wait_time, 5.0)
        self.assertEqual(timer.time_left, 5.0)

    def test_stop_detiene_temporizador(self) -> None:
        timer = Timer()
        timer.start()
        timer.stop()
        self.assertTrue(timer.is_stopped)
        self.assertFalse(timer.is_running)
        self.assertEqual(timer.time_left, 0.0)

    def test_pausa_reanuda(self) -> None:
        timer = Timer()
        timer.start()
        self.assertTrue(timer.is_running)
        timer.pause()
        self.assertFalse(timer.is_running)
        self.assertTrue(timer.paused)
        timer.resume()
        self.assertTrue(timer.is_running)
        self.assertFalse(timer.paused)

    def test_wait_time_minimo(self) -> None:
        timer = Timer(wait_time=0.0)
        self.assertGreater(timer.wait_time, 0.0)
        timer.start(0.0)
        self.assertGreater(timer.wait_time, 0.0)

    def test_serialization_round_trip(self) -> None:
        timer = Timer(wait_time=3.5, one_shot=True, autostart=True, paused=True, ignore_time_scale=True)
        timer.enabled = False
        data = timer.to_dict()
        restored = Timer.from_dict(data)
        self.assertEqual(restored.wait_time, 3.5)
        self.assertTrue(restored.one_shot)
        self.assertTrue(restored.autostart)
        self.assertTrue(restored.paused)
        self.assertTrue(restored.ignore_time_scale)
        self.assertFalse(restored.enabled)


if __name__ == "__main__":
    unittest.main()
