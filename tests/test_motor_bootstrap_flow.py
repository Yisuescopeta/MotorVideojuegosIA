"""
tests/test_motor_bootstrap_flow.py - Tests for motor doctor and bootstrap-ai flow

Validates the official AI bootstrap workflow:
1. motor doctor detects missing AI files
2. motor project bootstrap-ai generates the files
3. motor doctor confirms the files exist

Ensures:
- doctor is read-only (no mutations)
- bootstrap-ai creates the expected files
- All commands use 'motor ...' syntax exclusively
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from motor.cli import run_motor_command


class MotorBootstrapFlowTests(unittest.TestCase):
    """End-to-end tests for doctor -> bootstrap-ai -> doctor flow."""

    def setUp(self) -> None:
        """Set up a clean project for each test."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        
        # Create a minimal valid project
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
        
        # Create required directories
        for dir_name in ["assets", "levels", "scripts", "settings", ".motor"]:
            (self.project_root / dir_name).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def test_doctor_detects_missing_ai_files(self) -> None:
        """Step 1: doctor detects missing motor_ai.json and START_HERE_AI.md."""
        import io
        import sys
        import contextlib
        
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exit_code = run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
        
        output = captured.getvalue()
        data = json.loads(output[output.index("{"):])
        
        # Doctor should report missing files
        self.assertTrue(data["success"])
        self.assertFalse(data["data"]["checks"]["motor_ai_exists"])
        self.assertFalse(data["data"]["checks"]["start_here_exists"])
        
        # Should recommend bootstrap-ai command
        recommendations = data["data"].get("recommendations", [])
        bootstrap_recommendation = [r for r in recommendations if "bootstrap-ai" in r]
        self.assertTrue(
            len(bootstrap_recommendation) > 0,
            "doctor should recommend 'motor project bootstrap-ai'"
        )

    def test_doctor_is_read_only(self) -> None:
        """doctor does not create AI bootstrap files or modify critical project state."""
        # Record initial manifest
        initial_manifest = (self.project_root / "project.json").read_text()
        
        # Run doctor multiple times
        for _ in range(3):
            import io
            import sys
            import contextlib
            
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                run_motor_command([
                    "doctor",
                    "--project", str(self.project_root),
                    "--json"
                ])
        
        # Verify AI bootstrap files were NOT created
        self.assertFalse(
            (self.project_root / "motor_ai.json").exists(),
            "doctor should not create motor_ai.json"
        )
        self.assertFalse(
            (self.project_root / "START_HERE_AI.md").exists(),
            "doctor should not create START_HERE_AI.md"
        )
        
        # Verify manifest unchanged
        final_manifest = (self.project_root / "project.json").read_text()
        self.assertEqual(initial_manifest, final_manifest)

    def test_bootstrap_ai_creates_files(self) -> None:
        """Step 2: bootstrap-ai creates motor_ai.json and START_HERE_AI.md."""
        import io
        import sys
        import contextlib
        
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exit_code = run_motor_command([
                "project", "bootstrap-ai",
                "--project", str(self.project_root),
                "--json"
            ])
        
        # Verify command succeeded
        self.assertEqual(exit_code, 0)
        
        # Verify files created
        motor_ai_path = self.project_root / "motor_ai.json"
        start_here_path = self.project_root / "START_HERE_AI.md"
        
        self.assertTrue(motor_ai_path.exists(), "motor_ai.json should be created")
        self.assertTrue(start_here_path.exists(), "START_HERE_AI.md should be created")
        
        # Verify motor_ai.json is valid
        motor_ai_data = json.loads(motor_ai_path.read_text())
        self.assertIn("schema_version", motor_ai_data)
        self.assertIn("capabilities", motor_ai_data)
        
        # Verify START_HERE_AI.md contains motor commands
        start_here_content = start_here_path.read_text()
        self.assertIn("motor doctor", start_here_content)
        self.assertIn("motor project bootstrap-ai", start_here_content)

    def test_full_bootstrap_flow(self) -> None:
        """Step 3: Complete flow doctor -> bootstrap-ai -> doctor."""
        import io
        import sys
        import contextlib
        
        # Phase 1: Initial doctor (files missing)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
        
        output = captured.getvalue()
        data1 = json.loads(output[output.index("{"):])
        self.assertFalse(data1["data"]["checks"]["motor_ai_exists"])
        
        # Phase 2: Bootstrap AI files
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            run_motor_command([
                "project", "bootstrap-ai",
                "--project", str(self.project_root),
                "--json"
            ])
        
        # Phase 3: Final doctor (files present)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
        
        output = captured.getvalue()
        data3 = json.loads(output[output.index("{"):])
        
        # Verify files now exist
        self.assertTrue(data3["data"]["checks"]["motor_ai_exists"])
        self.assertTrue(data3["data"]["checks"]["start_here_exists"])
        
        # Should have no bootstrap recommendation
        recommendations = data3["data"].get("recommendations", [])
        bootstrap_recommendation = [r for r in recommendations if "bootstrap-ai" in r]
        self.assertEqual(
            len(bootstrap_recommendation), 0,
            "doctor should not recommend bootstrap-ai after files exist"
        )

    def test_bootstrap_ai_is_idempotent(self) -> None:
        """bootstrap-ai can be run multiple times safely."""
        import io
        import sys
        import contextlib
        
        # Run bootstrap-ai twice
        for i in range(2):
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                exit_code = run_motor_command([
                    "project", "bootstrap-ai",
                    "--project", str(self.project_root),
                    "--json"
                ])
            self.assertEqual(exit_code, 0)
        
        # Verify files still exist and are valid
        motor_ai_path = self.project_root / "motor_ai.json"
        start_here_path = self.project_root / "START_HERE_AI.md"
        
        self.assertTrue(motor_ai_path.exists())
        self.assertTrue(start_here_path.exists())
        
        motor_ai_data = json.loads(motor_ai_path.read_text())
        self.assertIn("capabilities", motor_ai_data)


class MotorDoctorReadOnlyTests(unittest.TestCase):
    """Tests ensuring doctor command has no side effects."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temp_dir.name) / "TestGame"
        self.project_root.mkdir(parents=True)
        
        (self.project_root / "project.json").write_text(
            json.dumps({
                "name": "TestGame",
                "version": 2,
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "scripts": "scripts", "settings": "settings",
                    "meta": ".motor/meta", "build": ".motor/build"
                },
            }),
            encoding="utf-8",
        )
        for d in ["assets", "levels", "scripts", "settings", ".motor"]:
            (self.project_root / d).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_doctor_does_not_create_ai_files(self) -> None:
        """doctor never creates AI bootstrap files."""
        import io
        import contextlib
        
        # Run doctor
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
        
        # Verify AI files were NOT created
        self.assertFalse((self.project_root / "motor_ai.json").exists())
        self.assertFalse((self.project_root / "START_HERE_AI.md").exists())

    def test_doctor_does_not_modify_manifest(self) -> None:
        """doctor never modifies project.json."""
        import io
        import contextlib
        
        original_content = (self.project_root / "project.json").read_text()
        original_mtime = (self.project_root / "project.json").stat().st_mtime
        
        # Run doctor
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
        
        # Verify manifest unchanged
        current_content = (self.project_root / "project.json").read_text()
        self.assertEqual(original_content, current_content)


class MotorCommandSyntaxTests(unittest.TestCase):
    """Tests validating motor command syntax in outputs."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temp_dir.name) / "TestGame"
        self.project_root.mkdir(parents=True)
        
        (self.project_root / "project.json").write_text(
            json.dumps({
                "name": "TestGame",
                "version": 2,
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "scripts": "scripts", "settings": "settings",
                    "meta": ".motor/meta", "build": ".motor/build"
                },
            }),
            encoding="utf-8",
        )
        for d in ["assets", "levels", "scripts", "settings", ".motor"]:
            (self.project_root / d).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_doctor_recommends_motor_commands(self) -> None:
        """doctor recommendations use 'motor ...' syntax exclusively."""
        import io
        import contextlib
        
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            run_motor_command([
                "doctor",
                "--project", str(self.project_root),
                "--json"
            ])
        
        output = captured.getvalue()
        data = json.loads(output[output.index("{"):])
        
        recommendations = data["data"].get("recommendations", [])
        for rec in recommendations:
            # Should not contain deprecated syntax
            self.assertNotIn("python -m tools.engine_cli", rec)
            # Should use motor syntax
            if "bootstrap" in rec.lower() or "migrate" in rec.lower():
                self.assertIn("motor project bootstrap-ai", rec)


if __name__ == "__main__":
    unittest.main()