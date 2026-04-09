import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertIn("ui.play_clicked", event_names)

        self.api.game._event_bus.clear_history()
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        self.api.game._ui_system.inject_pointer_state(40.0, 40.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertNotIn("ui.play_clicked", event_names)

    def test_button_does_not_fire_when_ui_overlay_is_updated_without_runtime_interaction(self) -> None:
        scene_path = self._write_scene(
            "ui_edit_blocked.json",
            {
                "name": "UI Edit Blocked",
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

        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=False)
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=False)

        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertNotIn("ui.play_clicked", event_names)

    def test_scene_viewport_size_helper_uses_scene_texture_dimensions(self) -> None:
        self.api.game.editor_layout = SimpleNamespace(
            active_tab="SCENE",
            scene_texture=SimpleNamespace(texture=SimpleNamespace(width=320, height=180)),
            game_texture=SimpleNamespace(texture=SimpleNamespace(width=640, height=360)),
        )

        self.assertEqual(self.api.game._ui_viewport_size_for_tab("SCENE"), (320.0, 180.0))
        self.assertEqual(self.api.game._ui_viewport_size_for_tab("GAME"), (640.0, 360.0))

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

        intent = self.api.game._ui_system.get_cursor_intent(
            self.api.game.world,
            (800.0, 600.0),
            400.0,
            300.0,
            allow_interaction=True,
        )

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

    def test_scene_view_ui_visibility_requires_play_or_selected_root_canvas(self) -> None:
        scene_path = self._write_scene(
            "ui_visibility.json",
            {
                "name": "UI Visibility",
                "entities": [
                    {
                        "name": "MainCanvas",
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
                        "name": "TitleText",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "MainCanvas",
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
                                "width": 240.0,
                                "height": 64.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIText": {
                                "enabled": True,
                                "text": "Title",
                                "font_size": 24,
                                "color": [255, 255, 255, 255],
                                "alignment": "center",
                                "wrap": False,
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

        self.assertFalse(ui_system.should_render_scene_view_ui(world, allow_runtime=False))
        self.assertTrue(self.api.scene_manager.set_selected_entity("TitleText"))
        self.assertFalse(ui_system.should_render_scene_view_ui(world, allow_runtime=False))
        self.assertTrue(self.api.scene_manager.set_selected_entity("MainCanvas"))
        self.assertTrue(ui_system.should_render_scene_view_ui(world, allow_runtime=False))
        self.assertTrue(ui_system.should_render_scene_view_ui(world, allow_runtime=True))

    def test_ui_focus_navigation_submit_and_cancel_work_through_engine_api(self) -> None:
        scene_path = self._write_scene(
            "ui_focus_navigation.json",
            {
                "name": "UI Focus Navigation",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.assertTrue(self.api.create_canvas(name="CanvasRoot", initial_focus_entity_id="PlayButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": -140.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
                nav_right="OptionsButton",
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "OptionsButton",
                "Options",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": 140.0},
                {"type": "emit_event", "name": "ui.options_clicked"},
                nav_left="PlayButton",
            )["success"]
        )

        focus_state = self.api.get_ui_focus()
        self.assertEqual(focus_state["active_canvas"], "CanvasRoot")
        self.assertTrue(focus_state["has_focus"])
        self.assertEqual(focus_state["focused_entity"], "PlayButton")
        self.assertEqual(focus_state["canvas_focus"]["CanvasRoot"], "PlayButton")
        self.assertEqual(focus_state["focused_button"]["label"], "Play")
        self.assertEqual(focus_state["focused_button"]["navigation"]["right"], "OptionsButton")

        move_result = self.api.move_ui_focus("right")
        self.assertTrue(move_result["success"])
        self.assertEqual(move_result["data"]["focused_entity"], "OptionsButton")

        self.api.play()
        self.api.game.event_bus.clear_history()

        submit_result = self.api.inject_ui_navigation(submit=True, frames=1)
        self.assertTrue(submit_result["success"])
        self.api.step(1)
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]
        self.assertIn("ui.options_clicked", event_names)

        self.api.game.event_bus.clear_history()
        cancel_result = self.api.cancel_ui_focus()
        self.assertTrue(cancel_result["success"])
        cancel_events = [event.name for event in self.api.game.event_bus.get_recent_events()]
        self.assertIn("ui.cancel", cancel_events)

    def test_simple_menu_can_be_driven_via_public_focus_move_submit_aliases(self) -> None:
        scene_path = self._write_scene(
            "ui_simple_menu_aliases.json",
            {
                "name": "UI Simple Menu Aliases",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.assertTrue(self.api.create_canvas(name="MenuCanvas", initial_focus_entity_id="PlayButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "MenuCanvas",
                {"width": 220.0, "height": 72.0, "anchored_y": -90.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
                nav_down="QuitButton",
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "QuitButton",
                "Quit",
                "MenuCanvas",
                {"width": 220.0, "height": 72.0, "anchored_y": 10.0},
                {"type": "emit_event", "name": "ui.quit_clicked"},
                nav_up="PlayButton",
            )["success"]
        )

        focus_result = self.api.focus_entity("PlayButton")
        self.assertTrue(focus_result["success"])
        self.assertEqual(focus_result["data"]["focused_entity"], "PlayButton")

        move_result = self.api.ui_move_focus("down")
        self.assertTrue(move_result["success"])
        self.assertEqual(move_result["data"]["focused_entity"], "QuitButton")

        self.api.play()
        self.api.game.event_bus.clear_history()
        submit_result = self.api.ui_submit()
        self.assertTrue(submit_result["success"])
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]
        self.assertIn("ui.quit_clicked", event_names)

        self.api.game.event_bus.clear_history()
        cancel_result = self.api.ui_cancel()
        self.assertTrue(cancel_result["success"])
        cancel_events = self.api.game.event_bus.get_recent_events()
        self.assertIn("ui.cancel", [event.name for event in cancel_events])
        self.assertEqual(cancel_events[-1].data["canvas"], "MenuCanvas")

    def test_ui_focus_invalid_initial_target_falls_back_to_first_focusable(self) -> None:
        scene_path = self._write_scene(
            "ui_focus_initial_fallback.json",
            {
                "name": "UI Focus Initial Fallback",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot", initial_focus_entity_id="MissingButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "FirstButton",
                "First",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_y": -60.0},
                {"type": "emit_event", "name": "ui.first_clicked"},
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "SecondButton",
                "Second",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_y": 60.0},
                {"type": "emit_event", "name": "ui.second_clicked"},
            )["success"]
        )

        focus_state = self.api.get_ui_focus()

        self.assertEqual(focus_state["focused_entity"], "FirstButton")
        self.assertEqual(focus_state["active_canvas"], "CanvasRoot")

    def test_ui_focus_spatial_fallback_and_submit_uses_focus_not_hover(self) -> None:
        scene_path = self._write_scene(
            "ui_focus_spatial_submit.json",
            {
                "name": "UI Focus Spatial Submit",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot", initial_focus_entity_id="LeftButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "LeftButton",
                "Left",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": -160.0},
                {"type": "emit_event", "name": "ui.left_clicked"},
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "RightButton",
                "Right",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": 160.0},
                {"type": "emit_event", "name": "ui.right_clicked"},
            )["success"]
        )

        self.api.game._ui_system.inject_pointer_state(560.0, 300.0, down=False, pressed=False, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        hover_state = self.api.game._ui_system.get_button_state(self.api.game.world.get_entity_by_name("RightButton"))
        self.assertTrue(hover_state["hovered"])
        self.assertFalse(hover_state["focused"])

        move_result = self.api.move_ui_focus("right")
        self.assertTrue(move_result["success"])
        self.assertEqual(move_result["data"]["focused_entity"], "RightButton")

        self.api.play()
        self.api.game.event_bus.clear_history()
        submit_result = self.api.submit_ui_focus()
        self.assertTrue(submit_result["success"])
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]
        self.assertIn("ui.right_clicked", event_names)
        self.assertNotIn("ui.left_clicked", event_names)

    def test_ui_pointer_hover_does_not_steal_focus_but_click_does(self) -> None:
        scene_path = self._write_scene(
            "ui_focus_pointer_priority.json",
            {
                "name": "UI Focus Pointer Priority",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot", initial_focus_entity_id="PrimaryButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PrimaryButton",
                "Primary",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": -140.0},
                {"type": "emit_event", "name": "ui.primary_clicked"},
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "SecondaryButton",
                "Secondary",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": 140.0},
                {"type": "emit_event", "name": "ui.secondary_clicked"},
            )["success"]
        )

        self.api.game._ui_system.inject_pointer_state(540.0, 300.0, down=False, pressed=False, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        focus_state = self.api.get_ui_focus()
        self.assertEqual(focus_state["focused_entity"], "PrimaryButton")

        self.api.game._ui_system.inject_pointer_state(540.0, 300.0, down=True, pressed=True, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        self.api.game._ui_system.inject_pointer_state(540.0, 300.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)

        focus_state = self.api.get_ui_focus()
        self.assertEqual(focus_state["focused_entity"], "SecondaryButton")

    def test_ui_set_focus_and_resync_when_focused_button_becomes_non_interactable(self) -> None:
        scene_path = self._write_scene(
            "ui_focus_resync.json",
            {
                "name": "UI Focus Resync",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot", initial_focus_entity_id="FirstButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "FirstButton",
                "First",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": -140.0},
                {"type": "emit_event", "name": "ui.first_clicked"},
                nav_right="SecondButton",
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "SecondButton",
                "Second",
                "CanvasRoot",
                {"width": 220.0, "height": 72.0, "anchored_x": 140.0},
                {"type": "emit_event", "name": "ui.second_clicked"},
                nav_left="FirstButton",
            )["success"]
        )

        set_focus_result = self.api.set_ui_focus("SecondButton")
        self.assertTrue(set_focus_result["success"])
        self.assertEqual(set_focus_result["data"]["focused_entity"], "SecondButton")

        self.assertTrue(self.api.edit_component("SecondButton", "UIButton", "interactable", False)["success"])

        focus_state = self.api.get_ui_focus()
        self.assertEqual(focus_state["focused_entity"], "FirstButton")
        self.assertEqual(focus_state["active_canvas"], "CanvasRoot")

    def test_ui_set_focus_can_switch_active_canvas_for_cancel_and_submit(self) -> None:
        scene_path = self._write_scene(
            "ui_focus_multi_canvas.json",
            {
                "name": "UI Focus Multi Canvas",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="BackgroundCanvas", sort_order=0, initial_focus_entity_id="BackgroundButton")["success"])
        self.assertTrue(self.api.create_canvas(name="OverlayCanvas", sort_order=10, initial_focus_entity_id="OverlayButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "BackgroundButton",
                "Background",
                "BackgroundCanvas",
                {"width": 220.0, "height": 72.0, "anchored_y": 120.0},
                {"type": "emit_event", "name": "ui.background_clicked"},
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "OverlayButton",
                "Overlay",
                "OverlayCanvas",
                {"width": 220.0, "height": 72.0, "anchored_y": -120.0},
                {"type": "emit_event", "name": "ui.overlay_clicked"},
            )["success"]
        )

        initial_focus = self.api.get_ui_focus()
        self.assertEqual(initial_focus["active_canvas"], "OverlayCanvas")
        self.assertEqual(initial_focus["focused_entity"], "OverlayButton")

        set_focus_result = self.api.set_ui_focus("BackgroundButton", canvas_name="BackgroundCanvas")
        self.assertTrue(set_focus_result["success"])
        self.assertEqual(set_focus_result["data"]["active_canvas"], "BackgroundCanvas")

        focus_state = self.api.get_ui_focus()
        self.assertEqual(focus_state["active_canvas"], "BackgroundCanvas")
        self.assertEqual(focus_state["focused_entity"], "BackgroundButton")

        self.api.play()
        self.api.game.event_bus.clear_history()
        submit_result = self.api.submit_ui_focus()
        self.assertTrue(submit_result["success"])
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]
        self.assertIn("ui.background_clicked", event_names)
        self.assertNotIn("ui.overlay_clicked", event_names)

        self.api.game.event_bus.clear_history()
        cancel_result = self.api.cancel_ui_focus()
        self.assertTrue(cancel_result["success"])
        cancel_events = self.api.game.event_bus.get_recent_events()
        self.assertIn("ui.cancel", [event.name for event in cancel_events])
        self.assertEqual(cancel_events[-1].data["canvas"], "BackgroundCanvas")

        self.api.stop()


if __name__ == "__main__":
    unittest.main()
