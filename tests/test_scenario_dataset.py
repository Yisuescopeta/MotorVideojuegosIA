import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.rl.scenario_dataset import generate_scenarios, replay_episode, run_episode_dataset


class ScenarioDatasetTests(unittest.TestCase):
    def test_generate_scenarios_writes_manifest_and_scene_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = generate_scenarios(
                "levels/multiagent_toy_scene.json",
                out_dir=temp_dir,
                count=3,
                seed=123,
            )
            self.assertEqual(len(manifest["scenarios"]), 3)
            self.assertTrue((Path(temp_dir) / "manifest.json").exists())
            self.assertTrue(Path(manifest["scenarios"][0]["scene_path"]).exists())

    def test_run_episode_dataset_and_replay_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "episodes.jsonl"
            summary = run_episode_dataset(
                scene_path="levels/platformer_test_scene.json",
                out_jsonl=dataset_path.as_posix(),
                episodes=2,
                max_steps=12,
                seed=77,
                env_kind="single",
            )
            self.assertEqual(summary["completed_episodes"], 2)
            report = replay_episode(dataset_path.as_posix(), "episode_0000")
        self.assertTrue(report["match"])

    def test_parallel_runner_cli_produces_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exit_code = os.system(
                f'py -3 tools/parallel_rollout_runner.py levels/multiagent_toy_scene.json --workers 2 --episodes 4 --max-steps 12 --seed 10 --out-dir "{temp_dir}"'
            )
            self.assertEqual(exit_code, 0)
            report = json.loads((Path(temp_dir) / "parallel_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["workers"], 2)
        self.assertEqual(report["episodes"], 4)
        self.assertIn("throughput_steps_per_second", report)


if __name__ == "__main__":
    unittest.main()
