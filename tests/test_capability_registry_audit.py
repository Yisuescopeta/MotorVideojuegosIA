from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tools.capability_registry_audit import build_audit_report

ROOT = Path(__file__).resolve().parents[1]


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    return env


class CapabilityRegistryAuditTests(unittest.TestCase):
    def test_build_audit_report_passes_for_current_registry(self) -> None:
        payload = build_audit_report()
        self.assertTrue(payload["success"], payload)
        self.assertEqual(payload["data"]["issue_count"], 0)
        self.assertGreaterEqual(payload["data"]["warning_count"], 0)

    def test_module_cli_outputs_json(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "tools.capability_registry_audit", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        payload = json.loads(result.stdout)
        self.assertTrue(payload["success"])
        check_names = [item["name"] for item in payload["data"]["checks"]]
        self.assertIn("api-methods", check_names)
        self.assertIn("cli-commands", check_names)

    def test_legacy_wrapper_delegates_to_tools_module(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/audit_registry.py", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=_subprocess_env(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        payload = json.loads(result.stdout)
        self.assertTrue(payload["success"])
        self.assertIn("Capability registry audit passed", payload["message"])
        self.assertGreaterEqual(payload["data"]["warning_count"], 0)


if __name__ == "__main__":
    unittest.main()
