import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.project.project_service import ProjectService

ROOT = Path(__file__).resolve().parents[1]


def _run_module_result(*args: str, cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def _scene_payload(name: str = "CLI Scene") -> dict:
    return {
        "name": name,
        "entities": [],
        "rules": [],
        "feature_metadata": {},
    }


class AIWorkflowCliTests(unittest.TestCase):
    def test_ai_context_generates_stable_artifacts_and_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_root = workspace / "project"
            global_home = workspace / "global"
            project_root.mkdir(parents=True, exist_ok=True)

            first = _run_module_result(
                "tools.engine_cli",
                "ai-context",
                "--project-root",
                project_root.as_posix(),
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )
            second = _run_module_result(
                "tools.engine_cli",
                "ai-context",
                "--project-root",
                project_root.as_posix(),
                "--json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )

            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            json_path = project_root / ".motor" / "meta" / "ai_context_pack.json"
            markdown_path = project_root / ".motor" / "meta" / "ai_context_pack.md"
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            first_contents = json_path.read_text(encoding="utf-8")
            second_payload = json.loads(second.stdout)
            self.assertEqual(second_payload["json_path"], ".motor/meta/ai_context_pack.json")
            self.assertEqual(first_contents, json_path.read_text(encoding="utf-8"))

    def test_ai_validate_handles_valid_scene_and_invalid_prefab(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_root = workspace / "project"
            global_home = workspace / "global"
            levels = project_root / "levels"
            prefabs = project_root / "prefabs"
            levels.mkdir(parents=True, exist_ok=True)
            prefabs.mkdir(parents=True, exist_ok=True)
            (levels / "valid_scene.json").write_text(json.dumps(_scene_payload(), indent=2), encoding="utf-8")
            (prefabs / "broken.prefab").write_text(
                json.dumps(
                    {
                        "root_name": "Broken",
                        "entities": [
                            {"name": "Broken", "components": {"Transform": {"enabled": True, "x": 0, "y": 0, "rotation": 0, "scale_x": 1, "scale_y": 1}}},
                            {"name": "Child", "components": {"Transform": {"enabled": True, "x": 0, "y": 0, "rotation": 0, "scale_x": 1, "scale_y": 1}}},
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            valid = _run_module_result(
                "tools.engine_cli",
                "ai-validate",
                "--target",
                "scene-file",
                "--path",
                "levels/valid_scene.json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )
            invalid = _run_module_result(
                "tools.engine_cli",
                "ai-validate",
                "--target",
                "prefab-file",
                "--path",
                "prefabs/broken.prefab",
                "--json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )

            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            self.assertIn("[OK] validation passed", valid.stdout)
            self.assertEqual(invalid.returncode, 2, invalid.stdout + invalid.stderr)
            invalid_payload = json.loads(invalid.stdout)
            self.assertFalse(invalid_payload["valid"])
            self.assertTrue(any(item["category"] == "prefab_schema" for item in invalid_payload["diagnostics"]))

    def test_ai_verify_reports_pass_fail_and_setup_failure_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_root = workspace / "project"
            global_home = workspace / "global"
            ProjectService(project_root, global_state_dir=global_home)
            levels = project_root / "levels"
            levels.mkdir(parents=True, exist_ok=True)
            (levels / "verify_scene.json").write_text(
                json.dumps(
                    {
                        "name": "Verify Scene",
                        "entities": [
                            {
                                "name": "Probe",
                                "active": True,
                                "tag": "Untagged",
                                "layer": "Default",
                                "components": {
                                    "Transform": {
                                        "enabled": True,
                                        "x": 1.0,
                                        "y": 2.0,
                                        "rotation": 0.0,
                                        "scale_x": 1.0,
                                        "scale_y": 1.0,
                                    }
                                },
                            }
                        ],
                        "rules": [],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            pass_scenario = workspace / "pass_scenario.json"
            fail_scenario = workspace / "fail_scenario.json"
            missing_scenario = workspace / "missing_scenario.json"
            pass_scenario.write_text(
                json.dumps(
                    {
                        "scenario_id": "pass-scenario",
                        "scene_path": "levels/verify_scene.json",
                        "assertions": [
                            {"assertion_id": "entity", "kind": "entity_exists", "entity_name": "Probe"}
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            fail_scenario.write_text(
                json.dumps(
                    {
                        "scenario_id": "fail-scenario",
                        "scene_path": "levels/verify_scene.json",
                        "assertions": [
                            {"assertion_id": "missing", "kind": "entity_exists", "entity_name": "Ghost"}
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            missing_scenario.write_text(
                json.dumps(
                    {
                        "scenario_id": "missing-scene",
                        "scene_path": "levels/missing_scene.json",
                        "assertions": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            passed = _run_module_result(
                "tools.engine_cli",
                "ai-verify",
                "--scenario",
                pass_scenario.as_posix(),
                "--json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )
            failed = _run_module_result(
                "tools.engine_cli",
                "ai-verify",
                "--scenario",
                fail_scenario.as_posix(),
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )
            missing = _run_module_result(
                "tools.engine_cli",
                "ai-verify",
                "--scenario",
                missing_scenario.as_posix(),
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )

            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertEqual(json.loads(passed.stdout)["status"], "pass")
            self.assertEqual(failed.returncode, 3, failed.stdout + failed.stderr)
            self.assertIn("[ERROR] verification failed", failed.stdout)
            self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
            self.assertIn("Failed to load scene", missing.stdout)

    def test_ai_workflow_runs_context_execution_validation_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_root = workspace / "project"
            global_home = workspace / "global"
            project_root.mkdir(parents=True, exist_ok=True)
            spec_path = workspace / "workflow_spec.json"
            out_path = workspace / "workflow_report.json"
            spec_path.write_text(
                json.dumps(
                    {
                        "context": {"enabled": True},
                        "authoring_request": {
                            "request_id": "workflow-pass",
                            "label": "create-scene",
                            "operations": [
                                {
                                    "operation_id": "create-scene",
                                    "kind": "create_scene",
                                    "scene_name": "Workflow Scene",
                                },
                                {
                                    "operation_id": "save-scene",
                                    "kind": "save_scene",
                                    "scene_ref": "levels/workflow_scene.json",
                                },
                            ],
                        },
                        "validation": {"target": "active-scene"},
                        "verification": {
                            "scenario_id": "verify-created-scene",
                            "scene_path": "levels/workflow_scene.json",
                            "assertions": [
                                {
                                    "assertion_id": "scene-selected",
                                    "kind": "selected_scene_is",
                                    "expected_scene_path": "levels/workflow_scene.json",
                                },
                                {
                                    "assertion_id": "scene-sanity",
                                    "kind": "engine_status_sanity",
                                    "expected_state": "EDIT",
                                    "min_entity_count": 0,
                                    "max_entity_count": 0,
                                },
                            ],
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = _run_module_result(
                "tools.engine_cli",
                "ai-workflow",
                "--spec",
                spec_path.as_posix(),
                "--json",
                "--out",
                out_path.as_posix(),
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertIsNotNone(payload["context"])
            self.assertEqual(payload["execution"]["status"], "success")
            self.assertTrue(payload["validation"]["valid"])
            self.assertEqual(payload["verification"]["status"], "pass")
            self.assertTrue((project_root / "levels" / "workflow_scene.json").exists())
            self.assertTrue(out_path.exists())

    def test_ai_workflow_returns_step_specific_failure_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_root = workspace / "project"
            global_home = workspace / "global"
            levels = project_root / "levels"
            project_root.mkdir(parents=True, exist_ok=True)
            levels.mkdir(parents=True, exist_ok=True)
            (levels / "invalid_scene.json").write_text(
                json.dumps(
                    {
                        "name": "Broken",
                        "entities": [{"name": "Child", "parent": "Ghost", "components": {}}],
                        "rules": [],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            execution_spec = workspace / "workflow_exec_fail.json"
            validation_spec = workspace / "workflow_validation_fail.json"
            verification_spec = workspace / "workflow_verification_fail.json"

            execution_spec.write_text(
                json.dumps(
                    {
                        "authoring_request": {
                            "request_id": "workflow-exec-fail",
                            "label": "reject-mixed",
                            "operations": [
                                {"operation_id": "op-1", "kind": "create_scene", "scene_name": "Mixed Scene"},
                                {"operation_id": "op-2", "kind": "create_entity", "entity_name": "Probe"},
                            ],
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            validation_spec.write_text(
                json.dumps(
                    {
                        "validation": {
                            "target": "scene-file",
                            "path": "levels/invalid_scene.json",
                        }
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            verification_spec.write_text(
                json.dumps(
                    {
                        "authoring_request": {
                            "request_id": "workflow-verify-fail",
                            "label": "create-scene",
                            "operations": [
                                {"operation_id": "op-1", "kind": "create_scene", "scene_name": "Verify Fail Scene"},
                                {"operation_id": "op-2", "kind": "save_scene", "scene_ref": "levels/verify_fail_scene.json"},
                            ],
                        },
                        "verification": {
                            "scenario_id": "verify-fail",
                            "scene_path": "levels/verify_fail_scene.json",
                            "assertions": [
                                {"assertion_id": "missing-entity", "kind": "entity_exists", "entity_name": "Ghost"}
                            ],
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            execution_result = _run_module_result(
                "tools.engine_cli",
                "ai-workflow",
                "--spec",
                execution_spec.as_posix(),
                "--json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )
            validation_result = _run_module_result(
                "tools.engine_cli",
                "ai-workflow",
                "--spec",
                validation_spec.as_posix(),
                "--json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )
            verification_result = _run_module_result(
                "tools.engine_cli",
                "ai-workflow",
                "--spec",
                verification_spec.as_posix(),
                "--json",
                cwd=project_root,
                extra_env={"MOTORVIDEOJUEGOSIA_HOME": global_home.as_posix()},
            )

            self.assertEqual(execution_result.returncode, 4, execution_result.stdout + execution_result.stderr)
            self.assertEqual(json.loads(execution_result.stdout)["exit_code"], 4)
            self.assertEqual(validation_result.returncode, 2, validation_result.stdout + validation_result.stderr)
            self.assertEqual(json.loads(validation_result.stdout)["exit_code"], 2)
            self.assertEqual(verification_result.returncode, 3, verification_result.stdout + verification_result.stderr)
            self.assertEqual(json.loads(verification_result.stdout)["exit_code"], 3)


if __name__ == "__main__":
    unittest.main()
