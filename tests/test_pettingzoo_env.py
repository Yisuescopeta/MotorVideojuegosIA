import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.rl import MotorParallelEnv

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


class MotorParallelEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self._temp_dir.name) / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        _copy_project_file(self.project_root, "levels/multiagent_toy_scene.json")

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_reset_exposes_two_agents_and_parallel_contract(self) -> None:
        root_editor_state = _read_root_editor_state()
        env = MotorParallelEnv(
            (self.project_root / "levels" / "multiagent_toy_scene.json").as_posix(),
            project_root=self.project_root.as_posix(),
            max_steps=20,
        )
        observations, infos = env.reset(seed=12)

        self.assertEqual(set(env.agents), {"AgentA", "AgentB"})
        self.assertEqual(set(observations.keys()), {"AgentA", "AgentB"})
        self.assertEqual(set(infos.keys()), {"AgentA", "AgentB"})
        env.close()
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_parallel_step_updates_both_agents(self) -> None:
        root_editor_state = _read_root_editor_state()
        env = MotorParallelEnv(
            (self.project_root / "levels" / "multiagent_toy_scene.json").as_posix(),
            project_root=self.project_root.as_posix(),
            max_steps=20,
        )
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
        self.assertEqual(_read_root_editor_state(), root_editor_state)

    def test_multiagent_rollout_dataset_script_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "multiagent.jsonl"
            result = _run_module(
                "tools.multiagent_rollout_dataset",
                "levels/multiagent_toy_scene.json",
                "--project-root",
                self.project_root.as_posix(),
                "--episodes",
                "2",
                "--max-steps",
                "10",
                "--seed",
                "55",
                "--out",
                output_path.as_posix(),
                cwd=self.project_root,
            )
            self.assertIn("[OK]", result.stdout)
            lines = output_path.read_text(encoding="utf-8").strip().splitlines()

        self.assertGreater(len(lines), 0)
        first = json.loads(lines[0])
        self.assertIn("actions", first)
        self.assertIn("rewards", first)
        self.assertIn("infos", first)


if __name__ == "__main__":
    unittest.main()
