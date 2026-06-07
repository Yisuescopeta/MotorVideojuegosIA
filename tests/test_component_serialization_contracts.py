import json
import unittest
from unittest.mock import patch

from engine.components.transform import Transform
from engine.ecs.component import (
    Component,
    LegacyComponentSerializationWarning,
    has_explicit_serialization_contract,
)
from engine.ecs.world import World, WorldSerializationError
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

        with self.assertWarns(LegacyComponentSerializationWarning):
            payload = world.serialize()

        self.assertEqual(
            payload["entities"][0]["components"]["IncompleteLegacyComponent"],
            {"enabled": True, "value": 7},
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
