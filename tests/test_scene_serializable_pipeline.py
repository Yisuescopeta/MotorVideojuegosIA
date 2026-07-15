import ast
import copy
import inspect
import textwrap
import unittest
from unittest.mock import call, patch

import engine.scenes.serializable_pipeline as pipeline_module
from engine.levels.component_registry import create_default_registry
from engine.scenes.contracts import SceneSerializableTransactionPort
from engine.scenes.edit_sync import (
    LEGACY_AUTHORING_SYNC_REASON,
    TRANSIENT_PREVIEW_SYNC_REASON,
    SceneEditSyncCoordinator,
)
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_authoring import SceneSerializableAuthoring
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.serializable_pipeline import SceneSerializableAuthoringPipeline
from engine.scenes.workspace_lifecycle import SceneWorkspace

SERIALIZABLE_METHOD_OWNERS = {
    "get_feature_metadata": "_component_authoring",
    "get_component_data": "_component_authoring",
    "get_component_data_for_entry": "_component_authoring",
    "get_component_metadata": "_component_authoring",
    "upsert_component_for_scene": "_component_authoring",
    "remove_component_for_scene": "_component_authoring",
    "apply_edit_to_world": "_component_authoring",
    "replace_component_data": "_component_authoring",
    "replace_component_data_by_id": "_component_authoring",
    "add_component_to_entity": "_component_authoring",
    "add_component_to_entity_by_id": "_component_authoring",
    "remove_component_from_entity": "_component_authoring",
    "remove_component_from_entity_by_id": "_component_authoring",
    "set_component_enabled": "_component_authoring",
    "set_component_metadata": "_component_authoring",
    "set_feature_metadata": "_component_authoring",
    "set_scene_flow_target": "_component_authoring",
    "apply_authoring_component_state": "_component_authoring",
    "find_entity_data_for_entry": "_entity_authoring",
    "list_scene_entities": "_entity_authoring",
    "find_entity_data": "_entity_authoring",
    "find_entity_data_by_id": "_entity_authoring",
    "update_entity_property": "_entity_authoring",
    "update_entity_property_by_id": "_entity_authoring",
    "set_entity_groups": "_entity_authoring",
    "create_entity": "_entity_authoring",
    "create_entity_from_data": "_entity_authoring",
}


class _History:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.scene_changes: list[tuple] = []

    def record_snapshot_change(self, *, label, undo, redo) -> None:
        self.events.append("history")
        self.scene_changes.append((label, undo, redo))

    def record_differential_change(self, *, label, undo, redo) -> None:
        raise AssertionError("pipeline must not record differential history")


class SceneSerializablePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        registry = create_default_registry()
        self.projection = SceneProjectionService(registry)
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
        self.pipeline = SceneSerializableAuthoringPipeline(
            self.workspace,
            self.edit_sync,
            self.mutations,
            self.history,
        )
        self.workspace.load_scene(
            {
                "name": "Pipeline",
                "entities": [
                    {
                        "id": "hero-id",
                        "name": "Hero",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None

    def test_protocol_is_narrow_and_pipeline_has_only_transaction_dependencies(self) -> None:
        methods = {
            name
            for name, value in vars(SceneSerializableTransactionPort).items()
            if callable(value) and not name.startswith("_")
        }
        source = inspect.getsource(pipeline_module)

        self.assertEqual(
            methods,
            {
                "flush_pending",
                "begin",
                "rollback",
                "commit_snapshot",
                "commit_incremental",
            },
        )
        self.assertEqual(
            tuple(inspect.signature(SceneSerializableAuthoringPipeline).parameters),
            ("workspace", "edit_sync", "mutations", "history"),
        )
        for forbidden in (
            "SceneComponentAuthoring",
            "SceneEntityAuthoring",
            "ComponentRegistry",
            "PrefabOverridePort",
            "SceneFlowPolicy",
            "SceneProjectionService",
            "SceneManager",
            "SceneStructuralAuthoring",
        ):
            self.assertNotIn(forbidden, source)

    def test_snapshot_pipeline_orders_flush_capture_commit_dirty_history(self) -> None:
        events: list[str] = []
        flush = self.edit_sync.flush_pending
        capture = self.mutations.capture_snapshot
        snapshot = self.mutations.snapshot_scene_data
        commit = self.mutations.commit_mutation
        mark_dirty = self.workspace.mark_dirty
        self.history.events = events

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
                self.mutations,
                "snapshot_scene_data",
                side_effect=lambda *args, **kwargs: (
                    events.append("snapshot"),
                    snapshot(*args, **kwargs),
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
            transaction = self.pipeline.begin(
                self.entry,
                failure_context="pipeline_test",
            )
            assert transaction is not None
            token, before = transaction
            self.assertTrue(
                self.entry.scene.update_entity_property("Hero", "tag", "Player")
            )
            self.assertTrue(
                self.pipeline.commit_snapshot(
                    self.entry,
                    token,
                    before,
                    label="Hero.tag",
                )
            )

        self.assertEqual(
            events,
            ["flush", "capture", "snapshot", "commit", "dirty", "history"],
        )

    def test_play_rejects_begin_before_flush_or_capture(self) -> None:
        self.assertIsNotNone(self.workspace.enter_play())

        with (
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(self.mutations, "capture_snapshot") as capture,
        ):
            self.assertIsNone(
                self.pipeline.begin(
                    self.entry,
                    failure_context="play_rejection",
                )
            )

        flush.assert_not_called()
        capture.assert_not_called()

    def test_pending_guard_capture_failure_is_contained_before_flush(self) -> None:
        self.edit_sync.restore_pending_reason(
            self.entry,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        with (
            patch.object(
                self.mutations,
                "capture_snapshot",
                side_effect=RuntimeError("guard unavailable"),
            ),
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(pipeline_module, "log_err") as log_error,
        ):
            self.assertFalse(
                self.pipeline.flush_pending(
                    self.entry,
                    failure_context="guard_failure",
                )
            )

        flush.assert_not_called()
        log_error.assert_called_once_with(
            "SceneSerializableAuthoringPipeline: failed to guard pending flush "
            "guard_failure: guard unavailable"
        )

    def test_flush_without_active_legacy_pending_does_not_capture_guard(self) -> None:
        with (
            patch.object(self.mutations, "capture_snapshot") as capture,
            patch.object(
                self.edit_sync,
                "flush_pending",
                return_value=True,
            ) as flush,
        ):
            self.assertTrue(
                self.pipeline.flush_pending(
                    self.entry,
                    failure_context="no_pending",
                )
            )

        capture.assert_not_called()
        flush.assert_called_once_with(
            self.entry,
            failure_context="no_pending",
        )

    def test_inactive_legacy_pending_rejects_before_delegate_guard_or_log(self) -> None:
        self.edit_sync.restore_pending_reason(
            self.entry,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        self.workspace.create_new_scene("Other", activate=True)

        with (
            patch.object(self.edit_sync, "flush_pending") as flush,
            patch.object(self.mutations, "capture_snapshot") as capture,
            patch.object(pipeline_module, "log_err") as log_error,
        ):
            self.assertFalse(
                self.pipeline.flush_pending(
                    self.entry,
                    failure_context="inactive_legacy",
                )
            )

        flush.assert_not_called()
        capture.assert_not_called()
        log_error.assert_not_called()

    def test_inactive_nonlegacy_pending_delegates_without_guard(self) -> None:
        self.workspace.create_new_scene("Other", activate=True)

        for reason in (None, TRANSIENT_PREVIEW_SYNC_REASON):
            with self.subTest(reason=reason):
                self.edit_sync.restore_pending_reason(self.entry, reason)
                with (
                    patch.object(
                        self.edit_sync,
                        "flush_pending",
                        return_value=True,
                    ) as flush,
                    patch.object(self.mutations, "capture_snapshot") as capture,
                ):
                    self.assertTrue(
                        self.pipeline.flush_pending(
                            self.entry,
                            failure_context="inactive_nonlegacy",
                        )
                    )

                flush.assert_called_once_with(
                    self.entry,
                    failure_context="inactive_nonlegacy",
                )
                capture.assert_not_called()

    def test_normal_pending_rejection_does_not_restore_guard(self) -> None:
        self.edit_sync.restore_pending_reason(
            self.entry,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        guard = object()
        with (
            patch.object(self.mutations, "capture_snapshot", return_value=guard) as capture,
            patch.object(self.edit_sync, "flush_pending", return_value=False),
            patch.object(self.mutations, "restore_snapshot") as restore,
        ):
            self.assertFalse(
                self.pipeline.flush_pending(
                    self.entry,
                    failure_context="normal_rejection",
                )
            )

        capture.assert_called_once_with(self.entry)
        restore.assert_not_called()

    def test_successful_pending_flush_uses_fresh_authoring_snapshot(self) -> None:
        self.edit_sync.restore_pending_reason(
            self.entry,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        guard = object()
        authoring_token = object()

        def flush_pending(*args, **kwargs):
            self.edit_sync.clear_pending(self.entry)
            return True

        with (
            patch.object(
                self.mutations,
                "capture_snapshot",
                side_effect=[guard, authoring_token],
            ) as capture,
            patch.object(self.edit_sync, "flush_pending", side_effect=flush_pending),
            patch.object(
                self.mutations,
                "snapshot_scene_data",
                return_value={"name": "after flush"},
            ),
        ):
            transaction = self.pipeline.begin(
                self.entry,
                failure_context="pending_success",
            )

        self.assertIsNotNone(transaction)
        assert transaction is not None
        self.assertIs(transaction[0], authoring_token)
        self.assertEqual(
            capture.call_args_list,
            [
                call(self.entry),
                call(self.entry, clone_world=False),
            ],
        )

    def test_begin_returns_none_when_snapshot_preparation_fails(self) -> None:
        with (
            patch.object(
                self.mutations,
                "snapshot_scene_data",
                side_effect=RuntimeError("snapshot unavailable"),
            ),
            patch.object(pipeline_module, "log_err") as log_error,
        ):
            self.assertIsNone(
                self.pipeline.begin(
                    self.entry,
                    failure_context="begin_failure",
                )
            )

        self.assertEqual(self.entry.scene.find_entity("Hero")["tag"], "Untagged")
        self.assertFalse(self.entry.dirty)
        log_error.assert_called_once_with(
            "SceneSerializableAuthoringPipeline: failed to begin "
            "begin_failure: snapshot unavailable"
        )

    def test_snapshot_history_failure_rolls_back_all_state(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        self.edit_sync.restore_pending_reason(
            self.entry,
            TRANSIENT_PREVIEW_SYNC_REASON,
        )
        scene_before = copy.deepcopy(self.entry.scene.to_dict())
        world_before = copy.deepcopy(self.entry.edit_world.serialize())
        self.history.scene_changes.append(("previous",))
        transaction = self.pipeline.begin(
            self.entry,
            failure_context="history_failure",
        )
        assert transaction is not None
        token, before = transaction
        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Player"))

        with patch.object(
            self.history,
            "record_snapshot_change",
            side_effect=RuntimeError("history unavailable"),
        ):
            self.assertFalse(
                self.pipeline.commit_snapshot(
                    self.entry,
                    token,
                    before,
                    label="Hero.tag",
                )
            )

        self.assertEqual(self.entry.scene.to_dict(), scene_before)
        self.assertEqual(self.entry.edit_world.serialize(), world_before)
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertEqual(self.entry.edit_world.selected_entity_name, "Hero")
        self.assertFalse(self.entry.dirty)
        self.assertEqual(
            self.entry.pending_edit_world_sync_reason,
            TRANSIENT_PREVIEW_SYNC_REASON,
        )
        self.assertEqual(self.entry.edit_world_version, self.entry.edit_world.version)
        self.assertEqual(self.history.scene_changes, [("previous",)])

    def test_facade_has_exactly_27_single_delegation_wrappers(self) -> None:
        public_methods = {
            name: value
            for name, value in vars(SceneSerializableAuthoring).items()
            if callable(value) and not name.startswith("_")
        }

        self.assertEqual(set(public_methods), set(SERIALIZABLE_METHOD_OWNERS))
        for method_name, owner_attribute in SERIALIZABLE_METHOD_OWNERS.items():
            function = public_methods[method_name]
            tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
            self.assertEqual(len(calls), 1, method_name)
            target = calls[0].func
            self.assertIsInstance(target, ast.Attribute, method_name)
            self.assertEqual(target.attr, method_name, method_name)
            self.assertIsInstance(target.value, ast.Attribute, method_name)
            self.assertEqual(target.value.attr, owner_attribute, method_name)

    def test_split_modules_have_unidirectional_acyclic_imports(self) -> None:
        import engine.scenes.component_authoring as component_module
        import engine.scenes.entity_authoring as entity_module
        import engine.scenes.serializable_authoring as facade_module

        component_source = inspect.getsource(component_module)
        entity_source = inspect.getsource(entity_module)
        facade_source = inspect.getsource(facade_module)

        self.assertNotIn("entity_authoring", component_source)
        self.assertNotIn("component_authoring", entity_source)
        self.assertNotIn("serializable_authoring", component_source)
        self.assertNotIn("serializable_authoring", entity_source)
        self.assertIn("component_authoring", facade_source)
        self.assertIn("entity_authoring", facade_source)
        self.assertIn("serializable_pipeline", facade_source)


if __name__ == "__main__":
    unittest.main()
