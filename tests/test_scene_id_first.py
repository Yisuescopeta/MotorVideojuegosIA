import unittest

from engine.scenes.scene import Scene


class SceneIdFirstMutationTests(unittest.TestCase):
    def _scene(self) -> Scene:
        return Scene.from_dict(
            {
                "schema_version": 3,
                "name": "IdFirst",
                "entities": [
                    {"id": "root-id", "name": "Root", "components": {}},
                    {
                        "id": "child-id",
                        "name": "Child",
                        "parent_id": "root-id",
                        "parent": "Root",
                        "components": {},
                    },
                    {"id": "other-id", "name": "Other", "components": {}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_rename_and_reparent_by_id_preserve_identity(self) -> None:
        scene = self._scene()

        self.assertTrue(scene.rename_entity_by_id("root-id", "RenamedRoot"))
        self.assertTrue(scene.reparent_entity_by_id("child-id", "other-id"))

        self.assertEqual(scene.find_entity_by_id("root-id")["name"], "RenamedRoot")
        child = scene.find_entity_by_id("child-id")
        self.assertEqual(child["id"], "child-id")
        self.assertEqual(child["parent_id"], "other-id")
        self.assertEqual(child["parent"], "Other")

    def test_id_first_parent_validation_is_atomic(self) -> None:
        scene = self._scene()
        before = scene.to_dict()

        self.assertFalse(scene.reparent_entity_by_id("child-id", "missing-id"))
        self.assertFalse(scene.reparent_entity_by_id("root-id", "child-id"))

        self.assertEqual(scene.to_dict(), before)

    def test_delete_and_property_update_by_id_do_not_resolve_name(self) -> None:
        scene = self._scene()

        self.assertTrue(scene.update_entity_property_by_id("child-id", "name", "RenamedChild"))
        self.assertTrue(scene.update_entity_property_by_id("child-id", "parent_id", None))
        self.assertTrue(scene.remove_entity_by_id("child-id"))

        self.assertIsNone(scene.find_entity_by_id("child-id"))
        self.assertIsNotNone(scene.find_entity_by_id("root-id"))
        self.assertEqual(scene.find_entity_by_id("root-id")["name"], "Root")


if __name__ == "__main__":
    unittest.main()
