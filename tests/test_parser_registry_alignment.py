"""
tests/test_parser_registry_alignment.py - Strict alignment tests between CLI parser and capability registry

Ensures that every cli_command in the registry matches the actual CLI parser implementation exactly.
"""

from __future__ import annotations

import argparse
import re
import unittest

from engine.ai import get_default_registry
from motor.cli import create_motor_parser


def _public_leaf_commands(parser: argparse.ArgumentParser) -> set[tuple[str, ...]]:
    """Return public executable command paths, excluding hidden legacy aliases."""
    leaf_commands: set[tuple[str, ...]] = set()

    def walk(current: argparse.ArgumentParser, path: tuple[str, ...], hidden: bool = False) -> None:
        subparser_actions = [
            action for action in current._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if not subparser_actions:
            if path and not hidden:
                leaf_commands.add(path)
            return

        for action in subparser_actions:
            for name, child in action.choices.items():
                choice_action = next(
                    (choice for choice in action._choices_actions if choice.dest == name),
                    None,
                )
                child_hidden = hidden or (
                    choice_action is not None and choice_action.help is argparse.SUPPRESS
                )
                walk(child, path + (name,), child_hidden)

    walk(parser, ())
    return leaf_commands


def _registry_command_path(cli_command: str) -> tuple[str, ...]:
    """Extract the executable command path from a registry cli_command."""
    parts = cli_command.split()
    if not parts or parts[0] != "motor":
        return ()

    command_parts: list[str] = []
    for part in parts[1:]:
        if part.startswith(("<", "[", "--")):
            break
        command_parts.append(part)
    return tuple(command_parts)


class ParserRegistryStrictAlignmentTests(unittest.TestCase):
    """Tests that verify exact alignment between parser and registry."""

    @classmethod
    def setUpClass(cls):
        cls.registry = get_default_registry()
        cls.parser = create_motor_parser()
        cls.implemented_caps = [cap for cap in cls.registry.list_all()
                                if cap.status == "implemented"]

    def _get_parser_subcommands(self, *path: str) -> set[str]:
        """Get subcommands from parser following path."""
        current = self.parser
        for part in path:
            for action in current._actions:
                if hasattr(action, 'choices') and action.choices:
                    if part in action.choices:
                        current = action.choices[part]
                        break

        # Get subcommands at this level
        subcommands = set()
        for action in current._actions:
            if hasattr(action, 'choices') and action.choices:
                subcommands.update(action.choices.keys())
        return subcommands

    def _extract_required_args(self, cli_command: str) -> list[str]:
        """Extract required arguments (in <>) from cli_command."""
        return re.findall(r'<([^>]+)>', cli_command)

    def _extract_optional_flags(self, cli_command: str) -> list[str]:
        """Extract optional flags (in []) from cli_command."""
        # Remove required args first
        without_required = re.sub(r'<[^>]+>', '', cli_command)
        # Find optional flags like [--flag] or [--flag <arg>]
        return re.findall(r'\[(--[\w-]+)', without_required)

    def test_scene_commands_alignment(self) -> None:
        """Verify scene commands in registry match parser exactly."""
        scene_caps = [cap for cap in self.implemented_caps
                      if cap.id.startswith("scene:") and ":" not in cap.id[6:]]  # Only top-level scene commands

        for cap in scene_caps:
            with self.subTest(capability=cap.id):
                # scene:save should be in parser
                subcommand = cap.id.split(":")[1]  # "save" from "scene:save"
                parser_subcommands = self._get_parser_subcommands("scene")
                self.assertIn(subcommand, parser_subcommands,
                              f"Capability {cap.id} documents '{subcommand}' but parser doesn't have it")

    def test_entity_create_signature_matches(self) -> None:
        """Verify entity create signature matches exactly."""
        entity_create = next((cap for cap in self.implemented_caps
                              if cap.id == "entity:create"), None)
        self.assertIsNotNone(entity_create, "entity:create capability must exist")

        # Check cli_command mentions --components (not --component)
        self.assertIn("--components", entity_create.cli_command,
                      "entity:create must document --components (with 's'), not --component")
        self.assertNotIn("--component]", entity_create.cli_command,
                         "entity:create must not suggest --component without 's'")

    def test_animator_state_create_signature_matches(self) -> None:
        """Verify animator state create signature matches exactly."""
        state_create = next((cap for cap in self.implemented_caps
                             if cap.id == "animator:state:create"), None)
        self.assertIsNotNone(state_create, "animator:state:create capability must exist")

        # Check all flags are documented
        required_flags = ["--slices", "--fps", "--loop", "--no-loop", "--set-default", "--auto-create"]
        for flag in required_flags:
            self.assertIn(flag, state_create.cli_command,
                          f"animator:state:create must document {flag}")

    def test_no_registry_uses_legacy_upsert_state(self) -> None:
        """Verify registry doesn't document legacy upsert-state command."""
        for cap in self.implemented_caps:
            self.assertNotIn("upsert-state", cap.cli_command,
                             f"Capability {cap.id} must not use legacy 'upsert-state' command")

    def test_cli_command_is_copyable(self) -> None:
        """Verify cli_command examples can be copied and executed (structure-wise)."""
        for cap in self.implemented_caps:
            with self.subTest(capability=cap.id):
                cmd = cap.cli_command
                # Must start with 'motor '
                self.assertTrue(cmd.startswith("motor "),
                                f"{cap.id}: cli_command must start with 'motor '")

                # Must have valid structure: motor <noun> [<subnoun>] <verb> [<args>]
                parts = cmd.split()[1:]  # Remove 'motor'
                self.assertGreaterEqual(len(parts), 2,
                                        f"{cap.id}: cli_command must have at least <noun> and <verb>")

    def test_required_vs_optional_args_clear(self) -> None:
        """Verify required args use <>, optional use [brackets]."""
        for cap in self.implemented_caps:
            with self.subTest(capability=cap.id):
                cmd = cap.cli_command

                # Verify --project is wrapped in optional brackets: [--project <path>]
                if "--project" in cmd:
                    self.assertIn(
                        "[--project",
                        cmd,
                        f"{cap.id}: --project must be wrapped in optional brackets [...]: got '{cmd}'"
                    )

    def test_notes_match_cli_behavior(self) -> None:
        """Verify notes field accurately describes CLI behavior."""
        # animator:state:create should mention --auto-create in notes
        state_create = next((cap for cap in self.implemented_caps
                             if cap.id == "animator:state:create"), None)
        if state_create:
            self.assertIn("--auto-create", state_create.notes,
                          "animator:state:create notes must explain --auto-create behavior")


class ParserRegistryNoDivergenceTests(unittest.TestCase):
    """Tests that fail if parser and registry diverge."""

    def test_all_implemented_capabilities_match_parser(self) -> None:
        """FAIL if any implemented capability doesn't match parser structure."""
        registry = get_default_registry()
        parser = create_motor_parser()

        mismatches = []

        for cap in registry.list_implemented():
            # Parse the cli_command structure
            parts = cap.cli_command.split()
            if len(parts) < 2:
                mismatches.append(f"{cap.id}: Invalid cli_command structure")
                continue

            # Build command path: motor <scope> [<subscope>] <action>
            scope = parts[1]  # "scene", "entity", "animator", etc.

            # Check if scope exists in parser
            scope_found = False
            for action in parser._actions:
                if hasattr(action, 'choices') and action.choices:
                    if scope in action.choices:
                        scope_found = True
                        break

            if not scope_found:
                mismatches.append(f"{cap.id}: Scope '{scope}' not found in parser")

        if mismatches:
            self.fail("Parser-Registry divergences detected:\n" + "\n".join(mismatches))

    def test_public_parser_commands_have_implemented_capability(self) -> None:
        """FAIL if a public leaf CLI command is missing from implemented capabilities."""
        registry = get_default_registry()
        parser = create_motor_parser()

        public_cli_commands = _public_leaf_commands(parser)
        implemented_commands = {
            _registry_command_path(cap.cli_command)
            for cap in registry.list_implemented()
            if cap.cli_command.startswith("motor ")
        }

        missing = sorted(public_cli_commands - implemented_commands)
        self.assertEqual(
            missing,
            [],
            "Public parser commands missing implemented capabilities:\n"
            + "\n".join("  motor " + " ".join(command) for command in missing),
        )

    def test_planned_capabilities_do_not_have_public_parser_command(self) -> None:
        """FAIL if a planned capability points at an executable public CLI command."""
        registry = get_default_registry()
        parser = create_motor_parser()

        public_cli_commands = _public_leaf_commands(parser)
        violations = []
        for cap in registry.list_planned():
            command = _registry_command_path(cap.cli_command)
            if command in public_cli_commands:
                violations.append(f"{cap.id}: motor {' '.join(command)}")

        self.assertEqual(
            violations,
            [],
            "Planned capabilities with public parser commands:\n" + "\n".join(violations),
        )

    def test_implemented_capabilities_have_parser_leaf(self) -> None:
        """FAIL if an implemented capability's full command path is missing from parser."""
        registry = get_default_registry()
        parser = create_motor_parser()

        mismatches = []
        for cap in registry.list_implemented():
            path = _registry_command_path(cap.cli_command)
            if not path:
                mismatches.append(f"{cap.id}: could not derive path from '{cap.cli_command}'")
                continue

            current = parser
            valid = True
            for part in path:
                found = False
                for action in current._actions:
                    if isinstance(action, argparse._SubParsersAction) and action.choices:
                        if part in action.choices:
                            current = action.choices[part]
                            found = True
                            break
                if not found:
                    valid = False
                    break

            if not valid:
                mismatches.append(
                    f"{cap.id}: path 'motor {' '.join(path)}' not found in parser"
                )
                continue

            # Verify we arrived at a leaf (no further public subparsers)
            has_public_subparsers = any(
                isinstance(action, argparse._SubParsersAction) and action.choices
                for action in current._actions
            )
            if has_public_subparsers:
                mismatches.append(
                    f"{cap.id}: path 'motor {' '.join(path)}' is not a leaf command in parser"
                )

        self.assertEqual(
            mismatches,
            [],
            "Implemented capabilities with missing or non-leaf parser paths:\n"
            + "\n".join(mismatches),
        )


if __name__ == "__main__":
    unittest.main()
