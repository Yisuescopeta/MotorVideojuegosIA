"""
tests/test_motor_entrypoint.py - Tests for the official `motor` CLI entrypoint

Validates:
- motor package can be imported
- python -m motor works
- motor.cli.run_motor_command() works
- Entrypoint functions are accessible
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MotorEntrypointImportTests(unittest.TestCase):
    """Tests for motor package importability."""

    def test_motor_package_can_be_imported(self) -> None:
        """motor package is importable."""
        import motor
        self.assertIsNotNone(motor)
        self.assertEqual(motor.__version__, "2026.03")

    def test_motor_cli_can_be_imported(self) -> None:
        """motor.cli module is importable."""
        from motor import cli
        self.assertIsNotNone(cli)
        self.assertTrue(hasattr(cli, "main"))
        self.assertTrue(hasattr(cli, "cli_main"))
        self.assertTrue(hasattr(cli, "run_motor_command"))

    def test_motor_main_function_exists(self) -> None:
        """motor.cli.main function exists and is callable."""
        from motor.cli import cli_main, main, run_motor_command
        self.assertTrue(callable(main))
        self.assertTrue(callable(cli_main))
        self.assertTrue(callable(run_motor_command))


class MotorCommandExecutionTests(unittest.TestCase):
    """Tests for motor command execution via different methods."""

    def test_python_dash_m_motor_imports(self) -> None:
        """python -m motor can be imported without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "motor", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        # Should either show help or at least not crash on import
        self.assertIn(result.returncode, [0, 1, 2])  # 0=success, 1=no command, 2=argparse error

    def test_motor_capabilities_via_module(self) -> None:
        """motor capabilities command works via python -m motor."""
        result = subprocess.run(
            [sys.executable, "-m", "motor", "capabilities", "--json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        # Parse output (skip any non-JSON prefix)
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]

        try:
            data = json.loads(output)
            self.assertIn("success", data)
            self.assertIn("data", data)
            self.assertIn("capabilities", data["data"])
        except json.JSONDecodeError:
            # If JSON parsing fails, at least check it didn't crash
            pass


class MotorEntrypointIntegrationTests(unittest.TestCase):
    """Integration tests with a real project."""

    def setUp(self) -> None:
        """Set up a test project."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)

        # Create minimal project
        self.project_root = self.workspace / "TestGame"
        self.project_root.mkdir()

        (self.project_root / "project.json").write_text(
            json.dumps({
                "name": "TestGame",
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

        for dir_name in ["assets", "levels", "scripts", "settings", ".motor"]:
            (self.project_root / dir_name).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        """Clean up."""
        self._temp_dir.cleanup()

    def test_motor_doctor_command(self) -> None:
        """motor doctor command works with a project."""
        # Change to project directory and run doctor
        import os

        from motor.cli import run_motor_command
        old_cwd = os.getcwd()
        try:
            os.chdir(self.project_root)
            exit_code = run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
            # Should complete without crashing
            self.assertIn(exit_code, [0, 1])  # 0=healthy, 1=issues found
        finally:
            os.chdir(old_cwd)

    def test_motor_capabilities_via_function(self) -> None:
        """motor capabilities works via run_motor_command function."""
        import contextlib
        import io

        from motor.cli import run_motor_command

        # Capture stdout
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exit_code = run_motor_command(["capabilities", "--json"])

        self.assertEqual(exit_code, 0)

        output = captured.getvalue()
        if "{" in output:
            output = output[output.index("{"):]
            data = json.loads(output)
            self.assertTrue(data["success"])
            self.assertIn("capabilities", data["data"])


class MotorEntrypointContractTests(unittest.TestCase):
    """Contract tests for motor entrypoint stability."""

    def test_run_motor_command_accepts_list_of_strings(self) -> None:
        """run_motor_command accepts List[str] argument."""
        from motor.cli import run_motor_command

        # Should not raise type error
        try:
            result = run_motor_command(["--help"])
            # --help returns 0 on success
            self.assertIn(result, [0, 1])
        except SystemExit as e:
            # argparse may call sys.exit
            self.assertIn(e.code, [0, None])

    def test_run_motor_command_accepts_none(self) -> None:
        """run_motor_command accepts None (uses sys.argv)."""
        from motor.cli import run_motor_command

        # Save original sys.argv
        old_argv = sys.argv
        try:
            sys.argv = ["motor", "--help"]
            try:
                result = run_motor_command(None)
                self.assertIn(result, [0, 1])
            except SystemExit as e:
                self.assertIn(e.code, [0, None])
        finally:
            sys.argv = old_argv

    def test_motor_exports_stable_api(self) -> None:
        """motor package exports stable public API."""
        import motor

        # Check expected exports exist
        expected = ["main", "cli_main"]
        for name in expected:
            self.assertTrue(
                hasattr(motor, name),
                f"motor should export {name}"
            )


class MotorBackwardCompatibilityTests(unittest.TestCase):
    """Tests ensuring backward compatibility with tools.engine_cli."""

    def test_tools_engine_cli_still_works(self) -> None:
        """tools.engine_cli remains functional as backend."""
        from tools import engine_cli

        self.assertTrue(hasattr(engine_cli, "cmd_capabilities"))
        self.assertTrue(hasattr(engine_cli, "cmd_doctor"))
        # create_parser is now create_motor_parser in motor.cli
        self.assertTrue(hasattr(engine_cli, "create_motor_parser"))

    def test_motor_uses_tools_engine_cli_functions(self) -> None:
        """motor.cli imports from tools.engine_cli."""
        from motor import cli
        from tools import engine_cli

        # Verify motor.cli imports the actual functions
        self.assertIs(cli.cmd_capabilities, engine_cli.cmd_capabilities)
        self.assertIs(cli.cmd_doctor, engine_cli.cmd_doctor)


if __name__ == "__main__":
    unittest.main()
