"""
tests/test_texture_manager.py - Tests para TextureManager.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from engine.resources.texture_manager import TextureManager


def make_texture(texture_id: int, width: int = 16, height: int = 8) -> SimpleNamespace:
    return SimpleNamespace(id=texture_id, width=width, height=height)


class TestTextureManager(unittest.TestCase):
    def test_load_caches_valid_texture(self) -> None:
        texture = make_texture(10)
        manager = TextureManager()

        with patch("engine.resources.texture_manager.rl.load_texture", return_value=texture) as load_texture:
            first = manager.load("assets/player.png", cache_key="player")
            second = manager.load("assets/player.png", cache_key="player")

        self.assertIs(first, texture)
        self.assertIs(second, texture)
        self.assertEqual(load_texture.call_count, 1)
        self.assertTrue(manager.is_loaded("player"))
        self.assertEqual(manager.get_loaded_count(), 1)

    def test_failed_load_is_not_cached_and_is_counted(self) -> None:
        failed = make_texture(0, width=0, height=0)
        recovered = make_texture(11)
        manager = TextureManager()

        with patch("engine.resources.texture_manager.rl.load_texture", side_effect=[failed, recovered]) as load_texture:
            first = manager.load("missing.png", cache_key="missing")
            second = manager.load("missing.png", cache_key="missing")

        self.assertIs(first, failed)
        self.assertIs(second, recovered)
        self.assertEqual(load_texture.call_count, 2)
        self.assertTrue(manager.is_loaded("missing"))
        self.assertEqual(manager.get_failed_count(), 1)

    def test_acquire_increments_refcount_for_cached_texture(self) -> None:
        texture = make_texture(12)
        manager = TextureManager()

        with patch("engine.resources.texture_manager.rl.load_texture", return_value=texture) as load_texture:
            first = manager.acquire("assets/player.png", cache_key="player")
            second = manager.acquire("assets/player.png", cache_key="player")

        self.assertIs(first, texture)
        self.assertIs(second, texture)
        self.assertEqual(load_texture.call_count, 1)
        self.assertEqual(manager.get_refcount("player"), 2)

    def test_release_unloads_when_refcount_reaches_zero(self) -> None:
        texture = make_texture(13)
        manager = TextureManager()

        with (
            patch("engine.resources.texture_manager.rl.load_texture", return_value=texture),
            patch("engine.resources.texture_manager.rl.unload_texture") as unload_texture,
        ):
            manager.acquire("assets/player.png", cache_key="player")
            manager.acquire("assets/player.png", cache_key="player")
            manager.release("player")
            self.assertTrue(manager.is_loaded("player"))
            self.assertEqual(manager.get_refcount("player"), 1)
            unload_texture.assert_not_called()

            manager.release("player")

        unload_texture.assert_called_once_with(texture)
        self.assertFalse(manager.is_loaded("player"))
        self.assertEqual(manager.get_refcount("player"), 0)

    def test_unload_ignores_refcount(self) -> None:
        texture = make_texture(14)
        manager = TextureManager()

        with (
            patch("engine.resources.texture_manager.rl.load_texture", return_value=texture),
            patch("engine.resources.texture_manager.rl.unload_texture") as unload_texture,
        ):
            manager.acquire("assets/player.png", cache_key="player")
            manager.acquire("assets/player.png", cache_key="player")
            manager.unload("player")

        unload_texture.assert_called_once_with(texture)
        self.assertFalse(manager.is_loaded("player"))

    def test_unload_all_clears_cache_and_metrics(self) -> None:
        texture_a = make_texture(15, width=10, height=10)
        texture_b = make_texture(16, width=20, height=5)
        manager = TextureManager()

        with (
            patch("engine.resources.texture_manager.rl.load_texture", side_effect=[texture_a, texture_b]),
            patch("engine.resources.texture_manager.rl.unload_texture") as unload_texture,
        ):
            manager.load("a.png", cache_key="a")
            manager.acquire("b.png", cache_key="b")
            self.assertEqual(manager.get_loaded_count(), 2)
            self.assertEqual(manager.get_approx_memory(), 800)

            manager.unload_all()

        self.assertEqual(unload_texture.call_count, 2)
        self.assertEqual(manager.get_loaded_count(), 0)
        self.assertEqual(manager.get_approx_memory(), 0)
        self.assertEqual(manager.get_refcount("b"), 0)

    def test_metrics_report_loaded_failed_and_memory(self) -> None:
        failed = make_texture(0, width=0, height=0)
        texture = make_texture(17, width=7, height=3)
        manager = TextureManager()

        with patch("engine.resources.texture_manager.rl.load_texture", side_effect=[failed, texture]):
            manager.load("missing.png", cache_key="missing")
            manager.load("ok.png", cache_key="ok")

        self.assertEqual(
            manager.get_metrics(),
            {
                "loaded_count": 1,
                "failed_count": 1,
                "approx_memory": 84,
            },
        )


if __name__ == "__main__":
    unittest.main()
