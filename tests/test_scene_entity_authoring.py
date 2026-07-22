import copy
import inspect
import unittest
from unittest.mock import patch

import engine.scenes.entity_authoring as entity_module
from engine.components.transform import Transform
from engine.scenes.contracts import SceneSerializableEntityPort
from engine.scenes.edit_sync import (
    LEGACY_AUTHORING_SYNC_REASON,
    TRANSIENT_PREVIEW_SYNC_REASON,
)
from engine.scenes.entity_authoring import SceneEntityAuthoring
from tests.test_scene_serializable_authoring import _SerializableOwnerTestSupport

ENTITY_METHODS = {
    "find_entity_data_for_entry",
    "list_scene_entities",
    "find_entity_data",
    "find_entity_data_by_id",
    "update_entity_property",
    "update_entity_property_by_id",
    "set_entity_groups",
    "create_entity",
    "create_entity_from_data",
}


class SceneEntityAuthoringArchitectureTests(unittest.TestCase):
    def test_entity_behavior_fixture_constructs_only_entity_owner(self) -> None:
        fixture_source = inspect.getsource(SceneEntityAuthoringTests.setUp)
        support_source = inspect.getsource(_SerializableOwnerTestSupport.setUp)
        fixture = SceneEntityAuthoringTests(
            "test_play_rejects_by_id_route_before_flush_or_capture"
        )
        fixture.setUp()

        self.assertIn("SceneEntityAuthoring(", fixture_source)
        self.assertNotIn("SceneSerializableAuthoring(", fixture_source)
        self.assertNotIn("SceneComponentAuthoring(", fixture_source)
        self.assertNotIn("SceneSerializableAuthoring(", support_source)
        self.assertNotIn("SceneComponentAuthoring(", support_source)
        self.assertNotIn("SceneEntityAuthoring(", support_source)
        self.assertIsInstance(fixture.authoring, SceneEntityAuthoring)
        self.assertFalse(hasattr(fixture, "component_authoring"))
        self.assertFalse(hasattr(fixture, "serializable_authoring"))

    def test_entity_owner_has_exact_methods_implements_port_and_is_independent(self) -> None:
        owner_methods = {
            name
            for name, value in vars(SceneEntityAuthoring).items()
            if callable(value) and not name.startswith("_")
        }
        port_methods = {
            name
            for name, value in vars(SceneSerializableEntityPort).items()
            if callable(value) and not name.startswith("_")
        }
        source = inspect.getsource(entity_module)

        self.assertEqual(owner_methods, ENTITY_METHODS)
        self.assertEqual(
            port_methods,
            {"create_entity", "create_entity_from_data", "update_entity_property"},
        )
        for forbidden in (
            "SceneComponentAuthoring",
            "SceneSerializableAuthoring",
            "SceneManager",
            "SceneStructuralAuthoring",
            "SceneEditSyncCoordinator",
            "SerializableMutationCoordinator",
            "record_scene_change(",
            "mark_dirty(",
        ):
            self.assertNotIn(forbidden, source)


class SceneEntityAuthoringTests(_SerializableOwnerTestSupport):
    def setUp(self) -> None:
        super().setUp()
        self.authoring = SceneEntityAuthoring(
            self.workspace,
            self.pipeline,
            self.projection,
            self.history,
            self.prefab_overrides,
            self.flow_policy,
            self.registry,
        )

    def test_entity_prefab_fallback_uses_only_the_port(self) -> None:
        self.assertTrue(
            self.authoring.update_entity_property(
                "Expanded",
                "tag",
                "Enemy",
            )
        )

        self.assertEqual(
            self.prefab_overrides.calls,
            ["update_entity_property"],
        )

    def test_entity_queries_return_defensive_copies(self) -> None:
        exposed_entity = self.authoring.find_entity_data("Hero")
        exposed_by_id = self.authoring.find_entity_data_by_id("hero-id")
        exposed_entity["components"]["Transform"]["x"] = 99.0
        exposed_by_id["tag"] = "Poisoned"

        stored = self.entry.scene.find_entity("Hero")
        self.assertEqual(stored["components"]["Transform"]["x"], 1.0)
        self.assertEqual(stored["tag"], "Untagged")

    def test_entity_by_id_mutation_targets_the_same_entity(self) -> None:
        self.assertTrue(
            self.authoring.update_entity_property_by_id(
                "hero-id",
                "tag",
                "Player",
            )
        )

        stored = self.entry.scene.find_entity_by_id("hero-id")
        self.assertEqual(stored["tag"], "Player")

    def test_entity_by_id_route_flushes_before_lookup_and_keeps_id_target(self) -> None:
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
            self.assertTrue(
                self.authoring.update_entity_property_by_id(
                    "hero-id",
                    "tag",
                    "Player",
                )
            )

        self.assertLess(events.index("flush"), events.index("lookup"))
        self.assertEqual(
            self.entry.scene.find_entity_by_id("hero-id")["name"],
            "Hero",
        )

    def test_play_rejects_by_id_route_before_flush_or_capture(self) -> None:
        self.assertIsNotNone(self.workspace.enter_play())
        with (
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(self.mutations, "capture_snapshot") as capture,
        ):
            self.assertFalse(
                self.authoring.update_entity_property_by_id(
                    "hero-id",
                    "tag",
                    "Player",
                )
            )

        flush.assert_not_called()
        capture.assert_not_called()

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
                side_effect=lambda *args, **kwargs: (
                    events.append("capture"),
                    capture(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.flow_policy,
                "prepare_entity",
                side_effect=lambda *args, **kwargs: (
                    events.append("prepare"),
                    prepare(*args, **kwargs),
                )[1],
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

    def test_creation_delta_undo_flushes_before_id_lookup(self) -> None:
        self.assertTrue(self.authoring.create_entity("Added"))
        undo = self.history.differential_changes[-1]["undo"]
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
            self.assertTrue(undo())

        self.assertLess(events.index("flush"), events.index("lookup"))
        self.assertIsNone(self.entry.scene.find_entity("Added"))

    def test_creation_delta_redo_blocks_pending_legacy_without_import(self) -> None:
        self.assertTrue(self.authoring.create_entity("Added"))
        change = self.history.differential_changes[-1]
        self.assertTrue(change["undo"]())

        hero = self.entry.edit_world.get_entity_by_name("Hero")
        hero_transform = hero.get_component(Transform)
        hero_transform.x = 42.0
        self.assertTrue(
            self.edit_sync.mark_edit_world_dirty(
                reason=LEGACY_AUTHORING_SYNC_REASON,
            )
        )
        events: list[str] = []
        flush = self.edit_sync.flush_pending
        capture = self.mutations.capture_snapshot
        add = self.projection.add_entity

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
                    events.append(
                        "capture_authoring"
                        if kwargs.get("clone_world") is True
                        else "capture_guard"
                    ),
                    capture(*args, **kwargs),
                )[1],
            ),
            patch.object(
                self.projection,
                "add_entity",
                side_effect=lambda *args, **kwargs: (
                    events.append("add"),
                    add(*args, **kwargs),
                )[1],
            ),
        ):
            self.assertFalse(change["redo"]())

        self.assertEqual(
            events,
            ["capture_guard", "flush"],
        )
        self.assertEqual(
            self.entry.scene.find_entity("Hero")["components"]["Transform"]["x"],
            1.0,
        )
        hero = self.entry.edit_world.get_entity_by_name("Hero")
        self.assertEqual(hero.get_component(Transform).x, 42.0)
        self.assertIsNone(self.entry.scene.find_entity("Added"))
        self.assertIsNone(self.entry.edit_world.get_entity_by_name("Added"))
        self.assertEqual(self.entry.pending_edit_world_sync_reason, LEGACY_AUTHORING_SYNC_REASON)

    def test_creation_delta_redo_failure_restores_post_flush_state(self) -> None:
        self.assertTrue(self.authoring.create_entity("Added"))
        change = self.history.differential_changes[-1]
        self.assertTrue(change["undo"]())
        self.workspace.clear_dirty(self.entry)
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        hero = self.entry.edit_world.get_entity_by_name("Hero")
        hero_transform = hero.get_component(Transform)
        hero_transform.x = 42.0
        self.assertTrue(
            self.edit_sync.mark_edit_world_dirty(
                reason=LEGACY_AUTHORING_SYNC_REASON,
            )
        )
        with patch.object(
            self.projection,
            "add_entity",
            wraps=self.projection.add_entity,
        ):
            self.assertFalse(change["redo"]())

        self.assertEqual(
            self.entry.scene.find_entity("Hero")["components"]["Transform"]["x"],
            1.0,
        )
        hero = self.entry.edit_world.get_entity_by_name("Hero")
        self.assertEqual(hero.get_component(Transform).x, 42.0)
        self.assertIsNone(self.entry.scene.find_entity("Added"))
        self.assertIsNone(self.entry.edit_world.get_entity_by_name("Added"))
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertEqual(
            self.entry.selected_entity_id,
            self.entry.scene.find_entity("Hero")["id"],
        )
        self.assertEqual(self.entry.edit_world.selected_entity_name, "Hero")
        self.assertTrue(self.entry.dirty)
        self.assertEqual(self.entry.pending_edit_world_sync_reason, LEGACY_AUTHORING_SYNC_REASON)
        self.assertEqual(len(self.history.differential_changes), 1)
        self.assertEqual(self.history.scene_changes, [])

    def test_creation_delta_redo_rejects_play_before_flush_or_capture(self) -> None:
        self.assertTrue(self.authoring.create_entity("Added"))
        change = self.history.differential_changes[-1]
        self.assertTrue(change["undo"]())
        self.assertIsNotNone(self.workspace.enter_play())

        with (
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(self.mutations, "capture_snapshot") as capture,
        ):
            self.assertFalse(change["redo"]())

        flush.assert_not_called()
        capture.assert_not_called()

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

    def test_creation_history_failure_rolls_back_scene_world_and_prior_history(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        self.edit_sync.restore_pending_reason(
            self.entry,
            TRANSIENT_PREVIEW_SYNC_REASON,
        )
        scene_before = copy.deepcopy(self.entry.scene.to_dict())
        world_before = copy.deepcopy(self.entry.edit_world.serialize())
        prior_change = {"label": "previous", "undo": lambda: True, "redo": lambda: True}
        self.history.differential_changes.append(prior_change)

        with patch.object(
            self.history,
            "record_differential_change",
            side_effect=RuntimeError("history unavailable"),
        ):
            self.assertFalse(self.authoring.create_entity("RejectedByHistory"))

        self.assertEqual(self.entry.scene.to_dict(), scene_before)
        self.assertEqual(self.entry.edit_world.serialize(), world_before)
        self.assertIsNone(self.entry.scene.find_entity("RejectedByHistory"))
        self.assertIsNone(self.entry.edit_world.get_entity_by_name("RejectedByHistory"))
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertEqual(self.entry.edit_world.selected_entity_name, "Hero")
        self.assertFalse(self.entry.dirty)
        self.assertEqual(
            self.entry.pending_edit_world_sync_reason,
            TRANSIENT_PREVIEW_SYNC_REASON,
        )
        self.assertEqual(self.entry.edit_world_version, self.entry.edit_world.version)
        self.assertEqual(self.history.differential_changes, [prior_change])

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

        self.assertEqual(calls, 1)
        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertIsNone(self.entry.edit_world.get_entity_by_name("Rejected"))
        self.assertFalse(self.entry.dirty)
        self.assertEqual(self.history.differential_changes, [])


if __name__ == "__main__":
    unittest.main()
