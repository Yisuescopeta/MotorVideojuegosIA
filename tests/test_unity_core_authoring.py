import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.getcwd())

import pyray as rl

from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI
from engine.components.animator import Animator
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.inputmap import InputMap
from engine.components.rigidbody import RigidBody
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.transform import Transform
from engine.editor.console_panel import GLOBAL_LOGS
from engine.systems.render_system import RenderSystem
from engine.systems.selection_system import SelectionSystem


class UnityCoreAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = EngineAPI()
        self.api.load_level("levels/demo_level.json")
        self._temp_scripts: list[Path] = []
        GLOBAL_LOGS.clear()

    def tearDown(self) -> None:
        for path in self._temp_scripts:
            if path.exists():
                path.unlink()
        self.api.shutdown()

    def _write_temp_script(self, name: str, contents: str, mtime_offset: int = 0) -> str:
        path = Path("scripts") / f"{name}.py"
        path.write_text(contents, encoding="utf-8")
        timestamp = time.time() + mtime_offset
        os.utime(path, (timestamp, timestamp))
        self._temp_scripts.append(path)
        return name

    def test_entity_metadata_and_component_crud(self) -> None:
        created = self.api.create_entity("CameraRig")
        self.assertTrue(created["success"])

        add_camera = self.api.add_component(
            "CameraRig",
            "Camera2D",
            {"enabled": True, "offset_x": 320.0, "offset_y": 180.0, "zoom": 1.5, "is_primary": True},
        )
        self.assertTrue(add_camera["success"])

        self.assertTrue(self.api.set_entity_tag("CameraRig", "MainCamera")["success"])
        self.assertTrue(self.api.set_entity_layer("CameraRig", "Gameplay")["success"])
        self.assertTrue(self.api.set_entity_active("CameraRig", False)["success"])

        entity = self.api.get_entity("CameraRig")
        self.assertEqual(entity["tag"], "MainCamera")
        self.assertEqual(entity["layer"], "Gameplay")
        self.assertFalse(entity["active"])
        self.assertIn("Camera2D", entity["components"])

        self.assertTrue(self.api.remove_component("CameraRig", "Camera2D")["success"])
        entity = self.api.get_entity("CameraRig")
        self.assertNotIn("Camera2D", entity["components"])

    def test_input_audio_and_feature_metadata_are_serializable(self) -> None:
        self.assertTrue(
            self.api.create_input_map(
                "PlayerSettings",
                {"move_left": "A,LEFT", "move_right": "D,RIGHT", "action_1": "SPACE"},
            )["success"]
        )
        self.assertTrue(
            self.api.update_input_map(
                "PlayerSettings",
                {"action_2": "SHIFT"},
            )["success"]
        )
        self.assertTrue(
            self.api.create_audio_source(
                "MusicPlayer",
                audio={"asset_path": "assets/jump.wav", "play_on_awake": True, "volume": 0.5},
            )["success"]
        )
        self.assertTrue(self.api.set_feature_metadata("input_profile", {"source": "code"})["success"])

        entity = self.api.get_entity("PlayerSettings")
        self.assertEqual(entity["components"]["InputMap"]["move_left"], "A,LEFT")
        self.assertEqual(entity["components"]["InputMap"]["action_2"], "SHIFT")
        audio_state = self.api.get_audio_state("MusicPlayer")
        self.assertEqual(audio_state["asset_path"], "assets/jump.wav")
        self.assertEqual(audio_state["asset"]["path"], "assets/jump.wav")
        self.assertEqual(self.api.get_feature_metadata()["input_profile"]["source"], "code")
        self.assertEqual(self.api.get_input_state("PlayerSettings"), {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0})

    def test_component_enablement_round_trip(self) -> None:
        result = self.api.set_component_enabled("Ground", "Collider", False)
        self.assertTrue(result["success"])

        ground = self.api.get_entity("Ground")
        self.assertFalse(ground["components"]["Collider"]["enabled"])

    def test_runtime_ignores_inactive_entities_and_disabled_components(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "ActiveMover",
                {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "velocity_x": 60.0, "velocity_y": 0.0, "gravity_scale": 0.0, "is_grounded": True},
                },
            )["success"]
        )
        self.assertTrue(
            self.api.create_entity(
                "InactiveMover",
                {
                    "Transform": {"enabled": True, "x": 10.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "velocity_x": 60.0, "velocity_y": 0.0, "gravity_scale": 0.0, "is_grounded": True},
                },
            )["success"]
        )
        self.assertTrue(
            self.api.create_entity(
                "DisabledMover",
                {
                    "Transform": {"enabled": True, "x": 20.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "velocity_x": 60.0, "velocity_y": 0.0, "gravity_scale": 0.0, "is_grounded": True},
                },
            )["success"]
        )
        self.assertTrue(self.api.set_entity_active("InactiveMover", False)["success"])
        self.assertTrue(self.api.set_component_enabled("DisabledMover", "RigidBody", False)["success"])

        edit_entities = [entity.name for entity in self.api.game.world.get_entities_with(Transform)]
        self.assertNotIn("InactiveMover", edit_entities)

        self.api.play()
        self.api.step(10)

        active_entity = self.api.get_entity("ActiveMover")
        inactive_entity = self.api.get_entity("InactiveMover")
        disabled_entity = self.api.get_entity("DisabledMover")

        self.assertGreater(active_entity["components"]["Transform"]["x"], 0.0)
        self.assertEqual(inactive_entity["components"]["Transform"]["x"], 10.0)
        self.assertEqual(disabled_entity["components"]["Transform"]["x"], 20.0)

    def test_disabled_optional_components_do_not_drive_selection_bounds(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "SelectionProbe",
                {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "Sprite": {"enabled": False, "texture_path": "", "width": 80, "height": 80, "origin_x": 0.5, "origin_y": 0.5},
                    "Collider": {"enabled": False, "width": 80, "height": 80, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            )["success"]
        )
        entity = self.api.game.world.get_entity_by_name("SelectionProbe")
        selection_system = SelectionSystem()
        self.assertFalse(selection_system._is_point_in_entity(30.0, 0.0, entity))

    def test_script_executor_has_equivalent_commands_for_input_and_audio(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [
            {"action": "CREATE_INPUT_MAP", "args": {"name": "ScriptInput", "bindings": {"action_1": "CTRL"}}},
            {"action": "SET_INPUT_BINDING", "args": {"entity": "ScriptInput", "binding": "move_left", "value": "J"}},
            {"action": "CREATE_AUDIO_SOURCE", "args": {"name": "ScriptAudio", "audio": {"asset_path": "assets/theme.wav", "play_on_awake": True}}},
            {"action": "AUDIO_PLAY", "args": {"entity": "ScriptAudio"}},
        ]

        self.assertTrue(executor.run_all())
        self.assertEqual(self.api.get_entity("ScriptInput")["components"]["InputMap"]["move_left"], "J")
        self.assertEqual(self.api.get_entity("ScriptInput")["components"]["InputMap"]["action_1"], "CTRL")
        self.assertTrue(self.api.get_audio_state("ScriptAudio")["is_playing"])

    def test_script_executor_can_play_a_short_controller_sequence(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [
            {
                "action": "CREATE_ENTITY",
                "args": {
                    "name": "ScriptPlayer",
                },
            },
            {"action": "ADD_COMPONENT", "args": {"entity": "ScriptPlayer", "component": "RigidBody", "data": {"enabled": True, "gravity_scale": 1.0, "is_grounded": True}}},
            {"action": "ADD_COMPONENT", "args": {"entity": "ScriptPlayer", "component": "InputMap", "data": {"enabled": True, "move_left": "A", "move_right": "D", "action_1": "SPACE"}}},
            {"action": "ADD_COMPONENT", "args": {"entity": "ScriptPlayer", "component": "PlayerController2D", "data": {"enabled": True, "move_speed": 180.0, "jump_velocity": -320.0}}},
            {"action": "INSPECT_EDIT", "args": {"entity": "ScriptPlayer", "component": "Transform", "property": "x", "value": 100.0}},
            {"action": "INSPECT_EDIT", "args": {"entity": "ScriptPlayer", "component": "Transform", "property": "y", "value": 500.0}},
            {"action": "PLAY", "args": {}},
            {"action": "INJECT_INPUT", "args": {"entity": "ScriptPlayer", "state": {"horizontal": 1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0}, "frames": 2}},
            {"action": "WAIT", "args": {"frames": 5}},
        ]

        self.assertTrue(executor.run_all())
        player = self.api.get_entity("ScriptPlayer")
        self.assertGreater(player["components"]["Transform"]["x"], 100.0)
        self.assertLess(player["components"]["Transform"]["y"], 500.0)

    def test_scene_manager_accepts_serialized_entity_data_for_shared_authoring(self) -> None:
        created = self.api.scene_manager.create_entity_from_data(
            {
                "name": "DroppedSprite",
                "active": True,
                "tag": "Prop",
                "layer": "Gameplay",
                "components": {
                    "Transform": {"enabled": True, "x": 12.0, "y": 24.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "Sprite": {"enabled": True, "texture_path": "assets/box.png", "width": 0, "height": 0, "origin_x": 0.5, "origin_y": 0.5},
                },
            }
        )
        self.assertTrue(created)

        entity = self.api.get_entity("DroppedSprite")
        self.assertEqual(entity["tag"], "Prop")
        self.assertEqual(entity["layer"], "Gameplay")
        self.assertEqual(entity["components"]["Transform"]["x"], 12.0)
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/box.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/box.png")

    def test_player_controller_moves_and_jumps(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "ControllerPlayer",
                {
                    "Transform": {"enabled": True, "x": 100.0, "y": 500.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "velocity_x": 0.0, "velocity_y": 0.0, "gravity_scale": 1.0, "is_grounded": True},
                    "InputMap": {"enabled": True, "move_left": "A", "move_right": "D", "action_1": "SPACE"},
                    "PlayerController2D": {"enabled": True, "move_speed": 180.0, "jump_velocity": -320.0, "air_control": 0.75},
                },
            )["success"]
        )

        entity = self.api.game.world.get_entity_by_name("ControllerPlayer")
        transform = entity.get_component(Transform)
        rigidbody = entity.get_component(RigidBody)
        input_map = entity.get_component(InputMap)
        start_x = transform.x
        start_y = transform.y

        input_map.last_state = {"horizontal": 1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0}
        self.api.game._player_controller_system.update(self.api.game.world)
        self.api.game._physics_system.update(self.api.game.world, 1.0 / 60.0)

        self.assertGreater(rigidbody.velocity_x, 0.0)
        self.assertLess(rigidbody.velocity_y, 0.0)
        self.assertGreater(transform.x, start_x)
        self.assertLess(transform.y, start_y)

    def test_physics_resolves_platform_collisions_instead_of_crossing_platforms(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "PlatformCollisionPlayer",
                {
                    "Transform": {"enabled": True, "x": 100.0, "y": 160.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "Collider": {"enabled": True, "width": 28.0, "height": 28.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                    "RigidBody": {"enabled": True, "velocity_x": 0.0, "velocity_y": 0.0, "gravity_scale": 1.0, "is_grounded": False},
                },
            )["success"]
        )
        self.assertTrue(
            self.api.create_entity(
                "PlatformCollisionFloor",
                {
                    "Transform": {"enabled": True, "x": 100.0, "y": 220.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "Collider": {"enabled": True, "width": 140.0, "height": 20.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            )["success"]
        )

        self.api.play()
        self.api.step(40)

        player = self.api.game.world.get_entity_by_name("PlatformCollisionPlayer")
        transform = player.get_component(Transform)
        rigidbody = player.get_component(RigidBody)
        collider = player.get_component(Collider)
        floor = self.api.game.world.get_entity_by_name("PlatformCollisionFloor")
        floor_transform = floor.get_component(Transform)
        floor_collider = floor.get_component(Collider)

        player_bottom = transform.y + collider.height / 2
        floor_top = floor_transform.y - floor_collider.height / 2

        self.assertAlmostEqual(player_bottom, floor_top, delta=1.1)
        self.assertTrue(rigidbody.is_grounded)
        self.assertEqual(rigidbody.velocity_y, 0.0)

    def test_platformer_test_scene_switches_animator_state_with_controller_motion(self) -> None:
        self.api.load_level("levels/platformer_test_scene.json")
        player = self.api.game.world.get_entity_by_name("Player")
        rigidbody = player.get_component(RigidBody)
        input_map = player.get_component(InputMap)
        animator = player.get_component(Animator)

        rigidbody.is_grounded = True
        input_map.last_state = {"horizontal": 1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}
        self.api.game._player_controller_system.update(self.api.game.world)
        self.assertEqual(animator.current_state, "run")
        self.assertFalse(animator.flip_x)

        input_map.last_state = {"horizontal": -1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}
        self.api.game._player_controller_system.update(self.api.game.world)
        self.assertEqual(animator.current_state, "run")
        self.assertTrue(animator.flip_x)

        rigidbody.is_grounded = False
        rigidbody.velocity_y = -50.0
        input_map.last_state = {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}
        self.api.game._player_controller_system.update(self.api.game.world)
        self.assertEqual(animator.current_state, "jump")
        self.assertTrue(animator.flip_x)

    def test_animator_flip_x_round_trips_through_serialization(self) -> None:
        animator = Animator.from_dict(
            {
                "sprite_sheet": "assets/player.png",
                "frame_width": 32,
                "frame_height": 32,
                "flip_x": True,
                "animations": {"idle": {"frames": [0], "fps": 8.0, "loop": True}},
                "default_state": "idle",
                "current_state": "idle",
            }
        )
        self.assertTrue(animator.flip_x)
        self.assertTrue(animator.to_dict()["flip_x"])
        self.assertEqual(animator.to_dict()["sprite_sheet"]["path"], "assets/player.png")

    def test_tag_layer_filters_and_camera_helpers_use_serializable_data(self) -> None:
        created = self.api.create_camera2d(
            "MainCamera",
            transform={"x": 128.0, "y": 64.0},
            camera={"offset_x": 320.0, "offset_y": 180.0, "zoom": 2.0, "follow_entity": "Player"},
        )
        self.assertTrue(created["success"])
        self.assertTrue(self.api.set_entity_tag("MainCamera", "MainCamera")["success"])
        self.assertTrue(self.api.set_entity_layer("MainCamera", "Gameplay")["success"])

        filtered = self.api.list_entities(tag="MainCamera", layer="Gameplay", active=True)
        self.assertEqual([entity["name"] for entity in filtered], ["MainCamera"])

        primary = self.api.get_primary_camera()
        self.assertIsNotNone(primary)
        self.assertEqual(primary["name"], "MainCamera")

        render_system = RenderSystem()
        camera = render_system._build_camera_from_world(self.api.game.world, viewport_size=(640.0, 360.0))
        self.assertIsNotNone(camera)

        player = self.api.game.world.get_entity_by_name("Player")
        player_transform = player.get_component(Transform)
        self.assertEqual(camera.target.x, player_transform.x)
        self.assertLess(camera.target.y, player_transform.y)
        self.assertEqual(camera.offset.x, 320.0)
        self.assertEqual(camera.offset.y, 180.0)
        self.assertEqual(camera.zoom, 2.0)

        scene_entity = self.api.scene_manager.current_scene.find_entity("MainCamera")
        self.assertEqual(scene_entity["tag"], "MainCamera")
        self.assertEqual(scene_entity["layer"], "Gameplay")
        self.assertEqual(scene_entity["components"]["Camera2D"]["follow_entity"], "Player")

    def test_script_behaviour_round_trip_and_api_public_data(self) -> None:
        self.assertTrue(self.api.create_entity("ScriptedActor")["success"])
        self.assertTrue(
            self.api.add_script_behaviour(
                "ScriptedActor",
                "platformer_character",
                {"health": 3},
                run_in_edit_mode=False,
            )["success"]
        )

        entity = self.api.get_entity("ScriptedActor")
        self.assertEqual(entity["components"]["ScriptBehaviour"]["module_path"], "platformer_character")
        self.assertEqual(entity["components"]["ScriptBehaviour"]["script"]["path"], "")
        self.assertEqual(entity["components"]["ScriptBehaviour"]["public_data"]["health"], 3)

        self.assertTrue(self.api.set_script_public_data("ScriptedActor", {"health": 5, "coins": 2})["success"])
        self.assertEqual(self.api.get_script_public_data("ScriptedActor")["coins"], 2)

    def test_script_behaviour_missing_module_does_not_crash(self) -> None:
        self.assertTrue(self.api.create_entity("MissingScriptEntity")["success"])
        self.assertTrue(self.api.add_script_behaviour("MissingScriptEntity", "missing_script_module")["success"])

        self.api.play()
        self.api.step(1)

        self.assertTrue(self.api.game.is_play_mode)
        self.assertTrue(any("missing_script_module" in message for _, message in GLOBAL_LOGS))

    def test_script_behaviour_hook_exception_logs_and_continues(self) -> None:
        module_name = self._write_temp_script(
            "temp_script_error",
            "def on_update(context, dt):\n"
            "    raise RuntimeError('boom')\n",
            mtime_offset=2,
        )
        self.assertTrue(self.api.create_entity("ErrorScriptEntity")["success"])
        self.assertTrue(self.api.add_script_behaviour("ErrorScriptEntity", module_name)["success"])

        self.api.play()
        self.api.step(1)

        self.assertTrue(self.api.game.is_play_mode)
        self.assertTrue(any("boom" in message for _, message in GLOBAL_LOGS))

    def test_script_behaviour_public_data_persists_across_hot_reload(self) -> None:
        module_name = self._write_temp_script(
            "temp_script_reload",
            "def on_play(context):\n"
            "    context.public_data['count'] = context.public_data.get('count', 0) + 1\n"
            "    context.public_data['version'] = 1\n"
            "\n"
            "def on_update(context, dt):\n"
            "    context.public_data['count'] = context.public_data.get('count', 0) + 1\n",
            mtime_offset=2,
        )
        self.assertTrue(self.api.create_entity("ReloadScriptEntity")["success"])
        self.assertTrue(self.api.add_script_behaviour("ReloadScriptEntity", module_name, {"count": 0})["success"])

        self.api.play()
        self.api.step(1)
        first_data = self.api.get_script_public_data("ReloadScriptEntity")
        self.assertEqual(first_data["version"], 1)
        self.assertGreaterEqual(first_data["count"], 2)

        self._write_temp_script(
            module_name,
            "def on_play(context):\n"
            "    context.public_data['version'] = 2\n"
            "\n"
            "def on_update(context, dt):\n"
            "    context.public_data['count'] = context.public_data.get('count', 0) + 10\n"
            "    context.public_data['version'] = 2\n",
            mtime_offset=4,
        )

        self.api.step(1)
        second_data = self.api.get_script_public_data("ReloadScriptEntity")
        self.assertEqual(second_data["version"], 2)
        self.assertGreater(second_data["count"], first_data["count"])

    def test_script_behaviour_run_in_edit_mode(self) -> None:
        module_name = self._write_temp_script(
            "temp_script_edit_mode",
            "def on_update(context, dt):\n"
            "    context.public_data['edit_ticks'] = context.public_data.get('edit_ticks', 0) + 1\n",
            mtime_offset=2,
        )
        self.assertTrue(self.api.create_entity("EditScriptEntity")["success"])
        self.assertTrue(
            self.api.add_script_behaviour(
                "EditScriptEntity",
                module_name,
                {"edit_ticks": 0},
                run_in_edit_mode=True,
            )["success"]
        )

        self.api.step(2)
        self.assertGreaterEqual(self.api.get_script_public_data("EditScriptEntity")["edit_ticks"], 2)

    def test_selection_persists_from_edit_to_play_and_back(self) -> None:
        self.assertTrue(self.api.scene_manager.set_selected_entity("Player"))
        self.assertEqual(self.api.game.world.selected_entity_name, "Player")

        self.api.play()
        self.assertEqual(self.api.game.world.selected_entity_name, "Player")

        self.api.stop()
        self.assertEqual(self.api.game.world.selected_entity_name, "Player")
        self.assertEqual(self.api.scene_manager.get_edit_world().selected_entity_name, "Player")

    def test_selection_system_returns_clicked_entity_name(self) -> None:
        selection_system = SelectionSystem()
        player = self.api.game.world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        self.assertIsNotNone(transform)

        with patch("pyray.is_mouse_button_pressed", return_value=True):
            selected_name = selection_system.update(self.api.game.world, rl.Vector2(transform.x, transform.y))

        self.assertEqual(selected_name, "Player")
        self.assertEqual(self.api.game.world.selected_entity_name, "Player")

    def test_camera_platformer_framing_recenters_and_clamps(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "CameraFollowTarget",
                {
                    "Transform": {"enabled": True, "x": 100.0, "y": 200.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                },
            )["success"]
        )
        self.assertTrue(
            self.api.create_camera2d(
                "FollowCamera",
                transform={"x": 0.0, "y": 0.0},
                camera={
                    "offset_x": 320.0,
                    "offset_y": 180.0,
                    "follow_entity": "CameraFollowTarget",
                    "dead_zone_width": 100.0,
                    "dead_zone_height": 60.0,
                    "clamp_left": 90.0,
                    "clamp_right": 150.0,
                    "clamp_top": 100.0,
                    "clamp_bottom": 180.0,
                    "recenter_on_play": True,
                },
            )["success"]
        )
        render_system = RenderSystem()
        first_camera = render_system._build_camera_from_world(self.api.game.world, viewport_size=(640.0, 360.0))
        self.assertEqual(first_camera.target.x, 100.0)
        self.assertAlmostEqual(first_camera.target.y, 156.8, places=1)

        target_entity = self.api.game.world.get_entity_by_name("CameraFollowTarget")
        target_transform = target_entity.get_component(Transform)
        target_transform.x = 240.0
        target_transform.y = 260.0

        second_camera = render_system._build_camera_from_world(self.api.game.world, viewport_size=(640.0, 360.0))
        self.assertEqual(second_camera.target.x, 150.0)
        self.assertLessEqual(second_camera.target.y, 180.0)
        self.assertGreaterEqual(second_camera.target.y, 100.0)


if __name__ == "__main__":
    unittest.main()
