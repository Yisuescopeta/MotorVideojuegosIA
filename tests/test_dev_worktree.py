from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.dev_worktree import get_repo_status, plan_worktree, validate_worktree

ROOT = Path(__file__).resolve().parents[1]


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    return env


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.dev_worktree", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )


def _init_repo(path: Path) -> None:
    result = subprocess.run(
        ["git", "init"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


class DevWorktreeTests(unittest.TestCase):
    def test_status_reports_repo_branch_and_clean_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _init_repo(repo)

            result = _run_module("--repo-root", repo.as_posix(), "status", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            payload = json.loads(result.stdout)
            data = payload["data"]
            self.assertTrue(payload["success"])
            self.assertTrue(data["is_git_repo"])
            self.assertEqual(data["repo_root"], repo.resolve().as_posix())
            self.assertFalse(data["dirty"])
            self.assertTrue(data["branch"])

    def test_list_reports_current_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _init_repo(repo)

            result = _run_module("--repo-root", repo.as_posix(), "list", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            payload = json.loads(result.stdout)
            worktrees = payload["data"]["worktrees"]
            self.assertEqual(len(worktrees), 1)
            self.assertEqual(worktrees[0]["path"], repo.resolve().as_posix())

    def test_validate_detects_dirty_tree_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _init_repo(repo)

            status = get_repo_status(repo)
            self.assertTrue(status["branch"])

            clean_validation = validate_worktree(
                repo,
                expected_branch=status["branch"],
                require_clean=True,
            )
            self.assertTrue(clean_validation["valid"], clean_validation)

            (repo / "notes.txt").write_text("dirty\n", encoding="utf-8")
            dirty_validation = validate_worktree(
                repo,
                expected_branch=status["branch"],
                require_clean=True,
            )
            self.assertFalse(dirty_validation["valid"])
            self.assertIn("Working tree is not clean", dirty_validation["issues"])

    def test_plan_generates_non_mutating_worktree_add_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            base_dir = Path(temp_dir) / "worktrees"
            repo.mkdir()
            base_dir.mkdir()
            _init_repo(repo)

            plan = plan_worktree(
                repo,
                branch="feat/test-branch",
                base_dir=base_dir.as_posix(),
            )
            self.assertTrue(plan["valid"], plan)
            self.assertFalse(plan["branch_exists_locally"])
            self.assertIn("-b", plan["command"])
            self.assertIn("git worktree add -b feat/test-branch", plan["command_text"])
            self.assertTrue(plan["destination"].startswith(base_dir.resolve().as_posix()))


if __name__ == "__main__":
    unittest.main()
