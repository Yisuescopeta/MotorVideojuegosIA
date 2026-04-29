from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.ai.compliance import run_ai_compliance
from engine.ai import get_default_registry
from motor.cli import create_motor_parser


ROOT = Path(__file__).resolve().parents[1]


def _transform() -> dict:
    return {
        "enabled": True,
        "x": 0.0,
        "y": 0.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _create_project(workspace: Path) -> Path:
    project = workspace / "ComplianceProject"
    project.mkdir()
    (project / "levels").mkdir()
    (project / "assets").mkdir()
    (project / "scripts").mkdir()
    (project / "settings").mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "name": "ComplianceProject",
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
        ),
        encoding="utf-8",
    )
    return project


def _create_engine_repo_like_project(workspace: Path) -> Path:
    project = _create_project(workspace)
    (project / "engine" / "ai").mkdir(parents=True)
    (project / "motor").mkdir()
    (project / "tests").mkdir()
    (project / "engine" / "ai" / "compliance.py").write_text('"""stub"""', encoding="utf-8")
    (project / "motor" / "cli.py").write_text('"""stub"""', encoding="utf-8")
    return project


def _write_scene(project: Path, components: dict | None = None) -> Path:
    scene = project / "levels" / "main_scene.json"
    scene.write_text(
        json.dumps(
            {
                "name": "Main Scene",
                "schema_version": 2,
                "entities": [
                    {
                        "id": "entity_player",
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": components or {"Transform": _transform()},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return scene


class AIComplianceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_home = tempfile.TemporaryDirectory(prefix="motor_compliance_home_")
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
        self.env["MOTORVIDEOJUEGOSIA_HOME"] = (Path(self._temp_home.name) / "home").as_posix()

    def tearDown(self) -> None:
        self._temp_home.cleanup()

    def test_native_simple_scene_passes_basic_compliance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            self.assertFalse(report["external_runtime_detected"], report)
            self.assertGreaterEqual(report["native_score"], 70)
            self.assertEqual(report["problems"], [])
            self.assertTrue(report["checks"]["serialized_entities_present"])

    def test_run_game_suspicious_fails_in_strict_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            clean_report = run_ai_compliance(project, strict=True)
            (project / "run_game.py").write_text(
                "import pyray\nwhile not pyray.window_should_close():\n    pyray.begin_drawing()\n    pyray.end_drawing()\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "motor",
                    "ai",
                    "compliance",
                    "--project",
                    project.as_posix(),
                    "--strict",
                    "--json",
                ],
                capture_output=True,
                text=True,
                env=self.env,
                cwd=ROOT,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout[result.stdout.index("{"):])
            self.assertFalse(payload["success"])
            data = payload["data"]
            self.assertFalse(data["strict_pass"])
            self.assertTrue(data["external_runtime_detected"])
            self.assertTrue(data["external_runtime_blocking"])
            self.assertLessEqual(data["native_score"], clean_report["native_score"] - 25)
            codes = {item["code"] for item in data["problems"]}
            self.assertIn("external_runtime_run_game", codes)

    def test_demo_run_game_warns_without_strict_failure_or_score_drop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            clean_report = run_ai_compliance(project, strict=True)
            demo_dir = project / "demo"
            demo_dir.mkdir()
            (demo_dir / "run_game.py").write_text(
                "import pyray\nwhile not pyray.window_should_close():\n    pyray.begin_drawing()\n    pyray.end_drawing()\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            self.assertTrue(report["external_runtime_detected"])
            self.assertFalse(report["external_runtime_blocking"])
            self.assertTrue(report["external_runtime_warnings"])
            self.assertGreaterEqual(report["native_score"], clean_report["native_score"])
            problem_codes = {item["code"] for item in report["problems"]}
            self.assertNotIn("external_runtime_run_game", problem_codes)
            warning_codes = {item["code"] for item in report["warnings"]}
            self.assertIn("external_runtime_run_game", warning_codes)

    def test_docs_archive_external_runtime_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            archive_dir = project / "docs" / "archive"
            archive_dir.mkdir(parents=True)
            (archive_dir / "run_game.py").write_text(
                "import pyray\nwhile not pyray.window_should_close():\n    pyray.begin_drawing()\n    pyray.end_drawing()\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            self.assertFalse(report["external_runtime_blocking"])
            external_codes = {
                item["code"]
                for item in [*report["problems"], *report["warnings"]]
                if item["code"].startswith("external_runtime_")
            }
            self.assertNotIn("external_runtime_run_game", external_codes)
            self.assertNotIn("external_runtime_loop", external_codes)
            self.assertNotIn("external_runtime_raylib", external_codes)

    def test_demo_bat_under_demo_is_warning_not_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            demo_dir = project / "demo"
            demo_dir.mkdir()
            (demo_dir / "launch.bat").write_text(
                "@echo off\npython main.py\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            self.assertTrue(report["external_runtime_detected"])
            self.assertFalse(report["external_runtime_blocking"])
            self.assertTrue(report["external_runtime_warnings"])
            problem_codes = {item["code"] for item in report["problems"]}
            self.assertNotIn("external_runtime_batch", problem_codes)
            warning_codes = {item["code"] for item in report["warnings"]}
            self.assertIn("external_runtime_batch", warning_codes)

    def test_pyray_loop_in_root_blocks_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            (project / "script.py").write_text(
                "import pyray\nwhile not pyray.window_should_close():\n    pyray.begin_drawing()\n    pyray.end_drawing()\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertFalse(report["success"], report)
            self.assertFalse(report["strict_pass"], report)
            self.assertTrue(report["external_runtime_detected"])
            self.assertTrue(report["external_runtime_blocking"])
            problem_codes = {item["code"] for item in report["problems"]}
            self.assertIn("external_runtime_loop", problem_codes)

    def test_root_main_py_is_allowed_for_engine_repo_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_engine_repo_like_project(Path(tmpdir))
            _write_scene(project)
            (project / "main.py").write_text(
                "import pyray as rl\n\n"
                "def main() -> None:\n"
                "    print('repo launcher')\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            external_codes = {
                item["code"]
                for item in [*report["problems"], *report["warnings"]]
                if item["path"] == "main.py"
            }
            self.assertEqual(external_codes, set())
            self.assertEqual(report["checks"]["project_scan_context"], "engine_repo")

    def test_nested_projects_are_ignored_when_scanning_engine_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_engine_repo_like_project(Path(tmpdir))
            _write_scene(project)
            nested = project / "projects" / "NestedGame"
            (nested / "scripts").mkdir(parents=True)
            (nested / "levels").mkdir()
            (nested / "assets").mkdir()
            (nested / "settings").mkdir()
            (nested / "project.json").write_text(
                json.dumps(
                    {
                        "name": "NestedGame",
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
                ),
                encoding="utf-8",
            )
            (nested / "scripts" / "battle_controller.py").write_text("import pyray as rl\n", encoding="utf-8")

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            nested_paths = {
                item["path"]
                for item in [*report["problems"], *report["warnings"]]
                if item.get("path", "").startswith("projects/NestedGame/")
            }
            self.assertEqual(nested_paths, set())
            self.assertEqual(report["checks"]["nested_project_roots"], [nested.as_posix()])

    def test_non_loop_pyray_script_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            (project / "scripts" / "main_menu_controller.py").write_text(
                "import pyray as rl\n\n"
                "def on_update(context, dt):\n"
                "    return rl.get_mouse_position()\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            external_codes = {
                item["code"]
                for item in [*report["problems"], *report["warnings"]]
                if item.get("path") == "scripts/main_menu_controller.py"
            }
            self.assertEqual(external_codes, set())

    def test_sitecustomize_style_stub_does_not_false_positive_in_engine_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_engine_repo_like_project(Path(tmpdir))
            _write_scene(project)
            (project / "sitecustomize.py").write_text(
                "def begin_drawing(*args, **kwargs):\n"
                "    return None\n\n"
                "MAPPING = {'begin_drawing': begin_drawing}\n",
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            external_codes = {
                item["code"]
                for item in [*report["problems"], *report["warnings"]]
                if item.get("path") == "sitecustomize.py"
            }
            self.assertEqual(external_codes, set())

    def test_archived_legacy_runner_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            archive_dir = project / "docs" / "archive" / "legacy_runners"
            archive_dir.mkdir(parents=True)
            (archive_dir / "run_platformer_demo.bat").write_text("@echo off\npython main.py\n", encoding="utf-8")

            report = run_ai_compliance(project, strict=True)

            self.assertTrue(report["success"], report)
            self.assertTrue(report["strict_pass"], report)
            external_codes = {
                item["code"]
                for item in [*report["problems"], *report["warnings"]]
                if item.get("path") == "docs/archive/legacy_runners/run_platformer_demo.bat"
            }
            self.assertEqual(external_codes, set())

    def test_temp_fix_script_is_absent_from_repo_root(self) -> None:
        self.assertFalse((ROOT / "fix_game_loop.py").exists())

    def test_compliance_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)
            (project / "run_game.py").write_text(
                "import pyray\nwhile not pyray.window_should_close():\n    pyray.begin_drawing()\n    pyray.end_drawing()\n",
                encoding="utf-8",
            )
            before = {p.name: p.stat().st_mtime for p in project.rglob("*") if p.is_file()}
            report = run_ai_compliance(project, strict=False)
            after = {p.name: p.stat().st_mtime for p in project.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertTrue(report["external_runtime_detected"])

    def test_missing_bootstrap_is_regenerable_and_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            _write_scene(project)

            report = run_ai_compliance(project)

            self.assertTrue(report["success"], report)
            self.assertFalse((project / "motor_ai.json").exists())
            self.assertFalse((project / "START_HERE_AI.md").exists())
            self.assertTrue(report["checks"]["motor_ai_regenerable"])
            self.assertTrue(report["checks"]["start_here_regenerable"])
            warning_codes = {item["code"] for item in report["warnings"]}
            self.assertIn("motor_ai_missing", warning_codes)
            self.assertIn("start_here_missing", warning_codes)

    def test_unknown_component_warns_without_mutating_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_project(Path(tmpdir))
            scene = _write_scene(project, {"Transform": _transform(), "MysteryAIComponent": {"enabled": True}})
            before = scene.read_text(encoding="utf-8")

            report = run_ai_compliance(project, strict=True)

            self.assertEqual(scene.read_text(encoding="utf-8"), before)
            self.assertTrue(report["strict_pass"], report)
            warning_codes = {item["code"] for item in report["warnings"]}
            self.assertIn("unknown_component", warning_codes)
            self.assertIn("MysteryAIComponent", report["checks"]["unknown_components"])

    def test_ai_compliance_is_implemented_in_registry_and_parser(self) -> None:
        registry = get_default_registry()
        cap = registry.get("ai:compliance")
        self.assertIsNotNone(cap)
        self.assertEqual(cap.status, "implemented")

        parser = create_motor_parser()
        help_text = parser.format_help()
        self.assertIn("ai", help_text)

        result = subprocess.run(
            [sys.executable, "-m", "motor", "ai", "compliance", "--help"],
            capture_output=True,
            text=True,
            env=self.env,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--strict", result.stdout)


if __name__ == "__main__":
    unittest.main()
