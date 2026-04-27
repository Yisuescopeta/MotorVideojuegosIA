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

    def test_add_entity_rejects_duplicate_name_using_index(self) -> None:
        scene = self._scene()

        added = scene.add_entity({"name": "Hero", "components": {}})

        self.assertFalse(added)
        self.assertEqual(len(scene.entities_data), 3)


if __name__ == "__main__":
    unittest.main()
