import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.inputmap import InputMap
from engine.components.mobile_controls_2d import MobileControls2D
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.mobile_controls_system import MobileControlsSystem
from motor.cli import run_motor_command


class MobileControlsComponentTests(unittest.TestCase):
    def test_mobile_controls_roundtrip(self) -> None:
        component = MobileControls2D(
            target_entity="Hero",
            profile="dual_action",
            left_stick_radius=96.0,
            opacity=0.5,
            deadzone=0.25,
        )

        restored = MobileControls2D.from_dict(component.to_dict())

        self.assertEqual(restored.target_entity, "Hero")
        self.assertEqual(restored.profile, "dual_action")
        self.assertEqual(restored.left_stick_radius, 96.0)
        self.assertEqual(restored.opacity, 0.5)
        self.assertEqual(restored.deadzone, 0.25)

    def test_mobile_controls_registered(self) -> None:
        registry = create_default_registry()

        self.assertIs(registry.get("MobileControls2D"), MobileControls2D)


class MobileControlsSystemTests(unittest.TestCase):
    def _make_world(self) -> tuple[World, InputMap]:
        world = World()
        player = world.create_entity("Player")
        input_map = InputMap()
        player.add_component(input_map)
        overlay = world.create_entity("MobileControlsOverlay")
        overlay.add_component(MobileControls2D(target_entity="Player"))
        return world, input_map

    def test_left_stick_updates_axis(self) -> None:
        world, input_map = self._make_world()
        system = MobileControlsSystem()

        system.inject_pointer_state(174.0, 398.0, down=True)
        system.update(world, (800.0, 600.0))

        self.assertGreater(input_map.last_state["horizontal"], 0.3)
        self.assertGreater(input_map.last_state["vertical"], 0.3)

    def test_action_buttons_update_actions(self) -> None:
        world, input_map = self._make_world()
        system = MobileControlsSystem()

        system.inject_pointer_state(672.0, 468.0, down=True)
        system.update(world, (800.0, 600.0))
        self.assertEqual(input_map.last_state["action_1"], 1.0)

        system.inject_pointer_state(576.0, 504.0, down=True)
        system.update(world, (800.0, 600.0))
        self.assertEqual(input_map.last_state["action_2"], 1.0)

    def test_release_resets_mobile_state(self) -> None:
        world, input_map = self._make_world()
        system = MobileControlsSystem()

        system.inject_pointer_state(672.0, 468.0, down=True)
        system.update(world, (800.0, 600.0))
        system.inject_pointer_state(672.0, 468.0, released=True)
        system.update(world, (800.0, 600.0))

        self.assertEqual(input_map.last_state["action_1"], 0.0)
        self.assertEqual(input_map.last_state["horizontal"], 0.0)

    def test_left_stick_drag_stays_captured_outside_visible_radius(self) -> None:
        world, input_map = self._make_world()
        system = MobileControlsSystem()

        system.inject_pointer_state(128.0, 468.0, down=True)
        system.update(world, (800.0, 600.0))
        system.inject_pointer_state(280.0, 468.0, down=True)
        system.update(world, (800.0, 600.0))

        self.assertGreater(input_map.last_state["horizontal"], 0.95)
        self.assertEqual(input_map.last_state["vertical"], 0.0)


class MobileControlsAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp.name) / "Project"
        self.api = EngineAPI(project_root=self.project_root.as_posix())
        self.scene_path = self.project_root / "levels" / "mobile_scene.json"
        self.scene_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_path.write_text(
            json.dumps({"name": "Mobile Scene", "entities": [], "rules": [], "feature_metadata": {}}),
            encoding="utf-8",
        )
        self.api.load_scene(self.scene_path.as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self.tmp.cleanup()

    def test_create_mobile_controls_is_idempotent(self) -> None:
        first = self.api.create_mobile_controls(target_entity="Player")
        second = self.api.create_mobile_controls(target_entity="Player")

        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertTrue(first["data"]["created"])
        self.assertFalse(second["data"]["created"])
        overlays = [
            entity
            for entity in self.api.list_entities(active=None)
            if "MobileControls2D" in entity.get("components", {})
        ]
        self.assertEqual(len(overlays), 1)

    def test_mobile_controls_cli_add_saves_scene(self) -> None:
        self.api.save_editor_state({"last_scene": self.scene_path.as_posix()})
        self.api.shutdown()

        code = run_motor_command(
            [
                "mobile",
                "controls",
                "add",
                "--target",
                "Player",
                "--profile",
                "platformer",
                "--project",
                self.project_root.as_posix(),
                "--json",
            ]
        )

        self.assertEqual(code, 0)
        raw = json.loads(self.scene_path.read_text(encoding="utf-8"))
        overlays = [
            entity
            for entity in raw["entities"]
            if "MobileControls2D" in entity.get("components", {})
        ]
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0]["components"]["MobileControls2D"]["target_entity"], "Player")

    def test_mobile_controls_cli_add_can_target_scene_path(self) -> None:
        other_scene = self.project_root / "levels" / "android_scene.json"
        other_scene.write_text(
            json.dumps({"name": "Android Scene", "entities": [], "rules": [], "feature_metadata": {}}),
            encoding="utf-8",
        )
        self.api.shutdown()

        code = run_motor_command(
            [
                "mobile",
                "controls",
                "add",
                "--scene",
                "levels/android_scene.json",
                "--target",
                "Player",
                "--profile",
                "platformer",
                "--project",
                self.project_root.as_posix(),
                "--json",
            ]
        )

        self.assertEqual(code, 0)
        raw = json.loads(other_scene.read_text(encoding="utf-8"))
        overlays = [
            entity
            for entity in raw["entities"]
            if "MobileControls2D" in entity.get("components", {})
        ]
        self.assertEqual(len(overlays), 1)
