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
            codes = {item["code"] for item in data["problems"]}
            self.assertIn("external_runtime_run_game", codes)

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
