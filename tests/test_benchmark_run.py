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
        ):
            first_payload, first_params = build_benchmark_scenario(
                scenario_name,
                backend="legacy_aabb",
                static_count=12,
                dynamic_count=4,
                columns=4,
                spacing=18.0,
                velocity=120.0,
            )
            second_payload, second_params = build_benchmark_scenario(
                scenario_name,
                backend="legacy_aabb",
                static_count=12,
                dynamic_count=4,
                columns=4,
                spacing=18.0,
                velocity=120.0,
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


if __name__ == "__main__":
    unittest.main()
