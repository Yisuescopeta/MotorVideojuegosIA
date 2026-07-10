from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SPEC = ROOT / "examples" / "vision" / "simple_platformer.gamespec.json"
EXAMPLE_IMAGE = ROOT / "tests" / "fixtures" / "vision" / "simple_platformer.ppm"


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
                "name": "VisionCLIContract",
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


class VisionCLIContractTests(unittest.TestCase):
    def test_validate_json_success_is_parseable_and_structured(self) -> None:
        result = _run_motor("vision", "spec", "validate", str(EXAMPLE_SPEC), "--project", ".", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = _payload(result)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["schema_version"], "gamespec2d.v1")
        self.assertEqual(payload["data"]["game_type"], "platformer")
        self.assertEqual(payload["data"]["warning_count"], 1)
        self.assertIn("confidence_summary", payload["data"])

    def test_validate_missing_file_fails_with_json_only(self) -> None:
        missing = ROOT / "examples" / "vision" / "missing.gamespec.json"
        result = _run_motor("vision", "spec", "validate", str(missing), "--project", ".", "--json")

        self.assertNotEqual(result.returncode, 0)
        payload = _payload(result)
        self.assertFalse(payload["success"])
        self.assertIn("not found", payload["message"].lower())

    def test_validate_invalid_spec_fails_with_json_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            invalid = Path(tmp) / "invalid.gamespec.json"
            data = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
            data["grid"]["width"] = 0
            invalid.write_text(json.dumps(data), encoding="utf-8")

            result = _run_motor("vision", "spec", "validate", str(invalid), "--project", str(project), "--json")

        self.assertNotEqual(result.returncode, 0)
        payload = _payload(result)
        self.assertFalse(payload["success"])
        self.assertIn("grid.width", payload["message"])

    def test_build_scene_valid_outputs_report_and_scene_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            out = project / "levels" / "generated.scene"

            result = _run_motor(
                "vision",
                "build-scene",
                str(EXAMPLE_SPEC),
                "--out",
                str(out),
                "--project",
                str(project),
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = _payload(result)
            self.assertTrue(payload["success"])
            self.assertTrue(out.exists())
            self.assertEqual(payload["data"]["scene_path"], out.as_posix())
            self.assertEqual(payload["data"]["representation"], "collider_blocks")
            self.assertGreater(payload["data"]["entity_count"], 0)
            scene = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(any(entity.get("name") == "vision_camera" for entity in scene.get("entities", [])))

    def test_build_scene_with_repo_project_and_external_output_leaves_no_repo_artifacts(self) -> None:
        artifact_paths = [
            ROOT / "levels" / "gamespec_scene.json",
            ROOT / "levels" / "gamespec_scene_2.json",
        ]
        editor_state = ROOT / ".motor" / "editor_state.json"
        before_editor_state = editor_state.read_bytes() if editor_state.exists() else None

        for artifact in artifact_paths:
            self.assertFalse(artifact.exists(), f"pre-existing artifact blocks isolation check: {artifact}")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "external_generated.scene"
            result = _run_motor(
                "vision",
                "build-scene",
                str(EXAMPLE_SPEC),
                "--out",
                str(out),
                "--project",
                ".",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = _payload(result)
            self.assertTrue(payload["success"])
            self.assertTrue(out.exists())

        for artifact in artifact_paths:
            self.assertFalse(artifact.exists(), f"CLI left repo-local artifact: {artifact}")
        after_editor_state = editor_state.read_bytes() if editor_state.exists() else None
        self.assertEqual(after_editor_state, before_editor_state)

    def test_build_scene_refuses_overwrite_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            out = project / "levels" / "generated.scene"
            out.parent.mkdir(parents=True)
            out.write_text("sentinel", encoding="utf-8")

            result = _run_motor(
                "vision", "build-scene", str(EXAMPLE_SPEC), "--out", str(out), "--project", str(project), "--json"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "sentinel")
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("already exists", payload["message"])

    def test_build_scene_invalid_spec_leaves_no_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            _create_project(project)
            invalid = Path(tmp) / "invalid.gamespec.json"
            data = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
            data["entities"][0]["type"] = "boss"
            invalid.write_text(json.dumps(data), encoding="utf-8")
            out = project / "levels" / "invalid.scene"

            result = _run_motor(
                "vision", "build-scene", str(invalid), "--out", str(out), "--project", str(project), "--json"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("entities[0].type", payload["message"])

    def test_annotate_json_success_outputs_overlay_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay.ppm"
            result = _run_motor(
                "vision",
                "annotate",
                str(EXAMPLE_IMAGE),
                "--gamespec",
                str(EXAMPLE_SPEC),
                "--out",
                str(out),
                "--project",
                ".",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = _payload(result)
            self.assertTrue(payload["success"])
            self.assertTrue(out.exists())
            self.assertEqual(payload["data"]["overlay_path"], out.as_posix())
            self.assertEqual(payload["data"]["source"], EXAMPLE_IMAGE.as_posix())
            self.assertEqual(payload["data"]["gamespec"], EXAMPLE_SPEC.as_posix())
            self.assertEqual(payload["data"]["dimensions"], {"width": 16, "height": 16})
            self.assertEqual(payload["data"]["format"], "PPM_P3")
            self.assertEqual(payload["data"]["warning_count"], 1)
            self.assertEqual(payload["data"]["annotation_counts"]["entities"], 3)

    def test_annotate_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay.ppm"
            out.write_text("sentinel", encoding="ascii")
            result = _run_motor(
                "vision",
                "annotate",
                str(EXAMPLE_IMAGE),
                "--gamespec",
                str(EXAMPLE_SPEC),
                "--out",
                str(out),
                "--project",
                ".",
                "--json",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(out.read_text(encoding="ascii"), "sentinel")
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("already exists", payload["message"])

    def test_annotate_invalid_spec_leaves_no_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invalid = Path(tmp) / "invalid.gamespec.json"
            data = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
            data["entities"][0]["type"] = "boss"
            invalid.write_text(json.dumps(data), encoding="utf-8")
            out = Path(tmp) / "overlay.ppm"
            result = _run_motor(
                "vision",
                "annotate",
                str(EXAMPLE_IMAGE),
                "--gamespec",
                str(invalid),
                "--out",
                str(out),
                "--project",
                ".",
                "--json",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("entities[0].type", payload["message"])

    def test_annotate_missing_image_leaves_no_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay.ppm"
            result = _run_motor(
                "vision",
                "annotate",
                str(Path(tmp) / "missing.ppm"),
                "--gamespec",
                str(EXAMPLE_SPEC),
                "--out",
                str(out),
                "--project",
                ".",
                "--json",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())
            payload = _payload(result)
            self.assertFalse(payload["success"])
            self.assertIn("image not found", payload["message"].lower())

    def test_help_paths_exist(self) -> None:
        for args in (
            ("vision", "--help"),
            ("vision", "spec", "--help"),
            ("vision", "spec", "validate", "--help"),
            ("vision", "build-scene", "--help"),
            ("vision", "annotate", "--help"),
        ):
            with self.subTest(args=args):
                result = _run_motor(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
