"""Tests for editor animation system (E1)."""
import unittest
from engine.editor.ui.animation import AnimationController, LerpValue, ColorLerp, PanelAnimation


class TestLerpValue(unittest.TestCase):
    def test_initial_current_is_zero(self):
        lv = LerpValue()
        self.assertEqual(lv.current, 0.0)

    def test_tick_moves_toward_target(self):
        lv = LerpValue(current=0.0, target=10.0, speed=10.0)
        result = lv.tick(0.1)
        self.assertGreater(result, 0.0)
        self.assertLessEqual(result, 10.0)

    def test_tick_converges_at_target(self):
        lv = LerpValue(current=9.999, target=10.0, speed=100.0)
        lv.tick(1.0)
        self.assertAlmostEqual(lv.current, 10.0, places=3)

    def test_is_done(self):
        lv = LerpValue(current=5.0, target=5.0)
        self.assertTrue(lv.is_done)
        lv.set_target(10.0)
        self.assertFalse(lv.is_done)

    def test_set_target(self):
        lv = LerpValue(target=5.0)
        lv.set_target(20.0)
        self.assertEqual(lv.target, 20.0)


class TestColorLerp(unittest.TestCase):
    def test_tick_blends_colors(self):
        cl = ColorLerp(current=(0, 0, 0, 255), target=(255, 255, 255, 255), speed=10.0)
        result = cl.tick(0.5)
        self.assertGreater(result[0], 0)
        self.assertLessEqual(result[0], 255)

    def test_is_done(self):
        cl = ColorLerp(current=(10, 20, 30, 255), target=(10, 20, 30, 255))
        self.assertTrue(cl.is_done)


class TestPanelAnimation(unittest.TestCase):
    def test_tick_returns_tuple(self):
        pa = PanelAnimation()
        result = pa.tick(0.1)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


class TestAnimationController(unittest.TestCase):
    def test_get_lerp_creates_once(self):
        ac = AnimationController()
        a = ac.get_lerp("test")
        b = ac.get_lerp("test")
        self.assertIs(a, b)

    def test_get_color_lerp_creates_once(self):
        ac = AnimationController()
        a = ac.get_color_lerp("btn")
        b = ac.get_color_lerp("btn")
        self.assertIs(a, b)

    def test_get_panel_creates_once(self):
        ac = AnimationController()
        a = ac.get_panel("panel1")
        b = ac.get_panel("panel1")
        self.assertIs(a, b)

    def test_tick_all_runs_without_error(self):
        ac = AnimationController()
        ac.get_lerp("a")
        ac.get_color_lerp("b")
        ac.get_panel("c")
        ac.tick_all(0.016)


if __name__ == "__main__":
    unittest.main()
