import unittest

from engine.core.game import Game
from engine.editor.ui.inspector_render import InspectorPanel


class FakeSceneManager:
    def __init__(self) -> None:
        self.calls = []

    def update_entity_property(self, entity_name, property_name, value):
        self.calls.append(("entity", entity_name, property_name, value))
        return True

    def apply_edit_to_world(self, entity_name, component_name, property_name, value):
        self.calls.append(("component", entity_name, component_name, property_name, value))
        return True


class FakeWorld:
    selected_entity_name = "Player"

    def __init__(self, entity):
        self.entity = entity

    def get_entity_by_name(self, name):
        return self.entity if name == "Player" else None


class FakeEntity:
    name = "Player"
    id = 1
    active = True
    tag = "Hero"
    layer = 2

    def iter_components(self):
        return [Transform(), FakeStats()]


class Transform:
    x = 1.0
    y = 2.0

    def to_dict(self):
        return {"x": self.x, "y": self.y}


class FakeStats:
    enabled = False
    name = "stats"
    hp = 10


class InspectorPanelTests(unittest.TestCase):
    def test_model_build_from_component_dict_world_like_object(self):
        panel = InspectorPanel()
        model = panel.build_model(FakeWorld(FakeEntity()))

        self.assertIsNotNone(model.find_group("Entity"))
        self.assertEqual(model.find_property("Transform", "x").value, 1.0)
        self.assertEqual(model.find_property("FakeStats", "hp").value, 10)

        dict_model = panel.build_model(
            {
                "selected_entity_name": "Enemy",
                "entities": {
                    "Enemy": {
                        "name": "Enemy",
                        "components": {"Stats": {"hp": 3, "enabled": True}},
                    }
                },
            },
            selection="Enemy",
        )
        self.assertEqual(dict_model.find_property("Stats", "hp").value, 3)

    def test_no_selection_empty_no_op(self):
        panel = InspectorPanel(FakeSceneManager())
        world = {"entities": {}}

        model = panel.build_model(world)

        self.assertEqual(model.groups, [])
        self.assertFalse(panel.commit_property("Entity", "active", False))

    def test_bool_commit_invokes_scene_manager(self):
        scene_manager = FakeSceneManager()
        panel = InspectorPanel(scene_manager)
        panel.build_model(FakeWorld(FakeEntity()))

        self.assertTrue(panel.toggle_bool("Entity", "active"))

        self.assertEqual(scene_manager.calls, [("entity", "Player", "active", False)])

    def test_text_edit_enter_commit_invokes_scene_manager(self):
        scene_manager = FakeSceneManager()
        panel = InspectorPanel(scene_manager)
        panel.build_model(FakeWorld(FakeEntity()))

        self.assertTrue(panel.begin_text_edit("FakeStats", "hp"))
        panel.set_text_buffer("not-a-number")

        self.assertFalse(panel.commit_text_edit())
        self.assertEqual(scene_manager.calls, [])
        self.assertEqual(panel.editing_key, "FakeStats:hp")

        panel.set_text_buffer("25")

        self.assertTrue(panel.commit_text_edit())
        self.assertEqual(scene_manager.calls, [("component", "Player", "FakeStats", "hp", 25)])

    def test_escape_cancels(self):
        panel = InspectorPanel(FakeSceneManager())
        panel.build_model(FakeWorld(FakeEntity()))
        panel.begin_text_edit("Entity", "tag")

        panel.handle_key(256)

        self.assertIsNone(panel.editing_key)

    def test_no_scene_manager_does_not_mutate_object(self):
        entity = FakeEntity()
        panel = InspectorPanel()
        panel.build_model(FakeWorld(entity))

        self.assertFalse(panel.toggle_bool("Entity", "active"))
        self.assertTrue(entity.active)

    def test_render_layout_bounds_within_panel_no_crash(self):
        panel = InspectorPanel(FakeSceneManager())

        panel.render(FakeWorld(FakeEntity()), 10, 20, 240, 180)

        self.assertTrue(panel.widget_rects)
        for rect in panel.widget_rects:
            self.assertGreaterEqual(rect.x, 10)
            self.assertGreaterEqual(rect.y, 20)
            self.assertLessEqual(rect.x + rect.width, 250)
            self.assertLessEqual(rect.y + rect.height, 200)

    def test_game_has_setter_and_legacy_fallback_remains_possible(self):
        game = Game()
        panel = InspectorPanel()

        game.set_inspector_panel(panel)

        self.assertIs(game._inspector_panel, panel)
        game.set_inspector_panel(None)
        self.assertIsNone(game._inspector_panel)


if __name__ == "__main__":
    unittest.main()
