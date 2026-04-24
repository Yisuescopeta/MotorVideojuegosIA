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

    def test_rename_updates_entity_index(self) -> None:
        scene = self._scene()
        hero = scene.find_entity("Hero")

        self.assertTrue(scene.update_entity_property("Hero", "name", "Player"))

        self.assertIsNone(scene.find_entity("Hero"))
        self.assertIs(scene.find_entity("Player"), hero)

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
