from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from engine.api import EngineAPI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic profile session and export metrics to JSON.")
    parser.add_argument("scene", type=str, help="Scene JSON path to load before profiling")
    parser.add_argument("--project-root", type=str, default="", help="Project root used to resolve relative scene paths")
    parser.add_argument("--frames", type=int, default=600, help="Number of frames to execute")
    parser.add_argument("--out", type=str, required=True, help="Output JSON path")
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed")
    parser.add_argument("--mode", choices=("play", "edit"), default="play", help="Profiling mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else Path(os.getcwd()).resolve()
    scene_path = Path(args.scene)
    if not scene_path.is_absolute():
        scene_path = project_root / scene_path
    api = EngineAPI(project_root=project_root.as_posix())
    api.load_level(scene_path.as_posix())
    if args.seed is not None:
        api.set_seed(args.seed)
    api.reset_profiler(run_label=f"profile:{scene_path.name}:{args.mode}")
    if api.game is not None:
        api.game.enable_runtime_metrics = True
    if args.mode == "play":
        api.play()
    api.step(frames=max(1, int(args.frames)))
    report = api.get_profiler_report()
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"[INFO] Profile report written to: {output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
