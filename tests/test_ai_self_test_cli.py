from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from motor.cli import run_motor_command


def _create_project(workspace: Path, name: str = "SelfTestProject") -> Path:
    project = workspace / name
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }
        ),
        encoding="utf-8",
    )
    for dirname in ["assets", "levels", "prefabs", "scripts", "settings", ".motor"]:
        (project / dirname).mkdir(parents=True, exist_ok=True)
    return project


def _run_motor(*args: str) -> tuple[int, dict]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        exit_code = run_motor_command(list(args))
    output = stdout_buffer.getvalue()
    if "{" not in output:
        output += stderr_buffer.getvalue()
    payload = json.loads(output[output.index("{"):])
    return exit_code, payload


def _file_snapshot(project: Path) -> dict[str, str]:
    return {
        path.relative_to(project).as_posix(): path.read_text(encoding="utf-8")
        for path in project.rglob("*")
        if path.is_file()
    }


class AISelfTestCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project = _create_project(self.workspace)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_self_test_platformer_passes_and_reports_required_json(self) -> None:
        exit_code, payload = _run_motor(
            "ai",
            "self-test",
            "--project",
            str(self.project),
            "--profile",
            "platformer",
            "--json",
        )

        self.assertEqual(exit_code, 0, payload)
        self.assertTrue(payload["success"], payload)
        data = payload["data"]
        for key in [
            "success",
            "profile",
            "commands_executed",
            "validations",
            "generated_scene",
            "events",
            "cleanup_status",
            "warnings",
        ]:
            self.assertIn(key, data)
        self.assertTrue(data["success"])
        self.assertEqual(data["profile"], "platformer")
        self.assertEqual(data["recipe"]["id"], "platformer-basic")
        self.assertTrue(data["commands_executed"])
        self.assertTrue(all(command["success"] for command in data["commands_executed"]))
        self.assertTrue(data["validations"])
        self.assertTrue(all(validation["success"] for validation in data["validations"]))
        self.assertTrue(data["generated_scene"]["exists_before_cleanup"])
        self.assertIn("Player", data["generated_scene"]["entity_names"])
        self.assertTrue(data["cleanup_status"]["removed"], data["cleanup_status"])

    def test_self_test_default_does_not_leave_real_project_files(self) -> None:
        before = _file_snapshot(self.project)

        exit_code, payload = _run_motor(
            "ai",
            "self-test",
            "--project",
            str(self.project),
            "--profile",
            "platformer",
            "--json",
        )

        self.assertEqual(exit_code, 0, payload)
        self.assertEqual(_file_snapshot(self.project), before)
        self.assertFalse((self.project / ".motor" / "tmp").exists())
        self.assertFalse(any((self.project / "levels").iterdir()))

    def test_self_test_in_place_creates_scene_in_real_project(self) -> None:
        exit_code, payload = _run_motor(
            "ai",
            "self-test",
            "--project",
            str(self.project),
            "--profile",
            "platformer",
            "--in-place",
            "--json",
        )

        self.assertEqual(exit_code, 0, payload)
        self.assertTrue(payload["success"], payload)
        self.assertTrue((self.project / "levels" / "level_1.json").exists())
        self.assertTrue(payload["data"]["cleanup_status"]["skipped"])

    def test_self_test_missing_capability_fails_before_recipe_execution(self) -> None:
        class MissingRegistry:
            def get(self, capability_id: str):  # noqa: ANN001
                if capability_id == "runtime:step":
                    return None

                class Cap:
                    id = capability_id
                    status = "implemented"

                return Cap()

            def to_dict(self) -> dict:
                return {"capabilities": []}

        with patch("engine.ai.get_default_registry", return_value=MissingRegistry()):
            with patch("engine.api._assets_project_api.AssetsProjectAPI.run_recipe") as run_recipe_mock:
                exit_code, payload = _run_motor(
                    "ai",
                    "self-test",
                    "--project",
                    str(self.project),
                    "--profile",
                    "platformer",
                    "--json",
                )

        self.assertEqual(exit_code, 1, payload)
        self.assertFalse(payload["success"], payload)
        missing = payload["data"]["missing_capabilities"]
        self.assertTrue(any(m["id"] == "runtime:step" and m["reason"] == "not_registered" for m in missing))
        run_recipe_mock.assert_not_called()
        self.assertFalse((self.project / ".motor" / "tmp").exists())

    def test_self_test_unknown_profile_fails_clearly(self) -> None:
        exit_code, payload = _run_motor(
            "ai",
            "self-test",
            "--project",
            str(self.project),
            "--profile",
            "unknown",
            "--json",
        )

        self.assertEqual(exit_code, 1, payload)
        self.assertFalse(payload["success"], payload)
        self.assertEqual(payload["message"], "AI self-test failed: unsupported profile")
        self.assertEqual(payload["data"]["profile"], "unknown")
        self.assertFalse((self.project / ".motor" / "tmp").exists())


if __name__ == "__main__":
    unittest.main()
