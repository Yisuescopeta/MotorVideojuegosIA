from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tools._tooling_common import ToolCommandResult
from tools.dev_checks import CheckCommand, build_suite_plan, list_suites, resolve_repo_root, run_suite_plan

ROOT = Path(__file__).resolve().parents[1]


def _run_module_result(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    return subprocess.run(
        [sys.executable, "-m", "tools.dev_checks", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


class DevChecksModuleTests(unittest.TestCase):
    def test_list_suites_exposes_expected_foundation_entries(self) -> None:
        names = [item["name"] for item in list_suites()]
        self.assertEqual(
            names,
            ["doctor", "registry-audit", "repo-contracts", "tooling-foundation"],
        )

    def test_build_suite_plan_expands_expected_commands(self) -> None:
        plan = build_suite_plan(["tooling-foundation", "doctor"], ROOT)
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0].suite, "tooling-foundation")
        self.assertIn("unittest", plan[0].command)
        self.assertEqual(plan[1].suite, "doctor")
        self.assertEqual(plan[1].command[:3], (sys.executable, "-m", "motor"))

    def test_run_suite_plan_collects_failure_result(self) -> None:
        command = CheckCommand(
            suite="tooling-foundation",
            label="fake",
            command=(sys.executable, "-m", "unittest"),
            cwd=ROOT.as_posix(),
        )
        fake_result = ToolCommandResult(
            command=command.command,
            cwd=command.cwd,
            returncode=1,
            stdout="failed",
            stderr="traceback",
        )
        with patch("tools.dev_checks.run_command", return_value=fake_result):
            results = run_suite_plan([command])

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["result"]["passed"])
        self.assertEqual(results[0]["result"]["returncode"], 1)

    def test_resolve_repo_root_defaults_to_current_repo(self) -> None:
        self.assertEqual(resolve_repo_root("").as_posix(), ROOT.as_posix())


class DevChecksCliTests(unittest.TestCase):
    def test_cli_lists_suites_in_json(self) -> None:
        result = _run_module_result("--list-suites", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        payload = json.loads(result.stdout)
        names = [item["name"] for item in payload["data"]["available_suites"]]
        self.assertIn("tooling-foundation", names)
        self.assertIn("registry-audit", names)

    def test_cli_dry_run_reports_planned_commands(self) -> None:
        result = _run_module_result("--suite", "tooling-foundation", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        payload = json.loads(result.stdout)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["data"]["dry_run"])
        command = payload["data"]["planned_commands"][0]
        self.assertEqual(command["suite"], "tooling-foundation")
        self.assertIn("tests.test_tooling_portability", command["command"])

    def test_cli_rejects_unknown_suite(self) -> None:
        result = _run_module_result("--suite", "missing-suite", "--json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

        payload = json.loads(result.stdout)
        self.assertFalse(payload["success"])
        self.assertIn("missing-suite", payload["data"]["unknown_suites"])


if __name__ == "__main__":
    unittest.main()
