import copy
import inspect
import unittest
from unittest.mock import patch

import engine.scenes.component_authoring as component_module
from engine.components.transform import Transform
from engine.scenes.component_authoring import SceneComponentAuthoring
from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON
from tests.test_scene_serializable_authoring import (
    _payload,
    _SerializableOwnerTestSupport,
    _transform,
)

COMPONENT_METHODS = {
    "get_feature_metadata",
    "get_component_data",
    "get_component_data_for_entry",
    "get_component_metadata",
    "upsert_component_for_scene",
    "remove_component_for_scene",
    "apply_edit_to_world",
    "replace_component_data",
    "replace_component_data_by_id",
    "add_component_to_entity",
    "add_component_to_entity_by_id",
    "remove_component_from_entity",
    "remove_component_from_entity_by_id",
    "set_component_enabled",
    "set_component_metadata",
    "set_feature_metadata",
    "set_scene_flow_target",
    "apply_authoring_component_state",
}


class SceneComponentAuthoringArchitectureTests(unittest.TestCase):
    def test_component_behavior_fixture_constructs_only_component_owner(self) -> None:
        fixture_source = inspect.getsource(SceneComponentAuthoringTests.setUp)
        support_source = inspect.getsource(_SerializableOwnerTestSupport.setUp)
        fixture = SceneComponentAuthoringTests(
            "test_play_rejects_mutation_before_capture"
        )
        fixture.setUp()

        self.assertIn("SceneComponentAuthoring(", fixture_source)
        self.assertNotIn("SceneSerializableAuthoring(", fixture_source)
        self.assertNotIn("SceneEntityAuthoring(", fixture_source)
        self.assertNotIn("SceneSerializableAuthoring(", support_source)
        self.assertNotIn("SceneComponentAuthoring(", support_source)
        self.assertNotIn("SceneEntityAuthoring(", support_source)
        self.assertIsInstance(fixture.authoring, SceneComponentAuthoring)
        self.assertFalse(hasattr(fixture, "entity_authoring"))
        self.assertFalse(hasattr(fixture, "serializable_authoring"))

    def test_component_owner_has_exact_methods_and_no_forbidden_dependencies(self) -> None:
        methods = {
            name
            for name, value in vars(SceneComponentAuthoring).items()
            if callable(value) and not name.startswith("_")
        }
        source = inspect.getsource(component_module)

        self.assertEqual(methods, COMPONENT_METHODS)
        for forbidden in (
            "SceneEntityAuthoring",
            "SceneSerializableAuthoring",
            "SceneManager",
            "SceneStructuralAuthoring",
            "SceneEditSyncCoordinator",
            "SerializableMutationCoordinator",
            "record_scene_change(",
            "mark_dirty(",
        ):
            self.assertNotIn(forbidden, source)


class SceneComponentAuthoringTests(_SerializableOwnerTestSupport):
    def setUp(self) -> None:
        super().setUp()
        self.authoring = SceneComponentAuthoring(
            self.workspace,
            self.pipeline,
            self.projection,
            self.prefab_overrides,
            self.flow_policy,
            self.registry,
        )

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
                side_effect=lambda *args, **kwargs: (
                    events.append("flush"),
                    flush(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.mutations,
                "capture_snapshot",
                side_effect=lambda *args, **kwargs: (
                    events.append("capture"),
                    capture(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.entry.scene,
                "update_component",
                side_effect=lambda *args, **kwargs: (
                    events.append("mutate"),
                    mutate(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.mutations,
                "commit_mutation",
                side_effect=lambda *args, **kwargs: (
                    events.append("commit"),
                    commit(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.workspace,
                "mark_dirty",
                side_effect=lambda *args, **kwargs: (
                    events.append("dirty"),
                    mark_dirty(*args, **kwargs),
                )[1],
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
        inactive = next(
            item
            for item in self.workspace.entries.values()
            if item.key != self.workspace.active_scene_key
        )

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

    def test_multiscene_component_routes_flush_before_entity_preconditions(self) -> None:
        assert self.entry.edit_world is not None
        pending_upsert = self.entry.edit_world.create_entity("PendingUpsert")
        pending_upsert.add_component(Transform(x=2.0))
        self.assertTrue(
            self.edit_sync.mark_edit_world_dirty(
                reason=LEGACY_AUTHORING_SYNC_REASON,
            )
        )

        self.assertTrue(
            self.authoring.upsert_component_for_scene(
                self.entry,
                "PendingUpsert",
                "Transform",
                _transform(8.0),
            )
        )
        self.assertEqual(
            self.entry.scene.find_entity("PendingUpsert")["components"]["Transform"]["x"],
            8.0,
        )

        pending_remove = self.entry.edit_world.create_entity("PendingRemove")
        pending_remove.add_component(Transform(x=3.0))
        self.assertTrue(
            self.edit_sync.mark_edit_world_dirty(
                reason=LEGACY_AUTHORING_SYNC_REASON,
            )
        )

        self.assertTrue(
            self.authoring.remove_component_for_scene(
                self.entry,
                "PendingRemove",
                "Transform",
            )
        )
        self.assertNotIn(
            "Transform",
            self.entry.scene.find_entity("PendingRemove")["components"],
        )

    def test_component_prefab_fallbacks_use_only_the_port(self) -> None:
        self.assertTrue(
            self.authoring.apply_edit_to_world(
                "Expanded",
                "Sprite",
                "enabled",
                False,
            )
        )
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

    def test_metadata_query_returns_defensive_copy(self) -> None:
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
        exposed_metadata["nested"]["values"].append(3)

        stored = self.entry.scene.find_entity("Hero")
        self.assertEqual(
            stored["component_metadata"]["Transform"],
            {"nested": {"values": [1]}},
        )

    def test_component_by_id_mutations_target_the_same_entity(self) -> None:
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
        self.assertEqual(stored["components"]["Transform"]["x"], 7.0)
        self.assertNotIn("SceneLink", stored["components"])

    def test_component_by_id_routes_flush_before_lookup_and_keep_id_target(self) -> None:
        operations = (
            lambda: self.authoring.replace_component_data_by_id(
                "hero-id",
                "Transform",
                _transform(4.0),
            ),
            lambda: self.authoring.add_component_to_entity_by_id(
                "hero-id",
                "SceneLink",
                {"flow_key": "exit", "target_path": "next.json"},
            ),
            lambda: self.authoring.remove_component_from_entity_by_id(
                "hero-id",
                "SceneLink",
            ),
        )

        for operation in operations:
            events: list[str] = []
            scene = self.entry.scene
            flush = self.edit_sync.flush_pending
            lookup = scene.find_entity_by_id
            with (
                patch.object(
                    self.edit_sync,
                    "flush_pending",
                    side_effect=lambda *args, **kwargs: (
                        events.append("flush"),
                        flush(*args, **kwargs),
                    )[1],
                ),
                patch.object(
                    scene,
                    "find_entity_by_id",
                    side_effect=lambda *args, **kwargs: (
                        events.append("lookup"),
                        lookup(*args, **kwargs),
                    )[1],
                ),
            ):
                self.assertTrue(operation())

            self.assertLess(events.index("flush"), events.index("lookup"))
            self.assertEqual(
                self.entry.scene.find_entity_by_id("hero-id")["name"],
                "Hero",
            )

    def test_play_rejects_multiscene_route_before_flush_or_capture(self) -> None:
        self.assertIsNotNone(self.workspace.enter_play())
        with (
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(self.mutations, "capture_snapshot") as capture,
        ):
            self.assertFalse(
                self.authoring.upsert_component_for_scene(
                    self.entry,
                    "Hero",
                    "Transform",
                    _transform(2.0),
                )
            )

        flush.assert_not_called()
        capture.assert_not_called()

    def test_scene_flow_target_orders_pipeline_policy_commit_dirty_history(self) -> None:
        events: list[str] = []
        self.history.events = events
        flush = self.edit_sync.flush_pending
        capture = self.mutations.capture_snapshot
        mutate = self.flow_policy.set_metadata_target
        commit = self.mutations.commit_mutation
        mark_dirty = self.workspace.mark_dirty

        with (
            patch.object(
                self.edit_sync,
                "flush_pending",
                side_effect=lambda *args, **kwargs: (
                    events.append("flush"),
                    flush(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.mutations,
                "capture_snapshot",
                side_effect=lambda *args, **kwargs: (
                    events.append("capture"),
                    capture(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.flow_policy,
                "set_metadata_target",
                side_effect=lambda *args, **kwargs: (
                    events.append("mutate"),
                    mutate(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.mutations,
                "commit_mutation",
                side_effect=lambda *args, **kwargs: (
                    events.append("commit"),
                    commit(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.workspace,
                "mark_dirty",
                side_effect=lambda *args, **kwargs: (
                    events.append("dirty"),
                    mark_dirty(*args, **kwargs),
                )[1],
            ),
        ):
            self.assertTrue(
                self.authoring.set_scene_flow_target(
                    " next ",
                    "levels/next.json",
                )
            )

        self.assertEqual(
            events,
            ["flush", "capture", "mutate", "commit", "dirty", "history"],
        )
        self.assertEqual(self.history.scene_changes[-1][1], "scene_flow:next")
        self.assertEqual(
            self.entry.scene.feature_metadata["scene_flow"],
            {"next": "levels/next.json"},
        )

    def test_scene_flow_target_rejects_play_before_flush_or_capture(self) -> None:
        self.assertIsNotNone(self.workspace.enter_play())

        with (
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(self.mutations, "capture_snapshot") as capture,
        ):
            self.assertFalse(
                self.authoring.set_scene_flow_target(
                    "next",
                    "levels/next.json",
                )
            )

        flush.assert_not_called()
        capture.assert_not_called()

    def test_scene_flow_target_rejects_blank_key_before_pipeline(self) -> None:
        with patch.object(self.pipeline, "begin") as begin:
            self.assertFalse(
                self.authoring.set_scene_flow_target(
                    "   ",
                    "levels/next.json",
                )
            )

        begin.assert_not_called()

    def test_scene_flow_target_exception_rolls_back_without_history(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_dict())
        mutate = self.flow_policy.set_metadata_target

        def mutate_then_fail(*args, **kwargs):
            mutate(*args, **kwargs)
            raise RuntimeError("flow mutation failed")

        with patch.object(
            self.flow_policy,
            "set_metadata_target",
            side_effect=mutate_then_fail,
        ):
            self.assertFalse(
                self.authoring.set_scene_flow_target(
                    "next",
                    "levels/next.json",
                )
            )

        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertFalse(self.entry.dirty)
        self.assertEqual(self.history.scene_changes, [])

    def test_scene_flow_target_commit_failure_restores_snapshot(self) -> None:
        before = copy.deepcopy(self.entry.scene.to_dict())
        validate = self.projection.validate_payload
        calls = 0

        def fail_first_validation(payload):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("invalid flow payload")
            return validate(payload)

        with patch.object(
            self.projection,
            "validate_payload",
            side_effect=fail_first_validation,
        ):
            self.assertFalse(
                self.authoring.set_scene_flow_target(
                    "next",
                    "levels/next.json",
                )
            )

        self.assertEqual(calls, 2)
        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertFalse(self.entry.dirty)
        self.assertEqual(self.history.scene_changes, [])

    def test_scene_flow_target_flushes_pending_before_snapshot(self) -> None:
        hero = self.entry.edit_world.get_entity_by_name("Hero")
        hero.get_component(Transform).x = 42.0
        self.assertTrue(
            self.edit_sync.mark_edit_world_dirty(
                reason=LEGACY_AUTHORING_SYNC_REASON,
            )
        )

        self.assertTrue(
            self.authoring.set_scene_flow_target(
                "next",
                "levels/next.json",
            )
        )

        self.assertEqual(
            self.entry.scene.find_entity("Hero")["components"]["Transform"]["x"],
            42.0,
        )
        self.assertEqual(
            self.entry.scene.feature_metadata["scene_flow"],
            {"next": "levels/next.json"},
        )
        self.assertIsNone(self.entry.pending_edit_world_sync_reason)


if __name__ == "__main__":
    unittest.main()
