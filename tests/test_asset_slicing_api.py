"""
tests/test_asset_slicing_api.py - Tests for asset slicing API

Validates:
- AssetsProjectAPI slicing methods
- EngineAPI slicing delegation
- Grid, auto, and manual slice operations
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI


class AssetSlicingAPITests(unittest.TestCase):
    """Tests for slicing API methods."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)

        # Create a minimal valid project
        self.project_root = self.workspace / "TestProject"
        self.project_root.mkdir()

        # Create project.json
        (self.project_root / "project.json").write_text(
            json.dumps({
                "name": "TestProject",
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

        # Create a simple test image (1x1 PNG)
        # Minimal valid PNG: 1x1 white pixel
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x10,  # width: 16
            0x00, 0x00, 0x00, 0x10,  # height: 16
            0x08, 0x02, 0x00, 0x00, 0x00,  # bit depth, color type, etc.
            0x90, 0x91, 0x68, 0x36,  # CRC
            0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, 0x54,  # IDAT chunk
            0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00,
            0x00, 0x03, 0x00, 0x01,
            0x00, 0x05, 0xFE, 0xD4,  # CRC
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,  # IEND chunk
            0xAE, 0x42, 0x60, 0x82,
        ])
        (self.project_root / "assets" / "spritesheet.png").write_bytes(png_data)

        self.api = EngineAPI(project_root=str(self.project_root), sandbox_paths=False)

    def tearDown(self) -> None:
        if hasattr(self, 'api') and self.api:
            try:
                self.api.shutdown()
            except Exception:
                pass
        self._temp_dir.cleanup()

    def test_get_asset_image_size(self) -> None:
        """Test getting image size from asset."""
        size = self.api.get_asset_image_size("assets/spritesheet.png")
        self.assertIn("width", size)
        self.assertIn("height", size)
        # The PNG is 16x16
        self.assertEqual(size["width"], 16)
        self.assertEqual(size["height"], 16)

    def test_create_grid_slices_returns_success(self) -> None:
        """Test creating grid slices."""
        result = self.api.create_grid_slices(
            asset_path="assets/spritesheet.png",
            cell_width=8,
            cell_height=8,
            margin=0,
            spacing=0,
        )
        self.assertTrue(result.get("success"))

        data = result.get("data", {})
        self.assertIn("slices", data)
        # 16x16 image with 8x8 cells = 4 slices
        self.assertEqual(len(data["slices"]), 4)

    def test_list_asset_slices_after_grid_creation(self) -> None:
        """Test listing slices after creating grid slices."""
        # First create grid slices
        self.api.create_grid_slices(
            asset_path="assets/spritesheet.png",
            cell_width=8,
            cell_height=8,
        )

        # Then list them
        slices = self.api.list_asset_slices("assets/spritesheet.png")
        self.assertEqual(len(slices), 4)

        # Check slice structure
        if slices:
            slice_data = slices[0]
            self.assertIn("name", slice_data)
            self.assertIn("x", slice_data)
            self.assertIn("y", slice_data)
            self.assertIn("width", slice_data)
            self.assertIn("height", slice_data)

    def test_preview_auto_slices_returns_list(self) -> None:
        """Test previewing auto slices."""
        slices = self.api.preview_auto_slices("assets/spritesheet.png")
        # Should return a list (may be empty depending on image content)
        self.assertIsInstance(slices, list)

    def test_save_manual_slices(self) -> None:
        """Test saving manual slices."""
        manual_slices = [
            {"name": "slice_0", "x": 0, "y": 0, "width": 8, "height": 8},
            {"name": "slice_1", "x": 8, "y": 0, "width": 8, "height": 8},
        ]

        result = self.api.save_manual_slices(
            asset_path="assets/spritesheet.png",
            slices=manual_slices,
        )
        self.assertTrue(result.get("success"))

        # Verify slices were saved
        saved_slices = self.api.list_asset_slices("assets/spritesheet.png")
        self.assertEqual(len(saved_slices), 2)

    def test_manual_slice_normalization(self) -> None:
        """Test that manual slices are normalized properly."""
        manual_slices = [
            {"name": "custom_name", "x": 0, "y": 0, "width": 8, "height": 8, "pivot_x": 0.25, "pivot_y": 0.75},
        ]

        result = self.api.save_manual_slices(
            asset_path="assets/spritesheet.png",
            slices=manual_slices,
        )

        self.assertTrue(result.get("success"))

        # Check metadata
        data = result.get("data", {})
        self.assertEqual(data.get("import_mode"), "manual")
        self.assertEqual(data.get("asset_type"), "sprite_sheet")


class AssetSlicingEdgeCasesTests(unittest.TestCase):
    """Edge case tests for slicing API."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_get_image_size_for_nonexistent_asset(self) -> None:
        """Test getting size for non-existent asset."""
        # Create minimal project
        project_root = self.workspace / "TestProject"
        project_root.mkdir()
        (project_root / "project.json").write_text(
            json.dumps({
                "name": "TestProject",
                "version": 2,
                "paths": {"assets": "assets", "levels": "levels", "scripts": "scripts", "settings": "settings", "meta": ".motor/meta", "build": ".motor/build"},
            }),
            encoding="utf-8",
        )
        for d in ["assets", "levels", "scripts", "settings", ".motor"]:
            (project_root / d).mkdir(parents=True, exist_ok=True)

        api = EngineAPI(project_root=str(project_root), sandbox_paths=False)
        try:
            size = api.get_asset_image_size("assets/nonexistent.png")
            self.assertEqual(size["width"], 0)
            self.assertEqual(size["height"], 0)
        finally:
            api.shutdown()


if __name__ == "__main__":
    unittest.main()
