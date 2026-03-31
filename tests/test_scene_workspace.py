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
                    "flow_key": "",
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

    def test_copy_paste_subtree_preserves_internal_parent_and_renames_conflicts(self) -> None:
        self.scene_manager.create_new_scene("Source")
        self.assertTrue(self.scene_manager.create_entity("Root", components={"Transform": self._transform_payload()}))
        self.assertTrue(self.scene_manager.create_child_entity("Root", "Child", {"Transform": self._transform_payload()}))
        source_key = self.scene_manager.active_scene_key

        self.assertTrue(self.scene_manager.copy_entity_subtree("Root"))

        self.scene_manager.create_new_scene("Target", activate=False)
        target_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Target")
        self.assertIsNotNone(self.scene_manager.activate_scene(target_key))
        self.assertTrue(self.scene_manager.create_entity("Root", components={"Transform": self._transform_payload()}))

        pasted = self.scene_manager.paste_copied_entities()

        self.assertTrue(pasted)
        target_world = self.scene_manager.get_edit_world()
        pasted_root = target_world.get_entity_by_name("Root_copy")
        pasted_child = target_world.get_entity_by_name("Child")
        self.assertIsNotNone(pasted_root)
        self.assertIsNotNone(pasted_child)
        self.assertEqual(pasted_child.parent_name, "Root_copy")

        self.assertIsNotNone(self.scene_manager.activate_scene(source_key))
        source_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(source_world.get_entity_by_name("Root"))
        self.assertIsNotNone(source_world.get_entity_by_name("Child"))
        self.assertIsNone(source_world.get_entity_by_name("Root_copy"))

    def test_workspace_activate_and_close_preserves_expected_active_scene(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        scene_a_key = self.scene_manager.active_scene_key
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")

        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)
        self.assertTrue(self.scene_manager.close_scene(scene_b_key, discard_changes=True))
        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)

        self.scene_manager.create_new_scene("Scene C", activate=False)
        scene_c_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene C")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_c_key))
        self.assertEqual(self.scene_manager.active_scene_key, scene_c_key)

        self.assertTrue(self.scene_manager.close_scene(scene_c_key, discard_changes=True))
        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)

    def test_activate_scene_is_blocked_while_active_scene_is_playing(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        scene_a_key = self.scene_manager.active_scene_key
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertIsNone(self.scene_manager.activate_scene(scene_b_key))
        self.assertEqual(self.scene_manager.active_scene_key, scene_a_key)
        self.assertTrue(self.scene_manager.is_playing)

    def test_workspace_state_tracks_active_scene_and_view_state(self) -> None:
        self.scene_manager.create_new_scene("Scene A")
        scene_a_key = self.scene_manager.active_scene_key
        self.scene_manager.set_scene_view_state(
            scene_a_key,
            {
                "selected_entity": "Hero",
                "camera_target": {"x": 12.0, "y": 24.0},
                "camera_zoom": 1.75,
            },
        )
        self.scene_manager.create_new_scene("Scene B", activate=False)
        scene_b_key = next(scene["key"] for scene in self.scene_manager.list_open_scenes() if scene["name"] == "Scene B")
        self.assertIsNotNone(self.scene_manager.activate_scene(scene_b_key))

        workspace_state = self.scene_manager.get_workspace_state()

        self.assertEqual(workspace_state["active_scene"], scene_b_key)
        self.assertEqual(workspace_state["open_scenes"], [scene_a_key, scene_b_key])
        self.assertEqual(
            workspace_state["scene_view_states"][scene_a_key],
            {
                "selected_entity": "Hero",
                "camera_target": {"x": 12.0, "y": 24.0},
                "camera_zoom": 1.75,
            },
        )

    def test_edit_play_stop_cycle_restores_edit_world_without_dirtying_scene(self) -> None:
        self.scene_manager.load_scene(
            {
                "name": "PlayProbe",
                "entities": [
                    {
                        "name": "Player",
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
        edit_world = self.scene_manager.get_edit_world()
        self.scene_manager.set_selected_entity("Player")

        runtime_world = self.scene_manager.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertTrue(self.scene_manager.is_playing)
        self.assertFalse(self.scene_manager.is_dirty)
        runtime_world.selected_entity_name = "Player"

        restored_world = self.scene_manager.exit_play()

        self.assertIs(restored_world, self.scene_manager.get_edit_world())
        self.assertIsNot(restored_world, runtime_world)
        self.assertIsNot(restored_world, edit_world)
        self.assertFalse(self.scene_manager.is_playing)
        self.assertFalse(self.scene_manager.is_dirty)
        self.assertEqual(restored_world.selected_entity_name, "Player")

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
