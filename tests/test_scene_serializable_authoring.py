import copy
import inspect
import unittest
from unittest.mock import patch

from engine.levels.component_registry import create_default_registry
from engine.scenes.contracts import SceneSerializableEntityPort
from engine.scenes.edit_sync import (
    TRANSIENT_PREVIEW_SYNC_REASON,
    SceneEditSyncCoordinator,
)
from engine.scenes.prefab_overrides import PrefabOverrideService
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_authoring import SceneSerializableAuthoring
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
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


class SceneSerializableAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()
        self.projection = SceneProjectionService(self.registry)
        self.workspace = SceneWorkspace(
            projection=self.projection,
            flow_policy=SceneFlowPolicy(),
        )
        self.edit_sync = SceneEditSyncCoordinator(self.workspace, self.projection)
        self.mutations = SerializableMutationCoordinator(
            self.workspace,
            self.projection,
            self.edit_sync,
        )
        self.history = _History()
        self.prefab_overrides = _PrefabOverrides()
        self.flow_policy = SceneFlowPolicy()
        self.authoring = SceneSerializableAuthoring(
            self.workspace,
            self.edit_sync,
            self.mutations,
            self.projection,
            self.history,
            self.prefab_overrides,
            self.flow_policy,
            self.registry,
        )
        self.workspace.load_scene(_payload())
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None

    def test_serializable_pipeline_orders_authorities(self) -> None:
        events: list[str] = []
        self.history.events = events
        flush = self.edit_sync.flush_pending
        capture = self.mutations.capture_snapshot
        mutate = self.entry.scene.update_component
        commit = self.mutations.commit_mutation
        mark_dirty = self.workspace.mark_dirty

        with (
            patch.object(
                self.edit_sync,
                "flush_pending",
                side_effect=lambda *args, **kwargs: (events.append("flush"), flush(*args, **kwargs))[1],
            ),
            patch.object(
                self.mutations,
                "capture_snapshot",
                side_effect=lambda *args, **kwargs: (events.append("capture"), capture(*args, **kwargs))[1],
            ),
            patch.object(
                self.entry.scene,
                "update_component",
                side_effect=lambda *args, **kwargs: (events.append("mutate"), mutate(*args, **kwargs))[1],
            ),
            patch.object(
                self.mutations,
                "commit_mutation",
                side_effect=lambda *args, **kwargs: (events.append("commit"), commit(*args, **kwargs))[1],
            ),
            patch.object(
                self.workspace,
                "mark_dirty",
                side_effect=lambda *args, **kwargs: (events.append("dirty"), mark_dirty(*args, **kwargs))[1],
            ),
        ):
            self.assertTrue(
                self.authoring.apply_edit_to_world(
                    "Hero",
                    "Transform",
                    "x",
                    9.0,
                )
            )

        self.assertEqual(
            events,
            ["flush", "capture", "mutate", "commit", "dirty", "history"],
        )

    def test_mutation_exception_restores_payload_and_records_no_history(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_dict())

        with patch.object(
            self.entry.scene,
            "update_component",
            side_effect=RuntimeError("mutation failed"),
        ):
            self.assertFalse(
                self.authoring.apply_edit_to_world(
                    "Hero",
                    "Transform",
                    "x",
                    4.0,
                )
            )

        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertFalse(self.entry.dirty)
        self.assertEqual(self.history.scene_changes, [])

    def test_play_rejects_mutation_before_capture(self) -> None:
        self.assertIsNotNone(self.workspace.enter_play())
        with patch.object(self.mutations, "capture_snapshot") as capture:
            self.assertFalse(
                self.authoring.apply_edit_to_world(
                    "Hero",
                    "Transform",
                    "x",
                    3.0,
                )
            )
        capture.assert_not_called()

    def test_active_and_inactive_component_removal_are_equivalent(self) -> None:
        self.workspace.load_scene(
            _payload("Inactive"),
            source_path="inactive.json",
            activate=False,
        )
        inactive = next(item for item in self.workspace.entries.values() if item.key != self.workspace.active_scene_key)

        self.assertTrue(
            self.authoring.remove_component_for_scene(
                inactive,
                "Hero",
                "Transform",
            )
        )
        self.assertNotIn(
            "Transform",
            inactive.scene.find_entity("Hero")["components"],
        )
        self.assertEqual(self.history.scene_changes, [])

        self.assertTrue(
            self.authoring.remove_component_for_scene(
                self.entry,
                "Hero",
                "Transform",
            )
        )
        self.assertNotIn(
            "Transform",
            self.entry.scene.find_entity("Hero")["components"],
        )
        self.assertEqual(len(self.history.scene_changes), 1)

    def test_four_prefab_fallbacks_use_only_the_port(self) -> None:
        self.assertTrue(
            self.authoring.apply_edit_to_world(
                "Expanded",
                "Sprite",
                "enabled",
                False,
            )
        )
        self.assertTrue(self.authoring.update_entity_property("Expanded", "tag", "Enemy"))
        self.assertTrue(
            self.authoring.replace_component_data(
                "Expanded",
                "Transform",
                _transform(2.0),
            )
        )
        self.assertTrue(
            self.authoring.remove_component_from_entity(
                "Expanded",
                "Sprite",
            )
        )

        self.assertEqual(
            self.prefab_overrides.calls,
            [
                "update_component_property",
                "update_entity_property",
                "replace_component",
                "remove_component",
            ],
        )

    def test_scene_link_uses_flow_policy_and_keeps_metadata_in_sync(self) -> None:
        self.assertTrue(
            self.authoring.set_feature_metadata(
                "scene_flow",
                {"exit": "levels/next.json"},
            )
        )
        self.assertTrue(
            self.authoring.add_component_to_entity(
                "Hero",
                "SceneLink",
                {"flow_key": "exit", "preview_label": "Exit"},
            )
        )

        link = self.authoring.get_component_data("Hero", "SceneLink")
        self.assertEqual(link["target_path"], "levels/next.json")
        self.assertEqual(
            self.authoring.get_feature_metadata()["scene_flow"],
            {"exit": "levels/next.json"},
        )

    def test_metadata_and_queries_return_defensive_copies(self) -> None:
        metadata = {"nested": {"values": [1]}}
        self.assertTrue(
            self.authoring.set_component_metadata(
                "Hero",
                "Transform",
                metadata,
            )
        )
        metadata["nested"]["values"].append(2)
        exposed_metadata = self.authoring.get_component_metadata(
            "Hero",
            "Transform",
        )
        exposed_entity = self.authoring.find_entity_data("Hero")
        exposed_by_id = self.authoring.find_entity_data_by_id("hero-id")
        exposed_metadata["nested"]["values"].append(3)
        exposed_entity["components"]["Transform"]["x"] = 99.0
        exposed_by_id["tag"] = "Poisoned"

        stored = self.entry.scene.find_entity("Hero")
        self.assertEqual(
            stored["component_metadata"]["Transform"],
            {"nested": {"values": [1]}},
        )
        self.assertEqual(stored["components"]["Transform"]["x"], 1.0)
        self.assertEqual(stored["tag"], "Untagged")

    def test_by_id_mutations_target_the_same_entity(self) -> None:
        self.assertTrue(
            self.authoring.update_entity_property_by_id(
                "hero-id",
                "tag",
                "Player",
            )
        )
        self.assertTrue(
            self.authoring.replace_component_data_by_id(
                "hero-id",
                "Transform",
                _transform(7.0),
            )
        )
        self.assertTrue(
            self.authoring.add_component_to_entity_by_id(
                "hero-id",
                "SceneLink",
                {"flow_key": "exit", "target_path": "next.json"},
            )
        )
        self.assertTrue(
            self.authoring.remove_component_from_entity_by_id(
                "hero-id",
                "SceneLink",
            )
        )

        stored = self.entry.scene.find_entity_by_id("hero-id")
        self.assertEqual(stored["tag"], "Player")
        self.assertEqual(stored["components"]["Transform"]["x"], 7.0)
        self.assertNotIn("SceneLink", stored["components"])

    def test_creation_captures_before_flow_and_preserves_scene_world_identity(self) -> None:
        scene = self.entry.scene
        world = self.entry.edit_world
        events: list[str] = []
        capture = self.mutations.capture_snapshot
        prepare = self.flow_policy.prepare_entity
        self.entry.pending_edit_world_sync_reason = TRANSIENT_PREVIEW_SYNC_REASON

        with (
            patch.object(
                self.mutations,
                "capture_snapshot",
                side_effect=lambda *args, **kwargs: (events.append("capture"), capture(*args, **kwargs))[1],
            ),
            patch.object(
                self.flow_policy,
                "prepare_entity",
                side_effect=lambda *args, **kwargs: (events.append("prepare"), prepare(*args, **kwargs))[1],
            ),
        ):
            self.assertTrue(self.authoring.create_entity("Added"))

        self.assertEqual(events, ["capture", "prepare"])
        self.assertIs(self.entry.scene, scene)
        self.assertIs(self.entry.edit_world, world)
        self.assertIsNotNone(world.get_entity_by_name("Added"))
        self.assertEqual(self.entry.edit_world_version, world.version)
        self.assertIsNone(self.entry.pending_edit_world_sync_reason)
        self.assertTrue(self.entry.dirty)
        self.assertEqual(len(self.history.differential_changes), 1)

    def test_creation_exception_rolls_back_and_records_no_history(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_dict())
        original_add = self.projection.add_entity

        def add_then_fail(scene, world, payload):
            self.assertIsNotNone(original_add(scene, world, payload))
            raise RuntimeError("after materialization")

        with patch.object(
            self.projection,
            "add_entity",
            side_effect=add_then_fail,
        ):
            self.assertFalse(self.authoring.create_entity("Partial"))

        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertIsNone(self.entry.edit_world.get_entity_by_name("Partial"))
        self.assertFalse(self.entry.dirty)
        self.assertEqual(self.history.differential_changes, [])

    def test_creation_validation_failure_restores_through_coordinator(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_dict())
        validate = self.projection.validate_payload
        calls = 0

        def fail_first_validation(payload):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("invalid incremental payload")
            return validate(payload)

        with patch.object(
            self.projection,
            "validate_payload",
            side_effect=fail_first_validation,
        ):
            self.assertFalse(self.authoring.create_entity("Rejected"))

        self.assertEqual(calls, 2)
        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertIsNone(self.entry.edit_world.get_entity_by_name("Rejected"))
        self.assertFalse(self.entry.dirty)
        self.assertEqual(self.history.differential_changes, [])


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
