from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())

from engine.rl import MotorParallelEnv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run random multiagent rollouts and export JSONL transitions.")
    parser.add_argument("scene", type=str, help="Scene used to create the multiagent environment")
    parser.add_argument("--episodes", type=int, default=5, help="Number of episodes")
    parser.add_argument("--max-steps", type=int, default=80, help="Maximum steps per episode")
    parser.add_argument("--seed", type=int, default=123, help="Base seed")
    parser.add_argument("--out", type=str, required=True, help="Output JSONL path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = MotorParallelEnv(args.scene, max_steps=args.max_steps)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for episode in range(max(1, int(args.episodes))):
            obs, infos = env.reset(seed=int(args.seed) + episode)
            while env.agents:
                actions = env.sample_actions()
                next_obs, rewards, terminations, truncations, step_infos = env.step(actions)
                handle.write(
                    json.dumps(
                        {
                            "episode": episode,
                            "agents": list(actions.keys()),
                            "actions": actions,
                            "observations": obs,
                            "next_observations": next_obs,
                            "rewards": rewards,
                            "terminations": terminations,
                            "truncations": truncations,
                            "infos": step_infos,
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                obs = next_obs
    env.close()
    print(f"[OK] multiagent rollout dataset written: {output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
