import unittest

from engine.editor.ui.inspector import build_inspector_model_from_dict, infer_property_kind
from engine.editor.ui.property_widgets import PropertyKind


class EditorUIInspectorTests(unittest.TestCase):
    def test_infer_property_kind_all_supported_values(self) -> None:
        cases = [
            (True, PropertyKind.BOOL),
            (7, PropertyKind.INT),
            (1.5, PropertyKind.FLOAT),
            ("text", PropertyKind.STR),
            ((255, 128, 0, 255), PropertyKind.COLOR),
            ((1, 2), PropertyKind.VECTOR2),
            ((1, 2, 3), PropertyKind.VECTOR3),
            ({"nested": True}, PropertyKind.DICT),
            (["not", "numeric"], PropertyKind.LIST),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(infer_property_kind(value), expected)

    def test_infer_property_kind_bool_before_int_and_unsupported(self) -> None:
        self.assertIs(infer_property_kind(False), PropertyKind.BOOL)
        self.assertIsNone(infer_property_kind(object()))

    def test_build_inspector_model_groups_finders_and_removable(self) -> None:
        model = build_inspector_model_from_dict(
            {
                "name": "Player",
                "id": "player-1",
                "active": True,
                "tag": "Hero",
                "layer": 2,
                "ignored": object(),
                "components": {
                    "Transform": {"position": (1, 2), "rotation": 0.0, "skip": object()},
                    "Sprite": {"color": [255, 255, 255, 255], "path": "hero.png"},
                    "Broken": object(),
                },
            }
        )

        entity = model.find_group("Entity")
        transform = model.find_group("Transform")
        sprite = model.find_group("Sprite")

        self.assertIsNotNone(entity)
        self.assertIsNotNone(transform)
        self.assertIsNotNone(sprite)
        self.assertFalse(entity.removable)
        self.assertFalse(transform.removable)
        self.assertTrue(sprite.removable)
        self.assertIs(model.find_property("Entity", "active").kind, PropertyKind.BOOL)
        self.assertIs(model.find_property("Transform", "position").kind, PropertyKind.VECTOR2)
        self.assertIs(model.find_property("Sprite", "color").kind, PropertyKind.COLOR)
        self.assertIsNone(model.find_property("Transform", "skip"))
        self.assertIsNone(model.find_group("Broken"))

    def test_build_inspector_model_supports_mixed_props(self) -> None:
        model = build_inspector_model_from_dict(
            {"components": {"Stats": {"hp": 10, "speed": 4.5, "flags": ["boss"], "meta": {"ai": "rush"}}}}
        )

        stats = model.find_group("Stats")

        self.assertEqual([prop.name for prop in stats.properties], ["hp", "speed", "flags", "meta"])
        self.assertIs(model.find_property("Stats", "hp").kind, PropertyKind.INT)
        self.assertIs(model.find_property("Stats", "speed").kind, PropertyKind.FLOAT)
        self.assertIs(model.find_property("Stats", "flags").kind, PropertyKind.LIST)
        self.assertIs(model.find_property("Stats", "meta").kind, PropertyKind.DICT)


if __name__ == "__main__":
    unittest.main()
