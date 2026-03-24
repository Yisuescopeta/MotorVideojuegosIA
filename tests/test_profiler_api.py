import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI
from engine.debug.profiler import PROFILE_REPORT_VERSION


class ProfilerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = EngineAPI(project_root=os.getcwd())
        self.api.load_level("levels/demo_level.json")

    def test_headless_step_populates_versioned_profiler_report(self) -> None:
        self.api.reset_profiler("headless_test")
        self.api.step(frames=3)
        report = self.api.get_profiler_report()

        self.assertEqual(report["profile_version"], PROFILE_REPORT_VERSION)
        self.assertEqual(report["run_label"], "headless_test")
        self.assertEqual(report["frames"], 3)
        self.assertIn("frame", report["systems"])
        self.assertIn("avg", report["counters"])
        self.assertIn("max", report["counters"])
        self.assertIn("entities", report["counters"]["avg"])
        self.assertIn("world_json_bytes", report["counters"]["avg"])
        self.assertEqual(report["last_frame"]["frame"], 3)
        self.assertIn("timings_ms", report["last_frame"])
        self.assertIn("memory", report["last_frame"])

    def test_profile_run_cli_writes_stable_report_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "profile_report.json"
            exit_code = os.system(
                f'py -3 tools/profile_run.py levels/demo_level.json --frames 2 --out "{output_path.as_posix()}"'
            )
            self.assertEqual(exit_code, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
