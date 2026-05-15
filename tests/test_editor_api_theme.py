from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from engine.api import EngineAPI
from engine.editor.ui_core.theme import set_active_theme
from motor.cli import run_motor_command


def _create_project(root: Path) -> Path:
    project = root / "ThemeProject"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"name": "ThemeProject", "version": 2, "engine_version": "2026.03"}),
        encoding="utf-8",
    )
    (project / ".motor").mkdir()
    return project


def _run_cli(*args: str) -> tuple[int, dict[str, object]]:
    output = StringIO()
    with redirect_stdout(output):
        code = run_motor_command(list(args))
    return code, json.loads(output.getvalue())


class EditorAPIThemeTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_active_theme("unity_dark")

    def test_engine_api_lists_sets_and_persists_active_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _create_project(Path(tmp))
            api = EngineAPI(project_root=str(project))
            self.assertIn("unity_dark", [theme["name"] for theme in api.list_editor_themes()])

            result = api.set_active_editor_theme("unity_light")
            self.assertTrue(result["success"])
            self.assertEqual(api.get_active_editor_theme()["name"], "unity_light")
            api.shutdown()

            api = EngineAPI(project_root=str(project))
            self.assertEqual(api.get_active_editor_theme()["name"], "unity_light")
            state = api.get_editor_state()
            self.assertEqual(state["preferences"]["editor_theme"], "unity_light")
            api.shutdown()

    def test_engine_api_exports_and_imports_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _create_project(Path(tmp))
            api = EngineAPI(project_root=str(project))
            export_result = api.export_editor_theme("theme.json", name="unity_light")
            self.assertTrue(export_result["success"])
            path = Path(export_result["data"]["path"])
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["name"] = "custom_light"
            path.write_text(json.dumps(payload), encoding="utf-8")

            import_result = api.import_editor_theme("theme.json")
            self.assertTrue(import_result["success"])
            self.assertEqual(api.get_active_editor_theme()["name"], "custom_light")
            api.shutdown()

            api = EngineAPI(project_root=str(project))
            self.assertEqual(api.get_active_editor_theme()["name"], "custom_light")
            api.shutdown()

    def test_cli_theme_list_active_set_export_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _create_project(Path(tmp))
            project_arg = str(project)

            code, response = _run_cli("editor", "theme", "list", "--project", project_arg, "--json")
            self.assertEqual(code, 0)
            self.assertTrue(response["success"])
            self.assertGreaterEqual(response["data"]["count"], 2)

            code, response = _run_cli("editor", "theme", "set", "unity_light", "--project", project_arg, "--json")
            self.assertEqual(code, 0)
            self.assertEqual(response["data"]["name"], "unity_light")

            code, response = _run_cli("editor", "theme", "active", "--project", project_arg, "--json")
            self.assertEqual(code, 0)
            self.assertEqual(response["data"]["name"], "unity_light")

            code, response = _run_cli(
                "editor", "theme", "export", "theme.json", "--name", "unity_dark", "--project", project_arg, "--json"
            )
            self.assertEqual(code, 0)
            path = Path(response["data"]["path"])
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["name"] = "cli_custom_dark"
            path.write_text(json.dumps(payload), encoding="utf-8")

            code, response = _run_cli("editor", "theme", "import", "theme.json", "--project", project_arg, "--json")
            self.assertEqual(code, 0)
            self.assertEqual(response["data"]["name"], "cli_custom_dark")

    def test_engine_api_feature_flags_default_set_persist_and_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
            os.environ.pop("MOTOR_EDITOR_CONTROL_CONSOLE", None)
            project = _create_project(Path(tmp))
            api = EngineAPI(project_root=str(project))

            payload = api.get_editor_feature_flags()
            self.assertEqual(payload["schema_version"], 1)
            self.assertIn("console_panel", payload["flags"])
            self.assertFalse(payload["flags"]["console_panel"])

            result = api.set_editor_feature_flag("console_panel", True)
            self.assertTrue(result["success"])
            self.assertEqual(result["data"]["flags"]["console_panel"], True)
            api.shutdown()

            api = EngineAPI(project_root=str(project))
            self.assertEqual(api.get_editor_feature_flags()["flags"]["console_panel"], True)
            api.shutdown()

            with patch.dict(os.environ, {"MOTOR_EDITOR_CONTROL_CONSOLE": "false"}):
                api = EngineAPI(project_root=str(project))
                payload = api.get_editor_feature_flags()
                self.assertEqual(payload["flags"]["console_panel"], False)
                self.assertEqual(payload["env_overrides"], {"console_panel": "MOTOR_EDITOR_CONTROL_CONSOLE"})
                api.shutdown()

    def test_engine_api_feature_flags_reject_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _create_project(Path(tmp))
            api = EngineAPI(project_root=str(project))
            result = api.set_editor_feature_flag("missing", True)
            self.assertFalse(result["success"])
            self.assertIn("Unknown editor feature flag", result["message"])
            api.shutdown()

    def test_cli_feature_flags_list_and_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
            os.environ.pop("MOTOR_EDITOR_CONTROL_CONSOLE", None)
            project = _create_project(Path(tmp))
            project_arg = str(project)

            code, response = _run_cli("editor", "feature-flags", "list", "--project", project_arg, "--json")
            self.assertEqual(code, 0)
            self.assertIn("console_panel", response["data"]["flags"])
            self.assertFalse(response["data"]["flags"]["console_panel"])

            code, response = _run_cli(
                "editor", "feature-flags", "set", "console_panel", "true", "--project", project_arg, "--json"
            )
            self.assertEqual(code, 0)
            self.assertEqual(response["data"]["flags"]["console_panel"], True)
