import copy
import inspect
import unittest
from unittest.mock import patch

from engine.levels.component_registry import create_default_registry
from engine.scenes.component_authoring import SceneComponentAuthoring
from engine.scenes.contracts import SceneSerializableEntityPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
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

    def record_scene_change(self, entry, label, before) -> None:
        if self.events is not None:
            self.events.append("history")
        self.scene_changes.append((entry, label, copy.deepcopy(before)))

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


if __name__ == "__main__":
    unittest.main()
