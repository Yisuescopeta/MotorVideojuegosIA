from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.editor.project_panel import ProjectPanel
from engine.project.project_service import ProjectService


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc```\xf8\x0f\x00\x01\x04\x01\x00"
    b"\x18\xdd\x8d\xb1"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ProjectPanelAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_service = ProjectService(self.root)
        self.panel = ProjectPanel(self.project_service.project_root_display.as_posix())
        self.panel.set_project_service(self.project_service)

        self._write_png("assets/plain.png")
        self._write_png("assets/unsliced.png")
        self._write_png("assets/characters/hero_ready.png")
        self._write_script("scripts/player_logic.py")
        self._write_prefab("prefabs/enemy.prefab")
        self._write_scene("levels/intro.json")

        self.panel.refresh_asset_catalog()
        assert self.panel.asset_service is not None
        self.panel.asset_service.save_metadata(
            "assets/plain.png",
            {
                "asset_type": "texture",
                "import_mode": "raw",
                "grid": {},
                "automatic": {},
                "slices": [],
            },
        )
        self.panel.asset_service.save_metadata(
            "assets/unsliced.png",
            {
                "asset_type": "sprite_sheet",
                "import_mode": "grid",
                "grid": {"cell_width": 16, "cell_height": 16},
                "automatic": {},
                "slices": [],
            },
        )
        self.panel.asset_service.save_sprite_manual_slices(
            "assets/characters/hero_ready.png",
            [{"name": "idle_0", "x": 0, "y": 0, "width": 1, "height": 1}],
        )
        self.panel.refresh_asset_catalog()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_png(self, relative_path: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MINIMAL_PNG_BYTES)

    def _write_script(self, relative_path: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("print('ok')\n", encoding="utf-8")

    def _write_prefab(self, relative_path: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"root_name": "Enemy", "entities": []}), encoding="utf-8")

    def _write_scene(self, relative_path: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": "Intro", "entities": [], "rules": []}), encoding="utf-8")

    def test_search_finds_assets_by_name_and_relative_path(self) -> None:
        self.panel.set_search_text("hero_ready")
        by_name = {item["relative_path"] for item in self.panel.get_visible_entries()}
        self.assertIn("assets/characters/hero_ready.png", by_name)

        self.panel.set_search_text("characters/hero")
        by_path = {item["relative_path"] for item in self.panel.get_visible_entries()}
        self.assertIn("assets/characters/hero_ready.png", by_path)

    def test_filter_images_limits_visible_files_but_keeps_folder_navigation(self) -> None:
        self.panel.current_path = self.project_service.get_project_path("assets").as_posix()
        self.panel.refresh()
        self.panel.set_asset_filter("images")

        entries = self.panel.get_visible_entries()
        file_entries = [item for item in entries if item["entry_type"] == "file"]
        dir_entries = [item for item in entries if item["entry_type"] == "dir"]

        self.assertTrue(file_entries)
        self.assertTrue(dir_entries)
        self.assertTrue(all(item["is_image"] for item in file_entries))

    def test_panel_distinguishes_plain_unsliced_and_ready_sprite_assets(self) -> None:
        self.assertTrue(self.panel.select_asset("assets/plain.png"))
        plain = self.panel.get_selected_asset_detail()
        self.assertEqual(plain["pipeline_detail"], "metadata only")

        self.assertTrue(self.panel.select_asset("assets/unsliced.png"))
        unsliced = self.panel.get_selected_asset_detail()
        self.assertEqual(unsliced["pipeline_detail"], "sprite sheet without slices")
        self.assertEqual(unsliced["slice_count"], 0)

        self.assertTrue(self.panel.select_asset("assets/characters/hero_ready.png"))
        ready = self.panel.get_selected_asset_detail()
        self.assertEqual(ready["pipeline_detail"], "sprite ready")
        self.assertEqual(ready["slice_count"], 1)

    def test_selected_asset_detail_exposes_pipeline_summary_and_image_data(self) -> None:
        self.assertTrue(self.panel.select_asset("assets/characters/hero_ready.png"))
        detail = self.panel.get_selected_asset_detail()

        self.assertEqual(detail["relative_path"], "assets/characters/hero_ready.png")
        self.assertEqual(detail["asset_kind"], "texture")
        self.assertEqual(detail["importer"], "texture")
        self.assertTrue(detail["guid_short"])
        self.assertEqual(detail["image_width"], 1)
        self.assertEqual(detail["image_height"], 1)
        self.assertEqual(detail["slice_count"], 1)
        self.assertEqual(detail["pipeline_detail"], "sprite ready")
        self.assertTrue(detail["has_meta"])

    def test_panel_can_request_open_sprite_editor_for_selected_image(self) -> None:
        self.assertTrue(self.panel.select_asset("assets/characters/hero_ready.png"))
        self.assertTrue(self.panel.open_selected_sprite_editor())
        self.assertEqual(self.panel.request_open_sprite_editor_for, "assets/characters/hero_ready.png")

    def test_panel_can_request_open_scene_for_selected_scene(self) -> None:
        self.assertTrue(self.panel.select_asset("levels/intro.json"))
        self.assertTrue(self.panel.open_selected_scene())
        self.assertEqual(self.panel.request_open_scene_for, "levels/intro.json")


class ProjectPanelSourceRegressionTests(unittest.TestCase):
    def test_project_panel_accepts_service_without_loaded_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_service = ProjectService(root, auto_ensure=False)
            panel = ProjectPanel(root.as_posix())

            panel.set_project_service(project_service)

            self.assertIs(panel.project_service, project_service)
            self.assertIsNone(panel.asset_service)
            self.assertEqual(panel.root_path, project_service.editor_root.as_posix())
            self.assertFalse(project_service.has_project)

    def test_project_panel_does_not_reference_modal_or_private_runtime_hooks(self) -> None:
        source = Path("engine/editor/project_panel.py").read_text(encoding="utf-8")
        forbidden_tokens = (
            "sprite_editor_modal",
            "._input_system",
            "._event_bus",
            "._process_ui_requests(",
        )

        for token in forbidden_tokens:
            self.assertNotIn(token, source, msg=f"engine/editor/project_panel.py still references {token}")


if __name__ == "__main__":
    unittest.main()
