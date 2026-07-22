from __future__ import annotations

import inspect
import unittest

from engine.levels.component_registry import create_default_registry
from engine.scenes.legacy_world_authoring_adapter import LegacyWorldAuthoringAdapter
from engine.scenes.scene_manager import SceneManager


class LegacyWorldAuthoringAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {"name": "LegacyAdapter", "entities": [], "rules": [], "feature_metadata": {}}
        )

    def test_allowlist_accepts_only_legacy_authoring_reason(self) -> None:
        adapter = self.manager._legacy_world_authoring

        self.assertTrue(adapter.mark_dirty())
        self.assertFalse(adapter.mark_dirty(reason="unknown_legacy_path"))
        self.assertEqual(adapter.ALLOWED_REASONS, frozenset({"legacy_authoring"}))

    def test_sync_pending_is_the_only_sync_entry_point_without_force(self) -> None:
        adapter = self.manager._legacy_world_authoring

        self.assertTrue(adapter.mark_dirty())
        self.assertTrue(adapter.sync_pending())
        self.assertNotIn("force", inspect.signature(adapter.sync_pending).parameters)
        self.assertNotIn("force", inspect.signature(self.manager.sync_from_edit_world).parameters)


if __name__ == "__main__":
    unittest.main()
