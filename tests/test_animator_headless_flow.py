"""
tests/test_animator_headless_flow.py - Complete headless animator flow tests

Tests the full AI-facing headless workflow for animator:
1. Create scene
2. Create entity
3. Ensure Animator component
4. Set sprite sheet
5. Create slices
6. Create loop state
7. Create no-loop state
8. Query final info

This validates that an AI can complete the entire animator setup
without opening the visual editor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AnimatorHeadlessFlowTests(unittest.TestCase):
    """Complete headless animator workflow tests."""

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
        
        # Set up environment
        self.env = os.environ.copy()
        root = Path(__file__).resolve().parents[1]
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(root) if not python_path else str(root) + os.pathsep + python_path

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._temp_dir.cleanup()

    def _run_motor(self, *args: str) -> dict:
        """Execute motor CLI command and return parsed JSON response."""
        cmd_args = list(args)
        if "--project" not in cmd_args:
            cmd_args = cmd_args + ["--project", str(self.project_root)]
        if "--json" not in cmd_args:
            cmd_args = cmd_args + ["--json"]
        
        cmd = [sys.executable, "-m", "motor"] + cmd_args
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            env=self.env,
        )
        # Parse JSON output
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"success": False, "message": f"Invalid JSON: {output[:200]}", "data": {}}

    def test_complete_headless_animator_flow(self) -> None:
        """Complete headless workflow: scene -> entity -> animator -> states."""
        entity_name = "Hero"
        
        # Step 1: Create scene
        print("\n1. Creating scene...")
        result = self._run_motor("scene", "create", "TestLevel")
        self.assertTrue(result.get("success"), f"Scene creation failed: {result.get('message')}")
        
        # Step 2: Create entity
        print("2. Creating entity...")
        result = self._run_motor("entity", "create", entity_name)
        self.assertTrue(result.get("success"), f"Entity creation failed: {result.get('message')}")
        
        # Step 3: Ensure Animator component
        print("3. Ensuring Animator component...")
        result = self._run_motor("animator", "ensure", entity_name)
        self.assertTrue(result.get("success"), f"Animator ensure failed: {result.get('message')}")
        self.assertTrue(result["data"].get("created"), "Animator should be created")
        
        # Verify Animator exists
        result = self._run_motor("animator", "info", entity_name)
        self.assertTrue(result["data"].get("exists"), "Animator should exist after ensure")
        
        # Step 4: Set sprite sheet
        print("4. Setting sprite sheet...")
        result = self._run_motor("animator", "set-sheet", entity_name, "assets/player.png")
        self.assertTrue(result.get("success"), f"Set sheet failed: {result.get('message')}")
        
        # Step 5: Create slices (using API directly for reliability in tests)
        print("5. Creating slices...")
        # For the E2E test, we use manual slices to avoid asset service initialization issues
        from engine.api import EngineAPI
        api = EngineAPI(project_root=str(self.project_root), sandbox_paths=False)
        manual_slices = [
            {"name": "idle_0", "x": 0, "y": 0, "width": 8, "height": 8},
            {"name": "idle_1", "x": 8, "y": 0, "width": 8, "height": 8},
            {"name": "attack_0", "x": 0, "y": 8, "width": 8, "height": 8},
            {"name": "attack_1", "x": 8, "y": 8, "width": 8, "height": 8},
        ]
        api.save_manual_slices("assets/player.png", manual_slices)
        api.shutdown()
        
        # Step 6: Create loop state (idle)
        print("6. Creating loop state (idle)...")
        result = self._run_motor(
            "animator", "state", "create", entity_name, "idle",
            "--slices", "idle_0,idle_1",
            "--fps", "8",
            "--loop",
            "--set-default"
        )
        self.assertTrue(result.get("success"), f"Idle state creation failed: {result.get('message')}")
        
        # Step 7: Create no-loop state (attack)
        print("7. Creating no-loop state (attack)...")
        result = self._run_motor(
            "animator", "state", "create", entity_name, "attack",
            "--slices", "attack_0,attack_1",
            "--fps", "12",
            "--no-loop"
        )
        self.assertTrue(result.get("success"), f"Attack state creation failed: {result.get('message')}")
        
        # Step 8: Query final info
        print("8. Querying final animator info...")
        result = self._run_motor("animator", "info", entity_name)
        self.assertTrue(result.get("success"), f"Info query failed: {result.get('message')}")
        
        info = result["data"]
        self.assertTrue(info.get("exists"), "Animator should exist")
        self.assertEqual(info.get("sprite_sheet"), "assets/player.png", "Sprite sheet should be set")
        
        states = info.get("states", [])
        self.assertGreaterEqual(len(states), 2, "Should have idle and attack states")
        
        # Verify idle state
        idle_state = next((s for s in states if s["name"] == "idle"), None)
        self.assertIsNotNone(idle_state, "Should have idle state")
        self.assertTrue(idle_state.get("loop"), "Idle should be looping")
        self.assertTrue(idle_state.get("is_default"), "Idle should be default")
        
        # Verify attack state
        attack_state = next((s for s in states if s["name"] == "attack"), None)
        self.assertIsNotNone(attack_state, "Should have attack state")
        self.assertFalse(attack_state.get("loop"), "Attack should not be looping")
        
        print("\n[OK] Complete headless animator flow successful!")

    def test_animator_flow_without_editor(self) -> None:
        """Verify the entire flow works without visual editor interaction."""
        # This test validates that all operations are truly headless
        entity_name = "Player"

        # Create scene and entity
        self._run_motor("scene", "create", "Level1")
        self._run_motor("entity", "create", entity_name)

        # All animator operations should work without editor
        operations = [
            ("ensure animator", ["animator", "ensure", entity_name]),
            ("set sheet", ["animator", "set-sheet", entity_name, "assets/player.png"]),
            ("create slices", ["asset", "slice", "grid", "assets/player.png", "--cell-width", "8", "--cell-height", "8"]),
            ("query info", ["animator", "info", entity_name]),
        ]

        for op_name, args in operations:
            result = self._run_motor(*args)
            self.assertTrue(
                result.get("success"),
                f"Operation '{op_name}' should work without editor: {result.get('message')}"
            )

    def test_ensure_sheet_semantics_when_animator_missing(self) -> None:
        """ensure --sheet should create Animator with sheet when it doesn't exist."""
        entity_name = "NewPlayer"

        # Create scene and entity
        self._run_motor("scene", "create", "Level1")
        self._run_motor("entity", "create", entity_name)

        # Ensure Animator with sheet when it doesn't exist
        result = self._run_motor("animator", "ensure", entity_name, "--sheet", "assets/player.png")
        self.assertTrue(result.get("success"), f"ensure --sheet should succeed: {result.get('message')}")
        self.assertTrue(result["data"].get("created"), "Animator should be created when missing")
        self.assertFalse(result["data"].get("updated"), "Should not be marked as updated when created")
        self.assertEqual(result["data"].get("sprite_sheet"), "assets/player.png", "Sheet should be set")

        # Verify the sheet was actually set
        result = self._run_motor("animator", "info", entity_name)
        self.assertEqual(result["data"].get("sprite_sheet"), "assets/player.png", "Sheet should persist")

    def test_ensure_sheet_semantics_when_animator_exists(self) -> None:
        """ensure --sheet should update sheet when Animator already exists."""
        entity_name = "ExistingPlayer"

        # Create scene and entity
        self._run_motor("scene", "create", "Level1")
        self._run_motor("entity", "create", entity_name)

        # First, create Animator without sheet
        result = self._run_motor("animator", "ensure", entity_name)
        self.assertTrue(result.get("success"))
        self.assertTrue(result["data"].get("created"))

        # Now ensure with sheet - should update existing Animator
        result = self._run_motor("animator", "ensure", entity_name, "--sheet", "assets/player.png")
        self.assertTrue(result.get("success"), f"ensure --sheet should succeed: {result.get('message')}")
        self.assertFalse(result["data"].get("created"), "Should not be marked as created when exists")
        self.assertTrue(result["data"].get("updated"), "Should be marked as updated")
        self.assertEqual(result["data"].get("sprite_sheet"), "assets/player.png", "New sheet should be set")

    def test_ensure_sheet_idempotent_with_same_sheet(self) -> None:
        """ensure --sheet should be idempotent when sheet already matches."""
        entity_name = "IdempotentPlayer"

        # Create scene and entity
        self._run_motor("scene", "create", "Level1")
        self._run_motor("entity", "create", entity_name)

        # Create Animator with sheet
        result = self._run_motor("animator", "ensure", entity_name, "--sheet", "assets/player.png")
        self.assertTrue(result.get("success"))

        # Ensure again with same sheet - should succeed without changes
        result = self._run_motor("animator", "ensure", entity_name, "--sheet", "assets/player.png")
        self.assertTrue(result.get("success"))
        self.assertFalse(result["data"].get("created"), "Should not be created (already exists)")
        self.assertFalse(result["data"].get("updated"), "Should not be updated (same sheet)")
        self.assertEqual(result["data"].get("sprite_sheet"), "assets/player.png", "Sheet should remain")

    def test_ensure_without_sheet_idempotent(self) -> None:
        """ensure without --sheet should be idempotent (just checks existence)."""
        entity_name = "SimplePlayer"

        # Create scene and entity
        self._run_motor("scene", "create", "Level1")
        self._run_motor("entity", "create", entity_name)

        # First ensure - creates Animator
        result = self._run_motor("animator", "ensure", entity_name)
        self.assertTrue(result.get("success"))
        self.assertTrue(result["data"].get("created"))

        # Second ensure without sheet - should succeed without changes
        result = self._run_motor("animator", "ensure", entity_name)
        self.assertTrue(result.get("success"))
        self.assertFalse(result["data"].get("created"))
        self.assertFalse(result["data"].get("updated"))


if __name__ == "__main__":
    unittest.main()
