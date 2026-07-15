import copy
import inspect
import unittest
from unittest.mock import patch

from engine.components.transform import Transform
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.component_authoring import SceneComponentAuthoring
from engine.scenes.contracts import SceneSerializableEntityPort
from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON, SceneEditSyncCoordinator
from engine.scenes.entity_authoring import SceneEntityAuthoring
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_authoring import SceneSerializableAuthoring
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.serializable_pipeline import SceneSerializableAuthoringPipeline
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _transform(x: float = 0.0) -> dict[str, object]:
    return {
        "enabled": True,
        "x": x,
        "y": 0.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _payload(name: str = "Serializable") -> dict[str, object]:
    return {
        "schema_version": 2,
        "name": name,
        "entities": [
            {
                "id": "hero-id",
                "name": "Hero",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {"Transform": _transform(1.0)},
                "component_metadata": {"Transform": {"origin": "native"}},
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


class _History:
    def __init__(self) -> None:
        self.scene_changes: list[tuple] = []
        self.differential_changes: list[dict] = []
        self.events: list[str] | None = None

    def record_snapshot_change(self, *, label, undo, redo) -> None:
        if self.events is not None:
            self.events.append("history")
        self.scene_changes.append((label, undo, redo))

    def record_differential_change(self, *, label, undo, redo) -> None:
        if self.events is not None:
            self.events.append("history")
        self.differential_changes.append({"label": label, "undo": undo, "redo": redo})


class _PrefabOverrides(PrefabOverrideService):
    def __init__(self) -> None:
        self.calls: list[str] = []

    @staticmethod
    def _publish(entry, operation: str) -> bool:
        entry.scene.set_feature_metadata("prefab_probe", operation)
        return True

    def update_component_property(self, entry, *args) -> bool:
        self.calls.append("update_component_property")
        return self._publish(entry, self.calls[-1])

    def update_entity_property(self, entry, *args) -> bool:
        self.calls.append("update_entity_property")
        return self._publish(entry, self.calls[-1])

    def replace_component(self, entry, *args) -> bool:
        self.calls.append("replace_component")
        return self._publish(entry, self.calls[-1])

    def remove_component(self, entry, *args) -> bool:
        self.calls.append("remove_component")
        return self._publish(entry, self.calls[-1])


class _SerializableOwnerTestSupport(unittest.TestCase):
    """Shared dependencies only; concrete fixtures install exactly one owner."""

    def setUp(self) -> None:
        self.registry = create_default_registry()
        self.projection = SceneProjectionService(self.registry)
        self.flow_policy = SceneFlowPolicy()
        self.workspace = SceneWorkspace(
            projection=self.projection,
            flow_policy=self.flow_policy,
        )
        self.edit_sync = SceneEditSyncCoordinator(self.workspace, self.projection)
        self.mutations = SerializableMutationCoordinator(
            self.workspace,
            self.projection,
            self.edit_sync,
        )
        self.history = _History()
        self.prefab_overrides = _PrefabOverrides()
        self.pipeline = SceneSerializableAuthoringPipeline(
            self.workspace,
            self.edit_sync,
            self.mutations,
            self.history,
        )
        self.workspace.load_scene(_payload())
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None


class SceneSerializableAuthoringArchitectureTests(unittest.TestCase):
    def test_entity_port_is_narrow_and_service_is_independent(self) -> None:
        methods = {
            name
            for name, value in vars(SceneSerializableEntityPort).items()
            if callable(value) and not name.startswith("_")
        }
        source = inspect.getsource(SceneSerializableAuthoring)

        self.assertEqual(
            methods,
            {"create_entity", "create_entity_from_data", "update_entity_property"},
        )
        for forbidden in (
            "SceneManager",
            "SceneStructuralAuthoring",
            "SceneIncrementalAuthoring",
        ):
            self.assertNotIn(forbidden, source)

    def test_facade_composes_exact_owners_with_shared_authorities(self) -> None:
        support = _SerializableOwnerTestSupport()
        support.setUp()
        authoring = SceneSerializableAuthoring(
            support.workspace,
            support.edit_sync,
            support.mutations,
            support.projection,
            support.history,
            support.prefab_overrides,
            support.flow_policy,
            support.registry,
        )

        self.assertIsInstance(authoring.component_authoring, SceneComponentAuthoring)
        self.assertIsInstance(authoring.entity_authoring, SceneEntityAuthoring)
        self.assertIs(authoring.component_authoring._pipeline, authoring.transaction_pipeline)
        self.assertIs(authoring.entity_authoring._pipeline, authoring.transaction_pipeline)
        self.assertIs(
            authoring.component_authoring._prefab_overrides,
            support.prefab_overrides,
        )
        self.assertIs(
            authoring.entity_authoring._prefab_overrides,
            support.prefab_overrides,
        )
        self.assertIs(authoring.component_authoring._flow_policy, support.flow_policy)
        self.assertIs(authoring.entity_authoring._flow_policy, support.flow_policy)


class SceneSerializableParentRoutingTests(unittest.TestCase):
    def test_manager_prevalidates_parent_by_name_and_id(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(_payload())

        with (
            patch.object(
                manager._structural_authoring,
                "validate_parent",
                return_value=False,
            ) as validate,
            patch.object(
                manager._serializable_authoring,
                "update_entity_property",
                wraps=manager._serializable_authoring.update_entity_property,
            ) as update_by_name,
            patch.object(
                manager._serializable_authoring,
                "update_entity_property_by_id",
                wraps=manager._serializable_authoring.update_entity_property_by_id,
            ) as update_by_id,
        ):
            self.assertFalse(manager.update_entity_property("Hero", "parent", "Missing"))
            self.assertFalse(
                manager.update_entity_property_by_id(
                    "hero-id",
                    "parent",
                    "Missing",
                )
            )

        self.assertEqual(validate.call_count, 2)
        update_by_name.assert_not_called()
        update_by_id.assert_not_called()


class SceneSerializableInactivePendingIntegrationTests(unittest.TestCase):
    def test_public_inactive_queries_and_upsert_preserve_pending_then_reactivate_cleanly(
        self,
    ) -> None:
        manager = SceneManager(create_default_registry())
        history = UndoRedoManager()
        manager.set_history_manager(history)
        manager.load_scene(_payload("Pending"))
        pending_key = manager.active_scene_key
        pending_entry = manager.resolve_entry(pending_key)
        assert pending_entry is not None and pending_entry.edit_world is not None
        self.assertTrue(manager.set_selected_entity("Hero"))
        pending_scene = pending_entry.scene
        pending_world = pending_entry.edit_world
        hero = pending_world.get_entity_by_name("Hero")
        assert hero is not None
        transform = hero.get_component(Transform)
        assert transform is not None
        transform.x = 42.0
        self.assertTrue(manager.mark_edit_world_dirty(LEGACY_AUTHORING_SYNC_REASON))
        scene_payload = copy.deepcopy(pending_scene.to_dict())
        world_payload = copy.deepcopy(pending_world.serialize())
        scene_entity_id = pending_scene.find_entity("Hero")["id"]
        world_entity_id = hero.serialized_id
        dirty_before = pending_entry.dirty
        dirty_baseline = pending_entry.dirty_before_pending_edit_world_sync
        pending_reason = pending_entry.pending_edit_world_sync_reason
        selection = (
            pending_entry.selected_entity_name,
            pending_entry.selected_entity_id,
            pending_world.selected_entity_name,
        )
        versions = (pending_entry.edit_world_version, pending_world.version)

        manager.load_scene(_payload("Active"), activate=True)
        active_key = manager.active_scene_key

        self.assertIsNone(
            manager.get_component_data_for_scene(pending_key, "Hero", "Transform")
        )
        self.assertIsNone(manager.find_entity_data_for_scene(pending_key, "Hero"))
        self.assertEqual(manager.list_scene_entities(pending_key), [])
        self.assertFalse(
            manager.upsert_component_for_scene(
                pending_key,
                "Hero",
                "Sprite",
                {"width": 16, "height": 8},
            )
        )

        self.assertEqual(manager.active_scene_key, active_key)
        self.assertIs(manager.resolve_entry(pending_key), pending_entry)
        self.assertIs(pending_entry.scene, pending_scene)
        self.assertIs(pending_entry.edit_world, pending_world)
        self.assertEqual(pending_entry.scene.to_dict(), scene_payload)
        self.assertEqual(pending_entry.edit_world.serialize(), world_payload)
        self.assertEqual(pending_entry.scene.find_entity("Hero")["id"], scene_entity_id)
        self.assertEqual(
            pending_entry.edit_world.get_entity_by_name("Hero").serialized_id,
            world_entity_id,
        )
        self.assertEqual(pending_entry.dirty, dirty_before)
        self.assertEqual(
            pending_entry.dirty_before_pending_edit_world_sync,
            dirty_baseline,
        )
        self.assertEqual(pending_entry.pending_edit_world_sync_reason, pending_reason)
        self.assertEqual(
            (
                pending_entry.selected_entity_name,
                pending_entry.selected_entity_id,
                pending_entry.edit_world.selected_entity_name,
            ),
            selection,
        )
        self.assertEqual(
            (pending_entry.edit_world_version, pending_entry.edit_world.version),
            versions,
        )
        self.assertFalse(history.can_undo())
        self.assertFalse(history.can_redo())

        self.assertIsNotNone(manager.activate_scene(pending_key))
        self.assertTrue(
            manager.upsert_component_for_scene(
                pending_key,
                "Hero",
                "Sprite",
                {"width": 16, "height": 8},
            )
        )
        self._assert_x_and_sprite(
            manager,
            has_sprite=True,
            entity_id=scene_entity_id,
        )
        self.assertTrue(history.can_undo())
        self.assertTrue(history.undo())
        self._assert_x_and_sprite(
            manager,
            has_sprite=False,
            entity_id=scene_entity_id,
        )
        self.assertFalse(history.can_undo())
        self.assertTrue(history.can_redo())
        self.assertTrue(history.redo())
        self._assert_x_and_sprite(
            manager,
            has_sprite=True,
            entity_id=scene_entity_id,
        )
        self.assertFalse(history.can_redo())

    def _assert_x_and_sprite(
        self,
        manager: SceneManager,
        *,
        has_sprite: bool,
        entity_id: str,
    ) -> None:
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None and entry.edit_world is not None
        entity_data = entry.scene.find_entity("Hero")
        self.assertEqual(entity_data["id"], entity_id)
        self.assertEqual(entity_data["components"]["Transform"]["x"], 42.0)
        self.assertEqual("Sprite" in entity_data["components"], has_sprite)
        self.assertEqual(entry.selected_entity_name, "Hero")
        self.assertEqual(entry.selected_entity_id, entity_id)
        hero = entry.edit_world.get_entity_by_name("Hero")
        assert hero is not None
        self.assertEqual(hero.serialized_id, entity_id)
        self.assertEqual(entry.edit_world.selected_entity_name, "Hero")
        transform = hero.get_component(Transform)
        assert transform is not None
        self.assertEqual(transform.x, 42.0)


if __name__ == "__main__":
    unittest.main()
