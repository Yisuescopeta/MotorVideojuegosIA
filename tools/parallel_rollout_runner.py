from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.append(os.getcwd())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel headless rollout runner using subprocess workers.")
    parser.add_argument("scene", type=str)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--worker-timeout", type=int, default=120)
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    worker_count = max(1, min(int(args.workers), int(args.episodes)))
    episodes_per_worker = int(math.ceil(int(args.episodes) / worker_count))
    processes: list[tuple[int, subprocess.Popen[str], Path, int]] = []
    start = time.perf_counter()

    for worker_index in range(worker_count):
        worker_episodes = min(episodes_per_worker, int(args.episodes) - worker_index * episodes_per_worker)
        if worker_episodes <= 0:
            continue
        shard_path = out_root / f"worker_{worker_index:02d}.jsonl"
        summary_path = out_root / f"worker_{worker_index:02d}_summary.json"
        command = [
            sys.executable,
            "tools/scenario_dataset_cli.py",
            "run-episodes",
            args.scene,
            "--episodes",
            str(worker_episodes),
            "--max-steps",
            str(args.max_steps),
            "--seed",
            str(int(args.seed) + worker_index * 1000),
            "--out",
            shard_path.as_posix(),
            "--summary-out",
            summary_path.as_posix(),
            "--env-kind",
            "auto",
        ]
        process = subprocess.Popen(command, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append((worker_index, process, summary_path, worker_episodes))

    failures: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for worker_index, process, summary_path, worker_episodes in processes:
        try:
            stdout, stderr = process.communicate(timeout=int(args.worker_timeout))
            if stdout.strip():
                print(stdout.strip())
            if stderr.strip():
                print(stderr.strip())
            if process.returncode != 0:
                failures.append({"worker": worker_index, "returncode": process.returncode})
                if args.stop_on_error:
                    return process.returncode
                continue
            if summary_path.exists():
                summaries.append(json.loads(summary_path.read_text(encoding="utf-8")))
            else:
                failures.append({"worker": worker_index, "returncode": 2, "reason": "missing_summary"})
        except subprocess.TimeoutExpired:
            process.kill()
            failures.append({"worker": worker_index, "returncode": -1, "reason": "timeout", "episodes": worker_episodes})
            if args.stop_on_error:
                return 1

    elapsed = max(time.perf_counter() - start, 1e-6)
    total_steps = sum(int(item.get("steps", 0)) for item in summaries)
    report = {
        "workers": worker_count,
        "episodes": int(args.episodes),
        "max_steps": int(args.max_steps),
        "elapsed_seconds": elapsed,
        "steps": total_steps,
        "throughput_steps_per_second": total_steps / elapsed,
        "failures": failures,
        "summaries": summaries,
        "resource_limits": {
            "max_workers": worker_count,
            "worker_timeout_seconds": int(args.worker_timeout),
            "memory_strategy": "subprocess_shards",
        },
    }
    report_path = out_root / "parallel_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"[OK] parallel rollout report written: {report_path.as_posix()}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
