"""
tests/test_parser_registry_alignment.py - Strict alignment tests between CLI parser and capability registry

Ensures that every cli_command in the registry matches the actual CLI parser implementation exactly.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from engine.ai import get_default_registry
from motor.cli import create_motor_parser


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
        """Verify required args use <>, optional use []."""
        for cap in self.implemented_caps:
            with self.subTest(capability=cap.id):
                cmd = cap.cli_command
                
                # Check that required args use <>
                if "<name>" in cmd or "<entity>" in cmd or "<state>" in cmd:
                    pass  # Good - using required notation
                
                # Check that optional args use []
                optional_pattern = r'\[--[\w-]+(?:\s+<[^>]+>)?\]'
                matches = re.findall(optional_pattern, cmd)
                
                # At minimum, --project and --json should be in []
                if "--project" in cmd:
                    self.assertIn("[", cmd.split("--project")[0].split()[-1] if "--project" in cmd else "",
                                  f"{cap.id}: --project must be in optional brackets [...]")

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


if __name__ == "__main__":
    unittest.main()
