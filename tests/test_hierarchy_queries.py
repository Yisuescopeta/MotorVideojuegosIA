import unittest

from engine.editor.hierarchy_queries import HierarchyQueries
from engine.scenes.refs import OpenDocumentId, OpenSceneRef
from engine.scenes.scene import Scene


class HierarchyQueriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = Scene(
            name="Hierarchy",
            data={
                "schema_version": 3,
                "name": "Hierarchy",
                "entities": [
                    {"id": "root-id", "name": "Root", "components": {"Transform": {}}},
                    {
                        "id": "child-id",
                        "name": "Child",
                        "parent_id": "root-id",
                        "parent": "Root",
                        "components": {"Sprite": {}},
                    },
                    {"id": "other-id", "name": "Other", "components": {"Camera2D": {}}},
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.scene_ref = OpenSceneRef(OpenDocumentId.new())

    def test_snapshot_is_id_first_and_preserves_hierarchy(self) -> None:
        snapshot = HierarchyQueries(self.scene, self.scene_ref).snapshot()

        self.assertEqual([ref.entity_id for ref in snapshot.roots], ["other-id", "root-id"])
        child = snapshot.by_id["child-id"]
        self.assertEqual(child.parent.entity_id, "root-id")
        self.assertEqual(child.depth, 1)
        self.assertEqual(child.component_types, ("Sprite",))
        self.assertEqual(child.ref.scene, self.scene_ref)

    def test_search_marks_rows_without_mutating_the_scene(self) -> None:
        before = self.scene.to_dict()
        snapshot = HierarchyQueries(self.scene, self.scene_ref).snapshot("sprite")

        self.assertFalse(snapshot.by_id["root-id"].is_match)
        self.assertTrue(snapshot.by_id["child-id"].is_match)
        self.assertEqual(self.scene.to_dict(), before)


if __name__ == "__main__":
    unittest.main()
