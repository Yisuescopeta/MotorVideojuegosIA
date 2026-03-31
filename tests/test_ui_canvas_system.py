import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.editor.cursor_manager import CursorVisualState


REPO_ROOT = Path(__file__).resolve().parents[1]


class CanvasUISystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "CanvasProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _copy_real_scene(self, filename: str) -> Path:
        source = REPO_ROOT / "levels" / filename
        target = self.project_root / "levels" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def test_canvas_components_roundtrip_and_api_lists_ui_nodes(self) -> None:
        scene_path = self._write_scene(
            "ui_roundtrip.json",
            {
                "name": "UI Roundtrip",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(self.api.create_ui_text("Title", "Hello UI", "CanvasRoot", {"width": 320.0, "height": 80.0})["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )
        self.api.game.save_current_scene()

        raw = json.loads(scene_path.read_text(encoding="utf-8"))
        entity_names = {entity["name"] for entity in raw["entities"]}
        self.assertIn("CanvasRoot", entity_names)
        self.assertIn("Title", entity_names)
        self.assertIn("PlayButton", entity_names)
        self.assertEqual(raw["entities"][0]["components"]["Canvas"]["render_mode"], "screen_space_overlay")
        self.assertEqual(raw["entities"][1]["components"]["UIText"]["text"], "Hello UI")
        self.assertEqual(raw["entities"][2]["components"]["UIButton"]["on_click"]["name"], "ui.play_clicked")

        ui_nodes = {entity["name"] for entity in self.api.list_ui_nodes()}
        self.assertEqual(ui_nodes, {"CanvasRoot", "Title", "PlayButton"})

    def test_rect_transform_layout_scales_with_reference_resolution(self) -> None:
        scene_path = self._write_scene(
            "ui_layout.json",
            {
                "name": "UI Layout",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "PlayButton",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 280.0,
                                "height": 84.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIButton": {
                                "enabled": True,
                                "interactable": True,
                                "label": "Play",
                                "normal_color": [72, 72, 72, 255],
                                "hover_color": [92, 92, 92, 255],
                                "pressed_color": [56, 56, 56, 255],
                                "disabled_color": [48, 48, 48, 200],
                                "transition_scale_pressed": 0.96,
                                "on_click": {"type": "emit_event", "name": "ui.play_clicked"},
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._update_ui_overlay(self.api.game.world, (800.0, 600.0))
        base_layout = self.api.game._ui_system.get_entity_screen_rect("PlayButton")
        self.api.game._update_ui_overlay(self.api.game.world, (1600.0, 1200.0))
        scaled_layout = self.api.game._ui_system.get_entity_screen_rect("PlayButton")

        self.assertEqual(base_layout, {"x": 260.0, "y": 258.0, "width": 280.0, "height": 84.0})
        self.assertEqual(scaled_layout, {"x": 520.0, "y": 516.0, "width": 560.0, "height": 168.0})

    def test_ui_hit_testing_prefers_rect_transform_nodes_over_canvas_root(self) -> None:
        scene_path = self._write_scene(
            "ui_hit_test.json",
            {
                "name": "UI Hit Test",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "Panel",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 200.0,
                                "height": 80.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        ui_system = self.api.game._ui_system
        world = self.api.game.world
        hit = ui_system.find_topmost_entity_at_point(world, 400.0, 300.0, (800.0, 600.0))
        self.assertIsNotNone(hit)
        self.assertEqual(hit.name, "Panel")

    def test_button_click_release_inside_fires_and_release_outside_does_not(self) -> None:
        scene_path = self._write_scene(
            "ui_interaction.json",
            {
                "name": "UI Interaction",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "PlayButton",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 280.0,
                                "height": 84.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIButton": {
                                "enabled": True,
                                "interactable": True,
                                "label": "Play",
                                "normal_color": [72, 72, 72, 255],
                                "hover_color": [92, 92, 92, 255],
                                "pressed_color": [56, 56, 56, 255],
                                "disabled_color": [48, 48, 48, 200],
                                "transition_scale_pressed": 0.96,
                                "on_click": {"type": "emit_event", "name": "ui.play_clicked"},
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.step(1)
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=False, pressed=False, released=True)
        self.api.step(1)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertIn("ui.play_clicked", event_names)

        self.api.game._event_bus.clear_history()
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.step(1)
        self.api.game._ui_system.inject_pointer_state(40.0, 40.0, down=False, pressed=False, released=True)
        self.api.step(1)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertNotIn("ui.play_clicked", event_names)

    def test_scene_without_canvas_remains_compatible(self) -> None:
        scene_path = self._write_scene(
            "plain_scene.json",
            {
                "name": "Plain Scene",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.step(1)

        self.assertEqual(self.api.list_ui_nodes(), [])
        self.assertEqual(self.api.get_ui_layout("Missing"), {})

    def test_non_interactable_button_blocks_click(self) -> None:
        scene_path = self._write_scene(
            "ui_disabled_button.json",
            {
                "name": "Disabled Button",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )
        self.assertTrue(self.api.edit_component("PlayButton", "UIButton", "interactable", False)["success"])

        result = self.api.click_ui_button("PlayButton")

        self.assertFalse(result["success"])
        self.assertEqual([event.name for event in self.api.game.event_bus.get_recent_events()], [])

    def test_cursor_intent_marks_enabled_button_as_interactive(self) -> None:
        scene_path = self._write_scene(
            "ui_cursor_enabled.json",
            {
                "name": "Cursor Enabled",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        intent = self.api.game._ui_system.get_cursor_intent(self.api.game.world, (800.0, 600.0), 400.0, 300.0)

        self.assertEqual(intent, CursorVisualState.INTERACTIVE)

    def test_cursor_intent_ignores_non_interactable_buttons(self) -> None:
        scene_path = self._write_scene(
            "ui_cursor_disabled.json",
            {
                "name": "Cursor Disabled",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )
        self.assertTrue(self.api.edit_component("PlayButton", "UIButton", "interactable", False)["success"])

        intent = self.api.game._ui_system.get_cursor_intent(self.api.game.world, (800.0, 600.0), 400.0, 300.0)

        self.assertEqual(intent, CursorVisualState.DEFAULT)

    def test_real_main_menu_canvas_button_loads_platformer_scene(self) -> None:
        self._copy_real_scene("main_menu_scene.json")
        self._copy_real_scene("platformer_test_scene.json")

        self.api.load_level("levels/main_menu_scene.json")

        ui_nodes = {entity["name"] for entity in self.api.list_ui_nodes()}
        self.assertIn("MainCanvas", ui_nodes)
        self.assertIn("PlayButton", ui_nodes)

        result = self.api.click_ui_button("PlayButton")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Platformer Test Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/platformer_test_scene.json"))


if __name__ == "__main__":
    unittest.main()
