import copy
import inspect
import unittest
from unittest.mock import patch

import engine.scenes.scene_manager as scene_manager_module
import engine.scenes.serializable_mutation as serializable_mutation_module
from engine.levels.component_registry import create_default_registry
from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON, SceneEditSyncCoordinator
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.workspace_lifecycle import SceneWorkspace


def _scene_payload() -> dict:
    return {
        "name": "Serializable Mutation",
        "entities": [
            {
                "name": "Hero",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 1.0,
                        "y": 2.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            },
            {
                "name": "Other",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {},
            },
        ],
        "rules": [],
        "feature_metadata": {},
    }


class SerializableMutationCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projection = SceneProjectionService(create_default_registry())
        self.workspace = SceneWorkspace(
            projection=self.projection,
            flow_policy=SceneFlowPolicy(),
        )
        self.edit_sync = SceneEditSyncCoordinator(self.workspace, self.projection)
        self.coordinator = SerializableMutationCoordinator(
            self.workspace,
            self.projection,
            self.edit_sync,
        )
        self.workspace.load_scene(_scene_payload())
        self.entry = self.workspace.get_active_entry()
        assert self.entry is not None

    def test_valid_commit_installs_equivalent_scene_world_and_clears_pending(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        self.edit_sync.restore_pending_reason(self.entry, LEGACY_AUTHORING_SYNC_REASON)
        token = self.coordinator.capture_snapshot(self.entry)
        before = self.coordinator.snapshot_scene_data(token)

        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Player"))

        self.assertTrue(
            self.coordinator.commit_mutation(
                self.entry,
                token,
                failure_context="valid_commit",
            )
        )

        self.assertEqual(self.entry.scene.find_entity("Hero")["tag"], "Player")
        self.assertEqual(
            self.entry.edit_world.get_entity_by_name("Hero").tag,
            "Player",
        )
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertEqual(
            self.entry.selected_entity_id,
            self.entry.scene.find_entity("Hero")["id"],
        )
        self.assertEqual(self.entry.edit_world.selected_entity_name, "Hero")
        self.assertFalse(self.entry.dirty)
        self.assertIsNone(self.entry.pending_edit_world_sync_reason)
        self.assertIsNone(self.entry.dirty_before_pending_edit_world_sync)
        self.assertEqual(self.entry.edit_world_version, self.entry.edit_world.version)
        self.assertEqual(self.coordinator.snapshot_scene_data(token), before)

    def test_projection_failure_restores_semantic_state_through_authorities(self) -> None:
        self.workspace.load_scene(
            _scene_payload(),
            source_path="inactive.json",
            activate=False,
        )
        entry = next(
            candidate
            for candidate in self.workspace.entries.values()
            if candidate.key != self.workspace.active_scene_key
        )
        self.assertTrue(self.workspace.select_entity(entry, entity_name="Hero"))
        self.workspace.mark_dirty(entry)
        entry.pending_edit_world_sync_reason = LEGACY_AUTHORING_SYNC_REASON
        entry.dirty_before_pending_edit_world_sync = False
        with patch.object(
            self.edit_sync,
            "capture_snapshot",
            wraps=self.edit_sync.capture_snapshot,
        ) as capture_pending:
            token = self.coordinator.capture_snapshot(entry)
        capture_pending.assert_called_once_with(entry)
        scene_before = copy.deepcopy(entry.scene.to_dict())
        world_before = copy.deepcopy(entry.edit_world.serialize())

        self.assertTrue(entry.scene.update_entity_property("Hero", "tag", "Mutated"))
        self.assertTrue(self.workspace.select_entity(entry, entity_name="Other"))
        self.workspace.clear_dirty(entry)
        self.edit_sync.clear_pending(entry)
        entry.edit_world_version = 777

        original_create_world = self.projection.create_world
        projection_calls = 0

        def fail_first_projection(scene):
            nonlocal projection_calls
            projection_calls += 1
            if projection_calls == 1:
                raise ValueError("reject mutation")
            return original_create_world(scene)

        with patch.object(
            self.projection,
            "create_world",
            side_effect=fail_first_projection,
        ), patch.object(
            self.workspace,
            "install_entry_state",
            wraps=self.workspace.install_entry_state,
        ) as install, patch.object(
            self.workspace,
            "restore_selection",
            wraps=self.workspace.restore_selection,
        ) as restore_selection, patch.object(
            self.workspace,
            "restore_dirty",
            wraps=self.workspace.restore_dirty,
        ) as restore_dirty, patch.object(
            self.edit_sync,
            "restore_snapshot",
            wraps=self.edit_sync.restore_snapshot,
        ) as restore_pending:
            self.assertFalse(
                self.coordinator.commit_mutation(
                    entry,
                    token,
                    failure_context="invalid_projection",
                )
            )

        self.assertEqual(entry.scene.to_dict(), scene_before)
        self.assertEqual(entry.edit_world.serialize(), world_before)
        self.assertEqual(entry.selected_entity_name, "Hero")
        self.assertEqual(
            entry.selected_entity_id,
            entry.scene.find_entity("Hero")["id"],
        )
        self.assertEqual(entry.edit_world.selected_entity_name, "Hero")
        self.assertTrue(entry.dirty)
        self.assertEqual(
            entry.pending_edit_world_sync_reason,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        self.assertFalse(entry.dirty_before_pending_edit_world_sync)
        self.assertNotEqual(entry.edit_world_version, 777)
        self.assertEqual(entry.edit_world_version, entry.edit_world.version)
        install.assert_called_once()
        restore_selection.assert_called_once()
        restore_dirty.assert_called_once_with(entry, True)
        restore_pending.assert_called_once()
        self.assertTrue(self.workspace.activate_scene(entry.key))
        with patch.object(
            self.projection,
            "validate_payload",
            side_effect=ValueError("invalid pending world"),
        ):
            self.assertFalse(
                self.edit_sync.flush_pending(
                    entry,
                    failure_context="inactive_pending_rejection",
                )
            )
        self.assertEqual(entry.scene.to_dict(), scene_before)
        self.assertFalse(entry.dirty)
        self.assertIsNone(entry.pending_edit_world_sync_reason)
        self.assertIsNone(entry.dirty_before_pending_edit_world_sync)

    def test_failed_commit_logs_context_and_original_validation_error(self) -> None:
        token = self.coordinator.capture_snapshot(self.entry)
        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Mutated"))
        original_create_world = self.projection.create_world
        calls = 0

        def fail_first_projection(scene):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("reject mutation")
            return original_create_world(scene)

        with patch.object(
            self.projection,
            "create_world",
            side_effect=fail_first_projection,
        ), patch.object(serializable_mutation_module, "log_err") as log_error:
            self.assertFalse(
                self.coordinator.commit_mutation(
                    self.entry,
                    token,
                    failure_context="feature_metadata:combat",
                )
            )

        log_error.assert_called_once_with(
            "SceneManager: rejected invalid serializable mutation during "
            "feature_metadata:combat: reject mutation"
        )

    def test_runtime_projection_failure_rolls_back_and_logs_context(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        self.workspace.mark_dirty(self.entry)
        self.edit_sync.restore_pending_reason(
            self.entry,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        token = self.coordinator.capture_snapshot(self.entry)
        scene_before = copy.deepcopy(self.entry.scene.to_dict())
        world_before = copy.deepcopy(self.entry.edit_world.serialize())
        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Mutated"))

        original_create_world = self.projection.create_world
        calls = 0

        def fail_first_projection(scene):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("runtime projection failure")
            return original_create_world(scene)

        with patch.object(
            self.projection,
            "create_world",
            side_effect=fail_first_projection,
        ), patch.object(serializable_mutation_module, "log_err") as log_error:
            self.assertFalse(
                self.coordinator.commit_mutation(
                    self.entry,
                    token,
                    failure_context="runtime_failure",
                )
            )

        self.assertEqual(self.entry.scene.to_dict(), scene_before)
        self.assertEqual(self.entry.edit_world.serialize(), world_before)
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertTrue(self.entry.dirty)
        self.assertEqual(
            self.entry.pending_edit_world_sync_reason,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        log_error.assert_called_once_with(
            "SceneManager: rejected invalid serializable mutation during "
            "runtime_failure: runtime projection failure"
        )

    def test_persistent_projection_failure_restores_without_reusing_projection(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        self.workspace.mark_dirty(self.entry)
        self.edit_sync.restore_pending_reason(
            self.entry,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        token = self.coordinator.capture_snapshot(self.entry)
        scene_before = copy.deepcopy(self.entry.scene.to_dict())
        world_before = self.entry.edit_world
        assert world_before is not None
        world_payload_before = copy.deepcopy(world_before.serialize())

        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Mutated"))
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Other"))
        self.workspace.clear_dirty(self.entry)
        self.edit_sync.clear_pending(self.entry)
        self.entry.edit_world_version = 777

        with patch.object(
            self.projection,
            "create_world",
            side_effect=RuntimeError("persistent projection failure"),
        ) as create_world:
            self.assertFalse(
                self.coordinator.commit_mutation(
                    self.entry,
                    token,
                    failure_context="persistent_projection_failure",
                )
            )

        create_world.assert_called_once()
        self.assertEqual(self.entry.scene.to_dict(), scene_before)
        self.assertIs(self.entry.edit_world, world_before)
        self.assertEqual(self.entry.edit_world.serialize(), world_payload_before)
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertEqual(
            self.entry.selected_entity_id,
            self.entry.scene.find_entity("Hero")["id"],
        )
        self.assertEqual(self.entry.edit_world.selected_entity_name, "Hero")
        self.assertTrue(self.entry.dirty)
        self.assertEqual(
            self.entry.pending_edit_world_sync_reason,
            LEGACY_AUTHORING_SYNC_REASON,
        )
        self.assertIsNone(self.entry.dirty_before_pending_edit_world_sync)
        self.assertEqual(self.entry.edit_world_version, self.entry.edit_world.version)

    def test_snapshot_scene_data_is_defensive_and_cannot_poison_rollback(self) -> None:
        token = self.coordinator.capture_snapshot(self.entry)
        exposed = self.coordinator.snapshot_scene_data(token)
        exposed["entities"][0]["tag"] = "Poisoned"
        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Mutated"))
        original_create_world = self.projection.create_world
        calls = 0

        def fail_first_projection(scene):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("reject mutation")
            return original_create_world(scene)

        with patch.object(
            self.projection,
            "create_world",
            side_effect=fail_first_projection,
        ):
            self.assertFalse(
                self.coordinator.commit_mutation(
                    self.entry,
                    token,
                    failure_context="defensive_snapshot",
                )
            )

        self.assertEqual(self.entry.scene.find_entity("Hero")["tag"], "Untagged")

    def test_install_failure_restores_after_partial_install_attempt(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        token = self.coordinator.capture_snapshot(self.entry)
        scene_before = copy.deepcopy(self.entry.scene.to_dict())
        world_before = copy.deepcopy(self.entry.edit_world.serialize())
        self.assertTrue(self.entry.scene.update_entity_property("Hero", "tag", "Mutated"))

        original_install = self.workspace.install_entry_state
        install_calls = 0

        def fail_first_install(entry, scene, world):
            nonlocal install_calls
            install_calls += 1
            if install_calls == 1:
                entry.scene = scene
                raise ValueError("partial install")
            return original_install(entry, scene, world)

        with patch.object(
            self.workspace,
            "install_entry_state",
            side_effect=fail_first_install,
        ):
            self.assertFalse(
                self.coordinator.commit_mutation(
                    self.entry,
                    token,
                    failure_context="partial_install",
                )
            )

        self.assertEqual(install_calls, 2)
        self.assertEqual(self.entry.scene.to_dict(), scene_before)
        self.assertEqual(self.entry.edit_world.serialize(), world_before)
        self.assertEqual(self.entry.edit_world_version, self.entry.edit_world.version)

    def test_restore_scene_data_uses_workspace_and_sync_authorities(self) -> None:
        self.assertTrue(self.workspace.select_entity(self.entry, entity_name="Hero"))
        self.edit_sync.restore_pending_reason(self.entry, LEGACY_AUTHORING_SYNC_REASON)
        payload = copy.deepcopy(self.entry.scene.to_dict())
        payload["entities"][0]["tag"] = "Restored"

        with patch.object(
            self.workspace,
            "replace_entry_scene",
            wraps=self.workspace.replace_entry_scene,
        ) as replace_scene, patch.object(
            self.edit_sync,
            "clear_pending",
            wraps=self.edit_sync.clear_pending,
        ) as clear_pending, patch.object(
            self.workspace,
            "mark_dirty",
            wraps=self.workspace.mark_dirty,
        ) as mark_dirty:
            self.assertTrue(self.coordinator.restore_scene_data(self.entry.key, payload))

        payload["entities"][0]["tag"] = "Poisoned"
        self.assertEqual(self.entry.scene.find_entity("Hero")["tag"], "Restored")
        self.assertEqual(self.entry.edit_world.get_entity_by_name("Hero").tag, "Restored")
        self.assertEqual(self.entry.selected_entity_name, "Hero")
        self.assertIsNone(self.entry.pending_edit_world_sync_reason)
        self.assertTrue(self.entry.dirty)
        self.assertEqual(self.entry.edit_world_version, self.entry.edit_world.version)
        replace_scene.assert_called_once()
        clear_pending.assert_called_once_with(self.entry)
        mark_dirty.assert_called_once_with(self.entry)

        self.assertTrue(self.coordinator.restore_scene_data(self.entry.key, self.entry.scene.to_dict()))
        self.assertEqual(self.entry.scene.find_entity("Hero")["tag"], "Restored")

    def test_restore_scene_data_rejects_missing_play_and_invalid_payload(self) -> None:
        payload = copy.deepcopy(self.entry.scene.to_dict())
        self.assertFalse(self.coordinator.restore_scene_data("missing", payload))
        self.entry.is_playing = True
        self.assertFalse(self.coordinator.restore_scene_data(self.entry.key, payload))
        self.entry.is_playing = False
        invalid = copy.deepcopy(payload)
        invalid["entities"] = "invalid"
        self.assertFalse(self.coordinator.restore_scene_data(self.entry.key, invalid))

    def test_manager_does_not_define_or_name_snapshot_implementation(self) -> None:
        manager_source = inspect.getsource(scene_manager_module)
        manager_class_source = inspect.getsource(scene_manager_module.SceneManager)

        self.assertNotIn("SerializableMutationSnapshot", manager_source)
        for removed_helper in (
            "_capture_serializable_mutation",
            "_restore_serializable_mutation",
            "_commit_serializable_scene_mutation",
        ):
            self.assertNotIn(f"def {removed_helper}", manager_class_source)

    def test_manager_prepares_transaction_snapshot_via_mutation_coordinator(self) -> None:
        manager = scene_manager_module.SceneManager(create_default_registry())
        manager.load_scene(_scene_payload())
        entry = manager.resolve_entry(manager.active_scene_key)
        assert entry is not None

        with patch.object(
            manager._serializable_mutations,
            "snapshot_entry_scene_data",
            wraps=manager._serializable_mutations.snapshot_entry_scene_data,
        ) as snapshot:
            self.assertTrue(manager.begin_transaction("probe"))

        snapshot.assert_called_once_with(entry)
        self.assertFalse(hasattr(manager._change_history, "_context"))


if __name__ == "__main__":
    unittest.main()
