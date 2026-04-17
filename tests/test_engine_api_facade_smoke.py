import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI


class EngineAPIFacadeSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        self.scene_path = self.project_root / "levels" / "platformer_test_scene.json"
        self.scene_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_path.write_text(
            (Path(__file__).resolve().parents[1] / "levels" / "platformer_test_scene.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _make_api(self) -> EngineAPI:
        api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.addCleanup(api.shutdown)
        return api

    def test_instance_exposes_delegated_public_methods(self) -> None:
        api = self._make_api()
        expected = (
            "load_level",
            "create_entity",
            "edit_component",
            "get_entity",
            "play",
            "step",
            "get_status",
            "create_scene",
            "get_active_scene",
            "set_next_scene",
            "get_project_manifest",
            "list_project_assets",
            "get_profiler_report",
            "create_ui_image",
            "get_ui_layout",
        )

        names = dir(api)
        for method_name in expected:
            self.assertIn(method_name, names)
            self.assertTrue(callable(getattr(api, method_name)))

    def test_facade_smoke_across_main_domains(self) -> None:
        api = self._make_api()
        api.load_level("levels/platformer_test_scene.json")

        create_result = api.create_entity("FacadeSmoke")
        self.assertTrue(create_result["success"])
        edit_result = api.edit_component("FacadeSmoke", "Transform", "x", 42.0)
        self.assertTrue(edit_result["success"])
        self.assertEqual(api.get_entity("FacadeSmoke")["components"]["Transform"]["x"], 42.0)

        self.assertTrue(api.set_next_scene("levels/platformer_test_scene.json")["success"])
        self.assertEqual(api.get_scene_connections()["next_scene"], "levels/platformer_test_scene.json")
        self.assertEqual(api.get_active_scene()["name"], "Platformer Test Scene")

        api.play()
        api.step(1)
        status = api.get_status()
        self.assertGreater(status["entity_count"], 0)
        api.stop()

        self.assertIsInstance(api.get_project_manifest(), dict)
        self.assertIsInstance(api.list_project_assets(), list)
        self.assertIsInstance(api.get_profiler_report(), dict)
        self.assertTrue(api.create_canvas("CanvasRoot")["success"])
        self.assertTrue(api.create_ui_image("Logo", "CanvasRoot", {"path": "assets/ui/logo.png"})["success"])
        self.assertEqual(api.get_ui_layout("Missing"), {})

    def test_facade_create_scene_remains_compatible(self) -> None:
        api = self._make_api()

        result = api.create_scene("Facade Scene")

        self.assertTrue(result["success"])
        self.assertEqual(api.get_active_scene()["name"], "Facade Scene")


if __name__ == "__main__":
    unittest.main()
