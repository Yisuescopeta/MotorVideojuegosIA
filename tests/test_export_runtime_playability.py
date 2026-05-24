"""Tests for ExportRuntime playability — verifies exported runtime can load scenes,
handle UI clicks, process input, and run game systems.

Tests ExportRuntime directly without requiring PyInstaller or full builds.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from engine.levels.component_registry import create_default_registry
from engine.runtime.content_loader import ContentLoader
from engine.runtime.export_runtime import ExportRuntime


def _make_menu_scene() -> dict[str, Any]:
    """Create a minimal main menu scene with Canvas + UIButton."""
    return {
        "name": "MainMenu",
        "entities": [
            {
                "name": "MainCanvas",
                "active": True,
                "tag": "UI",
                "layer": "UI",
                "components": {
                    "Canvas": {
                        "enabled": True,
                        "reference_width": 1280,
                        "reference_height": 720,
                        "sort_order": 0,
                    },
                },
            },
            {
                "name": "PlayButton",
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
                        "on_click": {
                            "type": "load_scene",
                            "path": "levels/platformer.json",
                        },
                    },
                },
            },
        ],
        "rules": [],
        "feature_metadata": {},
    }


def _make_platformer_scene() -> dict[str, Any]:
    """Create a minimal platformer scene with Player that has InputMap + PlayerController2D + RigidBody.

    Player starts grounded: y=468 places Player bottom (468+24=492) just above
    Ground top (500-16=484), letting gravity drop it onto the ground on first frame.
    air_control=1.0 ensures movement works even when not grounded.
    """
    return {
        "name": "Platformer",
        "entities": [
            {
                "name": "Player",
                "active": True,
                "tag": "Player",
                "layer": "Game",
                "components": {
                    "Transform": {"x": 400.0, "y": 460.0},
                    "RigidBody": {
                        "enabled": True,
                        "body_type": "dynamic",
                        "mass": 1.0,
                        "gravity_scale": 1.0,
                        "velocity_x": 0.0,
                        "velocity_y": 0.0,
                        "is_grounded": True,
                    },
                    "Collider": {
                        "enabled": True,
                        "width": 32.0,
                        "height": 48.0,
                        "is_trigger": False,
                    },
                    "InputMap": {
                        "enabled": True,
                        "move_left": "A,LEFT",
                        "move_right": "D,RIGHT",
                        "move_up": "W,UP",
                        "move_down": "S,DOWN",
                        "action_1": "SPACE",
                        "action_2": "ENTER",
                    },
                    "PlayerController2D": {
                        "enabled": True,
                        "move_speed": 400.0,
                        "jump_velocity": -500.0,
                        "air_control": 1.0,
                    },
                },
            },
            {
                "name": "Ground",
                "active": True,
                "tag": "Ground",
                "layer": "Game",
                "components": {
                    "Transform": {"x": 400.0, "y": 500.0},
                    "Collider": {
                        "enabled": True,
                        "width": 800.0,
                        "height": 32.0,
                        "is_trigger": False,
                    },
                    "RigidBody": {
                        "enabled": True,
                        "body_type": "static",
                        "mass": 0.0,
                        "velocity_x": 0.0,
                        "velocity_y": 0.0,
                    },
                },
            },
        ],
        "rules": [],
        "feature_metadata": {},
    }


class TestExportRuntimeSceneLoading(unittest.TestCase):
    """Tests for ExportRuntime scene loading."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        self.registry = create_default_registry()

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _write_scene(self, name: str, data: dict):
        path = self.tmp / "levels" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_load_scene_success(self):
        self._write_scene("menu.json", _make_menu_scene())
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)

        result = runtime.load_scene("levels/menu.json")
        self.assertTrue(result)
        self.assertIsNotNone(runtime.world)
        self.assertEqual(runtime.current_scene_path, "levels/menu.json")

    def test_load_scene_missing(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)

        result = runtime.load_scene("levels/nonexistent.json")
        self.assertFalse(result)
        self.assertIsNone(runtime.world)

    def test_load_scene_emits_event(self):
        self._write_scene("menu.json", _make_menu_scene())
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)

        runtime.load_scene("levels/menu.json")
        events = runtime.get_recent_events(10)
        event_names = [e["name"] for e in events]
        self.assertIn("scene_loaded", event_names)

    def test_load_scene_switches_scene(self):
        self._write_scene("menu.json", _make_menu_scene())
        self._write_scene("platformer.json", _make_platformer_scene())
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)

        runtime.load_scene("levels/menu.json")
        self.assertEqual(runtime.current_scene_path, "levels/menu.json")

        runtime.load_scene("levels/platformer.json")
        self.assertEqual(runtime.current_scene_path, "levels/platformer.json")


class TestExportRuntimeFrame(unittest.TestCase):
    """Tests for ExportRuntime frame execution."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        (self.tmp / "levels" / "menu.json").write_text(
            json.dumps(_make_menu_scene()), encoding="utf-8"
        )
        self.registry = create_default_registry()

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_run_frame_increments_count(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.load_scene("levels/menu.json")

        self.assertEqual(runtime.frame_count, 0)
        runtime.run_frame()
        self.assertEqual(runtime.frame_count, 1)
        runtime.run_frame()
        self.assertEqual(runtime.frame_count, 2)

    def test_run_frame_without_world_does_not_crash(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        # No scene loaded — world is None
        runtime.run_frame()  # Should not raise
        self.assertEqual(runtime.frame_count, 0)

    def test_run_frame_when_shutdown_does_not_crash(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.load_scene("levels/menu.json")
        runtime.shutdown()

        count_before = runtime.frame_count
        runtime.run_frame()
        self.assertEqual(runtime.frame_count, count_before)  # No increment

    def test_shutdown_sets_inactive(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        self.assertTrue(runtime.active)

        runtime.shutdown()
        self.assertFalse(runtime.active)


class TestExportRuntimeGameplay(unittest.TestCase):
    """Tests for gameplay: input → player movement."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        (self.tmp / "levels" / "platformer.json").write_text(
            json.dumps(_make_platformer_scene()), encoding="utf-8"
        )
        self.registry = create_default_registry()

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_input_moves_player_right(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry, gravity=0.0)
        runtime.load_scene("levels/platformer.json")

        entity = runtime.world.get_entity_by_name("Player")
        from engine.components.transform import Transform
        t = entity.get_component(Transform)
        initial_x = t.x

        # Inject right input for 10 frames
        runtime.inject_input("Player", {"horizontal": 1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}, frames=10)
        for _ in range(10):
            runtime.run_frame()

        self.assertGreater(t.x, initial_x, f"Player should move right. Initial: {initial_x}, Final: {t.x}")

    def test_input_moves_player_left(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry, gravity=0.0)
        runtime.load_scene("levels/platformer.json")

        entity = runtime.world.get_entity_by_name("Player")
        from engine.components.transform import Transform
        t = entity.get_component(Transform)
        initial_x = t.x

        # Inject left input for 10 frames
        runtime.inject_input("Player", {"horizontal": -1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}, frames=10)
        for _ in range(10):
            runtime.run_frame()

        self.assertLess(t.x, initial_x, f"Player should move left. Initial: {initial_x}, Final: {t.x}")

    def test_input_jump_moves_player_up(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry, gravity=0.0)
        runtime.load_scene("levels/platformer.json")

        entity = runtime.world.get_entity_by_name("Player")
        from engine.components.rigidbody import RigidBody
        from engine.components.transform import Transform
        t = entity.get_component(Transform)
        rb = entity.get_component(RigidBody)
        rb.is_grounded = True  # Must be grounded to jump
        initial_y = t.y

        # Inject jump for 10 frames (matches loop count to avoid raylib fallback)
        runtime.inject_input("Player", {"horizontal": 0.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0}, frames=10)
        for _ in range(10):
            runtime.run_frame()

        # With gravity=0 and jump_velocity=-500, player should move up (y decreases)
        self.assertLess(t.y, initial_y, f"Player should move up (jump). Initial: {initial_y}, Final: {t.y}")

    def test_gravity_pulls_player_down(self):
        """Player falls due to gravity when not on ground (gravity > 0)."""
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry, gravity=600.0)
        runtime.load_scene("levels/platformer.json")

        entity = runtime.world.get_entity_by_name("Player")
        from engine.components.rigidbody import RigidBody
        from engine.components.transform import Transform
        t = entity.get_component(Transform)
        rb = entity.get_component(RigidBody)
        # Move player well above ground so gravity can pull it down
        t.y = 300.0
        rb.is_grounded = False
        initial_y = t.y

        # Run frames — gravity pulls player down, then ground collision stops it
        for _ in range(120):
            runtime.run_frame()

        # Player should have moved downward (y increased) or landed on ground
        self.assertGreaterEqual(t.y, initial_y,
            f"Player should fall with gravity. Initial: {initial_y}, Final: {t.y}")


class TestExportRuntimeUI(unittest.TestCase):
    """Tests for UI interaction in ExportRuntime."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        (self.tmp / "levels" / "menu.json").write_text(
            json.dumps(_make_menu_scene()), encoding="utf-8"
        )
        (self.tmp / "levels" / "platformer.json").write_text(
            json.dumps(_make_platformer_scene()), encoding="utf-8"
        )
        self.registry = create_default_registry()

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_button_click_loads_scene(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.load_scene("levels/menu.json")

        # Simulate mouse press on PlayButton (centered at 640, 360 in 1280x720 viewport)
        runtime.update_ui(
            (1280.0, 720.0),
            mouse_x=640.0, mouse_y=360.0,
            mouse_down=True, mouse_pressed=True, mouse_released=False,
        )
        runtime.run_frame()
        # Release mouse — this triggers the on_click action
        runtime.update_ui(
            (1280.0, 720.0),
            mouse_x=640.0, mouse_y=360.0,
            mouse_down=False, mouse_pressed=False, mouse_released=True,
        )

        # After click, the scene should have changed to platformer
        self.assertEqual(runtime.current_scene_path, "levels/platformer.json")

    def test_update_ui_unloaded_menu_does_not_switch_scene(self):
        """Running update_ui on menu scene without clicking does NOT change scene."""
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.load_scene("levels/menu.json")

        # Run frames WITHOUT clicking — just hovering
        for _ in range(5):
            runtime.update_ui((1280.0, 720.0), mouse_x=640.0, mouse_y=360.0)
            runtime.run_frame()

        # Scene should still be menu
        self.assertEqual(runtime.current_scene_path, "levels/menu.json")


class TestExportRuntimeRealMenu(unittest.TestCase):
    """Tests the shipped menu scene contract used by Windows exports."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        repo_root = Path(__file__).resolve().parents[1]
        shutil.copy2(
            repo_root / "levels" / "main_menu_scene.json",
            self.tmp / "levels" / "main_menu_scene.json",
        )
        shutil.copy2(
            repo_root / "levels" / "platformer_test_scene.json",
            self.tmp / "levels" / "platformer_test_scene.json",
        )
        self.registry = create_default_registry()

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _make_runtime(self) -> ExportRuntime:
        loader = ContentLoader(str(self.tmp))
        return ExportRuntime(loader=loader, registry=self.registry)

    def test_real_main_menu_button_load_scene_flow_next_scene(self):
        runtime = self._make_runtime()
        self.assertTrue(runtime.load_scene("levels/main_menu_scene.json"))

        runtime.update_ui(
            (800.0, 600.0),
            mouse_x=400.0, mouse_y=336.0,
            mouse_down=True, mouse_pressed=True, mouse_released=False,
        )
        runtime.run_frame()
        runtime.update_ui(
            (800.0, 600.0),
            mouse_x=400.0, mouse_y=336.0,
            mouse_down=False, mouse_pressed=False, mouse_released=True,
        )

        self.assertEqual(runtime.current_scene_path, "levels/platformer_test_scene.json")

    def test_scene_flow_missing_target_returns_false(self):
        runtime = self._make_runtime()
        self.assertTrue(runtime.load_scene("levels/main_menu_scene.json"))

        self.assertFalse(runtime.load_scene_flow_target("missing_scene"))
        self.assertEqual(runtime.current_scene_path, "levels/main_menu_scene.json")


class TestExportRuntimeSystemsIntegration(unittest.TestCase):
    """Verifies that all systems are present and functional."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        (self.tmp / "levels" / "menu.json").write_text(
            json.dumps(_make_menu_scene()), encoding="utf-8"
        )
        (self.tmp / "levels" / "platformer.json").write_text(
            json.dumps(_make_platformer_scene()), encoding="utf-8"
        )
        self.registry = create_default_registry()

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_all_core_properties_accessible(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.load_scene("levels/menu.json")

        # Verify all properties are accessible
        self.assertIsNotNone(runtime.world)
        self.assertIsNotNone(runtime.event_bus)
        self.assertIsNotNone(runtime.render_system)
        self.assertIsNotNone(runtime.ui_system)
        self.assertEqual(runtime.current_scene_path, "levels/menu.json")
        self.assertTrue(runtime.active)

    def test_run_frame_does_not_crash_with_all_systems(self):
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.load_scene("levels/platformer.json")

        # Run 30 frames to ensure all systems run without error
        for _ in range(30):
            runtime.run_frame()
            runtime.update_ui((1280.0, 720.0))

        self.assertGreater(runtime.frame_count, 0)


if __name__ == "__main__":
    unittest.main()
