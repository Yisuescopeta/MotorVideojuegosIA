import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.assets.prefab import PrefabManager
from engine.project.project_service import ProjectService


class AuthoringTransactionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.level_path = self.root / "levels" / "txn_scene.json"
        self.level_path.write_text(
            json.dumps({"name": "TxnScene", "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
            encoding="utf-8",
        )
        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level("levels/txn_scene.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_transaction_commit_groups_changes_and_supports_undo_redo(self) -> None:
        self.assertTrue(self.api.begin_transaction("create-camera-rig")["success"])
        self.assertTrue(self.api.apply_change({"kind": "create_entity", "entity": "Rig"})["success"])
        self.assertTrue(
            self.api.apply_change(
                {
                    "kind": "add_component",
                    "entity": "Rig",
                    "component": "Camera2D",
                    "data": {"enabled": True, "offset_x": 320.0, "offset_y": 180.0, "zoom": 1.0, "is_primary": True},
                }
            )["success"]
        )
        self.assertTrue(
            self.api.apply_change(
                {"kind": "set_entity_property", "entity": "Rig", "field": "tag", "value": "MainCamera"}
            )["success"]
        )
        committed = self.api.commit_transaction()
        self.assertTrue(committed["success"])
        self.assertEqual(len(committed["data"]["changes"]), 3)

        entity = self.api.get_entity("Rig")
        self.assertEqual(entity["tag"], "MainCamera")
        self.assertIn("Camera2D", entity["components"])

        self.assertTrue(self.api.undo()["success"])
        with self.assertRaises(Exception):
            self.api.get_entity("Rig")

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("Rig")
        self.assertEqual(entity["tag"], "MainCamera")

    def test_transaction_rollback_restores_previous_scene_state(self) -> None:
        self.assertTrue(self.api.create_entity("Actor")["success"])
        self.assertTrue(self.api.begin_transaction("rollback-edit")["success"])
        self.assertTrue(
            self.api.apply_change(
                {"kind": "edit_component", "entity": "Actor", "component": "Transform", "field": "x", "value": 90.0}
            )["success"]
        )
        self.assertTrue(self.api.rollback_transaction()["success"])
        actor = self.api.get_entity("Actor")
        self.assertEqual(actor["components"]["Transform"]["x"], 0.0)

    def test_transaction_rollback_restores_deleted_hierarchy(self) -> None:
        self.assertTrue(self.api.create_entity("Parent")["success"])
        self.assertTrue(self.api.create_child_entity("Parent", "Child")["success"])

        self.assertTrue(self.api.begin_transaction("rollback-delete-parent")["success"])
        self.assertTrue(self.api.apply_change({"kind": "delete_entity", "entity": "Parent"})["success"])
        with self.assertRaises(Exception):
            self.api.get_entity("Parent")

        self.assertTrue(self.api.rollback_transaction()["success"])
        parent = self.api.get_entity("Parent")
        child = self.api.get_entity("Child")
        self.assertEqual(parent["name"], "Parent")
        self.assertEqual(child["parent"], "Parent")

    def test_transaction_commit_reports_complete_change_list_and_serializable_state(self) -> None:
        self.assertTrue(self.api.create_entity("Rig")["success"])
        self.assertTrue(self.api.add_component("Rig", "Camera2D", {"enabled": True, "offset_x": 0.0, "offset_y": 0.0, "zoom": 1.0, "is_primary": True})["success"])

        self.assertTrue(self.api.begin_transaction("camera-rewire")["success"])
        self.assertTrue(
            self.api.apply_change(
                {"kind": "edit_component", "entity": "Rig", "component": "Camera2D", "field": "zoom", "value": 2.0}
            )["success"]
        )
        self.assertTrue(
            self.api.apply_change(
                {"kind": "set_entity_property", "entity": "Rig", "field": "tag", "value": "MainCamera"}
            )["success"]
        )

        committed = self.api.commit_transaction()

        self.assertTrue(committed["success"])
        self.assertEqual(
            committed["data"]["changes"],
            [
                {"kind": "edit_component", "entity": "Rig", "component": "Camera2D", "field": "zoom", "value": 2.0},
                {"kind": "set_entity_property", "entity": "Rig", "field": "tag", "value": "MainCamera"},
            ],
        )
        rig = self.api.scene_manager.current_scene.find_entity("Rig")
        self.assertEqual(rig["tag"], "MainCamera")
        self.assertEqual(rig["components"]["Camera2D"]["zoom"], 2.0)

    def test_history_outside_transaction_still_supports_undo_redo(self) -> None:
        self.assertTrue(self.api.create_entity("Probe")["success"])
        self.assertTrue(self.api.set_entity_tag("Probe", "Hero")["success"])

        entity = self.api.get_entity("Probe")
        self.assertEqual(entity["tag"], "Hero")

        self.assertTrue(self.api.undo()["success"])
        entity = self.api.get_entity("Probe")
        self.assertEqual(entity["tag"], "Untagged")

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("Probe")
        self.assertEqual(entity["tag"], "Hero")

    def test_prefab_patch_operations_apply_at_load_time(self) -> None:
        prefab_path = self.root / "prefabs" / "enemy.prefab"
        prefab_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "root_name": "Enemy",
                    "entities": [
                        {
                            "name": "Enemy",
                            "active": True,
                            "tag": "Enemy",
                            "layer": "Actors",
                            "components": {
                                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                                "Collider": {"enabled": True, "width": 16.0, "height": 16.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            },
                        },
                        {
                            "name": "Weapon",
                            "parent": "",
                            "active": True,
                            "tag": "Weapon",
                            "layer": "Actors",
                            "components": {
                                "Transform": {"enabled": True, "x": 4.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
                            },
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        result = self.api.instantiate_prefab(
            "prefabs/enemy.prefab",
            name="EnemyPatched",
            overrides={
                "operations": [
                    {"op": "set_field", "target": "", "component": "Transform", "field": "x", "value": 40.0},
                    {"op": "add_component", "target": "", "component": "RigidBody", "data": {"enabled": True, "gravity_scale": 1.0}},
                    {"op": "remove_component", "target": "", "component": "Collider"},
                    {"op": "set_entity_property", "target": "Weapon", "field": "tag", "value": "Blade"},
                ]
            },
        )
        self.assertTrue(result["success"])

        enemy = self.api.get_entity("EnemyPatched")
        weapon = self.api.get_entity("EnemyPatched/Weapon")
        self.assertEqual(enemy["components"]["Transform"]["x"], 40.0)
        self.assertIn("RigidBody", enemy["components"])
        self.assertNotIn("Collider", enemy["components"])
        self.assertEqual(weapon["tag"], "Blade")

    def test_snap_entities_to_grid_updates_transform_and_recttransform(self) -> None:
        self.assertTrue(self.api.create_entity("Crate")["success"])
        self.assertTrue(self.api.edit_component("Crate", "Transform", "x", 13.2)["success"])
        self.assertTrue(self.api.edit_component("Crate", "Transform", "y", 30.7)["success"])
        self.assertTrue(self.api.create_canvas(name="MenuCanvas")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "MenuCanvas",
                {"anchored_x": 19.0, "anchored_y": 47.0, "width": 160.0, "height": 48.0},
            )["success"]
        )

        result = self.api.snap_entities_to_grid(["Crate", "PlayButton"], step_x=16.0)

        self.assertTrue(result["success"])
        crate = self.api.get_entity("Crate")
        button = self.api.get_entity("PlayButton")
        self.assertEqual(crate["components"]["Transform"]["x"], 16.0)
        self.assertEqual(crate["components"]["Transform"]["y"], 32.0)
        self.assertEqual(button["components"]["RectTransform"]["anchored_x"], 16.0)
        self.assertEqual(button["components"]["RectTransform"]["anchored_y"], 48.0)
        self.assertEqual(len(result["data"]["entities"]), 2)

    def test_duplicate_entities_with_offset_preserves_hierarchy(self) -> None:
        self.assertTrue(self.api.create_entity("Platform")["success"])
        self.assertTrue(self.api.edit_component("Platform", "Transform", "x", 32.0)["success"])
        self.assertTrue(self.api.edit_component("Platform", "Transform", "y", 48.0)["success"])
        self.assertTrue(self.api.create_child_entity("Platform", "Decoration")["success"])
        self.assertTrue(self.api.edit_component("Decoration", "Transform", "x", 4.0)["success"])
        self.assertTrue(self.api.edit_component("Decoration", "Transform", "y", -2.0)["success"])

        result = self.api.duplicate_entities(["Platform"], offset_x=64.0, offset_y=16.0, include_children=True)

        self.assertTrue(result["success"])
        created_names = [item["entity"] for item in result["data"]["created"]]
        self.assertIn("Platform_copy1", created_names)
        self.assertIn("Decoration_copy1", created_names)
        original_child = self.api.get_entity("Decoration")
        platform_copy = self.api.get_entity("Platform_copy1")
        decoration_copy = self.api.get_entity("Decoration_copy1")
        self.assertEqual(platform_copy["components"]["Transform"]["x"], 96.0)
        self.assertEqual(platform_copy["components"]["Transform"]["y"], 64.0)
        self.assertEqual(decoration_copy["parent"], "Platform_copy1")
        self.assertEqual(decoration_copy["components"]["Transform"]["x"], original_child["components"]["Transform"]["x"])
        self.assertEqual(decoration_copy["components"]["Transform"]["y"], original_child["components"]["Transform"]["y"])

    def test_align_entities_supports_batch_alignment(self) -> None:
        self.assertTrue(self.api.create_entity("ActorA")["success"])
        self.assertTrue(self.api.create_entity("ActorB")["success"])
        self.assertTrue(self.api.create_entity("ActorC")["success"])
        self.assertTrue(self.api.edit_component("ActorA", "Transform", "y", 10.0)["success"])
        self.assertTrue(self.api.edit_component("ActorB", "Transform", "y", 30.0)["success"])
        self.assertTrue(self.api.edit_component("ActorC", "Transform", "y", 50.0)["success"])

        result = self.api.align_entities(["ActorA", "ActorB", "ActorC"], axis="y", mode="center")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.get_entity("ActorA")["components"]["Transform"]["y"], 30.0)
        self.assertEqual(self.api.get_entity("ActorB")["components"]["Transform"]["y"], 30.0)
        self.assertEqual(self.api.get_entity("ActorC")["components"]["Transform"]["y"], 30.0)

    def test_align_entities_fails_cleanly_when_entity_has_no_supported_transform(self) -> None:
        self.assertTrue(self.api.create_entity("ActorA")["success"])
        self.assertTrue(self.api.create_entity("ActorB")["success"])
        self.assertTrue(self.api.remove_component("ActorB", "Transform")["success"])
        self.assertTrue(self.api.edit_component("ActorA", "Transform", "x", 10.0)["success"])

        result = self.api.align_entities(["ActorA", "ActorB"], axis="x", mode="min")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "All entities must have a supported transform for alignment")
        self.assertEqual(self.api.get_entity("ActorA")["components"]["Transform"]["x"], 10.0)

    def test_stamp_prefab_and_entities_from_source_support_fast_spawn_workflows(self) -> None:
        prefab_path = self.root / "prefabs" / "coin.prefab"
        prefab_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "root_name": "Coin",
                    "entities": [
                        {
                            "name": "Coin",
                            "active": True,
                            "tag": "Pickup",
                            "layer": "Default",
                            "components": {
                                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
                            },
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.assertTrue(self.api.create_entity("Torch")["success"])
        self.assertTrue(self.api.edit_component("Torch", "Transform", "x", 8.0)["success"])
        self.assertTrue(self.api.edit_component("Torch", "Transform", "y", 12.0)["success"])

        prefab_result = self.api.stamp_prefab(
            "prefabs/coin.prefab",
            [
                {"name": "CoinA", "x": 32.0, "y": 64.0},
                {"name": "CoinB", "x": 48.0, "y": 64.0},
            ],
        )
        entity_result = self.api.stamp_entities_from_source(
            "Torch",
            [
                {"name": "TorchA", "x": 96.0, "y": 24.0},
                {"name": "TorchB", "x": 128.0, "y": 24.0},
            ],
        )

        self.assertTrue(prefab_result["success"])
        self.assertTrue(entity_result["success"])
        self.assertEqual(self.api.get_entity("CoinA")["components"]["Transform"]["x"], 32.0)
        self.assertEqual(self.api.get_entity("CoinB")["components"]["Transform"]["y"], 64.0)
        self.assertEqual(self.api.get_entity("TorchA")["components"]["Transform"]["x"], 96.0)
        self.assertEqual(self.api.get_entity("TorchB")["components"]["Transform"]["y"], 24.0)


if __name__ == "__main__":
    unittest.main()
