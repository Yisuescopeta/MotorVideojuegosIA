import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.getcwd())

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
