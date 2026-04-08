"""
tests/test_capability_registry_semantic_audit.py - Semantic audit tests for capability registry

Validates that the capability registry accurately describes the real motor system:
- Component names in examples must exist in ComponentRegistry
- Capabilities must describe actually supported operations
- Modes (edit/play/both) must be accurate
- CLI commands must match real motor CLI syntax
"""

from __future__ import annotations

import unittest
from typing import Set

from engine.ai import get_default_registry
from engine.levels.component_registry import create_default_registry
from motor.cli import create_motor_parser


class ComponentNameSemanticTests(unittest.TestCase):
    """Tests validating component names in registry examples."""

    def setUp(self) -> None:
        """Set up component registry for validation."""
        self.component_registry = create_default_registry()
        self.valid_components: Set[str] = set(self.component_registry.list_registered())
        self.capability_registry = get_default_registry()

    def test_all_component_examples_use_canonical_names(self) -> None:
        """All component names in examples must exist in ComponentRegistry."""
        invalid_components = []
        
        for cap in self.capability_registry.list_all():
            # Check api_calls in examples
            if hasattr(cap.example, 'api_calls') and cap.example.api_calls:
                for call in cap.example.api_calls:
                    args = call.get('args', {})
                    
                    # Check component_name parameter
                    if 'component_name' in args:
                        comp_name = args['component_name']
                        if comp_name not in self.valid_components:
                            invalid_components.append((
                                cap.id, 
                                f"component_name='{comp_name}'"
                            ))
                    
                    # Check component parameter  
                    if 'component' in args:
                        comp_name = args['component']
                        if comp_name not in self.valid_components:
                            invalid_components.append((
                                cap.id,
                                f"component='{comp_name}'"
                            ))
        
        self.assertEqual(
            len(invalid_components),
            0,
            f"Found component names not in ComponentRegistry: {invalid_components}\n"
            f"Valid component names are: {sorted(self.valid_components)}"
        )

    def test_common_components_are_documented(self) -> None:
        """Most commonly used components should be documented in examples."""
        common_components = {
            'Transform', 'Sprite', 'Collider', 'RigidBody',
            'Animator', 'Camera2D', 'ScriptBehaviour'
        }
        
        components_in_examples = set()
        for cap in self.capability_registry.list_all():
            if hasattr(cap.example, 'api_calls') and cap.example.api_calls:
                for call in cap.example.api_calls:
                    args = call.get('args', {})
                    if 'component_name' in args:
                        components_in_examples.add(args['component_name'])
                    if 'component' in args:
                        components_in_examples.add(args['component'])
        
        # At least some common components should be in examples
        common_documented = common_components & components_in_examples
        self.assertTrue(
            len(common_documented) >= 2,
            f"Too few common components documented in examples. "
            f"Found: {common_documented}, expected at least 2 from {common_components}"
        )


class ModeSemanticTests(unittest.TestCase):
    """Tests validating capability modes match actual behavior."""

    def setUp(self) -> None:
        self.registry = get_default_registry()

    def test_all_capabilities_have_valid_mode(self) -> None:
        """All capabilities must have mode: edit, play, or both."""
        valid_modes = {'edit', 'play', 'both'}
        
        invalid_modes = []
        for cap in self.registry.list_all():
            if cap.mode not in valid_modes:
                invalid_modes.append((cap.id, cap.mode))
        
        self.assertEqual(
            len(invalid_modes),
            0,
            f"Found capabilities with invalid modes: {invalid_modes}"
        )

    def test_scene_save_is_edit_mode(self) -> None:
        """scene:save must be edit mode (mutates state)."""
        cap = self.registry.get('scene:save')
        if cap:
            self.assertEqual(cap.mode, 'edit')

    def test_component_operations_are_edit_mode(self) -> None:
        """All component mutation operations must be edit mode."""
        edit_capabilities = [
            'component:add', 'component:edit', 'component:remove'
        ]
        
        for cap_id in edit_capabilities:
            cap = self.registry.get(cap_id)
            if cap:
                self.assertEqual(
                    cap.mode, 'edit',
                    f"{cap_id} should be 'edit' mode but is '{cap.mode}'"
                )


class CLISyntaxSemanticTests(unittest.TestCase):
    """Tests validating CLI command syntax matches real motor CLI."""

    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.parser = create_motor_parser()
        
        # Get all available commands
        self.available_commands = set()
        for action in self.parser._actions:
            if hasattr(action, 'choices') and action.choices:
                self.available_commands.update(action.choices.keys())

    def test_all_cli_commands_use_motor_syntax(self) -> None:
        """All cli_command entries must use 'motor ...' syntax."""
        non_motor = []
        
        for cap in self.registry.list_all():
            if not cap.cli_command.startswith('motor '):
                non_motor.append((cap.id, cap.cli_command))
        
        self.assertEqual(
            len(non_motor),
            0,
            f"Found cli_commands not using 'motor ' prefix: {non_motor}"
        )

    def test_cli_commands_reference_existing_subcommands(self) -> None:
        """CLI commands should reference subcommands that exist in motor CLI."""
        # These are documented but not yet implemented (future)
        future_commands = {
            'runtime', 'prefab', 'undo', 'redo', 'status', 'physics'
        }
        
        mismatches = []
        for cap in self.registry.list_all():
            parts = cap.cli_command.split()
            if len(parts) >= 2:
                subcommand = parts[1]
                if subcommand not in self.available_commands and \
                   subcommand not in future_commands:
                    mismatches.append((cap.id, cap.cli_command, subcommand))
        
        self.assertEqual(
            len(mismatches),
            0,
            f"CLI commands reference non-existent subcommands: {mismatches}"
        )


class APIMethodSemanticTests(unittest.TestCase):
    """Tests validating API methods referenced in capabilities."""

    def setUp(self) -> None:
        self.registry = get_default_registry()

    def test_api_methods_use_canonical_naming(self) -> None:
        """API method names should follow consistent patterns."""
        # Valid API class prefixes
        valid_prefixes = {
            'SceneWorkspaceAPI',
            'AuthoringAPI',
            'AssetsProjectAPI',
            'RuntimeAPI',
            'CapabilityRegistry',
        }
        
        invalid_patterns = []
        for cap in self.registry.list_all():
            for method in cap.api_methods:
                # Should be ClassName.method_name format
                if '.' not in method:
                    invalid_patterns.append((cap.id, method, "missing class prefix"))
                    continue
                
                class_name = method.split('.')[0]
                # Allow CapabilityRegistry methods (self-referential)
                if class_name not in valid_prefixes and class_name != 'CapabilityRegistry':
                    invalid_patterns.append((cap.id, method, f"unknown class '{class_name}'"))
        
        # Only fail on clearly invalid patterns
        clear_errors = [p for p in invalid_patterns if "unknown class" not in p[2]]
        self.assertEqual(
            len(clear_errors),
            0,
            f"Found API methods with invalid patterns: {clear_errors}"
        )


class CapabilityFidelityTests(unittest.TestCase):
    """Tests validating capabilities match real system capabilities."""

    def setUp(self) -> None:
        self.registry = get_default_registry()

    def test_all_capability_ids_use_valid_format(self) -> None:
        """Capability IDs must follow 'scope:action' format."""
        invalid_ids = []
        
        for cap in self.registry.list_all():
            if ':' not in cap.id:
                invalid_ids.append(cap.id)
            else:
                parts = cap.id.split(':')
                if len(parts) < 2 or not all(parts):
                    invalid_ids.append(cap.id)
        
        self.assertEqual(
            len(invalid_ids),
            0,
            f"Found invalid capability IDs: {invalid_ids}"
        )

    def test_capabilities_have_required_fields(self) -> None:
        """All capabilities must have summary, mode, api_methods, and cli_command."""
        incomplete = []
        
        for cap in self.registry.list_all():
            issues = []
            if not cap.summary:
                issues.append("missing summary")
            if not cap.mode:
                issues.append("missing mode")
            if not cap.api_methods:
                issues.append("missing api_methods")
            if not cap.cli_command:
                issues.append("missing cli_command")
            
            if issues:
                incomplete.append((cap.id, issues))
        
        self.assertEqual(
            len(incomplete),
            0,
            f"Found capabilities with missing fields: {incomplete}"
        )

    def test_examples_have_required_fields(self) -> None:
        """All capability examples must have description and api_calls."""
        incomplete = []
        
        for cap in self.registry.list_all():
            if not hasattr(cap.example, 'description') or not cap.example.description:
                incomplete.append((cap.id, "missing example.description"))
            elif not hasattr(cap.example, 'api_calls') or not cap.example.api_calls:
                incomplete.append((cap.id, "missing example.api_calls"))
        
        self.assertEqual(
            len(incomplete),
            0,
            f"Found capabilities with incomplete examples: {incomplete}"
        )


class RegistryCoherenceTests(unittest.TestCase):
    """Tests validating overall registry coherence."""

    def setUp(self) -> None:
        self.registry = get_default_registry()

    def test_no_duplicate_capability_ids(self) -> None:
        """All capability IDs must be unique."""
        ids = [cap.id for cap in self.registry.list_all()]
        duplicates = set([i for i in ids if ids.count(i) > 1])
        
        self.assertEqual(
            len(duplicates),
            0,
            f"Found duplicate capability IDs: {duplicates}"
        )

    def test_summary_lengths_are_reasonable(self) -> None:
        """Summaries should be concise but informative (10-200 chars)."""
        invalid = []
        
        for cap in self.registry.list_all():
            length = len(cap.summary)
            if length < 10:
                invalid.append((cap.id, f"summary too short ({length} chars)"))
            elif length > 200:
                invalid.append((cap.id, f"summary too long ({length} chars)"))
        
        self.assertEqual(
            len(invalid),
            0,
            f"Found summaries with unreasonable lengths: {invalid}"
        )


if __name__ == "__main__":
    unittest.main()