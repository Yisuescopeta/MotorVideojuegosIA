import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.rl import ACTION_SPEC_VERSION, OBSERVATION_SPEC_VERSION, MotorGymEnv

ROOT = Path(__file__).resolve().parents[1]


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class MotorGymEnvTests(unittest.TestCase):
    def test_reset_and_step_follow_gym_contract(self) -> None:
        env = MotorGymEnv("levels/platformer_test_scene.json", max_steps=10)
        observation, info = env.reset(seed=123)

        self.assertEqual(info["action_spec_version"], ACTION_SPEC_VERSION)
        self.assertEqual(info["observation_spec_version"], OBSERVATION_SPEC_VERSION)
        self.assertIn("self_position", observation)
        self.assertEqual(len(observation["self_position"]), 2)

        next_observation, reward, terminated, truncated, step_info = env.step(2)
        self.assertIsInstance(reward, float)
        self.assertIsInstance(terminated, bool)
        self.assertIsInstance(truncated, bool)
        self.assertEqual(step_info["episode_step"], 1)
        self.assertEqual(next_observation["last_action"], [1.0, 0.0, 0.0, 0.0])
        env.close()

    def test_right_action_advances_agent(self) -> None:
        env = MotorGymEnv("levels/platformer_test_scene.json", max_steps=30)
        observation, _ = env.reset(seed=5)
        start_x = observation["self_position"][0]
        for _ in range(5):
            observation, _, terminated, truncated, _ = env.step(2)
            self.assertFalse(terminated)
            self.assertFalse(truncated)
        self.assertGreater(observation["self_position"][0], start_x)
        env.close()

    def test_same_seed_same_action_sequence_is_reproducible(self) -> None:
        actions = [2, 2, 2, 3, 2, 0, 1]
        env_a = MotorGymEnv("levels/platformer_test_scene.json", max_steps=20)
        env_b = MotorGymEnv("levels/platformer_test_scene.json", max_steps=20)

        obs_a, _ = env_a.reset(seed=77)
        obs_b, _ = env_b.reset(seed=77)
        trace_a = [json.dumps(obs_a, sort_keys=True)]
        trace_b = [json.dumps(obs_b, sort_keys=True)]

        for action in actions:
            obs_a, reward_a, term_a, trunc_a, _ = env_a.step(action)
            obs_b, reward_b, term_b, trunc_b, _ = env_b.step(action)
            trace_a.append(json.dumps({"obs": obs_a, "reward": reward_a, "term": term_a, "trunc": trunc_a}, sort_keys=True))
            trace_b.append(json.dumps({"obs": obs_b, "reward": reward_b, "term": term_b, "trunc": trunc_b}, sort_keys=True))

        self.assertEqual(trace_a, trace_b)
        env_a.close()
        env_b.close()

    def test_random_rollout_dataset_script_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "rollouts.jsonl"
            result = _run_module(
                "tools.random_rollout_dataset",
                "levels/platformer_test_scene.json",
                "--episodes",
                "2",
                "--max-steps",
                "8",
                "--seed",
                "90",
                "--out",
                output_path.as_posix(),
            )
            self.assertIn("[OK]", result.stdout)
            lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreater(len(lines), 0)
        first = json.loads(lines[0])
        self.assertIn("observation", first)
        self.assertIn("next_observation", first)
        self.assertIn("reward", first)


if __name__ == "__main__":
    unittest.main()
