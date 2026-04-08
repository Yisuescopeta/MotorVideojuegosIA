"""
tests/test_start_here_ai_coherence.py - Tests validating START_HERE_AI.md aligns with official CLI

Ensures the generated START_HERE_AI.md:
- Uses only current capability IDs
- References only official CLI commands (no legacy)
- Contains no obsolete references
"""

from __future__ import annotations

import re
import unittest

from engine.ai import get_default_registry, MotorAIBootstrapBuilder


class StartHereAICoherenceTests(unittest.TestCase):
    """Tests ensuring START_HERE_AI.md matches official CLI contract."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = get_default_registry()
        self.builder = MotorAIBootstrapBuilder(self.registry)
        self.content = self.builder.build_start_here_md("TestProject")

    def test_no_legacy_upsert_state_in_content(self) -> None:
        """CRITICAL: START_HERE_AI.md must not reference legacy 'upsert-state' command."""
        self.assertNotIn(
            "upsert-state", self.content,
            "START_HERE_AI.md must not contain legacy 'upsert-state' command. "
            "Use 'animator state create' instead."
        )

    def test_no_legacy_remove_state_in_content(self) -> None:
        """CRITICAL: START_HERE_AI.md must not reference legacy 'remove-state' command."""
        self.assertNotIn(
            "remove-state", self.content,
            "START_HERE_AI.md must not contain legacy 'remove-state' command. "
            "Use 'animator state remove' instead."
        )

    def test_uses_animator_state_create(self) -> None:
        """START_HERE_AI.md should use 'animator state create' (official)."""
        self.assertIn(
            "animator state create", self.content,
            "START_HERE_AI.md should document 'animator state create' command"
        )

    def test_uses_animator_ensure(self) -> None:
        """START_HERE_AI.md should use 'animator ensure' (official)."""
        self.assertIn(
            "animator ensure", self.content,
            "START_HERE_AI.md should document 'animator ensure' command"
        )

    def test_no_obsolete_capability_ids(self) -> None:
        """START_HERE_AI.md common capabilities should exist in registry."""
        # These are the IDs that should be in common_caps list
        expected_implemented = [
            "scene:load", "scene:save", "scene:create",
            "entity:create",
            "component:add",
            "asset:list", "asset:slice:grid", "asset:slice:list",
            "animator:set_sheet", "animator:state:create", "animator:info",
            "introspect:capabilities",
        ]
        
        for cap_id in expected_implemented:
            cap = self.registry.get(cap_id)
            self.assertIsNotNone(
                cap, f"Capability {cap_id} should exist in registry"
            )
            self.assertEqual(
                cap.status, "implemented",
                f"Capability {cap_id} should be 'implemented', not '{cap.status}'"
            )

    def test_no_planned_capabilities_in_common(self) -> None:
        """Common capabilities list should not include planned capabilities."""
        # These should NOT appear as common capabilities
        planned_ids = [
            "entity:delete", "entity:parent", "entity:list",
            "component:edit", "component:remove",
            "prefab:instantiate", "prefab:list",
            "runtime:play", "runtime:stop", "runtime:step",
            "introspect:status", "introspect:entity",
        ]

        for cap_id in planned_ids:
            cap = self.registry.get(cap_id)
            if cap:
                self.assertEqual(
                    cap.status, "planned",
                    f"If {cap_id} exists, it should be 'planned', not in common list"
                )

    def test_capabilities_by_category_only_implemented(self) -> None:
        """Implemented section must NOT include planned capabilities."""
        registry = get_default_registry()
        planned_ids = {cap.id for cap in registry.list_planned()}

        # Find the implemented capabilities section
        implemented_start = self.content.find("## Implemented Capabilities")
        coming_start = self.content.find("## Coming Soon")
        self.assertGreater(implemented_start, 0, "Should have 'Implemented Capabilities' section")

        implemented_section = self.content[implemented_start:coming_start if coming_start > 0 else len(self.content)]

        for pid in planned_ids:
            self.assertNotIn(
                pid, implemented_section,
                f"Planned capability '{pid}' must NOT appear in the implemented section "
                f"because it would mislead an AI into thinking it's available"
            )

    def test_coming_soon_section_exists_with_planned(self) -> None:
        """'Coming Soon' section must list all planned capabilities."""
        self.assertIn(
            "## Coming Soon", self.content,
            "START_HERE_AI.md must have a 'Coming Soon' section "
            "to explicitly separate future capabilities from implemented ones"
        )

        registry = get_default_registry()
        planned_ids = {cap.id for cap in registry.list_planned()}

        missing = []
        for pid in planned_ids:
            if pid not in self.content:
                missing.append(pid)

        self.assertEqual(
            len(missing), 0,
            f"Planned capabilities missing from 'Coming Soon' section: {missing}"
        )

    def test_no_planned_cli_command_in_quick_workflow(self) -> None:
        """Quick Workflow must use only implemented commands (no planned)."""
        # Find the Quick Workflow section
        workflow_start = self.content.find("### Quick Workflow")
        naming_start = self.content.find("## Naming Conventions")
        self.assertGreater(workflow_start, 0)

        workflow_content = self.content[workflow_start:naming_start]

        # Extract all 'motor X Y Z' commands from the workflow
        import re
        commands = re.findall(r'motor \w+(?: \w+)*', workflow_content)

        registry = get_default_registry()
        planned_commands = set()
        for cap in registry.list_planned():
            if cap.cli_command.startswith("motor "):
                # Strip motor prefix and optional args
                parts = cap.cli_command.split()[1:]
                clean = [p for p in parts if not p.startswith(('<', '['))]
                if clean:
                    planned_commands.add("motor " + " ".join(clean[:3]))

        violations = []
        for cmd in commands:
            for planned in planned_commands:
                if cmd.startswith(planned):
                    violations.append(f"{cmd} (planned command)")

        self.assertEqual(
            len(violations), 0,
            f"Quick Workflow contains planned commands: {violations}"
        )

    def test_official_cli_syntax_used(self) -> None:
        """All CLI examples should use 'motor' prefix."""
        # Find all CLI command examples (lines starting with motor)
        motor_lines = [line for line in self.content.split('\n') 
                      if line.strip().startswith('motor ')]
        
        self.assertGreater(
            len(motor_lines), 0,
            "START_HERE_AI.md should contain CLI examples"
        )
        
        for line in motor_lines:
            # Should not use legacy commands
            self.assertNotIn(
                "tools.engine_cli", line,
                f"Line should not use legacy tools.engine_cli: {line}"
            )

    def test_animator_workflow_is_correct(self) -> None:
        """Animator workflow should show correct sequence: ensure -> set-sheet -> state create."""
        # Find the "Configure animator" workflow section
        workflow_start = self.content.find("## Quick Workflow")
        self.assertGreater(workflow_start, 0, "Should have Quick Workflow section")
        
        # Only look at content after workflow section
        workflow_content = self.content[workflow_start:]
        
        ensure_pos = workflow_content.find("animator ensure")
        set_sheet_pos = workflow_content.find("animator set-sheet")
        state_create_pos = workflow_content.find("animator state create")
        
        self.assertGreater(
            ensure_pos, 0,
            "Quick workflow should document 'animator ensure' step"
        )
        self.assertGreater(
            set_sheet_pos, ensure_pos,
            "'animator set-sheet' should come after 'animator ensure' in workflow"
        )
        self.assertGreater(
            state_create_pos, set_sheet_pos,
            "'animator state create' should come after 'animator set-sheet' in workflow"
        )

    def test_motor_capabilities_documented(self) -> None:
        """Should reference 'motor capabilities' command."""
        self.assertIn(
            "motor capabilities", self.content,
            "START_HERE_AI.md should document 'motor capabilities' command"
        )

    def test_motor_doctor_documented(self) -> None:
        """Should reference 'motor doctor' command."""
        self.assertIn(
            "motor doctor", self.content,
            "START_HERE_AI.md should document 'motor doctor' command"
        )

    def test_legacy_only_in_deprecated_note(self) -> None:
        """Legacy references should only appear in explicit deprecation notes."""
        # Check that tools.engine_cli is only mentioned in context of deprecation
        if "tools.engine_cli" in self.content:
            # Find the context
            lines = self.content.split('\n')
            for i, line in enumerate(lines):
                if "tools.engine_cli" in line:
                    # Check surrounding lines for deprecation context
                    context = ' '.join(lines[max(0,i-2):i+3]).lower()
                    self.assertIn(
                        "deprecated", context,
                        f"tools.engine_cli should only appear in deprecation context: {line}"
                    )


class StartHereAIContentTests(unittest.TestCase):
    """Tests for content structure of START_HERE_AI.md."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = get_default_registry()
        self.builder = MotorAIBootstrapBuilder(self.registry)
        self.content = self.builder.build_start_here_md("TestProject")

    def test_has_quick_workflow_section(self) -> None:
        """Should have Quick Workflow section."""
        self.assertIn("## Quick Workflow", self.content)

    def test_has_implemented_capabilities_section(self) -> None:
        """Should clearly separate capabilities that are available now."""
        self.assertIn("## Implemented Capabilities", self.content)
        self.assertIn("available now and are safe to use", self.content)

    def test_has_naming_conventions_section(self) -> None:
        """Should have Naming Conventions section."""
        self.assertIn("## Naming Conventions", self.content)

    def test_has_official_cli_section(self) -> None:
        """Should have Official CLI section."""
        self.assertIn("## Official CLI", self.content)

    def test_no_animator_create_id(self) -> None:
        """Should not reference obsolete 'animator:create' ID."""
        # animator:create was replaced by animator:set_sheet and animator:ensure
        lines = self.content.split('\n')
        for line in lines:
            if 'animator:create' in line:
                self.fail(
                    "START_HERE_AI.md references obsolete 'animator:create'. "
                    "Use 'animator:set_sheet' or 'animator:ensure' instead."
                )

    def test_no_animator_state_add_id(self) -> None:
        """Should not reference obsolete 'animator:state:add' ID."""
        # animator:state:add was replaced by animator:state:create
        self.assertNotIn(
            "animator:state:add", self.content,
            "START_HERE_AI.md references obsolete 'animator:state:add'. "
            "Use 'animator:state:create' instead."
        )


if __name__ == "__main__":
    unittest.main()
