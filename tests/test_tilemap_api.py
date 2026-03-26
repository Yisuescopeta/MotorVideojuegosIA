import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI


class TilemapApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "TilemapProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self) -> Path:
        scene = {
            "name": "TilemapScene",
            "entities": [
                {
                    "name": "Grid",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Tilemap": {
                            "cell_width": 16,
                            "cell_height": 16,
                            "orientation": "orthogonal",
                            "tileset_path": "assets/tiles/terrain.png",
                            "layers": [{"name": "Ground", "tiles": []}],
                        },
                    },
                }
            ],
            "rules": [],
            "feature_metadata": {},
        }
        path = self.project_root / "levels" / "tilemap_scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(scene, indent=2), encoding="utf-8")
        return path

    def test_tilemap_roundtrip_modify_save_and_reload(self) -> None:
        scene_path = self._write_scene()
        self.api.load_level(scene_path.as_posix())

        result = self.api.set_tilemap_tile(
            "Grid",
            "Ground",
            2,
            3,
            "grass",
            source="assets/tiles/terrain.png",
            flags=["solid"],
            tags=["ground"],
            custom={"biome": "plains"},
        )
        self.assertTrue(result["success"])
        save_result = self.api.save_scene(path=scene_path.as_posix())
        self.assertTrue(save_result["success"])

        reloaded = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_reload").as_posix())
        try:
            reloaded.load_level(scene_path.as_posix())
            tilemap = reloaded.get_tilemap("Grid")
            layers = {layer["name"]: layer for layer in tilemap.get("layers", [])}
            tile = layers["Ground"]["tiles"][0]
            self.assertEqual((tile["x"], tile["y"], tile["tile_id"]), (2, 3, "grass"))
            self.assertEqual(tile["flags"], ["solid"])
            self.assertEqual(tile["tags"], ["ground"])
            self.assertEqual(tile["custom"]["biome"], "plains")
            self.assertEqual(tilemap["tileset_path"], "assets/tiles/terrain.png")
        finally:
            reloaded.shutdown()


if __name__ == "__main__":
    unittest.main()
