import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.project.project_service import ProjectService


class UIPresetAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.scene_path = self.root / "levels" / "ui_presets.json"
        self.scene_path.write_text(
            json.dumps({"name": "UIPresets", "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
            encoding="utf-8",
        )
        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level("levels/ui_presets.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_list_ui_presets_returns_expected_metadata(self) -> None:
        result = self.api.list_ui_presets()

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["count"], 5)
        self.assertEqual(
            [preset["id"] for preset in result["data"]["presets"]],
            ["hud-platformer", "main-menu", "pause-menu", "game-over", "dialog-box"],
        )

    def test_create_main_menu_preset_builds_canvas_title_and_buttons(self) -> None:
        result = self.api.create_ui_preset("main-menu")

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["root_entity"], "MainMenuCanvas")

        root = self.api.get_entity("MainMenuCanvas")
        title = self.api.get_entity("MainMenuTitle")
        play = self.api.get_entity("MainMenuPlayButton")
        options = self.api.get_entity("MainMenuOptionsButton")
        quit_button = self.api.get_entity("MainMenuQuitButton")

        self.assertIn("Canvas", root["components"])
        self.assertEqual(title["components"]["UIText"]["text"], "OpenGame")
        self.assertEqual(play["components"]["UIButton"]["on_click"]["name"], "ui.main_menu.play")
        self.assertEqual(options["components"]["UIButton"]["on_click"]["name"], "ui.main_menu.options")
        self.assertEqual(quit_button["components"]["UIButton"]["on_click"]["name"], "ui.main_menu.quit")

    def test_create_hud_platformer_builds_expected_nodes(self) -> None:
        result = self.api.create_ui_preset("hud-platformer")

        self.assertTrue(result["success"])
        self.assertTrue(self.api.get_entity("HUDPlatformerCanvas")["active"])
        self.assertEqual(self.api.get_entity("HUDPlatformerScoreText")["components"]["UIText"]["text"], "Score: 0000")
        self.assertEqual(self.api.get_entity("HUDPlatformerLivesText")["components"]["UIText"]["text"], "Lives: 3")
        self.assertEqual(self.api.get_entity("HUDPlatformerTimerText")["components"]["UIText"]["text"], "Time: 00:00")
        self.assertEqual(
            self.api.get_entity("HUDPlatformerPauseButton")["components"]["UIButton"]["on_click"]["name"],
            "ui.hud_platformer.pause",
        )

    def test_pause_game_over_and_dialog_presets_start_inactive(self) -> None:
        self.assertTrue(self.api.create_ui_preset("pause-menu")["success"])
        self.assertTrue(self.api.create_ui_preset("game-over")["success"])
        self.assertTrue(self.api.create_ui_preset("dialog-box")["success"])

        self.assertFalse(self.api.get_entity("PauseMenuCanvas")["active"])
        self.assertFalse(self.api.get_entity("GameOverCanvas")["active"])
        self.assertFalse(self.api.get_entity("DialogBoxCanvas")["active"])

    def test_unknown_preset_fails_with_clear_message(self) -> None:
        result = self.api.create_ui_preset("missing-preset")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Unknown UI preset 'missing-preset'")

    def test_replace_false_prevents_duplicates(self) -> None:
        self.assertTrue(self.api.create_ui_preset("main-menu")["success"])

        result = self.api.create_ui_preset("main-menu")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "UI preset 'main-menu' already exists. Use --replace to regenerate.")

    def test_replace_true_regenerates_same_tree_without_duplicates(self) -> None:
        self.assertTrue(self.api.create_ui_preset("main-menu")["success"])
        self.assertTrue(
            self.api.edit_component("MainMenuTitle", "UIText", "text", "Changed Title")["success"]
        )

        result = self.api.create_ui_preset("main-menu", replace=True)

        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["replaced"])
        self.assertEqual(self.api.get_entity("MainMenuTitle")["components"]["UIText"]["text"], "OpenGame")

        entity_names = [entity["name"] for entity in self.api.list_entities(active=None)]
        self.assertEqual(entity_names.count("MainMenuCanvas"), 1)
        self.assertEqual(entity_names.count("MainMenuTitle"), 1)
        self.assertEqual(entity_names.count("MainMenuPlayButton"), 1)


if __name__ == "__main__":
    unittest.main()
