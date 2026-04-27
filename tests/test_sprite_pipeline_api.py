from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pyray as rl
from engine.api import EngineAPI

GRID_PNG_BYTES = bytes([
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


class SpritePipelineAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text(
            json.dumps(
                {
                    "name": "SpritePipelineProject",
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
                }
            ),
            encoding="utf-8",
        )
        for dir_name in ("assets", "levels", "prefabs", "scripts", "settings", ".motor"):
            (self.project_root / dir_name).mkdir(parents=True, exist_ok=True)
        self.api = EngineAPI(project_root=self.project_root.as_posix(), sandbox_paths=False)

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_grid_sheet(self, relative_path: str = "assets/spritesheet.png") -> str:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(GRID_PNG_BYTES)
        return relative_path

    def _write_auto_slice_source(self, relative_path: str = "external/auto_source.png") -> str:
        path = self.workspace / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        image = rl.gen_image_color(6, 3, rl.BLANK)
        rl.image_draw_rectangle(image, 0, 0, 2, 3, rl.RED)
        rl.image_draw_rectangle(image, 4, 0, 2, 3, rl.BLUE)
        self.assertTrue(rl.export_image(image, path.as_posix()))
        rl.unload_image(image)
        return path.as_posix()

    def test_public_sprite_pipeline_grid_contract_supports_queries_without_ui(self) -> None:
        asset_path = self._write_grid_sheet()

        result = self.api.generate_sprite_grid_slices(
            asset_path=asset_path,
            cell_width=8,
            cell_height=8,
            naming_prefix="hero",
        )

        self.assertTrue(result["success"])
        metadata = self.api.get_sprite_metadata(asset_path)
        slices = self.api.list_sprite_slices(asset_path)
        rect = self.api.get_sprite_slice_rect(asset_path, "hero_3")

        self.assertEqual(metadata["import_mode"], "grid")
        self.assertEqual(metadata["import_settings"]["grid"], metadata["grid"])
        self.assertEqual(len(slices), 4)
        self.assertEqual((rect["x"], rect["y"], rect["width"], rect["height"]), (8, 8, 8, 8))
        self.assertEqual(self.api.get_sprite_image_size(asset_path), {"width": 16, "height": 16})

    def test_public_sprite_pipeline_auto_slices_can_import_and_persist(self) -> None:
        source_path = self._write_auto_slice_source()

        imported = self.api.import_sprite_asset(source_path)
        self.assertTrue(imported["success"])
        imported_path = imported["data"]["path"]

        result = self.api.generate_sprite_auto_slices(imported_path, naming_prefix="auto")

        self.assertTrue(result["success"])
        metadata = self.api.get_sprite_metadata(imported_path)
        self.assertEqual(metadata["import_mode"], "automatic")
        self.assertEqual(len(metadata["slices"]), 2)
        self.assertEqual(metadata["automatic"]["naming_prefix"], "auto")
        self.assertEqual(metadata["import_settings"]["automatic"], metadata["automatic"])

    def test_public_sprite_pipeline_manual_save_clears_previous_mode_state(self) -> None:
        asset_path = self._write_grid_sheet()
        self.api.generate_sprite_grid_slices(asset_path=asset_path, cell_width=8, cell_height=8, naming_prefix="grid")

        result = self.api.save_sprite_manual_slices(
            asset_path=asset_path,
            slices=[{"name": "manual_0", "x": 2, "y": 3, "width": 4, "height": 5}],
        )

        self.assertTrue(result["success"])
        metadata = self.api.get_sprite_metadata(asset_path)
        self.assertEqual(metadata["import_mode"], "manual")
        self.assertEqual(metadata["grid"], {})
        self.assertEqual(metadata["automatic"], {})
        self.assertEqual(metadata["import_settings"]["grid"], {})
        self.assertEqual(metadata["import_settings"]["automatic"], {})
        self.assertEqual([item["name"] for item in self.api.list_sprite_slices(asset_path)], ["manual_0"])
        self.assertEqual(self.api.get_sprite_slice_rect(asset_path, "manual_0")["height"], 5)

    def test_legacy_asset_slicing_wrappers_remain_compatible(self) -> None:
        asset_path = self._write_grid_sheet()

        legacy_result = self.api.create_grid_slices(asset_path=asset_path, cell_width=8, cell_height=8)

        self.assertTrue(legacy_result["success"])
        self.assertEqual(self.api.get_asset_metadata(asset_path)["import_mode"], "grid")
        self.assertEqual(len(self.api.list_asset_slices(asset_path)), 4)
        self.assertEqual(self.api.get_asset_image_size(asset_path), {"width": 16, "height": 16})


if __name__ == "__main__":
    unittest.main()
