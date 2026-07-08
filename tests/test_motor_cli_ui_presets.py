import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from engine.api import EngineAPI
from engine.project.project_service import ProjectService
from motor.cli import run_motor_command


class MotorCLIUIPresetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.primary_scene = self.root / "levels" / "ui_primary.json"
        self.secondary_scene = self.root / "levels" / "ui_secondary.json"
        for path, name in (
            (self.primary_scene, "UI Primary"),
            (self.secondary_scene, "UI Secondary"),
        ):
            path.write_text(
                json.dumps({"name": name, "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
                encoding="utf-8",
            )

        api = EngineAPI(project_root=self.root.as_posix())
        try:
            api.load_level("levels/ui_primary.json")
            api.save_scene()
        finally:
            api.shutdown()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _run_motor_json(self, *args: str) -> tuple[int, dict]:
        output = StringIO()
        with redirect_stdout(output):
            code = run_motor_command(list(args))
        raw = output.getvalue().strip()
        json_start = raw.find("{")
        self.assertGreaterEqual(json_start, 0, raw)
        payload = json.loads(raw[json_start:])
        return code, payload

    def test_ui_preset_list_returns_five_presets(self) -> None:
        code, payload = self._run_motor_json(
            "ui",
            "preset",
            "list",
            "--project",
            self.root.as_posix(),
            "--json",
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["count"], 5)
        self.assertEqual(
            [preset["id"] for preset in payload["data"]["presets"]],
            ["hud-platformer", "main-menu", "pause-menu", "game-over", "dialog-box"],
        )

    def test_ui_preset_add_main_menu_creates_canvas_title_and_buttons(self) -> None:
        code, payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "main-menu",
            "--project",
            self.root.as_posix(),
            "--json",
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["success"])

        raw = json.loads(self.primary_scene.read_text(encoding="utf-8"))
        entities = {entity["name"]: entity for entity in raw["entities"]}
        self.assertIn("MainMenuCanvas", entities)
        self.assertEqual(entities["MainMenuTitle"]["components"]["UIText"]["text"], "OpenGame")
        self.assertEqual(
            entities["MainMenuPlayButton"]["components"]["UIButton"]["on_click"]["name"],
            "ui.main_menu.play",
        )
        self.assertEqual(
            entities["MainMenuOptionsButton"]["components"]["UIButton"]["on_click"]["name"],
            "ui.main_menu.options",
        )
        self.assertEqual(
            entities["MainMenuQuitButton"]["components"]["UIButton"]["on_click"]["name"],
            "ui.main_menu.quit",
        )

    def test_ui_preset_add_hud_platformer_creates_expected_nodes(self) -> None:
        code, payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "hud-platformer",
            "--project",
            self.root.as_posix(),
            "--json",
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["success"])

        raw = json.loads(self.primary_scene.read_text(encoding="utf-8"))
        entities = {entity["name"]: entity for entity in raw["entities"]}
        self.assertIn("HUDPlatformerCanvas", entities)
        self.assertEqual(entities["HUDPlatformerScoreText"]["components"]["UIText"]["text"], "Score: 0000")
        self.assertEqual(entities["HUDPlatformerLivesText"]["components"]["UIText"]["text"], "Lives: 3")
        self.assertEqual(entities["HUDPlatformerTimerText"]["components"]["UIText"]["text"], "Time: 00:00")
        self.assertEqual(
            entities["HUDPlatformerPauseButton"]["components"]["UIButton"]["on_click"]["name"],
            "ui.hud_platformer.pause",
        )

    def test_ui_preset_add_scene_flag_targets_specific_scene(self) -> None:
        code, payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "pause-menu",
            "--scene",
            "levels/ui_secondary.json",
            "--project",
            self.root.as_posix(),
            "--json",
        )

        self.assertEqual(code, 0)
        self.assertTrue(payload["success"])

        secondary = json.loads(self.secondary_scene.read_text(encoding="utf-8"))
        primary = json.loads(self.primary_scene.read_text(encoding="utf-8"))
        secondary_names = {entity["name"] for entity in secondary["entities"]}
        primary_names = {entity["name"] for entity in primary["entities"]}

        self.assertIn("PauseMenuCanvas", secondary_names)
        self.assertNotIn("PauseMenuCanvas", primary_names)

    def test_ui_preset_add_replace_regenerates_without_duplicates(self) -> None:
        first_code, first_payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "main-menu",
            "--project",
            self.root.as_posix(),
            "--json",
        )
        self.assertEqual(first_code, 0)
        self.assertTrue(first_payload["success"])

        replace_code, replace_payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "main-menu",
            "--replace",
            "--project",
            self.root.as_posix(),
            "--json",
        )

        self.assertEqual(replace_code, 0)
        self.assertTrue(replace_payload["success"])
        self.assertTrue(replace_payload["data"]["replaced"])

        raw = json.loads(self.primary_scene.read_text(encoding="utf-8"))
        entity_names = [entity["name"] for entity in raw["entities"]]
        self.assertEqual(entity_names.count("MainMenuCanvas"), 1)
        self.assertEqual(entity_names.count("MainMenuTitle"), 1)
        self.assertEqual(entity_names.count("MainMenuPlayButton"), 1)

    def test_ui_preset_add_duplicate_failure_does_not_save_scene(self) -> None:
        first_code, first_payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "main-menu",
            "--project",
            self.root.as_posix(),
            "--json",
        )
        self.assertEqual(first_code, 0)
        self.assertTrue(first_payload["success"])
        before = self.primary_scene.read_text(encoding="utf-8")

        second_code, second_payload = self._run_motor_json(
            "ui",
            "preset",
            "add",
            "main-menu",
            "--project",
            self.root.as_posix(),
            "--json",
        )

        self.assertEqual(second_code, 1)
        self.assertFalse(second_payload["success"])
        self.assertEqual(
            second_payload["message"],
            "UI preset 'main-menu' already exists. Use --replace to regenerate.",
        )
        self.assertEqual(self.primary_scene.read_text(encoding="utf-8"), before)

    def test_capabilities_include_ui_preset_entries(self) -> None:
        code, payload = self._run_motor_json("capabilities", "--json")

        self.assertEqual(code, 0)
        self.assertTrue(payload["success"])
        capability_ids = {cap["id"] for cap in payload["data"]["capabilities"]}
        self.assertIn("ui:preset:list", capability_ids)
        self.assertIn("ui:preset:add", capability_ids)


if __name__ == "__main__":
    unittest.main()
