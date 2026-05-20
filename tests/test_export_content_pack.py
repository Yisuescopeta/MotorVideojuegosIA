"""Tests for content pack builder."""

import json
import tempfile
import unittest
from pathlib import Path

from engine.export.build_graph import build_content_graph
from engine.export.content_collector import collect_content, write_manifest, write_pak


class TestContentCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.levels = self.tmp / "levels"
        self.levels.mkdir(parents=True)
        self.assets = self.tmp / "assets"
        self.assets.mkdir(parents=True)
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _write_scene(self, name: str, data: dict):
        path = self.levels / name
        path.write_text(json.dumps(data), encoding="utf-8")

    def _write_asset(self, name: str, content: str = ""):
        path = self.assets / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_collect_copies_assets(self):
        self._write_asset("player.png", "fake_png")
        self._write_scene("main.json", {
            "entities": [
                {"components": {"Sprite": {"texture_path": "assets/player.png"}}},
            ],
        })
        graph = build_content_graph("levels/main.json", str(self.tmp))
        manifest = collect_content(graph, str(self.tmp), str(self.staging))

        self.assertEqual(len(manifest.assets), 1)
        self.assertEqual(manifest.assets[0].path, "assets/player.png")
        self.assertEqual(manifest.assets[0].kind, "texture")
        self.assertGreater(manifest.assets[0].size_bytes, 0)
        self.assertNotEqual(manifest.assets[0].sha256, "")
        self.assertTrue(manifest.assets[0].guid.startswith("guid_"))

        copied = self.staging / "content" / "assets" / "player.png"
        self.assertTrue(copied.exists())

    def test_manifest_generation(self):
        self._write_asset("sprite.png", "data")
        self._write_scene("main.json", {
            "entities": [
                {"components": {"Sprite": {"texture_path": "assets/sprite.png"}}},
            ],
        })
        graph = build_content_graph("levels/main.json", str(self.tmp))
        manifest = collect_content(graph, str(self.tmp), str(self.staging))

        d = manifest.to_dict()
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["entry_scene"], "levels/main.json")
        self.assertIn("assets", d)
        self.assertIn("scenes", d)
        self.assertIn("scripts", d)

    def test_write_manifest_file(self):
        self._write_scene("main.json", {"entities": []})
        graph = build_content_graph("levels/main.json", str(self.tmp))
        manifest = collect_content(graph, str(self.tmp), str(self.staging))
        manifest_path = write_manifest(manifest, str(self.staging))

        self.assertTrue(manifest_path.exists())
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["entry_scene"], "levels/main.json")

    def test_write_pak_file(self):
        self._write_asset("sprite.png", "data")
        self._write_scene("main.json", {
            "entities": [
                {"components": {"Sprite": {"texture_path": "assets/sprite.png"}}},
            ],
        })
        graph = build_content_graph("levels/main.json", str(self.tmp))
        manifest = collect_content(graph, str(self.tmp), str(self.staging))
        write_manifest(manifest, str(self.staging))
        pak_path = write_pak(str(self.staging))

        self.assertTrue(pak_path.exists())
        self.assertGreater(pak_path.stat().st_size, 0)

    def test_project_info_from_project_json(self):
        (self.tmp / "project.json").write_text(
            json.dumps({"name": "TestGame", "version": "2.0"}),
            encoding="utf-8",
        )
        self._write_scene("main.json", {"entities": []})
        graph = build_content_graph("levels/main.json", str(self.tmp))
        manifest = collect_content(graph, str(self.tmp), str(self.staging))

        self.assertEqual(manifest.project["name"], "TestGame")
        self.assertEqual(manifest.project["version"], "2.0")

    def test_scenes_collected(self):
        self._write_scene("main.json", {
            "entities": [],
            "feature_metadata": {"scene_flow": {"next_scene": "levels/sub.json"}},
        })
        self._write_scene("sub.json", {"entities": []})
        graph = build_content_graph("levels/main.json", str(self.tmp))
        manifest = collect_content(graph, str(self.tmp), str(self.staging))

        self.assertGreaterEqual(len(manifest.scenes), 1)
        scene_paths = [s.path for s in manifest.scenes]
        self.assertIn("levels/main.json", scene_paths)


if __name__ == "__main__":
    unittest.main()
