"""tests/test_resource_uid.py — Tests for ResourceUIDCache."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from engine.resources.resource_uid import ResourceUIDCache


class TestResourceUID(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_path = str(Path(self._tmp.name) / "resource_uid_cache.json")

    def tearDown(self):
        self._tmp.cleanup()

    def _fresh_cache(self) -> ResourceUIDCache:
        return ResourceUIDCache(cache_path=self.cache_path)

    def test_create_uid(self):
        cache = self._fresh_cache()
        uid = cache.get_or_create_uid("assets/textures/player.png")
        self.assertIsNotNone(uid)
        self.assertTrue(uid.startswith("uid://"))
        self.assertEqual(len(uid), len("uid://") + 12)

    def test_uid_resolves_to_path(self):
        cache = self._fresh_cache()
        uid = cache.get_or_create_uid("assets/hero.tileset")
        resolved = cache.resolve_uid(uid)
        self.assertEqual(resolved, "assets/hero.tileset")

    def test_same_path_gets_same_uid(self):
        cache = self._fresh_cache()
        uid1 = cache.get_or_create_uid("assets/hero.tileset")
        uid2 = cache.get_or_create_uid("assets/hero.tileset")
        self.assertEqual(uid1, uid2)

    def test_different_paths_get_different_uids(self):
        cache = self._fresh_cache()
        uid1 = cache.get_or_create_uid("assets/a.png")
        uid2 = cache.get_or_create_uid("assets/b.png")
        self.assertNotEqual(uid1, uid2)

    def test_persistence_across_sessions(self):
        cache1 = self._fresh_cache()
        uid = cache1.get_or_create_uid("assets/persist.png")

        cache2 = ResourceUIDCache(cache_path=self.cache_path)
        self.assertTrue(cache2.has_uid(uid))
        self.assertEqual(cache2.resolve_uid(uid), "assets/persist.png")
        self.assertEqual(cache2.get_or_create_uid("assets/persist.png"), uid)

    def test_remove_path(self):
        cache = self._fresh_cache()
        uid = cache.get_or_create_uid("assets/temp.png")
        cache.remove_path("assets/temp.png")
        self.assertFalse(cache.has_uid(uid))
        self.assertIsNone(cache.resolve_uid(uid))

    def test_clear(self):
        cache = self._fresh_cache()
        cache.get_or_create_uid("assets/a.png")
        cache.get_or_create_uid("assets/b.png")
        cache.clear()
        self.assertIsNone(cache.get_path("uid://nonexistent_uid"))

    def test_nonexistent_uid_returns_none(self):
        cache = self._fresh_cache()
        self.assertIsNone(cache.resolve_uid("uid://deadbeef1234"))
        self.assertFalse(cache.has_uid("uid://deadbeef1234"))

    def test_get_path_alias(self):
        cache = self._fresh_cache()
        uid = cache.get_or_create_uid("assets/x.png")
        self.assertEqual(cache.get_path(uid), "assets/x.png")


if __name__ == "__main__":
    unittest.main()
