from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from engine.debug.benchmark_runner import run_benchmark

BENCHMARK_SUITE_VERSION = 1


BenchmarkRunner = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class Threshold:
    metric: str
    soft_ms: float
    hard_ms: float


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    scenario: str
    mode: str
    frames: int
    parameters: dict[str, Any]
    quick_parameters: dict[str, Any]
    required_operations: tuple[str, ...]
    thresholds: tuple[Threshold, ...]
    expected_parameter: str

    def resolved_parameters(self, *, quick: bool) -> dict[str, Any]:
        return {**self.parameters, **(self.quick_parameters if quick else {})}


SUITE_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        name="transform_edit_stress_10k",
        scenario="transform_edit_stress",
        mode="edit",
        frames=1,
        parameters={"entity_count": 10000, "columns": 100},
        quick_parameters={},
        required_operations=("load_level", "transform_edit"),
        thresholds=(
            Threshold("operations.load_level.ms", soft_ms=15000.0, hard_ms=60000.0),
            Threshold("operations.transform_edit.ms", soft_ms=50.0, hard_ms=500.0),
            Threshold("operations.render_preparation.ms", soft_ms=3000.0, hard_ms=15000.0),
            Threshold("summary.frame_max_ms", soft_ms=1000.0, hard_ms=5000.0),
        ),
        expected_parameter="entity_count",
    ),
    BenchmarkCase(
        name="play_mode_clone_stress_10k",
        scenario="play_mode_clone_stress",
        mode="play",
        frames=1,
        parameters={"entity_count": 10000, "columns": 100},
        quick_parameters={},
        required_operations=("load_level", "edit_to_play", "play_to_edit"),
        thresholds=(
            Threshold("operations.load_level.ms", soft_ms=30000.0, hard_ms=120000.0),
            Threshold("operations.edit_to_play.ms", soft_ms=10000.0, hard_ms=60000.0),
            Threshold("operations.play_to_edit.ms", soft_ms=15000.0, hard_ms=90000.0),
            Threshold("operations.render_preparation.ms", soft_ms=5000.0, hard_ms=30000.0),
            Threshold("summary.frame_max_ms", soft_ms=1000.0, hard_ms=5000.0),
        ),
        expected_parameter="entity_count",
    ),
    BenchmarkCase(
        name="many_static_colliders",
        scenario="many_static_colliders",
        mode="play",
        frames=5,
        parameters={"static_count": 2000, "columns": 100},
        quick_parameters={"static_count": 1000, "columns": 50},
        required_operations=("load_level", "edit_to_play", "play_to_edit"),
        thresholds=(
            Threshold("operations.load_level.ms", soft_ms=10000.0, hard_ms=60000.0),
            Threshold("operations.edit_to_play.ms", soft_ms=5000.0, hard_ms=30000.0),
            Threshold("operations.play_to_edit.ms", soft_ms=10000.0, hard_ms=60000.0),
            Threshold("summary.frame_max_ms", soft_ms=2000.0, hard_ms=10000.0),
        ),
        expected_parameter="static_count",
    ),
    BenchmarkCase(
        name="many_sprite_entities_headless",
        scenario="many_sprite_entities",
        mode="play",
        frames=5,
        parameters={"entity_count": 5000, "columns": 100},
        quick_parameters={"entity_count": 2000, "columns": 50},
        required_operations=("load_level", "edit_to_play", "play_to_edit", "render_preparation"),
        thresholds=(
            Threshold("operations.load_level.ms", soft_ms=20000.0, hard_ms=90000.0),
            Threshold("operations.edit_to_play.ms", soft_ms=8000.0, hard_ms=45000.0),
            Threshold("operations.play_to_edit.ms", soft_ms=12000.0, hard_ms=60000.0),
            Threshold("operations.render_preparation.ms", soft_ms=4000.0, hard_ms=20000.0),
            Threshold("summary.frame_max_ms", soft_ms=1000.0, hard_ms=5000.0),
        ),
        expected_parameter="entity_count",
    ),
)


def _metric_value(payload: dict[str, Any], path: str) -> float | None:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def _evaluate_thresholds(report: dict[str, Any], thresholds: tuple[Threshold, ...]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    failures: list[str] = []

    for threshold in thresholds:
        value = _metric_value(report, threshold.metric)
        if value is None:
            failures.append(f"Missing metric: {threshold.metric}")
            checks.append(
                {
                    "metric": threshold.metric,
                    "value": None,
                    "soft_ms": threshold.soft_ms,
                    "hard_ms": threshold.hard_ms,
                    "status": "failed",
                }
            )
            continue

        status = "passed"
        if value > threshold.hard_ms:
            status = "failed"
            failures.append(f"{threshold.metric}={value:.3f}ms exceeded hard threshold {threshold.hard_ms:.3f}ms")
        elif value > threshold.soft_ms:
            status = "warning"
            warnings.append(f"{threshold.metric}={value:.3f}ms exceeded soft threshold {threshold.soft_ms:.3f}ms")

        checks.append(
            {
                "metric": threshold.metric,
                "value": value,
                "soft_ms": threshold.soft_ms,
                "hard_ms": threshold.hard_ms,
                "status": status,
            }
        )

    return checks, warnings, failures


def _validate_report(case: BenchmarkCase, report: dict[str, Any], *, expected_count: int) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []

    if report.get("scenario_name") != case.scenario:
        failures.append(f"Expected scenario {case.scenario}, got {report.get('scenario_name')!r}")
    if report.get("mode") != case.mode:
        failures.append(f"Expected mode {case.mode}, got {report.get('mode')!r}")
    if int(report.get("frames_requested", 0)) != case.frames:
        failures.append(f"Expected {case.frames} requested frames, got {report.get('frames_requested')!r}")
    if int(report.get("profiler_frames_recorded", 0)) != case.frames:
        failures.append(f"Expected {case.frames} profiler frames, got {report.get('profiler_frames_recorded')!r}")

    parameters = report.get("parameters", {})
    actual_count = int(parameters.get(case.expected_parameter, -1))
    if actual_count != expected_count:
        failures.append(f"Expected {case.expected_parameter}={expected_count}, got {actual_count}")

    operations = report.get("operations", {})
    for operation in case.required_operations:
        if operation not in operations:
            failures.append(f"Missing required operation: {operation}")

    if case.scenario == "transform_edit_stress":
        transform_edit = operations.get("transform_edit", {})
        if not bool(transform_edit.get("success", False)):
            failures.append("transform_edit operation did not report success")

    if case.scenario == "many_sprite_entities":
        render_stats = operations.get("render_preparation", {}).get("stats", {})
        if not bool(render_stats.get("spatial_culling_enabled", False)):
            warnings.append("many_sprite_entities did not report spatial culling enabled")
        if int(render_stats.get("render_entities", 0)) <= 0:
            failures.append("many_sprite_entities did not report visible render entities")

    return warnings, failures


def _run_case(case: BenchmarkCase, *, quick: bool, backend: str, benchmark_runner: BenchmarkRunner) -> dict[str, Any]:
    parameters = case.resolved_parameters(quick=quick)
    expected_count = int(parameters[case.expected_parameter])
    started = time.perf_counter()
    try:
        report = benchmark_runner(
            scenario=case.scenario,
            backend=backend,
            mode=case.mode,
            frames=case.frames,
            **parameters,
        )
        duration_ms = (time.perf_counter() - started) * 1000.0
        validation_warnings, validation_failures = _validate_report(case, report, expected_count=expected_count)
        checks, threshold_warnings, threshold_failures = _evaluate_thresholds(report, case.thresholds)
        warnings = [*validation_warnings, *threshold_warnings]
        failures = [*validation_failures, *threshold_failures]
        status = "failed" if failures else "warning" if warnings else "passed"
        return {
            "name": case.name,
            "scenario": case.scenario,
            "mode": case.mode,
            "frames": case.frames,
            "parameters": parameters,
            "duration_ms": duration_ms,
            "status": status,
            "threshold_checks": checks,
            "warnings": warnings,
            "failures": failures,
            "report": report,
        }
    except Exception as exc:  # pragma: no cover - exact exception type is runner-owned
        duration_ms = (time.perf_counter() - started) * 1000.0
        return {
            "name": case.name,
            "scenario": case.scenario,
            "mode": case.mode,
            "frames": case.frames,
            "parameters": parameters,
            "duration_ms": duration_ms,
            "status": "failed",
            "threshold_checks": [],
            "warnings": [],
            "failures": [f"Benchmark crashed: {type(exc).__name__}: {exc}"],
            "report": None,
        }


def run_suite(
    *,
    quick: bool = False,
    backend: str = "legacy_aabb",
    fail_on_warning: bool = False,
    benchmark_runner: BenchmarkRunner | None = None,
) -> dict[str, Any]:
    selected_runner = benchmark_runner or run_benchmark
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    started = time.perf_counter()
    results = [
        _run_case(case, quick=quick, backend=backend, benchmark_runner=selected_runner)
        for case in SUITE_CASES
    ]
    failed = sum(1 for result in results if result["status"] == "failed")
    warnings = sum(1 for result in results if result["warnings"])
    passed = sum(1 for result in results if result["status"] == "passed")
    status = "failed" if failed else "warning" if warnings else "passed"
    if fail_on_warning and warnings and not failed:
        status = "failed"

    return {
        "suite_version": BENCHMARK_SUITE_VERSION,
        "quick": bool(quick),
        "backend": backend,
        "fail_on_warning": bool(fail_on_warning),
        "started_at": started_at,
        "duration_ms": (time.perf_counter() - started) * 1000.0,
        "status": status,
        "summary": {
            "total": len(results),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        },
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CI-friendly benchmark suite with soft thresholds.")
    parser.add_argument("--quick", action="store_true", help="Use smaller CI-friendly workloads where possible.")
    parser.add_argument("--out", type=str, default="", help="Optional aggregate JSON output path.")
    parser.add_argument("--backend", choices=("legacy_aabb", "box2d"), default="legacy_aabb")
    parser.add_argument("--fail-on-warning", action="store_true", help="Exit non-zero when soft thresholds warn.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_suite(
        quick=bool(args.quick),
        backend=str(args.backend),
        fail_on_warning=bool(args.fail_on_warning),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=True)
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
