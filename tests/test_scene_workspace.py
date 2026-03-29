import tempfile
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class SceneWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene_manager = SceneManager(create_default_registry())

    def _transform_payload(self) -> dict:
        return {
            "enabled": True,
            "x": 0.0,
            "y": 0.0,
            "rotation": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }

    def test_scene_link_syncs_feature_metadata_and_invalid_badge(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "Links",
                "entities": [
                    {
                        "name": "Portal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        added = self.scene_manager.add_component_to_entity(
            "Portal",
            "SceneLink",
            {
                "enabled": True,
                "target_path": "levels/menu.json",
                "flow_key": "menu_scene",
                "preview_label": "Main Menu",
            },
        )

        self.assertTrue(added)
        self.assertEqual(self.scene_manager.get_scene_flow(), {"menu_scene": "levels/menu.json"})
        self.assertEqual(
            self.scene_manager.current_scene.feature_metadata["scene_flow"]["menu_scene"],
            "levels/menu.json",
        )
        self.assertFalse(self.scene_manager.list_open_scenes()[0]["has_invalid_links"])

        self.assertTrue(
            self.scene_manager.replace_component_data(
                "Portal",
                "SceneLink",
                {
                    "enabled": True,
                    "target_path": "",
                    "flow_key": "menu_scene",
                    "preview_label": "Broken",
                },
            )
        )
        self.assertTrue(self.scene_manager.list_open_scenes()[0]["has_invalid_links"])

    def test_component_metadata_persists_through_scene_and_world(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "Metadata",
                "entities": [
                    {
                        "name": "Actor",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        updated = self.scene_manager.set_component_metadata("Actor", "Transform", {"origin": "ai_custom"})

        self.assertTrue(updated)
        self.assertEqual(
            self.scene_manager.current_scene.find_entity("Actor")["component_metadata"]["Transform"]["origin"],
            "ai_custom",
        )

        world = self.scene_manager.get_edit_world()
        actor = world.get_entity_by_name("Actor")
        self.assertEqual(actor.get_component_metadata_by_name("Transform")["origin"], "ai_custom")

    def test_copy_paste_entities_between_open_scenes(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        self.assertTrue(
            self.scene_manager.create_entity(
                "Root",
                components={
                    "Transform": self._transform_payload(),
                    "SceneLink": {
                        "enabled": True,
                        "target_path": "levels/next.json",
                        "flow_key": "next_scene",
                        "preview_label": "Next",
                    },
                },
            )
        )
        self.assertTrue(self.scene_manager.create_child_entity("Root", "Child", {"Transform": self._transform_payload()}))
        scene_a_key = self.scene_manager.active_scene_key

        self.assertTrue(self.scene_manager.copy_entity_subtree("Root"))
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_b_key))

        pasted = self.scene_manager.paste_copied_entities()

        self.assertTrue(pasted)
        scene_b_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(scene_b_world.get_entity_by_name("Root"))
        self.assertIsNotNone(scene_b_world.get_entity_by_name("Child"))

        self.assertIsNotNone(self.scene_manager.activate_scene(scene_a_key))
        scene_a_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(scene_a_world.get_entity_by_name("Root"))
        self.assertIsNotNone(scene_a_world.get_entity_by_name("Child"))

    def test_save_scene_preserves_component_metadata(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "SaveMetadata",
                "entities": [
                    {
                        "name": "Actor",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {"Transform": self._transform_payload()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.assertTrue(self.scene_manager.set_component_metadata("Actor", "Transform", {"origin": "ai_custom"}))

        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "scene.json"
            saved = self.scene_manager.save_scene_to_file(target_path.as_posix())
            self.assertTrue(saved)
            raw = target_path.read_text(encoding="utf-8")

        self.assertIn('"component_metadata"', raw)
        self.assertIn('"ai_custom"', raw)


if __name__ == "__main__":
    unittest.main()
