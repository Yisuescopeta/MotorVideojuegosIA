from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pyray as rl

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
        self._write_text("assets/readme.txt")
        self._write_text("audio/theme.ogg")
        self._write_text("materials/wall.material")

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

    def _write_text(self, relative_path: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("notes\n", encoding="utf-8")

    def _asset_item(self, relative_path: str) -> dict:
        item = self.panel._build_file_entry((self.root / relative_path).as_posix())
        assert item is not None
        return item

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

    def test_file_entry_infers_asset_kind_from_extension_when_unknown(self) -> None:
        cases = (
            ("scripts/player_logic.py", "script"),
            ("prefabs/enemy.prefab", "prefab"),
            ("audio/theme.ogg", "audio"),
            ("materials/wall.material", "material"),
            ("levels/intro.json", "scene_data"),
            ("assets/readme.txt", "unknown"),
        )

        for relative_path, expected_kind in cases:
            with self.subTest(relative_path=relative_path):
                item = self.panel._build_file_entry_from_entry(
                    {
                        "name": Path(relative_path).name,
                        "path": relative_path,
                        "absolute_path": (self.root / relative_path).as_posix(),
                        "asset_kind": "unknown",
                        "importer": "unknown",
                    }
                )
                self.assertIsNotNone(item)
                self.assertEqual(item["asset_kind"], expected_kind)

    def test_panel_can_request_open_sprite_editor_for_selected_image(self) -> None:
        self.assertTrue(self.panel.select_asset("assets/characters/hero_ready.png"))
        self.assertTrue(self.panel.open_selected_sprite_editor())
        self.assertEqual(self.panel.request_open_sprite_editor_for, "assets/characters/hero_ready.png")

    def test_panel_can_request_open_scene_for_selected_scene(self) -> None:
        self.assertTrue(self.panel.select_asset("levels/intro.json"))
        self.assertTrue(self.panel.open_selected_scene())
        self.assertEqual(self.panel.request_open_scene_for, "levels/intro.json")

    def test_view_mode_defaults_to_grid_and_valid_changes_reset_scroll(self) -> None:
        self.assertEqual(self.panel.get_view_mode(), "grid")

        self.panel.scroll_offset = 42.0
        self.panel.set_view_mode("list")
        self.assertEqual(self.panel.get_view_mode(), "list")
        self.assertEqual(self.panel.scroll_offset, 0.0)

        self.panel.scroll_offset = 23.0
        self.panel.set_view_mode("list")
        self.assertEqual(self.panel.get_view_mode(), "list")
        self.assertEqual(self.panel.scroll_offset, 0.0)

        self.panel.scroll_offset = 17.0
        self.panel.set_view_mode("invalid")
        self.assertEqual(self.panel.get_view_mode(), "list")
        self.assertEqual(self.panel.scroll_offset, 17.0)

    def test_set_project_service_resets_view_mode_and_click_tracking(self) -> None:
        self.panel.set_view_mode("list")
        self.panel._last_click_key = "asset"
        self.panel._last_click_time = 1.0
        self.panel.thumbnail_provider._textures["fake"] = object()

        self.panel.set_project_service(self.project_service)

        self.assertEqual(self.panel.get_view_mode(), "grid")
        self.assertIsNone(self.panel._last_click_key)
        self.assertEqual(self.panel._last_click_time, -1.0)
        self.assertEqual(self.panel.thumbnail_provider._textures, {})

    def test_compute_list_view_rows_scroll_zero_offset_empty_and_bounded(self) -> None:
        self.panel._visible_entries = [{"name": f"item{i}"} for i in range(10)]
        self.panel.scroll_offset = 0.0

        rows = self.panel._compute_list_view_rows(10, 20, 200, self.panel.LIST_ROW_HEIGHT * 2)
        self.assertEqual([row["index"] for row in rows], [0, 1])
        self.assertEqual(rows[0]["x"], 10)
        self.assertEqual(rows[0]["y"], 20)

        self.panel.scroll_offset = float(self.panel.LIST_ROW_HEIGHT)
        rows = self.panel._compute_list_view_rows(10, 20, 200, self.panel.LIST_ROW_HEIGHT * 2)
        self.assertEqual([row["index"] for row in rows], [1, 2])

        self.panel._visible_entries = []
        self.assertEqual(self.panel._compute_list_view_rows(10, 20, 200, 100), [])

    def test_is_double_click_true_and_false_cases(self) -> None:
        self.panel._last_click_key = "a"
        self.panel._last_click_time = 1.0

        self.assertTrue(self.panel._is_double_click(1.2, "a"))
        self.assertFalse(self.panel._is_double_click(1.5, "a"))
        self.assertFalse(self.panel._is_double_click(1.2, "b"))
        self.assertFalse(self.panel._is_double_click(0.9, "a"))

    def test_double_click_image_sets_sprite_editor_request(self) -> None:
        item = self._asset_item("assets/plain.png")
        mouse = rl.Vector2(1, 1)

        self.assertFalse(self.panel._handle_file_item_click(item, mouse, now=10.0))
        self.assertTrue(self.panel._handle_file_item_click(item, mouse, now=10.2))

        self.assertEqual(self.panel.request_open_sprite_editor_for, "assets/plain.png")

    def test_double_click_scene_sets_scene_open_request(self) -> None:
        item = self._asset_item("levels/intro.json")
        mouse = rl.Vector2(1, 1)

        self.assertFalse(self.panel._handle_file_item_click(item, mouse, now=10.0))
        self.assertTrue(self.panel._handle_file_item_click(item, mouse, now=10.2))

        self.assertEqual(self.panel.request_open_scene_for, "levels/intro.json")

    def test_double_click_script_reveals_and_selects_without_open_requests(self) -> None:
        item = self._asset_item("scripts/player_logic.py")
        mouse = rl.Vector2(1, 1)

        self.assertFalse(self.panel._handle_file_item_click(item, mouse, now=10.0))
        self.assertTrue(self.panel._handle_file_item_click(item, mouse, now=10.2))

        self.assertIsNone(self.panel.request_open_sprite_editor_for)
        self.assertIsNone(self.panel.request_open_scene_for)
        self.assertEqual(Path(self.panel.selected_file), self.root / "scripts/player_logic.py")
        self.assertEqual(Path(self.panel.current_path), self.root / "scripts")

    def test_double_click_prefab_reveals_and_resets_hiding_filter(self) -> None:
        self.panel.set_asset_filter("images")
        item = self._asset_item("prefabs/enemy.prefab")
        mouse = rl.Vector2(1, 1)

        self.assertFalse(self.panel._handle_file_item_click(item, mouse, now=20.0))
        self.assertTrue(self.panel._handle_file_item_click(item, mouse, now=20.2))

        self.assertEqual(self.panel.asset_filter, "all")
        self.assertIsNone(self.panel.request_open_sprite_editor_for)
        self.assertIsNone(self.panel.request_open_scene_for)
        self.assertEqual(Path(self.panel.selected_file), self.root / "prefabs/enemy.prefab")
        self.assertEqual(Path(self.panel.current_path), self.root / "prefabs")

    def test_double_click_unknown_reveals_without_open_requests(self) -> None:
        item = self._asset_item("assets/readme.txt")
        mouse = rl.Vector2(1, 1)

        self.assertFalse(self.panel._handle_file_item_click(item, mouse, now=30.0))
        self.assertTrue(self.panel._handle_file_item_click(item, mouse, now=30.2))

        self.assertIsNone(self.panel.request_open_sprite_editor_for)
        self.assertIsNone(self.panel.request_open_scene_for)
        self.assertEqual(Path(self.panel.selected_file), self.root / "assets/readme.txt")

    def test_draw_item_icon_delegates_to_thumbnail_provider(self) -> None:
        calls = []

        class FakeThumbnailProvider:
            def draw_item_icon(self, rect, item):
                calls.append((rect, item))

            def clear(self):
                pass

        provider = FakeThumbnailProvider()
        self.panel.thumbnail_provider = provider
        rect = rl.Rectangle(1, 2, 3, 4)
        item = self._asset_item("assets/plain.png")

        self.panel._draw_item_icon(rect, item)

        self.assertEqual(calls, [(rect, item)])


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
            "engine.core.game",
            "scene_manager",
            "Game(",
        )

        for token in forbidden_tokens:
            self.assertNotIn(token, source, msg=f"engine/editor/project_panel.py still references {token}")


if __name__ == "__main__":
    unittest.main()
