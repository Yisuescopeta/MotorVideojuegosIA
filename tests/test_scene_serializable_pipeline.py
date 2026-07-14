import ast
import inspect
import textwrap
import unittest
from unittest.mock import patch

import engine.scenes.serializable_pipeline as pipeline_module
from engine.levels.component_registry import create_default_registry
from engine.scenes.contracts import SceneSerializableTransactionPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
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

    def record_scene_change(self, entry, label, before) -> None:
        self.events.append("history")
        self.scene_changes.append((entry, label, before))

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
