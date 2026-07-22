from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.legacy_world_authoring_adapter import LegacyWorldAuthoringAdapter
from engine.scenes.result import Err, Ok
from engine.scenes.scene_manager import SceneManager


class LegacyWorldAuthoringAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {
                "name": "LegacyAdapter",
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

    def test_allowlist_accepts_only_legacy_authoring_reason(self) -> None:
        adapter = self.manager._legacy_world_authoring

        self.assertTrue(adapter.mark_dirty())
        self.assertFalse(adapter.mark_dirty(reason="unknown_legacy_path"))
        self.assertEqual(adapter.ALLOWED_REASONS, frozenset({"legacy_authoring"}))

    def test_sync_pending_is_the_only_sync_entry_point_without_force(self) -> None:
        adapter = self.manager.legacy_authoring_adapter

        self.assertTrue(adapter.mark_dirty())
        self.assertFalse(adapter.sync_pending())
        self.assertNotIn("force", inspect.signature(adapter.sync_pending).parameters)
        self.assertNotIn("force", inspect.signature(self.manager.sync_from_edit_world).parameters)

    def test_explicit_scoped_lease_commits_by_open_document_id(self) -> None:
        adapter = self.manager.legacy_authoring_adapter
        entry = self.manager.resolve_entry(None)
        assert entry is not None
        opened = adapter.open_lease(
            entry,
            consumer="legacy-test",
            owner="test-owner",
            mutation_scope=frozenset({"Transform"}),
        )
        self.assertIsInstance(opened, Ok)
        assert isinstance(opened, Ok)
        entity = entry.edit_world.get_entity_by_serialized_id("hero-id")
        assert entity is not None
        transform = entity.get_component(Transform)
        assert transform is not None
        transform.x = 72.0

        committed = adapter.commit(opened.value)

        self.assertIsInstance(committed, Ok)
        self.assertFalse(adapter.has_open_lease(entry))
        self.assertEqual(adapter.consumer_metrics["legacy-test"], 1)
        self.assertEqual(entry.scene.find_entity_view("hero-id").get("components").get("Transform").get("x"), 72.0)

    def test_scope_violation_rolls_back_and_closes_lease(self) -> None:
        adapter = self.manager.legacy_authoring_adapter
        entry = self.manager.resolve_entry(None)
        assert entry is not None
        opened = adapter.open_lease(
            entry,
            consumer="legacy-test",
            owner="test-owner",
            mutation_scope=frozenset({"Transform"}),
        )
        self.assertIsInstance(opened, Ok)
        assert isinstance(opened, Ok)
        before = entry.scene.to_snapshot_dict()
        entry.edit_world.feature_metadata["unexpected"] = True

        result = adapter.commit(opened.value)

        self.assertIsInstance(result, Err)
        self.assertEqual(entry.scene.to_snapshot_dict(), before)
        self.assertFalse(adapter.has_open_lease(entry))

    def test_protected_boundaries_block_open_lease_without_adapter_commit(self) -> None:
        adapter = self.manager.legacy_authoring_adapter
        entry = self.manager.resolve_entry(None)
        assert entry is not None
        opened = adapter.open_lease(
            entry,
            consumer="legacy-test",
            owner="test-owner",
            mutation_scope=frozenset({"Transform"}),
        )
        self.assertIsInstance(opened, Ok)
        with patch.object(adapter, "commit", wraps=adapter.commit) as commit:
            self.assertFalse(self.manager.enter_play())
            with self.subTest(action="save"):
                self.assertFalse(self.manager.save_scene_to_file("legacy-blocked.json"))
            with self.subTest(action="switch"):
                other = self.manager.load_scene(
                    {"name": "Other", "entities": [], "rules": [], "feature_metadata": {}},
                    activate=False,
                )
                self.assertIsNotNone(other)
                self.assertFalse(self.manager.activate_scene(self.manager.list_open_scenes()[-1]["key"]))
            commit.assert_not_called()
        assert isinstance(opened, Ok)
        self.assertIsInstance(adapter.cancel(opened.value), Ok)
        self.assertFalse(adapter.has_open_lease(entry))


if __name__ == "__main__":
    unittest.main()
