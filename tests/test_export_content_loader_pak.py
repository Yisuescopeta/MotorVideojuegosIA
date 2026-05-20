"""Tests for ContentLoader scene loading from game.pak."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine.runtime.content_loader import ContentLoader


class TestContentLoaderPakSceneLoading(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.content_dir = self.tmp / "content"
        self.content_dir.mkdir(parents=True)
        (self.content_dir / "levels").mkdir(parents=True)
        (self.content_dir / "assets").mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _write_scene(self, rel_path: str, data: dict):
        full = self.content_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(json.dumps(data), encoding="utf-8")

    def _build_pak(self, scenes: dict[str, dict] | None = None):
        manifest = {
            "schema_version": 1,
            "entry_scene": "levels/main.json",
            "project": {"name": "Test", "version": "0.1.0"},
            "assets": [],
            "scenes": [
                {"guid": "g1", "path": "levels/main.json", "kind": "scene",
                 "sha256": "abc", "size_bytes": 100, "dependencies": []},
            ],
            "scripts": [],
        }
        if scenes is None:
            scenes = {"levels/main.json": {"entities": []}}
        pak_path = self.tmp / "game.pak"
        with zipfile.ZipFile(pak_path, "w", compression=zipfile.ZIP_DEFLATED) as pak:
            pak.writestr("game.manifest.json", json.dumps(manifest))
            for rel, data in scenes.items():
                pak.writestr(rel, json.dumps(data))
        return pak_path

    def test_load_scene_json_from_filesystem(self):
        self._write_scene("levels/main.json", {"entities": [{"id": "e1"}]})
        loader = ContentLoader(self.tmp)
        data = loader.load_scene_json("levels/main.json")
        self.assertIsNotNone(data)
        self.assertEqual(data["entities"][0]["id"], "e1")

    def test_load_scene_json_from_base_path(self):
        (self.tmp / "levels").mkdir(parents=True, exist_ok=True)
        (self.tmp / "levels" / "main.json").write_text(
            json.dumps({"entities": [{"id": "e2"}]}), encoding="utf-8",
        )
        loader = ContentLoader(self.tmp)
        data = loader.load_scene_json("levels/main.json")
        self.assertIsNotNone(data)
        self.assertEqual(data["entities"][0]["id"], "e2")

    def test_load_scene_json_from_pak(self):
        self._build_pak({"levels/main.json": {"entities": [{"id": "pak_e1"}]}})
        loader = ContentLoader(self.tmp)
        data = loader.load_scene_json("levels/main.json")
        self.assertIsNotNone(data)
        self.assertEqual(data["entities"][0]["id"], "pak_e1")

    def test_load_scene_json_filesystem_preferred_over_pak(self):
        self._write_scene("levels/main.json", {"entities": [{"id": "fs"}]})
        self._build_pak({"levels/main.json": {"entities": [{"id": "pak"}]}})
        loader = ContentLoader(self.tmp)
        data = loader.load_scene_json("levels/main.json")
        self.assertIsNotNone(data)
        self.assertEqual(data["entities"][0]["id"], "fs")

    def test_load_scene_json_not_found_returns_none(self):
        loader = ContentLoader(self.tmp)
        data = loader.load_scene_json("nonexistent.json")
        self.assertIsNone(data)

    def test_load_scene_json_from_pak_missing_entry(self):
        self._build_pak({"levels/main.json": {"entities": []}})
        loader = ContentLoader(self.tmp)
        data = loader.load_scene_json("levels/other.json")
        self.assertIsNone(data)

    def test_load_scene_json_lazy_loads_manifest(self):
        self._build_pak({"levels/main.json": {"entities": [{"id": "lazy"}]}})
        loader = ContentLoader(self.tmp)
        self.assertFalse(loader._loaded)
        data = loader.load_scene_json("levels/main.json")
        self.assertIsNotNone(data)
        self.assertTrue(loader._loaded)

    def test_get_entry_scene_from_pak(self):
        self._build_pak({"levels/main.json": {"entities": []}})
        loader = ContentLoader(self.tmp)
        entry = loader.get_entry_scene()
        self.assertEqual(entry, "levels/main.json")


if __name__ == "__main__":
    unittest.main()
