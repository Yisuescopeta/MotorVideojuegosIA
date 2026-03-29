from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.rl.scenario_dataset import generate_scenarios, load_json, replay_episode, run_episode_dataset, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scenario generation, reproducible episode logging, and replay tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate-scenarios")
    generate_parser.add_argument("template_scene")
    generate_parser.add_argument("--count", type=int, default=100)
    generate_parser.add_argument("--seed", type=int, default=123)
    generate_parser.add_argument("--out-dir", required=True)
    generate_parser.add_argument("--spec", default="")

    run_parser = subparsers.add_parser("run-episodes")
    run_parser.add_argument("scene")
    run_parser.add_argument("--episodes", type=int, default=100)
    run_parser.add_argument("--max-steps", type=int, default=120)
    run_parser.add_argument("--seed", type=int, default=123)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--summary-out", default="")
    run_parser.add_argument("--env-kind", choices=("auto", "single", "parallel"), default="auto")

    replay_parser = subparsers.add_parser("replay-episode")
    replay_parser.add_argument("dataset")
    replay_parser.add_argument("--episode-id", required=True)
    replay_parser.add_argument("--out", default="")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "generate-scenarios":
        spec = load_json(args.spec) if args.spec else None
        manifest = generate_scenarios(
            args.template_scene,
            out_dir=args.out_dir,
            count=args.count,
            seed=args.seed,
            spec=spec,
        )
        print(f"[OK] scenarios generated: {len(manifest['scenarios'])}")
        return 0
    if args.command == "run-episodes":
        summary = run_episode_dataset(
            scene_path=args.scene,
            out_jsonl=args.out,
            episodes=args.episodes,
            max_steps=args.max_steps,
            seed=args.seed,
            env_kind=args.env_kind,
        )
        if args.summary_out:
            write_json(args.summary_out, summary)
        print(f"[OK] episodes logged: {summary['completed_episodes']}")
        return 0
    if args.command == "replay-episode":
        report = replay_episode(args.dataset, args.episode_id)
        if args.out:
            write_json(args.out, report)
        else:
            print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0 if report["match"] else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
