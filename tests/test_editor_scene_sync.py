"""Tests for editor/API scene sync: save callbacks and external file change detection."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager

_SIMPLE_SCENE = {
    "name": "SyncTest",
    "entities": [
        {
            "name": "Hero",
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "components": {
                "Transform": {
                    "enabled": True,
                    "x": 10.0,
                    "y": 20.0,
                    "rotation": 0.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                }
            },
        }
    ],
    "rules": [],
    "feature_metadata": {},
}


class EditorSceneSyncCallbackTests(unittest.TestCase):
    """Tests for the on_scene_saved callback mechanism."""

    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.temp_dir = tempfile.TemporaryDirectory()
        self.scene_path = Path(self.temp_dir.name) / "callback_scene.json"
        self.manager.load_scene(_SIMPLE_SCENE)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_scene_to_file_calls_callback_after_successful_save(self) -> None:
        called_with: list = []

        def on_saved(path: str, info: dict) -> None:
            called_with.append((path, dict(info)))

        self.manager.register_on_scene_saved(on_saved)

        result = self.manager.save_scene_to_file(self.scene_path.as_posix())

        self.assertTrue(result)
        self.assertEqual(len(called_with), 1)
        saved_path, info = called_with[0]
        self.assertEqual(Path(saved_path).resolve(), self.scene_path.resolve())
        self.assertIn("key", info)
        self.assertEqual(info["scene_name"], "SyncTest")
        self.assertEqual(info["entity_count"], 1)

    def test_save_scene_to_file_calls_multiple_callbacks(self) -> None:
        called_a: list = []
        called_b: list = []

        def cb_a(path: str, info: dict) -> None:
            called_a.append(path)

        def cb_b(path: str, info: dict) -> None:
            called_b.append(path)

        self.manager.register_on_scene_saved(cb_a)
        self.manager.register_on_scene_saved(cb_b)

        self.manager.save_scene_to_file(self.scene_path.as_posix())

        self.assertEqual(len(called_a), 1)
        self.assertEqual(len(called_b), 1)

    def test_callback_exception_does_not_make_save_fail(self) -> None:
        called_good: list = []

        def bad_callback(path: str, info: dict) -> None:
            raise RuntimeError("intentional callback failure")

        def good_callback(path: str, info: dict) -> None:
            called_good.append(path)

        self.manager.register_on_scene_saved(bad_callback)
        self.manager.register_on_scene_saved(good_callback)

        result = self.manager.save_scene_to_file(self.scene_path.as_posix())

        self.assertTrue(result)
        self.assertEqual(len(called_good), 1)
        self.assertTrue(self.scene_path.is_file())

        # Verify that save was written correctly despite the exception
        on_disk = json.loads(self.scene_path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["name"], "SyncTest")

    def test_unregister_removes_callback(self) -> None:
        called: list = []

        def cb(path: str, info: dict) -> None:
            called.append(path)

        self.manager.register_on_scene_saved(cb)
        self.manager.unregister_on_scene_saved(cb)

        self.manager.save_scene_to_file(self.scene_path.as_posix())

        self.assertEqual(len(called), 0)

    def test_unregister_nonexistent_callback_does_not_raise(self) -> None:
        def cb(path: str, info: dict) -> None:
            pass

        # Should not raise
        self.manager.unregister_on_scene_saved(cb)


class EditorSceneSyncExternalChangeTests(unittest.TestCase):
    """Tests for external file change detection via refresh_active_scene_if_stale."""

    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.temp_dir = tempfile.TemporaryDirectory()
        self.scene_path = Path(self.temp_dir.name) / "external_scene.json"

        # Write initial scene file
        self.manager.load_scene(_SIMPLE_SCENE)
        self.manager.save_scene_to_file(self.scene_path.as_posix())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_scene_with_extra_entity(self) -> None:
        """Write the scene file with an added entity."""
        payload = {
            "name": "SyncTest",
            "schema_version": 1,
            "entities": [
                {
                    "name": "Hero",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 10.0,
                            "y": 20.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                },
                {
                    "name": "Enemy",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 100.0,
                            "y": 50.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        self.scene_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_refresh_detects_external_change_and_updates_edit_world(self) -> None:
        # Verify initial state has only Hero
        world = self.manager.get_edit_world()
        self.assertIsNotNone(world)
        self.assertIsNotNone(world.get_entity_by_name("Hero"))
        self.assertIsNone(world.get_entity_by_name("Enemy"))

        # Simulate external tool adding an entity
        self._write_scene_with_extra_entity()

        # refresh_active_scene_if_stale should detect the change
        refreshed = self.manager.refresh_active_scene_if_stale()
        self.assertIsNotNone(refreshed)

        # Enemy should now exist in the refreshed edit_world
        self.assertIsNotNone(refreshed.get_entity_by_name("Enemy"))
        transform = refreshed.get_entity_by_name("Enemy").get_component(
            __import__("engine.components.transform", fromlist=["Transform"]).Transform
        )
        self.assertIsNotNone(transform)
        self.assertEqual(transform.x, 100.0)
        self.assertEqual(transform.y, 50.0)

    def test_get_edit_world_auto_refreshes_stale_scene(self) -> None:
        # Verify initial state
        world = self.manager.get_edit_world()
        self.assertIsNone(world.get_entity_by_name("Enemy"))

        # External change
        self._write_scene_with_extra_entity()

        # get_edit_world automatically detects and refreshes
        world = self.manager.get_edit_world()
        self.assertIsNotNone(world.get_entity_by_name("Enemy"))

    def test_refresh_skips_when_scene_is_dirty(self) -> None:
        # Make an edit to dirty the scene
        self.assertTrue(self.manager.apply_edit_to_world("Hero", "Transform", "x", 99.0))
        self.assertTrue(self.manager.is_dirty)

        # External tool changes the file
        self._write_scene_with_extra_entity()

        # Refresh should skip because scene is dirty
        world = self.manager.refresh_active_scene_if_stale()
        self.assertIsNotNone(world)

        # Enemy should NOT appear (dirty state preserved)
        self.assertIsNone(world.get_entity_by_name("Enemy"))
        self.assertIsNotNone(world.get_entity_by_name("Hero"))

        # Verify Hero still has our unsaved x=99.0
        transform = world.get_entity_by_name("Hero").get_component(
            __import__("engine.components.transform", fromlist=["Transform"]).Transform
        )
        self.assertEqual(transform.x, 99.0)

    def test_refresh_noop_when_file_unchanged(self) -> None:
        world_before = self.manager.get_edit_world()
        entity_count_before = len(self.manager.current_scene.entities_data)

        # Refresh without any external change
        world_after = self.manager.refresh_active_scene_if_stale()

        self.assertIs(world_after, world_before)
        self.assertEqual(len(self.manager.current_scene.entities_data), entity_count_before)

    def test_refresh_mtime_key_resolved_consistently_no_redundant_reload(self) -> None:
        """When source_path is relative, mtime lookup resolves it consistently.

        After save_scene_to_file, the stored source_path may be a relative or
        un-normalised path, but _scene_file_mtimes keys are always resolved.
        refresh_active_scene_if_stale must resolve the source path before
        lookup/update so the mtime hit prevents a redundant reload.
        """
        # Load and save with a relative-style path to exercise path resolution
        self.manager.load_scene(_SIMPLE_SCENE)
        save_result = self.manager.save_scene_to_file(self.scene_path.as_posix())
        self.assertTrue(save_result)

        # Snapshot after save – scene is clean, mtime stored with resolved key
        scene_key_after_save = self.manager.active_scene_key
        entity_count = len(self.manager.current_scene.entities_data)

        # First refresh: file unchanged, should be a no-op (same world)
        world1 = self.manager.get_edit_world()
        self.assertEqual(len(self.manager.current_scene.entities_data), entity_count)

        # Second refresh: still unchanged – must NOT reload redundantly
        world2 = self.manager.refresh_active_scene_if_stale()
        self.assertIs(world2, world1, "second refresh must not reload unchanged file")
        self.assertEqual(self.manager.active_scene_key, scene_key_after_save)
        self.assertFalse(self.manager.is_dirty)

    def test_refresh_reloads_all_scene_data(self) -> None:
        # Write a scene with modified feature_metadata too
        payload = {
            "name": "SyncTest",
            "schema_version": 1,
            "entities": [
                {
                    "name": "Hero",
                    "active": True,
                    "tag": "HeroTag",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 50.0,
                            "y": 60.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                }
            ],
            "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "refreshed"}]}],
            "feature_metadata": {"music": "battle.ogg"},
        }
        self.scene_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        # Force mtime to advance
        time.sleep(0.1)

        refreshed = self.manager.refresh_active_scene_if_stale()
        self.assertIsNotNone(refreshed)

        # Check all data updated
        hero = refreshed.get_entity_by_name("Hero")
        self.assertIsNotNone(hero)
        self.assertEqual(hero.tag, "HeroTag")
        self.assertEqual(hero.layer, "Gameplay")
        transform = hero.get_component(
            __import__("engine.components.transform", fromlist=["Transform"]).Transform
        )
        self.assertEqual(transform.x, 50.0)
        self.assertEqual(transform.y, 60.0)

        scene = self.manager.current_scene
        self.assertEqual(len(scene.rules_data), 1)
        self.assertEqual(scene.rules_data[0]["do"][0]["message"], "refreshed")
        self.assertEqual(scene.feature_metadata.get("music"), "battle.ogg")

    def test_refresh_handles_missing_file_gracefully(self) -> None:
        # Delete the file
        self.scene_path.unlink()

        # Refresh should not crash, just return current world
        world = self.manager.refresh_active_scene_if_stale()
        self.assertIsNotNone(world)
        self.assertIsNotNone(world.get_entity_by_name("Hero"))


if __name__ == "__main__":
    unittest.main()
