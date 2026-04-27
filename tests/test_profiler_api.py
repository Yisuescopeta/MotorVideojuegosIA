import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def _assert_memory_diagnostic_counters(test_case: unittest.TestCase, report: dict) -> None:
    avg_counters = report["counters"]["avg"]
    last_counters = report["last_frame"]["counters"]
    for field in (
        "components",
        "component_count",
        "gc_gen0_count",
        "gc_gen1_count",
        "gc_gen2_count",
        "textures_loaded",
        "texture_load_failures",
        "texture_cache_approx_bytes",
        "render_sorted_entities_cache_size",
        "render_graph_pass_cache_size",
        "tilemap_chunk_cache_size",
    ):
        test_case.assertIn(field, avg_counters)
        test_case.assertIn(field, last_counters)


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
        assert self.api.game is not None
        self.game = self.api.game

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_reset_profiler_does_not_enable_runtime_metrics(self) -> None:
        self.game.enable_runtime_metrics = False
        self.game.enable_deep_profiling = True
        self.game._metrics_frame_index = 9

        self.api.reset_profiler("headless_test")

        self.assertFalse(self.game.enable_runtime_metrics)
        self.assertFalse(self.game.enable_deep_profiling)
        self.assertEqual(self.game._metrics_frame_index, 0)

    def test_play_does_not_enable_runtime_metrics(self) -> None:
        self.game.enable_runtime_metrics = False

        self.api.play()

        self.assertFalse(self.game.enable_runtime_metrics)

    def test_headless_step_skips_metrics_when_overlay_and_runtime_metrics_are_disabled(self) -> None:
        self.game.show_performance_overlay = False
        self.game.enable_runtime_metrics = False
        root_editor_state = _read_root_editor_state()
        self.api.reset_profiler("headless_test")
        self.api.step(frames=31)
        report = self.api.get_profiler_report()

        self.assertEqual(report["profile_version"], PROFILE_REPORT_VERSION)
        self.assertEqual(report["run_label"], "headless_test")
        self.assertEqual(report["frames"], 0)
        self.assertEqual(report["systems"], {})
        self.assertEqual(report["counters"]["avg"], {})
        self.assertEqual(report["counters"]["max"], {})
        self.assertEqual(report["last_frame"], {})
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_headless_step_collects_cheap_metrics_when_overlay_is_enabled(self) -> None:
        self.game.show_performance_overlay = True
        self.game.enable_runtime_metrics = False

        self.api.reset_profiler("overlay_test")
        self.api.step(frames=31)
        report = self.api.get_profiler_report()

        self.assertEqual(report["run_label"], "overlay_test")
        self.assertEqual(report["frames"], 3)
        self.assertIn("frame", report["systems"])
        self.assertIn("avg", report["counters"])
        self.assertIn("max", report["counters"])
        self.assertIn("entities", report["counters"]["avg"])
        _assert_memory_diagnostic_counters(self, report)
        self.assertIn("world_json_bytes", report["counters"]["avg"])
        self.assertEqual(report["last_frame"]["memory"]["world_json_bytes"], 0.0)
        self.assertEqual(report["last_frame"]["memory"]["entity_avg_json_bytes"], 0.0)
        self.assertEqual(report["last_frame"]["frame"], 31)
        self.assertIn("timings_ms", report["last_frame"])
        self.assertIn("memory", report["last_frame"])

    def test_headless_step_populates_versioned_profiler_report_when_runtime_metrics_are_explicitly_enabled(self) -> None:
        root_editor_state = _read_root_editor_state()
        self.game.enable_runtime_metrics = True

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
        _assert_memory_diagnostic_counters(self, report)
        self.assertIn("world_json_bytes", report["counters"]["avg"])
        self.assertEqual(report["last_frame"]["memory"]["world_json_bytes"], 0.0)
        self.assertEqual(report["last_frame"]["memory"]["entity_avg_json_bytes"], 0.0)
        self.assertEqual(report["last_frame"]["frame"], 31)
        self.assertIn("timings_ms", report["last_frame"])
        self.assertIn("memory", report["last_frame"])
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_headless_step_collects_deep_metrics_only_when_explicitly_enabled(self) -> None:
        self.game.enable_runtime_metrics = True

        self.api.reset_profiler("deep_test")
        self.assertFalse(self.game.enable_deep_profiling)

        self.game.enable_deep_profiling = True
        self.api.step(frames=31)
        report = self.api.get_profiler_report()

        self.assertEqual(report["run_label"], "deep_test")
        self.assertEqual(report["frames"], 3)
        self.assertGreater(report["last_frame"]["memory"]["world_json_bytes"], 0.0)
        self.assertGreater(report["last_frame"]["memory"]["entity_avg_json_bytes"], 0.0)

    def test_profiler_report_succeeds_when_psutil_is_missing(self) -> None:
        self.game.enable_runtime_metrics = True

        real_import_module = __import__("importlib").import_module

        def import_without_psutil(name: str, package: str | None = None):
            if name == "psutil":
                raise ModuleNotFoundError(name)
            return real_import_module(name, package)

        with mock.patch("engine.app.debug_tools_controller.importlib.import_module", side_effect=import_without_psutil):
            self.api.reset_profiler("no_psutil_test")
            self.api.step(frames=31)
            report = self.api.get_profiler_report()

        self.assertEqual(report["run_label"], "no_psutil_test")
        self.assertEqual(report["frames"], 3)
        self.assertIn("world_json_bytes", report["last_frame"]["memory"])
        self.assertNotIn("process_rss_bytes", report["last_frame"]["memory"])
        self.assertNotIn("process_vms_bytes", report["last_frame"]["memory"])

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
