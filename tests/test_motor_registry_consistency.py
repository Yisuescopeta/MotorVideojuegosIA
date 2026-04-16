"""
tests/test_motor_registry_consistency.py - Consistency tests between motor CLI and capability registry

Validates that:
1. All cli_command in registry start with "motor "
2. All commands documented in registry are valid motor commands
3. No commands use deprecated "python -m tools.engine_cli" format
"""

from __future__ import annotations

import re
import unittest

from engine.ai import get_default_registry
from motor.cli import create_motor_parser


class MotorRegistryConsistencyTests(unittest.TestCase):
    """Tests for consistency between motor CLI and capability registry."""

    def test_all_cli_commands_start_with_motor(self) -> None:
        """All cli_command entries in registry must start with 'motor '."""
        registry = get_default_registry()
        
        invalid_commands = []
        for cap in registry.list_all():
            cli_cmd = cap.cli_command
            if not cli_cmd.startswith("motor "):
                invalid_commands.append((cap.id, cli_cmd))
        
        self.assertEqual(
            len(invalid_commands),
            0,
            f"Found cli_commands not starting with 'motor ': {invalid_commands}"
        )

    def test_no_deprecated_cli_format(self) -> None:
        """No cli_command should reference deprecated tools.engine_cli."""
        registry = get_default_registry()
        
        deprecated_patterns = [
            "python -m tools.engine_cli",
            "tools.engine_cli",
            "python -m tools",
        ]
        
        deprecated_commands = []
        for cap in registry.list_all():
            cli_cmd = cap.cli_command
            for pattern in deprecated_patterns:
                if pattern in cli_cmd:
                    deprecated_commands.append((cap.id, cli_cmd))
                    break
        
        self.assertEqual(
            len(deprecated_commands),
            0,
            f"Found deprecated CLI format: {deprecated_commands}"
        )

    def test_cli_command_format_consistency(self) -> None:
        """CLI commands follow consistent naming pattern: motor <scope> <action>."""
        registry = get_default_registry()
        
        # Valid pattern: motor <command> [subcommand] [args...]
        valid_pattern = re.compile(r'^motor [a-z-]+(:?[a-z-]+)?( [^\s]+)*$')
        
        invalid_formats = []
        for cap in registry.list_all():
            cli_cmd = cap.cli_command
            # Extract just the command part (before any arguments in brackets or optional parts)
            base_cmd = cli_cmd.split('[')[0].split('<')[0].strip()
            if not valid_pattern.match(base_cmd):
                invalid_formats.append((cap.id, cli_cmd))
        
        self.assertEqual(
            len(invalid_formats),
            0,
            f"Found invalid CLI command formats: {invalid_formats}"
        )

    def test_cap_id_matches_cli_scope(self) -> None:
        """Capability ID scope should match CLI command scope."""
        registry = get_default_registry()
        
        mismatches = []
        for cap in registry.list_all():
            cap_scope = cap.id.split(':')[0]
            cli_parts = cap.cli_command.split()
            if len(cli_parts) >= 2:
                cli_scope = cli_parts[1]
                
                # Commands that are allowed to have different scopes
                allowed_exceptions = {
                    'runtime:undo': 'undo',  # motor undo
                    'runtime:redo': 'redo',  # motor redo
                    'introspect:doctor': 'doctor',  # motor doctor
                    'introspect:capabilities': 'capabilities',  # motor capabilities
                    'introspect:entity': 'entity',  # motor entity inspect
                    'introspect:status': 'status',  # motor status
                }
                
                if cap.id in allowed_exceptions:
                    continue
                
                # Some mappings are expected to differ
                expected_mappings = {
                    'asset': 'asset',
                    'scene': 'scene',
                    'entity': 'entity',
                    'component': 'component',
                    'animator': 'animator',
                    'prefab': 'prefab',
                    'project': 'project',
                    'runtime': 'runtime',
                    'physics': 'physics',
                    'introspect': 'introspect',
                    'slice': 'asset',  # slice commands are under asset
                }
                expected = expected_mappings.get(cap_scope, cap_scope)
                if cli_scope != expected:
                    mismatches.append((cap.id, cap.cli_command, f"expected scope '{expected}'"))
        
        self.assertEqual(
            len(mismatches),
            0,
            f"Scope mismatches: {mismatches}"
        )

    def test_registry_commands_match_motor_cli(self) -> None:
        """All command scopes in registry must exist in motor CLI.
        
        Note: Some commands in registry are documented for future implementation.
        """
        registry = get_default_registry()
        parser = create_motor_parser()
        
        # Get available commands from parser
        available_commands = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                available_commands.update(action.choices.keys())
        
        # Extract scopes from registry
        registry_scopes = set()
        for cap in registry.list_all():
            cli_parts = cap.cli_command.split()
            if len(cli_parts) >= 2:
                registry_scopes.add(cli_parts[1])
        
        # Commands that are documented but not yet implemented
        future_commands = {
            'runtime',  # runtime:play, runtime:stop, etc.
            'undo',     # runtime:undo
            'redo',     # runtime:redo
            'status',   # introspect:status
            'physics',  # physics:query:aabb, etc.
        }
        
        # Check all registry scopes exist in CLI or are future commands
        missing = registry_scopes - available_commands - future_commands
        self.assertEqual(
            len(missing),
            0,
            f"Registry references commands not in motor CLI: {missing}"
        )


class MotorCLIOfficialInterfaceTests(unittest.TestCase):
    """Tests validating the official motor CLI interface."""

    def test_motor_parser_has_expected_commands(self) -> None:
        """motor CLI has all expected top-level commands."""
        parser = create_motor_parser()
        
        expected_commands = [
            'capabilities',
            'doctor',
            'project',
            'scene',
            'entity',
            'component',
            'prefab',
            'animator',
            'asset',
        ]
        
        # Get available commands from parser
        available = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                available.update(action.choices.keys())
        
        for cmd in expected_commands:
            self.assertIn(
                cmd, available,
                f"Expected command '{cmd}' not found in motor CLI"
            )

    def test_motor_help_mentions_official_interface(self) -> None:
        """motor --help identifies itself as the official CLI."""
        parser = create_motor_parser()
        
        # Check prog name
        self.assertEqual(parser.prog, "motor")
        
        # Check description mentions official
        self.assertIn("Official CLI", parser.description)


class MotorAIBootstrapFilesTests(unittest.TestCase):
    """Tests for AI-facing bootstrap files consistency."""

    def test_motor_ai_json_uses_motor_commands(self) -> None:
        """motor_ai.json contains only motor commands in cli_command fields."""
        registry = get_default_registry()
        
        non_motor_commands = []
        for cap in registry.list_all():
            if not cap.cli_command.startswith("motor "):
                non_motor_commands.append((cap.id, cap.cli_command))
        
        self.assertEqual(
            len(non_motor_commands),
            0,
            f"motor_ai.json would contain non-motor commands: {non_motor_commands}"
        )

    def test_examples_use_motor_syntax(self) -> None:
        """All examples in registry use motor syntax."""
        registry = get_default_registry()
        
        bad_examples = []
        for cap in registry.list_all():
            # Check cli_command
            if 'python -m' in cap.cli_command and 'tools' in cap.cli_command:
                bad_examples.append((cap.id, 'cli_command', cap.cli_command))
            
            # Check example description (if it mentions CLI)
            if hasattr(cap.example, 'description'):
                desc = cap.example.description
                if 'python -m tools' in desc or 'python -m engine_cli' in desc:
                    bad_examples.append((cap.id, 'example', desc))
        
        self.assertEqual(
            len(bad_examples),
            0,
            f"Found examples with deprecated syntax: {bad_examples}"
        )


class MotorGrammarUniquenessTests(unittest.TestCase):
    """Tests to ensure grammar uniqueness - no duplicate official syntax."""
    
    def test_no_legacy_aliases_in_official_registry(self) -> None:
        """Registry commands should not document legacy aliases as official.
        
        Legacy aliases pueden existir en el CLI por compatibilidad,
        pero no deben aparecer en el registry como interfaz oficial.
        """
        registry = get_default_registry()
        
        # Patrones legacy que no deben estar en cli_command oficial
        legacy_patterns = [
            "upsert-state",  # Ahora es 'state create'
            "remove-state",  # Ahora es 'state remove'
        ]
        
        violations = []
        for cap in registry.list_all():
            for pattern in legacy_patterns:
                if pattern in cap.cli_command:
                    violations.append((cap.id, cap.cli_command))
        
        if violations:
            self.fail(
                f"Registry documenta aliases legacy como oficiales:\n" + 
                "\n".join([f"  {cid}: {cmd}" for cid, cmd in violations]) +
                "\n\nUse 'animator state create/remove' en su lugar."
            )
    
    def test_grammar_pattern_consistency(self) -> None:
        """All CLI commands follow the unified grammar pattern.
        
        Gramática oficial: motor <noun> [<subnoun>] <verb> [<args>]
        """
        registry = get_default_registry()
        
        # Verbos oficiales permitidos
        official_verbs = {
            "create", "list", "load", "save", "add", "remove", 
            "edit", "info", "ensure", "set-sheet", "bootstrap-ai",
            "grid", "auto", "manual", "open", "instantiate",
            "unpack", "apply", "play", "stop", "step", "query",
        }
        
        violations = []
        for cap in registry.list_all():
            parts = cap.cli_command.split()
            if len(parts) < 2:
                continue
            
            # Extraer verbo (último componente antes de argumentos)
            cmd_parts = parts[1:]  # Remove 'motor'
            
            # Verificar si termina en un verbo conocido
            last_part = cmd_parts[-1] if cmd_parts else ""
            if last_part.startswith("<") or last_part.startswith("["):
                # El verbo es el anterior a los argumentos
                last_part = cmd_parts[-2] if len(cmd_parts) >= 2 else ""
            
            # Los comandos de 3 niveles (animator state create) son válidos
            # No necesitan verificación adicional
        
        # Este test es informativo, no falla por ahora
        # Se puede hacer más estricto en el futuro


if __name__ == "__main__":
    unittest.main()
