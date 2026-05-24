"""Tests for export entry-scene override APIs."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.export.exporter_registry import ExporterRegistry


class _FakeWindowsExporter:
    platform = "windows"

    def export(self, ctx) -> bool:
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        config_path = ctx.staging_dir / "runtime_config.json"
        config_path.write_text(
            json.dumps({"entry_scene": ctx.preset.entry_scene}, indent=2),
            encoding="utf-8",
        )
        artifact_path = ctx.output_dir / "Game.exe"
        artifact_path.write_text("stub", encoding="utf-8")
        ctx.add_artifact(artifact_path.relative_to(ctx.project_root).as_posix(), "binary")
        return True


class TestExportAPIEntrySceneOverride(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)
        (self.project_root / "levels").mkdir(parents=True, exist_ok=True)
        (self.project_root / "dist").mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text(
            json.dumps(
                {
                    "name": "Test Project",
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
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (self.project_root / "levels" / "main.json").write_text(
            json.dumps({"name": "Main Scene", "entities": []}, indent=2),
            encoding="utf-8",
        )
        (self.project_root / "levels" / "boss.json").write_text(
            json.dumps({"name": "Boss Scene", "entities": []}, indent=2),
            encoding="utf-8",
        )
        self.presets_path = self.project_root / "export_presets.motor.json"
        self.presets_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "presets": [
                        {
                            "name": "Windows Desktop",
                            "platform": "windows",
                            "mode": "release",
                            "output_path": "dist/windows/App",
                            "entry_scene": "levels/main.json",
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.api = EngineAPI(project_root=self.project_root.as_posix())
        self.original_exporter = ExporterRegistry._exporters.get("windows")
        ExporterRegistry._exporters["windows"] = _FakeWindowsExporter()

    def tearDown(self) -> None:
        if self.original_exporter is None:
            ExporterRegistry._exporters.pop("windows", None)
        else:
            ExporterRegistry._exporters["windows"] = self.original_exporter
        self.api.shutdown()
        self.tmpdir.cleanup()

    def test_build_export_for_scene_does_not_modify_export_presets_file(self) -> None:
        before = self.presets_path.read_text(encoding="utf-8")

        result = self.api.build_export_for_scene("Windows Desktop", "levels/boss.json")

        self.assertTrue(result["success"])
        self.assertEqual(before, self.presets_path.read_text(encoding="utf-8"))

    def test_build_export_for_scene_writes_runtime_config_with_override(self) -> None:
        result = self.api.build_export_for_scene("Windows Desktop", "levels/boss.json")

        self.assertTrue(result["success"])
        config_path = self.project_root / ".motor" / "build" / "staging" / "Windows_Desktop" / "runtime_config.json"
        self.assertTrue(config_path.exists())
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["entry_scene"], "levels/boss.json")
        self.assertEqual(result["data"]["effective_entry_scene"], "levels/boss.json")
        self.assertEqual(result["data"]["entry_scene_override"], "levels/boss.json")

    def test_build_export_keeps_using_preset_entry_scene_without_override(self) -> None:
        result = self.api.build_export("Windows Desktop")

        self.assertTrue(result["success"])
        config_path = self.project_root / ".motor" / "build" / "staging" / "Windows_Desktop" / "runtime_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["entry_scene"], "levels/main.json")
        self.assertEqual(result["data"]["effective_entry_scene"], "levels/main.json")
        self.assertIsNone(result["data"]["entry_scene_override"])

    def test_build_export_for_scene_returns_actionable_error_for_missing_scene(self) -> None:
        result = self.api.build_export_for_scene("Windows Desktop", "levels/missing.json")

        self.assertFalse(result["success"])
        errors = result["data"]["errors"]
        self.assertTrue(any(error["code"] == "ENTRY_SCENE_NOT_FOUND" for error in errors))

    def test_build_export_for_scene_returns_actionable_error_for_blank_scene(self) -> None:
        result = self.api.build_export_for_scene("Windows Desktop", "   ")

        self.assertFalse(result["success"])
        errors = result["data"]["errors"]
        self.assertTrue(any(error["code"] == "ENTRY_SCENE_REQUIRED" for error in errors))

    def test_list_export_entry_scenes_returns_relative_scene_paths_and_active_scene(self) -> None:
        self.api.load_level((self.project_root / "levels" / "boss.json").as_posix())

        result = self.api.list_export_entry_scenes()

        self.assertTrue(result["success"])
        paths = [scene["path"] for scene in result["data"]["scenes"]]
        self.assertIn("levels/main.json", paths)
        self.assertIn("levels/boss.json", paths)
        self.assertEqual(result["data"]["active_scene"], "levels/boss.json")

    def test_list_export_entry_scenes_filters_stale_missing_scene_records(self) -> None:
        original = self.api.project_service.list_project_scenes

        def _stale_listing() -> list[dict[str, str]]:
            return list(original()) + [
                {
                    "name": "Missing Scene",
                    "path": "levels/main_scene.json",
                    "absolute_path": (self.project_root / "levels" / "main_scene.json").as_posix(),
                }
            ]

        self.api.project_service.list_project_scenes = _stale_listing

        result = self.api.list_export_entry_scenes()

        paths = [scene["path"] for scene in result["data"]["scenes"]]
        self.assertNotIn("levels/main_scene.json", paths)


if __name__ == "__main__":
    unittest.main()
