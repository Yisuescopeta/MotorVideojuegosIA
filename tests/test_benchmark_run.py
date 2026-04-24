import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.debug.benchmark_runner import BENCHMARK_REPORT_VERSION, run_benchmark
from engine.debug.benchmark_scenarios import build_benchmark_scenario

ROOT = Path(__file__).resolve().parents[1]

NEW_SYNTHETIC_SCENARIOS = (
    "many_transform_entities",
    "many_sprite_entities",
    "many_ui_buttons",
    "huge_tilemap",
    "transform_edit_stress",
    "play_mode_clone_stress",
)


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


class BenchmarkRunTests(unittest.TestCase):
    def test_benchmark_scenarios_are_deterministic(self) -> None:
        for scenario_name in (
            "many_static_colliders",
            "one_dynamic_many_static",
            "many_dynamic_and_static",
            *NEW_SYNTHETIC_SCENARIOS,
        ):
            first_payload, first_params = build_benchmark_scenario(
                scenario_name,
                backend="legacy_aabb",
                static_count=12,
                dynamic_count=4,
                entity_count=12,
                columns=4,
                spacing=18.0,
                velocity=120.0,
                tilemap_width=4,
                tilemap_height=3,
            )
            second_payload, second_params = build_benchmark_scenario(
                scenario_name,
                backend="legacy_aabb",
                static_count=12,
                dynamic_count=4,
                entity_count=12,
                columns=4,
                spacing=18.0,
                velocity=120.0,
                tilemap_width=4,
                tilemap_height=3,
            )

            self.assertEqual(first_payload, second_payload)
            self.assertEqual(first_params, second_params)

    def test_benchmark_runner_returns_expected_json_schema(self) -> None:
        report = run_benchmark(
            scenario="many_static_colliders",
            backend="legacy_aabb",
            frames=4,
            static_count=9,
            columns=3,
            spacing=20.0,
        )

        self.assertEqual(report["benchmark_version"], BENCHMARK_REPORT_VERSION)
        self.assertEqual(report["source"], "scenario")
        self.assertEqual(report["scenario_name"], "many_static_colliders")
        self.assertEqual(report["frames_requested"], 4)
        self.assertEqual(report["profiler_frames_recorded"], 4)
        self.assertIn("profiler_report", report)
        self.assertIn("summary", report)
        self.assertIn("last_sample", report)
        self.assertIn("operations", report)
        self.assertIn("load_level", report["operations"])
        self.assertEqual(
            set(report["summary"].keys()),
            {
                "frame_avg_ms",
                "frame_max_ms",
                "gameplay_avg_ms",
                "gameplay_max_ms",
                "candidate_solids_avg",
                "candidate_solids_max",
                "collision_candidates_avg",
                "collision_candidates_max",
                "collision_pairs_tested_avg",
                "collision_pairs_tested_max",
                "collision_hits_avg",
                "collision_hits_max",
                "entities_avg",
                "entities_max",
                "draw_calls_avg",
                "draw_calls_max",
                "render_entities_avg",
                "render_entities_max",
            },
        )

    def test_new_synthetic_benchmark_scenarios_run_headless(self) -> None:
        for scenario_name in NEW_SYNTHETIC_SCENARIOS:
            with self.subTest(scenario=scenario_name):
                report = run_benchmark(
                    scenario=scenario_name,
                    backend="legacy_aabb",
                    frames=1,
                    entity_count=6,
                    static_count=6,
                    dynamic_count=2,
                    columns=3,
                    spacing=18.0,
                    velocity=120.0,
                    tilemap_width=4,
                    tilemap_height=3,
                )

                self.assertEqual(report["scenario_name"], scenario_name)
                self.assertEqual(report["frames_requested"], 1)
                self.assertEqual(report["profiler_frames_recorded"], 1)
                self.assertIn("load_level", report["operations"])
                self.assertGreaterEqual(report["operations"]["load_level"]["ms"], 0.0)

    def test_transform_edit_stress_reports_edit_operation(self) -> None:
        report = run_benchmark(
            scenario="transform_edit_stress",
            backend="legacy_aabb",
            mode="edit",
            frames=1,
            entity_count=8,
            columns=4,
            spacing=12.0,
        )

        operation = report["operations"]["transform_edit"]
        self.assertTrue(operation["success"])
        self.assertEqual(operation["target_entity"], "Entity_7")
        self.assertEqual(operation["field"], "Transform.x")
        self.assertGreaterEqual(operation["ms"], 0.0)

    def test_play_mode_clone_stress_reports_play_transitions(self) -> None:
        report = run_benchmark(
            scenario="play_mode_clone_stress",
            backend="legacy_aabb",
            mode="play",
            frames=1,
            entity_count=8,
            columns=4,
            spacing=12.0,
        )

        self.assertIn("edit_to_play", report["operations"])
        self.assertIn("play_to_edit", report["operations"])
        self.assertGreaterEqual(report["operations"]["edit_to_play"]["ms"], 0.0)
        self.assertGreaterEqual(report["operations"]["play_to_edit"]["ms"], 0.0)

    def test_sprite_benchmark_reports_headless_render_preparation(self) -> None:
        report = run_benchmark(
            scenario="many_sprite_entities",
            backend="legacy_aabb",
            frames=1,
            entity_count=8,
            columns=4,
            spacing=12.0,
        )

        operation = report["operations"]["render_preparation"]
        self.assertGreaterEqual(operation["ms"], 0.0)
        self.assertGreater(operation["stats"]["render_entities"], 0)
        self.assertTrue(operation["stats"]["spatial_culling_enabled"])
        self.assertLess(operation["stats"]["spatial_visible_entities"], operation["stats"]["spatial_total_entities"])
        self.assertEqual(operation["visible_entities"], operation["stats"]["spatial_visible_entities"])
        self.assertEqual(operation["total_entities"], operation["stats"]["spatial_total_entities"])

    def test_huge_tilemap_benchmark_reports_visible_chunk_reduction(self) -> None:
        report = run_benchmark(
            scenario="huge_tilemap",
            backend="legacy_aabb",
            frames=1,
            tilemap_width=128,
            tilemap_height=128,
        )

        stats = report["operations"]["render_preparation"]["stats"]
        self.assertGreater(stats["tilemap_total_chunks"], 0)
        self.assertGreater(stats["tilemap_visible_chunks"], 0)
        self.assertLess(stats["tilemap_visible_chunks"], stats["tilemap_total_chunks"])
        self.assertEqual(stats["tilemap_chunks"], stats["tilemap_visible_chunks"])

    def test_benchmark_runner_does_not_enable_deep_profiling_by_default(self) -> None:
        report = run_benchmark(
            scenario="one_dynamic_many_static",
            backend="legacy_aabb",
            frames=4,
            static_count=10,
            columns=5,
            spacing=18.0,
            velocity=120.0,
        )

        self.assertEqual(report["profiler_frames_recorded"], 4)
        self.assertEqual(report["last_sample"]["memory"]["world_json_bytes"], 0.0)
        self.assertEqual(report["last_sample"]["memory"]["entity_avg_json_bytes"], 0.0)

    def test_benchmark_runner_collects_runtime_metrics_headless_without_overlay(self) -> None:
        report = run_benchmark(
            scenario="one_dynamic_many_static",
            backend="legacy_aabb",
            frames=4,
            static_count=12,
            columns=4,
            spacing=18.0,
            velocity=140.0,
        )

        self.assertEqual(report["profiler_frames_recorded"], 4)
        self.assertGreater(report["summary"]["entities_avg"], 0.0)
        self.assertIn("physics_candidate_solids", report["profiler_report"]["counters"]["avg"])

    def test_benchmark_runner_can_enable_deep_profiling_when_requested(self) -> None:
        report = run_benchmark(
            scenario="many_dynamic_and_static",
            backend="legacy_aabb",
            frames=4,
            static_count=8,
            dynamic_count=4,
            columns=4,
            spacing=18.0,
            velocity=140.0,
            deep=True,
        )

        self.assertEqual(report["profiler_frames_recorded"], 4)
        self.assertGreater(report["last_sample"]["memory"]["world_json_bytes"], 0.0)
        self.assertGreater(report["last_sample"]["memory"]["entity_avg_json_bytes"], 0.0)

    def test_benchmark_cli_writes_json_report_for_synthetic_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "benchmark_report.json"
            result = _run_module(
                "tools.benchmark_run",
                "--scenario",
                "one_dynamic_many_static",
                "--backend",
                "legacy_aabb",
                "--frames",
                "3",
                "--static-count",
                "10",
                "--columns",
                "5",
                "--spacing",
                "18",
                "--velocity",
                "120",
                "--out",
                output_path.as_posix(),
                cwd=ROOT,
            )
            self.assertIn('"benchmark_version"', result.stdout)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["scenario_name"], "one_dynamic_many_static")
        self.assertEqual(report["frames_requested"], 3)
        self.assertEqual(report["profiler_frames_recorded"], 3)
        self.assertIn("summary", report)

    def test_benchmark_cli_accepts_entity_count_for_new_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "benchmark_report.json"
            result = _run_module(
                "tools.benchmark_run",
                "--scenario",
                "many_transform_entities",
                "--backend",
                "legacy_aabb",
                "--mode",
                "edit",
                "--frames",
                "1",
                "--entity-count",
                "5",
                "--columns",
                "5",
                "--out",
                output_path.as_posix(),
                cwd=ROOT,
            )
            self.assertIn('"scenario_name": "many_transform_entities"', result.stdout)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["scenario_name"], "many_transform_entities")
        self.assertEqual(report["parameters"]["entity_count"], 5)
        self.assertIn("render_preparation", report["operations"])


if __name__ == "__main__":
    unittest.main()
