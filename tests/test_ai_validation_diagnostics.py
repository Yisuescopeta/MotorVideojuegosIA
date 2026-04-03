import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.serialization.schema import migrate_prefab_data, migrate_scene_data
from engine.workflows.ai_assist import (
    AuthoringValidationService,
    ValidationDiagnosticCategory,
    ValidationTargetKind,
)


def _transform() -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": 0.0,
        "y": 0.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _entity(
    name: str,
    *,
    components: dict[str, object] | None = None,
    parent: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "active": True,
        "tag": "Untagged",
        "layer": "Default",
        "components": components or {"Transform": _transform()},
    }
    if parent is not None:
        payload["parent"] = parent
    return payload


def _scene_payload(
    name: str,
    entities: list[dict[str, object]],
    *,
    feature_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "entities": entities,
        "rules": [],
        "feature_metadata": feature_metadata or {},
    }


class AIValidationDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "project"
        self.api = EngineAPI(project_root=self.project_root.as_posix())
        self.validator = AuthoringValidationService(self.api)

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, relative_path: str, payload: dict[str, object]) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(migrate_scene_data(payload), indent=2), encoding="utf-8")
        return path

    def _write_prefab(self, relative_path: str, payload: dict[str, object]) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(migrate_prefab_data(payload), indent=2), encoding="utf-8")
        return path

    def test_validate_scene_file_accepts_valid_scene(self) -> None:
        self._write_scene(
            "levels/valid_scene.json",
            _scene_payload("Valid Scene", [_entity("Player")]),
        )

        report = self.validator.validate_scene_file("levels/valid_scene.json")

        self.assertTrue(report.valid)
        self.assertEqual(report.target_kind, ValidationTargetKind.SCENE_FILE)
        self.assertEqual(report.target_reference, "levels/valid_scene.json")
        self.assertEqual(report.diagnostics, [])
        self.assertEqual(report.raw_messages, [])

    def test_validate_scene_file_reports_invalid_hierarchy(self) -> None:
        self._write_scene(
            "levels/invalid_hierarchy.json",
            _scene_payload("Broken Hierarchy", [_entity("Child", parent="Ghost")]),
        )

        report = self.validator.validate_scene_file("levels/invalid_hierarchy.json")

        self.assertFalse(report.valid)
        self.assertTrue(report.raw_messages)
        self.assertTrue(
            any(diagnostic.category == ValidationDiagnosticCategory.SCENE_HIERARCHY for diagnostic in report.diagnostics)
        )
        self.assertTrue(
            any(diagnostic.code == "scene_hierarchy.unknown_parent" for diagnostic in report.diagnostics)
        )
        self.assertTrue(any("unknown parent 'Ghost'" in message for message in report.raw_messages))

    def test_validate_scene_transition_references_reports_broken_target(self) -> None:
        self._write_scene(
            "levels/source_scene.json",
            _scene_payload(
                "Source Scene",
                [
                    _entity(
                        "Portal",
                        components={
                            "Transform": _transform(),
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/missing_scene.json",
                                "target_entry_id": "",
                            },
                        },
                    )
                ],
            ),
        )

        transition_report = self.validator.validate_scene_transition_references("levels/source_scene.json")
        scene_report = self.validator.validate_scene_file("levels/source_scene.json")

        self.assertFalse(transition_report.valid)
        self.assertTrue(
            any(diagnostic.category == ValidationDiagnosticCategory.SCENE_TRANSITION for diagnostic in transition_report.diagnostics)
        )
        self.assertTrue(
            any(diagnostic.code == "scene_transition.target_scene_missing" for diagnostic in transition_report.diagnostics)
        )
        self.assertTrue(any("target scene 'levels/missing_scene.json' does not exist" in message for message in transition_report.raw_messages))
        self.assertFalse(scene_report.valid)
        self.assertTrue(
            any(diagnostic.category == ValidationDiagnosticCategory.SCENE_TRANSITION for diagnostic in scene_report.diagnostics)
        )

    def test_validate_prefab_file_reports_invalid_prefab(self) -> None:
        self._write_prefab(
            "prefabs/invalid_enemy.prefab",
            {
                "root_name": "Enemy",
                "entities": [
                    {"name": "Enemy", "components": {"Transform": _transform()}},
                    {"name": "Weapon", "components": {"Transform": _transform()}},
                ],
            },
        )

        report = self.validator.validate_prefab_file("prefabs/invalid_enemy.prefab")

        self.assertFalse(report.valid)
        self.assertEqual(report.target_kind, ValidationTargetKind.PREFAB_FILE)
        self.assertTrue(
            all(diagnostic.category == ValidationDiagnosticCategory.PREFAB_SCHEMA for diagnostic in report.diagnostics)
        )
        self.assertTrue(any("expected exactly one root entity" in message for message in report.raw_messages))

    def test_validate_project_lightweight_reports_mixed_validity(self) -> None:
        self._write_scene(
            "levels/valid_scene.json",
            _scene_payload("Valid Scene", [_entity("Player")]),
        )
        self._write_scene(
            "levels/invalid_scene.json",
            _scene_payload("Invalid Scene", [_entity("Child", parent="Ghost")]),
        )
        self._write_scene(
            "levels/transition_scene.json",
            _scene_payload(
                "Transition Scene",
                [
                    _entity(
                        "Portal",
                        components={
                            "Transform": _transform(),
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/nowhere.json",
                                "target_entry_id": "",
                            },
                        },
                    )
                ],
            ),
        )
        self._write_prefab(
            "prefabs/broken.prefab",
            {
                "root_name": "Broken",
                "entities": [
                    {"name": "Broken", "components": {"Transform": _transform()}},
                    {"name": "Child", "parent": "Ghost", "components": {"Transform": _transform()}},
                ],
            },
        )

        report = self.validator.validate_project_lightweight()

        self.assertFalse(report.valid)
        self.assertEqual(report.target_kind, ValidationTargetKind.PROJECT)
        self.assertIn("levels/valid_scene.json", report.checked_files)
        self.assertIn("levels/invalid_scene.json", report.checked_files)
        self.assertIn("levels/transition_scene.json", report.checked_files)
        self.assertIn("prefabs/broken.prefab", report.checked_files)
        self.assertTrue(
            any(diagnostic.category == ValidationDiagnosticCategory.SCENE_HIERARCHY for diagnostic in report.diagnostics)
        )
        self.assertTrue(
            any(diagnostic.category == ValidationDiagnosticCategory.SCENE_TRANSITION for diagnostic in report.diagnostics)
        )
        self.assertTrue(
            any(diagnostic.category == ValidationDiagnosticCategory.PREFAB_SCHEMA for diagnostic in report.diagnostics)
        )

    def test_validate_active_scene_uses_unsaved_workspace_state(self) -> None:
        self._write_scene(
            "levels/live_scene.json",
            _scene_payload("Live Scene", [_entity("Player")]),
        )
        self.api.load_level("levels/live_scene.json")
        create_result = self.api.create_entity("UnsavedEnemy")
        self.assertTrue(create_result["success"])
        self.assertTrue(self.api.get_active_scene()["dirty"])

        report = self.validator.validate_active_scene()

        self.assertTrue(report.valid)
        self.assertEqual(report.target_kind, ValidationTargetKind.ACTIVE_SCENE)
        self.assertEqual(report.target_reference, "levels/live_scene.json")
        self.assertEqual(report.checked_files, ["levels/live_scene.json"])
        json.dumps(report.to_dict(), sort_keys=True)


if __name__ == "__main__":
    unittest.main()
