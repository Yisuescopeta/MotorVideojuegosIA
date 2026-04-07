import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.project.project_service import ProjectService
from tools import engine_cli


class EngineCliBuildCommandsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "project"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = ["engine_cli.py", *args]
        with patch("sys.argv", argv):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = engine_cli.main()
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_build_settings_show_and_set_support_json_and_file_output(self) -> None:
        show_out = self.workspace / "build_settings_show.json"
        exit_code, stdout, _ = self._run_cli(
            "build-settings",
            "show",
            "--project-root",
            self.project_root.as_posix(),
            "--json",
            "--out",
            show_out.as_posix(),
        )

        self.assertEqual(exit_code, 0)
        show_payload = json.loads(stdout)
        self.assertEqual(show_payload["startup_scene"], "levels/main_scene.json")
        self.assertTrue(show_out.exists())

        set_out = self.workspace / "build_settings_set.json"
        exit_code, stdout, _ = self._run_cli(
            "build-settings",
            "set",
            "--project-root",
            self.project_root.as_posix(),
            "--product-name",
            "CLI Project",
            "--company-name",
            "CLI Studio",
            "--startup-scene",
            "levels/main_scene.json",
            "--scene",
            "levels/main_scene.json",
            "--output-name",
            "CLI Project Build",
            "--development-build",
            "--include-logs",
            "--json",
            "--out",
            set_out.as_posix(),
        )

        self.assertEqual(exit_code, 0)
        set_payload = json.loads(stdout)
        self.assertEqual(set_payload["product_name"], "CLI Project")
        self.assertEqual(set_payload["company_name"], "CLI Studio")
        self.assertEqual(set_payload["scenes_in_build"], ["levels/main_scene.json"])
        self.assertTrue(set_payload["development_build"])
        self.assertTrue(set_payload["include_logs"])
        self.assertEqual(set_payload["output_name"], "CLI_Project_Build")
        self.assertTrue(set_out.exists())

    def test_prebuild_check_returns_zero_and_writes_json_for_valid_project(self) -> None:
        report_out = self.workspace / "prebuild_report.json"

        exit_code, stdout, _ = self._run_cli(
            "prebuild-check",
            "--project-root",
            self.project_root.as_posix(),
            "--json",
            "--out",
            report_out.as_posix(),
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["startup_scene"], "levels/main_scene.json")
        self.assertEqual(payload["selected_content"]["scenes"], ["levels/main_scene.json"])
        self.assertTrue(report_out.exists())

    def test_prebuild_check_returns_validation_exit_code_for_invalid_project(self) -> None:
        (self.project_root / "levels" / "main_scene.json").unlink()
        report_out = self.workspace / "prebuild_invalid.json"

        exit_code, stdout, _ = self._run_cli(
            "prebuild-check",
            "--project-root",
            self.project_root.as_posix(),
            "--json",
            "--out",
            report_out.as_posix(),
        )

        self.assertEqual(exit_code, 2)
        payload = json.loads(stdout)
        self.assertFalse(payload["valid"])
        self.assertTrue(any(item["code"] == "build_settings.startup_scene_missing" for item in payload["blocking_errors"]))
        self.assertTrue(report_out.exists())

    def test_build_player_command_emits_json_and_exit_codes(self) -> None:
        report_out = self.workspace / "build_player_report.json"

        class _FakeReport:
            def __init__(self, payload):
                self._payload = payload

            def to_dict(self):
                return dict(self._payload)

        class _FakeBuildPlayerService:
            def __init__(self, project_service):
                self.project_service = project_service

            def build_player(self, options):
                self.options = options
                return _FakeReport(
                    {
                        "status": "succeeded",
                        "target_platform": "windows_desktop",
                        "output_path": "C:/build/out",
                        "duration_seconds": 1.25,
                        "startup_scene": "levels/main_scene.json",
                        "included_scenes": ["levels/main_scene.json"],
                        "included_asset_counts": {
                            "scenes": 1,
                            "prefabs": 0,
                            "scripts": 0,
                            "assets": 0,
                            "metadata": 3,
                        },
                        "warnings": [],
                        "errors": [],
                        "output_summary": [],
                        "top_assets_by_size": [],
                        "references": {},
                        "generated_at_utc": "2026-04-03T22:30:00+00:00",
                        "development_build": False,
                        "development_extras": [],
                        "report_path": ".motor/build/player_build_report.json",
                    }
                )

        with patch("engine.project.BuildPlayerService", _FakeBuildPlayerService):
            exit_code, stdout, _ = self._run_cli(
                "build-player",
                "--project-root",
                self.project_root.as_posix(),
                "--json",
                "--report-out",
                report_out.as_posix(),
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["target_platform"], "windows_desktop")
        self.assertTrue(report_out.exists())

        class _FailingBuildPlayerService:
            def __init__(self, project_service):
                self.project_service = project_service

            def build_player(self, options):
                return _FakeReport(
                    {
                        "status": "failed",
                        "target_platform": "windows_desktop",
                        "output_path": "",
                        "duration_seconds": 0.1,
                        "startup_scene": "levels/main_scene.json",
                        "included_scenes": [],
                        "included_asset_counts": {
                            "scenes": 0,
                            "prefabs": 0,
                            "scripts": 0,
                            "assets": 0,
                            "metadata": 0,
                        },
                        "warnings": [],
                        "errors": [
                            {
                                "severity": "error",
                                "code": "build_player.packaging_failed",
                                "message": "Packaging failed.",
                                "path": "",
                                "stage": "packaging",
                            }
                        ],
                        "output_summary": [],
                        "top_assets_by_size": [],
                        "references": {},
                        "generated_at_utc": "2026-04-03T22:31:00+00:00",
                        "development_build": False,
                        "development_extras": [],
                    }
                )

        with patch("engine.project.BuildPlayerService", _FailingBuildPlayerService):
            exit_code, stdout, _ = self._run_cli(
                "build-player",
                "--project-root",
                self.project_root.as_posix(),
                "--json",
            )

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["errors"][0]["code"], "build_player.packaging_failed")


if __name__ == "__main__":
    unittest.main()
