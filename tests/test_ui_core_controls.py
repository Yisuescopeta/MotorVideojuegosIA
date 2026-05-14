"""Tests for retained-mode control tree (Fase 11)."""

import json
import sys
import unittest

from engine.editor.ui_core.controls.events import (
    ControlEvent,
    ControlEventKind,
    Margin,
    Size,
)
from engine.editor.ui_core.controls.control import Button, Control, Label, Panel, TextureRect
from engine.editor.ui_core.controls.container import (
    Container,
    HBoxContainer,
    LayoutDirection,
    ScrollContainer,
    VBoxContainer,
)
from engine.editor.ui_core.controls.focus import FocusManager


class TestSize(unittest.TestCase):
    def test_size_creation(self):
        s = Size(100.0, 50.0)
        self.assertEqual(s.width, 100.0)
        self.assertEqual(s.height, 50.0)
        self.assertEqual(s.min_axis, 50.0)

    def test_size_add(self):
        s1 = Size(10.0, 20.0)
        s2 = Size(5.0, 8.0)
        result = s1 + s2
        self.assertEqual(result.width, 15.0)
        self.assertEqual(result.height, 28.0)

    def test_size_max(self):
        s1 = Size(10.0, 30.0)
        s2 = Size(20.0, 10.0)
        result = s1.max(s2)
        self.assertEqual(result.width, 20.0)
        self.assertEqual(result.height, 30.0)

    def test_size_div(self):
        s = Size(100.0, 50.0)
        result = s / 2.0
        self.assertEqual(result.width, 50.0)
        self.assertEqual(result.height, 25.0)


class TestControlEvents(unittest.TestCase):
    def test_event_kinds(self):
        kinds = list(ControlEventKind)
        self.assertIn(ControlEventKind.CLICK, kinds)
        self.assertIn(ControlEventKind.MOUSE_ENTER, kinds)
        self.assertIn(ControlEventKind.MOUSE_EXIT, kinds)
        self.assertIn(ControlEventKind.FOCUS_GAIN, kinds)
        self.assertIn(ControlEventKind.FOCUS_LOST, kinds)
        self.assertIn(ControlEventKind.DRAG_START, kinds)
        self.assertIn(ControlEventKind.DRAG, kinds)
        self.assertIn(ControlEventKind.DRAG_END, kinds)
        self.assertIn(ControlEventKind.KEY_DOWN, kinds)
        self.assertIn(ControlEventKind.KEY_UP, kinds)
        self.assertIn(ControlEventKind.RESIZED, kinds)
        self.assertIn(ControlEventKind.SCROLL, kinds)

    def test_event_creation(self):
        evt = ControlEvent(ControlEventKind.CLICK, global_x=50.0, global_y=30.0)
        self.assertEqual(evt.kind, ControlEventKind.CLICK)
        self.assertFalse(evt.consumed)
        self.assertEqual(evt.global_x, 50.0)
        self.assertEqual(evt.global_y, 30.0)


class TestControlBase(unittest.TestCase):
    def test_control_defaults(self):
        c = Control(name="test")
        self.assertEqual(c.name, "test")
        self.assertTrue(c.visible)
        self.assertFalse(c.disabled)
        self.assertEqual(c.rect, (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(c.children, [])
        self.assertIsNone(c.parent)

    def test_add_remove_child(self):
        parent = Control(name="parent")
        child = Control(name="child")
        parent.add_child(child)
        self.assertIn(child, parent.children)
        self.assertIs(child.parent, parent)

        parent.remove_child(child)
        self.assertNotIn(child, parent.children)
        self.assertIsNone(child.parent)

    def test_find_child(self):
        root = Control(name="root")
        a = Control(name="A")
        b = Control(name="B")
        root.add_child(a)
        a.add_child(b)

        self.assertIs(root.find_child("A"), a)
        self.assertIs(root.find_child("B"), b)
        self.assertIsNone(root.find_child("C"))

    def test_global_rect(self):
        root = Control(name="root")
        root.arrange((10.0, 20.0, 200.0, 100.0))
        child = Control(name="child")
        root.add_child(child)
        child.arrange((5.0, 5.0, 50.0, 30.0))

        gr = child.global_rect
        self.assertEqual(gr, (15.0, 25.0, 50.0, 30.0))

    def test_contains_point(self):
        root = Control(name="root")
        root.arrange((0.0, 0.0, 100.0, 100.0))
        child = Control(name="child")
        root.add_child(child)
        child.arrange((10.0, 10.0, 50.0, 50.0))

        self.assertTrue(child.contains_point(20.0, 20.0))
        self.assertTrue(child.contains_point(60.0, 60.0))
        self.assertFalse(child.contains_point(5.0, 5.0))
        self.assertFalse(child.contains_point(70.0, 70.0))

    def test_to_local(self):
        root = Control(name="root")
        root.arrange((100.0, 100.0, 200.0, 200.0))
        child = Control(name="child")
        root.add_child(child)
        child.arrange((20.0, 30.0, 60.0, 40.0))

        lx, ly = child.to_local(130.0, 140.0)
        self.assertAlmostEqual(lx, 10.0)
        self.assertAlmostEqual(ly, 10.0)

    def test_measure_min_size(self):
        c = Control(name="test")
        s = c.measure(Size(100.0, 100.0))
        self.assertEqual(s.width, 0.0)
        self.assertEqual(s.height, 0.0)

    def test_measure_with_custom_min_size(self):
        c = Control(name="test", custom_min_size=Size(30.0, 20.0))
        s = c.measure(Size(100.0, 100.0))
        self.assertEqual(s.width, 30.0)
        self.assertEqual(s.height, 20.0)

    def test_measure_with_margin(self):
        c = Control(name="test", margin=Margin(4.0, 4.0, 4.0, 4.0))
        s = c.measure(Size(100.0, 100.0))
        self.assertEqual(s.width, 8.0)
        self.assertEqual(s.height, 8.0)

    def test_dispatch_click_callback(self):
        called = []
        btn = Button(name="btn")
        btn.on_click = lambda c, e: called.append(True)
        evt = ControlEvent(ControlEventKind.CLICK)
        btn.dispatch(evt)
        self.assertTrue(called)

    def test_dispatch_focus_gain(self):
        c = Control(name="test")
        self.assertFalse(c.focused)
        c.dispatch(ControlEvent(ControlEventKind.FOCUS_GAIN))
        self.assertTrue(c.focused)

    def test_dispatch_focus_lost(self):
        c = Control(name="test", _focused=True)
        self.assertTrue(c.focused)
        c.dispatch(ControlEvent(ControlEventKind.FOCUS_LOST))
        self.assertFalse(c.focused)

    def test_invisible_control_skips_dispatch(self):
        c = Control(name="test", visible=False)
        c.on_click = lambda c, e: None
        result = c.dispatch(ControlEvent(ControlEventKind.CLICK))
        self.assertFalse(result)


class TestLabel(unittest.TestCase):
    def test_label_measure(self):
        lbl = Label(name="lbl", text="Hello", font_size=12)
        s = lbl.measure(Size(100.0, 100.0))
        self.assertGreater(s.width, 0)
        self.assertGreater(s.height, 0)

    def test_label_empty(self):
        lbl = Label(name="lbl", text="")
        s = lbl.measure(Size(50.0, 50.0))
        self.assertGreaterEqual(s.width, 0.0)
        self.assertGreater(s.height, 0.0)


class TestButton(unittest.TestCase):
    def test_button_measure(self):
        btn = Button(name="btn", text="OK")
        s = btn.measure(Size(100.0, 100.0))
        self.assertGreater(s.width, 20.0)
        self.assertGreater(s.height, 20.0)

    def test_button_arrange(self):
        btn = Button(name="btn")
        btn.arrange((0.0, 0.0, 80.0, 30.0))
        self.assertEqual(btn.rect, (0.0, 0.0, 80.0, 30.0))


class TestPanel(unittest.TestCase):
    def test_panel_measure_empty(self):
        p = Panel(name="panel")
        s = p.measure(Size(200.0, 200.0))
        self.assertGreaterEqual(s.width, 0.0)
        self.assertGreaterEqual(s.height, 0.0)

    def test_panel_measure_with_children(self):
        p = Panel(name="panel")
        btn = Button(name="btn", text="OK")
        p.add_child(btn)
        s = p.measure(Size(200.0, 200.0))
        self.assertGreater(s.width, 0.0)
        self.assertGreater(s.height, 0.0)

    def test_panel_arrange_children(self):
        p = Panel(name="panel", margin=Margin(4.0, 4.0, 4.0, 4.0))
        btn = Button(name="btn")
        p.add_child(btn)
        p.arrange((0.0, 0.0, 200.0, 100.0))

        self.assertEqual(p.rect, (0.0, 0.0, 200.0, 100.0))
        self.assertEqual(btn.rect, (4.0, 4.0, 192.0, 92.0))


class TestTextureRect(unittest.TestCase):
    def test_texture_rect_measure(self):
        tr = TextureRect(name="img")
        s = tr.measure(Size(100.0, 100.0))
        self.assertGreaterEqual(s.width, 32.0)
        self.assertGreaterEqual(s.height, 32.0)


class TestContainer(unittest.TestCase):
    def test_container_defaults(self):
        c = Container(name="box")
        self.assertEqual(c.direction, LayoutDirection.VERTICAL)
        self.assertEqual(c.spacing, 0.0)
        self.assertEqual(c.alignment, "start")

    def test_vbox_measure(self):
        vbox = VBoxContainer(name="vbox")
        btn1 = Button(name="btn1", text="A")
        btn2 = Button(name="btn2", text="B")
        vbox.add_child(btn1)
        vbox.add_child(btn2)
        s = vbox.measure(Size(200.0, 200.0))
        self.assertGreater(s.height, 40.0)

    def test_hbox_measure(self):
        hbox = HBoxContainer(name="hbox", spacing=4.0)
        btn1 = Button(name="btn1", text="A")
        btn2 = Button(name="btn2", text="B")
        hbox.add_child(btn1)
        hbox.add_child(btn2)
        s = hbox.measure(Size(300.0, 100.0))
        self.assertGreater(s.width, 40.0)

    def test_hbox_arrange(self):
        hbox = HBoxContainer(name="hbox")
        btn1 = Button(name="btn1", text="A")
        btn2 = Button(name="btn2", text="B")
        hbox.add_child(btn1)
        hbox.add_child(btn2)
        hbox.arrange((0.0, 0.0, 200.0, 40.0))

        self.assertEqual(hbox.rect, (0.0, 0.0, 200.0, 40.0))
        self.assertGreater(btn2.rect[0], btn1.rect[0])

    def test_container_with_expand_h(self):
        hbox = HBoxContainer(name="hbox")
        btn1 = Button(name="btn1", text="A", expand_h=True)
        btn2 = Button(name="btn2", text="B", expand_h=True)
        hbox.add_child(btn1)
        hbox.add_child(btn2)
        hbox.arrange((0.0, 0.0, 200.0, 40.0))

        self.assertAlmostEqual(btn1.rect[2], 100.0, delta=2.0)
        self.assertAlmostEqual(btn2.rect[2], 100.0, delta=2.0)

    def test_container_with_margin(self):
        vbox = VBoxContainer(name="vbox", margin=Margin(5.0, 5.0, 5.0, 5.0))
        btn = Button(name="btn", text="A")
        vbox.add_child(btn)
        vbox.arrange((0.0, 0.0, 200.0, 100.0))
        self.assertEqual(btn.rect[0], 5.0)
        self.assertEqual(btn.rect[1], 5.0)


class TestScrollContainer(unittest.TestCase):
    def test_scroll_defaults(self):
        sc = ScrollContainer(name="scroll")
        s = sc.measure(Size(200.0, 200.0))
        self.assertGreaterEqual(s.width, 100.0)
        self.assertGreaterEqual(s.height, 100.0)


class TestFocusManager(unittest.TestCase):
    def test_empty_focus(self):
        fm = FocusManager()
        self.assertIsNone(fm.current)
        self.assertIsNone(fm.focused)

    def test_set_focus(self):
        fm = FocusManager()
        c = Control(name="test")
        fm.set_focus(c)
        self.assertIs(fm.current, c)

    def test_grab_ungrab(self):
        fm = FocusManager()
        c = Control(name="test")
        fm.grab(c)
        self.assertIs(fm.current, c)
        fm.ungrab()
        self.assertIsNone(fm.current)
        self.assertIs(fm.grabber, None)

    def test_build_tab_order(self):
        fm = FocusManager()
        root = Panel(name="root")
        a = Button(name="A", tab_index=2)
        b = Button(name="B", tab_index=1)
        c = Button(name="C", tab_index=3)
        d = Button(name="D", tab_index=0)  # invisible, should be skipped
        d.visible = False
        root.add_child(a)
        root.add_child(b)
        root.add_child(c)
        root.add_child(d)

        fm.build_tab_order(root)
        self.assertEqual(len(fm._tab_order), 3)
        self.assertEqual(fm._tab_order[0].name, "B")
        self.assertEqual(fm._tab_order[1].name, "A")
        self.assertEqual(fm._tab_order[2].name, "C")

    def test_focus_next_prev(self):
        fm = FocusManager()
        a = Button(name="A", tab_index=0)
        b = Button(name="B", tab_index=1)
        root = Panel(name="root")
        root.add_child(a)
        root.add_child(b)
        fm.build_tab_order(root)

        result = fm.focus_next()
        self.assertIs(result, a)
        self.assertIs(fm.current, a)

        result = fm.focus_next()
        self.assertIs(result, b)
        self.assertIs(fm.current, b)

        result = fm.focus_next()
        self.assertIs(result, a)

        result = fm.focus_prev()
        self.assertIs(result, b)

    def test_focus_next_empty(self):
        fm = FocusManager()
        result = fm.focus_next()
        self.assertIsNone(result)

    def test_pick_at(self):
        fm = FocusManager()
        root = Panel(name="root")
        root.arrange((0.0, 0.0, 500.0, 500.0))
        a = Button(name="A")
        b = Button(name="B")
        root.add_child(a)
        root.add_child(b)
        a.arrange((10.0, 10.0, 100.0, 30.0))
        b.arrange((10.0, 50.0, 100.0, 30.0))

        picked = fm.pick_at(root, 50.0, 20.0)
        self.assertIsNotNone(picked)
        self.assertEqual(picked.name, "A")

        picked = fm.pick_at(root, 50.0, 60.0)
        self.assertIsNotNone(picked)
        self.assertEqual(picked.name, "B")

        picked = fm.pick_at(root, 2000.0, 2000.0)
        self.assertIsNone(picked)

    def test_pick_at_nested(self):
        fm = FocusManager()
        root = Panel(name="root")
        root.arrange((0.0, 0.0, 500.0, 500.0))
        outer = Panel(name="outer")
        root.add_child(outer)
        outer.arrange((10.0, 10.0, 400.0, 400.0))
        inner = Button(name="inner")
        outer.add_child(inner)
        inner.arrange((10.0, 10.0, 100.0, 30.0))

        picked = fm.pick_at(root, 30.0, 30.0)
        self.assertIsNotNone(picked)
        self.assertEqual(picked.name, "inner")

    def test_clear_focus(self):
        fm = FocusManager()
        c = Control(name="test")
        fm.set_focus(c)
        fm.grab(c)
        fm.clear_focus()
        self.assertIsNone(fm.current)
        self.assertIsNone(fm.focused)
        self.assertIsNone(fm.grabber)


class TestControlsPurity(unittest.TestCase):
    def test_import_controls_does_not_import_pyray(self):
        sys.modules.pop("pyray", None)
        import engine.editor.ui_core.controls

        self.assertNotIn("pyray", sys.modules)

    def test_controls_modules_are_serializable(self):
        from engine.editor.ui_core.controls import (
            Button,
            Control,
            ControlEvent,
            ControlEventKind,
            FocusManager,
        )

        evt = ControlEvent(ControlEventKind.CLICK, global_x=10.0, global_y=20.0)
        serialized = json.dumps({
            "kind": evt.kind.name,
            "global_x": evt.global_x,
            "global_y": evt.global_y,
        })
        self.assertIsInstance(serialized, str)
        decoded = json.loads(serialized)
        self.assertEqual(decoded["kind"], "CLICK")
        self.assertEqual(decoded["global_x"], 10.0)

        ctrl = Button(name="TestBtn")
        self.assertEqual(ctrl.name, "TestBtn")
        fm = FocusManager()
        fm.set_focus(ctrl)
        self.assertIs(fm.current, ctrl)


class TestControlsFromUICoreInit(unittest.TestCase):
    def test_controls_accessible_via_ui_core(self):
        from engine.editor.ui_core import (
            Anchor, Button, Container, Control, ControlEvent,
            ControlEventKind, FocusManager, HBoxContainer, Label,
            LayoutDirection, Margin, Panel, ScrollContainer,
            Size, TextureRect, VBoxContainer,
        )

        self.assertIsNotNone(Size(10.0, 10.0))
        self.assertIsNotNone(Button(name="b"))
        self.assertIsNotNone(Label(name="l"))
        self.assertIsNotNone(Panel(name="p"))
        self.assertIsNotNone(Container(name="c"))
        self.assertIsNotNone(HBoxContainer(name="h"))
        self.assertIsNotNone(VBoxContainer(name="v"))
        self.assertIsNotNone(ScrollContainer(name="s"))
        self.assertIsNotNone(TextureRect(name="t"))
        self.assertIsNotNone(FocusManager())


if __name__ == "__main__":
    unittest.main()
