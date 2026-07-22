import inspect
import unittest
from unittest.mock import patch

import engine.scenes.structural_authoring as structural_module
from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.contracts import SceneSerializableEntityPort
from engine.scenes.scene_manager import SceneManager
from engine.scenes.structural_authoring import SceneStructuralAuthoring


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
    def test_context_is_removed_and_constructor_has_exact_four_ports(self) -> None:
        self.assertFalse(hasattr(structural_module, "SceneStructuralAuthoringContext"))
        self.assertEqual(
            list(inspect.signature(SceneStructuralAuthoring).parameters),
            [
                "workspace",
                "pipeline",
                "serializable_entities",
                "prefab_overrides",
            ],
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
        self.assertNotIn("entry.dirty", source)
        self.assertNotIn("scene.data", source)
        self.assertNotIn("_rebuild_entity_index", source)

    def test_manager_injects_exact_shared_owners_into_structural_services(self) -> None:
        manager = _manager(_entity("Parent"))
        owner = manager._serializable_authoring.entity_authoring
        pipeline = manager._serializable_authoring.transaction_pipeline
        structural = manager._structural_authoring

        self.assertIs(structural._serializable_entities, owner)
        self.assertIs(structural._hierarchy.serializable_entities, owner)
        self.assertIs(structural._prefabs.serializable_entities, owner)
        self.assertIs(structural._hierarchy.workspace, manager._workspace)
        self.assertIs(structural._prefabs.workspace, manager._workspace)
        self.assertIs(structural._hierarchy.pipeline, pipeline)
        self.assertIs(structural._prefabs.pipeline, pipeline)
        self.assertIs(structural._prefab_overrides, manager._prefab_overrides)


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

    def test_parent_without_transform_uses_shared_pipeline_and_scene_primitive(self) -> None:
        manager = _manager(_entity("Parent"), _entity("Child", transform=False))
        port = manager._serializable_authoring.entity_authoring
        pipeline = manager._serializable_authoring.transaction_pipeline
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None

        with (
            patch.object(port, "update_entity_property", wraps=port.update_entity_property) as update,
            patch.object(pipeline, "begin", wraps=pipeline.begin) as begin,
            patch.object(
                entry.scene,
                "reparent_entity_by_id",
                wraps=entry.scene.reparent_entity_by_id,
            ) as primitive,
        ):
            self.assertTrue(manager.set_entity_parent("Child", "Parent"))

        update.assert_not_called()
        begin.assert_called_once_with(entry, failure_context="reparent:Child")
        primitive.assert_called_once_with(
            entry.scene.find_entity("Child")["id"],
            entry.scene.find_entity("Parent")["id"],
        )
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


class SceneStructuralPendingFlushTests(unittest.TestCase):
    def test_duplicate_blocks_pending_legacy_without_import(self) -> None:
        manager = _manager(_entity("Rig"))
        world = manager.get_edit_world()
        world.get_entity_by_name("Rig").get_component(Transform).local_x = 25.0
        self.assertTrue(manager.mark_edit_world_dirty())

        self.assertFalse(manager.duplicate_entity_subtree("Rig", "RigCopy"))

        scene = manager._workspace.get_active_entry().scene
        self.assertIsNone(scene.find_entity("RigCopy"))
        self.assertEqual(scene.find_entity("Rig")["components"]["Transform"]["x"], 0.0)
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None
        self.assertTrue(entry.edit_world_sync_pending)

    def test_paste_blocks_pending_legacy_without_import(self) -> None:
        manager = _manager(_entity("Seed"))
        self.assertTrue(manager.copy_entity_subtree("Seed"))
        manager.get_edit_world().get_entity_by_name("Seed").name = "Renamed"
        self.assertTrue(manager.mark_edit_world_dirty())

        self.assertFalse(manager.paste_copied_entities())

        scene = manager._workspace.get_active_entry().scene
        self.assertIsNotNone(scene.find_entity("Seed"))
        self.assertIsNone(scene.find_entity("Seed_copy"))
        self.assertIsNone(scene.find_entity("Renamed"))

    def test_create_prefab_replace_blocks_pending_legacy_without_import(self) -> None:
        root = _entity("Root")
        root["parent"] = "ParentA"
        manager = _manager(_entity("ParentA"), _entity("ParentB"), root)
        manager.get_edit_world().get_entity_by_name("Root").parent_name = "ParentB"
        self.assertTrue(manager.mark_edit_world_dirty())

        with patch("engine.assets.prefab.PrefabManager.save_prefab", return_value=True):
            self.assertFalse(
                manager.create_prefab(
                    "Root",
                    "prefabs/root.prefab",
                    replace_original=True,
                )
            )

        scene = manager._workspace.get_active_entry().scene
        self.assertEqual(scene.find_entity("Root")["parent"], "ParentA")


if __name__ == "__main__":
    unittest.main()
