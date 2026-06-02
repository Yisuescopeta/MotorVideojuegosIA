"""Tests for EngineAPI exposure of scene sync: refresh_active_scene_if_stale
and register/unregister on_scene_saved callbacks."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from engine.api import EngineAPI

_SIMPLE_SCENE = {
    "name": "ApiSyncTest",
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


class EngineAPISceneSyncPublicContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.scene_dir = self.project_root / "levels"
        self.scene_dir.mkdir(parents=True, exist_ok=True)
        self.scene_path = self.scene_dir / "api_sync_scene.json"
        self.scene_path.write_text(json.dumps(_SIMPLE_SCENE, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _make_api(self) -> EngineAPI:
        api = EngineAPI(
            project_root=self.project_root.as_posix(),
        )
        self.addCleanup(api.shutdown)
        return api

    # ---- refresh_active_scene_if_stale ----

    def test_engine_api_exposes_refresh_active_scene_if_stale(self) -> None:
        api = self._make_api()
        self.assertTrue(hasattr(api, "refresh_active_scene_if_stale"))
        self.assertTrue(callable(api.refresh_active_scene_if_stale))

    def test_refresh_active_scene_if_stale_returns_action_result(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        result = api.refresh_active_scene_if_stale()

        self.assertTrue(result["success"])
        self.assertIn("world_available", result["data"])
        self.assertTrue(result["data"]["world_available"])
        self.assertIn("active_scene", result["data"])

    def test_refresh_active_scene_if_stale_detects_external_change(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        # Verify initial state
        self.assertIsNotNone(api.game.world.get_entity_by_name("Hero"))
        self.assertIsNone(api.game.world.get_entity_by_name("Enemy"))

        # Simulate external tool modifying the file
        time.sleep(0.05)
        payload = json.loads(self.scene_path.read_text(encoding="utf-8"))
        payload["entities"].append({
            "name": "Enemy",
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "components": {
                "Transform": {"enabled": True, "x": 50.0, "y": 60.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        })
        self.scene_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        result = api.refresh_active_scene_if_stale()

        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["world_available"])
        # Enemy should now exist in the refreshed world
        self.assertIsNotNone(api.game.world.get_entity_by_name("Enemy"))

    def test_refresh_active_scene_if_stale_skips_dirty_scene(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        # Make the scene dirty via a tracked authoring change
        api.create_entity("Temp", components={"Transform": {"x": 0.0, "y": 0.0}})
        self.assertTrue(api.get_active_scene_info()["dirty"])

        # External change
        time.sleep(0.05)
        payload = json.loads(self.scene_path.read_text(encoding="utf-8"))
        payload["entities"].append({
            "name": "Enemy",
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "components": {
                "Transform": {"enabled": True, "x": 99.0, "y": 99.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        })
        self.scene_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        result = api.refresh_active_scene_if_stale()

        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["world_available"])
        # Enemy should NOT appear because scene was dirty
        self.assertIsNone(api.game.world.get_entity_by_name("Enemy"))
        # Temp should still exist (dirty state preserved)
        self.assertIsNotNone(api.game.world.get_entity_by_name("Temp"))

    def test_refresh_active_scene_if_stale_noop_on_unchanged_file(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        first_result = api.refresh_active_scene_if_stale()
        self.assertTrue(first_result["success"])

        # Second call without any external change
        second_result = api.refresh_active_scene_if_stale()
        self.assertTrue(second_result["success"])
        # World should still be available
        self.assertTrue(second_result["data"]["world_available"])

    # ---- register_on_scene_saved / unregister_on_scene_saved ----

    def test_engine_api_exposes_register_on_scene_saved(self) -> None:
        api = self._make_api()
        self.assertTrue(hasattr(api, "register_on_scene_saved"))
        self.assertTrue(callable(api.register_on_scene_saved))

    def test_engine_api_exposes_unregister_on_scene_saved(self) -> None:
        api = self._make_api()
        self.assertTrue(hasattr(api, "unregister_on_scene_saved"))
        self.assertTrue(callable(api.unregister_on_scene_saved))

    def test_register_on_scene_saved_returns_action_result(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        def dummy(path: str, info: dict) -> None:
            pass

        result = api.register_on_scene_saved(dummy)
        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["registered"])
        self.assertIn("callback_id", result["data"])

    def test_unregister_on_scene_saved_returns_action_result(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        def dummy(path: str, info: dict) -> None:
            pass

        api.register_on_scene_saved(dummy)
        result = api.unregister_on_scene_saved(dummy)

        self.assertTrue(result["success"])
        self.assertIn("callback_id", result["data"])

    def test_save_scene_fires_callback_via_engine_api(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        called_with: list = []

        def on_saved(path: str, info: dict) -> None:
            called_with.append((path, dict(info)))

        result = api.register_on_scene_saved(on_saved)
        self.assertTrue(result["success"])

        # Do something to make scene dirty, then save
        api.create_entity("CallbackTest", components={"Transform": {"x": 1.0, "y": 2.0}})
        save_result = api.save_scene()
        self.assertTrue(save_result["success"])

        self.assertEqual(len(called_with), 1)
        saved_path, info = called_with[0]
        self.assertEqual(
            Path(saved_path).resolve(),
            self.scene_path.resolve(),
        )
        self.assertIn("key", info)
        self.assertEqual(info["scene_name"], "ApiSyncTest")
        self.assertEqual(info["entity_count"], 2)

    def test_unregister_stops_callback(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        called: list = []

        def on_saved(path: str, info: dict) -> None:
            called.append(path)

        api.register_on_scene_saved(on_saved)
        api.unregister_on_scene_saved(on_saved)

        api.create_entity("NoCallback", components={"Transform": {"x": 0.0, "y": 0.0}})
        api.save_scene()

        self.assertEqual(len(called), 0)

    def test_unregister_nonexistent_callback_returns_success(self) -> None:
        api = self._make_api()
        api.load_level(self.scene_path.as_posix())

        def never_registered(path: str, info: dict) -> None:
            pass

        result = api.unregister_on_scene_saved(never_registered)
        self.assertTrue(result["success"])

    def test_register_on_scene_saved_fails_without_scene_manager(self) -> None:
        api = self._make_api()
        api.scene_manager = None

        def cb(path: str, info: dict) -> None:
            pass

        result = api.register_on_scene_saved(cb)
        self.assertFalse(result["success"])
        self.assertIn("SceneManager", result["message"])

    def test_refresh_active_scene_if_stale_fails_without_scene_manager(self) -> None:
        api = self._make_api()
        api.scene_manager = None

        result = api.refresh_active_scene_if_stale()
        self.assertFalse(result["success"])
        self.assertIn("SceneManager", result["message"])


if __name__ == "__main__":
    unittest.main()
