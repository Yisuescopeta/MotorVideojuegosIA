import inspect
import unittest
from dataclasses import fields
from unittest.mock import patch

from engine.levels.component_registry import create_default_registry
from engine.scenes.contracts import SceneSerializableEntityPort
from engine.scenes.scene_manager import SceneManager
from engine.scenes.structural_authoring import (
    SceneStructuralAuthoring,
    SceneStructuralAuthoringContext,
)


def _entity(name: str, *, transform: bool = True) -> dict[str, object]:
    components: dict[str, object] = {}
    if transform:
        components["Transform"] = {
            "enabled": True,
            "x": 0.0,
            "y": 0.0,
            "rotation": 0.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
    return {
        "name": name,
        "active": True,
        "tag": "Untagged",
        "layer": "Default",
        "components": components,
    }


def _manager(*entities: dict[str, object]) -> SceneManager:
    manager = SceneManager(create_default_registry())
    manager.load_scene(
        {
            "name": "Structural Port",
            "entities": list(entities),
            "rules": [],
            "feature_metadata": {},
        }
    )
    return manager


class SceneStructuralAuthoringArchitectureTests(unittest.TestCase):
    def test_context_has_no_serializable_crud_callbacks(self) -> None:
        field_names = {field.name for field in fields(SceneStructuralAuthoringContext)}

        self.assertEqual(
            field_names,
            {
                "get_active_entry",
                "resolve_entry",
                "flush_pending_edit_world",
                "rebuild_edit_world",
                "record_scene_change",
                "sync_scene_links_from_feature_metadata",
                "unique_entity_name",
            },
        )
        self.assertTrue(
            {
                "create_entity",
                "create_entity_from_data",
                "update_entity_property",
            }.isdisjoint(field_names)
        )

    def test_structural_dependencies_use_narrow_entity_port_without_cycles(self) -> None:
        port_methods = {
            name
            for name, value in vars(SceneSerializableEntityPort).items()
            if callable(value) and not name.startswith("_")
        }
        source = inspect.getsource(inspect.getmodule(SceneStructuralAuthoring))

        self.assertEqual(
            port_methods,
            {"create_entity", "create_entity_from_data", "update_entity_property"},
        )
        self.assertIn("SceneSerializableEntityPort", source)
        self.assertNotIn("SceneEntityAuthoring", source)
        self.assertNotIn("SceneSerializableAuthoring", source)
        self.assertNotIn("SceneManager", source)
        self.assertNotIn("context.create_entity", source)
        self.assertNotIn("context.create_entity_from_data", source)
        self.assertNotIn("context.update_entity_property", source)

    def test_manager_injects_same_entity_owner_into_all_structural_services(self) -> None:
        manager = _manager(_entity("Parent"))
        owner = manager._serializable_authoring.entity_authoring
        structural = manager._structural_authoring

        self.assertIs(structural._serializable_entities, owner)
        self.assertIs(structural._hierarchy.serializable_entities, owner)
        self.assertIs(structural._prefabs.serializable_entities, owner)


class SceneStructuralEntityPortRoutingTests(unittest.TestCase):
    def test_create_child_uses_entity_port_create_then_parent_update(self) -> None:
        manager = _manager(_entity("Parent"))
        port = manager._serializable_authoring.entity_authoring

        with (
            patch.object(
                port,
                "create_entity",
                wraps=port.create_entity,
            ) as create,
            patch.object(
                port,
                "update_entity_property",
                wraps=port.update_entity_property,
            ) as update,
        ):
            self.assertTrue(manager.create_child_entity("Parent", "Child"))

        create.assert_called_once_with("Child", None)
        update.assert_called_once_with("Child", "parent", "Parent")

    def test_create_child_prevalidates_missing_parent_before_port_update(self) -> None:
        manager = _manager()
        port = manager._serializable_authoring.entity_authoring

        with patch.object(
            port,
            "update_entity_property",
            wraps=port.update_entity_property,
        ) as update:
            self.assertFalse(manager.create_child_entity("Missing", "Orphan"))

        update.assert_not_called()
        orphan = manager.find_entity_data("Orphan")
        self.assertIsNotNone(orphan)
        self.assertIsNone(orphan["parent"])

    def test_parent_fallback_uses_entity_port_after_prevalidation(self) -> None:
        manager = _manager(_entity("Parent"), _entity("Child", transform=False))
        port = manager._serializable_authoring.entity_authoring

        with patch.object(
            port,
            "update_entity_property",
            wraps=port.update_entity_property,
        ) as update:
            self.assertTrue(manager.set_entity_parent("Child", "Parent"))

        update.assert_called_once_with("Child", "parent", "Parent")
        self.assertEqual(manager.find_entity_data("Child")["parent"], "Parent")

    def test_instantiate_prefab_uses_entity_port_payload(self) -> None:
        manager = _manager(_entity("Parent"))
        port = manager._serializable_authoring.entity_authoring

        with patch.object(
            port,
            "create_entity_from_data",
            wraps=port.create_entity_from_data,
        ) as create_from_data:
            self.assertTrue(
                manager.instantiate_prefab(
                    "Enemy",
                    "prefabs/enemy.prefab",
                    parent="Parent",
                    overrides={"tag": "Elite"},
                    root_name="EnemyRoot",
                )
            )

        create_from_data.assert_called_once()
        payload = create_from_data.call_args.args[0]
        self.assertEqual(payload["name"], "Enemy")
        self.assertEqual(payload["parent"], "Parent")
        self.assertEqual(
            payload["prefab_instance"],
            {
                "prefab_path": "prefabs/enemy.prefab",
                "root_name": "EnemyRoot",
                "overrides": {"tag": "Elite"},
            },
        )


if __name__ == "__main__":
    unittest.main()
