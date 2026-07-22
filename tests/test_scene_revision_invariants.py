import unittest

from engine.scenes.scene import Scene


def _scene() -> Scene:
    return Scene(
        "Revision",
        {
            "name": "Revision",
            "entities": [
                {
                    "id": "parent-id",
                    "name": "Parent",
                    "components": {"Transform": {"x": 0.0}},
                },
                {
                    "id": "child-id",
                    "name": "Child",
                    "parent_id": None,
                    "components": {"Transform": {"x": 1.0}},
                },
            ],
            "rules": [],
            "feature_metadata": {},
        },
    )


class SceneRevisionInvariantTests(unittest.TestCase):
    def test_main_mutation_families_bump_once_and_noops_do_not_bump(self) -> None:
        scene = _scene()
        operations = (
            lambda: scene.update_component("Parent", "Transform", "x", 2.0),
            lambda: scene.update_component_properties("Parent", "Transform", {"x": 3.0}),
            lambda: scene.set_component_metadata("Parent", "Transform", {"origin": "test"}),
            lambda: scene.update_entity_property("Parent", "tag", "Player"),
            lambda: scene.set_entity_groups("Parent", ["actors"]),
            lambda: scene.rename_entity_by_id("parent-id", "Root"),
            lambda: scene.reparent_entity_by_id("child-id", "parent-id"),
            lambda: scene.add_component("Root", "SceneEntryPoint", {"entry_id": "spawn"}),
            lambda: scene.replace_component_data("Root", "SceneEntryPoint", {"entry_id": "start"}),
            lambda: scene.remove_component("Root", "SceneEntryPoint"),
            lambda: scene.set_feature_metadata("signals", {"connections": []}),
            lambda: scene.remove_feature_metadata("signals"),
            lambda: scene.add_entity({"id": "new-id", "name": "New", "components": {}}),
            lambda: scene.remove_entity_by_id("new-id"),
        )
        for operation in operations:
            before = scene.revision
            self.assertTrue(operation())
            self.assertEqual(scene.revision, before + 1)

        before = scene.revision
        self.assertFalse(scene.update_component("Root", "Transform", "x", 3.0))
        self.assertEqual(scene.revision, before)
        self.assertFalse(scene.set_component_metadata("Root", "Transform", {"origin": "test"}))
        self.assertEqual(scene.revision, before)
        scene.set_feature_metadata("signals", {})
        before = scene.revision
        self.assertFalse(scene.set_feature_metadata("signals", {}))
        self.assertEqual(scene.revision, before)
        self.assertFalse(scene.reparent_entity_by_id("child-id", "parent-id"))
        self.assertEqual(scene.revision, before)

    def test_failed_operations_leave_revision_unchanged(self) -> None:
        scene = _scene()
        before = scene.revision
        self.assertFalse(scene.rename_entity_by_id("missing", "Nope"))
        self.assertFalse(scene.reparent_entity_by_id("child-id", "missing"))
        self.assertFalse(scene.remove_component_by_id("missing", "Transform"))
        self.assertEqual(scene.revision, before)


if __name__ == "__main__":
    unittest.main()
