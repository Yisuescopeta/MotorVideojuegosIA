"""
tests/test_capability_registry_semantic_accuracy.py

Tests to verify that capability registry descriptions accurately reflect
the actual behavior of the engine implementation.

These tests catch discrepancies between documented (AI-facing) behavior
and actual implementation.
"""

from __future__ import annotations

import json
import unittest

from engine.ai.registry_builder import CapabilityRegistryBuilder, MotorAIBootstrapBuilder


class EntityDeleteSemanticTests(unittest.TestCase):
    """
    Tests that entity:delete capability description matches actual behavior.

    Actual behavior: Children are REPARENTED to grandparent, not deleted.

    Note: Behavioral tests are covered by structural_authoring tests.
    These tests verify the registry description accuracy.
    """

    def test_registry_entity_delete_description_is_accurate(self) -> None:
        """Verify the registry description mentions reparenting behavior."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        cap = registry.get("entity:delete")
        self.assertIsNotNone(cap)

        # Summary should mention reparenting
        self.assertIn("reparent", cap.summary.lower(),
                     "Summary should mention reparenting")

        # Notes should clarify children are not deleted
        self.assertIn("reparent", cap.notes.lower(),
                     "Notes should mention reparenting")
        self.assertIn("grandparent", cap.notes.lower(),
                     "Notes should mention grandparent")

        # Expected outcome should describe the actual result
        outcome = cap.example.expected_outcome.lower()
        self.assertTrue(
            "reparent" in outcome or "grandparent" in outcome or "unparent" in outcome,
            f"Expected outcome should describe reparenting: {outcome}"
        )


class AnimatorStateRemoveSemanticTests(unittest.TestCase):
    """
    Tests that animator:state:remove capability description matches actual behavior.

    Documented behavior (WRONG): "Cannot remove the last state"
    Actual behavior: CAN remove the last state (schema uses placeholder)

    Note: Behavioral tests are covered by test_motor_animator_e2e tests.
    These tests verify the registry description accuracy.
    """

    def test_registry_animator_state_remove_description_is_accurate(self) -> None:
        """Verify the registry description mentions that last state CAN be removed."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        cap = registry.get("animator:state:remove")
        self.assertIsNotNone(cap)

        notes_lower = cap.notes.lower()

        # Should NOT claim last state cannot be removed (old incorrect docs)
        self.assertNotIn("cannot remove the last", notes_lower,
                        "Notes should NOT claim last state cannot be removed")

        # Should mention that removal IS possible
        self.assertIn("can remove", notes_lower,
                     "Notes should mention that last state CAN be removed")

        # Should mention on_complete clearing
        self.assertIn("on_complete", notes_lower,
                     "Notes should mention on_complete references are cleared")


class CapabilityRegistryDescriptionTests(unittest.TestCase):
    """
    Tests that capability descriptions in registry match actual implementation.
    """

    def test_entity_delete_notes_mentions_reparenting(self) -> None:
        """Verify entity:delete notes mentions reparenting, not recursive deletion."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        cap = registry.get("entity:delete")
        self.assertIsNotNone(cap)

        # Check notes mentions reparenting
        self.assertIn("reparent", cap.notes.lower(),
                     "entity:delete notes should mention reparenting behavior")

        # Check notes does NOT claim children are deleted
        self.assertNotIn("removes child", cap.notes.lower(),
                        "entity:delete notes should NOT claim children are removed")

    def test_entity_delete_expected_outcome_is_accurate(self) -> None:
        """Verify entity:delete expected_outcome accurately describes behavior."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        cap = registry.get("entity:delete")
        self.assertIsNotNone(cap)

        outcome = cap.example.expected_outcome.lower()

        # Should mention reparenting or grandparent
        mentions_reparenting = (
            "reparent" in outcome or
            "grandparent" in outcome or
            "unparent" in outcome
        )
        self.assertTrue(mentions_reparenting,
                       f"expected_outcome should mention reparenting: {outcome}")

    def test_animator_state_remove_notes_allows_last_state_removal(self) -> None:
        """Verify animator:state:remove notes correctly states last state CAN be removed."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        cap = registry.get("animator:state:remove")
        self.assertIsNotNone(cap)

        notes_lower = cap.notes.lower()

        # Should mention that last state CAN be removed
        # (old incorrect docs said "Cannot remove the last state")
        self.assertNotIn("cannot remove the last", notes_lower,
                        "Notes should NOT claim last state cannot be removed")

        # Should mention that removal IS possible
        self.assertIn("can remove", notes_lower,
                     "Notes should mention that last state CAN be removed")

    def test_no_planned_capabilities_have_implementations(self) -> None:
        """Verify planned capabilities are partitioned from implemented ones."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        planned = registry.list_planned()
        implemented_ids = {cap.id for cap in registry.list_implemented()}

        self.assertGreater(len(planned), 0, "Expected planned capabilities in the registry")
        for cap in planned:
            self.assertEqual(cap.status, "planned")
            self.assertNotIn(cap.id, implemented_ids)

    def test_all_registered_capabilities_are_implemented(self) -> None:
        """Verify registry separates implemented and planned capabilities."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        all_caps = registry.list_all()
        implemented = [c for c in all_caps if c.status == "implemented"]
        planned = [c for c in all_caps if c.status == "planned"]

        self.assertGreater(len(implemented), 0)
        self.assertGreater(len(planned), 0)
        self.assertEqual(len(implemented) + len(planned), len(all_caps))


class RegistryBuildTests(unittest.TestCase):
    """Tests for the registry builder itself."""

    def test_registry_builds_without_errors(self) -> None:
        """Verify registry builds successfully."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()

        # Should have capabilities
        self.assertGreater(len(registry.list_all()), 0, "Registry should have capabilities")

        # Should validate without errors
        errors = registry.validate()
        self.assertEqual(len(errors), 0, f"Registry validation errors: {errors}")

    def test_motor_ai_json_includes_implemented_capabilities(self) -> None:
        """Verify motor_ai.json includes all implemented capabilities."""
        builder = CapabilityRegistryBuilder()
        registry = builder.build()
        bootstrap_builder = MotorAIBootstrapBuilder(registry)

        json_content = bootstrap_builder.build_motor_ai_json({
            "project": {"name": "Test", "root": "."},
            "entrypoints": {},
        })
        data = json.loads(json_content)

        # Should have implemented_capabilities array
        self.assertIn("implemented_capabilities", data)
        implemented = data["implemented_capabilities"]
        self.assertGreater(len(implemented), 0, "Should have implemented capabilities")

        planned = data["planned_capabilities"]

        self.assertEqual(len(implemented), len(registry.list_implemented()))
        self.assertEqual(len(planned), len(registry.list_planned()))
        self.assertEqual(
            len(implemented) + len(planned),
            len(registry.list_all()),
            "Implemented + planned should match full registry",
        )


if __name__ == "__main__":
    unittest.main()
