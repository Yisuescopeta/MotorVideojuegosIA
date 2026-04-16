"""
tests/test_ai_capability_registry.py - Contract tests for AI capability registry

Validates:
- Registry structure and invariants
- Capability uniqueness
- Required fields
- Serialization round-trip
- Integration with project bootstrap
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
import tempfile

from engine.ai import (
    Capability,
    CapabilityExample,
    CapabilityRegistry,
    CapabilityRegistryBuilder,
    MotorAIBootstrapBuilder,
    get_default_registry,
)
from engine.config import ENGINE_VERSION


class CapabilityModelTests(unittest.TestCase):
    """Tests for individual Capability model validation."""

    def test_capability_requires_scope_action_format(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Capability(
                id="invalid_no_colon",
                summary="Test",
                mode="edit",
                api_methods=["test"],
                cli_command="test",
                example=CapabilityExample(
                    description="Test",
                    api_calls=[],
                    expected_outcome="",
                ),
            )
        self.assertIn("scope:action", str(ctx.exception))

    def test_capability_requires_valid_mode(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Capability(
                id="test:action",
                summary="Test",
                mode="invalid_mode",
                api_methods=["test"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
            )
        self.assertIn("mode", str(ctx.exception))

    def test_capability_requires_at_least_one_api_method(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            Capability(
                id="test:action",
                summary="Test",
                mode="edit",
                api_methods=[],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
            )
        self.assertIn("api_method", str(ctx.exception))

    def test_capability_accepts_valid_edit_mode(self) -> None:
        cap = Capability(
            id="test:valid",
            summary="A test capability",
            mode="edit",
            api_methods=["TestAPI.method"],
            cli_command="motor test valid",
            example=CapabilityExample(
                description="Do something",
                api_calls=[{"method": "method", "args": {}}],
                expected_outcome="It works",
            ),
            notes="Test notes",
            tags=["test"],
        )
        self.assertEqual(cap.id, "test:valid")
        self.assertEqual(cap.mode, "edit")

    def test_capability_accepts_valid_play_mode(self) -> None:
        cap = Capability(
            id="test:play_action",
            summary="A play mode action",
            mode="play",
            api_methods=["RuntimeAPI.play"],
            cli_command="motor runtime play",
            example=CapabilityExample(description="Play", api_calls=[]),
        )
        self.assertEqual(cap.mode, "play")

    def test_capability_accepts_valid_both_mode(self) -> None:
        cap = Capability(
            id="test:universal",
            summary="Works in both modes",
            mode="both",
            api_methods=["API.method"],
            cli_command="motor test",
            example=CapabilityExample(description="Test", api_calls=[]),
        )
        self.assertEqual(cap.mode, "both")


class CapabilityRegistryContractTests(unittest.TestCase):
    """Tests for CapabilityRegistry contract enforcement."""

    def setUp(self) -> None:
        self.registry = CapabilityRegistry(
            schema_version=1,
            engine_name="TestEngine",
            engine_version="1.0.0",
        )

    def test_register_and_retrieve_capability(self) -> None:
        cap = Capability(
            id="scene:test",
            summary="Test scene capability",
            mode="edit",
            api_methods=["SceneAPI.test"],
            cli_command="motor scene test",
            example=CapabilityExample(description="Test", api_calls=[]),
        )
        self.registry.register(cap)
        retrieved = self.registry.get("scene:test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "scene:test")

    def test_duplicate_capability_id_raises(self) -> None:
        cap = Capability(
            id="scene:test",
            summary="Test",
            mode="edit",
            api_methods=["API.test"],
            cli_command="test",
            example=CapabilityExample(description="Test", api_calls=[]),
        )
        self.registry.register(cap)
        with self.assertRaises(ValueError) as ctx:
            self.registry.register(cap)
        self.assertIn("Duplicate", str(ctx.exception))

    def test_list_all_returns_all_capabilities(self) -> None:
        caps = [
            Capability(
                id=f"test:{i}",
                summary=f"Test {i}",
                mode="edit",
                api_methods=["API.method"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
            )
            for i in range(3)
        ]
        for cap in caps:
            self.registry.register(cap)
        all_caps = self.registry.list_all()
        self.assertEqual(len(all_caps), 3)

    def test_list_by_mode_filters_correctly(self) -> None:
        edit_cap = Capability(
            id="edit:only",
            summary="Edit only",
            mode="edit",
            api_methods=["API.edit"],
            cli_command="edit",
            example=CapabilityExample(description="Edit", api_calls=[]),
        )
        play_cap = Capability(
            id="play:only",
            summary="Play only",
            mode="play",
            api_methods=["API.play"],
            cli_command="play",
            example=CapabilityExample(description="Play", api_calls=[]),
        )
        both_cap = Capability(
            id="both:modes",
            summary="Both modes",
            mode="both",
            api_methods=["API.both"],
            cli_command="both",
            example=CapabilityExample(description="Both", api_calls=[]),
        )
        self.registry.register(edit_cap)
        self.registry.register(play_cap)
        self.registry.register(both_cap)

        edit_caps = self.registry.list_by_mode("edit")
        play_caps = self.registry.list_by_mode("play")
        both_caps = self.registry.list_by_mode("both")

        self.assertEqual(len(edit_caps), 1)
        self.assertEqual(len(play_caps), 1)
        self.assertEqual(len(both_caps), 1)
        self.assertEqual(edit_caps[0].id, "edit:only")

    def test_list_by_tag_filters_correctly(self) -> None:
        cap_a = Capability(
            id="a:cap",
            summary="Tag A",
            mode="edit",
            api_methods=["API.a"],
            cli_command="a",
            example=CapabilityExample(description="A", api_calls=[]),
            tags=["alpha", "shared"],
        )
        cap_b = Capability(
            id="b:cap",
            summary="Tag B",
            mode="edit",
            api_methods=["API.b"],
            cli_command="b",
            example=CapabilityExample(description="B", api_calls=[]),
            tags=["beta", "shared"],
        )
        self.registry.register(cap_a)
        self.registry.register(cap_b)

        alpha_caps = self.registry.list_by_tag("alpha")
        shared_caps = self.registry.list_by_tag("shared")
        missing_caps = self.registry.list_by_tag("gamma")

        self.assertEqual(len(alpha_caps), 1)
        self.assertEqual(len(shared_caps), 2)
        self.assertEqual(len(missing_caps), 0)


class CapabilityRegistryValidationTests(unittest.TestCase):
    """Tests for registry validation."""

    def test_validate_empty_registry_has_no_errors(self) -> None:
        registry = CapabilityRegistry(schema_version=1)
        errors = registry.validate()
        self.assertEqual(errors, [])

    def test_validate_detects_invalid_schema_version(self) -> None:
        registry = CapabilityRegistry(schema_version=0)
        errors = registry.validate()
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_validate_detects_invalid_mode(self) -> None:
        registry = CapabilityRegistry(schema_version=1)
        cap = Capability(
            id="test:valid",
            summary="Test",
            mode="edit",
            api_methods=["API.method"],
            cli_command="test",
            example=CapabilityExample(description="Test", api_calls=[]),
        )
        registry._capabilities["test:valid"] = cap
        # Manually corrupt the mode
        object.__setattr__(cap, "mode", "invalid")
        errors = registry.validate()
        self.assertTrue(any("Invalid mode" in e for e in errors))


class CapabilityRegistrySerializationTests(unittest.TestCase):
    """Tests for registry serialization."""

    def test_to_dict_includes_all_fields(self) -> None:
        registry = CapabilityRegistry(
            schema_version=1,
            engine_name="TestEngine",
            engine_version="2.0.0",
        )
        cap = Capability(
            id="scene:load",
            summary="Load a scene",
            mode="both",
            api_methods=["SceneAPI.load"],
            cli_command="motor scene load",
            example=CapabilityExample(
                description="Load scene",
                api_calls=[{"method": "load", "args": {"path": "test.json"}}],
                expected_outcome="Scene loaded",
            ),
            notes="Important notes",
            tags=["scene", "core"],
        )
        registry.register(cap)

        data = registry.to_dict()

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["engine"]["name"], "TestEngine")
        self.assertEqual(data["engine"]["version"], "2.0.0")
        self.assertEqual(len(data["capabilities"]), 1)

        cap_data = data["capabilities"][0]
        self.assertEqual(cap_data["id"], "scene:load")
        self.assertEqual(cap_data["mode"], "both")
        self.assertEqual(cap_data["api_methods"], ["SceneAPI.load"])
        self.assertEqual(cap_data["cli_command"], "motor scene load")
        self.assertEqual(cap_data["notes"], "Important notes")
        self.assertEqual(cap_data["tags"], ["scene", "core"])

    def test_to_dict_includes_status(self) -> None:
        """to_dict must include status field."""
        registry = CapabilityRegistry(schema_version=1)

        # Test all status values
        for status in ["implemented", "planned", "deprecated"]:
            cap = Capability(
                id=f"test:{status}",
                summary=f"Test {status}",
                mode="edit",
                api_methods=["API.test"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
                status=status,
            )
            registry.register(cap)

        data = registry.to_dict()
        cap_by_id = {c["id"]: c for c in data["capabilities"]}

        self.assertEqual(cap_by_id["test:implemented"]["status"], "implemented")
        self.assertEqual(cap_by_id["test:planned"]["status"], "planned")
        self.assertEqual(cap_by_id["test:deprecated"]["status"], "deprecated")

    def test_from_dict_roundtrip(self) -> None:
        registry = CapabilityRegistry(schema_version=1)
        cap = Capability(
            id="test:roundtrip",
            summary="Test roundtrip",
            mode="edit",
            api_methods=["API.test"],
            cli_command="test",
            example=CapabilityExample(description="Test", api_calls=[{"method": "test"}]),
        )
        registry.register(cap)

        data = registry.to_dict()
        restored = CapabilityRegistry.from_dict(data)

        self.assertEqual(restored.schema_version, registry.schema_version)
        self.assertEqual(len(restored.list_all()), 1)
        restored_cap = restored.get("test:roundtrip")
        self.assertIsNotNone(restored_cap)
        self.assertEqual(restored_cap.summary, "Test roundtrip")

    def test_from_dict_preserves_status(self) -> None:
        """from_dict must preserve status field exactly."""
        registry = CapabilityRegistry(schema_version=1)

        for status in ["implemented", "planned", "deprecated"]:
            cap = Capability(
                id=f"test:{status}",
                summary=f"Test {status}",
                mode="edit",
                api_methods=["API.test"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
                status=status,
            )
            registry.register(cap)

        data = registry.to_dict()
        restored = CapabilityRegistry.from_dict(data)

        for status in ["implemented", "planned", "deprecated"]:
            cap = restored.get(f"test:{status}")
            self.assertIsNotNone(cap, f"Capability test:{status} should exist after roundtrip")
            self.assertEqual(
                cap.status, status,
                f"Status for test:{status} not preserved: expected '{status}', got '{cap.status}'"
            )

    def test_from_dict_defaults_to_implemented(self) -> None:
        """from_dict should default to 'implemented' if status is missing."""
        data = {
            "schema_version": 1,
            "engine": {"name": "Test", "version": "1.0"},
            "capabilities": [
                {
                    "id": "test:no_status",
                    "summary": "Test",
                    "mode": "edit",
                    "api_methods": ["API.test"],
                    "cli_command": "test",
                    "example": {"description": "Test", "api_calls": []},
                    # Note: no "status" field
                }
            ],
        }

        restored = CapabilityRegistry.from_dict(data)
        cap = restored.get("test:no_status")
        self.assertIsNotNone(cap)
        self.assertEqual(cap.status, "implemented", "Missing status should default to 'implemented'")

    def test_list_implemented_filters_correctly(self) -> None:
        """list_implemented must return only capabilities with status='implemented'."""
        registry = CapabilityRegistry(schema_version=1)

        for status in ["implemented", "planned", "deprecated"]:
            cap = Capability(
                id=f"test:{status}",
                summary=f"Test {status}",
                mode="edit",
                api_methods=["API.test"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
                status=status,
            )
            registry.register(cap)

        implemented = registry.list_implemented()
        self.assertEqual(len(implemented), 1)
        self.assertEqual(implemented[0].id, "test:implemented")

    def test_list_planned_filters_correctly(self) -> None:
        """list_planned must return only capabilities with status='planned'."""
        registry = CapabilityRegistry(schema_version=1)

        for status in ["implemented", "planned", "deprecated"]:
            cap = Capability(
                id=f"test:{status}",
                summary=f"Test {status}",
                mode="edit",
                api_methods=["API.test"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
                status=status,
            )
            registry.register(cap)

        planned = registry.list_planned()
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0].id, "test:planned")

    def test_list_deprecated_filters_correctly(self) -> None:
        """list_deprecated must return only capabilities with status='deprecated'."""
        registry = CapabilityRegistry(schema_version=1)

        for status in ["implemented", "planned", "deprecated"]:
            cap = Capability(
                id=f"test:{status}",
                summary=f"Test {status}",
                mode="edit",
                api_methods=["API.test"],
                cli_command="test",
                example=CapabilityExample(description="Test", api_calls=[]),
                status=status,
            )
            registry.register(cap)

        deprecated = registry.list_deprecated()
        self.assertEqual(len(deprecated), 1)
        self.assertEqual(deprecated[0].id, "test:deprecated")

    def test_full_roundtrip_preserves_all_fields(self) -> None:
        """Full roundtrip must preserve ALL capability fields including status."""
        original = CapabilityRegistry(schema_version=2)
        cap = Capability(
            id="test:full",
            summary="Full test capability",
            mode="both",
            api_methods=["API.test", "API.other"],
            cli_command="motor test full",
            example=CapabilityExample(
                description="Full example",
                api_calls=[{"method": "test", "args": {"key": "value"}}],
                expected_outcome="Works",
            ),
            notes="Important notes",
            tags=["test", "full"],
            status="planned",
        )
        original.register(cap)

        # Serialize and deserialize
        data = original.to_dict()
        restored = CapabilityRegistry.from_dict(data)

        # Verify all fields
        restored_cap = restored.get("test:full")
        self.assertIsNotNone(restored_cap)
        self.assertEqual(restored_cap.id, cap.id)
        self.assertEqual(restored_cap.summary, cap.summary)
        self.assertEqual(restored_cap.mode, cap.mode)
        self.assertEqual(restored_cap.status, cap.status)
        self.assertEqual(restored_cap.api_methods, cap.api_methods)
        self.assertEqual(restored_cap.cli_command, cap.cli_command)
        self.assertEqual(restored_cap.notes, cap.notes)
        self.assertEqual(restored_cap.tags, cap.tags)
        self.assertEqual(restored_cap.example.description, cap.example.description)
        self.assertEqual(restored_cap.example.expected_outcome, cap.example.expected_outcome)


class DefaultRegistryContentTests(unittest.TestCase):
    """Tests for the default registry content."""

    def setUp(self) -> None:
        self.registry = get_default_registry()

    def test_registry_has_expected_categories(self) -> None:
        """Ensure all major categories are represented."""
        all_ids = {cap.id for cap in self.registry.list_all()}

        categories = {
            "scene:": ["scene:create", "scene:load", "scene:save"],
            "entity:": ["entity:create", "entity:delete"],
            "component:": ["component:add", "component:edit"],
            "asset:": ["asset:list", "asset:find"],
            "asset:slice:": ["asset:slice:grid", "asset:slice:list"],  # slice commands under asset
            "animator:": ["animator:set_sheet", "animator:info", "animator:state:create", "animator:state:remove"],
            "prefab:": ["prefab:create", "prefab:instantiate", "prefab:list"],
            "project:": ["project:open", "project:manifest"],
            "runtime:": ["runtime:play", "runtime:stop"],
            "physics:": ["physics:query:aabb", "physics:query:ray"],
            "introspect:": ["introspect:capabilities"],
        }

        for prefix, required_ids in categories.items():
            matching = {cap_id for cap_id in all_ids if cap_id.startswith(prefix)}
            self.assertTrue(
                matching,
                f"No capabilities found for category {prefix}",
            )
            for req_id in required_ids:
                self.assertIn(
                    req_id,
                    all_ids,
                    f"Required capability {req_id} not found in registry",
                )

    def test_all_capability_ids_are_unique(self) -> None:
        ids = [cap.id for cap in self.registry.list_all()]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate capability IDs found")

    def test_all_capabilities_have_examples(self) -> None:
        for cap in self.registry.list_all():
            self.assertIsInstance(
                cap.example,
                CapabilityExample,
                f"{cap.id} missing valid example",
            )
            self.assertTrue(
                cap.example.description,
                f"{cap.id} example missing description",
            )

    def test_all_capabilities_have_api_methods(self) -> None:
        for cap in self.registry.list_all():
            self.assertTrue(
                cap.api_methods,
                f"{cap.id} missing api_methods",
            )

    def test_all_capabilities_have_cli_commands(self) -> None:
        for cap in self.registry.list_all():
            self.assertTrue(
                cap.cli_command,
                f"{cap.id} missing cli_command",
            )

    def test_all_cli_commands_use_motor_prefix(self) -> None:
        """Blindaje: TODOS los cli_command deben empezar con 'motor '."""
        for cap in self.registry.list_all():
            self.assertTrue(
                cap.cli_command.startswith("motor "),
                f"{cap.id} CLI command must start with 'motor ': got '{cap.cli_command}'",
            )

    def test_no_cli_commands_use_legacy_tools_engine_cli(self) -> None:
        """Blindaje: NINGÚN cli_command debe usar tools.engine_cli."""
        legacy_patterns = [
            "python -m tools.engine_cli",
            "tools.engine_cli",
            "python -m tools",
        ]
        for cap in self.registry.list_all():
            for pattern in legacy_patterns:
                self.assertNotIn(
                    pattern, cap.cli_command,
                    f"{cap.id} uses deprecated CLI pattern '{pattern}': {cap.cli_command}"
                )

    def test_registry_passes_validation(self) -> None:
        errors = self.registry.validate()
        self.assertEqual(errors, [], f"Registry validation failed: {errors}")

    def test_registry_uses_engine_version(self) -> None:
        self.assertEqual(self.registry.engine_version, ENGINE_VERSION)


class MotorAIBootstrapBuilderTests(unittest.TestCase):
    """Tests for MotorAIBootstrapBuilder."""

    def setUp(self) -> None:
        self.registry = get_default_registry()
        self.builder = MotorAIBootstrapBuilder(self.registry)

    def test_build_motor_ai_json_is_valid_json(self) -> None:
        content = self.builder.build_motor_ai_json()
        data = json.loads(content)
        self.assertIn("schema_version", data)
        self.assertIn("engine", data)
        self.assertIn("implemented_capabilities", data)
        self.assertIn("planned_capabilities", data)
        self.assertIn("capability_counts", data)

    def test_motor_ai_json_has_correct_schema_version(self) -> None:
        content = self.builder.build_motor_ai_json()
        data = json.loads(content)
        self.assertEqual(data["schema_version"], 3)  # Updated for status field
        self.assertEqual(data["engine"]["capabilities_schema_version"], 1)

    def test_motor_ai_json_includes_project_data_when_provided(self) -> None:
        project_data = {
            "project": {"name": "TestProject", "root": "/test"},
            "entrypoints": {"manifest": "/test/project.json"},
        }
        content = self.builder.build_motor_ai_json(project_data)
        data = json.loads(content)
        self.assertEqual(data["project"]["name"], "TestProject")
        self.assertEqual(data["entrypoints"]["manifest"], "/test/project.json")

    def test_build_start_here_md_contains_project_name(self) -> None:
        content = self.builder.build_start_here_md("MyGame")
        self.assertIn("MyGame", content)
        self.assertIn("MotorVideojuegosIA", content)

    def test_start_here_md_lists_common_capabilities(self) -> None:
        content = self.builder.build_start_here_md("Test")
        self.assertIn("scene:load", content)
        self.assertIn("entity:create", content)
        self.assertIn("prefab:create", content)
        self.assertIn("prefab:instantiate", content)

    def test_start_here_md_has_naming_conventions(self) -> None:
        content = self.builder.build_start_here_md("Test")
        self.assertIn("Naming Conventions", content)
        self.assertIn("scope:action", content)

    def test_write_to_project_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_data = {"project": {"name": "TestProject"}}
            paths = self.builder.write_to_project(root, project_data)

            self.assertTrue(paths["motor_ai_json"].exists())
            self.assertTrue(paths["start_here_md"].exists())

            motor_ai_content = paths["motor_ai_json"].read_text()
            self.assertIn("TestProject", motor_ai_content)


class RegistryBuilderPatternTests(unittest.TestCase):
    """Tests for CapabilityRegistryBuilder pattern."""

    def test_builder_creates_populated_registry(self) -> None:
        from engine.ai.registry_builder import CapabilityRegistryBuilder
        builder = CapabilityRegistryBuilder(engine_version="2026.03")
        registry = builder.build()

        self.assertGreater(len(registry.list_all()), 0)
        self.assertEqual(registry.engine_version, "2026.03")

    def test_builder_has_all_expected_scopes(self) -> None:
        from engine.ai.registry_builder import CapabilityRegistryBuilder
        registry = CapabilityRegistryBuilder().build()

        scopes = set()
        for cap in registry.list_all():
            scope = cap.id.split(":")[0]
            scopes.add(scope)

        expected_scopes = {
            "scene", "entity", "component", "asset",  # slice is under asset
            "animator", "prefab", "project", "runtime", "physics", "introspect",
        }
        self.assertTrue(
            expected_scopes.issubset(scopes),
            f"Missing scopes: {expected_scopes - scopes}",
        )


if __name__ == "__main__":
    unittest.main()
