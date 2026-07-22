import unittest
import warnings

from engine.scenes.scene import Scene


def _scene() -> Scene:
    return Scene.from_dict(
        {
            "schema_version": 2,
            "name": "Views",
            "entities": [
                {
                    "id": "actor-id",
                    "name": "Actor",
                    "components": {"Transform": {"x": 1.0}},
                }
            ],
            "rules": [{"when": {"event": "start"}, "do": []}],
            "feature_metadata": {"nested": {"items": [1]}},
        }
    )


class SceneViewTests(unittest.TestCase):
    def test_entity_and_metadata_views_are_deeply_immutable(self) -> None:
        scene = _scene()

        entity = scene.find_entity_view("actor-id")
        self.assertIsNotNone(entity)
        assert entity is not None
        with self.assertRaises(TypeError):
            entity["components"]["Transform"]["x"] = 9.0

        metadata = scene.feature_metadata_view()
        with self.assertRaises(TypeError):
            metadata["nested"]["items"] = ()
        with self.assertRaises(AttributeError):
            metadata["nested"]["items"].append(2)

    def test_snapshot_and_collection_views_are_detached(self) -> None:
        scene = _scene()

        snapshot = scene.snapshot()
        entity_views = scene.list_entity_views()
        rules = scene.rules_view()

        self.assertEqual(snapshot.name, "Views")
        self.assertEqual(snapshot.revision, 0)
        self.assertEqual(entity_views[0].id, "actor-id")
        self.assertEqual(entity_views[0].get("name"), "Actor")
        self.assertEqual(rules[0].get("when"), {"event": "start"})

        scene.update_component("Actor", "Transform", "x", 2.0)
        self.assertEqual(snapshot.to_dict()["entities"][0]["components"]["Transform"]["x"], 1.0)
        self.assertEqual(scene.revision, 1)

    def test_legacy_getters_return_deep_copies_and_warn(self) -> None:
        scene = _scene()

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", DeprecationWarning)
            entity = scene.find_entity("Actor")
            entity["components"]["Transform"]["x"] = 20.0
            metadata = scene.feature_metadata
            metadata["nested"]["items"].append(2)
            entities = scene.entities_data
            rules = scene.rules_data

        self.assertGreaterEqual(len(captured), 4)
        self.assertEqual(scene.find_entity_view("actor-id").get("components")["Transform"]["x"], 1.0)
        self.assertEqual(scene.feature_metadata_view().get("nested")["items"], (1,))
        self.assertEqual(len(entities), 1)
        self.assertEqual(len(rules), 1)


if __name__ == "__main__":
    unittest.main()
