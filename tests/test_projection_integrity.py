from __future__ import annotations

import unittest

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.projection_integrity import (
    AuthoringProjectionFingerprintService,
    ProjectionFingerprintError,
)
from engine.scenes.scene import Scene
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _scene() -> Scene:
    return Scene(
        "FingerprintProbe",
        {
            "name": "FingerprintProbe",
            "schema_version": 2,
            "entities": [
                {
                    "id": "actor-id",
                    "name": "Actor",
                    "active": True,
                    "tag": "Player",
                    "layer": "Default",
                    "components": {"Transform": {"x": 1.0, "y": 2.0}},
                }
            ],
            "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "ok"}]}],
            "feature_metadata": {"nested": {"values": [1, 2, 3]}},
        },
    )


class ProjectionIntegrityFingerprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = _scene()
        registry = create_default_registry()
        self.service = AuthoringProjectionFingerprintService(
            lambda scene: scene.create_world(registry)
        )
        self.world = self.scene.create_world(registry)

    def test_fresh_projection_matches_scene(self) -> None:
        self.assertTrue(self.service.scene_matches_world(self.scene, self.world))
        evidence = self.service.build_evidence(self.scene, self.world, scene_revision=4)
        self.assertEqual(evidence.scene_revision, 4)
        self.assertEqual(evidence.projected_world_version, self.world.version)
        self.assertEqual(evidence.canonical_fingerprint, self.service.fingerprint_scene(self.scene))
        self.assertEqual(evidence.projection_schema_version, 1)

    def test_direct_component_assignment_changes_observed_fingerprint_without_touch(self) -> None:
        before = self.service.fingerprint_world(self.scene, self.world)
        actor = self.world.get_entity_by_name("Actor")
        assert actor is not None
        transform = actor.get_component(Transform)
        assert transform is not None
        world_version = self.world.version

        transform.x = 72.0

        self.assertEqual(self.world.version, world_version)
        self.assertNotEqual(before, self.service.fingerprint_world(self.scene, self.world))
        self.assertFalse(self.service.scene_matches_world(self.scene, self.world))

    def test_selection_is_excluded_from_fingerprint(self) -> None:
        before = self.service.fingerprint_world(self.scene, self.world)
        self.world.selected_entity_name = "Actor"
        self.assertEqual(before, self.service.fingerprint_world(self.scene, self.world))
        self.assertTrue(self.service.scene_matches_world(self.scene, self.world))

    def test_nested_key_order_is_canonical(self) -> None:
        left = {"b": {"z": 2, "a": 1}, "a": [3, 2, 1]}
        right = {"a": [3, 2, 1], "b": {"a": 1, "z": 2}}
        self.assertEqual(self.service.fingerprint_payload(left), self.service.fingerprint_payload(right))

    def test_non_finite_values_are_rejected(self) -> None:
        with self.assertRaises(ProjectionFingerprintError):
            self.service.fingerprint_payload({"value": float("nan")})

    def test_workspace_records_evidence_when_projection_is_installed(self) -> None:
        projection = SceneProjectionService(create_default_registry())
        workspace = SceneWorkspace(projection=projection, flow_policy=SceneFlowPolicy())
        workspace.load_scene(self.scene.to_dict())
        entry = workspace.get_active_entry()
        assert entry is not None and entry.projection_integrity_evidence is not None

        self.assertEqual(entry.projection_integrity_evidence.scene_revision, 1)
        self.assertEqual(
            entry.projection_integrity_evidence.canonical_fingerprint,
            AuthoringProjectionFingerprintService(projection.create_world).fingerprint_scene(entry.scene),
        )


if __name__ == "__main__":
    unittest.main()
