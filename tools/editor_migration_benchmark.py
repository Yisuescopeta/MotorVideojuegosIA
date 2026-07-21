"""Run the G0 editor-migration reference benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * 0.95) - 1))
    return ordered[index]


def measure(operation: Callable[[], object], *, warmup: int, repeats: int) -> dict[str, object]:
    for _ in range(warmup):
        operation()
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "warmup": warmup,
        "repeats": repeats,
        "samples_ms": [round(sample, 6) for sample in samples],
        "median_ms": round(statistics.median(samples), 6),
        "p95_ms": round(_percentile_95(samples), 6),
        "max_ms": round(max(samples), 6),
    }


def run_benchmark(scene_path: Path, budget_path: Path) -> dict[str, object]:
    scene_bytes = scene_path.read_bytes()
    scene_data = json.loads(scene_bytes.decode("utf-8"))
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    scene = Scene(name=str(scene_data.get("name", "G0ReferenceScene")), data=scene_data)
    registry = create_default_registry()

    warmup = int(budget["warmup"])
    repeats = int(budget["repeats"])
    operations: dict[str, dict[str, object]] = {}
    definitions: dict[str, Callable[[], object]] = {
        "projection_create_world": lambda: scene.create_world(registry),
        "world_serialize": lambda: scene.create_world(registry).serialize(),
        "world_clone": lambda: scene.create_world(registry).clone(),
    }
    for name, operation in definitions.items():
        result = measure(operation, warmup=warmup, repeats=repeats)
        result["budget_p95_ms"] = float(budget["operations"][name]["p95_ms"])
        result["passed"] = float(result["p95_ms"]) <= float(result["budget_p95_ms"])
        operations[name] = result

    return {
        "schema_version": 1,
        "benchmark": "editor_migration_g0",
        "scene": {
            "path": scene_path.as_posix(),
            "sha256": hashlib.sha256(scene_bytes).hexdigest(),
            "entity_count": len(scene.entities_data),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "implementation": sys.implementation.name,
        },
        "operations": operations,
        "passed": all(bool(result["passed"]) for result in operations.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the G0 editor migration benchmark.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = run_benchmark(args.scene.resolve(), args.budget.resolve())
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": report["passed"], "operations": report["operations"]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
