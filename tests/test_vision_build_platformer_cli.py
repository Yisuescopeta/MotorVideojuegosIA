from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.ai import get_default_registry

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "vision" / "simple_platformer.ppm"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    return env


def _run_motor(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "motor", *args],
        cwd=str(cwd),
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def _create_project(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "project.json").write_text(
        json.dumps(
            {
                "name": "VisionBuildPlatformerCLI",
                "version": 2,
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                },
            }
        ),
        encoding="utf-8",
    )


class VisionBuildPlatformerCLITests(unittest.TestCase):
    def test_success_writes_scene_and_default_gamespec_sidecar_with_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            scene = project / "levels" / "from_image.scene"
            sidecar = Path(f"{scene}.gamespec.json")

            result = _run_motor("vision", "build-platformer", str(FIXTURE), "--out", str(scene), "--project", str(project), "--json")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = _payload(result)
            self.assertTrue(payload["success"])
            self.assertTrue(scene.exists())
            self.assertTrue(sidecar.exists())
            self.assertEqual(payload["data"]["scene_path"], scene.as_posix())
            self.assertEqual(payload["data"]["gamespec_path"], sidecar.as_posix())
            self.assertGreater(payload["data"]["entity_count"], 0)
            self.assertIn("warnings", payload["data"])
            self.assertIn("confidence", payload["data"])
            self.assertIn("unsupported_features", payload["data"])
            self.assertIsInstance(payload["data"]["warnings"], list)
            self.assertIsInstance(payload["data"]["confidence"], (int, float))
            self.assertIsInstance(payload["data"]["unsupported_features"], list)

            spec = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(spec["schema_version"], "gamespec2d.v1")
            self.assertEqual(spec["game_type"], "platformer")
            scene_data = json.loads(scene.read_text(encoding="utf-8"))
            entities = scene_data.get("entities", [])
            self.assertGreater(len(entities), 0)
            self.assertTrue(any(entity.get("name") == "vision_camera" for entity in entities))

    def test_custom_gamespec_sidecar_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            scene = project / "levels" / "custom_sidecar.scene"
            sidecar = project / "specs" / "custom.gamespec.json"

            result = _run_motor(
                "vision", "build-platformer", str(FIXTURE), "--out", str(scene), "--gamespec-out", str(sidecar), "--project", str(project), "--json"
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = _payload(result)
            self.assertTrue(payload["success"])
            self.assertTrue(scene.exists())
            self.assertTrue(sidecar.exists())
            self.assertEqual(payload["data"]["gamespec_path"], sidecar.as_posix())

    def test_refuses_to_overwrite_existing_scene_and_preserves_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            scene = project / "levels" / "existing.scene"
            scene.parent.mkdir(parents=True)
            scene.write_text("sentinel-scene", encoding="utf-8")
            sidecar = Path(f"{scene}.gamespec.json")

            result = _run_motor("vision", "build-platformer", str(FIXTURE), "--out", str(scene), "--project", str(project), "--json")

            self.assertNotEqual(result.returncode, 0)
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("already exists", payload["message"])
            self.assertEqual(scene.read_text(encoding="utf-8"), "sentinel-scene")
            self.assertFalse(sidecar.exists())

    def test_refuses_overlapping_scene_and_custom_gamespec_path_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            scene = project / "levels" / "overlap.scene"

            result = _run_motor(
                "vision",
                "build-platformer",
                str(FIXTURE),
                "--out",
                str(scene),
                "--gamespec-out",
                str(scene),
                "--project",
                str(project),
                "--json",
            )

            self.assertNotEqual(result.returncode, 0)
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("must be distinct", payload["message"])
            self.assertFalse(scene.exists())

    def test_refuses_to_overwrite_existing_gamespec_and_preserves_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            scene = project / "levels" / "blocked.scene"
            sidecar = Path(f"{scene}.gamespec.json")
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text("sentinel-gamespec", encoding="utf-8")

            result = _run_motor("vision", "build-platformer", str(FIXTURE), "--out", str(scene), "--project", str(project), "--json")

            self.assertNotEqual(result.returncode, 0)
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("already exists", payload["message"])
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "sentinel-gamespec")
            self.assertFalse(scene.exists())

    def test_missing_image_leaves_no_partial_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            scene = project / "levels" / "missing.scene"
            sidecar = Path(f"{scene}.gamespec.json")

            result = _run_motor("vision", "build-platformer", str(Path(tmp) / "missing.ppm"), "--out", str(scene), "--project", str(project), "--json")

            self.assertNotEqual(result.returncode, 0)
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("image not found", payload["message"])
            self.assertEqual(payload["data"]["warnings"], [])
            self.assertIsNone(payload["data"]["confidence"])
            self.assertEqual(payload["data"]["unsupported_features"], [])
            self.assertFalse(scene.exists())
            self.assertFalse(sidecar.exists())

    def test_invalid_image_leaves_no_partial_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            invalid = Path(tmp) / "invalid.ppm"
            invalid.write_text("not a ppm", encoding="utf-8")
            scene = project / "levels" / "invalid.scene"
            sidecar = Path(f"{scene}.gamespec.json")

            result = _run_motor("vision", "build-platformer", str(invalid), "--out", str(scene), "--project", str(project), "--json")

            self.assertNotEqual(result.returncode, 0)
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("unsupported_image_format", payload["message"])
            self.assertFalse(scene.exists())
            self.assertFalse(sidecar.exists())

    def test_help_and_registry_entry_exist(self) -> None:
        help_result = _run_motor("vision", "build-platformer", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("usage:", help_result.stdout.lower())
        self.assertIn("--gamespec-out", help_result.stdout)

        cap = get_default_registry().get("vision:build-platformer")
        self.assertIsNotNone(cap)
        assert cap is not None
        self.assertEqual(cap.status, "implemented")
        self.assertEqual(cap.cli_command.split()[0:3], ["motor", "vision", "build-platformer"])
        self.assertIn("CapabilityRegistry.cmd_vision_build_platformer", cap.api_methods)
        self.assertIn("CLI/internal helper only", cap.notes)
        self.assertIn("not an EngineAPI method", cap.notes)
        self.assertNotIn("object detection", cap.summary.lower())


if __name__ == "__main__":
    unittest.main()
