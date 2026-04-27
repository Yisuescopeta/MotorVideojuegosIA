"""
tests/test_doctor_bootstrap_flow.py - Integration tests for doctor + bootstrap-ai workflow

Tests the complete diagnostic and bootstrap workflow:
1. Project without bootstrap files
2. Doctor detects missing files
3. Bootstrap-ai generates them
4. Subsequent doctor run confirms they're present
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DoctorBootstrapFlowTests(unittest.TestCase):
    """Integration tests for the doctor → bootstrap-ai workflow."""

    def setUp(self) -> None:
        self._home_tmp = tempfile.TemporaryDirectory(prefix="motor_doctor_home_")
        self.isolated_home = Path(self._home_tmp.name) / "isolated_home"

    def tearDown(self) -> None:
        self._home_tmp.cleanup()

    def _run_motor(self, *args: str, cwd: Path) -> tuple[int, str, str]:
        """Run motor CLI command and return (returncode, stdout, stderr)."""
        import os
        cmd = [sys.executable, "-m", "motor"] + list(args)

        # Set up environment with project root in PYTHONPATH
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) if not python_path else str(root) + os.pathsep + python_path
        env["MOTORVIDEOJUEGOSIA_HOME"] = self.isolated_home.as_posix()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    def _create_test_project(self, workspace: Path, name: str = "TestProject") -> Path:
        """Create a minimal valid test project without bootstrap files."""
        project_root = workspace / name
        project_root.mkdir()

        # Create project.json
        (project_root / "project.json").write_text(
            json.dumps({
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
            }),
            encoding="utf-8",
        )

        # Create required directories
        for dir_name in ["assets", "levels", "scripts", "settings", "prefabs", ".motor"]:
            (project_root / dir_name).mkdir(parents=True, exist_ok=True)

        return project_root

    def test_doctor_detects_missing_bootstrap_files(self) -> None:
        """Doctor should detect missing motor_ai.json and START_HERE_AI.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Run doctor
            returncode, stdout, stderr = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )

            self.assertEqual(returncode, 0, f"doctor should succeed: {stderr}")

            # Parse output
            output = stdout
            if "{" in output:
                output = output[output.index("{"):]
            result = json.loads(output)

            # Should have warnings about missing files
            checks = result.get("data", {}).get("checks", {})
            self.assertFalse(checks.get("motor_ai_exists", True),
                           "motor_ai.json should not exist initially")
            self.assertFalse(checks.get("start_here_exists", True),
                           "START_HERE_AI.md should not exist initially")

            # Should recommend bootstrap-ai
            recommendations = result.get("data", {}).get("recommendations", [])
            has_bootstrap_recommendation = any(
                "bootstrap-ai" in rec for rec in recommendations
            )
            self.assertTrue(has_bootstrap_recommendation,
                          "Doctor should recommend 'motor project bootstrap-ai'")

    def test_bootstrap_ai_generates_files(self) -> None:
        """Bootstrap-ai should generate motor_ai.json and START_HERE_AI.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Verify files don't exist initially
            self.assertFalse((project / "motor_ai.json").exists())
            self.assertFalse((project / "START_HERE_AI.md").exists())

            # Run bootstrap-ai
            returncode, stdout, stderr = self._run_motor(
                "project", "bootstrap-ai", "--project", str(project), "--json",
                cwd=project
            )

            self.assertEqual(returncode, 0, f"bootstrap-ai should succeed: {stderr}")

            # Parse output
            output = stdout
            if "{" in output:
                output = output[output.index("{"):]
            result = json.loads(output)

            self.assertTrue(result.get("success"), "bootstrap-ai should report success")

            # Verify files were created
            self.assertTrue((project / "motor_ai.json").exists(),
                          "motor_ai.json should be created")
            self.assertTrue((project / "START_HERE_AI.md").exists(),
                          "START_HERE_AI.md should be created")

            # Verify motor_ai.json is valid and portable
            motor_ai = json.loads((project / "motor_ai.json").read_text())
            self.assertEqual(motor_ai.get("project", {}).get("root"), ".",
                           "motor_ai.json should use relative paths")

    def test_doctor_recognizes_bootstrap_after_generation(self) -> None:
        """After bootstrap-ai, doctor should recognize the files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # First doctor run - should detect missing files
            _, stdout1, _ = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )
            output1 = stdout1[stdout1.index("{"):]
            result1 = json.loads(output1)

            initial_warnings = result1.get("data", {}).get("warnings", [])
            has_missing_bootstrap_warning1 = any(
                "motor_ai.json" in w or "START_HERE_AI.md" in w
                for w in initial_warnings
            )
            self.assertTrue(has_missing_bootstrap_warning1,
                          "Initial doctor run should warn about missing bootstrap")

            # Run bootstrap-ai
            self._run_motor(
                "project", "bootstrap-ai", "--project", str(project),
                cwd=project
            )

            # Second doctor run - should recognize files
            _, stdout2, _ = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )
            output2 = stdout2[stdout2.index("{"):]
            result2 = json.loads(output2)

            checks = result2.get("data", {}).get("checks", {})
            self.assertTrue(checks.get("motor_ai_exists", False),
                          "Second doctor run should find motor_ai.json")
            self.assertTrue(checks.get("start_here_exists", False),
                          "Second doctor run should find START_HERE_AI.md")

            # Should not have warnings about missing bootstrap files
            final_warnings = result2.get("data", {}).get("warnings", [])
            has_missing_bootstrap_warning2 = any(
                "motor_ai.json not found" in w or "START_HERE_AI.md not found" in w
                for w in final_warnings
            )
            self.assertFalse(has_missing_bootstrap_warning2,
                           "Doctor should not warn about bootstrap after generation")

    def test_bootstrap_ai_is_idempotent(self) -> None:
        """Running bootstrap-ai twice should succeed both times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # First run
            returncode1, _, _ = self._run_motor(
                "project", "bootstrap-ai", "--project", str(project),
                cwd=project
            )
            self.assertEqual(returncode1, 0, "First bootstrap-ai should succeed")

            # Get first generation timestamp
            motor_ai1 = (project / "motor_ai.json").read_text()

            # Second run
            returncode2, _, _ = self._run_motor(
                "project", "bootstrap-ai", "--project", str(project),
                cwd=project
            )
            self.assertEqual(returncode2, 0, "Second bootstrap-ai should succeed")

            # File should still be valid
            motor_ai2_text = (project / "motor_ai.json").read_text()
            motor_ai2 = json.loads(motor_ai2_text)
            self.assertIn("implemented_capabilities", motor_ai2)
            self.assertEqual(motor_ai1, motor_ai2_text)

    def test_doctor_is_read_only(self) -> None:
        """Doctor should not modify project files or create editor state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Get initial state of critical project files
            initial_project_json = (project / "project.json").read_text()

            # Run doctor multiple times
            for _ in range(3):
                returncode, _, _ = self._run_motor(
                    "doctor", "--project", str(project),
                    cwd=project
                )
                self.assertEqual(returncode, 0)

            # Verify project.json was not modified
            final_project_json = (project / "project.json").read_text()
            self.assertEqual(initial_project_json, final_project_json,
                           "Doctor should not modify project.json")
            self.assertFalse((project / ".motor" / "editor_state.json").exists(),
                           "Doctor should not create .motor/editor_state.json")
            self.assertFalse((project / "settings" / "project_settings.json").exists(),
                           "Doctor should not create settings/project_settings.json")

            # Verify motor_ai.json and START_HERE_AI.md were not created by doctor
            self.assertFalse((project / "motor_ai.json").exists(),
                           "Doctor should not create motor_ai.json")
            self.assertFalse((project / "START_HERE_AI.md").exists(),
                           "Doctor should not create START_HERE_AI.md")
            self.assertFalse(
                self.isolated_home.exists(),
                "Doctor should not create isolated MOTORVIDEOJUEGOSIA_HOME artifacts"
            )

    def test_bootstrap_ai_fails_without_project(self) -> None:
        """Bootstrap-ai should fail gracefully when run outside a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()

            returncode, stdout, _ = self._run_motor(
                "project", "bootstrap-ai", "--project", str(empty_dir), "--json",
                cwd=empty_dir
            )

            self.assertNotEqual(returncode, 0,
                              "bootstrap-ai should fail without project.json")

            # Parse output
            if "{" in stdout:
                output = stdout[stdout.index("{"):]
                result = json.loads(output)
                self.assertFalse(result.get("success"),
                               "bootstrap-ai should report failure")

    def test_doctor_reads_v3_schema_correctly(self) -> None:
        """Doctor should correctly read motor_ai.json v3 schema with implemented/planned split."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Generate bootstrap files (creates v3 schema)
            returncode, _, _ = self._run_motor(
                "project", "bootstrap-ai", "--project", str(project),
                cwd=project
            )
            self.assertEqual(returncode, 0, "bootstrap-ai should succeed")

            # Verify motor_ai.json has v3 structure
            motor_ai_path = project / "motor_ai.json"
            motor_ai_data = json.loads(motor_ai_path.read_text())

            self.assertEqual(motor_ai_data.get("schema_version"), 3,
                           "motor_ai.json should be schema v3")
            self.assertIn("implemented_capabilities", motor_ai_data,
                        "v3 schema should have implemented_capabilities")
            self.assertIn("planned_capabilities", motor_ai_data,
                        "v3 schema should have planned_capabilities")
            self.assertIn("capability_counts", motor_ai_data,
                        "v3 schema should have capability_counts")

            # Run doctor - should read v3 correctly
            returncode, stdout, _ = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )
            self.assertEqual(returncode, 0, "doctor should succeed with v3 schema")

            # Parse doctor output
            output = stdout
            if "{" in output:
                output = output[output.index("{"):]
            result = json.loads(output)

            checks = result.get("data", {}).get("checks", {})

            # Doctor should correctly read v3 fields
            self.assertEqual(checks.get("motor_ai_schema_version"), 3,
                           "Doctor should detect schema v3")
            self.assertIn("motor_ai_implemented_count", checks,
                        "Doctor should report implemented capabilities count")
            self.assertIn("motor_ai_planned_count", checks,
                        "Doctor should report planned capabilities count")
            self.assertIn("motor_ai_capabilities_count", checks,
                        "Doctor should report total capabilities count")

            # Counts should match what was generated
            self.assertGreater(checks.get("motor_ai_implemented_count", 0), 0,
                             "Should have implemented capabilities")
            self.assertGreater(checks.get("motor_ai_planned_count", 0), 0,
                             "Should have planned capabilities")
            self.assertGreater(checks.get("motor_ai_capabilities_count", 0), 0,
                             "Should have total capabilities count")

            # Verify consistency with actual data
            expected_implemented = len(motor_ai_data.get("implemented_capabilities", []))
            expected_planned = len(motor_ai_data.get("planned_capabilities", []))
            self.assertEqual(checks.get("motor_ai_implemented_count"), expected_implemented,
                           "Doctor implemented count should match file")
            self.assertEqual(checks.get("motor_ai_planned_count"), expected_planned,
                           "Doctor planned count should match file")


    def test_doctor_reads_legacy_v1_schema(self) -> None:
        """Doctor should gracefully handle legacy v1 schema (capabilities.capabilities)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Manually write a legacy v1 schema motor_ai.json
            legacy_schema = {
                "schema_version": 1,
                "engine": {
                    "name": "MotorVideojuegosIA",
                    "version": "2026.03",
                    "api_version": "1",
                },
                "capabilities": {
                    "capabilities": [
                        {"id": "scene:create", "summary": "Create a scene"},
                        {"id": "entity:create", "summary": "Create an entity"},
                    ]
                },
            }
            (project / "motor_ai.json").write_text(
                json.dumps(legacy_schema), encoding="utf-8"
            )
            (project / "START_HERE_AI.md").write_text("# Test\n", encoding="utf-8")

            # Run doctor
            returncode, stdout, _ = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )
            self.assertEqual(returncode, 0, "Doctor should succeed with legacy schema")

            # Parse output
            output = stdout
            if "{" in output:
                output = output[output.index("{"):]
            result = json.loads(output)

            checks = result.get("data", {}).get("checks", {})

            # Doctor should correctly identify legacy schema
            self.assertEqual(checks.get("motor_ai_schema_version"), 1,
                           "Doctor should detect schema v1")
            self.assertEqual(checks.get("motor_ai_capabilities_count"), 2,
                           "Doctor should count legacy capabilities correctly")
            self.assertEqual(checks.get("motor_ai_implemented_count"), 2,
                           "Legacy schema: all capabilities count as implemented")
            self.assertEqual(checks.get("motor_ai_planned_count"), 0,
                           "Legacy schema: no planned capabilities")

    def test_doctor_reads_legacy_v2_schema(self) -> None:
        """Doctor should gracefully handle legacy v2 schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Manually write a legacy v2 schema motor_ai.json
            legacy_schema = {
                "schema_version": 2,
                "engine": {
                    "name": "MotorVideojuegosIA",
                    "version": "2026.03",
                    "api_version": "1",
                },
                "capabilities": {
                    "capabilities": [
                        {"id": "scene:list", "summary": "List scenes"},
                        {"id": "entity:create", "summary": "Create entity"},
                        {"id": "asset:list", "summary": "List assets"},
                    ]
                },
            }
            (project / "motor_ai.json").write_text(
                json.dumps(legacy_schema), encoding="utf-8"
            )
            (project / "START_HERE_AI.md").write_text("# Test\n", encoding="utf-8")

            # Run doctor
            returncode, stdout, _ = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )
            self.assertEqual(returncode, 0, "Doctor should succeed with legacy v2 schema")

            output = stdout
            if "{" in output:
                output = output[output.index("{"):]
            result = json.loads(output)

            checks = result.get("data", {}).get("checks", {})

            self.assertEqual(checks.get("motor_ai_schema_version"), 2,
                           "Doctor should detect schema v2")
            self.assertEqual(checks.get("motor_ai_capabilities_count"), 3,
                           "Doctor should count v2 capabilities correctly")
            self.assertEqual(checks.get("motor_ai_implemented_count"), 3,
                           "Legacy v2: all capabilities count as implemented")
            self.assertEqual(checks.get("motor_ai_planned_count"), 0,
                           "Legacy v2: no planned capabilities")

    def test_doctor_warns_on_v3_missing_counts(self) -> None:
        """Doctor should warn if v3 schema is missing capability_counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Write a malformed v3 schema (has implemented/planned but no counts)
            malformed_v3 = {
                "schema_version": 3,
                "engine": {
                    "name": "MotorVideojuegosIA",
                    "version": "2026.03",
                    "api_version": "1",
                },
                "implemented_capabilities": [
                    {"id": "scene:create", "summary": "Create scene"},
                ],
                "planned_capabilities": [
                    {"id": "entity:delete", "summary": "Delete entity"},
                ],
                # NOTE: missing "capability_counts"
            }
            (project / "motor_ai.json").write_text(
                json.dumps(malformed_v3), encoding="utf-8"
            )
            (project / "START_HERE_AI.md").write_text("# Test\n", encoding="utf-8")

            returncode, stdout, _ = self._run_motor(
                "doctor", "--project", str(project), "--json",
                cwd=project
            )
            self.assertEqual(returncode, 0)

            output = stdout
            if "{" in output:
                output = output[output.index("{"):]
            result = json.loads(output)

            # Doctor should warn about missing capability_counts
            warnings = result.get("data", {}).get("warnings", [])
            has_count_warning = any(
                "capability_counts" in w for w in warnings
            )
            self.assertTrue(has_count_warning,
                          "Doctor should warn when v3 schema is missing capability_counts")

            # But counts should still be computed from the lists
            checks = result.get("data", {}).get("checks", {})
            self.assertEqual(checks.get("motor_ai_capabilities_count"), 2,
                           "Doctor should compute total from lists when counts missing")


if __name__ == "__main__":
    unittest.main()
