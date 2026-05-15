"""Tests for Control dirty flags and cache (E5)."""
import unittest
from engine.editor.ui_core.controls.control import Control, Label, Button, Panel
from engine.editor.ui_core.controls.events import Anchor, Margin, Size


class TestControlDirty(unittest.TestCase):
    def test_new_control_is_dirty(self):
        c = Control(name="test")
        self.assertTrue(c.is_dirty)

    def test_mark_clean(self):
        c = Control(name="test")
        c.mark_clean()
        self.assertFalse(c.is_dirty)

    def test_mark_dirty(self):
        c = Control(name="test")
        c.mark_clean()
        c.mark_dirty()
        self.assertTrue(c.is_dirty)

    def test_arrange_runs_even_when_clean(self):
        c = Control(name="test")
        c.mark_clean()
        c.arrange((10.0, 20.0, 30.0, 40.0))
        self.assertEqual(c._rect, (10.0, 20.0, 30.0, 40.0))
        self.assertFalse(c.is_dirty)

    def test_arrange_runs_when_dirty(self):
        c = Control(name="test")
        c.arrange((10.0, 20.0, 30.0, 40.0))
        self.assertEqual(c._rect, (10.0, 20.0, 30.0, 40.0))
        self.assertFalse(c.is_dirty)

    def test_add_child_sets_dirty(self):
        parent = Control(name="parent")
        parent.mark_clean()
        child = Control(name="child")
        parent.add_child(child)
        self.assertTrue(parent.is_dirty)

    def test_remove_child_sets_dirty(self):
        parent = Control(name="parent")
        child = Control(name="child")
        parent.add_child(child)
        parent.mark_clean()
        parent.remove_child(child)
        self.assertTrue(parent.is_dirty)


class TestLabelSetText(unittest.TestCase):
    def test_set_text_updates_text_and_dirty(self):
        label = Label(text="hello")
        label.mark_clean()
        label.set_text("world")
        self.assertEqual(label.text, "world")
        self.assertTrue(label.is_dirty)


class TestButtonSetText(unittest.TestCase):
    def test_set_text_updates_text_and_dirty(self):
        btn = Button(text="Click")
        btn.mark_clean()
        btn.set_text("Submit")
        self.assertEqual(btn.text, "Submit")
        self.assertTrue(btn.is_dirty)

    def test_arrange_runs_even_when_clean(self):
        btn = Button(text="OK")
        btn.mark_clean()
        btn.arrange((0, 0, 100, 30))
        self.assertEqual(btn._rect, (0, 0, 100, 30))
        self.assertFalse(btn.is_dirty)

    def test_arrange_runs_when_dirty(self):
        btn = Button(text="OK")
        btn.arrange((10, 20, 100, 30))
        self.assertEqual(btn._rect, (10, 20, 100, 30))
        self.assertFalse(btn.is_dirty)


class TestPanelDirty(unittest.TestCase):
    def test_panel_arrange_runs_even_when_clean(self):
        panel = Panel(name="p")
        panel.mark_clean()
        panel.arrange((5, 5, 200, 100))
        self.assertEqual(panel._rect, (5, 5, 200, 100))
        self.assertFalse(panel.is_dirty)

    def test_panel_arrange_runs_when_dirty(self):
        panel = Panel(name="p")
        panel.arrange((10, 10, 300, 200))
        self.assertEqual(panel._rect, (10, 10, 300, 200))
        self.assertFalse(panel.is_dirty)


if __name__ == "__main__":
    unittest.main()
