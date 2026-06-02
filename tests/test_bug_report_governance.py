"""
tests/test_bug_report_governance.py — Governance tests for bug reports, markers, and skip hygiene.

Bug 3.3: Tests for marker policies in docs, BUG() cleanup in engine/, and
actionable skip messages for optional dependencies.

These tests are infrastructure/health checks, not functional runtime tests.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MarkerPolicyDocsTests(unittest.TestCase):
    """Verify docs/documentation_governance.md defines marker policies."""

    def test_docs_governance_contains_marker_policy_section(self) -> None:
        """docs/documentation_governance.md must define TODO/FIXME/BUG/LIMITATION policy."""
        gov_path = ROOT / "docs" / "documentation_governance.md"
        self.assertTrue(gov_path.exists(), f"documentation_governance.md must exist at {gov_path}")

        content = gov_path.read_text(encoding="utf-8")

        # Must have a section header about markers
        self.assertIn("Marcadores", content,
            "documentation_governance.md must have a 'Marcadores' section")

        # Must mention all four marker types
        for marker in ("TODO(", "FIXME(", "BUG(", "LIMITATION"):
            self.assertIn(marker, content,
                f"documentation_governance.md must reference '{marker}' marker")

        # Must contain the anti-false-BUG rule
        self.assertIn("false BUG", content,
            "documentation_governance.md must forbid false BUG markers")

        # Must link to bug report
        self.assertIn("bug_report.md", content,
            "documentation_governance.md must reference bug_report.md for cross-traceability")


class NoFalseBUGMarkersInEngineTests(unittest.TestCase):
    """Verify engine/ directory contains no unaccepted BUG() markers."""

    def test_engine_directory_contains_no_bug_markers(self) -> None:
        """engine/ must not contain BUG( markers unless tied to an accepted policy.

        Current policy: zero BUG() markers in engine/. If a BUG() marker is
        added intentionally, it must reference an accepted issue ID and be
        reviewed against docs/bug_report.md.
        """
        engine_dir = ROOT / "engine"
        self.assertTrue(engine_dir.exists(), f"engine/ directory must exist at {engine_dir}")

        violations = []
        for py_file in engine_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # Find all BUG( occurrences
            for match in re.finditer(r"BUG\(", content):
                line_num = content[:match.start()].count("\n") + 1
                line = content.split("\n")[line_num - 1].strip()
                violations.append(f"{py_file.relative_to(ROOT)}:{line_num}: {line}")

        if violations:
            self.fail(
                "engine/ contains BUG() markers:\n" +
                "\n".join(f"  {v}" for v in violations) +
                "\n\nAll BUG() markers must be removed or tied to tracked issues per "
                "docs/documentation_governance.md marcadores policy."
            )

    def test_no_lingering_bug_markers_in_python_files(self) -> None:
        """Quick scan: no BUG( anywhere in engine/**/*.py."""
        engine_dir = ROOT / "engine"
        count = 0
        for py_file in engine_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            count += len(re.findall(r"BUG\(", content))

        self.assertEqual(count, 0,
            f"engine/ has {count} BUG() marker(s). Expected 0 per marker policy.")


class OptionalDependencySkipMessageTests(unittest.TestCase):
    """Verify that optional-dependency skip messages include actionable setup hints."""

    def test_box2d_skip_message_includes_install_hint(self) -> None:
        """Box2D skip decorators must include install instructions."""
        physics_files = [
            ROOT / "tests" / "test_physics_backend_contract.py",
            ROOT / "tests" / "test_physics_move_and_slide.py",
        ]

        for file_path in physics_files:
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            # Find Box2D-related skip conditions
            if "BOX2D_AVAILABLE" in content:
                # The skip message should contain install guidance
                skip_context = content
                self.assertIn("pip install", skip_context,
                    f"{file_path.name}: Box2D skip must mention 'pip install' with package name")

    def test_prueva1_skip_message_includes_setup_hint(self) -> None:
        """Prueva1 skip decorators must include setup/clone instructions."""
        file_path = ROOT / "tests" / "test_export_runtime_playability.py"
        if not file_path.exists():
            return

        content = file_path.read_text(encoding="utf-8")

        # Extract skip messages for Prueva1
        skip_messages = re.findall(
            r'skipUnless\([^,]+,\s*"([^"]+)"\)',
            content
        )

        prueba_messages = [m for m in skip_messages if "Prueva1" in m]
        self.assertGreater(len(prueba_messages), 0,
            "Expected at least one Prueva1-related skip message")

        for msg in prueba_messages:
            self.assertRegex(
                msg,
                r"(Clone|create|build|source|projects/Prueva1|export pack)",
                f"Prueva1 skip message must contain actionable setup hint. Got: {msg}"
            )

    def test_dpapi_skip_message_includes_platform_hint(self) -> None:
        """DPAPI skip message must mention platform requirement."""
        file_path = ROOT / "tests" / "test_agent_service.py"
        if not file_path.exists():
            return

        content = file_path.read_text(encoding="utf-8")

        # Find skipTest calls with DPAPI
        skip_messages = re.findall(
            r'skipTest\(\s*"([^"]*DPAPI[^"]*)"',
            content,
            re.DOTALL
        )

        self.assertGreater(len(skip_messages), 0,
            "Expected at least one DPAPI skip message in test_agent_service.py")

        for msg in skip_messages:
            normalized = msg.replace("\n", " ").replace('"', "")
            self.assertRegex(
                normalized,
                r"(Windows|mock|platform|cross-plat)",
                f"DPAPI skip must mention platform or mocking option. Got: {normalized}"
            )


if __name__ == "__main__":
    unittest.main()
