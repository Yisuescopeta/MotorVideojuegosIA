from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.rl import MotorGymEnv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run random Gym-style rollouts and export a JSONL dataset.")
    parser.add_argument("scene", type=str, help="Scene used to create the environment")
    parser.add_argument("--episodes", type=int, default=10, help="Number of episodes to execute")
    parser.add_argument("--max-steps", type=int, default=120, help="Maximum steps per episode")
    parser.add_argument("--seed", type=int, default=123, help="Base seed for reproducible rollouts")
    parser.add_argument("--out", type=str, required=True, help="Output JSONL path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = MotorGymEnv(args.scene, max_steps=args.max_steps)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for episode_index in range(max(1, int(args.episodes))):
            seed = int(args.seed) + episode_index
            observation, info = env.reset(seed=seed)
            terminated = False
            truncated = False
            while not terminated and not truncated:
                action = env.sample_action()
                next_observation, reward, terminated, truncated, step_info = env.step(action)
                handle.write(
                    json.dumps(
                        {
                            "episode": episode_index,
                            "seed": seed,
                            "step": int(step_info["episode_step"]),
                            "action": int(action),
                            "reward": float(reward),
                            "terminated": bool(terminated),
                            "truncated": bool(truncated),
                            "observation": observation,
                            "next_observation": next_observation,
                            "info": step_info,
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )
                observation = next_observation
    env.close()
    print(f"[OK] rollout dataset written: {output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
