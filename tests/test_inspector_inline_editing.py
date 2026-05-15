from __future__ import annotations

import unittest

from engine.editor.ui.inspector import build_inspector_model_from_dict
from engine.editor.ui.inspector_render import InspectorPanel
from engine.editor.ui.property_widgets import PropertyKind


class TestColorEditing(unittest.TestCase):
    def setUp(self):
        self.panel = InspectorPanel()

    def test_begin_color_edit_sets_state(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {
                "Sprite": {"color": (255, 128, 64, 255)}
            }
        })
        self.panel.model = model
        self.panel.entity_name = "Test"

        result = self.panel._begin_color_edit("Sprite", "color")
        self.assertTrue(result)
        self.assertEqual(self.panel.editing_color_group, "Sprite")
        self.assertEqual(self.panel.editing_color_prop, "color")
        self.assertEqual(self.panel.editing_color_value, (255, 128, 64, 255))

    def test_begin_color_edit_invalid_prop_returns_false(self):
        result = self.panel._begin_color_edit("Nonexistent", "bogus")
        self.assertFalse(result)

    def test_cancel_color_edit_clears_state(self):
        self.panel.editing_color_group = "Sprite"
        self.panel.editing_color_prop = "color"
        self.panel._cancel_color_edit()
        self.assertEqual(self.panel.editing_color_group, "")
        self.assertEqual(self.panel.editing_color_prop, "")

    def test_color_shown_as_swatch_not_text(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Sprite": {"tint": (255, 0, 0, 255)}}
        })
        self.panel.model = model
        self.panel.entity_name = "Test"
        prop = model.find_property("Sprite", "tint")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.kind, PropertyKind.COLOR)


class TestVectorEditing(unittest.TestCase):
    def setUp(self):
        self.panel = InspectorPanel()

    def test_vector2_inferred_correctly(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Transform": {"position": (100.0, 200.0)}}
        })
        prop = model.find_property("Transform", "position")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.kind, PropertyKind.VECTOR2)
        self.assertEqual(prop.value, (100.0, 200.0))

    def test_vector3_inferred_correctly(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Transform": {"scale": (1.0, 1.0, 1.0)}}
        })
        prop = model.find_property("Transform", "scale")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.kind, PropertyKind.VECTOR3)

    def test_begin_vector_edit_sets_text_buffer(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Transform": {"position": (100.0, 200.0)}}
        })
        self.panel.model = model
        self.panel.entity_name = "Test"

        result = self.panel._begin_vector_edit("Transform", "position")
        self.assertTrue(result)
        self.assertIn("100", self.panel.text_buffer)

    def test_parse_vector2_text_value(self):
        result = self.panel._parse_text_value("3.5, 7.2", PropertyKind.VECTOR2)
        self.assertEqual(result, (3.5, 7.2))

    def test_parse_vector3_text_value(self):
        result = self.panel._parse_text_value("1, 2, 3", PropertyKind.VECTOR3)
        self.assertEqual(result, (1.0, 2.0, 3.0))

    def test_vector_in_begin_text_edit_accepted(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Transform": {"position": (5.0, 10.0)}}
        })
        self.panel.model = model
        result = self.panel.begin_text_edit("Transform", "position")
        self.assertTrue(result)


class TestNestedProperties(unittest.TestCase):
    def setUp(self):
        self.panel = InspectorPanel()

    def test_dict_inferred_correctly(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Config": {"settings": {"volume": 0.8, "muted": False}}}
        })
        prop = model.find_property("Config", "settings")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.kind, PropertyKind.DICT)

    def test_list_inferred_correctly(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Waypoints": {"points": [(0, 0), (10, 20), (30, 40)]}}
        })
        prop = model.find_property("Waypoints", "points")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.kind, PropertyKind.LIST)

    def test_toggle_expand_adds_and_removes_key(self):
        key = self.panel._widget_key("Config", "settings")
        self.assertNotIn(key, self.panel.expanded_keys)

        self.panel._toggle_expand("Config", "settings")
        self.assertIn(key, self.panel.expanded_keys)

        self.panel._toggle_expand("Config", "settings")
        self.assertNotIn(key, self.panel.expanded_keys)


class TestMouseClickHandling(unittest.TestCase):
    def setUp(self):
        self.panel = InspectorPanel()

    def test_handle_mouse_click_exists(self):
        self.assertTrue(hasattr(self.panel, 'handle_mouse_click'))
        self.assertTrue(callable(self.panel.handle_mouse_click))

    def test_handle_mouse_click_on_bool_toggles(self):
        model = build_inspector_model_from_dict({
            "name": "Test",
            "components": {"Sprite": {"visible": True}}
        })
        self.panel.model = model
        self.panel.entity_name = "Test"

        self.panel.render({"entities": {"Test": {"name": "Test", "components": {"Sprite": {"visible": True}}}}}, 0, 0, 300, 400)

        bool_rects = [wr for wr in self.panel.widget_rects if wr.kind == PropertyKind.BOOL]
        if bool_rects:
            wr = bool_rects[0]
            self.panel.handle_mouse_click(wr.x + 1, wr.y + 1)

    def test_handle_mouse_click_on_color(self):
        self.panel.editing_color_group = "Sprite"
        self.panel.editing_color_prop = "color"
        self.panel.editing_key = "Sprite:color"
        result = self.panel.handle_mouse_click(10, 10)
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
