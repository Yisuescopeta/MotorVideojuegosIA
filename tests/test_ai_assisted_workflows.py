import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from engine.api import EngineAPI
from engine.workflows.ai_assist import (
    AuthoringOperationKind,
    AuthoringPlan,
    AuthoringPlanStep,
    AuthoringRequest,
    PlanStepKind,
    ValidationStatus,
    VerificationMode,
    VerificationStatus,
    WorkflowStatus,
    build_project_context_snapshot,
    summarize_workflow_result,
    validate_prefab_payload,
    validate_scene_payload,
    validate_workflow,
    verify_headless_capture,
)


def _scene_payload() -> dict:
    return {
        "name": "Workflow Scene",
        "entities": [
            {
                "name": "Player",
                "active": True,
                "tag": "Player",
                "layer": "Gameplay",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 10.0,
                        "y": 20.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            }
        ],
        "rules": [],
        "feature_metadata": {"scene_flow": {"next_scene": "levels/next.json"}},
    }


def _prefab_payload() -> dict:
    return {
        "root_name": "EnemyPrefab",
        "entities": [
            {
                "name": "EnemyPrefab",
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
    }


class AIAssistedWorkflowFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "project"
        self.global_state_dir = self.root / "global_state"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.scene_path = self.project_root / "levels" / "workflow_scene.json"
        self.scene_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_path.write_text(json.dumps(_scene_payload(), indent=2), encoding="utf-8")
        script_path = self.project_root / "scripts" / "player_logic.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text("def update(entity, dt):\n    return None\n", encoding="utf-8")
        prefab_path = self.project_root / "prefabs" / "enemy.prefab"
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.write_text(json.dumps(_prefab_payload(), indent=2), encoding="utf-8")

        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_context_snapshot_is_serializable_and_uses_public_engine_surfaces(self) -> None:
        self.api.load_level("levels/workflow_scene.json")

        snapshot = build_project_context_snapshot(self.api, snapshot_id="ctx-1")
        payload = snapshot.to_dict()

        self.assertEqual(snapshot.snapshot_id, "ctx-1")
        self.assertEqual(snapshot.project_name, self.project_root.name)
        self.assertEqual(snapshot.current_scene_name, "Workflow Scene")
        self.assertIn("levels/workflow_scene.json", payload["current_scene_path"])
        self.assertIn("prefabs/enemy.prefab", snapshot.prefab_paths)
        self.assertIn("scripts/player_logic.py", snapshot.script_paths)
        self.assertGreaterEqual(snapshot.asset_count, 0)
        json.dumps(payload, sort_keys=True)

    def test_validate_workflow_blocks_empty_plan_and_paths_outside_project(self) -> None:
        request = AuthoringRequest(
            workflow_id="wf-1",
            goal="Add enemy prefab to scene",
            operation_kind=AuthoringOperationKind.SCENE_EDIT,
            verification_mode=VerificationMode.HEADLESS_CAPTURE,
            target_scene_path="levels/workflow_scene.json",
            target_prefab_path=(self.root / "outside" / "enemy.json").as_posix(),
        )
        plan = AuthoringPlan(plan_id="plan-1", request_id="wf-1", steps=[])

        report = validate_workflow(self.api, request, plan=plan)

        self.assertEqual(report.status, ValidationStatus.FAIL)
        self.assertGreaterEqual(report.blocking_issue_count, 2)
        self.assertTrue(any(issue.code == "plan.no_steps" for issue in report.issues))
        self.assertTrue(any(issue.code == "request.path_outside_project" for issue in report.issues))

    def test_schema_validation_helpers_reuse_existing_scene_and_prefab_validation(self) -> None:
        invalid_scene = _scene_payload()
        invalid_scene["entities"][0]["components"]["Transform"]["x"] = "bad"
        scene_report = validate_scene_payload(invalid_scene)
        self.assertEqual(scene_report.status, ValidationStatus.FAIL)

        valid_prefab = validate_prefab_payload(_prefab_payload())
        self.assertEqual(valid_prefab.status, ValidationStatus.PASS)

    def test_verification_report_records_headless_capture_evidence(self) -> None:
        self.api.load_level("levels/workflow_scene.json")

        report = verify_headless_capture(self.api, frames=2, capture_every=1)

        self.assertEqual(report.status, VerificationStatus.PASS)
        self.assertEqual(report.executed_checks, ["headless_capture"])
        self.assertEqual(report.evidences[0].kind, "headless_capture")
        self.assertIn("final_world_hash", report.runtime_details)

    def test_workflow_summary_composes_validation_and_verification_states(self) -> None:
        self.api.load_level("levels/workflow_scene.json")
        context = build_project_context_snapshot(self.api, snapshot_id="ctx-2")
        request = AuthoringRequest(
            workflow_id="wf-2",
            goal="Verify loaded scene",
            operation_kind=AuthoringOperationKind.ANALYSIS_ONLY,
            verification_mode=VerificationMode.HEADLESS_CAPTURE,
            target_scene_path="levels/workflow_scene.json",
        )
        plan = AuthoringPlan(
            plan_id="plan-2",
            request_id="wf-2",
            steps=[
                AuthoringPlanStep(
                    step_id="step-1",
                    kind=PlanStepKind.CHECK,
                    description="Ensure scene is loaded before verification.",
                    target="levels/workflow_scene.json",
                )
            ],
        )
        validation = validate_workflow(self.api, request, plan=plan)
        verification = verify_headless_capture(self.api, frames=1)

        summary = summarize_workflow_result(
            request,
            context=context,
            validation=validation,
            verification=verification,
            plan=plan,
            changed_targets=["levels/workflow_scene.json"],
        )

        self.assertEqual(summary.status, WorkflowStatus.VERIFIED)
        self.assertEqual(summary.validation_status, ValidationStatus.PASS)
        self.assertEqual(summary.verification_status, VerificationStatus.PASS)
        self.assertEqual(summary.context_snapshot_id, "ctx-2")
        json.dumps(summary.to_dict(), sort_keys=True)

    def test_dataclasses_remain_json_friendly(self) -> None:
        request = AuthoringRequest(
            workflow_id="wf-json",
            goal="Keep structure explicit",
            operation_kind=AuthoringOperationKind.SCRIPT_EDIT,
            verification_mode=VerificationMode.NONE,
            target_script_path="scripts/player_logic.py",
            constraints=["Do not edit engine internals."],
        )
        plan = AuthoringPlan(
            plan_id="plan-json",
            request_id="wf-json",
            steps=[
                AuthoringPlanStep(
                    step_id="step-json",
                    kind=PlanStepKind.ENGINE_API_CALL,
                    description="Apply script update through a higher-level caller.",
                    engine_api_call="save_asset_metadata",
                    target="scripts/player_logic.py",
                )
            ],
            requires_confirmation=True,
        )

        json.dumps(asdict(request), sort_keys=True)
        json.dumps(asdict(plan), sort_keys=True)


if __name__ == "__main__":
    unittest.main()
