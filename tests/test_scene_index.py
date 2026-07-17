import unittest

from engine.scenes.scene import Scene


class SceneIndexTests(unittest.TestCase):
    def _scene(self) -> Scene:
        return Scene(
            data={
                "name": "IndexProbe",
                "entities": [
                    {"name": "Hero", "components": {}},
                    {"name": "Enemy", "components": {}},
                    {"name": "Pickup", "components": {}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_find_entity_uses_rebuilt_index_from_loaded_data(self) -> None:
        scene = self._scene()

        self.assertEqual(scene.find_entity("Enemy")["name"], "Enemy")
        self.assertIsNone(scene.find_entity("Missing"))

    def test_find_entity_by_id_uses_rebuilt_index_from_loaded_data(self) -> None:
        scene = self._scene()
        enemy_id = scene.find_entity("Enemy")["id"]

        self.assertEqual(scene.find_entity_by_id(enemy_id)["name"], "Enemy")
        self.assertIsNone(scene.find_entity_by_id("missing"))

    def test_rename_updates_entity_index(self) -> None:
        scene = self._scene()
        hero = scene.find_entity("Hero")
        hero_id = hero["id"]

        self.assertTrue(scene.update_entity_property("Hero", "name", "Player"))

        self.assertIsNone(scene.find_entity("Hero"))
        self.assertIs(scene.find_entity("Player"), hero)
        self.assertEqual(scene.find_entity("Player")["id"], hero_id)
        self.assertIs(scene.find_entity_by_id(hero_id), hero)

    def test_internal_id_apis_edit_same_entity_as_name_apis(self) -> None:
        scene = self._scene()
        hero_id = scene.find_entity("Hero")["id"]

        self.assertTrue(scene.add_component_by_id(hero_id, "Marker2D", {"enabled": True, "marker_name": "hero"}))
        self.assertTrue(scene.update_component_by_id(hero_id, "Marker2D", "marker_name", "player"))
        self.assertEqual(scene.find_entity("Hero")["components"]["Marker2D"]["marker_name"], "player")
        self.assertTrue(scene.replace_component_data_by_id(hero_id, "Marker2D", {"enabled": True, "marker_name": "root"}))
        self.assertEqual(scene.find_entity("Hero")["components"]["Marker2D"]["marker_name"], "root")
        self.assertTrue(scene.remove_component_by_id(hero_id, "Marker2D"))
        self.assertNotIn("Marker2D", scene.find_entity("Hero")["components"])

    def test_rename_updates_known_name_references_without_changing_id(self) -> None:
        scene = Scene(
            data={
                "name": "RenameRefs",
                "entities": [
                    {"name": "Parent", "components": {}},
                    {"name": "Child", "parent": "Parent", "components": {}},
                    {
                        "name": "Link",
                        "components": {"SceneLink": {"target_entity_name": "Parent", "target_path": "levels/a.json"}},
                    },
                ],
                "rules": [{"event": "start", "do": [{"action": "destroy_entity", "entity": "Parent"}]}],
                "feature_metadata": {
                    "signals": {
                        "connections": [
                            {
                                "id": "sig_1",
                                "source": {"id": "source", "signal": "done"},
                                "target": {"kind": "entity", "name": "Parent", "component": "ScriptBehaviour"},
                                "callable": {"method": "on_done"},
                            }
                        ]
                    }
                },
            }
        )
        parent_id = scene.find_entity("Parent")["id"]

        self.assertTrue(scene.update_entity_property("Parent", "name", "ParentRenamed"))

        self.assertEqual(scene.find_entity("ParentRenamed")["id"], parent_id)
        self.assertEqual(scene.find_entity("Child")["parent"], "ParentRenamed")
        self.assertEqual(
            scene.find_entity("Link")["components"]["SceneLink"]["target_entity_name"],
            "ParentRenamed",
        )
        self.assertEqual(scene.rules_data[0]["do"][0]["entity"], "ParentRenamed")
        target = scene.feature_metadata["signals"]["connections"][0]["target"]
        self.assertEqual(target["name"], "ParentRenamed")

    def test_remove_entity_updates_entity_index(self) -> None:
        scene = self._scene()

        self.assertTrue(scene.remove_entity("Hero"))

        self.assertIsNone(scene.find_entity("Hero"))
        self.assertEqual([entity["name"] for entity in scene.entities_data], ["Enemy", "Pickup"])

    def test_remove_entity_subtree_is_transitive_ordered_and_reindexes_all_keys(self) -> None:
        scene = Scene(
            data={
                "name": "SubtreeIndex",
                "entities": [
                    {"id": "leaf-id", "name": "Leaf", "parent": "Branch", "components": {}},
                    {"id": "keep-a-id", "name": "KeepA", "components": {}},
                    {
                        "id": "root-id",
                        "name": "Root",
                        "components": {"SceneEntryPoint": {"entry_id": "root-entry"}},
                    },
                    {"id": "keep-b-id", "name": "KeepB", "components": {}},
                    {
                        "id": "branch-id",
                        "name": "Branch",
                        "parent": "Root",
                        "components": {"SceneEntryPoint": {"entry_id": "branch-entry"}},
                    },
                    {"id": "deep-id", "name": "Deep", "parent": "Leaf", "components": {}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        self.assertTrue(scene.remove_entity_subtree("Root"))

        self.assertEqual(
            [entity["name"] for entity in scene.entities_data],
            ["KeepA", "KeepB"],
        )
        for name in ("Root", "Branch", "Leaf", "Deep"):
            self.assertIsNone(scene.find_entity(name))
        for entity_id in ("root-id", "branch-id", "leaf-id", "deep-id"):
            self.assertIsNone(scene.find_entity_by_id(entity_id))
        self.assertTrue(
            scene.add_entity(
                {
                    "name": "ReplacementEntry",
                    "components": {"SceneEntryPoint": {"entry_id": "branch-entry"}},
                }
            )
        )

    def test_remove_entity_subtree_missing_is_exact_noop(self) -> None:
        scene = self._scene()
        before = scene.to_dict()

        self.assertFalse(scene.remove_entity_subtree("Missing"))

        self.assertEqual(scene.to_dict(), before)

    def test_prefab_empty_override_preservation_only_applies_to_explicit_empty_map(self) -> None:
        scene = Scene(
            data={
                "name": "OverrideShapes",
                "entities": [
                    {
                        "name": "ExplicitEmpty",
                        "prefab_instance": {
                            "prefab_path": "empty.prefab",
                            "root_name": "Root",
                            "overrides": {},
                        },
                        "components": {},
                    },
                    {
                        "name": "CanonicalEmpty",
                        "prefab_instance": {
                            "prefab_path": "canonical.prefab",
                            "root_name": "Root",
                            "overrides": {"operations": []},
                        },
                        "components": {},
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        self.assertEqual(
            scene.find_entity("ExplicitEmpty")["prefab_instance"]["overrides"],
            {},
        )
        self.assertEqual(
            scene.find_entity("CanonicalEmpty")["prefab_instance"]["overrides"],
            {"operations": []},
        )

    def test_add_entity_rejects_duplicate_name_using_index(self) -> None:
        scene = self._scene()

        added = scene.add_entity({"name": "Hero", "components": {}})

        self.assertFalse(added)
        self.assertEqual(len(scene.entities_data), 3)

    def test_update_component_properties_preserves_existing_payload(self) -> None:
        scene = Scene(
            data={
                "name": "BatchUpdate",
                "entities": [
                    {
                        "name": "Actor",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 1.0,
                                "y": 2.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                                "editor_data": {"locked": True},
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        component = scene.find_entity("Actor")["components"]["Transform"]

        updated = scene.update_component_properties(
            "Actor",
            "Transform",
            {"x": 9.0, "rotation": 45.0},
        )

        self.assertTrue(updated)
        stored = scene.find_entity("Actor")["components"]["Transform"]
        self.assertIs(stored, component)
        self.assertEqual(stored["x"], 9.0)
        self.assertEqual(stored["rotation"], 45.0)
        self.assertEqual(stored["y"], 2.0)
        self.assertEqual(stored["editor_data"], {"locked": True})
        self.assertFalse(scene.update_component_properties("Missing", "Transform", {"x": 1.0}))
        self.assertFalse(scene.update_component_properties("Actor", "Missing", {"x": 1.0}))

    def test_update_component_properties_reindexes_scene_entry_point(self) -> None:
        scene = Scene(
            data={
                "name": "EntryIndex",
                "entities": [
                    {
                        "name": "Gate",
                        "components": {
                            "SceneEntryPoint": {
                                "enabled": True,
                                "entry_id": "arrival",
                                "label": "Arrival",
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        self.assertTrue(
            scene.update_component_properties(
                "Gate",
                "SceneEntryPoint",
                {"entry_id": "north_gate", "label": "North Gate"},
            )
        )
        self.assertTrue(
            scene.add_entity(
                {
                    "name": "OldArrival",
                    "components": {"SceneEntryPoint": {"entry_id": "arrival"}},
                }
            )
        )
        self.assertFalse(
            scene.add_entity(
                {
                    "name": "DuplicateNorth",
                    "components": {"SceneEntryPoint": {"entry_id": "north_gate"}},
                }
            )
        )
        entry_point = scene.find_entity("Gate")["components"]["SceneEntryPoint"]
        self.assertTrue(entry_point["enabled"])
        self.assertEqual(entry_point["label"], "North Gate")

    def test_remove_feature_metadata_removes_only_requested_key(self) -> None:
        scene = Scene(
            data={
                "name": "FeatureMetadata",
                "entities": [],
                "rules": [],
                "feature_metadata": {
                    "scene_flow": {"next": "levels/next.json"},
                    "signals": {"connections": []},
                },
            }
        )

        self.assertTrue(scene.remove_feature_metadata("scene_flow"))
        self.assertNotIn("scene_flow", scene.feature_metadata)
        self.assertEqual(
            scene.feature_metadata["signals"],
            {"connections": []},
        )
        self.assertFalse(scene.remove_feature_metadata("scene_flow"))


if __name__ == "__main__":
    unittest.main()
