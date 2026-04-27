import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pyray as rl
from engine.api import EngineAPI
from engine.editor.console_panel import GLOBAL_LOGS


def _transform(x: float, y: float) -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _player_components(x: float, y: float, *, with_input: bool = False) -> dict[str, object]:
    components: dict[str, object] = {
        "Transform": _transform(x, y),
        "PlayerController2D": {
            "enabled": True,
            "move_speed": 180.0,
            "jump_velocity": -320.0,
            "air_control": 0.75,
        },
    }
    if with_input:
        components["InputMap"] = {
            "enabled": True,
            "move_left": "A,LEFT",
            "move_right": "D,RIGHT",
            "move_up": "W,UP",
            "move_down": "S,DOWN",
            "action_1": "SPACE",
            "action_2": "ENTER",
        }
    return components


class SceneTransitionRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "SceneTransitionProject"
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=(self.root / "global_state").as_posix(),
        )
        GLOBAL_LOGS.clear()

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _attach_game_tab_layout(self) -> None:
        self.api.game.editor_layout = SimpleNamespace(
            active_tab="GAME",
            editor_camera=SimpleNamespace(target=rl.Vector2(0.0, 0.0), zoom=1.0),
            get_center_view_rect=lambda: rl.Rectangle(0, 0, self.api.game.width, self.api.game.height),
            set_scene_tabs=lambda *_args, **_kwargs: None,
        )

    def _target_scene_payload(self, *, include_spawn: bool = True) -> dict:
        entities = [
            {
                "name": "Player",
                "active": True,
                "tag": "Player",
                "layer": "Default",
                "components": _player_components(16.0, 24.0),
            }
        ]
        if include_spawn:
            entities.append(
                {
                    "name": "ArrivalPoint",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {
                        "Transform": _transform(192.0, 144.0),
                        "SceneEntryPoint": {
                            "enabled": True,
                            "entry_id": "arrival",
                            "label": "Arrival",
                        },
                    },
                }
            )
        return {
            "name": "Target Scene",
            "entities": entities,
            "rules": [],
            "feature_metadata": {},
        }

    def test_ui_button_runs_scene_transition_and_applies_spawn(self) -> None:
        source_path = self._write_scene(
            "button_source.json",
            {
                "name": "Button Source",
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
                                "on_click": {"type": "run_scene_transition"},
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_scene.json",
                                "target_entry_id": "arrival",
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=True))

        self.api.load_level(source_path.as_posix())
        self._attach_game_tab_layout()
        self.api.play()

        result = self.api.click_ui_button("PlayButton")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Target Scene")
        self.assertEqual(self.api.game.editor_layout.active_tab, "GAME")
        self.assertTrue(self.api.game.is_play_mode)
        player = self.api.get_entity("Player")
        self.assertEqual(player["components"]["Transform"]["x"], 192.0)
        self.assertEqual(player["components"]["Transform"]["y"], 144.0)

    def test_ui_button_load_scene_keeps_runtime_state_when_clicked_in_play(self) -> None:
        source_path = self._write_scene(
            "button_load_scene_source.json",
            {
                "name": "Button Load Scene Source",
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
                                "on_click": {"type": "load_scene", "path": "levels/target_scene.json"},
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=True))

        self.api.load_level(source_path.as_posix())
        self._attach_game_tab_layout()
        self.api.play()

        result = self.api.click_ui_button("PlayButton")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Target Scene")
        self.assertTrue(self.api.game.is_play_mode)
        self.assertEqual(self.api.game.editor_layout.active_tab, "GAME")

    def test_contact_triggers_change_scene_for_trigger_and_collision_modes(self) -> None:
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=False))

        for filename, collider_is_trigger, mode in (
            ("trigger_source.json", True, "trigger_enter"),
            ("collision_source.json", False, "collision"),
        ):
            with self.subTest(mode=mode):
                source_path = self._write_scene(
                    filename,
                    {
                        "name": f"Source {mode}",
                        "entities": [
                            {
                                "name": "Player",
                                "active": True,
                                "tag": "Player",
                                "layer": "Default",
                                "components": {
                                    "Transform": _transform(0.0, 0.0),
                                    "Collider": {
                                        "enabled": True,
                                        "width": 32.0,
                                        "height": 32.0,
                                        "offset_x": 0.0,
                                        "offset_y": 0.0,
                                        "is_trigger": False,
                                    },
                                    "PlayerController2D": {
                                        "enabled": True,
                                        "move_speed": 180.0,
                                        "jump_velocity": -320.0,
                                        "air_control": 0.75,
                                    },
                                },
                            },
                            {
                                "name": "Portal",
                                "active": True,
                                "tag": "Untagged",
                                "layer": "Default",
                                "components": {
                                    "Transform": _transform(0.0, 0.0),
                                    "Collider": {
                                        "enabled": True,
                                        "width": 32.0,
                                        "height": 32.0,
                                        "offset_x": 0.0,
                                        "offset_y": 0.0,
                                        "is_trigger": collider_is_trigger,
                                    },
                                    "SceneTransitionAction": {
                                        "enabled": True,
                                        "target_scene_path": "levels/target_scene.json",
                                        "target_entry_id": "",
                                    },
                                    "SceneTransitionOnContact": {
                                        "enabled": True,
                                        "mode": mode,
                                        "require_player": True,
                                    },
                                },
                            },
                        ],
                        "rules": [],
                        "feature_metadata": {},
                    },
                )

                GLOBAL_LOGS.clear()
                self.api.load_level(source_path.as_posix())
                self._attach_game_tab_layout()
                self.api.play()
                self.api.step(1)

                self.assertEqual(self.api.scene_manager.scene_name, "Target Scene")
                self.assertEqual(self.api.game.editor_layout.active_tab, "GAME")
                self.assertFalse(self.api.game.is_edit_mode)
                self.assertEqual([level for level, _ in GLOBAL_LOGS if level == "ERR"], [])

    def test_interaction_trigger_changes_scene_only_when_action_2_is_pressed(self) -> None:
        source_path = self._write_scene(
            "interact_source.json",
            {
                "name": "Interact Source",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Default",
                        "components": {
                            **_player_components(0.0, 0.0, with_input=True),
                            "Collider": {
                                "enabled": True,
                                "width": 32.0,
                                "height": 32.0,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "is_trigger": False,
                            },
                        },
                    },
                    {
                        "name": "Portal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": _transform(0.0, 0.0),
                            "Collider": {
                                "enabled": True,
                                "width": 48.0,
                                "height": 48.0,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "is_trigger": True,
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_scene.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnInteract": {
                                "enabled": True,
                                "require_player": True,
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=False))

        self.api.load_level(source_path.as_posix())
        self.api.play()
        self.api.step(1)
        self.assertEqual(self.api.scene_manager.scene_name, "Interact Source")

        self.api.inject_input_state(
            "Player",
            {
                "horizontal": 0.0,
                "vertical": 0.0,
                "action_1": 0.0,
                "action_2": 1.0,
            },
            frames=1,
        )
        self.api.step(1)

        self.assertEqual(self.api.scene_manager.scene_name, "Target Scene")

    def test_player_death_runs_transition_on_same_entity(self) -> None:
        source_path = self._write_scene(
            "death_source.json",
            {
                "name": "Death Source",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Default",
                        "components": {
                            **_player_components(0.0, 0.0),
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_scene.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnPlayerDeath": {
                                "enabled": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=False))

        self.api.load_level(source_path.as_posix())
        self.api.play()
        self.api.game.event_bus.emit("player_death", {"entity": "Player"})
        self.api.step(1)

        self.assertEqual(self.api.scene_manager.scene_name, "Target Scene")

    def test_transition_without_spawn_keeps_authored_player_position(self) -> None:
        source_path = self._write_scene(
            "no_spawn_source.json",
            {
                "name": "No Spawn Source",
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
                            }
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
                                "on_click": {"type": "run_scene_transition"},
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_scene.json",
                                "target_entry_id": "",
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=True))

        self.api.load_level(source_path.as_posix())
        self.api.play()
        self.api.click_ui_button("PlayButton")

        player = self.api.get_entity("Player")
        self.assertEqual(self.api.scene_manager.scene_name, "Target Scene")
        self.assertEqual(player["components"]["Transform"]["x"], 16.0)
        self.assertEqual(player["components"]["Transform"]["y"], 24.0)

    def test_missing_target_scene_is_logged_and_scene_does_not_change(self) -> None:
        source_path = self._write_scene(
            "missing_scene_source.json",
            {
                "name": "Missing Scene Source",
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
                            }
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
                                "on_click": {"type": "run_scene_transition"},
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/missing_target_scene.json",
                                "target_entry_id": "",
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )

        self.api.load_level(source_path.as_posix())
        self.api.play()

        result = self.api.click_ui_button("PlayButton")

        self.assertFalse(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Missing Scene Source")
        self.assertTrue(any(level == "ERR" and "target scene 'levels/missing_target_scene.json'" in message for level, message in GLOBAL_LOGS))

    def test_missing_target_spawn_is_logged_and_scene_does_not_change(self) -> None:
        source_path = self._write_scene(
            "missing_spawn_source.json",
            {
                "name": "Missing Spawn Source",
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
                            }
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
                                "on_click": {"type": "run_scene_transition"},
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_scene.json",
                                "target_entry_id": "missing_spawn",
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_scene.json", self._target_scene_payload(include_spawn=True))

        self.api.load_level(source_path.as_posix())
        self.api.play()

        result = self.api.click_ui_button("PlayButton")

        self.assertFalse(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Missing Spawn Source")
        self.assertTrue(any(level == "ERR" and "target entry point 'missing_spawn'" in message for level, message in GLOBAL_LOGS))


if __name__ == "__main__":
    unittest.main()
