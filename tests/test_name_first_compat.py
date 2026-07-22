import unittest

from engine.scenes.compat.name_first import NameFirstResolutionMetrics, NameFirstSceneFacade
from engine.scenes.refs import OpenDocumentId, OpenSceneRef
from engine.scenes.result import Err, Ok
from engine.scenes.scene import Scene


class NameFirstCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = Scene(
            name="Compat",
            data={
                "schema_version": 3,
                "name": "Compat",
                "entities": [
                    {"id": "hero-id", "name": "Hero", "components": {}},
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.metrics = NameFirstResolutionMetrics()
        self.facade = NameFirstSceneFacade(
            self.scene,
            OpenSceneRef(OpenDocumentId.new()),
            metrics=self.metrics,
        )

    def test_resolves_once_to_entity_ref_and_records_metrics(self) -> None:
        result = self.facade.resolve_entity("Hero")

        self.assertIsInstance(result, Ok)
        self.assertEqual(result.value.entity_id, "hero-id")
        self.assertEqual(self.metrics.snapshot(), {"calls": 1, "resolved": 1, "not_found": 0, "ambiguous": 0})

    def test_unresolved_name_returns_typed_error(self) -> None:
        result = self.facade.resolve_entity("Missing")

        self.assertIsInstance(result, Err)
        self.assertEqual(result.error.code.value, "NOT_FOUND")
        self.assertEqual(self.metrics.not_found, 1)

    def test_empty_name_is_not_sent_to_scene_lookup(self) -> None:
        result = self.facade.resolve_entity(" ")

        self.assertIsInstance(result, Err)
        self.assertEqual(self.metrics.snapshot(), {"calls": 1, "resolved": 0, "not_found": 1, "ambiguous": 0})


if __name__ == "__main__":
    unittest.main()
