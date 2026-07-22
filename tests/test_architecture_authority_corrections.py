from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.components.transform import Transform
from engine.editor.editor_preview_coordinator import EditorPreviewCoordinator
from engine.levels.component_registry import create_default_registry
from engine.scenes.preview_leases import PreviewCancelReason
from engine.scenes.result import CommandError, CommandErrorCode, Err, Ok
from engine.scenes.scene_manager import SceneManager


class ArchitectureAuthorityCorrectionTests(unittest.TestCase):
    def _manager(self) -> SceneManager:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "Authority",
                "entities": [
                    {
                        "id": "hero-id",
                        "name": "Hero",
                        "components": {"Transform": {"x": 1.0, "y": 2.0}},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        return manager

    def test_save_blocks_pending_legacy_without_promoting_world(self) -> None:
        manager = self._manager()
        entry = manager.resolve_entry(None)
        assert entry is not None
        before = entry.scene.to_snapshot_dict()
        world_entity = entry.edit_world.get_entity_by_serialized_id("hero-id")
        assert world_entity is not None
        transform = world_entity.get_component(Transform)
        assert transform is not None
        transform.x = 72.0
        manager.mark_edit_world_dirty(reason="legacy_authoring")

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "authority.json"
            with patch.object(manager._edit_sync, "flush_pending", wraps=manager._edit_sync.flush_pending) as flush:
                result = manager.save_scene_to_file(target.as_posix())

        self.assertFalse(result)
        flush.assert_not_called()
        self.assertEqual(entry.scene.to_snapshot_dict(), before)
        self.assertFalse(target.exists())

    def test_play_projection_does_not_copy_editor_selection(self) -> None:
        manager = self._manager()
        entry = manager.resolve_entry(None)
        assert entry is not None
        entry.edit_world.selected_entity_name = "Hero"

        runtime = manager.enter_play()

        self.assertIsNotNone(runtime)
        assert runtime is not None
        self.assertIsNone(runtime.selected_entity_name)
        self.assertIsNot(runtime, entry.edit_world)

    def test_play_projection_excludes_editor_only_state_and_shares_no_mutables(self) -> None:
        manager = self._manager()
        entry = manager.resolve_entry(None)
        assert entry is not None
        entry.edit_world.editor_cache = {"hover": "hero-id"}
        edit_entity = entry.edit_world.get_entity_by_serialized_id("hero-id")
        assert edit_entity is not None
        edit_transform = edit_entity.get_component(Transform)
        assert edit_transform is not None

        runtime = manager.enter_play()

        self.assertIsNotNone(runtime)
        assert runtime is not None
        self.assertFalse(hasattr(runtime, "editor_cache"))
        runtime_entity = runtime.get_entity_by_serialized_id("hero-id")
        assert runtime_entity is not None
        self.assertIsNot(runtime_entity.get_component(Transform), edit_transform)

    def test_preview_cancel_isolated_by_open_document_id(self) -> None:
        manager = self._manager()
        entry_a = manager.resolve_entry(None)
        assert entry_a is not None
        manager.load_scene(
            {"name": "Other", "entities": [], "rules": [], "feature_metadata": {}},
            activate=False,
        )
        entry_b = next(
            entry
            for item in manager.list_open_scenes()
            if item["key"] != entry_a.key
            for entry in [manager.resolve_entry(item["key"])]
            if entry is not None
        )
        coordinator = EditorPreviewCoordinator(manager.create_preview_lease_registry())
        first = coordinator.acquire(entry_a, kind="test", label="first")
        self.assertTrue(first.success)
        self.assertEqual(coordinator.active_for(entry_a.open_document_id), (first.lease,))
        self.assertEqual(coordinator.active_for(entry_b.open_document_id), ())
        self.assertIsInstance(
            coordinator.cancel_all(entry_b.open_document_id, PreviewCancelReason.SCENE_SWITCH),
            Ok,
        )
        self.assertEqual(coordinator.active_for(entry_a.open_document_id), (first.lease,))
        self.assertIsInstance(coordinator.cancel_all(entry_a.open_document_id, PreviewCancelReason.SAVE), Ok)

    def test_failed_preview_cancel_blocks_save_and_keeps_lease_diagnostic(self) -> None:
        manager = self._manager()
        entry = manager.resolve_entry(None)
        assert entry is not None
        coordinator = EditorPreviewCoordinator(manager.create_preview_lease_registry())
        manager.set_preview_coordinator(coordinator)
        acquired = coordinator.acquire(entry, kind="test", label="uncancellable")
        self.assertTrue(acquired.success)
        assert acquired.lease is not None
        coordinator.bind(
            acquired.lease.lease_id,
            lambda _reason: Err(
                CommandError(CommandErrorCode.PREVIEW_CANCEL_FAILED, "synthetic cancellation failure")
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertFalse(manager.save_scene_to_file(str(Path(temp_dir) / "blocked.json")))
        self.assertEqual(coordinator.active_for(entry.open_document_id), (acquired.lease,))
        self.assertEqual(manager._edit_sync.last_integrity_report.code.value, "PREVIEW_CANCEL_FAILED")
        self.assertIsInstance(coordinator.release(acquired.lease.lease_id), Ok)


if __name__ == "__main__":
    unittest.main()
