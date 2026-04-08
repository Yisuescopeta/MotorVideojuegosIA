"""
tests/test_bootstrap_single_source_of_truth.py

Tests ensuring AI bootstrap generation has a single source of truth.

Verifies that:
1. CLI delegates to ProjectService (doesn't duplicate bootstrap logic)
2. Both CLI and service produce identical output structure
3. Future divergence is detected immediately
"""

from __future__ import annotations

import ast
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from engine.ai import get_default_registry, MotorAIBootstrapBuilder
from engine.project.project_service import ProjectService, ProjectManifest
import motor.cli_core as cli_core_module


class BootstrapSingleSourceOfTruthTests(unittest.TestCase):
    """Tests ensuring bootstrap generation has single source of truth."""

    def _create_test_project(self, workspace: Path, name: str = "TestProject") -> tuple[Path, ProjectManifest]:
        """Create a minimal test project with manifest."""
        project_root = workspace / name
        project_root.mkdir()

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

        for d in ["assets", "levels", "scripts", "settings", "prefabs", ".motor"]:
            (project_root / d).mkdir(parents=True, exist_ok=True)

        manifest = ProjectManifest.from_dict(manifest_data)
        return project_root, manifest

    def test_cli_delegates_to_project_service(self) -> None:
        """CLI cmd_project_bootstrap_ai must delegate to ProjectService, not duplicate logic."""
        source = inspect.getsource(cli_core_module.cmd_project_bootstrap_ai)

        # Should call ProjectService.generate_ai_bootstrap
        self.assertIn(
            "generate_ai_bootstrap",
            source,
            "CLI must delegate to ProjectService.generate_ai_bootstrap() for single source of truth"
        )

        # Should NOT directly use MotorAIBootstrapBuilder (that's an implementation detail of the service)
        self.assertNotIn(
            "MotorAIBootstrapBuilder",
            source,
            "CLI should not directly use MotorAIBootstrapBuilder; this is an implementation detail of ProjectService"
        )

        # Should NOT directly use get_default_registry to build content (should use service result)
        # Registry usage in CLI should only be for metadata (capability counts), not for building content
        registry_build_patterns = [
            "build_motor_ai_json",
            "build_start_here_md",
            "write_to_project",
        ]
        for pattern in registry_build_patterns:
            self.assertNotIn(
                pattern,
                source,
                f"CLI should not call {pattern}(); this is ProjectService's responsibility"
            )

    def test_cli_and_service_produce_identical_structure(self) -> None:
        """Both CLI delegation and direct service call must produce identical output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))

            # Method 1: Direct ProjectService call (single source of truth)
            service = ProjectService(project_root, auto_ensure=False)
            service_result = service.generate_ai_bootstrap(project_root, manifest)

            # Method 2: Clean project, use CLI (via cmd_project_bootstrap_ai function)
            project_root2, manifest2 = self._create_test_project(Path(tmpdir), "TestProject2")

            # Call CLI function directly
            exit_code = cli_core_module.cmd_project_bootstrap_ai(project_root2, json_output=True)
            self.assertEqual(exit_code, 0, "CLI bootstrap should succeed")

            # Load CLI-generated motor_ai.json
            cli_motor_ai_path = project_root2 / "motor_ai.json"
            self.assertTrue(cli_motor_ai_path.exists(), "CLI should create motor_ai.json")
            cli_result = json.loads(cli_motor_ai_path.read_text(encoding="utf-8"))

            # Compare structure (ignore dynamic fields like engine version if they differ)
            # The key structural elements should match
            self.assertEqual(
                set(service_result.keys()),
                set(cli_result.keys()),
                "Service and CLI must produce motor_ai.json with same top-level keys"
            )

            # Project section should have same structure
            self.assertEqual(
                set(service_result.get("project", {}).keys()),
                set(cli_result.get("project", {}).keys()),
                "Service and CLI must produce same project section structure"
            )

            # Entrypoints should have same keys
            self.assertEqual(
                set(service_result.get("entrypoints", {}).keys()),
                set(cli_result.get("entrypoints", {}).keys()),
                "Service and CLI must produce same entrypoints structure"
            )

    def test_bootstrap_content_is_portable_via_both_paths(self) -> None:
        """Bootstrap files must be portable regardless of generation path (CLI vs Service)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test CLI path
            project_root_cli, _ = self._create_test_project(Path(tmpdir), "CLIProject")
            cli_core_module.cmd_project_bootstrap_ai(project_root_cli, json_output=True)
            cli_content = json.loads((project_root_cli / "motor_ai.json").read_text())

            # Test Service path
            project_root_svc, manifest = self._create_test_project(Path(tmpdir), "ServiceProject")
            service = ProjectService(project_root_svc, auto_ensure=False)
            service.generate_ai_bootstrap(project_root_svc, manifest)
            svc_content = json.loads((project_root_svc / "motor_ai.json").read_text())

            # Both should have relative paths (portability check)
            for source, name in [(cli_content, "CLI"), (svc_content, "Service")]:
                project_root = source.get("project", {}).get("root", "")
                self.assertEqual(
                    project_root, ".",
                    f"{name} bootstrap must use relative root path '.'"
                )

                # Check no absolute paths in entrypoints
                for key, path in source.get("entrypoints", {}).items():
                    self.assertNotIn(
                        ":", str(path),
                        f"{name} bootstrap entrypoint {key} must not contain Windows absolute path"
                    )

    def test_service_method_is_single_implementation(self) -> None:
        """ProjectService.generate_ai_bootstrap must be the sole implementation."""
        source = inspect.getsource(ProjectService.generate_ai_bootstrap)

        # Should use MotorAIBootstrapBuilder (the actual implementation)
        self.assertIn(
            "MotorAIBootstrapBuilder",
            source,
            "ProjectService.generate_ai_bootstrap must use MotorAIBootstrapBuilder"
        )

        # Should build both files
        self.assertIn(
            "build_motor_ai_json",
            source,
            "Service must build motor_ai.json content"
        )
        self.assertIn(
            "build_start_here_md",
            source,
            "Service must build START_HERE_AI.md content"
        )

    def test_detect_future_cli_divergence(self) -> None:
        """Fail if CLI starts reimplementing bootstrap logic instead of delegating.

        This test acts as a guard against future duplication.
        """
        source = inspect.getsource(cli_core_module.cmd_project_bootstrap_ai)

        # Parse AST to check function structure
        tree = ast.parse(source)

        # Find the function definition
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "cmd_project_bootstrap_ai":
                func_def = node
                break

        self.assertIsNotNone(func_def, "Should find cmd_project_bootstrap_ai function")

        # Count direct calls to ProjectService methods (should be at least 1 - migrate_project_bootstrap or generate_ai_bootstrap)
        service_calls = []
        valid_service_methods = ["migrate_project_bootstrap", "generate_ai_bootstrap"]
        for node in ast.walk(func_def):
            if isinstance(node, ast.Call):
                # Check for service method call
                if isinstance(node.func, ast.Attribute) and node.func.attr in valid_service_methods:
                    service_calls.append(node.func.attr)

        self.assertGreaterEqual(
            len(service_calls), 1,
            "CLI must call ProjectService.migrate_project_bootstrap() or generate_ai_bootstrap() for bootstrap generation"
        )

        # Check that CLI doesn't recreate the project_data structure
        # (this would indicate duplication of the service logic)
        project_data_assignments = []
        for node in ast.walk(func_def):
            if isinstance(node, ast.Dict):
                # Check if this dict has project/entrypoints keys
                keys = []
                for k in node.keys:
                    if isinstance(k, ast.Constant):
                        keys.append(k.value)
                    elif isinstance(k, ast.Str):  # Python < 3.8
                        keys.append(k.s)

                if "project" in keys and "entrypoints" in keys:
                    project_data_assignments.append(keys)

        self.assertEqual(
            len(project_data_assignments), 0,
            "CLI should not recreate project_data structure; this is ProjectService's responsibility. "
            "Delegate to ProjectService.generate_ai_bootstrap() instead."
        )


class BootstrapContractStabilityTests(unittest.TestCase):
    """Tests ensuring the bootstrap contract remains stable."""

    def test_motor_ai_json_schema_version(self) -> None:
        """motor_ai.json schema version must match expected value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "TestProject"
            project_root.mkdir()

            manifest_data = {
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
            }
            (project_root / "project.json").write_text(json.dumps(manifest_data))
            for d in ["assets", "levels", "scripts", "settings", "prefabs", ".motor"]:
                (project_root / d).mkdir(parents=True, exist_ok=True)

            manifest = ProjectManifest.from_dict(manifest_data)
            service = ProjectService(project_root, auto_ensure=False)
            result = service.generate_ai_bootstrap(project_root, manifest)

            # Schema version should be consistent
            self.assertEqual(
                result.get("schema_version"), 3,
                "motor_ai.json schema_version must be 3 (capabilities separated by status)"
            )

    def test_bootstrap_files_are_created_by_service(self) -> None:
        """ProjectService.generate_ai_bootstrap must create both bootstrap files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root, manifest = self._create_test_project(Path(tmpdir))

            # Verify files don't exist initially
            self.assertFalse((project_root / "motor_ai.json").exists())
            self.assertFalse((project_root / "START_HERE_AI.md").exists())

            service = ProjectService(project_root, auto_ensure=False)
            service.generate_ai_bootstrap(project_root, manifest)

            # Both files should be created
            self.assertTrue(
                (project_root / "motor_ai.json").exists(),
                "Service must create motor_ai.json"
            )
            self.assertTrue(
                (project_root / "START_HERE_AI.md").exists(),
                "Service must create START_HERE_AI.md"
            )

    def _create_test_project(self, workspace: Path, name: str = "TestProject") -> tuple[Path, ProjectManifest]:
        """Create a minimal test project with manifest."""
        project_root = workspace / name
        project_root.mkdir()

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

        for d in ["assets", "levels", "scripts", "settings", "prefabs", ".motor"]:
            (project_root / d).mkdir(parents=True, exist_ok=True)

        manifest = ProjectManifest.from_dict(manifest_data)
        return project_root, manifest


if __name__ == "__main__":
    unittest.main()
