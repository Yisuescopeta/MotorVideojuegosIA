import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools import benchmark_suite

ROOT = Path(__file__).resolve().parents[1]


def _fake_report(**kwargs):
    scenario = kwargs["scenario"]
    parameters = {
        "entity_count": int(kwargs.get("entity_count", 0)),
        "static_count": int(kwargs.get("static_count", 0)),
        "columns": int(kwargs.get("columns", 0)),
    }
    operations = {
        "load_level": {"ms": 1.0},
        "edit_to_play": {"ms": 1.0},
        "play_to_edit": {"ms": 1.0},
        "render_preparation": {
            "ms": 1.0,
            "stats": {
                "render_entities": max(1, int(kwargs.get("entity_count", kwargs.get("static_count", 1)))),
                "spatial_culling_enabled": True,
            },
        },
    }
    if scenario == "transform_edit_stress":
        operations["transform_edit"] = {
            "ms": 1.0,
            "success": True,
            "target_entity": f"Entity_{int(kwargs.get('entity_count', 1)) - 1}",
            "field": "Transform.x",
        }
    return {
        "scenario_name": scenario,
        "mode": kwargs["mode"],
        "frames_requested": kwargs["frames"],
        "profiler_frames_recorded": kwargs["frames"],
        "parameters": parameters,
        "operations": operations,
        "summary": {"frame_max_ms": 1.0},
    }


class BenchmarkSuiteTests(unittest.TestCase):
    def test_required_scenarios_are_present(self) -> None:
        scenarios = {case.scenario for case in benchmark_suite.SUITE_CASES}

        self.assertIn("transform_edit_stress", scenarios)
        self.assertIn("play_mode_clone_stress", scenarios)
        self.assertIn("many_static_colliders", scenarios)
        self.assertIn("many_sprite_entities", scenarios)

    def test_quick_uses_smaller_profile_for_non_10k_cases(self) -> None:
        report = benchmark_suite.run_suite(quick=True, benchmark_runner=_fake_report)
        by_scenario = {result["scenario"]: result["parameters"] for result in report["results"]}

        self.assertEqual(by_scenario["transform_edit_stress"]["entity_count"], 10000)
        self.assertEqual(by_scenario["play_mode_clone_stress"]["entity_count"], 10000)
        self.assertEqual(by_scenario["many_static_colliders"]["static_count"], 1000)
        self.assertEqual(by_scenario["many_sprite_entities"]["entity_count"], 2000)
        self.assertEqual(report["status"], "passed")

    def test_soft_threshold_warning_does_not_fail_by_default(self) -> None:
        def runner(**kwargs):
            report = _fake_report(**kwargs)
            report["operations"]["load_level"]["ms"] = 20000.0
            return report

        report = benchmark_suite.run_suite(quick=True, benchmark_runner=runner)

        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertGreater(report["summary"]["warnings"], 0)

    def test_fail_on_warning_turns_warning_into_failed_suite(self) -> None:
        def runner(**kwargs):
            report = _fake_report(**kwargs)
            report["operations"]["load_level"]["ms"] = 20000.0
            return report

        report = benchmark_suite.run_suite(quick=True, fail_on_warning=True, benchmark_runner=runner)

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["summary"]["failed"], 0)

    def test_hard_threshold_failure_returns_failed_status(self) -> None:
        def runner(**kwargs):
            report = _fake_report(**kwargs)
            report["operations"]["load_level"]["ms"] = 999999.0
            return report

        report = benchmark_suite.run_suite(quick=True, benchmark_runner=runner)

        self.assertEqual(report["status"], "failed")
        self.assertGreater(report["summary"]["failed"], 0)

    def test_main_exit_code_matches_threshold_policy(self) -> None:
        original_runner = benchmark_suite.run_benchmark

        def soft_runner(**kwargs):
            report = _fake_report(**kwargs)
            report["operations"]["load_level"]["ms"] = 20000.0
            return report

        def hard_runner(**kwargs):
            report = _fake_report(**kwargs)
            report["operations"]["load_level"]["ms"] = 999999.0
            return report

        try:
            benchmark_suite.run_benchmark = soft_runner
            with redirect_stdout(StringIO()):
                self.assertEqual(benchmark_suite.main(["--quick"]), 0)
            with redirect_stdout(StringIO()):
                self.assertEqual(benchmark_suite.main(["--quick", "--fail-on-warning"]), 1)

            benchmark_suite.run_benchmark = hard_runner
            with redirect_stdout(StringIO()):
                self.assertEqual(benchmark_suite.main(["--quick"]), 1)
        finally:
            benchmark_suite.run_benchmark = original_runner

    def test_cli_writes_aggregate_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "suite.json"
            env = os.environ.copy()
            python_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from tools import benchmark_suite; "
                        "benchmark_suite.run_benchmark = lambda **kwargs: {"
                        "'scenario_name': kwargs['scenario'], 'mode': kwargs['mode'], "
                        "'frames_requested': kwargs['frames'], 'profiler_frames_recorded': kwargs['frames'], "
                        "'parameters': {'entity_count': int(kwargs.get('entity_count', 0)), "
                        "'static_count': int(kwargs.get('static_count', 0)), 'columns': int(kwargs.get('columns', 0))}, "
                        "'operations': {'load_level': {'ms': 1.0}, 'edit_to_play': {'ms': 1.0}, "
                        "'play_to_edit': {'ms': 1.0}, 'transform_edit': {'ms': 1.0, 'success': True}, "
                        "'render_preparation': {'ms': 1.0, 'stats': {'render_entities': 1, 'spatial_culling_enabled': True}}}, "
                        "'summary': {'frame_max_ms': 1.0}}; "
                        f"raise SystemExit(benchmark_suite.main(['--quick', '--out', r'{output_path.as_posix()}']))"
                    ),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["suite_version"], benchmark_suite.BENCHMARK_SUITE_VERSION)
        self.assertTrue(report["quick"])
        self.assertEqual(report["summary"]["total"], len(benchmark_suite.SUITE_CASES))
        self.assertEqual(len(report["results"]), len(benchmark_suite.SUITE_CASES))


if __name__ == "__main__":
    unittest.main()
