import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI
from engine.components.recttransform import RectTransform
from engine.components.transform import Transform


class InspectorCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        demo_level = Path(__file__).resolve().parents[1] / "levels" / "demo_level.json"
        target_level = self.project_root / "levels" / "demo_level.json"
        target_level.parent.mkdir(parents=True, exist_ok=True)
        target_level.write_text(demo_level.read_text(encoding="utf-8"), encoding="utf-8")
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")
        self.inspector = self.api.game._inspector_system

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _create_probe(self, name: str, components: dict) -> None:
        result = self.api.create_entity(name, components=components)
        self.assertTrue(result["success"])

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _target_scene_payload(self, scene_name: str, entry_points: list[tuple[str, str, float, float]]) -> dict:
        entities = [
            {
                "name": "Player",
                "active": True,
                "tag": "Player",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 16.0,
                        "y": 24.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    },
                    "PlayerController2D": {
                        "enabled": True,
                        "move_speed": 180.0,
                        "jump_velocity": -320.0,
                        "air_control": 0.75,
                    },
                },
            }
        ]
        for entry_id, label, x, y in entry_points:
            entities.append(
                {
                    "name": f"{entry_id.title()}Point",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": x,
                            "y": y,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        },
                        "SceneEntryPoint": {
                            "enabled": True,
                            "entry_id": entry_id,
                            "label": label,
                        },
                    },
                }
            )
        return {
            "schema_version": 2,
            "name": scene_name,
            "entities": entities,
            "rules": [],
            "feature_metadata": {},
        }

    def test_registry_covers_all_current_builtins(self) -> None:
        expected = {
            "Transform",
            "Sprite",
            "Collider",
            "RigidBody",
            "Animator",
            "Camera2D",
            "AudioSource",
            "InputMap",
            "PlayerController2D",
            "ScriptBehaviour",
            "SceneEntryPoint",
        }
        self.assertTrue(expected.issubset(set(self.inspector.list_dedicated_editors())))

    def test_sprite_payload_edits_update_scene_and_support_undo_redo(self) -> None:
        self._create_probe(
            "InspectorSpriteProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Sprite": {
                    "enabled": True,
                    "texture_path": "assets/player.png",
                    "width": 32,
                    "height": 32,
                    "origin_x": 0.5,
                    "origin_y": 0.5,
                    "flip_x": False,
                    "flip_y": False,
                    "tint": [255, 255, 255, 255],
                },
            },
        )

        def update(payload: dict) -> None:
            payload["texture_path"] = "assets/player_alt.png"
            payload["tint"] = [128, 200, 255, 255]

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorSpriteProbe", "Sprite", update)
        self.assertTrue(success)

        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [128, 200, 255, 255])
        scene_sprite = self.api.scene_manager.current_scene.find_entity("InspectorSpriteProbe")["components"]["Sprite"]
        self.assertEqual(scene_sprite["tint"], [128, 200, 255, 255])

        self.assertTrue(self.api.undo()["success"])
        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [255, 255, 255, 255])

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [128, 200, 255, 255])

    def test_animator_payload_edits_use_serializable_source_and_history(self) -> None:
        self._create_probe(
            "InspectorAnimatorProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Animator": {
                    "enabled": True,
                    "sprite_sheet": "assets/player_sheet.png",
                    "frame_width": 32,
                    "frame_height": 32,
                    "animations": {
                        "idle": {
                            "frames": [0, 1],
                            "slice_names": ["idle_0", "idle_1"],
                            "fps": 8.0,
                            "loop": True,
                            "on_complete": None,
                        }
                    },
                    "default_state": "idle",
                    "current_state": "idle",
                    "current_frame": 0,
                    "is_finished": False,
                },
            },
        )

        def update(payload: dict) -> None:
            payload["default_state"] = "run"
            payload["animations"]["run"] = {
                "frames": [2, 3, 4],
                "slice_names": ["run_0", "run_1", "run_2"],
                "fps": 12.0,
                "loop": True,
                "on_complete": None,
            }

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorAnimatorProbe", "Animator", update)
        self.assertTrue(success)

        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "run")
        self.assertEqual(animator["animations"]["run"]["slice_names"], ["run_0", "run_1", "run_2"])
        scene_animator = self.api.scene_manager.current_scene.find_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertIn("run", scene_animator["animations"])

        self.assertTrue(self.api.undo()["success"])
        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "idle")
        self.assertNotIn("run", animator["animations"])

        self.assertTrue(self.api.redo()["success"])
        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "run")
        self.assertIn("run", animator["animations"])

    def test_script_behaviour_payload_edits_use_common_route_and_history(self) -> None:
        self._create_probe(
            "InspectorScriptProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "ScriptBehaviour": {
                    "enabled": True,
                    "module_path": "platformer_character",
                    "run_in_edit_mode": False,
                    "public_data": {"health": 3, "coins": 0},
                },
            },
        )

        def update(payload: dict) -> None:
            payload["module_path"] = "enemy_brain"
            payload["public_data"] = {"health": 5, "coins": 2, "alive": True}

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorScriptProbe", "ScriptBehaviour", update)
        self.assertTrue(success)

        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "enemy_brain")
        self.assertEqual(script_data["public_data"], {"health": 5, "coins": 2, "alive": True})
        scene_script = self.api.scene_manager.current_scene.find_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(scene_script["public_data"]["coins"], 2)

        self.assertTrue(self.api.undo()["success"])
        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "platformer_character")
        self.assertEqual(script_data["public_data"], {"health": 3, "coins": 0})

        self.assertTrue(self.api.redo()["success"])
        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "enemy_brain")
        self.assertEqual(script_data["public_data"]["alive"], True)

    def test_transform_editor_uses_serializable_local_values_for_child_entity(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorParent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 200.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "InspectorParent",
                "InspectorChild",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 15.0, "scale_x": 1.5, "scale_y": 0.75}},
            )["success"]
        )

        child = self.api.game.world.get_entity_by_name("InspectorChild")
        transform = child.get_component(Transform)
        rendered_values: dict[str, float | bool] = {}

        def capture(label, value, *args, **kwargs):
            rendered_values[label] = value
            return args[4] + 1

        with patch.object(self.inspector, "_draw_component_field", side_effect=capture):
            self.inspector._draw_transform_editor(transform, child.id, 0, 0, 240, True, self.api.game.world)

        self.assertEqual(rendered_values["X"], 12.0)
        self.assertEqual(rendered_values["Y"], 8.0)
        self.assertEqual(rendered_values["Rotation"], 15.0)
        self.assertEqual(rendered_values["Scale X"], 1.5)
        self.assertEqual(rendered_values["Scale Y"], 0.75)

    def test_inspector_transform_edit_persists_local_transform_after_save_and_reload(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorParent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 50.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "InspectorParent",
                "InspectorChild",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(self.api.scene_manager.set_selected_entity("InspectorChild"))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorChild", "Transform", "x", 30.0))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorChild", "Transform", "y", 40.0))

        child_data = self.api.scene_manager.current_scene.find_entity("InspectorChild")
        self.assertEqual(child_data["components"]["Transform"]["x"], 30.0)
        self.assertEqual(child_data["components"]["Transform"]["y"], 40.0)
        self.assertEqual(self.api.game.world.selected_entity_name, "InspectorChild")

        save_path = self.project_root / "levels" / "inspector_transform_scene.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        child = self.api.game.world.get_entity_by_name("InspectorChild")
        transform = child.get_component(Transform)
        self.assertEqual(transform.local_x, 30.0)
        self.assertEqual(transform.local_y, 40.0)
        self.assertEqual(transform.x, 130.0)
        self.assertEqual(transform.y, 90.0)

    def test_inspector_rect_transform_edit_persists_after_save_and_reload(self) -> None:
        self._create_probe(
            "InspectorButton",
            {
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
                }
            },
        )

        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorButton", "RectTransform", "anchored_x", 32.0))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorButton", "RectTransform", "height", 96.0))

        button_data = self.api.scene_manager.current_scene.find_entity("InspectorButton")
        self.assertEqual(button_data["components"]["RectTransform"]["anchored_x"], 32.0)
        self.assertEqual(button_data["components"]["RectTransform"]["height"], 96.0)

        save_path = self.project_root / "levels" / "inspector_rect_scene.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        button = self.api.game.world.get_entity_by_name("InspectorButton")
        rect_transform = button.get_component(RectTransform)
        self.assertEqual(rect_transform.anchored_x, 32.0)
        self.assertEqual(rect_transform.height, 96.0)

    def test_inspector_scene_transition_ui_button_persists_and_supports_undo_redo(self) -> None:
        self._write_scene(
            "transition_target.json",
            self._target_scene_payload("Transition Target", [("arrival", "Arrival", 192.0, 144.0)]),
        )
        self._create_probe(
            "PortalButton",
            {
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
                    "width": 220.0,
                    "height": 64.0,
                    "rotation": 0.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                },
                "UIButton": {
                    "enabled": True,
                    "interactable": True,
                    "label": "Go",
                    "normal_color": [72, 72, 72, 255],
                    "hover_color": [92, 92, 92, 255],
                    "pressed_color": [56, 56, 56, 255],
                    "disabled_color": [48, 48, 48, 200],
                    "transition_scale_pressed": 0.96,
                    "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                },
            },
        )

        self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "PortalButton", "ui_button"))
        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "PortalButton",
                "levels/transition_target.json",
            )
        )
        self.assertTrue(self.inspector._set_scene_transition_target_spawn(self.api.game.world, "PortalButton", "arrival"))

        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["UIButton"]["on_click"]["type"], "run_scene_transition")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_scene_path"], "levels/transition_target.json")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")

        self.assertTrue(self.api.undo()["success"])
        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "")

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")

        save_path = self.project_root / "levels" / "inspector_transition_saved.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["UIButton"]["on_click"]["type"], "run_scene_transition")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_scene_path"], "levels/transition_target.json")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")

    def test_inspector_scene_transition_trigger_presets_materialize_expected_components(self) -> None:
        self._create_probe(
            "TransitionProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Collider": {
                    "enabled": True,
                    "width": 32.0,
                    "height": 32.0,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "is_trigger": True,
                },
                "UIButton": {
                    "enabled": True,
                    "interactable": True,
                    "label": "Go",
                    "normal_color": [72, 72, 72, 255],
                    "hover_color": [92, 92, 92, 255],
                    "pressed_color": [56, 56, 56, 255],
                    "disabled_color": [48, 48, 48, 200],
                    "transition_scale_pressed": 0.96,
                    "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                },
            },
        )

        for preset, component_name, mode in (
            ("interact_near", "SceneTransitionOnInteract", None),
            ("trigger_enter", "SceneTransitionOnContact", "trigger_enter"),
            ("collision", "SceneTransitionOnContact", "collision"),
            ("player_death", "SceneTransitionOnPlayerDeath", None),
        ):
            with self.subTest(preset=preset):
                self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "TransitionProbe", preset))
                components = self.api.get_entity("TransitionProbe")["components"]
                self.assertIn("SceneTransitionAction", components)
                self.assertIn(component_name, components)
                if mode is not None:
                    self.assertEqual(components["SceneTransitionOnContact"]["mode"], mode)
                trigger_count = sum(
                    1
                    for trigger_name in (
                        "SceneTransitionOnContact",
                        "SceneTransitionOnInteract",
                        "SceneTransitionOnPlayerDeath",
                    )
                    if trigger_name in components
                )
                self.assertEqual(trigger_count, 1)

    def test_scene_transition_target_scene_change_refreshes_spawn_options_and_clears_invalid_spawn(self) -> None:
        self._write_scene(
            "transition_target_a.json",
            self._target_scene_payload("Transition A", [("arrival", "Arrival", 100.0, 100.0)]),
        )
        self._write_scene(
            "transition_target_b.json",
            self._target_scene_payload("Transition B", [("exit", "Exit", 240.0, 140.0)]),
        )
        self._create_probe(
            "Portal",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            },
        )

        self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "Portal", "collision"))
        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "Portal",
                "levels/transition_target_a.json",
            )
        )
        self.assertTrue(self.inspector._set_scene_transition_target_spawn(self.api.game.world, "Portal", "arrival"))

        spawn_options = self.inspector._get_scene_transition_spawn_options(self.api.game.world, "Portal")
        self.assertIn(("arrival", "Arrival (ArrivalPoint)"), spawn_options)

        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "Portal",
                "levels/transition_target_b.json",
            )
        )

        entity = self.api.get_entity("Portal")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "")
        spawn_options = self.inspector._get_scene_transition_spawn_options(self.api.game.world, "Portal")
        self.assertIn(("exit", "Exit (ExitPoint)"), spawn_options)
        self.assertFalse(any(key == "arrival" for key, _ in spawn_options))

    def test_scene_transition_validation_messages_cover_invalid_scene_spawn_and_player_death_warning(self) -> None:
        self._write_scene(
            "transition_target_valid.json",
            self._target_scene_payload("Transition Valid", [("arrival", "Arrival", 96.0, 64.0)]),
        )
        self._create_probe(
            "InteractPortal",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            },
        )

        self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "InteractPortal", "player_death"))
        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "InteractPortal",
                "levels/missing_scene.json",
            )
        )
        messages = self.inspector._get_scene_transition_validation_messages(self.api.game.world, "InteractPortal")
        self.assertTrue(any("player-like entity" in message for _, message in messages))
        self.assertTrue(any("does not exist" in message for _, message in messages))

        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "InteractPortal",
                "levels/transition_target_valid.json",
            )
        )
        self.assertTrue(self.inspector._set_scene_transition_target_spawn(self.api.game.world, "InteractPortal", "ghost"))
        messages = self.inspector._get_scene_transition_validation_messages(self.api.game.world, "InteractPortal")
        self.assertTrue(any("player-like entity" in message for _, message in messages))
        self.assertTrue(any("ghost" in message for _, message in messages))

    def test_script_executor_exposes_undo_redo_commands(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [
            {"action": "INSPECT_EDIT", "args": {"entity": "Ground", "component": "Transform", "property": "x", "value": 700.0}},
            {"action": "UNDO", "args": {}},
            {"action": "REDO", "args": {}},
        ]

        self.assertTrue(executor.run_all())
        ground = self.api.get_entity("Ground")
        self.assertEqual(ground["components"]["Transform"]["x"], 700.0)

    def test_scene_link_mode_syncs_runtime_button_transition(self) -> None:
        self._create_probe(
            "FlowButton",
            {
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
                    "width": 220.0,
                    "height": 72.0,
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
                    "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                },
                "SceneLink": {
                    "enabled": True,
                    "target_path": "levels/demo_level.json",
                    "flow_key": "",
                    "preview_label": "Demo",
                    "link_mode": "",
                    "target_entry_id": "",
                },
            },
        )

        self.assertTrue(self.inspector._set_scene_link_mode(self.api.game.world, "FlowButton", "ui_button"))
        entity = self.api.get_entity("FlowButton")
        self.assertEqual(entity["components"]["SceneLink"]["link_mode"], "ui_button")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_scene_path"], "levels/demo_level.json")
        self.assertEqual(entity["components"]["UIButton"]["on_click"]["type"], "run_scene_transition")

    def test_scene_link_target_spawn_updates_runtime_transition(self) -> None:
        self._write_scene(
            "flow_target.json",
            self._target_scene_payload("FlowTarget", [("arrival", "Arrival", 48.0, 64.0)]),
        )
        self._create_probe(
            "PortalFlow",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Collider": {
                    "enabled": True,
                    "width": 32.0,
                    "height": 32.0,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "is_trigger": True,
                },
                "SceneLink": {
                    "enabled": True,
                    "target_path": "levels/flow_target.json",
                    "flow_key": "",
                    "preview_label": "Target",
                    "link_mode": "trigger_enter",
                    "target_entry_id": "",
                },
            },
        )

        self.assertTrue(self.inspector._sync_scene_link_runtime(self.api.game.world, "PortalFlow"))
        self.assertTrue(self.inspector._set_scene_link_target_spawn(self.api.game.world, "PortalFlow", "arrival"))
        entity = self.api.get_entity("PortalFlow")
        self.assertEqual(entity["components"]["SceneLink"]["target_entry_id"], "arrival")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")
        self.assertEqual(entity["components"]["SceneTransitionOnContact"]["mode"], "trigger_enter")


if __name__ == "__main__":
    unittest.main()
