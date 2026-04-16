from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.debug.benchmark_runner import run_benchmark
from engine.debug.benchmark_scenarios import SCENARIO_BUILDERS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reproducible headless benchmarks and export comparable metrics.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--scenario", choices=sorted(SCENARIO_BUILDERS.keys()), help="Synthetic benchmark scenario name.")
    source_group.add_argument("--scene", type=str, help="Existing scene path to benchmark.")
    parser.add_argument("--project-root", type=str, default="", help="Project root used to resolve relative scene paths.")
    parser.add_argument("--backend", choices=("legacy_aabb", "box2d"), default="legacy_aabb")
    parser.add_argument("--mode", choices=("play", "edit"), default="play")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--dt", type=float, default=1.0 / 60.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--out", type=str, default="", help="Optional JSON output path.")
    parser.add_argument("--static-count", type=int, default=100)
    parser.add_argument("--dynamic-count", type=int, default=12)
    parser.add_argument("--columns", type=int, default=10)
    parser.add_argument("--spacing", type=float, default=24.0)
    parser.add_argument("--velocity", type=float, default=160.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_benchmark(
        scenario=args.scenario,
        scene_path=args.scene,
        project_root=args.project_root or None,
        backend=args.backend,
        mode=args.mode,
        frames=args.frames,
        dt=args.dt,
        seed=args.seed,
        deep=bool(args.deep),
        static_count=args.static_count,
        dynamic_count=args.dynamic_count,
        columns=args.columns,
        spacing=args.spacing,
        velocity=args.velocity,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=True)
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
