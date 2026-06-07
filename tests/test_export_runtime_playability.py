"""Tests for ExportRuntime playability — verifies exported runtime can load scenes,
handle UI clicks, process input, and run game systems.

Tests ExportRuntime directly without requiring PyInstaller or full builds.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


class TestExportRuntimePackedScripts(unittest.TestCase):
    """Tests exported runtime imports ScriptBehaviour modules packed inside game.pak."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.registry = create_default_registry()
        self.module_name = "pak_script_probe_for_export_runtime"

    def tearDown(self):
        sys.modules.pop(self.module_name, None)
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _write_pak(self) -> None:
        scene_path = "levels/main.json"
        script_path = f"scripts/{self.module_name}.py"
        scene = {
            "name": "PackedScriptScene",
            "entities": [
                {
                    "name": "Player",
                    "active": True,
                    "tag": "Player",
                    "components": {
                        "ScriptBehaviour": {
                            "enabled": True,
                            "module_path": script_path,
                            "run_in_edit_mode": False,
                            "public_data": {},
                        },
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        scene_bytes = json.dumps(scene, ensure_ascii=True).encode("utf-8")
        script_bytes = (
            b"def on_update(context, dt):\n"
            b"    context.public_data['packed_updates'] = context.public_data.get('packed_updates', 0) + 1\n"
        )
        manifest = {
            "schema_version": 1,
            "entry_scene": scene_path,
            "project": {"name": "PackedScriptTest", "version": "0.1.0"},
            "assets": [],
            "scenes": [
                {
                    "guid": "scene",
                    "path": scene_path,
                    "kind": "scene",
                    "sha256": _sha256_bytes(scene_bytes),
                    "size_bytes": len(scene_bytes),
                    "dependencies": [script_path],
                }
            ],
            "scripts": [
                {
                    "guid": "script",
                    "path": script_path,
                    "kind": "script",
                    "sha256": _sha256_bytes(script_bytes),
                    "size_bytes": len(script_bytes),
                    "dependencies": [],
                }
            ],
        }
        with zipfile.ZipFile(self.tmp / "game.pak", "w", compression=zipfile.ZIP_DEFLATED) as pak:
            pak.writestr("game.manifest.json", json.dumps(manifest, ensure_ascii=True))
            pak.writestr(scene_path, scene_bytes)
            pak.writestr(script_path, script_bytes)

    def test_script_behaviour_imports_module_from_game_pak(self):
        self._write_pak()
        before_paths = set(sys.path)
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)

        try:
            runtime.setup_scripts_path()
            self.assertTrue(runtime.load_scene("levels/main.json"))
            runtime.run_frame()

            from engine.components.scriptbehaviour import ScriptBehaviour

            player = runtime.world.get_entity_by_name("Player")
            script = player.get_component(ScriptBehaviour)
            self.assertEqual(script.public_data["packed_updates"], 1)
        finally:
            sys.modules.pop(self.module_name, None)
            for path in list(sys.path):
                if path not in before_paths:
                    sys.path.remove(path)


class TestExportRuntimeSystemParity(unittest.TestCase):
    """Tests export does not run editor-absent semantic pickup logic."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        self.registry = create_default_registry()

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_collectible_without_script_is_not_destroyed_by_export_only_system(self):
        scene = {
            "name": "CoinScene",
            "entities": [
                {
                    "name": "Player",
                    "active": True,
                    "tag": "Player",
                    "components": {
                        "Transform": {"x": 100.0, "y": 100.0},
                        "Collider": {
                            "enabled": True,
                            "width": 32.0,
                            "height": 32.0,
                            "is_trigger": False,
                        },
                    },
                },
                {
                    "name": "Coin",
                    "active": True,
                    "tag": "Collectible",
                    "components": {
                        "Transform": {"x": 100.0, "y": 100.0},
                        "Collider": {
                            "enabled": True,
                            "width": 16.0,
                            "height": 16.0,
                            "is_trigger": True,
                        },
                        "Collectible2D": {
                            "enabled": True,
                            "points": 7,
                            "destroy_on_collect": True,
                            "event_name": "coin_collected",
                        },
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        (self.tmp / "levels" / "coin.json").write_text(json.dumps(scene), encoding="utf-8")
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)

        self.assertTrue(runtime.load_scene("levels/coin.json"))
        runtime.run_frame()

        event_names = [event["name"] for event in runtime.get_recent_events(20)]
        self.assertNotIn("coin_collected", event_names)
        self.assertIsNotNone(runtime.world.get_entity_by_name("Coin"))


class TestExportRuntimeScriptedPickups(unittest.TestCase):
    """Tests scripted pickup effects run in exported runtime before pickup removal."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True)
        (self.tmp / "scripts").mkdir(parents=True)
        self.registry = create_default_registry()

    def tearDown(self):
        sys.modules.pop("scripted_pickup_probe", None)
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_scripted_pickup_applies_score_effect(self):
        (self.tmp / "scripts" / "scripted_pickup_probe.py").write_text(
            "\n".join(
                [
                    "def on_update(context, dt):",
                    "    player = context.get_entity()",
                    "    pt = player.get_component_by_name('Transform')",
                    "    for entity in list(context.world.iter_all_entities()):",
                    "        if entity.name == player.name:",
                    "            continue",
                    "        collectible = entity.get_component_by_name('Collectible2D')",
                    "        transform = entity.get_component_by_name('Transform')",
                    "        if collectible is None or transform is None:",
                    "            continue",
                    "        if abs(transform.x - pt.x) <= 16 and abs(transform.y - pt.y) <= 16:",
                    "            context.public_data['score'] = context.public_data.get('score', 0) + collectible.points",
                    "            context.world.destroy_entity(entity.id)",
                    "            break",
                ]
            ),
            encoding="utf-8",
        )
        scene = {
            "name": "ScriptedPickupScene",
            "entities": [
                {
                    "name": "Player",
                    "active": True,
                    "tag": "Player",
                    "components": {
                        "Transform": {"x": 100.0, "y": 100.0},
                        "Collider": {"enabled": True, "width": 32.0, "height": 32.0, "is_trigger": False},
                        "ScriptBehaviour": {
                            "enabled": True,
                            "module_path": "scripts/scripted_pickup_probe.py",
                            "run_in_edit_mode": False,
                            "public_data": {"score": 0},
                        },
                    },
                },
                {
                    "name": "Coin",
                    "active": True,
                    "tag": "Collectible",
                    "components": {
                        "Transform": {"x": 100.0, "y": 100.0},
                        "Collider": {"enabled": True, "width": 16.0, "height": 16.0, "is_trigger": True},
                        "Collectible2D": {"enabled": True, "points": 9, "destroy_on_collect": True},
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        (self.tmp / "levels" / "scripted_pickup.json").write_text(json.dumps(scene), encoding="utf-8")
        loader = ContentLoader(str(self.tmp))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        before_paths = set(sys.path)

        try:
            runtime.setup_scripts_path()
            self.assertTrue(runtime.load_scene("levels/scripted_pickup.json"))
            runtime.run_frame()

            from engine.components.scriptbehaviour import ScriptBehaviour

            player = runtime.world.get_entity_by_name("Player")
            script = player.get_component(ScriptBehaviour)
            self.assertEqual(script.public_data["score"], 9)
            self.assertIsNone(runtime.world.get_entity_by_name("Coin"))
        finally:
            for path in list(sys.path):
                if path not in before_paths:
                    sys.path.remove(path)


class TestRPGAndroidRuntimeParity(unittest.TestCase):
    """Regression coverage for RPG Animator state through Android shared runtime path."""

    repo_root = Path(__file__).resolve().parents[1]
    project_root = repo_root / "projects" / "RPG"

    def setUp(self):
        self.registry = create_default_registry()
        self._before_paths = set(sys.path)

    def tearDown(self):
        sys.modules.pop("player", None)
        for path in list(sys.path):
            if path not in self._before_paths:
                sys.path.remove(path)

    @unittest.skipUnless(project_root.exists(), "RPG project not present at projects/RPG")
    def test_rpg_shared_runtime_advances_idle_and_mobile_walk_animation(self):
        from engine.runtime.shared_game_runtime import SharedGameRuntime

        runtime = SharedGameRuntime(
            loader=ContentLoader(self.project_root),
            registry=self.registry,
            window_config={"width": 844, "height": 390},
        )
        runtime.setup_scripts_path()
        try:
            self.assertTrue(runtime.load_scene("levels/main_scene.json"))
            for _ in range(10):
                runtime.run_frame(1.0 / 60.0)

            player = runtime.world.get_entity_by_name("Player")
            animator = player.get_component_by_name("Animator")
            self.assertEqual(animator.current_state, "idle_down")
            self.assertGreater(animator.current_frame, 0)

            self.assertTrue(runtime.load_scene("levels/main_scene.json"))
            for frame in range(20):
                runtime.run_frame(
                    1.0 / 60.0,
                    pointer_state={
                        "x": 80.0,
                        "y": 304.0,
                        "down": True,
                        "pressed": frame == 0,
                        "released": False,
                        "frames": 1,
                    },
                )

            player = runtime.world.get_entity_by_name("Player")
            animator = player.get_component_by_name("Animator")
            transform = player.get_component_by_name("Transform")
            input_map = player.get_component_by_name("InputMap")
            self.assertEqual(animator.current_state, "walk_side")
            self.assertGreater(animator.current_frame, 0)
            self.assertTrue(animator.flip_x)
            self.assertLess(transform.x, -1.0)
            self.assertLess(input_map.last_state["horizontal"], 0.0)
        finally:
            runtime.shutdown()


class TestPrueva1ExportParity(unittest.TestCase):
    """Regression coverage for Prueva1 scripted pickups in export runtime."""

    repo_root = Path(__file__).resolve().parents[1]
    project_root = repo_root / "projects" / "Prueva1"
    packed_root = project_root / "dist" / "export" / "windows" / "Prueva1" / "Prueva1"
    pickup_cases = [
        ("Coin_A", 300.0, 448.0, "score", 1),
        ("SpeedBoost_A", 520.0, 340.0, "speed_timer", 5.9),
        ("JumpBoost_A", 820.0, 276.0, "jump_timer", 5.9),
        ("Life_A", 1050.0, 340.0, "health", 4),
    ]

    def setUp(self):
        self.registry = create_default_registry()
        self._before_paths = set(sys.path)

    def tearDown(self):
        sys.modules.pop("player_powerups", None)
        for path in list(sys.path):
            if path not in self._before_paths:
                sys.path.remove(path)

    @unittest.skipUnless(project_root.exists(), "Prueva1 project not present. Clone from source or create at projects/Prueva1 with a valid project.json and levels/")
    def test_prueva1_project_pickups_apply_script_effects(self):
        for case in self.pickup_cases:
            with self.subTest(pickup=case[0]):
                self._assert_pickup_effect(self.project_root, case)

    @unittest.skipUnless(project_root.exists(), "Prueva1 project not present. Clone from source or create at projects/Prueva1 with a valid project.json and levels/")
    def test_prueva1_android_shared_runtime_adapter_pickups_apply_script_effects(self):
        module = self._load_android_runtime_adapter()
        config = {
            "entry_scene": "levels/playground_platformer_mobile.json",
            "window": {"width": 1280, "height": 720},
        }
        try:
            for case in self.pickup_cases:
                pickup_name, x, y, field, expected = case
                with self.subTest(pickup=pickup_name):
                    created = json.loads(module.create_shared_runtime(str(self.project_root), json.dumps(config)))
                    self.assertTrue(created["ok"], created.get("error", ""))
                    moved = json.loads(module.set_entity_transform("Player", x, y))
                    self.assertTrue(moved["ok"])
                    snapshot = {}
                    for _ in range(2):
                        snapshot = json.loads(module.run_shared_frame(1.0 / 60.0, "{}"))
                    self.assertTrue(snapshot["ok"], snapshot.get("error", ""))

                    by_name = {entity["name"]: entity for entity in snapshot["scene"]["entities"]}
                    self.assertNotIn(pickup_name, by_name)
                    player = by_name["Player"]
                    script = player["components"]["ScriptBehaviour"]
                    controller = player["components"]["PlayerController2D"]
                    value = script["public_data"].get(field)
                    if field.endswith("_timer"):
                        self.assertGreaterEqual(float(value), float(expected))
                    else:
                        self.assertEqual(value, expected)
                    if field == "speed_timer":
                        self.assertGreater(controller["move_speed"], script["public_data"]["base_move_speed"])
                    if field == "jump_timer":
                        self.assertLess(controller["jump_velocity"], script["public_data"]["base_jump_velocity"])
        finally:
            module.shutdown_shared_runtime()
            sys.modules.pop("motor_android_runtime_test_adapter", None)

    @unittest.skipUnless(project_root.exists(), "Prueva1 project not present. Clone from source or create at projects/Prueva1 with a valid project.json and levels/")
    def test_prueva1_android_adapter_forces_pyray_stub_when_runtime_is_copied(self):
        import os

        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            project_dir = tmp / "android_project"
            assets_dir = project_dir / "app" / "src" / "main" / "assets"
            shutil.copytree(self.project_root / "levels", assets_dir / "levels")
            shutil.copytree(self.project_root / "assets", assets_dir / "assets")
            (assets_dir / "runtime_config.json").write_text(
                json.dumps(
                    {
                        "entry_scene": "levels/playground_platformer_mobile.json",
                        "window": {"width": 844, "height": 390},
                        "android_python_runtime": True,
                    }
                ),
                encoding="utf-8",
            )
            preset = ExportPreset(
                name="Android Mobile Debug",
                platform="android",
                mode="debug",
                output_path="dist/export/android/Prueva1-mobile-debug.apk",
                entry_scene="levels/playground_platformer_mobile.json",
                display_name="Prueva1",
                application_id="com.prueva1.game",
                min_sdk=24,
                extra={"android_python_runtime": True},
            )
            ctx = BuildContext(preset, self.project_root)
            AndroidExporter()._copy_android_python_runtime(ctx, project_dir, ["scripts/player_powerups.py"])
            self.assertFalse(ctx.errors)
            template_adapter = (
                self.repo_root
                / "platforms"
                / "android"
                / "template"
                / "app"
                / "src"
                / "main"
                / "python"
                / "motor_android_runtime.py"
            )
            adapter_path = project_dir / "app" / "src" / "main" / "python" / "motor_android_runtime.py"
            shutil.copy2(template_adapter, adapter_path)

            before_env = os.environ.pop("PYRAY_FORCE_STUB", None)
            before_paths = list(sys.path)
            before_pyray = sys.modules.get("pyray")
            sys.modules.pop("pyray", None)
            try:
                spec = importlib.util.spec_from_file_location("motor_android_runtime_copied_adapter", adapter_path)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                sys.modules["motor_android_runtime_copied_adapter"] = module
                sys.path.insert(0, str(adapter_path.parent))
                spec.loader.exec_module(module)
                payload = json.loads(
                    module.create_shared_runtime(
                        str(assets_dir.resolve()),
                        (assets_dir / "runtime_config.json").read_text(encoding="utf-8"),
                    )
                )

                self.assertTrue(payload["ok"], payload.get("traceback", payload.get("error", "")))
                self.assertEqual(payload["current_scene"], "levels/playground_platformer_mobile.json")
                self.assertGreater(len(payload["scene"]["entities"]), 0)
                self.assertEqual(os.environ.get("PYRAY_FORCE_STUB"), "1")
            finally:
                try:
                    module.shutdown_shared_runtime()
                except Exception:
                    pass
                sys.modules.pop("motor_android_runtime_copied_adapter", None)
                sys.modules.pop("pyray", None)
                if before_pyray is not None:
                    sys.modules["pyray"] = before_pyray
                sys.path[:] = before_paths
                if before_env is None:
                    os.environ.pop("PYRAY_FORCE_STUB", None)
                else:
                    os.environ["PYRAY_FORCE_STUB"] = before_env

    @unittest.skipUnless(packed_root.exists(), "Prueva1 packed build not present. Build with: py -m motor export pack \"Windows Desktop\" --project projects/Prueva1 --json")
    def test_prueva1_packed_pickups_apply_script_effects(self):
        for case in self.pickup_cases:
            with self.subTest(pickup=case[0]):
                self._assert_pickup_effect(self.packed_root, case)

    @unittest.skipUnless(packed_root.exists(), "Prueva1 packed build not present. Build with: py -m motor export pack \"Windows Desktop\" --project projects/Prueva1 --json")
    def test_prueva1_packed_texture_hot_path_does_not_refresh_authoring_catalog(self):
        from engine.assets.asset_database import AssetDatabase
        from engine.components.animator import Animator
        from engine.components.sprite import Sprite

        class FakeTexture:
            id = 1
            width = 32
            height = 32

        loader = ContentLoader(str(self.packed_root))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.setup_scripts_path()
        self.assertTrue(runtime.load_scene("levels/playground_platformer.json"))

        drawable_refs = []
        for entity in runtime.world.iter_all_entities():
            sprite = entity.get_component(Sprite)
            if sprite is not None and sprite.enabled and sprite.texture_path:
                drawable_refs.append((sprite.get_texture_reference(), sprite.texture_path, sprite.sync_texture_reference))
            animator = entity.get_component(Animator)
            if animator is not None and animator.enabled and animator.sprite_sheet:
                drawable_refs.append(
                    (animator.get_sprite_sheet_reference(), animator.sprite_sheet, animator.sync_sprite_sheet_reference)
                )
        self.assertTrue(drawable_refs)

        render_system = runtime.render_system
        with (
            patch.object(AssetDatabase, "refresh_catalog", side_effect=AssertionError("authoring catalog used")),
            patch.object(render_system.texture_manager, "load", return_value=FakeTexture()) as load_texture,
        ):
            for _ in range(2):
                for reference, path, sync_callback in drawable_refs:
                    render_system._load_texture(reference, path, sync_callback=sync_callback)

        self.assertGreater(load_texture.call_count, 0)
        runtime.shutdown()

    def _assert_pickup_effect(self, base_path: Path, case: tuple[str, float, float, str, float]) -> None:
        pickup_name, x, y, field, expected = case
        loader = ContentLoader(str(base_path))
        runtime = ExportRuntime(loader=loader, registry=self.registry)
        runtime.setup_scripts_path()
        self.assertTrue(runtime.load_scene("levels/playground_platformer.json"))

        from engine.components.playercontroller2d import PlayerController2D
        from engine.components.scriptbehaviour import ScriptBehaviour
        from engine.components.transform import Transform

        player = runtime.world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        transform.x = x
        transform.y = y

        runtime.run_frame(1.0 / 60.0)
        runtime.run_frame(1.0 / 60.0)

        script = player.get_component(ScriptBehaviour)
        controller = player.get_component(PlayerController2D)
        self.assertIsNone(runtime.world.get_entity_by_name(pickup_name))
        value = script.public_data.get(field)
        if field.endswith("_timer"):
            self.assertGreaterEqual(float(value), float(expected))
        else:
            self.assertEqual(value, expected)
        if field == "speed_timer":
            self.assertGreater(controller.move_speed, script.public_data["base_move_speed"])
        if field == "jump_timer":
            self.assertLess(controller.jump_velocity, script.public_data["base_jump_velocity"])
        runtime.shutdown()

    def _load_android_runtime_adapter(self):
        adapter_path = (
            self.repo_root
            / "platforms"
            / "android"
            / "template"
            / "app"
            / "src"
            / "main"
            / "python"
            / "motor_android_runtime.py"
        )
        spec = importlib.util.spec_from_file_location("motor_android_runtime_test_adapter", adapter_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules["motor_android_runtime_test_adapter"] = module
        spec.loader.exec_module(module)
        return module


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
