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
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _run_module_result(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


class EngineCliTests(unittest.TestCase):
    def test_validate_scene_subcommand(self) -> None:
        root_editor_state = _read_root_editor_state()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            project_root.mkdir(parents=True, exist_ok=True)
            _copy_project_file(project_root, "levels/demo_level.json")
            result = _run_module(
                "tools.engine_cli",
                "validate",
                "--target",
                "scene",
                "--path",
                "levels/demo_level.json",
                cwd=project_root,
            )
            self.assertIn("[OK]", result.stdout)
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_validate_scene_subcommand_fails_for_invalid_rule_payload(self) -> None:
        root_editor_state = _read_root_editor_state()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            project_root.mkdir(parents=True, exist_ok=True)
            invalid_scene = project_root / "levels" / "invalid_rules.json"
            invalid_scene.parent.mkdir(parents=True, exist_ok=True)
            invalid_scene.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "BrokenRules",
                        "entities": [],
                        "rules": [{"event": "tick", "do": [{"action": "emit_event"}]}],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            result = _run_module_result(
                "tools.engine_cli",
                "validate",
                "--target",
                "scene",
                "--path",
                "levels/invalid_rules.json",
                cwd=project_root,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("$.rules[0].do[0].event: expected non-empty string", result.stdout)
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_cli_and_schema_import_without_pyray(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) if not env.get("PYTHONPATH") else str(ROOT) + os.pathsep + env["PYTHONPATH"]
        env["PYRAY_FORCE_STUB"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import tools.engine_cli; import engine.serialization.schema; from engine.api import EngineAPI",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Import smoke test failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

    def test_smoke_subcommand_produces_expected_artifacts(self) -> None:
        root_editor_state = _read_root_editor_state()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            project_root.mkdir(parents=True, exist_ok=True)
            _copy_project_file(project_root, "levels/demo_level.json")
            out_dir = Path(temp_dir) / "smoke"
            result = _run_module(
                "tools.engine_cli",
                "smoke",
                "--scene",
                "levels/demo_level.json",
                "--frames",
                "2",
                "--seed",
                "7",
                "--out-dir",
                out_dir.as_posix(),
                cwd=project_root,
            )
            self.assertIn("[OK]", result.stdout)
            self.assertTrue((out_dir / "smoke_migrated_scene.json").exists())
            self.assertTrue((out_dir / "smoke_debug_dump.json").exists())
            self.assertTrue((out_dir / "smoke_profile.json").exists())

            profile_report = json.loads((out_dir / "smoke_profile.json").read_text(encoding="utf-8"))
            debug_dump = json.loads((out_dir / "smoke_debug_dump.json").read_text(encoding="utf-8"))

        self.assertEqual(profile_report["frames"], 2)
        self.assertEqual(debug_dump["pass"], "Debug")
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_smoke_subcommand_stops_before_artifacts_when_scene_is_invalid(self) -> None:
        root_editor_state = _read_root_editor_state()
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            project_root.mkdir(parents=True, exist_ok=True)
            invalid_scene = project_root / "levels" / "invalid_rules.json"
            invalid_scene.parent.mkdir(parents=True, exist_ok=True)
            invalid_scene.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "BrokenRules",
                        "entities": [],
                        "rules": [{"event": "", "do": [{"action": "log_message", "message": "hi"}]}],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            out_dir = Path(temp_dir) / "smoke"
            result = _run_module_result(
                "tools.engine_cli",
                "smoke",
                "--scene",
                "levels/invalid_rules.json",
                "--frames",
                "2",
                "--seed",
                "7",
                "--out-dir",
                out_dir.as_posix(),
                cwd=project_root,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("$.rules[0].event: expected non-empty string", result.stdout)
            self.assertFalse((out_dir / "smoke_profile.json").exists())
        self.assertEqual(_read_root_editor_state(), root_editor_state)


class CLISlicingTests(unittest.TestCase):
    """Tests for assets slices CLI commands."""

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

        # Create a simple test image (16x16 PNG)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x10,
            0x00, 0x00, 0x00, 0x10,
            0x08, 0x02, 0x00, 0x00, 0x00,
            0x90, 0x91, 0x68, 0x36,
            0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, 0x54,
            0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
            0x00, 0x03, 0x00, 0x01,
            0x00, 0x05, 0xFE, 0xD4,
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
            0xAE, 0x42, 0x60, 0x82,
        ])
        (self.project_root / "assets" / "spritesheet.png").write_bytes(png_data)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_slices_list_command_fails_for_nonexistent_asset(self) -> None:
        result = _run_module_result(
            "tools.engine_cli",
            "assets",
            "slices",
            "list",
            "assets/nonexistent.png",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])  # List operation succeeds but returns empty
        self.assertEqual(data["data"]["count"], 0)

    def test_slices_grid_command_creates_slices(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "assets",
            "slices",
            "grid",
            "assets/spritesheet.png",
            "--project",
            str(self.project_root),
            "--cell-width", "8",
            "--cell-height", "8",
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        # 16x16 image with 8x8 cells = 4 slices
        self.assertEqual(data["data"]["slices_count"], 4)

    def test_slices_auto_preview_command_works(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "assets",
            "slices",
            "auto",
            "assets/spritesheet.png",
            "--project",
            str(self.project_root),
            "--preview",
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        self.assertTrue(data["data"]["preview"])

    def test_slices_manual_command_with_inline_json(self) -> None:
        slices_json = '[{"name": "test", "x": 0, "y": 0, "width": 8, "height": 8}]'
        result = _run_module(
            "tools.engine_cli",
            "assets",
            "slices",
            "manual",
            "assets/spritesheet.png",
            "--project",
            str(self.project_root),
            "--slices",
            slices_json,
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])


class CLIHeadlessWorkflowTests(unittest.TestCase):
    """Tests for headless workflow commands (scene, entity, component, animator)."""

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

        # Create a simple test scene
        (self.project_root / "levels" / "existing_scene.json").write_text(
            json.dumps({
                "name": "Existing Scene",
                "entities": [],
                "rules": [],
            }),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_scene_create_command_works(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "scene",
            "create",
            "Test Level",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        # Scene file should be created
        scene_file = self.project_root / "levels" / "test_level.json"
        self.assertTrue(scene_file.exists())

    def test_entity_create_command_works(self) -> None:
        # First create a scene
        _run_module(
            "tools.engine_cli",
            "scene",
            "create",
            "EntityTest",
            "--project",
            str(self.project_root),
            cwd=self.workspace,
        )
        # Create entity
        result = _run_module(
            "tools.engine_cli",
            "entity",
            "create",
            "Player",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])

    def test_component_add_command_works(self) -> None:
        # Create scene and entity first
        _run_module(
            "tools.engine_cli",
            "scene",
            "create",
            "ComponentTest",
            "--project",
            str(self.project_root),
            cwd=self.workspace,
        )
        _run_module(
            "tools.engine_cli",
            "entity",
            "create",
            "Player",
            "--project",
            str(self.project_root),
            cwd=self.workspace,
        )
        # Add component
        result = _run_module(
            "tools.engine_cli",
            "component",
            "add",
            "Player",
            "Transform",
            '--data={"x":100,"y":200}',
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])

    def test_animator_info_command_no_animator(self) -> None:
        # Create scene and entity
        _run_module(
            "tools.engine_cli",
            "scene",
            "create",
            "AnimatorTest",
            "--project",
            str(self.project_root),
            cwd=self.workspace,
        )
        _run_module(
            "tools.engine_cli",
            "entity",
            "create",
            "Player",
            "--project",
            str(self.project_root),
            cwd=self.workspace,
        )
        # Check animator info (should fail - no animator)
        result = _run_module_result(
            "tools.engine_cli",
            "animator",
            "info",
            "Player",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        # Should return failure because entity has no animator
        self.assertNotEqual(result.returncode, 0)


class CLIAIFacingTests(unittest.TestCase):
    """Tests for new AI-facing commands (capabilities, doctor, project, scene, assets)."""

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

        # Create a simple scene
        (self.project_root / "levels" / "main_scene.json").write_text(
            json.dumps({
                "name": "Main Scene",
                "entities": [],
                "rules": [],
            }),
            encoding="utf-8",
        )

        # Create an asset
        (self.project_root / "assets" / "player.png").write_bytes(b"fake_png_data")

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_capabilities_command_outputs_valid_json(self) -> None:
        result = _run_module("tools.engine_cli", "capabilities", "--json", cwd=self.workspace)
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("capabilities", data["data"])
        self.assertGreater(data["data"]["count"], 0)

    def test_capabilities_command_has_expected_structure(self) -> None:
        result = _run_module("tools.engine_cli", "capabilities", "--json", cwd=self.workspace)
        data = json.loads(result.stdout)["data"]
        self.assertIn("engine_version", data)
        self.assertIn("capabilities_schema_version", data)
        self.assertIsInstance(data["capabilities"], list)

        if data["capabilities"]:
            cap = data["capabilities"][0]
            self.assertIn("id", cap)
            self.assertIn("summary", cap)
            self.assertIn("mode", cap)
            self.assertIn("api_methods", cap)
            self.assertIn("cli_command", cap)

    def test_doctor_command_reports_project_status(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "doctor",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertIn("success", data)
        self.assertIn("data", data)
        self.assertIn("healthy", data["data"])
        self.assertIn("checks", data["data"])

    def test_doctor_command_fails_for_missing_project(self) -> None:
        result = _run_module_result(
            "tools.engine_cli",
            "doctor",
            "--project",
            "/nonexistent/path",
            "--json",
            cwd=self.workspace,
        )
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["success"])

    def test_project_info_command_works(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "project",
            "info",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["project"]["name"], "TestProject")

    def test_scene_list_command_works(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "scene",
            "list",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(len(data["data"]["scenes"]), 1)
        self.assertEqual(data["data"]["scenes"][0]["name"], "Main Scene")

    def test_assets_list_command_works(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "assets",
            "list",
            "--project",
            str(self.project_root),
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["count"], 1)

    def test_assets_list_with_search_filter(self) -> None:
        result = _run_module(
            "tools.engine_cli",
            "assets",
            "list",
            "--project",
            str(self.project_root),
            "--search",
            "player",
            "--json",
            cwd=self.workspace,
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["search"], "player")

    def test_json_response_format_consistency(self) -> None:
        """All commands should return consistent JSON format."""
        commands = [
            ("capabilities", ["--json"]),
            ("doctor", ["--project", str(self.project_root), "--json"]),
            ("project", ["info", "--project", str(self.project_root), "--json"]),
            ("scene", ["list", "--project", str(self.project_root), "--json"]),
            ("assets", ["list", "--project", str(self.project_root), "--json"]),
        ]

        for cmd, args in commands:
            with self.subTest(command=cmd):
                result = _run_module("tools.engine_cli", cmd, *args, cwd=self.workspace)
                data = json.loads(result.stdout)
                # Check standard response format
                self.assertIn("success", data, f"{cmd} missing 'success' field")
                self.assertIn("message", data, f"{cmd} missing 'message' field")
                self.assertIn("data", data, f"{cmd} missing 'data' field")
                self.assertIsInstance(data["success"], bool, f"{cmd} 'success' should be boolean")
                self.assertIsInstance(data["message"], str, f"{cmd} 'message' should be string")
                self.assertIsInstance(data["data"], dict, f"{cmd} 'data' should be dict")


if __name__ == "__main__":
    unittest.main()
