import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.rl import MotorParallelEnv


class MotorParallelEnvTests(unittest.TestCase):
    def test_reset_exposes_two_agents_and_parallel_contract(self) -> None:
        env = MotorParallelEnv("levels/multiagent_toy_scene.json", max_steps=20)
        observations, infos = env.reset(seed=12)

        self.assertEqual(set(env.agents), {"AgentA", "AgentB"})
        self.assertEqual(set(observations.keys()), {"AgentA", "AgentB"})
        self.assertEqual(set(infos.keys()), {"AgentA", "AgentB"})
        env.close()

    def test_parallel_step_updates_both_agents(self) -> None:
        env = MotorParallelEnv("levels/multiagent_toy_scene.json", max_steps=20)
        observations, _ = env.reset(seed=9)
        start_a = observations["AgentA"]["self_position"][0]
        start_b = observations["AgentB"]["self_position"][0]

        next_obs, rewards, terminations, truncations, infos = env.step({"AgentA": 2, "AgentB": 1})

        self.assertGreater(next_obs["AgentA"]["self_position"][0], start_a)
        self.assertLess(next_obs["AgentB"]["self_position"][0], start_b)
        self.assertIn("AgentA", rewards)
        self.assertIn("AgentB", rewards)
        self.assertFalse(terminations["AgentA"])
        self.assertFalse(truncations["AgentB"])
        self.assertTrue(infos["AgentA"]["parallel_api"])
        env.close()

    def test_multiagent_rollout_dataset_script_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "multiagent.jsonl"
            exit_code = os.system(
                f'py -3 tools/multiagent_rollout_dataset.py levels/multiagent_toy_scene.json --episodes 2 --max-steps 10 --seed 55 --out "{output_path.as_posix()}"'
            )
            self.assertEqual(exit_code, 0)
            lines = output_path.read_text(encoding="utf-8").strip().splitlines()

        self.assertGreater(len(lines), 0)
        first = json.loads(lines[0])
        self.assertIn("actions", first)
        self.assertIn("rewards", first)
        self.assertIn("infos", first)


if __name__ == "__main__":
    unittest.main()
