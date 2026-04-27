import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
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


if __name__ == "__main__":
    unittest.main()
