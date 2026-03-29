import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.rl import ACTION_SPEC_VERSION, OBSERVATION_SPEC_VERSION, MotorGymEnv

ROOT = Path(__file__).resolve().parents[1]


def _copy_project_file(project_root: Path, relative_path: str) -> Path:
    source = ROOT / relative_path
    target = project_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _read_root_editor_state() -> str:
    return (ROOT / ".motor" / "editor_state.json").read_text(encoding="utf-8")


def _run_module(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class MotorGymEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temp_dir.name) / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        _copy_project_file(self.project_root, "levels/platformer_test_scene.json")

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_reset_and_step_follow_gym_contract(self) -> None:
        root_editor_state = _read_root_editor_state()
        env = MotorGymEnv(
            (self.project_root / "levels" / "platformer_test_scene.json").as_posix(),
            project_root=self.project_root.as_posix(),
            max_steps=10,
        )
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
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_right_action_advances_agent(self) -> None:
        root_editor_state = _read_root_editor_state()
        env = MotorGymEnv(
            (self.project_root / "levels" / "platformer_test_scene.json").as_posix(),
            project_root=self.project_root.as_posix(),
            max_steps=30,
        )
        observation, _ = env.reset(seed=5)
        start_x = observation["self_position"][0]
        for _ in range(5):
            observation, _, terminated, truncated, _ = env.step(2)
            self.assertFalse(terminated)
            self.assertFalse(truncated)
        self.assertGreater(observation["self_position"][0], start_x)
        env.close()
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_same_seed_same_action_sequence_is_reproducible(self) -> None:
        root_editor_state = _read_root_editor_state()
        actions = [2, 2, 2, 3, 2, 0, 1]
        scene_path = (self.project_root / "levels" / "platformer_test_scene.json").as_posix()
        env_a = MotorGymEnv(scene_path, project_root=self.project_root.as_posix(), max_steps=20)
        env_b = MotorGymEnv(scene_path, project_root=self.project_root.as_posix(), max_steps=20)

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
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_random_rollout_dataset_script_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "rollouts.jsonl"
            result = _run_module(
                "tools.random_rollout_dataset",
                "levels/platformer_test_scene.json",
                "--project-root",
                self.project_root.as_posix(),
                "--episodes",
                "2",
                "--max-steps",
                "8",
                "--seed",
                "90",
                "--out",
                output_path.as_posix(),
                cwd=self.project_root,
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
