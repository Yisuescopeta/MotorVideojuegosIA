import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.debug.profiler import PROFILE_REPORT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _copy_project_file(project_root: Path, relative_path: str) -> Path:
    source = ROOT / relative_path
    target = project_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _read_catalog_snapshot() -> str:
    return (ROOT / ".motor" / "meta" / "asset_catalog.json").read_text(encoding="utf-8")


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


class ProfilerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temp_dir.name) / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = Path(self._temp_dir.name) / "global_state"
        _copy_project_file(self.project_root, "levels/demo_level.json")
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_headless_step_populates_versioned_profiler_report(self) -> None:
        root_editor_state = _read_root_editor_state()
        self.api.reset_profiler("headless_test")
        self.api.step(frames=31)
        report = self.api.get_profiler_report()

        self.assertEqual(report["profile_version"], PROFILE_REPORT_VERSION)
        self.assertEqual(report["run_label"], "headless_test")
        self.assertEqual(report["frames"], 3)
        self.assertIn("frame", report["systems"])
        self.assertIn("avg", report["counters"])
        self.assertIn("max", report["counters"])
        self.assertIn("entities", report["counters"]["avg"])
        self.assertIn("world_json_bytes", report["counters"]["avg"])
        self.assertEqual(report["last_frame"]["memory"]["world_json_bytes"], 0.0)
        self.assertEqual(report["last_frame"]["memory"]["entity_avg_json_bytes"], 0.0)
        self.assertEqual(report["last_frame"]["frame"], 31)
        self.assertIn("timings_ms", report["last_frame"])
        self.assertIn("memory", report["last_frame"])
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_profile_run_cli_writes_stable_report_schema(self) -> None:
        original_catalog = _read_catalog_snapshot()
        original_editor_state = _read_root_editor_state()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "profile_report.json"
            result = _run_module(
                "tools.profile_run",
                "levels/demo_level.json",
                "--project-root",
                self.project_root.as_posix(),
                "--frames",
                "2",
                "--out",
                output_path.as_posix(),
                cwd=self.project_root,
            )
            self.assertIn("[INFO]", result.stdout)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(_read_catalog_snapshot(), original_catalog)
        self.assertEqual(_read_root_editor_state(), original_editor_state)
        self.assertEqual(
            set(report.keys()),
            {"profile_version", "run_label", "frames", "systems", "counters", "last_frame"},
        )
        self.assertEqual(set(report["counters"].keys()), {"avg", "max"})
        self.assertEqual(
            set(report["last_frame"].keys()),
            {"frame", "mode", "backend", "timings_ms", "counters", "memory", "backend_metrics"},
        )
        self.assertEqual(report["profile_version"], PROFILE_REPORT_VERSION)

    def test_engine_api_can_export_debug_geometry_dump(self) -> None:
        root_editor_state = _read_root_editor_state()
        result = self.api.configure_debug_overlay(
            draw_tile_chunks=True,
            primitives=[
                {
                    "kind": "circle",
                    "x": 32.0,
                    "y": 32.0,
                    "radius": 12.0,
                    "color": [255, 0, 0, 255],
                }
            ],
        )
        self.assertTrue(result["success"])
        dump = self.api.get_debug_geometry_dump(320, 180)

        self.assertEqual(dump["pass"], "Debug")
        self.assertEqual(dump["viewport"], {"width": 320, "height": 180})
        self.assertTrue(any(command["debug_kind"] == "circle" for command in dump["commands"]))
        self.assertEqual(_read_root_editor_state(), root_editor_state)


if __name__ == "__main__":
    unittest.main()
