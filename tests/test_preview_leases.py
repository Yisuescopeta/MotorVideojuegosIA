from __future__ import annotations

import unittest

from engine.levels.component_registry import create_default_registry
from engine.scenes.preview_leases import PreviewLeaseCode, PreviewLeaseRegistry
from engine.scenes.projection_integrity import AuthoringProjectionFingerprintService
from engine.scenes.scene_manager import SceneManager


class _History:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_snapshot_change(self, *, label, undo, redo) -> None:
        self.records.append({"label": label, "undo": undo, "redo": redo})

    def record_differential_change(self, *, label, undo, redo) -> None:
        raise AssertionError("preview commit must use one snapshot history entry")


class PreviewLeaseRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {
                "name": "PreviewLease",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.entry = self.manager.resolve_entry(None)
        assert self.entry is not None
        self.history = _History()
        self.registry = PreviewLeaseRegistry(
            AuthoringProjectionFingerprintService(self.manager._projection.create_world),
            history=self.history,
            restore_snapshot=lambda key, snapshot: self.manager._workspace.replace_entry_scene(
                self.manager.resolve_entry(key), snapshot
            )
            is not None,
        )

    def test_acquire_commit_records_one_history_entry(self) -> None:
        acquired = self.registry.acquire(self.entry, kind="collider", label="Collider preview")
        assert acquired.lease is not None
        self.assertTrue(acquired.success)

        def apply_preview() -> bool:
            payload = self.entry.scene.to_dict()
            payload["feature_metadata"] = {"preview": {"enabled": True}}
            self.manager._workspace.replace_entry_scene(self.entry, payload)
            return True

        committed = self.registry.commit(
            acquired.lease.lease_id,
            self.entry,
            apply_preview=apply_preview,
        )

        self.assertTrue(committed.success)
        self.assertEqual(committed.code, PreviewLeaseCode.COMMITTED)
        self.assertTrue(committed.history_recorded)
        self.assertEqual(len(self.history.records), 1)
        self.assertIsNone(self.registry.active_for_scene(self.entry.key))

    def test_cancel_does_not_write_scene_or_history(self) -> None:
        before = self.entry.scene.to_dict()
        acquired = self.registry.acquire(self.entry, kind="layout", label="Layout preview")
        assert acquired.lease is not None

        cancelled = self.registry.cancel(acquired.lease.lease_id)

        self.assertTrue(cancelled.success)
        self.assertEqual(cancelled.code, PreviewLeaseCode.CANCELLED)
        self.assertEqual(self.entry.scene.to_dict(), before)
        self.assertEqual(self.history.records, [])

    def test_second_lease_for_same_scene_is_rejected(self) -> None:
        first = self.registry.acquire(self.entry, kind="one", label="One")
        second = self.registry.acquire(self.entry, kind="two", label="Two")

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertEqual(second.code, PreviewLeaseCode.ACTIVE_LEASE)

    def test_commit_rejects_stale_scene_revision(self) -> None:
        acquired = self.registry.acquire(self.entry, kind="collider", label="Collider preview")
        assert acquired.lease is not None
        self.manager.create_entity("AddedOutsidePreview")

        committed = self.registry.commit(
            acquired.lease.lease_id,
            self.entry,
            apply_preview=lambda: True,
        )

        self.assertFalse(committed.success)
        self.assertEqual(committed.code, PreviewLeaseCode.CONFLICT)
        self.assertIsNotNone(self.registry.active_for_scene(self.entry.key))


if __name__ == "__main__":
    unittest.main()
