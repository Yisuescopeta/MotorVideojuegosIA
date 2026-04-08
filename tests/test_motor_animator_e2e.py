"""
tests/test_motor_animator_e2e.py - End-to-end tests for Motor CLI Animator workflow

Tests the complete headless animator workflow using the official `motor` CLI:
1. Ensure Animator component exists
2. Set sprite sheet
3. Create animation states (loop and no-loop)
4. Query animator info
5. Remove states

These tests verify the AI-facing animator API works correctly without visual editor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MotorAnimatorEndToEndTests(unittest.TestCase):
    """End-to-end tests for the official motor animator workflow."""

    def setUp(self) -> None:
        """Set up a clean project for each test."""
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        
        # Create a minimal valid project
        self.project_root = self.workspace / "TestGame"
        self.project_root.mkdir()
        
        # Create project.json
        (self.project_root / "project.json").write_text(
            json.dumps({
                "name": "TestGame",
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }),
            encoding="utf-8",
        )
        
        # Create required directories
        for dir_name in ["assets", "levels", "scripts", "settings", ".motor"]:
            (self.project_root / dir_name).mkdir(parents=True, exist_ok=True)
        
        # Create a simple test image (16x16 PNG with 4 8x8 cells)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x10,
            0x00, 0x00, 0x00, 0x10,
            0x08, 0x02, 0x00, 0x00, 0x00,
            0x90, 0x91, 0x68, 0x36,
            0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, 0x54,
            0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
            0x00, 0x03, 0x00, 0x01,
            0x00, 0x05, 0xFE, 0xD4,
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
            0xAE, 0x42, 0x60, 0x82,
        ])
        (self.project_root / "assets" / "player.png").write_bytes(png_data)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def _run_motor(self, *args: str) -> dict:
        """Execute motor CLI command and return parsed JSON response."""
        # Ensure project path is included
        cmd_args = list(args)
        if "--project" not in cmd_args:
            cmd_args = cmd_args + ["--project", str(self.project_root)]
        if "--json" not in cmd_args:
            cmd_args = cmd_args + ["--json"]
        
        cmd = [sys.executable, "-m", "motor"] + cmd_args
        
        # Set PYTHONPATH to include the workspace root
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(root) if not python_path else str(root) + os.pathsep + python_path
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            env=env,
        )
        # Parse JSON output (skip any leading non-JSON lines like raylib loading message)
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # If we can't parse, return error structure
            return {"success": False, "message": f"Invalid JSON output: {repr(output[:200])}", "data": {}}

    def _setup_scene_and_entity(self, scene_name: str = "TestScene", entity_name: str = "Player") -> None:
        """Helper to create scene and entity (entity creation auto-saves)."""
        # Create scene
        result = self._run_motor("scene", "create", scene_name)
        self.assertTrue(result.get("success"), f"Scene creation failed: {result.get('message')}")
        
        # Load the scene (required for subsequent operations)
        scene_path = result["data"]["path"]
        load_result = self._run_motor("scene", "load", scene_path)
        self.assertTrue(load_result.get("success"), f"Scene load failed: {load_result.get('message')}")
        
        # Create entity (auto-saves scene)
        entity_result = self._run_motor("entity", "create", entity_name)
        self.assertTrue(entity_result.get("success"), f"Entity creation failed: {entity_result.get('message')}")

    def test_animator_ensure_creates_component(self) -> None:
        """motor animator ensure creates Animator component if missing."""
        # Setup
        self._setup_scene_and_entity("EnsureTest", "TestPlayer")
        
        # Ensure Animator exists
        result = self._run_motor("animator", "ensure", "TestPlayer")
        
        self.assertTrue(result.get("success"), f"Ensure failed: {result.get('message')}")
        self.assertTrue(result["data"].get("created"), "Animator should be created")
        
        # Verify Animator exists by getting info
        info = self._run_motor("animator", "info", "TestPlayer")
        self.assertTrue(info["data"].get("exists"), "Animator should exist after ensure")

    def test_animator_ensure_idempotent(self) -> None:
        """motor animator ensure is idempotent - doesn't recreate if exists."""
        # Setup
        self._setup_scene_and_entity("IdempotentTest", "IdemPlayer")
        self._run_motor("animator", "ensure", "IdemPlayer")
        
        # Ensure again
        result = self._run_motor("animator", "ensure", "IdemPlayer")
        
        self.assertTrue(result.get("success"))
        self.assertFalse(result["data"].get("created"), "Animator should not be recreated")

    def test_animator_ensure_with_sprite_sheet(self) -> None:
        """motor animator ensure can set initial sprite sheet."""
        # Setup
        self._setup_scene_and_entity("SheetTest", "SheetPlayer")
        
        # Ensure with sprite sheet
        result = self._run_motor("animator", "ensure", "SheetPlayer", "--sheet", "assets/player.png")
        
        self.assertTrue(result.get("success"))
        self.assertTrue(result["data"].get("created"))
        
        # Verify sprite sheet is set
        info = self._run_motor("animator", "info", "SheetPlayer")
        self.assertEqual(info["data"].get("sprite_sheet"), "assets/player.png")

    def test_animator_set_sheet_updates_sprite_sheet(self) -> None:
        """motor animator set-sheet updates the sprite sheet reference."""
        # Setup
        self._setup_scene_and_entity("SetSheetTest", "SheetPlayer2")
        self._run_motor("animator", "ensure", "SheetPlayer2")
        
        # Set sprite sheet
        result = self._run_motor("animator", "set-sheet", "SheetPlayer2", "assets/player.png")
        
        self.assertTrue(result.get("success"))
        
        # Verify
        info = self._run_motor("animator", "info", "SheetPlayer2")
        self.assertEqual(info["data"].get("sprite_sheet"), "assets/player.png")

    def test_animator_state_create_creates_looping_state(self) -> None:
        """motor animator state create creates looping state with --loop."""
        # Setup
        self._setup_scene_and_entity("LoopTest", "LoopPlayer")
        self._run_motor("animator", "ensure", "LoopPlayer")
        
        # Create looping state
        result = self._run_motor(
            "animator", "state", "create", "LoopPlayer", "idle",
            "--slices", "slice_0,slice_1",
            "--fps", "8",
            "--loop",
            "--set-default",
        )
        
        self.assertTrue(result.get("success"), f"State create failed: {result.get('message')}")
        
        # Verify state exists and is looping
        info = self._run_motor("animator", "info", "LoopPlayer")
        states = info["data"].get("states", [])
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["name"], "idle")
        self.assertTrue(states[0]["loop"], "State should be looping")
        self.assertTrue(states[0]["is_default"], "State should be default")

    def test_animator_state_create_creates_non_looping_state(self) -> None:
        """motor animator state create creates non-looping state with --no-loop."""
        # Setup
        self._setup_scene_and_entity("NoLoopTest", "NoLoopPlayer")
        self._run_motor("animator", "ensure", "NoLoopPlayer")
        
        # Create non-looping state
        result = self._run_motor(
            "animator", "state", "create", "NoLoopPlayer", "attack",
            "--slices", "slice_0,slice_1",
            "--fps", "12",
            "--no-loop",
        )
        
        self.assertTrue(result.get("success"))
        
        # Verify state exists and is not looping
        info = self._run_motor("animator", "info", "NoLoopPlayer")
        states = info["data"].get("states", [])
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0]["name"], "attack")
        self.assertFalse(states[0]["loop"], "State should not be looping")

    def test_animator_state_create_defaults_to_looping(self) -> None:
        """motor animator state create defaults to looping when no flag specified."""
        # Setup
        self._setup_scene_and_entity("DefaultLoopTest", "DefLoopPlayer")
        self._run_motor("animator", "ensure", "DefLoopPlayer")
        
        # Create state without explicit loop flag
        result = self._run_motor(
            "animator", "state", "create", "DefLoopPlayer", "walk",
            "--slices", "slice_0",
            "--fps", "10",
        )
        
        self.assertTrue(result.get("success"))
        
        # Verify state defaults to looping
        info = self._run_motor("animator", "info", "DefLoopPlayer")
        states = info["data"].get("states", [])
        self.assertEqual(len(states), 1)
        self.assertTrue(states[0]["loop"], "State should default to looping")

    def test_animator_state_create_auto_create_flag(self) -> None:
        """motor animator state create --auto-create creates Animator if missing."""
        # Setup (note: NOT calling animator ensure)
        self._setup_scene_and_entity("AutoCreateTest", "AutoPlayer")
        
        # Create state with auto-create
        result = self._run_motor(
            "animator", "state", "create", "AutoPlayer", "idle",
            "--slices", "slice_0",
            "--fps", "8",
            "--loop",
            "--auto-create",
        )
        
        self.assertTrue(result.get("success"), f"State create with auto-create failed: {result.get('message')}")
        
        # Verify Animator was created
        info = self._run_motor("animator", "info", "AutoPlayer")
        self.assertTrue(info["data"].get("exists"))

    def test_animator_info_returns_full_state_data(self) -> None:
        """motor animator info returns comprehensive animator data."""
        # Setup
        self._setup_scene_and_entity("InfoTest", "InfoPlayer")
        self._run_motor("animator", "ensure", "InfoPlayer", "--sheet", "assets/player.png")
        self._run_motor(
            "animator", "state", "create", "InfoPlayer", "idle",
            "--slices", "slice_0,slice_1",
            "--fps", "8",
            "--loop",
            "--set-default",
        )
        
        # Get info
        result = self._run_motor("animator", "info", "InfoPlayer")
        
        self.assertTrue(result.get("success"))
        data = result["data"]
        
        # Verify structure
        self.assertTrue(data.get("exists"))
        self.assertEqual(data.get("sprite_sheet"), "assets/player.png")
        self.assertIn("states", data)
        self.assertEqual(len(data["states"]), 1)
        
        state = data["states"][0]
        self.assertIn("name", state)
        self.assertIn("frame_count", state)
        self.assertIn("fps", state)
        self.assertIn("loop", state)
        self.assertIn("duration_seconds", state)
        self.assertIn("is_default", state)

    def test_animator_state_remove_deletes_state(self) -> None:
        """motor animator state remove deletes the specified state."""
        # Setup
        self._setup_scene_and_entity("RemoveTest", "RemovePlayer")
        self._run_motor("animator", "ensure", "RemovePlayer")
        self._run_motor(
            "animator", "state", "create", "RemovePlayer", "idle",
            "--slices", "slice_0",
            "--fps", "8",
        )
        
        # Remove state
        result = self._run_motor("animator", "state", "remove", "RemovePlayer", "idle")
        
        self.assertTrue(result.get("success"))
        
        # Verify state removed
        info = self._run_motor("animator", "info", "RemovePlayer")
        self.assertEqual(len(info["data"].get("states", [])), 0)

    def test_full_animator_workflow(self) -> None:
        """Complete animator workflow: ensure → set-sheet → states → info."""
        # 1. Create scene, load it, create entity
        self._setup_scene_and_entity("FullWorkflow", "Hero")
        
        # 2. Ensure Animator exists
        ensure_result = self._run_motor(
            "animator", "ensure", "Hero", "--sheet", "assets/player.png",
        )
        self.assertTrue(ensure_result["success"])
        
        # 3. Create looping idle state
        idle_result = self._run_motor(
            "animator", "state", "create", "Hero", "idle",
            "--slices", "slice_0,slice_1",
            "--fps", "8",
            "--loop",
            "--set-default",
        )
        self.assertTrue(idle_result["success"])
        
        # 4. Create non-looping attack state
        attack_result = self._run_motor(
            "animator", "state", "create", "Hero", "attack",
            "--slices", "slice_2,slice_3",
            "--fps", "12",
            "--no-loop",
        )
        self.assertTrue(attack_result["success"])
        
        # 5. Verify final state
        info = self._run_motor("animator", "info", "Hero")
        self.assertTrue(info["success"])
        
        data = info["data"]
        self.assertEqual(data["sprite_sheet"], "assets/player.png")
        self.assertEqual(len(data["states"]), 2)
        
        # Find states
        idle_state = next((s for s in data["states"] if s["name"] == "idle"), None)
        attack_state = next((s for s in data["states"] if s["name"] == "attack"), None)
        
        self.assertIsNotNone(idle_state)
        self.assertIsNotNone(attack_state)
        
        self.assertTrue(idle_state["loop"])
        self.assertTrue(idle_state["is_default"])
        self.assertEqual(idle_state["fps"], 8.0)
        
        self.assertFalse(attack_state["loop"])
        self.assertEqual(attack_state["fps"], 12.0)

    def test_loop_no_loop_mutual_exclusivity(self) -> None:
        """--loop and --no-loop are mutually exclusive (--no-loop wins if both)."""
        # Setup
        self._setup_scene_and_entity("MutualTest", "MutualPlayer")
        self._run_motor("animator", "ensure", "MutualPlayer")
        
        # Try passing both flags (last one should win in argparse)
        result = self._run_motor(
            "animator", "state", "create", "MutualPlayer", "test",
            "--slices", "slice_0",
            "--loop",
            "--no-loop",  # This should win
        )
        
        self.assertTrue(result.get("success"))
        
        # Verify non-looping (last flag wins)
        info = self._run_motor("animator", "info", "MutualPlayer")
        states = info["data"].get("states", [])
        self.assertEqual(len(states), 1)
        self.assertFalse(states[0]["loop"], "--no-loop should win when both specified")


class MotorAnimatorCommandSyntaxTests(unittest.TestCase):
    """Tests for command syntax and argument validation."""

    def test_state_create_requires_slices(self) -> None:
        """motor animator state create requires --slices argument."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            (project / "project.json").write_text(
                json.dumps({
                    "name": "Test",
                    "version": 2,
                    "paths": {
                        "assets": "assets", "levels": "levels",
                        "scripts": "scripts", "settings": "settings",
                        "meta": ".motor/meta", "build": ".motor/build"
                    },
                }),
                encoding="utf-8",
            )
            for d in ["assets", "levels", "scripts", "settings", ".motor"]:
                (project / d).mkdir(parents=True, exist_ok=True)

            # Try without --slices (should fail argparse validation)
            root = Path(__file__).resolve().parents[1]
            env = os.environ.copy()
            python_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(root) if not python_path else str(root) + os.pathsep + python_path

            cmd = [
                sys.executable, "-m", "motor",
                "animator", "state", "create", "Player", "idle",
                "--project", str(project),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            # Argparse should fail with non-zero exit
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
