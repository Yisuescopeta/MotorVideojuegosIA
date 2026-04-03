import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.workflows.ai_assist import (
    AuthoringEntityPropertyKind,
    AuthoringExecutionOperation,
    AuthoringExecutionOperationKind,
    AuthoringExecutionRequest,
    AuthoringExecutionService,
    AuthoringExecutionStatus,
    RollbackStatus,
)


def _scene_payload(name: str = "Execution Scene") -> dict:
    return {
        "name": name,
        "entities": [],
        "rules": [],
        "feature_metadata": {},
    }


def _collider_payload() -> dict:
    return {
        "enabled": True,
        "shape_type": "box",
        "width": 16.0,
        "height": 16.0,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "is_trigger": False,
    }


class AIAuthoringExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.scene_path = self.project_root / "levels" / "execution_scene.json"
        self.scene_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_path.write_text(json.dumps(_scene_payload(), indent=2), encoding="utf-8")
        self.api = EngineAPI(project_root=self.project_root.as_posix())
        self.executor = AuthoringExecutionService(self.api)

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _load_main_scene(self) -> None:
        self.api.load_level("levels/execution_scene.json")

    def test_successful_transactional_session_commits_and_groups_undo(self) -> None:
        self._load_main_scene()
        request = AuthoringExecutionRequest(
            request_id="exec-1",
            label="create-probe-rig",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_ENTITY,
                    entity_name="Probe",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-2",
                    kind=AuthoringExecutionOperationKind.ADD_COMPONENT,
                    entity_name="Probe",
                    component_name="Collider",
                    component_data=_collider_payload(),
                ),
                AuthoringExecutionOperation(
                    operation_id="op-3",
                    kind=AuthoringExecutionOperationKind.EDIT_COMPONENT_FIELD,
                    entity_name="Probe",
                    component_name="Transform",
                    field_name="x",
                    field_value=25.0,
                ),
                AuthoringExecutionOperation(
                    operation_id="op-4",
                    kind=AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY,
                    entity_name="Probe",
                    property_kind=AuthoringEntityPropertyKind.TAG,
                    property_value="MainCamera",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-5",
                    kind=AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY,
                    entity_name="Probe",
                    property_kind=AuthoringEntityPropertyKind.LAYER,
                    property_value="Gameplay",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-6",
                    kind=AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY,
                    entity_name="Probe",
                    property_kind=AuthoringEntityPropertyKind.ACTIVE,
                    property_value=False,
                ),
            ],
            target_scene_ref="levels/execution_scene.json",
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.SUCCESS)
        self.assertEqual(result.rollback_status, RollbackStatus.NOT_NEEDED)
        self.assertEqual(result.operations_applied, ["op-1", "op-2", "op-3", "op-4", "op-5", "op-6"])
        self.assertTrue(result.validation_required_next)
        probe = self.api.get_entity("Probe")
        self.assertEqual(probe["components"]["Transform"]["x"], 25.0)
        self.assertEqual(probe["tag"], "MainCamera")
        self.assertEqual(probe["layer"], "Gameplay")
        self.assertFalse(probe["active"])
        self.assertIn("Collider", probe["components"])

        self.assertTrue(self.api.undo()["success"])
        with self.assertRaises(Exception):
            self.api.get_entity("Probe")

        self.assertTrue(self.api.redo()["success"])
        probe = self.api.get_entity("Probe")
        self.assertEqual(probe["tag"], "MainCamera")
        json.dumps(result.to_dict(), sort_keys=True)

    def test_failing_transactional_session_rolls_back(self) -> None:
        self._load_main_scene()
        request = AuthoringExecutionRequest(
            request_id="exec-rollback",
            label="rollback-on-failure",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_ENTITY,
                    entity_name="WillRollback",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-2",
                    kind=AuthoringExecutionOperationKind.EDIT_COMPONENT_FIELD,
                    entity_name="MissingEntity",
                    component_name="Transform",
                    field_name="x",
                    field_value=10.0,
                ),
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.ROLLED_BACK)
        self.assertEqual(result.rollback_status, RollbackStatus.SUCCEEDED)
        self.assertEqual(result.operations_applied, ["op-1"])
        self.assertTrue(any(diagnostic.code == "operation.failed" for diagnostic in result.diagnostics))
        with self.assertRaises(Exception):
            self.api.get_entity("WillRollback")

    def test_prefab_instantiation_uses_public_workflow_dispatch(self) -> None:
        self._load_main_scene()
        prefab_path = self.project_root / "prefabs" / "enemy.prefab"
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "root_name": "Enemy",
                    "entities": [
                        {
                            "name": "Enemy",
                            "active": True,
                            "tag": "Enemy",
                            "layer": "Gameplay",
                            "components": {
                                "Transform": {
                                    "enabled": True,
                                    "x": 0.0,
                                    "y": 0.0,
                                    "rotation": 0.0,
                                    "scale_x": 1.0,
                                    "scale_y": 1.0,
                                }
                            },
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        request = AuthoringExecutionRequest(
            request_id="exec-prefab",
            label="instantiate-prefab",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-prefab",
                    kind=AuthoringExecutionOperationKind.INSTANTIATE_PREFAB,
                    prefab_path="prefabs/enemy.prefab",
                    prefab_name="EnemyFromWorkflow",
                )
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.SUCCESS)
        self.assertEqual(result.operations_applied, ["op-prefab"])
        self.assertTrue(result.validation_required_next)
        enemy = self.api.get_entity("EnemyFromWorkflow")
        self.assertEqual(enemy["name"], "EnemyFromWorkflow")
        json.dumps(result.to_dict(), sort_keys=True)

    def test_workspace_only_scene_operations_preserve_workspace_state(self) -> None:
        self._load_main_scene()
        second_scene = self.project_root / "levels" / "secondary_scene.json"
        second_scene.write_text(json.dumps(_scene_payload("Secondary Scene"), indent=2), encoding="utf-8")

        request = AuthoringExecutionRequest(
            request_id="exec-workspace",
            label="workspace-session",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_SCENE,
                    scene_name="Created Scene",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-2",
                    kind=AuthoringExecutionOperationKind.OPEN_SCENE,
                    scene_ref="levels/secondary_scene.json",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-3",
                    kind=AuthoringExecutionOperationKind.ACTIVATE_SCENE,
                    scene_ref="levels/created_scene.json",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-4",
                    kind=AuthoringExecutionOperationKind.SAVE_SCENE,
                    scene_ref="levels/created_scene.json",
                ),
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.SUCCESS)
        self.assertEqual(result.rollback_status, RollbackStatus.NOT_APPLICABLE)
        self.assertTrue(result.validation_required_next)
        self.assertTrue(result.final_target_scene_ref.endswith("levels/created_scene.json"))
        open_paths = {str(scene["path"]) for scene in self.api.list_open_scenes()}
        self.assertTrue(any(path.endswith("levels/execution_scene.json") for path in open_paths))
        self.assertTrue(any(path.endswith("levels/secondary_scene.json") for path in open_paths))
        self.assertTrue(any(path.endswith("levels/created_scene.json") for path in open_paths))
        self.assertTrue((self.project_root / "levels" / "created_scene.json").exists())

    def test_rejects_mixed_execution_modes(self) -> None:
        self._load_main_scene()
        request = AuthoringExecutionRequest(
            request_id="exec-mixed",
            label="mixed-request",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_ENTITY,
                    entity_name="Probe",
                ),
                AuthoringExecutionOperation(
                    operation_id="op-2",
                    kind=AuthoringExecutionOperationKind.SAVE_SCENE,
                    scene_ref="levels/execution_scene.json",
                ),
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.REJECTED)
        self.assertTrue(any(diagnostic.code == "request.mixed_execution_modes" for diagnostic in result.diagnostics))

    def test_rejects_missing_required_fields_and_invalid_property_kind(self) -> None:
        self._load_main_scene()
        request = AuthoringExecutionRequest(
            request_id="exec-invalid",
            label="invalid-fields",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_ENTITY,
                ),
                AuthoringExecutionOperation(
                    operation_id="op-2",
                    kind=AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY,
                    entity_name="Probe",
                    property_kind="parent",  # type: ignore[arg-type]
                    property_value="Root",
                ),
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.REJECTED)
        codes = {diagnostic.code for diagnostic in result.diagnostics}
        self.assertIn("operation.missing_entity_name", codes)
        self.assertIn("operation.invalid_property_kind", codes)

    def test_rejects_transactional_request_without_active_scene(self) -> None:
        request = AuthoringExecutionRequest(
            request_id="exec-no-scene",
            label="no-active-scene",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_ENTITY,
                    entity_name="Probe",
                )
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.REJECTED)
        self.assertTrue(any(diagnostic.code == "request.no_active_scene" for diagnostic in result.diagnostics))

    def test_rejects_transactional_target_scene_mismatch(self) -> None:
        self._load_main_scene()
        request = AuthoringExecutionRequest(
            request_id="exec-mismatch",
            label="scene-mismatch",
            target_scene_ref="levels/other_scene.json",
            operations=[
                AuthoringExecutionOperation(
                    operation_id="op-1",
                    kind=AuthoringExecutionOperationKind.CREATE_ENTITY,
                    entity_name="Probe",
                )
            ],
        )

        result = self.executor.execute(request)

        self.assertEqual(result.status, AuthoringExecutionStatus.REJECTED)
        self.assertTrue(any(diagnostic.code == "request.target_scene_mismatch" for diagnostic in result.diagnostics))


if __name__ == "__main__":
    unittest.main()
