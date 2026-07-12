import json
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import engine.ecs.world as world_module
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.transform import Transform
from engine.ecs.component import (
    Component,
    LegacyComponentSerializationWarning,
    has_explicit_serialization_contract,
)
from engine.ecs.world import World, WorldSerializationError
from engine.ecs.world_serialization import (
    WorldSerializationError as SerializationAuthorityError,
)
from engine.ecs.world_serialization import (
    serialize_world,
)
from engine.levels.component_registry import create_default_registry


class LegacyDataComponent(Component):
    def __init__(self) -> None:
        self.enabled = True
        self.label = "legacy"
        self.settings = {"points": [[1, 2], [3, 4]]}
        self.callback = lambda: None
        self._runtime_cache = {"ignored": True}

    def __dir__(self) -> list[str]:
        raise AssertionError("legacy serialization must not call dir()")


class IncompleteLegacyComponent(Component):
    def to_dict(self) -> dict[str, object]:
        return {"enabled": True, "value": 7}


class MissingOfficialContract(Component):
    __module__ = "engine.components.missing_contract"

    def __init__(self) -> None:
        self.enabled = True


class ComponentSerializationContractTests(unittest.TestCase):
    def _assert_incomplete_contract_warning(self, caught_warnings) -> None:
        self.assertEqual(len(caught_warnings), 1)
        warning = caught_warnings[0]
        self.assertIs(warning.category, LegacyComponentSerializationWarning)
        self.assertEqual(Path(warning.filename).resolve(), Path(world_module.__file__).resolve())
        self.assertEqual(
            str(warning.message),
            (
                f"{IncompleteLegacyComponent.__module__}.IncompleteLegacyComponent tiene un contrato "
                "de serializacion legacy incompleto; implemente from_dict() explicito"
            ),
        )

    def test_world_serialize_delegates_to_module_authority(self) -> None:
        world = World()

        with patch("engine.ecs.world_serialization.serialize_world", wraps=serialize_world) as serializer:
            payload = world.serialize()

        serializer.assert_called_once_with(world)
        self.assertEqual(payload, {"entities": [], "rules": [], "feature_metadata": {}})
        self.assertIs(WorldSerializationError, SerializationAuthorityError)

    def test_all_registered_components_have_explicit_roundtrip_contracts(self) -> None:
        registry = create_default_registry()

        for descriptor in registry.list_descriptors():
            component_type = descriptor.component_class
            with self.subTest(component=descriptor.name):
                self.assertTrue(
                    has_explicit_serialization_contract(component_type),
                    f"{descriptor.name} must implement explicit to_dict/from_dict",
                )
                component = component_type.from_dict(descriptor.default_payload)
                payload = component.to_dict()
                encoded = json.dumps(payload)
                restored = component_type.from_dict(json.loads(encoded))
                self.assertEqual(restored.to_dict(), payload)

    def test_official_serialization_does_not_use_component_fallback(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.add_component(Transform(x=12.0, y=34.0))

        with patch.object(Component, "to_dict", side_effect=AssertionError("legacy fallback used")):
            payload = world.serialize()

        self.assertEqual(payload["entities"][0]["components"]["Transform"]["x"], 12.0)

    def test_legacy_component_warns_and_preserves_public_data(self) -> None:
        world = World()
        entity = world.create_entity("Legacy")
        entity.add_component(LegacyDataComponent())

        with self.assertWarns(LegacyComponentSerializationWarning):
            payload = world.serialize()

        component_payload = payload["entities"][0]["components"]["LegacyDataComponent"]
        self.assertEqual(
            component_payload,
            {
                "enabled": True,
                "label": "legacy",
                "settings": {"points": [[1, 2], [3, 4]]},
            },
        )

    def test_incomplete_external_contract_warns_but_keeps_to_dict_payload(self) -> None:
        world = World()
        entity = world.create_entity("Legacy")
        entity.add_component(IncompleteLegacyComponent())

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            payload = world.serialize()

        self._assert_incomplete_contract_warning(caught_warnings)
        self.assertEqual(
            payload["entities"][0]["components"]["IncompleteLegacyComponent"],
            {"enabled": True, "value": 7},
        )

    def test_incomplete_prefab_contract_warning_is_attributed_to_world_wrapper(self) -> None:
        world = World()
        entity = world.create_entity("LegacyPrefab")
        entity.prefab_instance = {
            "prefab_path": "prefabs/legacy.prefab",
            "root_name": "LegacyPrefab",
        }
        entity.add_component(IncompleteLegacyComponent())

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            payload = world.serialize()

        self._assert_incomplete_contract_warning(caught_warnings)
        component_payload = payload["entities"][0]["prefab_instance"]["overrides"][""][
            "components"
        ]["IncompleteLegacyComponent"]
        self.assertEqual(component_payload, {"enabled": True, "value": 7})

    def test_world_serialization_returns_defensive_nested_payloads(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default"]}}
        entity = world.create_entity("Hero")
        entity.prefab_instance = {
            "prefab_path": "prefabs/hero.prefab",
            "overrides": {"components": {"Transform": {"x": 1.0}}},
        }
        entity.prefab_source_path = "Hero"
        entity.add_component(
            Transform(),
            metadata={"details": {"editable_fields": ["x"]}},
        )
        entity.add_component(
            ScriptBehaviour(public_data={"inventory": [{"id": "key"}]}),
        )

        payload = world.serialize()
        serialized_entity = payload["entities"][0]
        payload["feature_metadata"]["render_2d"]["sorting_layers"].append("UI")
        serialized_entity["prefab_instance"]["overrides"]["components"]["Transform"]["x"] = 9.0
        serialized_entity["component_metadata"]["Transform"]["details"]["editable_fields"].append("y")
        serialized_entity["components"]["ScriptBehaviour"]["public_data"]["inventory"][0]["id"] = "coin"

        self.assertEqual(world.feature_metadata["render_2d"]["sorting_layers"], ["Default"])
        self.assertEqual(
            entity.prefab_instance["overrides"]["components"]["Transform"]["x"],
            1.0,
        )
        self.assertEqual(
            entity.get_component_metadata(Transform)["details"]["editable_fields"],
            ["x"],
        )
        self.assertEqual(
            entity.get_component(ScriptBehaviour).public_data["inventory"][0]["id"],
            "key",
        )

    def test_official_component_without_explicit_contract_fails(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.add_component(MissingOfficialContract())

        with self.assertRaisesRegex(
            WorldSerializationError,
            r"Hero\.MissingOfficialContract.*to_dict\(\)/from_dict\(\)",
        ):
            world.serialize()

    def test_transform_runtime_hierarchy_is_not_serialized(self) -> None:
        parent = Transform(x=10.0, y=20.0)
        child = Transform(x=3.0, y=4.0)
        child.parent = parent

        payload = child.to_dict()

        self.assertNotIn("parent", payload)
        self.assertNotIn("children", payload)
        self.assertNotIn("_parent", payload)
        self.assertEqual(payload["x"], 3.0)
        self.assertEqual(payload["y"], 4.0)


if __name__ == "__main__":
    unittest.main()
