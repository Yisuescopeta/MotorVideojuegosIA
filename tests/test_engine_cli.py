"""
tests/test_engine_cli.py - Legacy compatibility tests for tools.engine_cli

This file maintains backward compatibility tests for the legacy CLI.
For new tests, use test_motor_interface_coherence.py and test_motor_animator_e2e.py

The official CLI interface is `motor [command] [options]` via python -m motor.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _copy_project_file(project_root: Path, relative_path: str) -> Path:
    source = ROOT / relative_path
    target = project_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _read_root_editor_state() -> str:
    return (ROOT / ".motor" / "editor_state.json").read_text(encoding="utf-8")


def _run_module(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run python -m motor command (official interface)."""
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    result = subprocess.run(
        [sys.executable, "-m", "motor"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: motor {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _run_module_result(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run python -m motor command without asserting success (official interface)."""
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    return subprocess.run(
        [sys.executable, "-m", "motor"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def _run_legacy_module(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run python -m tools.engine_cli command (legacy, for compatibility only)."""
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    result = subprocess.run(
        [sys.executable, "-m", "tools.engine_cli"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: python -m tools.engine_cli {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class MotorCliOfficialInterfaceTests(unittest.TestCase):
    """Tests for the official `motor` CLI interface."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)

        # Create a minimal valid project
        self.project_root = self.workspace / "TestProject"
        self.project_root.mkdir()

        # Create project.json
        (self.project_root / "project.json").write_text(
            json.dumps({
                "name": "TestProject",
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
            }),
            encoding="utf-8",
        )

        # Create required directories
        for dir_name in ["assets", "levels", "scripts", "settings", ".motor"]:
            (self.project_root / dir_name).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_motor_capabilities_outputs_valid_json(self) -> None:
        """motor capabilities --json returns valid JSON."""
        result = _run_module("capabilities", "--json", cwd=self.workspace)
        data = json.loads(result.stdout[result.stdout.index("{"):])
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("capabilities", data["data"])

    def test_motor_doctor_reports_project_health(self) -> None:
        """motor doctor --project <path> --json reports project health."""
        result = _run_module(
            "doctor",
            "--project", str(self.project_root),
            "--json",
            cwd=self.workspace
        )
        data = json.loads(result.stdout[result.stdout.index("{"):])
        self.assertIn("success", data)
        self.assertIn("data", data)
        self.assertIn("healthy", data["data"])

    def test_motor_scene_create_and_list(self) -> None:
        """motor scene create and list work end-to-end."""
        # Create scene
        result = _run_module(
            "scene", "create", "Test Level",
            "--project", str(self.project_root),
            "--json",
            cwd=self.workspace
        )
        data = json.loads(result.stdout[result.stdout.index("{"):])
        self.assertTrue(data["success"])

        # List scenes
        result = _run_module(
            "scene", "list",
            "--project", str(self.project_root),
            "--json",
            cwd=self.workspace
        )
        data = json.loads(result.stdout[result.stdout.index("{"):])
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["count"], 1)

    def test_motor_entity_create(self) -> None:
        """motor entity create works."""
        # First create a scene
        _run_module(
            "scene", "create", "EntityTest",
            "--project", str(self.project_root),
            cwd=self.workspace
        )

        # Create entity
        result = _run_module(
            "entity", "create", "Player",
            "--project", str(self.project_root),
            "--json",
            cwd=self.workspace
        )
        data = json.loads(result.stdout[result.stdout.index("{"):])
        self.assertTrue(data["success"])

    def test_motor_json_response_format_consistency(self) -> None:
        """All motor commands return consistent JSON format."""
        commands = [
            (["capabilities"], False),
            (["doctor", "--project", str(self.project_root)], True),
            (["scene", "list", "--project", str(self.project_root)], True),
            (["asset", "list", "--project", str(self.project_root)], True),
        ]

        for cmd_args, needs_project in commands:
            with self.subTest(command=cmd_args[0]):
                args = cmd_args + ["--json"]
                result = _run_module(*args, cwd=self.workspace)
                output = result.stdout
                if "{" in output:
                    output = output[output.index("{"):]
                data = json.loads(output)

                # Contract: must have these fields
                self.assertIn("success", data, f"Command {cmd_args} missing 'success'")
                self.assertIn("message", data, f"Command {cmd_args} missing 'message'")
                self.assertIn("data", data, f"Command {cmd_args} missing 'data'")
                self.assertIsInstance(data["success"], bool)
                self.assertIsInstance(data["message"], str)
                self.assertIsInstance(data["data"], dict)

    def test_motor_agent_provider_login_help_includes_codex_flags(self) -> None:
        """motor agent providers login --help expone flags de login gestionado por Codex."""
        result = _run_module("agent", "providers", "login", "--help", cwd=self.workspace)

        self.assertIn("--codex-chatgpt", result.stdout)
        self.assertIn("--device-auth", result.stdout)

    def test_motor_agent_provider_status_reports_runtime_ready_field(self) -> None:
        """motor agent providers status devuelve metadata extendida de auth."""
        result = _run_module(
            "agent",
            "providers",
            "status",
            "openai",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout[result.stdout.index("{"):])

        self.assertTrue(data["success"])
        self.assertIn("runtime_ready", data["data"])
        self.assertIn("codex_cli_available", data["data"])


class LegacyEngineCliCompatibilityTests(unittest.TestCase):
    """Backward compatibility tests for legacy tools.engine_cli.

    These tests ensure the legacy CLI still works for commands that
    were migrated to `motor`. Commands like 'validate' and 'smoke'
    are legacy only and not part of the official motor interface.
    """

    def test_legacy_cli_shows_deprecation_warning(self) -> None:
        """Legacy: python -m tools.engine_cli muestra warning de deprecación."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.engine_cli", "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        # Should show deprecation warning
        self.assertIn("deprecated", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
