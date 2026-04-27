import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.api import EngineAPI
from engine.assets.asset_service import AssetService
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


class AssetDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_service = ProjectService(self.root)
        self.asset_service = AssetService(self.project_service)
        self.api: EngineAPI | None = None

    def tearDown(self) -> None:
        if self.api is not None:
            self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_png(self, relative_path: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MINIMAL_PNG_BYTES)
        return path

    def _write_script(self, relative_path: str, contents: str = "def on_play(context):\n    context.public_data['loaded'] = True\n") -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def _write_prefab(self, relative_path: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": "EnemyPrefab", "components": {}}, indent=4), encoding="utf-8")
        return path

    def _write_level(self, relative_path: str, entities: list[dict]) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": "Level", "entities": entities, "rules": []}, indent=4), encoding="utf-8")
        return path

    def test_refresh_catalog_indexes_assets_scripts_prefabs_and_levels(self) -> None:
        self._write_png("assets/player.png")
        self._write_script("scripts/brain.py")
        self._write_prefab("prefabs/enemy.prefab")
        self._write_level("levels/intro.json", [])

        catalog = self.asset_service.refresh_catalog()
        by_path = {item["path"]: item for item in catalog["assets"]}

        self.assertEqual(by_path["assets/player.png"]["asset_kind"], "texture")
        self.assertEqual(by_path["scripts/brain.py"]["asset_kind"], "script")
        self.assertEqual(by_path["prefabs/enemy.prefab"]["asset_kind"], "prefab")
        self.assertEqual(by_path["levels/intro.json"]["asset_kind"], "scene_data")
        self.assertTrue((self.root / "assets" / "player.png.meta.json").exists())
        self.assertTrue((self.root / "scripts" / "brain.py.meta.json").exists())
        self.assertTrue(by_path["assets/player.png"]["guid"].startswith("ast_"))

    def test_sqlite_rebuild_creates_incremental_index_with_expected_fields(self) -> None:
        self._write_png("assets/player.png")
        self._write_script("scripts/brain.py")
        database = self.asset_service.get_asset_database()

        self.assertFalse(database.index_exists())
        self.assertEqual(database.get_index_metadata(), {})
        self.assertIsNone(database.get_index_version())

        database.rebuild()

        self.assertEqual(database.get_index_path(), (self.root / ".motor" / "asset_index.sqlite").resolve())
        self.assertTrue(database.index_exists())
        metadata = database.get_index_metadata()
        self.assertEqual(metadata["schema_version"], database.INDEX_SCHEMA_VERSION)
        self.assertTrue(metadata["schema_valid"])
        self.assertTrue(metadata["assets_schema_valid"])
        self.assertEqual(database.get_index_version(), database.INDEX_SCHEMA_VERSION)
        entries = {item["path"]: item for item in database.list_assets()}
        player = entries["assets/player.png"]
        self.assertTrue(player["guid"].startswith("ast_"))
        self.assertEqual(player["absolute_path"], (self.root / "assets" / "player.png").resolve().as_posix())
        self.assertEqual(player["extension"], ".png")
        self.assertEqual(player["type"], "texture")
        self.assertEqual(player["size"], len(MINIMAL_PNG_BYTES))
        self.assertEqual(player["display_name"], "player")
        self.assertEqual(entries["scripts/brain.py"]["type"], "script")

    def test_sqlite_list_assets_filters_by_search_and_extensions(self) -> None:
        self._write_png("assets/player.png")
        self._write_png("assets/enemy.png")
        self._write_script("scripts/player_brain.py")
        database = self.asset_service.get_asset_database()

        database.rebuild()

        paths = [item["path"] for item in database.list_assets(search="player")]
        self.assertEqual(paths, ["assets/player.png", "scripts/player_brain.py"])
        png_paths = [item["path"] for item in database.list_assets(extensions=["png"])]
        self.assertEqual(png_paths, ["assets/enemy.png", "assets/player.png"])

    def test_list_assets_with_existing_index_does_not_scan_filesystem(self) -> None:
        self._write_png("assets/player.png")
        self._write_png("assets/enemy.png")
        self._write_script("scripts/player_brain.py")
        database = self.asset_service.get_asset_database()
        database.rebuild()

        path_class = type(self.root)
        with patch.object(path_class, "rglob", side_effect=AssertionError("rglob should not run when index exists")):
            assets = database.list_assets(search="player")

        self.assertEqual([item["path"] for item in assets], ["assets/player.png", "scripts/player_brain.py"])

    def test_sqlite_get_by_path_and_guid_return_indexed_rows(self) -> None:
        self._write_png("assets/icon.png")
        database = self.asset_service.get_asset_database()

        database.rebuild()

        by_path = database.get_by_path("assets/icon.png")
        self.assertIsNotNone(by_path)
        by_guid = database.get_by_guid(by_path["guid"])
        self.assertEqual(by_guid, by_path)

    def test_sqlite_update_changed_adds_updates_and_removes_assets(self) -> None:
        script_path = self._write_script("scripts/brain.py", "value = 1\n")
        removed_path = self._write_png("assets/removed.png")
        database = self.asset_service.get_asset_database()
        database.rebuild()
        original = database.get_by_path("scripts/brain.py")

        script_path.write_text("value = 100\n", encoding="utf-8")
        future = script_path.stat().st_mtime + 10.0
        os.utime(script_path, (future, future))
        self._write_png("assets/added.png")
        removed_path.unlink()

        database.update_changed()

        updated = database.get_by_path("scripts/brain.py")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["size"], script_path.stat().st_size)
        self.assertGreater(updated["mtime"], original["mtime"])
        self.assertIsNotNone(database.get_by_path("assets/added.png"))
        self.assertIsNone(database.get_by_path("assets/removed.png"))
        self.assertEqual(database.get_index_version(), database.INDEX_SCHEMA_VERSION)
        self.assertTrue(database.get_index_metadata()["schema_valid"])

    def test_project_service_index_listing_still_exposes_only_project_assets(self) -> None:
        self._write_png("assets/icon.png")
        self._write_script("scripts/brain.py")
        database = self.asset_service.get_asset_database()

        database.rebuild()

        sqlite_paths = [item["path"] for item in database.list_assets()]
        project_service_paths = [item["path"] for item in self.project_service.list_assets()]
        self.assertIn("scripts/brain.py", sqlite_paths)
        self.assertEqual(project_service_paths, ["assets/icon.png"])

    def test_guid_resolution_survives_asset_move_and_updates_level_reference_paths(self) -> None:
        self._write_png("assets/player.png")
        self.asset_service.refresh_catalog()
        reference = self.asset_service.get_asset_reference("assets/player.png")
        level_path = self._write_level(
            "levels/intro.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Sprite": {"enabled": True, "texture": dict(reference), "texture_path": reference["path"]},
                    },
                }
            ],
        )

        moved = self.asset_service.move_asset(reference["guid"], "assets/characters/player.png")

        self.assertIsNotNone(moved)
        self.assertEqual(moved["path"], "assets/characters/player.png")
        resolved = self.asset_service.resolve_asset_path(reference)
        self.assertEqual(self.project_service.to_relative_path(resolved), "assets/characters/player.png")

        level_data = json.loads(level_path.read_text(encoding="utf-8"))
        sprite_data = level_data["entities"][0]["components"]["Sprite"]
        self.assertEqual(sprite_data["texture"]["path"], "assets/characters/player.png")
        self.assertEqual(sprite_data["texture"]["guid"], reference["guid"])

    def test_saving_scene_normalizes_legacy_asset_fields_to_reference_objects(self) -> None:
        self._write_png("assets/player.png")
        self._write_png("assets/player_sheet.png")
        self._write_script("scripts/player_logic.py")
        level_path = self._write_level(
            "levels/normalize.json",
            [
                {
                    "name": "AuthoringProbe",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Sprite": {"enabled": True, "texture_path": "assets/player.png", "width": 16, "height": 16},
                        "Animator": {
                            "enabled": True,
                            "sprite_sheet": "assets/player_sheet.png",
                            "frame_width": 16,
                            "frame_height": 16,
                            "animations": {"idle": {"frames": [0], "fps": 8.0, "loop": True}},
                            "default_state": "idle",
                            "current_state": "idle",
                            "current_frame": 0,
                            "is_finished": False,
                        },
                        "AudioSource": {"enabled": True, "asset_path": "assets/player.wav"},
                        "ScriptBehaviour": {"enabled": True, "module_path": "scripts/player_logic.py", "public_data": {}},
                    },
                }
            ],
        )

        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level(level_path.as_posix())
        self.api.game.current_scene_path = level_path.as_posix()
        self.api.game.save_current_scene()

        level_data = json.loads(level_path.read_text(encoding="utf-8"))
        components = level_data["entities"][0]["components"]
        self.assertEqual(components["Sprite"]["texture"]["path"], "assets/player.png")
        self.assertEqual(components["Animator"]["sprite_sheet"]["path"], "assets/player_sheet.png")
        self.assertEqual(components["AudioSource"]["asset"]["path"], "assets/player.wav")
        self.assertEqual(components["ScriptBehaviour"]["script"]["path"], "scripts/player_logic.py")

    def test_script_behaviour_can_load_module_from_asset_reference(self) -> None:
        script_path = self._write_script(
            "scripts/nested/brain.py",
            "def on_play(context):\n"
            "    context.public_data['loaded'] = True\n",
        )
        self.asset_service.refresh_catalog()
        script_ref = self.asset_service.get_asset_reference("scripts/nested/brain.py")
        level_path = self._write_level(
            "levels/script_ref.json",
            [
                {
                    "name": "Scripted",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "ScriptBehaviour": {"enabled": True, "script": script_ref, "module_path": "nested.brain", "public_data": {}},
                    },
                }
            ],
        )

        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level(level_path.as_posix())
        self.api.play()
        self.api.step(1)

        public_data = self.api.get_script_public_data("Scripted")
        self.assertTrue(public_data["loaded"])
        self.assertTrue(script_path.exists())

    def test_api_list_assets_exposes_guid_kind_and_meta_status(self) -> None:
        self._write_png("assets/icon.png")
        self._write_prefab("prefabs/card.prefab")

        self.api = EngineAPI(project_root=self.root.as_posix())
        catalog_result = self.api.refresh_asset_catalog()
        self.assertTrue(catalog_result["success"])

        entries = {item["path"]: item for item in self.api.list_project_assets()}
        self.assertIn("assets/icon.png", entries)
        self.assertIn("prefabs/card.prefab", entries)
        self.assertTrue(entries["assets/icon.png"]["guid"].startswith("ast_"))
        self.assertEqual(entries["prefabs/card.prefab"]["asset_kind"], "prefab")
        self.assertTrue(entries["assets/icon.png"]["has_meta"])

    def test_repeated_slice_queries_reuse_cached_metadata(self) -> None:
        self._write_png("assets/player_sheet.png")
        self.asset_service.save_metadata(
            "assets/player_sheet.png",
            {
                "asset_type": "sprite_sheet",
                "import_mode": "manual",
                "slices": [
                    {
                        "name": "idle_0",
                        "x": 0,
                        "y": 0,
                        "width": 16,
                        "height": 16,
                        "pivot_x": 0.5,
                        "pivot_y": 0.5,
                    }
                ],
            },
        )
        cold_asset_service = AssetService(self.project_service)

        with patch("engine.assets.asset_database.json.load", wraps=json.load) as load_mock:
            first = cold_asset_service.get_slice_rect("assets/player_sheet.png", "idle_0")
            second = cold_asset_service.get_slice_rect("assets/player_sheet.png", "idle_0")

        self.assertEqual(first["width"], 16)
        self.assertEqual(second["width"], 16)
        self.assertEqual(load_mock.call_count, 1)

    def test_sprite_service_grid_contract_persists_canonical_pipeline_metadata(self) -> None:
        self._write_png("assets/player_sheet.png")

        metadata = self.asset_service.generate_sprite_grid_slices(
            "assets/player_sheet.png",
            cell_width=1,
            cell_height=1,
            naming_prefix="player",
        )

        self.assertEqual(metadata["asset_type"], "sprite_sheet")
        self.assertEqual(metadata["import_mode"], "grid")
        self.assertEqual(metadata["grid"]["cell_width"], 1)
        self.assertEqual(metadata["automatic"], {})
        self.assertEqual(metadata["import_settings"]["asset_type"], "sprite_sheet")
        self.assertEqual(metadata["import_settings"]["import_mode"], "grid")
        self.assertEqual(metadata["import_settings"]["grid"], metadata["grid"])
        self.assertEqual(metadata["import_settings"]["automatic"], {})
        self.assertEqual(metadata["import_settings"]["slices"], metadata["slices"])

        loaded = self.asset_service.get_sprite_metadata("assets/player_sheet.png")
        self.assertEqual(loaded["import_settings"]["grid"], metadata["grid"])
        self.assertEqual(loaded["slices"][0]["name"], "player_0")

    def test_sprite_service_mode_transition_clears_stale_import_settings(self) -> None:
        self._write_png("assets/player_sheet.png")

        with patch.object(
            self.asset_service,
            "preview_auto_slices",
            return_value=[{"name": "auto_0", "x": 0, "y": 0, "width": 1, "height": 1, "pivot_x": 0.5, "pivot_y": 0.5}],
        ):
            auto_metadata = self.asset_service.generate_sprite_auto_slices("assets/player_sheet.png", naming_prefix="auto")

        self.assertEqual(auto_metadata["import_mode"], "automatic")
        self.assertEqual(auto_metadata["grid"], {})
        self.assertEqual(auto_metadata["automatic"]["naming_prefix"], "auto")
        self.assertEqual(auto_metadata["import_settings"]["automatic"], auto_metadata["automatic"])

        manual_metadata = self.asset_service.save_sprite_manual_slices(
            "assets/player_sheet.png",
            [{"name": "manual_0", "x": 0, "y": 0, "width": 1, "height": 1}],
        )

        self.assertEqual(manual_metadata["import_mode"], "manual")
        self.assertEqual(manual_metadata["grid"], {})
        self.assertEqual(manual_metadata["automatic"], {})
        self.assertEqual(manual_metadata["import_settings"]["grid"], {})
        self.assertEqual(manual_metadata["import_settings"]["automatic"], {})
        self.assertEqual([item["name"] for item in manual_metadata["slices"]], ["manual_0"])
        self.assertEqual([item["name"] for item in manual_metadata["import_settings"]["slices"]], ["manual_0"])

    def test_sprite_service_query_contract_lists_slices_and_rects(self) -> None:
        self._write_png("assets/player_sheet.png")
        self.asset_service.generate_sprite_grid_slices(
            "assets/player_sheet.png",
            cell_width=1,
            cell_height=1,
            naming_prefix="query",
        )

        slices = self.asset_service.list_sprite_slices("assets/player_sheet.png")
        rect = self.asset_service.get_sprite_slice_rect("assets/player_sheet.png", "query_0")

        self.assertEqual([item["name"] for item in slices], ["query_0"])
        self.assertIsNotNone(rect)
        self.assertEqual(rect["width"], 1)
        self.assertEqual(rect["height"], 1)

    def test_sprite_asset_summary_reports_pipeline_status_and_image_data(self) -> None:
        self._write_png("assets/plain.png")
        self._write_png("assets/metadata_only.png")
        self._write_png("assets/unsliced_sheet.png")
        self._write_png("assets/ready_sheet.png")

        self.asset_service.save_metadata(
            "assets/metadata_only.png",
            {
                "asset_type": "texture",
                "import_mode": "raw",
                "grid": {},
                "automatic": {},
                "slices": [],
            },
        )
        self.asset_service.save_metadata(
            "assets/unsliced_sheet.png",
            {
                "asset_type": "sprite_sheet",
                "import_mode": "grid",
                "grid": {"cell_width": 1, "cell_height": 1},
                "automatic": {},
                "slices": [],
            },
        )
        self.asset_service.save_sprite_manual_slices(
            "assets/ready_sheet.png",
            [{"name": "idle_0", "x": 0, "y": 0, "width": 1, "height": 1}],
        )

        plain = self.asset_service.get_sprite_asset_summary("assets/plain.png")
        metadata_only = self.asset_service.get_sprite_asset_summary("assets/metadata_only.png")
        unsliced = self.asset_service.get_sprite_asset_summary("assets/unsliced_sheet.png")
        ready = self.asset_service.get_sprite_asset_summary("assets/ready_sheet.png")

        self.assertEqual(plain["pipeline_status"], "image")
        self.assertEqual(metadata_only["pipeline_status"], "metadata")
        self.assertEqual(unsliced["pipeline_status"], "needs slicing")
        self.assertEqual(ready["pipeline_status"], "ready")
        self.assertEqual(ready["slice_count"], 1)
        self.assertEqual(tuple(ready["image_size"]), (1, 1))
        self.assertTrue(ready["has_metadata"])

    def test_absolute_project_paths_resolve_without_recursive_refresh(self) -> None:
        absolute_path = self._write_png("assets/player.png")
        self.asset_service.refresh_catalog()

        entry = self.asset_service.get_asset_entry(absolute_path.as_posix())

        self.assertIsNotNone(entry)
        self.assertEqual(entry["path"], "assets/player.png")

    def test_catalog_infers_scene_and_prefab_dependencies_and_reverse_references(self) -> None:
        self._write_png("assets/player.png")
        self._write_script("scripts/brain.py")
        self._write_prefab("prefabs/enemy.prefab")
        self._write_level(
            "levels/deps.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Sprite": {"enabled": True, "texture_path": "assets/player.png"},
                        "ScriptBehaviour": {"enabled": True, "module_path": "brain", "script": {"path": "scripts/brain.py", "guid": ""}, "public_data": {}},
                    },
                    "prefab_instance": {"prefab_path": "prefabs/enemy.prefab", "root_name": "Enemy", "overrides": {}},
                }
            ],
        )

        catalog = self.asset_service.refresh_catalog()
        by_path = {item["path"]: item for item in catalog["assets"]}

        self.assertIn("assets/player.png", by_path["levels/deps.json"]["dependencies"])
        self.assertIn("scripts/brain.py", by_path["levels/deps.json"]["dependencies"])
        self.assertIn("prefabs/enemy.prefab", by_path["levels/deps.json"]["dependencies"])
        self.assertIn("levels/deps.json", by_path["assets/player.png"]["referenced_by"])

    def test_build_asset_artifacts_uses_hashes_and_cache_hits(self) -> None:
        self._write_png("assets/player.png")
        self.asset_service.refresh_catalog()

        first = self.asset_service.build_asset_artifacts()
        artifact = next(item for item in first["artifacts"] if item["path"] == "assets/player.png")
        self.assertFalse(artifact["cache_hit"])

        second = self.asset_service.build_asset_artifacts()
        artifact_second = next(item for item in second["artifacts"] if item["path"] == "assets/player.png")
        self.assertTrue(artifact_second["cache_hit"])

        metadata = self.asset_service.load_metadata("assets/player.png")
        metadata["import_settings"]["compression"] = "none"
        self.asset_service.save_metadata("assets/player.png", metadata)
        third = self.asset_service.build_asset_artifacts()
        artifact_third = next(item for item in third["artifacts"] if item["path"] == "assets/player.png")
        self.assertFalse(artifact_third["cache_hit"])

    def test_bundle_report_is_generated_with_top_assets(self) -> None:
        self._write_png("assets/player.png")
        self._write_script("scripts/brain.py")
        self.asset_service.refresh_catalog()

        report = self.asset_service.create_bundle()

        self.assertTrue(Path(report["bundle_path"]).exists())
        self.assertGreaterEqual(report["asset_count"], 2)
        self.assertTrue(report["top_assets_by_size"])


if __name__ == "__main__":
    unittest.main()
