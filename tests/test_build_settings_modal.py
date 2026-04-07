import unittest

from engine.editor.build_settings_modal import BuildSettingsModal


class BuildSettingsModalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.modal = BuildSettingsModal()
        self.scene_entries = [
            {"name": "Main Scene", "path": "levels/main_scene.json"},
            {"name": "Alpha", "path": "levels/alpha.json"},
            {"name": "Beta", "path": "levels/beta.json"},
        ]
        self.settings = {
            "product_name": "Project",
            "company_name": "Studio",
            "startup_scene": "levels/alpha.json",
            "scenes_in_build": ["levels/alpha.json", "levels/main_scene.json"],
            "target_platform": "windows_desktop",
            "development_build": False,
            "include_logs": False,
            "include_profiler": False,
            "output_name": "project",
        }
        self.modal.open(self.settings, self.scene_entries)

    def test_scene_order_is_preserved_and_can_be_moved(self) -> None:
        self.assertEqual(self.modal.scenes_in_build, ["levels/alpha.json", "levels/main_scene.json"])

        self.modal.move_scene("levels/main_scene.json", -1)

        self.assertEqual(self.modal.scenes_in_build, ["levels/main_scene.json", "levels/alpha.json"])

    def test_removing_startup_scene_promotes_first_remaining_scene(self) -> None:
        self.modal.toggle_scene_in_build("levels/alpha.json")

        self.assertEqual(self.modal.scenes_in_build, ["levels/main_scene.json"])
        self.assertEqual(self.modal.startup_scene, "levels/main_scene.json")

    def test_setting_profiler_enables_development_build(self) -> None:
        self.modal._toggle_profiler()

        self.assertTrue(self.modal.development_build)
        self.assertTrue(self.modal.include_profiler)

    def test_build_settings_payload_reflects_current_modal_state(self) -> None:
        self.modal.product_name = "Editor Project"
        self.modal.company_name = "Editor Studio"
        self.modal.output_name = "editor_project"
        self.modal.toggle_scene_in_build("levels/beta.json")
        self.modal.set_startup_scene("levels/beta.json")

        payload = self.modal.build_settings_payload()

        self.assertEqual(payload["product_name"], "Editor Project")
        self.assertEqual(payload["company_name"], "Editor Studio")
        self.assertEqual(payload["startup_scene"], "levels/beta.json")
        self.assertEqual(
            payload["scenes_in_build"],
            ["levels/alpha.json", "levels/main_scene.json", "levels/beta.json"],
        )


if __name__ == "__main__":
    unittest.main()
