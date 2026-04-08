"""
tests/test_cli_capabilities_status.py - Tests for CLI capabilities status field

Ensures that 'motor capabilities --json' includes 'status' field.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLICapabilitiesStatusTests(unittest.TestCase):
    """Tests ensuring motor capabilities includes status field."""

    def setUp(self) -> None:
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    def _run_motor_capabilities(self) -> dict:
        """Run motor capabilities --json and return parsed result."""
        result = subprocess.run(
            [sys.executable, "-m", "motor", "capabilities", "--json"],
            capture_output=True,
            text=True,
            env=self.env,
        )
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        return json.loads(output)

    def test_capabilities_json_includes_status_field(self) -> None:
        """motor capabilities --json must include status for each capability."""
        data = self._run_motor_capabilities()

        self.assertTrue(data.get("success"), "motor capabilities should succeed")
        capabilities = data.get("data", {}).get("capabilities", [])

        self.assertGreater(len(capabilities), 0, "Should have capabilities")

        for cap in capabilities:
            with self.subTest(capability=cap["id"]):
                self.assertIn("status", cap, f"Capability {cap['id']} missing status field")
                self.assertIn(
                    cap["status"],
                    {"implemented", "planned", "deprecated"},
                    f"Capability {cap['id']} has invalid status: {cap['status']}"
                )

    def test_all_default_capabilities_have_valid_status(self) -> None:
        """All capabilities should have a valid status (implemented, planned, or deprecated)."""
        data = self._run_motor_capabilities()
        capabilities = data.get("data", {}).get("capabilities", [])

        for cap in capabilities:
            with self.subTest(capability=cap["id"]):
                self.assertIn(
                    cap.get("status"),
                    {"implemented", "planned", "deprecated"},
                    f"Capability {cap['id']} has invalid status: {cap.get('status')}"
                )

    def test_implemented_count_matches_cli_commands(self) -> None:
        """Count of implemented capabilities should be reasonable."""
        data = self._run_motor_capabilities()
        capabilities = data.get("data", {}).get("capabilities", [])

        implemented = [c for c in capabilities if c.get("status") == "implemented"]
        planned = [c for c in capabilities if c.get("status") == "planned"]

        # Should have at least the core implemented commands
        self.assertGreaterEqual(
            len(implemented), 15,
            f"Should have at least 15 implemented capabilities, found {len(implemented)}"
        )

        # Should have planned capabilities (commands not yet in CLI)
        self.assertGreater(
            len(planned), 0,
            f"Should have some planned capabilities, found {len(planned)}"
        )

        # Print summary for visibility
        print(f"\n  Implemented: {len(implemented)}, Planned: {len(planned)}")

    def test_capabilities_json_is_complete(self) -> None:
        """motor capabilities --json should return complete capability info."""
        data = self._run_motor_capabilities()
        capabilities = data.get("data", {}).get("capabilities", [])

        for cap in capabilities:
            with self.subTest(capability=cap["id"]):
                # Required fields
                self.assertIn("id", cap, f"Capability missing 'id'")
                self.assertIn("summary", cap, f"Capability missing 'summary'")
                self.assertIn("mode", cap, f"Capability missing 'mode'")
                self.assertIn("status", cap, f"Capability missing 'status'")
                self.assertIn("api_methods", cap, f"Capability missing 'api_methods'")
                self.assertIn("cli_command", cap, f"Capability missing 'cli_command'")
                self.assertIn("tags", cap, f"Capability missing 'tags'")

                # Validate field types/values
                self.assertTrue(cap["id"], f"Capability id should not be empty")
                self.assertIn(cap["mode"], {"edit", "play", "both"}, f"Invalid mode for {cap['id']}")
                self.assertIsInstance(cap["api_methods"], list, f"api_methods should be list for {cap['id']}")
                self.assertTrue(cap["cli_command"], f"cli_command should not be empty for {cap['id']}")
                self.assertIsInstance(cap["tags"], list, f"tags should be list for {cap['id']}")


if __name__ == "__main__":
    unittest.main()
