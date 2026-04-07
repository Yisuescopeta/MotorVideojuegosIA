"""
tests/test_bootstrap_portability.py - Tests for portable motor_ai.json generation

Verifies that generated AI bootstrap files are:
1. Portable (no absolute paths)
2. Commit-friendly (no machine-specific data)
3. Complete enough for AI discovery
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.ai import get_default_registry, MotorAIBootstrapBuilder
from engine.project.project_service import ProjectService, ProjectManifest


class BootstrapPortabilityTests(unittest.TestCase):
    """Tests ensuring motor_ai.json is portable and commit-friendly."""
    
    def _create_test_project(self, workspace: Path, name: str = "TestProject") -> tuple[Path, ProjectManifest]:
        """Create a minimal test project with manifest."""
        project_root = workspace / name
        project_root.mkdir()
        
        # Create project.json
        manifest_data = {
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
        (project_root / "project.json").write_text(
            json.dumps(manifest_data), encoding="utf-8"
        )
        
        # Create directories
        for d in ["assets", "levels", "scripts", "settings", "prefabs", ".motor"]:
            (project_root / d).mkdir(parents=True, exist_ok=True)
        
        manifest = ProjectManifest.from_dict(manifest_data)
        return project_root, manifest
    
    def _has_absolute_paths(self, data: dict | str) -> list[str]:
        """Recursively check for absolute paths in data."""
        violations = []
        
        if isinstance(data, str):
            # Check for Windows absolute paths (C:\, D:\, etc.)
            if len(data) >= 2 and data[1] == ":" and data[0].isalpha():
                violations.append(data)
            # Check for Unix absolute paths (/home/, /Users/, etc.)
            elif data.startswith("/home/") or data.startswith("/Users/") or data.startswith("/root/"):
                violations.append(data)
            # Check for network paths
            elif data.startswith("\\\\"):
                violations.append(data)
        elif isinstance(data, dict):
            for key, value in data.items():
                violations.extend(self._has_absolute_paths(value))
        elif isinstance(data, list):
            for item in data:
                violations.extend(self._has_absolute_paths(item))
        
        return violations
    
    def test_motor_ai_json_has_no_absolute_paths(self) -> None:
        """Generated motor_ai.json must not contain absolute paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))
            
            service = ProjectService(project_root, auto_ensure=False)
            result = service.generate_ai_bootstrap(project_root, manifest)
            
            # Check for absolute paths anywhere in the result
            violations = self._has_absolute_paths(result)
            
            if violations:
                self.fail(
                    f"motor_ai.json contains absolute paths:\n" +
                    "\n".join(f"  - {v}" for v in violations) +
                    f"\n\nFull result:\n{json.dumps(result, indent=2)}"
                )
    
    def test_motor_ai_json_project_root_is_relative(self) -> None:
        """Project root must be relative (typically '.')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))
            
            service = ProjectService(project_root, auto_ensure=False)
            result = service.generate_ai_bootstrap(project_root, manifest)
            
            project_info = result.get("project", {})
            root_path = project_info.get("root", "")
            
            # Root should be "." or relative path, never absolute
            self.assertNotIn(":", root_path, "project.root must not be absolute Windows path")
            self.assertFalse(
                root_path.startswith("/") and not root_path.startswith("./"),
                f"project.root must be relative, got: {root_path}"
            )
    
    def test_motor_ai_json_entrypoints_are_relative(self) -> None:
        """All entrypoint paths must be relative to project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))
            
            service = ProjectService(project_root, auto_ensure=False)
            result = service.generate_ai_bootstrap(project_root, manifest)
            
            entrypoints = result.get("entrypoints", {})
            
            for key, path in entrypoints.items():
                with self.subTest(entrypoint=key):
                    # Check for Windows absolute paths
                    self.assertNotIn(":", str(path), f"entrypoints.{key} must not be absolute")
                    # Check for Unix absolute paths (except simple / for root which we don't want either)
                    if str(path).startswith("/"):
                        self.fail(f"entrypoints.{key} must be relative, got: {path}")
    
    def test_motor_ai_json_contains_required_fields(self) -> None:
        """motor_ai.json must contain essential fields for AI discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))
            
            service = ProjectService(project_root, auto_ensure=False)
            result = service.generate_ai_bootstrap(project_root, manifest)
            
            # Check required fields
            self.assertIn("project", result, "Must have 'project' section")
            self.assertIn("entrypoints", result, "Must have 'entrypoints' section")
            self.assertIn("capabilities", result, "Must have 'capabilities' section")
            self.assertIn("engine", result, "Must have 'engine' section")
            
            # Check project fields
            project = result["project"]
            self.assertIn("name", project, "project.name is required")
            self.assertIn("root", project, "project.root is required")
            self.assertIn("paths", project, "project.paths is required")
            
            # Check entrypoints
            entrypoints = result["entrypoints"]
            self.assertIn("manifest", entrypoints, "entrypoints.manifest is required")
            self.assertIn("assets_dir", entrypoints, "entrypoints.assets_dir is required")
            self.assertIn("scripts_dir", entrypoints, "entrypoints.scripts_dir is required")
    
    def test_motor_ai_json_is_valid_json(self) -> None:
        """Generated content must be valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))
            
            service = ProjectService(project_root, auto_ensure=False)
            result = service.generate_ai_bootstrap(project_root, manifest)
            
            # Should be able to serialize and deserialize
            json_str = json.dumps(result)
            reparsed = json.loads(json_str)
            self.assertEqual(result, reparsed)
    
    def test_start_here_md_is_portable(self) -> None:
        """START_HERE_AI.md must not contain absolute paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))
            
            registry = get_default_registry()
            builder = MotorAIBootstrapBuilder(registry)
            
            content = builder.build_start_here_md(manifest.name)
            
            # Check for common absolute path patterns
            absolute_patterns = [
                r"[A-Za-z]:\\",  # Windows C:\
                r"/home/",
                r"/Users/",
                r"/root/",
            ]
            
            for pattern in absolute_patterns:
                self.assertNotRegex(
                    content, pattern,
                    f"START_HERE_AI.md contains absolute path pattern: {pattern}"
                )


class BootstrapWriteToProjectTests(unittest.TestCase):
    """Tests for the write_to_project method."""
    
    def test_write_to_project_creates_files(self) -> None:
        """write_to_project must create motor_ai.json and START_HERE_AI.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "TestProject"
            project_root.mkdir()
            
            # Create minimal project structure
            (project_root / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }))
            
            registry = get_default_registry()
            builder = MotorAIBootstrapBuilder(registry)
            
            result = builder.write_to_project(
                project_root,
                {
                    "project": {
                        "name": "TestProject",
                        "root": ".",
                        "engine_version": "2026.03",
                    },
                    "entrypoints": {
                        "manifest": "project.json",
                        "assets_dir": "assets",
                    },
                }
            )
            
            # Check files were created
            self.assertTrue(
                (project_root / "motor_ai.json").exists(),
                "motor_ai.json must be created"
            )
            self.assertTrue(
                (project_root / "START_HERE_AI.md").exists(),
                "START_HERE_AI.md must be created"
            )
            
            # Verify motor_ai.json content is portable
            motor_ai_content = json.loads(
                (project_root / "motor_ai.json").read_text(encoding="utf-8")
            )
            
            # Check no absolute paths
            content_str = json.dumps(motor_ai_content)
            self.assertNotIn("C:\\", content_str, "motor_ai.json must not contain Windows absolute paths")
            self.assertNotIn("/home/", content_str, "motor_ai.json must not contain Unix absolute paths")


if __name__ == "__main__":
    unittest.main()
