from __future__ import annotations

import json
import unittest
from pathlib import Path

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.edit_sync import SceneEditSyncCoordinator
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _scene_payload() -> dict[str, object]:
    return {
        "name": "IntegrityProbe",
        "schema_version": 2,
        "entities": [
            {
                "id": "actor-id",
                "name": "Actor",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {"Transform": {"x": 1.0, "y": 2.0}},
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


class SceneProjectionIntegrityBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        projection = SceneProjectionService(create_default_registry())
        self.workspace = SceneWorkspace(projection=projection, flow_policy=SceneFlowPolicy())
        self.coordinator = SceneEditSyncCoordinator(self.workspace, projection)
        self.workspace.load_scene(_scene_payload())
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None and self.entry.edit_world is not None

    def test_direct_component_mutation_is_not_observed_by_world_version(self) -> None:
        assert self.entry.edit_world is not None
        actor = self.entry.edit_world.get_entity_by_name("Actor")
        assert actor is not None
        transform = actor.get_component(Transform)
        assert transform is not None
        before_version = self.entry.edit_world.version

        transform.x = 72.0

        self.assertEqual(self.entry.edit_world.version, before_version)
        self.assertEqual(transform.x, 72.0)

    def test_protected_save_should_reject_unregistered_component_mutation(self) -> None:
        assert self.entry.edit_world is not None
        actor = self.entry.edit_world.get_entity_by_name("Actor")
        assert actor is not None
        transform = actor.get_component(Transform)
        assert transform is not None
        transform.x = 72.0

        # Expected red baseline. G0.5 must make this return False without
        # importing the mutated EditWorld into Scene.
        self.assertFalse(
            self.coordinator.prepare_for_save(
                self.entry,
                failure_context="g0_direct_component_mutation",
            )
        )

    def test_selection_change_is_not_a_persistent_mutation(self) -> None:
        assert self.entry.edit_world is not None
        self.entry.edit_world.selected_entity_name = "Actor"

        self.assertTrue(
            self.coordinator.prepare_for_save(
                self.entry,
                failure_context="g0_selection_only",
            )
        )
        self.assertEqual(self.entry.scene.find_entity("Actor")["components"]["Transform"]["x"], 1.0)

    def test_mutation_corpus_covers_required_g0_families(self) -> None:
        corpus_path = Path(__file__).resolve().parents[1] / "artifacts" / "refactor_editor_migration_v4" / "g0-02-mutation-corpus.json"
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        cases = corpus["cases"]
        families = {case["family"] for case in cases}

        self.assertEqual(
            families,
            {"component", "nested_payload", "structure", "metadata", "selection", "preview"},
        )
        self.assertEqual(len(cases), 8)


if __name__ == "__main__":
    unittest.main()
