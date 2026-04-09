from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.assets.asset_service import AssetService
from engine.project.project_service import ProjectService


def _write_test_project(root: Path) -> Path:
    project_root = root / "TestProject"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.json").write_text(
        json.dumps(
            {
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
            }
        ),
        encoding="utf-8",
    )
    for dir_name in ["assets", "levels", "scripts", "settings", ".motor"]:
        (project_root / dir_name).mkdir(parents=True, exist_ok=True)
    png_data = bytes(
        [
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
        ]
    )
    (project_root / "assets" / "spritesheet.png").write_bytes(png_data)
    return project_root


class AssetServiceAnimationFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = _write_test_project(self.workspace)
        self.project_service = ProjectService(self.project_root.as_posix())
        self.service = AssetService(self.project_service)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_preview_auto_slices_supports_structured_payload(self) -> None:
        payload = self.service.preview_auto_slices("assets/spritesheet.png", structured=True)

        self.assertEqual(payload["asset_path"], "assets/spritesheet.png")
        self.assertEqual(payload["image"], {"width": 16, "height": 16})
        self.assertEqual(payload["settings"]["naming_prefix"], "spritesheet")
        self.assertEqual(payload["slice_count"], len(payload["slices"]))
        self.assertIsInstance(payload["slices"], list)

    def test_group_slices_supports_row_prefix_and_visual_order(self) -> None:
        self.service.apply_manual_slices(
            "assets/spritesheet.png",
            [
                {"name": "idle_0", "x": 0, "y": 0, "width": 8, "height": 8},
                {"name": "idle_1", "x": 8, "y": 0, "width": 8, "height": 8},
                {"name": "attack_0", "x": 0, "y": 8, "width": 8, "height": 8},
                {"name": "attack_1", "x": 8, "y": 8, "width": 8, "height": 8},
            ],
        )

        row_groups = self.service.group_slices("assets/spritesheet.png", group_mode="row")
        prefix_groups = self.service.group_slices("assets/spritesheet.png", group_mode="name_prefix")
        visual_groups = self.service.group_slices("assets/spritesheet.png", group_mode="visual_order")

        self.assertEqual([group["slice_names"] for group in row_groups["groups"]], [["idle_0", "idle_1"], ["attack_0", "attack_1"]])
        self.assertEqual([group["group_key"] for group in prefix_groups["groups"]], ["idle", "attack"])
        self.assertEqual(visual_groups["groups"][0]["slice_names"], ["idle_0", "idle_1", "attack_0", "attack_1"])

    def test_build_animation_from_slices_returns_deterministic_preview(self) -> None:
        self.service.apply_manual_slices(
            "assets/spritesheet.png",
            [
                {"name": "run_0", "x": 8, "y": 0, "width": 6, "height": 8},
                {"name": "run_1", "x": 0, "y": 0, "width": 8, "height": 8},
                {"name": "run_2", "x": 0, "y": 8, "width": 10, "height": 12},
            ],
        )

        payload = self.service.build_animation_from_slices(
            "assets/spritesheet.png",
            ["run_2", "run_0", "run_1"],
            state_name="run",
            fps=12.0,
            loop=False,
            order_mode="visual",
        )

        self.assertEqual(payload["animation"]["slice_names"], ["run_1", "run_0", "run_2"])
        self.assertEqual(payload["animation"]["frames"], [0, 1, 2])
        self.assertFalse(payload["animation"]["loop"])
        self.assertEqual(payload["preview"]["frame_count"], 3)
        self.assertTrue(payload["preview"]["frame_size_summary"]["variable_size"])
        self.assertEqual([frame["slice_name"] for frame in payload["preview"]["frames"]], ["run_1", "run_0", "run_2"])


if __name__ == "__main__":
    unittest.main()
