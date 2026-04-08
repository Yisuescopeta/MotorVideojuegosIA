"""
tests/test_ai_facing_e2e.py - End-to-end tests for AI-facing system

Simulates the workflow of an AI assistant without context:
1. Open project folder
2. Detect engine
3. Query capabilities
4. Execute useful headless commands
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


class AIFacingEndToEndTests(unittest.TestCase):
    """End-to-end tests simulating AI assistant workflow."""

    def setUp(self) -> None:
        """Set up a clean project for each test."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        
        # Create a minimal valid project
        self.project_root = self.workspace / "TestGame"
        self.project_root.mkdir()
        
        # Create project.json
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
        
        # Create a simple scene
        (self.project_root / "levels" / "main_scene.json").write_text(
            json.dumps({
                "name": "Main Scene",
                "entities": [],
                "rules": [],
            }),
            encoding="utf-8",
        )
        
        # Create motor_ai.json (AI bootstrap)
        (self.project_root / "motor_ai.json").write_text(
            json.dumps({
                "schema_version": 2,
                "engine": {
                    "name": "MotorVideojuegosIA",
                    "version": "2026.03",
                    "api_version": "1",
                    "capabilities_schema_version": 1,
                },
                "project": {
                    "name": "TestGame",
                    "root": str(self.project_root),
                },
                "entrypoints": {
                    "manifest": str(self.project_root / "project.json"),
                    "settings": str(self.project_root / "settings" / "project_settings.json"),
                },
                "capabilities": {
                    "schema_version": 1,
                    "engine": {"name": "MotorVideojuegosIA", "version": "2026.03"},
                    "capabilities": [
                        {"id": "scene:create", "summary": "Create scene"},
                        {"id": "entity:create", "summary": "Create entity"},
                    ],
                },
            }),
            encoding="utf-8",
        )
        
        # Create START_HERE_AI.md
        (self.project_root / "START_HERE_AI.md").write_text(
            "# TestGame - AI Quick Start\n\nThis is a test project.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def _run_motor(self, *args: str) -> dict:
        """Execute motor CLI command and return parsed JSON response."""
        import os
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) if not python_path else str(root) + os.pathsep + python_path
        
        # Commands that don't need --project
        no_project_commands = ["capabilities"]
        
        cmd = [sys.executable, "-m", "motor"] + list(args) + ["--json"]
        if args[0] not in no_project_commands:
            cmd.extend(["--project", str(self.project_root)])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            env=env,
        )
        # Parse JSON output (skip any leading non-JSON lines)
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"success": False, "message": f"Invalid JSON: {output[:200]}", "data": {}}

    def test_step_1_ai_opens_project_folder(self) -> None:
        """Step 1: AI opens project folder and finds motor_ai.json."""
        motor_ai_path = self.project_root / "motor_ai.json"
        start_here_path = self.project_root / "START_HERE_AI.md"
        
        self.assertTrue(motor_ai_path.exists(), "motor_ai.json should exist")
        self.assertTrue(start_here_path.exists(), "START_HERE_AI.md should exist")
        
        # Verify motor_ai.json is valid
        data = json.loads(motor_ai_path.read_text())
        self.assertIn("schema_version", data)
        self.assertIn("capabilities", data)
        self.assertIn("entrypoints", data)

    def test_step_2_ai_runs_doctor(self) -> None:
        """Step 2: AI runs doctor to validate project health."""
        result = self._run_motor("doctor")
        
        self.assertIn("success", result)
        self.assertIn("data", result)
        
        data = result["data"]
        self.assertIn("healthy", data)
        self.assertIn("status", data)
        self.assertIn("checks", data)
        
        # Verify critical checks passed
        checks = data["checks"]
        self.assertTrue(checks.get("project_manifest_exists"))
        self.assertTrue(checks.get("project_manifest_valid"))
        self.assertTrue(checks.get("motor_ai_exists"))
        self.assertTrue(checks.get("motor_ai_valid"))
        self.assertTrue(checks.get("start_here_exists"))

    def test_step_3_ai_queries_capabilities(self) -> None:
        """Step 3: AI queries engine capabilities."""
        result = self._run_motor("capabilities")
        
        self.assertTrue(result.get("success"), "Capabilities query should succeed")
        
        data = result["data"]
        self.assertIn("count", data)
        self.assertIn("capabilities", data)
        self.assertIn("engine_version", data)
        
        # Should have multiple capabilities
        self.assertGreater(data["count"], 0, "Should have at least one capability")
        self.assertIsInstance(data["capabilities"], list)

    def test_step_4_ai_lists_scenes(self) -> None:
        """Step 4: AI lists available scenes."""
        result = self._run_motor("scene", "list")
        
        self.assertTrue(result.get("success"), "Scene list should succeed")
        
        data = result["data"]
        self.assertIn("count", data)
        self.assertIn("scenes", data)
        
        # Should find the main_scene we created
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["scenes"][0]["name"], "Main Scene")

    def test_step_5_ai_creates_scene_headless(self) -> None:
        """Step 5: AI creates a new scene headlessly."""
        result = self._run_motor("scene", "create", "AI Test Level")
        
        self.assertTrue(result.get("success"), "Scene creation should succeed")
        
        data = result["data"]
        self.assertIn("path", data)
        
        # Verify scene file was created
        scene_path = self.project_root / "levels" / "ai_test_level.json"
        self.assertTrue(scene_path.exists(), "Scene file should be created")

    def test_step_6_ai_creates_entity(self) -> None:
        """Step 6: AI creates an entity in the active scene."""
        # First create a scene
        self._run_motor("scene", "create", "EntityTest")
        
        # Create entity
        result = self._run_motor("entity", "create", "AIPlayer")
        
        self.assertTrue(result.get("success"), "Entity creation should succeed")
        
        data = result["data"]
        self.assertIn("entity", data)
        self.assertEqual(data["entity"], "AIPlayer")

    def test_step_7_ai_adds_component(self) -> None:
        """Step 7: AI adds a component to an entity."""
        # Setup
        self._run_motor("scene", "create", "ComponentTest")
        self._run_motor("entity", "create", "Player")
        
        # Add component
        result = self._run_motor(
            "component", "add", "Player", "Transform",
            "--data", '{"x":100,"y":200}'
        )
        
        self.assertTrue(result.get("success"), "Component add should succeed")

    def test_full_ai_workflow(self) -> None:
        """Complete AI workflow: detect → validate → query → create → configure."""
        # 1. Detect motor project
        self.assertTrue((self.project_root / "motor_ai.json").exists())
        
        # 2. Validate with doctor
        doctor_result = self._run_motor("doctor")
        self.assertTrue(doctor_result["data"]["healthy"])
        
        # 3. Query capabilities
        caps_result = self._run_motor("capabilities")
        self.assertTrue(caps_result["success"])
        self.assertGreater(caps_result["data"]["count"], 0)
        
        # 4. Create scene
        scene_result = self._run_motor("scene", "create", "AIWorkflow")
        self.assertTrue(scene_result["success"])
        
        # 5. Create entity
        entity_result = self._run_motor("entity", "create", "Hero")
        self.assertTrue(entity_result["success"])
        
        # 6. Add components
        transform_result = self._run_motor(
            "component", "add", "Hero", "Transform",
            "--data", '{"x":50,"y":100}'
        )
        self.assertTrue(transform_result["success"])

    def test_doctor_reports_invalid_project(self) -> None:
        """Doctor correctly reports issues in invalid project."""
        # Create invalid project (missing required fields)
        bad_project = self.workspace / "BadProject"
        bad_project.mkdir()
        (bad_project / "project.json").write_text(
            json.dumps({"name": "Bad"}),  # Missing version and paths
            encoding="utf-8",
        )
        
        cmd = [
            sys.executable, "-m", "motor",
            "doctor",
            "--project", str(bad_project),
            "--json"
        ]
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        data = json.loads(output)
        
        # Should report warnings for missing fields (but still healthy)
        self.assertIn("warnings", data["data"])
        self.assertTrue(len(data["data"]["warnings"]) > 0, "Should have warnings for missing fields")
        
        # Should have specific checks
        checks = data["data"]["checks"]
        self.assertTrue(checks.get("project_manifest_exists"))
        # But motor_ai.json won't exist
        self.assertFalse(checks.get("motor_ai_exists", True))


class AIFacingContractTests(unittest.TestCase):
    """Contract tests for AI-facing API stability."""

    def test_cli_response_format(self) -> None:
        """All CLI responses must have consistent format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            (project / "project.json").write_text(
                json.dumps({
                    "name": "Test",
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
                (project / d).mkdir(parents=True, exist_ok=True)
            
            # Test multiple commands
            commands = [
                (["capabilities"], False),  # No project needed
                (["doctor"], True),
                (["scene", "list"], True),
                (["asset", "list"], True),
            ]
            
            for cmd_args, needs_project in commands:
                cmd = [sys.executable, "-m", "motor"] + cmd_args + ["--json"]
                if needs_project:
                    cmd.extend(["--project", str(project)])
                env = os.environ.copy()
                python_path = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                output = result.stdout
                if "{" in output:
                    output = output[output.index("{"):]
                try:
                    data = json.loads(output)
                except json.JSONDecodeError:
                    self.fail(f"Command {cmd_args} returned invalid JSON: {output[:200]}")
                
                # Contract: must have these fields
                self.assertIn("success", data, f"Command {cmd_args} missing 'success'")
                self.assertIn("message", data, f"Command {cmd_args} missing 'message'")
                self.assertIn("data", data, f"Command {cmd_args} missing 'data'")
                self.assertIsInstance(data["success"], bool)
                self.assertIsInstance(data["message"], str)
                self.assertIsInstance(data["data"], dict)

    def test_motor_ai_json_schema(self) -> None:
        """motor_ai.json must follow expected schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            
            # Create minimal valid motor_ai.json
            motor_ai = {
                "schema_version": 2,
                "engine": {
                    "name": "MotorVideojuegosIA",
                    "version": "2026.03",
                    "api_version": "1",
                },
                "project": {
                    "name": "Test",
                    "root": str(project),
                },
                "entrypoints": {
                    "manifest": str(project / "project.json"),
                },
                "capabilities": {
                    "schema_version": 1,
                    "capabilities": [],
                },
            }
            (project / "motor_ai.json").write_text(json.dumps(motor_ai), encoding="utf-8")
            
            # Verify schema
            data = json.loads((project / "motor_ai.json").read_text())
            self.assertEqual(data["schema_version"], 2)
            self.assertIn("engine", data)
            self.assertIn("project", data)
            self.assertIn("entrypoints", data)
            self.assertIn("capabilities", data)


if __name__ == "__main__":
    unittest.main()