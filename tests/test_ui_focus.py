"""
tests/test_ui_focus.py - Tests for UIFocusSystem.
"""

from __future__ import annotations

import unittest

from engine.components.recttransform import RectTransform
from engine.events.event_bus import EventBus
from engine.systems.ui_focus_system import UIFocusSystem


class TestUIFocusSystem(unittest.TestCase):
    def test_create_focus_system(self):
        """Crear UIFocusSystem sin event_bus."""
        system = UIFocusSystem()
        self.assertIsNotNone(system)
        self.assertIsNone(system.get_focused_entity())

    def test_set_focus(self):
        """set_focus asigna entity_id."""
        system = UIFocusSystem()
        system.set_focus(42)
        self.assertEqual(system.get_focused_entity(), 42)

    def test_get_focus(self):
        """get_focused_entity retorna ID correcto."""
        system = UIFocusSystem()
        self.assertIsNone(system.get_focused_entity())
        system.set_focus(7)
        self.assertEqual(system.get_focused_entity(), 7)

    def test_clear_focus(self):
        """clear_focus pone None."""
        system = UIFocusSystem()
        system.set_focus(100)
        system.clear_focus()
        self.assertIsNone(system.get_focused_entity())

    def test_focus_entered_event(self):
        """set_focus emite focus_entered."""
        bus = EventBus()
        system = UIFocusSystem(event_bus=bus)

        received: list[dict] = []

        def handler(event):
            received.append(event.data)

        bus.subscribe("focus_entered", handler)
        system.set_focus(1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["entity_id"], 1)

    def test_focus_exited_event(self):
        """Cambiar foco emite focus_exited en el viejo."""
        bus = EventBus()
        system = UIFocusSystem(event_bus=bus)

        received: list[dict] = []

        def handler(event):
            received.append({"name": event.name, "data": event.data})

        bus.subscribe("focus_exited", handler)
        bus.subscribe("focus_entered", handler)
        system.set_focus(10)
        system.set_focus(20)

        exited_events = [e for e in received if e["name"] == "focus_exited"]
        entered_events = [e for e in received if e["name"] == "focus_entered"]

        self.assertEqual(len(exited_events), 1)
        self.assertEqual(exited_events[0]["data"]["entity_id"], 10)
        self.assertEqual(len(entered_events), 2)
        self.assertEqual(entered_events[-1]["data"]["entity_id"], 20)

    def test_same_focus_no_event(self):
        """Mismo foco no emite duplicados."""
        bus = EventBus()
        system = UIFocusSystem(event_bus=bus)

        count = 0

        def handler(_event):
            nonlocal count
            count += 1

        bus.subscribe("focus_entered", handler)
        bus.subscribe("focus_exited", handler)
        system.set_focus(5)
        self.assertEqual(count, 1)
        system.set_focus(5)
        self.assertEqual(count, 1)

    def test_recttransform_focusable(self):
        """RectTransform con focusable=True."""
        rt = RectTransform(focusable=True, focus_mode="all", mouse_filter="stop")
        self.assertTrue(rt.focusable)
        self.assertEqual(rt.focus_mode, "all")
        self.assertEqual(rt.mouse_filter, "stop")

        data = rt.to_dict()
        self.assertTrue(data["focusable"])
        self.assertEqual(data["focus_mode"], "all")
        self.assertEqual(data["mouse_filter"], "stop")

        rt2 = RectTransform.from_dict(data)
        self.assertTrue(rt2.focusable)
        self.assertEqual(rt2.focus_mode, "all")
        self.assertEqual(rt2.mouse_filter, "stop")


if __name__ == "__main__":
    unittest.main()
