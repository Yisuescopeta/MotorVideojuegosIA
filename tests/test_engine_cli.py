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


if __name__ == "__main__":
    unittest.main()
