"""Tests for ContentLoader scene loading from game.pak."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine.runtime.content_loader import ContentLoader
from engine.runtime.runtime_project_service import RuntimeProjectService


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
        if scenes is None:
            scenes = {"levels/main.json": {"entities": []}}
        
        # Compute real SHA-256 for each scene
        scene_entries = []
        for rel, data in scenes.items():
            content = json.dumps(data, ensure_ascii=True).encode("utf-8")
            sha = hashlib.sha256(content).hexdigest()
            scene_entries.append({
                "guid": f"g_{rel}", "path": rel, "kind": "scene",
                "sha256": sha, "size_bytes": len(content), "dependencies": [],
            })

        manifest = {
            "schema_version": 1,
            "entry_scene": "levels/main.json",
            "project": {"name": "Test", "version": "0.1.0"},
            "assets": [],
            "scenes": scene_entries,
            "scripts": [],
        }
        pak_path = self.tmp / "game.pak"
        with zipfile.ZipFile(pak_path, "w", compression=zipfile.ZIP_DEFLATED) as pak:
            pak.writestr("game.manifest.json", json.dumps(manifest))
            for rel, data in scenes.items():
                pak.writestr(rel, json.dumps(data, ensure_ascii=True))
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

    def test_verify_integrity_valid(self):
        scenes = {"levels/main.json": {"entities": []}}
        self._build_pak(scenes)
        # Also write scene to filesystem for integrity check
        self._write_scene("levels/main.json", {"entities": []})
        loader = ContentLoader(self.tmp)
        result = loader.verify_integrity()
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["tampered"]), 0)

    def test_verify_integrity_missing_file_from_pak(self):
        """When file not on FS, ContentLoader reads from pak and verifies hash."""
        scenes = {"levels/main.json": {"entities": []}}
        self._build_pak(scenes)
        loader = ContentLoader(self.tmp)
        result = loader.verify_integrity()
        # File is only in pak, but should be found via _read_manifest_from_pak
        # and hashed from pak data
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["tampered"]), 0)

    def test_verify_integrity_tampered(self):
        scenes = {"levels/main.json": {"entities": [{"id": "x"}]}}
        self._build_pak(scenes)
        # Write tampered file on filesystem — content differs from pak, hash mismatch
        (self.content_dir / "levels" / "main.json").write_text(
            json.dumps({"entities": [{"id": "tampered"}]}), encoding="utf-8",
        )
        loader = ContentLoader(self.tmp)
        result = loader.verify_integrity()
        self.assertFalse(result["valid"])
        self.assertIn("levels/main.json", result["tampered"])

    def test_verify_integrity_missing_entry(self):
        manifest = {
            "schema_version": 1,
            "entry_scene": "levels/main.json",
            "project": {"name": "Test", "version": "0.1.0"},
            "assets": [],
            "scenes": [
                {"guid": "g1", "path": "levels/missing.json", "kind": "scene",
                 "sha256": "abc123", "size_bytes": 100, "dependencies": []},
            ],
            "scripts": [],
        }
        pak_path = self.tmp / "game.pak"
        with zipfile.ZipFile(pak_path, "w", compression=zipfile.ZIP_DEFLATED) as pak:
            pak.writestr("game.manifest.json", json.dumps(manifest))
        loader = ContentLoader(self.tmp)
        result = loader.verify_integrity()
        self.assertFalse(result["valid"])
        self.assertIn("levels/missing.json", result["tampered"])


class TestRuntimeProjectServiceSlices(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _metadata_payload(self) -> dict:
        return {
            "path": "assets/player.png",
            "import_settings": {
                "slices": [
                    {"name": "idle_0", "x": 4, "y": 8, "width": 16, "height": 24, "pivot_x": 0.5, "pivot_y": 0.5},
                ],
            },
        }

    def test_get_slice_rect_from_directory_sidecar(self):
        metadata_path = self.tmp / "assets" / "player.png.meta.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(self._metadata_payload()), encoding="utf-8")

        service = RuntimeProjectService(self.tmp)
        rect = service.get_slice_rect({"path": "assets/player.png", "guid": ""}, "idle_0")

        self.assertEqual(rect["x"], 4)
        self.assertEqual(rect["y"], 8)
        self.assertEqual(rect["width"], 16)
        self.assertEqual(rect["height"], 24)

    def test_get_slice_rect_from_packed_sidecar(self):
        manifest = {
            "schema_version": 1,
            "entry_scene": "levels/main.json",
            "assets": [
                {"guid": "guid_player", "path": "assets/player.png", "kind": "texture", "sha256": "", "size_bytes": 0, "dependencies": []},
                {"guid": "guid_player_meta", "path": "assets/player.png.meta.json", "kind": "data", "sha256": "", "size_bytes": 0, "dependencies": []},
            ],
            "scenes": [],
            "scripts": [],
        }
        with zipfile.ZipFile(self.tmp / "game.pak", "w", compression=zipfile.ZIP_DEFLATED) as pak:
            pak.writestr("game.manifest.json", json.dumps(manifest))
            pak.writestr("assets/player.png.meta.json", json.dumps(self._metadata_payload()))

        service = RuntimeProjectService(self.tmp)
        rect = service.get_slice_rect("assets/player.png", "idle_0")

        self.assertEqual(rect["x"], 4)
        self.assertEqual(rect["y"], 8)
        self.assertEqual(rect["width"], 16)
        self.assertEqual(rect["height"], 24)


if __name__ == "__main__":
    unittest.main()
