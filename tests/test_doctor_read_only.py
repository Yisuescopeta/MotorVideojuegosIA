"""
tests/test_doctor_read_only.py - Tests verifying motor doctor is strictly read-only

Ensures that motor doctor:
- Does not create directories
- Does not write motor_ai.json
- Does not write START_HERE_AI.md
- Does not register recent projects
- Does not modify any files
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DoctorReadOnlyTests(unittest.TestCase):
    """Tests ensuring motor doctor is strictly read-only."""

    def setUp(self):
        """Set up test environment."""
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    def _get_project_state(self, project_path: Path) -> dict:
        """Capture the complete state of a project directory."""
        state = {
            "files": {},
            "dirs": set(),
            "file_count": 0,
        }
        
        if project_path.exists():
            for path in project_path.rglob("*"):
                relative = path.relative_to(project_path)
                if path.is_file():
                    stat = path.stat()
                    state["files"][str(relative)] = {
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                    state["file_count"] += 1
                elif path.is_dir():
                    state["dirs"].add(str(relative))
        
        return state

    def test_doctor_does_not_create_directories(self) -> None:
        """CRITICAL: motor doctor must not create any directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create minimal project structure (only project.json)
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Record state before doctor
            state_before = self._get_project_state(project)
            
            # Run doctor
            result = subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=self.env,
            )
            
            self.assertEqual(result.returncode, 0, "doctor should succeed")
            
            # Record state after doctor
            state_after = self._get_project_state(project)
            
            # Verify no new directories were created
            new_dirs = state_after["dirs"] - state_before["dirs"]
            self.assertEqual(
                len(new_dirs), 0,
                f"doctor created new directories: {new_dirs}"
            )

    def test_doctor_does_not_create_motor_ai_json(self) -> None:
        """CRITICAL: motor doctor must not create motor_ai.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create minimal project WITHOUT motor_ai.json
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Verify motor_ai.json does not exist
            motor_ai_path = project / "motor_ai.json"
            self.assertFalse(motor_ai_path.exists(), "motor_ai.json should not exist initially")
            
            # Run doctor
            result = subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=self.env,
            )
            
            self.assertEqual(result.returncode, 0, "doctor should succeed")
            
            # Verify motor_ai.json was NOT created
            self.assertFalse(
                motor_ai_path.exists(),
                "doctor must NOT create motor_ai.json - it should only diagnose"
            )

    def test_doctor_does_not_create_start_here_md(self) -> None:
        """CRITICAL: motor doctor must not create START_HERE_AI.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create minimal project WITHOUT START_HERE_AI.md
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Verify START_HERE_AI.md does not exist
            start_here_path = project / "START_HERE_AI.md"
            self.assertFalse(start_here_path.exists(), "START_HERE_AI.md should not exist initially")
            
            # Run doctor
            result = subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=self.env,
            )
            
            self.assertEqual(result.returncode, 0, "doctor should succeed")
            
            # Verify START_HERE_AI.md was NOT created
            self.assertFalse(
                start_here_path.exists(),
                "doctor must NOT create START_HERE_AI.md - it should only diagnose"
            )

    def test_doctor_does_not_create_global_storage(self) -> None:
        """CRITICAL: motor doctor must not create global storage directory.
        
        Uses an isolated MOTORVIDEOJUEGOSIA_HOME so the test is fully deterministic
        and does not depend on the real home directory or prior state.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project = workspace / "TestProject"
            project.mkdir()
            
            # Isolated global storage directory
            isolated_home = workspace / "isolated_home"
            
            # Create minimal project
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Check for global storage in isolated directory
            global_dir = isolated_home / ".motorvideojuegosia"
            recents_file = global_dir / "recent_projects.json"
            
            # Build env with isolated MOTORVIDEOJUEGOSIA_HOME
            test_env = self.env.copy()
            test_env["MOTORVIDEOJUEGOSIA_HOME"] = isolated_home.as_posix()
            
            # Run doctor
            result = subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=test_env,
            )
            
            self.assertEqual(result.returncode, 0, "doctor should succeed")
            
            # Verify no global storage was created in isolated home
            self.assertFalse(
                global_dir.exists(),
                f"doctor must NOT create global storage directory in isolated MOTORVIDEOJUEGOSIA_HOME "
                f"({isolated_home}). Global dir path checked: {global_dir}"
            )
            self.assertFalse(
                recents_file.exists(),
                "doctor must NOT create recent_projects.json in isolated global storage"
            )

    def test_doctor_does_not_modify_existing_files(self) -> None:
        """CRITICAL: motor doctor must not modify any existing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create minimal project
            project_json = project / "project.json"
            project_json.write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Record file state before doctor
            stat_before = project_json.stat()
            content_before = project_json.read_text()
            
            # Run doctor multiple times
            for _ in range(3):
                result = subprocess.run(
                    [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                    capture_output=True,
                    text=True,
                    env=self.env,
                )
                self.assertEqual(result.returncode, 0, "doctor should succeed")
            
            # Verify file was not modified
            stat_after = project_json.stat()
            content_after = project_json.read_text()
            
            self.assertEqual(
                content_before, content_after,
                "doctor must not modify project.json content"
            )
            self.assertEqual(
                stat_before.st_mtime, stat_after.st_mtime,
                "doctor must not modify project.json timestamp"
            )
            self.assertFalse((project / ".motor" / "editor_state.json").exists(),
                           "doctor must not create .motor/editor_state.json")
            self.assertFalse((project / "settings" / "project_settings.json").exists(),
                           "doctor must not create settings/project_settings.json")

    def test_doctor_reports_missing_bootstrap_correctly(self) -> None:
        """doctor should report missing bootstrap without creating it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create directories (simulating an existing project)
            for d in ["assets", "levels", "scripts", "settings"]:
                (project / d).mkdir(parents=True, exist_ok=True)
            
            # Create project.json
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Run doctor
            result = subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=self.env,
            )
            
            self.assertEqual(result.returncode, 0, "doctor should succeed")
            
            # Parse output
            output = result.stdout
            if "{" in output:
                output = output[output.index("{"):]
            data = json.loads(output)
            
            # Should report missing bootstrap
            checks = data.get("data", {}).get("checks", {})
            self.assertFalse(checks.get("motor_ai_exists", True), "should report motor_ai missing")
            self.assertFalse(checks.get("start_here_exists", True), "should report START_HERE missing")
            
            # Should recommend bootstrap-ai (not create it)
            recommendations = data.get("data", {}).get("recommendations", [])
            has_bootstrap_rec = any("bootstrap-ai" in rec for rec in recommendations)
            self.assertTrue(has_bootstrap_rec, "should recommend bootstrap-ai command")
            
            # Verify files were NOT created
            self.assertFalse((project / "motor_ai.json").exists(), "must not create motor_ai.json")
            self.assertFalse((project / "START_HERE_AI.md").exists(), "must not create START_HERE_AI.md")

    def test_doctor_multiple_runs_idempotent(self) -> None:
        """Running doctor multiple times should have same effect as running once (no side effects)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create project
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            # Run doctor once and capture state
            subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=self.env,
            )
            state_after_1 = self._get_project_state(project)
            
            # Run doctor 5 more times
            for _ in range(5):
                subprocess.run(
                    [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                    capture_output=True,
                    text=True,
                    env=self.env,
                )
            state_after_6 = self._get_project_state(project)
            
            # States should be identical
            self.assertEqual(
                state_after_1["file_count"], state_after_6["file_count"],
                "Multiple doctor runs should not create files"
            )
            self.assertEqual(
                state_after_1["dirs"], state_after_6["dirs"],
                "Multiple doctor runs should not create directories"
            )


if __name__ == "__main__":
    unittest.main()
