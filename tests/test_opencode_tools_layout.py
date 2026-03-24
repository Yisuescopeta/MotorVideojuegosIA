from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent


class OpenCodeToolsLayoutTests(unittest.TestCase):
    def test_expected_custom_tool_files_exist(self) -> None:
        expected = [
            ".opencode/lib/engine-tools.ts",
            ".opencode/tools/engine_unittest.ts",
            ".opencode/tools/engine_smoke.ts",
            ".opencode/tools/dataset_generate_scenarios.ts",
            ".opencode/tools/dataset_run_episodes.ts",
            ".opencode/tools/dataset_replay_episode.ts",
            ".opencode/tools/runner_parallel_rollout.ts",
            "docs/opencode/tools.md",
        ]
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).exists(), f"Missing {relative_path}")


if __name__ == "__main__":
    unittest.main()
