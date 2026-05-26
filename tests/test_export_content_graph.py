"""Tests for export content graph."""

import json
import tempfile
import unittest
from pathlib import Path

from engine.export.build_graph import build_content_graph


class TestBuildGraph(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.levels = self.tmp / "levels"
        self.levels.mkdir(parents=True)
        self.assets = self.tmp / "assets"
        self.assets.mkdir(parents=True)
        self.scripts = self.tmp / "scripts"
        self.scripts.mkdir(parents=True)

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

    def test_empty_scene_produces_no_assets(self):
        self._write_scene("empty.json", {"entities": []})
        result = build_content_graph("levels/empty.json", str(self.tmp))
        self.assertEqual(result.entry_scene, "levels/empty.json")
        self.assertEqual(len(result.reachable_assets), 0)
        self.assertEqual(len(result.reachable_scripts), 0)

    def test_detects_texture_path(self):
        self._write_asset("player.png")
        self._write_scene("test.json", {
            "entities": [
                {"name": "Player", "components": {"Sprite": {"texture_path": "assets/player.png"}}},
            ],
        })
        result = build_content_graph("levels/test.json", str(self.tmp))
        self.assertIn("assets/player.png", result.reachable_assets)

    def test_detects_prefab_path(self):
        self._write_asset("hero.prefab.json")
        self._write_scene("main.json", {
            "entities": [
                {"prefab_path": "assets/hero.prefab.json"},
            ],
        })
        result = build_content_graph("levels/main.json", str(self.tmp))
        self.assertIn("assets/hero.prefab.json", result.reachable_assets)

    def test_detects_script_path(self):
        script_path = self.scripts / "player.py"
        script_path.write_text("pass", encoding="utf-8")
        self._write_scene("test.json", {
            "entities": [
                {"name": "Player", "components": {"ScriptBehaviour": {"script_path": "scripts/player.py"}}},
            ],
        })
        result = build_content_graph("levels/test.json", str(self.tmp))
        self.assertIn("scripts/player.py", result.reachable_scripts)

    def test_script_literal_asset_dependencies_are_reachable(self):
        self._write_asset("player_speed.png")
        script_path = self.scripts / "player_powerups.py"
        script_path.write_text('SPEED_SHEET = "assets/player_speed.png"\n', encoding="utf-8")
        self._write_scene("test.json", {
            "entities": [
                {"components": {"ScriptBehaviour": {"script": {"path": "scripts/player_powerups.py"}}}},
            ],
        })

        result = build_content_graph("levels/test.json", str(self.tmp))

        self.assertIn("scripts/player_powerups.py", result.reachable_scripts)
        self.assertIn("assets/player_speed.png", result.reachable_assets)

    def test_script_metadata_dependencies_are_reachable(self):
        self._write_asset("player_jump.png")
        script_path = self.scripts / "player_powerups.py"
        script_path.write_text("VALUE = 1\n", encoding="utf-8")
        (self.scripts / "player_powerups.py.meta.json").write_text(
            json.dumps({"dependencies": ["assets/player_jump.png"]}),
            encoding="utf-8",
        )
        self._write_scene("test.json", {
            "entities": [
                {"components": {"ScriptBehaviour": {"script": {"path": "scripts/player_powerups.py"}}}},
            ],
        })

        result = build_content_graph("levels/test.json", str(self.tmp))

        self.assertIn("assets/player_jump.png", result.reachable_assets)

    def test_detects_missing_asset(self):
        self._write_scene("test.json", {
            "entities": [
                {"name": "Ghost", "components": {"Sprite": {"texture_path": "assets/missing.png"}}},
            ],
        })
        result = build_content_graph("levels/test.json", str(self.tmp))
        self.assertIn("assets/missing.png", result.missing_assets)

    def test_scene_flow_followed(self):
        self._write_scene("scene_a.json", {
            "entities": [],
            "feature_metadata": {"scene_flow": {"next_scene": "levels/scene_b.json"}},
        })
        self._write_scene("scene_b.json", {
            "entities": [],
        })
        result = build_content_graph("levels/scene_a.json", str(self.tmp))
        self.assertIn("levels/scene_b.json", result.reachable_scenes)

    def test_no_infinite_loop(self):
        self._write_scene("loop.json", {
            "entities": [],
            "feature_metadata": {"scene_flow": {"next_scene": "levels/loop.json"}},
        })
        result = build_content_graph("levels/loop.json", str(self.tmp))
        self.assertEqual(len(result.warnings), 0)

    def test_nested_references_in_components(self):
        self._write_asset("img/tile.png")
        self._write_scene("nested.json", {
            "entities": [
                {
                    "name": "Map",
                    "components": {
                        "TileMap": {
                            "layers": [
                                {"tilemap_source": "assets/img/tile.png"},
                            ],
                        },
                    },
                },
            ],
        })
        result = build_content_graph("levels/nested.json", str(self.tmp))
        self.assertIn("assets/img/tile.png", result.reachable_assets)

    def test_sorted_output(self):
        self._write_asset("img/a.png")
        self._write_asset("img/z.png")
        self._write_scene("sort.json", {
            "entities": [
                {"components": {"Sprite": {"texture_path": "assets/img/z.png"}}},
                {"components": {"Sprite": {"texture_path": "assets/img/a.png"}}},
            ],
        })
        result = build_content_graph("levels/sort.json", str(self.tmp))
        assets = result.reachable_assets
        self.assertEqual(assets, sorted(assets))


if __name__ == "__main__":
    unittest.main()
