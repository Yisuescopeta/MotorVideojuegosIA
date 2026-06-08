from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from engine.resources.texture_resolution_cache import TextureResolutionCache


class FakeTextureManager:
    def __init__(self) -> None:
        self.loaded: set[str] = set()
        self.load_calls: list[tuple[str, str]] = []

    def load(self, path: str, cache_key: str | None = None) -> SimpleNamespace:
        key = str(cache_key or path)
        self.loaded.add(key)
        self.load_calls.append((path, key))
        return SimpleNamespace(id=len(self.load_calls), width=16, height=16)

    def is_loaded(self, cache_key: str) -> bool:
        return cache_key in self.loaded


class TextureResolutionCacheTests(unittest.TestCase):
    def test_catalog_and_path_are_resolved_once_while_sync_runs_per_use(self) -> None:
        manager = FakeTextureManager()
        resolver = Mock()
        resolver.resolve_entry.return_value = {
            "absolute_path": "C:/project/assets/hero.png",
            "guid": "guid_hero",
            "path": "assets/hero.png",
        }
        project_service = Mock()
        sync = Mock()
        cache = TextureResolutionCache(
            manager,  # type: ignore[arg-type]
            project_service=project_service,
            asset_resolver=resolver,
        )

        first = cache.resolve({"path": "assets/hero.png"}, "assets/hero.png", sync)
        second = cache.resolve(
            {"guid": "guid_hero", "path": "assets/hero.png"},
            "assets/hero.png",
            sync,
        )

        self.assertIs(first, second)
        resolver.resolve_entry.assert_called_once()
        project_service.resolve_path.assert_not_called()
        self.assertEqual(manager.load_calls, [("C:/project/assets/hero.png", "guid_hero")])
        self.assertEqual(sync.call_count, 2)
        sync.assert_called_with({"guid": "guid_hero", "path": "assets/hero.png"})

    def test_fallback_resolution_is_cached_and_clear_invalidates_it(self) -> None:
        manager = FakeTextureManager()
        resolver = Mock()
        resolver.resolve_entry.return_value = None
        project_service = Mock()
        project_service.resolve_path.return_value = Path("C:/project/assets/legacy.png")
        cache = TextureResolutionCache(
            manager,  # type: ignore[arg-type]
            project_service=project_service,
            asset_resolver=resolver,
        )

        cache.resolve({"path": "assets/legacy.png"}, "assets/legacy.png")
        cache.resolve({"path": "assets/legacy.png"}, "assets/legacy.png")
        self.assertEqual(project_service.resolve_path.call_count, 1)

        cache.clear()
        cache.resolve({"path": "assets/legacy.png"}, "assets/legacy.png")
        self.assertEqual(project_service.resolve_path.call_count, 2)

    def test_cached_texture_reloads_when_texture_manager_no_longer_owns_it(self) -> None:
        manager = FakeTextureManager()
        resolver = Mock()
        resolver.resolve_entry.return_value = {
            "absolute_path": "C:/project/assets/hero.png",
            "guid": "guid_hero",
            "path": "assets/hero.png",
        }
        cache = TextureResolutionCache(manager, asset_resolver=resolver)  # type: ignore[arg-type]

        first = cache.resolve({"guid": "guid_hero", "path": "assets/hero.png"})
        manager.loaded.clear()
        second = cache.resolve({"guid": "guid_hero", "path": "assets/hero.png"})

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(manager.load_calls), 2)
        resolver.resolve_entry.assert_called_once()

    def test_invalid_texture_does_not_repeat_resolution_or_load(self) -> None:
        manager = FakeTextureManager()
        manager.load = Mock(return_value=SimpleNamespace(id=0, width=0, height=0))  # type: ignore[method-assign]
        resolver = Mock()
        resolver.resolve_entry.return_value = None
        project_service = Mock()
        project_service.resolve_path.return_value = Path("C:/project/assets/missing.png")
        cache = TextureResolutionCache(
            manager,  # type: ignore[arg-type]
            project_service=project_service,
            asset_resolver=resolver,
        )

        cache.resolve({"path": "assets/missing.png"}, "assets/missing.png")
        cache.resolve({"path": "assets/missing.png"}, "assets/missing.png")

        resolver.resolve_entry.assert_called_once()
        project_service.resolve_path.assert_called_once()
        manager.load.assert_called_once()


if __name__ == "__main__":
    unittest.main()
