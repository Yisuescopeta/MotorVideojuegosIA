import tempfile
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class SceneManagerContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {
                "name": "Contracts Probe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 10.0,
                                "y": 20.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_runtime_port_is_memoized_and_preserves_play_stop_semantics(self) -> None:
        port = self.manager.runtime_port

        self.assertIs(port, self.manager.runtime_port)
        self.assertIs(port.current_scene, self.manager.current_scene)
        self.assertIs(port.active_world, self.manager.active_world)

        runtime_world = port.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertTrue(self.manager.is_playing)
        self.assertIs(runtime_world, self.manager.active_world)

        edit_world = port.exit_play()

        self.assertIsNotNone(edit_world)
        self.assertFalse(self.manager.is_playing)
        self.assertIs(edit_world, self.manager.active_world)

    def test_authoring_and_workspace_ports_delegate_serializable_state(self) -> None:
        authoring = self.manager.authoring_port
        workspace = self.manager.workspace_port

        self.assertIs(authoring, self.manager.authoring_port)
        self.assertIs(workspace, self.manager.workspace_port)
        self.assertTrue(
            authoring.create_entity(
                "Enemy",
                components={
                    "Transform": {
                        "enabled": True,
                        "x": 8.0,
                        "y": 4.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            )
        )
        self.assertTrue(authoring.set_feature_metadata("phase_1", {"enabled": True}))
        self.assertTrue(workspace.set_scene_flow_target("next_scene", "levels/next_scene.json"))
        self.assertEqual(authoring.get_component_data("Enemy", "Transform")["x"], 8.0)
        enemy_data = self.manager.find_entity_data("Enemy")
        self.assertIsInstance(enemy_data.get("id"), str)
        self.assertTrue(enemy_data["id"])

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "contracts_probe.json"

            self.assertTrue(workspace.save_scene_to_file(scene_path.as_posix(), key=workspace.active_scene_key))

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))
            self.assertIsNotNone(reloaded.find_entity_data("Enemy"))
            self.assertEqual(reloaded.get_feature_metadata()["phase_1"], {"enabled": True})
            self.assertEqual(reloaded.get_scene_flow()["next_scene"], "levels/next_scene.json")

    def test_internal_id_authoring_wrappers_resolve_current_name(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]

        self.assertTrue(self.manager.update_entity_property_by_id(player_id, "tag", "Hero"))
        self.assertEqual(self.manager.find_entity_data("Player")["tag"], "Hero")
        self.assertTrue(
            self.manager.add_component_to_entity_by_id(
                player_id,
                "Marker2D",
                {"enabled": True, "marker_name": "player"},
            )
        )
        self.assertEqual(
            self.manager.find_entity_data_by_id(player_id)["components"]["Marker2D"]["marker_name"],
            "player",
        )
        self.assertTrue(self.manager.update_entity_property_by_id(player_id, "name", "RenamedPlayer"))
        self.assertIsNone(self.manager.find_entity_data("Player"))
        self.assertEqual(self.manager.find_entity_data_by_id(player_id)["name"], "RenamedPlayer")
        self.assertTrue(self.manager.remove_component_from_entity_by_id(player_id, "Marker2D"))
        self.assertNotIn("Marker2D", self.manager.find_entity_data_by_id(player_id)["components"])

    def test_selected_entity_rename_preserves_selection_by_id(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]

        self.assertTrue(self.manager.set_selected_entity("Player"))
        self.assertTrue(self.manager.update_entity_property("Player", "name", "Hero"))

        self.assertEqual(self.manager.resolve_entry(None).selected_entity_id, player_id)
        self.assertEqual(self.manager.resolve_entry(None).selected_entity_name, "Hero")
        self.assertEqual(self.manager.get_edit_world().selected_entity_name, "Hero")
        self.assertIsNone(self.manager.find_entity_data("Player"))
        self.assertEqual(self.manager.find_entity_data_by_id(player_id)["name"], "Hero")

    def test_selected_renamed_entity_survives_play_stop_rebuild(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]

        self.assertTrue(self.manager.set_selected_entity("Player"))
        self.assertTrue(self.manager.update_entity_property("Player", "name", "Hero"))

        runtime_world = self.manager.enter_play()
        self.assertIsNotNone(runtime_world)
        self.assertEqual(runtime_world.selected_entity_name, "Hero")

        edit_world = self.manager.exit_play()
        self.assertIsNotNone(edit_world)
        self.assertEqual(edit_world.selected_entity_name, "Hero")
        self.assertEqual(self.manager.resolve_entry(None).selected_entity_id, player_id)

    def test_reparent_renamed_entity_resolves_current_name_from_id(self) -> None:
        player_id = self.manager.find_entity_data("Player")["id"]
        self.assertTrue(self.manager.create_entity("Parent"))
        self.assertTrue(self.manager.update_entity_property_by_id(player_id, "name", "Hero"))

        self.assertTrue(self.manager.set_entity_parent("Hero", "Parent"))

        self.assertEqual(self.manager.find_entity_data_by_id(player_id)["parent"], "Parent")


if __name__ == "__main__":
    unittest.main()
