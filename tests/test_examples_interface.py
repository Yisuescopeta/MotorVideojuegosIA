"""
tests/test_examples_interface.py - Tests validating examples use official motor interface

Ensures AI workflow examples use the official `motor` CLI interface
and do not teach legacy `tools.engine_cli` patterns.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples" / "ai_workflows"
README_PATH = EXAMPLES_DIR / "README.md"


class ExamplesInterfaceTests(unittest.TestCase):
    """Tests that examples use the official motor CLI interface."""

    LEGACY_PATTERNS = [
        r"python\s+-m\s+tools\.engine_cli",
        r"tools\.engine_cli",
        r"from\s+tools\.engine_cli",
        r"import\s+tools\.engine_cli",
    ]

    def _get_example_files(self) -> list[Path]:
        """Get all Python example files."""
        if not EXAMPLES_DIR.exists():
            return []
        return list(EXAMPLES_DIR.glob("*.py"))

    def test_examples_use_motor_not_legacy_cli(self) -> None:
        """All examples must use 'motor' command via python -m, not legacy tools.engine_cli."""
        examples = self._get_example_files()

        violations = []
        for py_file in examples:
            content = py_file.read_text(encoding="utf-8")

            # Check for legacy patterns in code
            for pattern in self.LEGACY_PATTERNS:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                for match in matches:
                    line_num = content[:match.start()].count("\n") + 1
                    line = content.split("\n")[line_num - 1].strip()

                    # Skip if in a comment explaining it's legacy
                    if "legacy" in line.lower() or "deprecated" in line.lower():
                        continue

                    violations.append(f"{py_file.name}:{line_num}: {line}")

            # Check they use python -m motor for execution (robust approach)
            # Examples should use: [sys.executable, "-m", "motor", ...]
            if 'sys.executable, "-m", "motor"' not in content:
                violations.append(f"{py_file.name}: Does not use 'sys.executable, \"-m\", \"motor\"' for execution. "
                                 f"Examples must use python -m motor for robustness in clean checkouts.")

        if violations:
            self.fail(
                "Examples using legacy interface or wrong execution pattern found:\n" +
                "\n".join(f"  {v}" for v in violations) +
                "\n\nUse [sys.executable, \"-m\", \"motor\", ...] for execution."
            )

    def test_examples_have_proper_env_setup(self) -> None:
        """Examples should set up PYTHONPATH properly for motor execution."""
        examples = self._get_example_files()

        for py_file in examples:
            with self.subTest(example=py_file.name):
                content = py_file.read_text(encoding="utf-8")

                # Should set up PYTHONPATH
                self.assertIn(
                    "PYTHONPATH", content,
                    f"{py_file.name} should set up PYTHONPATH for motor execution"
                )

                # Should use subprocess.run with motor
                self.assertIn(
                    'subprocess.run', content,
                    f"{py_file.name} should use subprocess.run to execute motor"
                )

                # Should use python -m motor for robust execution (not rely on global motor binary)
                self.assertIn(
                    'sys.executable, "-m", "motor"',
                    content,
                    f"{py_file.name} should use 'sys.executable, \"-m\", \"motor\"' "
                    f"for robust execution in clean checkouts"
                )

    def test_examples_use_official_grammar(self) -> None:
        """Examples should use official command grammar (not legacy aliases).

        Legacy commands like 'upsert-state' should not be in examples.
        """
        LEGACY_COMMANDS = [
            "animator upsert-state",
            "animator remove-state",
        ]

        examples = self._get_example_files()

        violations = []
        for py_file in examples:
            content = py_file.read_text(encoding="utf-8")

            for legacy_cmd in LEGACY_COMMANDS:
                if legacy_cmd in content:
                    # Find line number
                    for i, line in enumerate(content.split("\n"), 1):
                        if legacy_cmd in line:
                            # Skip if in a comment explaining it's legacy
                            if "legacy" not in line.lower() and "deprecated" not in line.lower():
                                violations.append(f"{py_file.name}:{i}: {line.strip()}")

        if violations:
            self.fail(
                "Examples using legacy command grammar found:\n" +
                "\n".join(f"  {v}" for v in violations) +
                "\n\nUse 'animator state create/remove' instead."
            )

    def test_readme_uses_official_interface(self) -> None:
        """README.md should teach the official motor interface."""
        if not README_PATH.exists():
            self.skipTest("README.md not found")

        content = README_PATH.read_text(encoding="utf-8")

        # Check that official motor is shown first and prominently
        self.assertIn(
            "motor doctor --project .",
            content,
            "README should show official motor command"
        )

        # Check legacy is marked as deprecated (not primary)
        legacy_section = re.search(
            r"legacy.*deprecated|deprecated.*legacy",
            content,
            re.IGNORECASE
        )
        self.assertIsNotNone(
            legacy_section,
            "README should mark legacy interface as deprecated"
        )

    def test_readme_not_use_legacy_as_primary(self) -> None:
        """README.md should not use legacy commands as primary examples.

        Legacy commands should only appear in compatibility notes, not
        as the main teaching examples.
        """
        if not README_PATH.exists():
            self.skipTest("README.md not found")

        content = README_PATH.read_text(encoding="utf-8")

        # Extract code blocks
        code_blocks = re.findall(r"```bash(.*?)```", content, re.DOTALL)

        LEGACY_PATTERNS = [
            "tools.engine_cli",
            "upsert-state",
        ]

        violations = []
        for block in code_blocks:
            for pattern in LEGACY_PATTERNS:
                if pattern in block:
                    violations.append(f"Code block contains '{pattern}':\n{block[:200]}")

        if violations:
            self.fail(
                "README.md uses legacy patterns in code examples:\n" +
                "\n".join(f"  {v}" for v in violations)
            )

    def test_examples_are_executable_python(self) -> None:
        """All example files should be valid Python syntax."""
        examples = self._get_example_files()

        for py_file in examples:
            with self.subTest(example=py_file.name):
                content = py_file.read_text(encoding="utf-8")

                # Should parse as valid Python
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    self.fail(f"{py_file.name} has syntax error: {e}")

    def test_examples_import_structure(self) -> None:
        """Examples should use proper imports for motor execution."""
        examples = self._get_example_files()

        for py_file in examples:
            with self.subTest(example=py_file.name):
                content = py_file.read_text(encoding="utf-8")

                # Should have shebang or main guard
                has_shebang = content.startswith("#!/usr/bin/env python")
                has_main_guard = 'if __name__ == "__main__"' in content

                self.assertTrue(
                    has_shebang or has_main_guard,
                    f"{py_file.name} should have shebang or main guard"
                )

                # Should import subprocess
                self.assertIn(
                    "import subprocess",
                    content,
                    f"{py_file.name} should import subprocess for motor execution"
                )

                # Should import json for parsing
                self.assertIn(
                    "import json",
                    content,
                    f"{py_file.name} should import json for parsing motor output"
                )


class ExamplesNoRegressionTests(unittest.TestCase):
    """Regression tests to prevent legacy interface from reappearing."""

    def test_no_hardcoded_tools_engine_cli_in_examples(self) -> None:
        """Fail if tools.engine_cli appears as main execution path.

        This test ensures we don't regress to teaching the wrong interface.
        """
        examples = list(EXAMPLES_DIR.glob("*.py")) if EXAMPLES_DIR.exists() else []
        readme = README_PATH if README_PATH.exists() else None

        all_content = ""
        for py_file in examples:
            all_content += py_file.read_text(encoding="utf-8") + "\n"
        if readme:
            all_content += readme.read_text(encoding="utf-8") + "\n"

        # Should not have tools.engine_cli outside of deprecation context
        matches = re.finditer(r"tools\.engine_cli", all_content, re.IGNORECASE)

        violations = []
        for match in matches:
            # Get context (100 chars before and after)
            start = max(0, match.start() - 100)
            end = min(len(all_content), match.end() + 100)
            context = all_content[start:end].lower()

            # Only allowed in explicit deprecation/legacy context
            if "legacy" not in context and "deprecated" not in context:
                line_num = all_content[:match.start()].count("\n") + 1
                violations.append(f"Line ~{line_num}: {all_content[match.start():match.end()+50]}")

        if violations:
            self.fail(
                "tools.engine_cli found outside deprecation context:\n" +
                "\n".join(f"  {v}" for v in violations) +
                "\n\nUse 'motor' command instead."
            )


class ExamplesOfficialInterfaceTests(unittest.TestCase):
    """Tests ensuring examples teach official motor interface while using robust execution."""

    def test_examples_show_official_motor_syntax_in_output(self) -> None:
        """Examples should show 'motor ...' as official interface in user-facing output.

        Even though examples use 'python -m motor' internally for robustness,
        they should still teach users the official 'motor ...' syntax.
        """
        examples = self._get_example_files()

        for py_file in examples:
            with self.subTest(example=py_file.name):
                content = py_file.read_text(encoding="utf-8")

                # Should show official motor syntax in print statements (user-facing)
                # Look for patterns like: print(f"  motor doctor --project .") or print("motor ...")
                motor_in_print = re.search(
                    r'print\(f?["\'][^"\']*motor\s+',
                    content
                )

                self.assertIsNotNone(
                    motor_in_print,
                    f"{py_file.name} should show official 'motor ...' syntax in print statements "
                    f"to teach users the correct interface"
                )

    def test_examples_document_execution_strategy(self) -> None:
        """Examples should document why they use python -m motor internally."""
        examples = self._get_example_files()

        for py_file in examples:
            with self.subTest(example=py_file.name):
                content = py_file.read_text(encoding="utf-8")

                # Should have a docstring or comment explaining the execution strategy
                has_execution_comment = (
                    "python -m motor" in content and
                    ("robust" in content.lower() or "checkout" in content.lower() or
                     "install" in content.lower() or "development" in content.lower())
                )

                self.assertTrue(
                    has_execution_comment,
                    f"{py_file.name} should document why it uses 'python -m motor' "
                    f"(for robustness in clean checkouts)"
                )

    def _get_example_files(self) -> list[Path]:
        """Get all Python example files."""
        if not EXAMPLES_DIR.exists():
            return []
        return list(EXAMPLES_DIR.glob("*.py"))


if __name__ == "__main__":
    unittest.main()
