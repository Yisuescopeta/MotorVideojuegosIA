import json
import tempfile
import unittest
from pathlib import Path

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

    def test_tilemap_new_tile_fields_roundtrip(self) -> None:
        scene_path = self._write_scene()
        self.api.load_level(scene_path.as_posix())

        result = self.api.set_tilemap_tile_full(
            "Grid",
            "Ground",
            5,
            7,
            "animated_grass",
            source="assets/tiles/terrain.png",
            flags=["solid", "walkable"],
            tags=["vegetation", "ground"],
            custom={"growth_stage": 2},
            animated=True,
            animation_id="grass_sway",
            terrain_type="grassland",
        )
        self.assertTrue(result["success"])
        save_result = self.api.save_scene(path=scene_path.as_posix())
        self.assertTrue(save_result["success"])

        reloaded = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_reload2").as_posix())
        try:
            reloaded.load_level(scene_path.as_posix())
            tilemap = reloaded.get_tilemap("Grid")
            layers = {layer["name"]: layer for layer in tilemap.get("layers", [])}
            tile = layers["Ground"]["tiles"][0]
            self.assertEqual(tile["tile_id"], "animated_grass")
            self.assertEqual(tile["animated"], True)
            self.assertEqual(tile["animation_id"], "grass_sway")
            self.assertEqual(tile["terrain_type"], "grassland")
            self.assertEqual(tile["flags"], ["solid", "walkable"])
            self.assertEqual(tile["tags"], ["vegetation", "ground"])
            self.assertEqual(tile["custom"]["growth_stage"], 2)
        finally:
            reloaded.shutdown()

    def test_tilemap_layer_crud_operations(self) -> None:
        scene_path = self._write_scene()
        self.api.load_level(scene_path.as_posix())

        create_result = self.api.create_tilemap_layer(
            "Grid",
            "Walls",
            visible=True,
            opacity=0.8,
            locked=False,
            offset_x=0.0,
            offset_y=0.0,
            collision_layer=1,
        )
        self.assertTrue(create_result["success"])

        get_result = self.api.get_tilemap_layer("Grid", "Walls")
        self.assertEqual(get_result["name"], "Walls")
        self.assertEqual(get_result["visible"], True)
        self.assertEqual(get_result["opacity"], 0.8)
        self.assertEqual(get_result["locked"], False)
        self.assertEqual(get_result["collision_layer"], 1)

        update_result = self.api.update_tilemap_layer(
            "Grid",
            "Walls",
            visible=False,
            locked=True,
            collision_layer=2,
            metadata={"purpose": "collision"},
        )
        self.assertTrue(update_result["success"])

        get_after = self.api.get_tilemap_layer("Grid", "Walls")
        self.assertEqual(get_after["visible"], False)
        self.assertEqual(get_after["locked"], True)
        self.assertEqual(get_after["collision_layer"], 2)
        self.assertEqual(get_after["metadata"]["purpose"], "collision")

        delete_result = self.api.delete_tilemap_layer("Grid", "Walls")
        self.assertTrue(delete_result["success"])

        get_deleted = self.api.get_tilemap_layer("Grid", "Walls")
        self.assertEqual(get_deleted, {})

    def test_tilemap_bulk_set_tiles(self) -> None:
        scene_path = self._write_scene()
        self.api.load_level(scene_path.as_posix())

        tiles = [
            {"x": 0, "y": 0, "tile_id": "grass", "animated": False, "terrain_type": "grassland"},
            {"x": 1, "y": 0, "tile_id": "grass", "animated": False, "terrain_type": "grassland"},
            {"x": 2, "y": 0, "tile_id": "water", "animated": True, "animation_id": "water_shimmer", "terrain_type": "water"},
            {"x": 0, "y": 1, "tile_id": "grass", "animated": False, "terrain_type": "grassland"},
            {"x": 1, "y": 1, "tile_id": "sand", "flags": ["walkable"], "terrain_type": "beach"},
        ]
        bulk_result = self.api.bulk_set_tilemap_tiles("Grid", "Ground", tiles)
        self.assertTrue(bulk_result["success"])
        self.assertEqual(bulk_result["data"]["count"], 5)

        save_result = self.api.save_scene(path=scene_path.as_posix())
        self.assertTrue(save_result["success"])

        reloaded = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_reload3").as_posix())
        try:
            reloaded.load_level(scene_path.as_posix())
            tilemap = reloaded.get_tilemap("Grid")
            ground_layer = next((l for l in tilemap["layers"] if l["name"] == "Ground"), None)
            self.assertIsNotNone(ground_layer)
            tile_map = {(t["x"], t["y"]): t for t in ground_layer["tiles"]}
            self.assertEqual(tile_map[(0, 0)]["tile_id"], "grass")
            self.assertEqual(tile_map[(2, 0)]["animated"], True)
            self.assertEqual(tile_map[(2, 0)]["animation_id"], "water_shimmer")
            self.assertEqual(tile_map[(1, 1)]["terrain_type"], "beach")
            self.assertEqual(tile_map[(1, 1)]["flags"], ["walkable"])
        finally:
            reloaded.shutdown()

    def test_tilemap_resize(self) -> None:
        scene_path = self._write_scene()
        self.api.load_level(scene_path.as_posix())

        resize_result = self.api.resize_tilemap("Grid", cell_width=32, cell_height=32, offset_x=0, offset_y=0)
        self.assertTrue(resize_result["success"])

        save_result = self.api.save_scene(path=scene_path.as_posix())
        self.assertTrue(save_result["success"])

        reloaded = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_reload4").as_posix())
        try:
            reloaded.load_level(scene_path.as_posix())
            tilemap = reloaded.get_tilemap("Grid")
            self.assertEqual(tilemap["cell_width"], 32)
            self.assertEqual(tilemap["cell_height"], 32)
            self.assertEqual(tilemap["metadata"]["grid_offset_x"], 0)
            self.assertEqual(tilemap["metadata"]["grid_offset_y"], 0)
        finally:
            reloaded.shutdown()

    def test_tilemap_full_model_roundtrip_with_all_fields(self) -> None:
        scene = {
            "name": "FullTilemapScene",
            "entities": [
                {
                    "name": "Map",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Tilemap": {
                            "enabled": True,
                            "cell_width": 16,
                            "cell_height": 16,
                            "orientation": "orthogonal",
                            "tileset": {"guid": "", "path": "assets/tileset.png"},
                            "tileset_path": "assets/tileset.png",
                            "metadata": {"author": "test", "version": 1},
                            "tileset_tile_width": 32,
                            "tileset_tile_height": 32,
                            "tileset_columns": 8,
                            "tileset_spacing": 2,
                            "tileset_margin": 1,
                            "default_layer_name": "Ground",
                            "layers": [
                                {
                                    "name": "Ground",
                                    "visible": True,
                                    "opacity": 1.0,
                                    "locked": False,
                                    "offset_x": 0.0,
                                    "offset_y": 0.0,
                                    "collision_layer": 0,
                                    "tilemap_source": {},
                                    "metadata": {"layer_type": "terrain"},
                                    "tiles": [
                                        {
                                            "x": 0,
                                            "y": 0,
                                            "tile_id": "grass",
                                            "source": {"guid": "", "path": "assets/tileset.png"},
                                            "flags": ["solid"],
                                            "tags": ["ground"],
                                            "custom": {"biome": "forest"},
                                            "animated": False,
                                            "animation_id": "",
                                            "terrain_type": "grass",
                                        }
                                    ],
                                },
                                {
                                    "name": "Walls",
                                    "visible": False,
                                    "opacity": 0.5,
                                    "locked": True,
                                    "offset_x": 10.0,
                                    "offset_y": 20.0,
                                    "collision_layer": 1,
                                    "tilemap_source": {"guid": "", "path": "assets/walls.png"},
                                    "metadata": {},
                                    "tiles": [
                                        {
                                            "x": 5,
                                            "y": 5,
                                            "tile_id": "brick",
                                            "source": {"guid": "", "path": "assets/walls.png"},
                                            "flags": ["solid", "climbable"],
                                            "tags": ["structure"],
                                            "custom": {},
                                            "animated": True,
                                            "animation_id": "brick_shake",
                                            "terrain_type": "",
                                        }
                                    ],
                                },
                            ],
                        },
                    },
                }
            ],
            "rules": [],
            "feature_metadata": {},
        }
        path = self.project_root / "levels" / "full_tilemap_scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(scene, indent=2), encoding="utf-8")

        self.api.load_level(path.as_posix())

        tilemap = self.api.get_tilemap("Map")
        self.assertEqual(tilemap["cell_width"], 16)
        self.assertEqual(tilemap["cell_height"], 16)
        self.assertEqual(tilemap["metadata"]["author"], "test")
        self.assertEqual(tilemap["tileset_tile_width"], 32)
        self.assertEqual(tilemap["tileset_columns"], 8)
        self.assertEqual(tilemap["default_layer_name"], "Ground")

        layers = {l["name"]: l for l in tilemap["layers"]}
        self.assertEqual(layers["Ground"]["locked"], False)
        self.assertEqual(layers["Ground"]["offset_x"], 0.0)
        self.assertEqual(layers["Ground"]["collision_layer"], 0)
        self.assertEqual(layers["Walls"]["visible"], False)
        self.assertEqual(layers["Walls"]["locked"], True)
        self.assertEqual(layers["Walls"]["offset_x"], 10.0)
        self.assertEqual(layers["Walls"]["collision_layer"], 1)

        ground_tile = layers["Ground"]["tiles"][0]
        self.assertEqual(ground_tile["animated"], False)
        self.assertEqual(ground_tile["terrain_type"], "grass")

        wall_tile = layers["Walls"]["tiles"][0]
        self.assertEqual(wall_tile["animated"], True)
        self.assertEqual(wall_tile["animation_id"], "brick_shake")
        self.assertEqual(wall_tile["flags"], ["solid", "climbable"])

        save_result = self.api.save_scene(path=path.as_posix())
        self.assertTrue(save_result["success"])

        reloaded = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_reload5").as_posix())
        try:
            reloaded.load_level(path.as_posix())
            tilemap_reloaded = reloaded.get_tilemap("Map")
            self.assertEqual(tilemap_reloaded["tileset_tile_width"], 32)
            self.assertEqual(tilemap_reloaded["default_layer_name"], "Ground")
            layers_reloaded = {l["name"]: l for l in tilemap_reloaded["layers"]}
            self.assertEqual(layers_reloaded["Walls"]["locked"], True)
            self.assertEqual(layers_reloaded["Walls"]["offset_x"], 10.0)
            self.assertEqual(layers_reloaded["Walls"]["collision_layer"], 1)
            wall_tile_reloaded = layers_reloaded["Walls"]["tiles"][0]
            self.assertEqual(wall_tile_reloaded["animated"], True)
            self.assertEqual(wall_tile_reloaded["animation_id"], "brick_shake")
        finally:
            reloaded.shutdown()


class TilemapComponentTests(unittest.TestCase):
    def test_tilemap_fill_rect(self) -> None:
        from engine.components.tilemap import Tilemap

        tilemap = Tilemap(
            cell_width=16,
            cell_height=16,
            layers=[{"name": "Ground", "tiles": []}],
        )

        count = tilemap.fill_rect(
            "Ground",
            0, 0, 4, 4,
            "grass",
            flags=["solid"],
            terrain_type="grassland",
        )
        self.assertEqual(count, 25)

        for y in range(5):
            for x in range(5):
                tile = tilemap.get_tile("Ground", x, y)
                self.assertIsNotNone(tile)
                self.assertEqual(tile["tile_id"], "grass")
                self.assertEqual(tile["flags"], ["solid"])
                self.assertEqual(tile["terrain_type"], "grassland")

        empty = tilemap.get_tile("Ground", 5, 5)
        self.assertIsNone(empty)

    def test_tilemap_layer_properties_update(self) -> None:
        from engine.components.tilemap import Tilemap

        tilemap = Tilemap(layers=[{"name": "Layer1", "tiles": []}])

        result = tilemap.set_layer_properties(
            "Layer1",
            visible=False,
            opacity=0.5,
            locked=True,
            offset_x=10.0,
            offset_y=20.0,
            collision_layer=3,
            metadata={"key": "value"},
        )
        self.assertTrue(result)

        layer = tilemap.get_layer("Layer1")
        self.assertIsNotNone(layer)
        self.assertEqual(layer["visible"], False)
        self.assertEqual(layer["opacity"], 0.5)
        self.assertEqual(layer["locked"], True)
        self.assertEqual(layer["offset_x"], 10.0)
        self.assertEqual(layer["offset_y"], 20.0)
        self.assertEqual(layer["collision_layer"], 3)
        self.assertEqual(layer["metadata"]["key"], "value")

    def test_tilemap_remove_layer(self) -> None:
        from engine.components.tilemap import Tilemap

        tilemap = Tilemap(layers=[{"name": "Layer1", "tiles": []}, {"name": "Layer2", "tiles": []}])

        result = tilemap.remove_layer("Layer1")
        self.assertTrue(result)
        self.assertEqual(len(tilemap.layers), 1)
        self.assertEqual(tilemap.layers[0]["name"], "Layer2")

        result = tilemap.remove_layer("Nonexistent")
        self.assertFalse(result)

    def test_tilemap_resize_updates_dimensions(self) -> None:
        from engine.components.tilemap import Tilemap

        tilemap = Tilemap(cell_width=16, cell_height=16)
        self.assertEqual(tilemap.cell_width, 16)
        self.assertEqual(tilemap.cell_height, 16)

        tilemap.resize(32, 64, offset_x=5, offset_y=10)
        self.assertEqual(tilemap.cell_width, 32)
        self.assertEqual(tilemap.cell_height, 64)
        self.assertEqual(tilemap.metadata["grid_offset_x"], 5)
        self.assertEqual(tilemap.metadata["grid_offset_y"], 10)

    def test_tilemap_set_tile_full_accepts_new_fields(self) -> None:
        from engine.components.tilemap import Tilemap

        tilemap = Tilemap(layers=[{"name": "Ground", "tiles": []}])

        tilemap.set_tile_full(
            "Ground",
            1, 2, "animated_tile",
            animated=True,
            animation_id="test_anim",
            terrain_type="water",
            flags=["solid"],
        )

        tile = tilemap.get_tile("Ground", 1, 2)
        self.assertIsNotNone(tile)
        self.assertEqual(tile["tile_id"], "animated_tile")
        self.assertEqual(tile["animated"], True)
        self.assertEqual(tile["animation_id"], "test_anim")
        self.assertEqual(tile["terrain_type"], "water")
        self.assertEqual(tile["flags"], ["solid"])

    def test_tilemap_from_dict_preserves_all_new_fields(self) -> None:
        from engine.components.tilemap import Tilemap

        data = {
            "enabled": True,
            "cell_width": 16,
            "cell_height": 16,
            "orientation": "orthogonal",
            "tileset": {"guid": "", "path": "assets/tiles.png"},
            "tileset_path": "assets/tiles.png",
            "metadata": {"author": "tester"},
            "tileset_tile_width": 32,
            "tileset_tile_height": 32,
            "tileset_columns": 8,
            "tileset_spacing": 2,
            "tileset_margin": 1,
            "default_layer_name": "CustomLayer",
            "layers": [
                {
                    "name": "CustomLayer",
                    "visible": True,
                    "opacity": 0.9,
                    "locked": True,
                    "offset_x": 5.0,
                    "offset_y": 10.0,
                    "collision_layer": 2,
                    "tilemap_source": {"guid": "", "path": "assets/layer_tiles.png"},
                    "metadata": {"layer_note": "test"},
                    "tiles": [
                        {
                            "x": 0, "y": 0,
                            "tile_id": "special",
                            "source": {},
                            "flags": [],
                            "tags": [],
                            "custom": {},
                            "animated": True,
                            "animation_id": "pulse",
                            "terrain_type": "special",
                        }
                    ],
                }
            ],
        }

        tilemap = Tilemap.from_dict(data)
        self.assertEqual(tilemap.metadata["author"], "tester")
        self.assertEqual(tilemap.tileset_tile_width, 32)
        self.assertEqual(tilemap.tileset_columns, 8)
        self.assertEqual(tilemap.default_layer_name, "CustomLayer")

        layer = tilemap.get_layer("CustomLayer")
        self.assertIsNotNone(layer)
        self.assertEqual(layer["locked"], True)
        self.assertEqual(layer["offset_x"], 5.0)
        self.assertEqual(layer["collision_layer"], 2)

        tile = tilemap.get_tile("CustomLayer", 0, 0)
        self.assertIsNotNone(tile)
        self.assertEqual(tile["animated"], True)
        self.assertEqual(tile["animation_id"], "pulse")
        self.assertEqual(tile["terrain_type"], "special")

    def test_tilemap_to_dict_contains_all_new_fields(self) -> None:
        from engine.components.tilemap import Tilemap

        tilemap = Tilemap(
            cell_width=16,
            cell_height=16,
            metadata={"version": 2},
            tileset_tile_width=32,
            tileset_tile_height=32,
            tileset_columns=8,
            tileset_spacing=2,
            tileset_margin=1,
            default_layer_name="MyLayer",
            layers=[
                {
                    "name": "MyLayer",
                    "visible": True,
                    "opacity": 1.0,
                    "locked": True,
                    "offset_x": 3.0,
                    "offset_y": 4.0,
                    "collision_layer": 1,
                    "tilemap_source": {"guid": "", "path": "assets/layer.png"},
                    "metadata": {"note": "test"},
                    "tiles": [
                        {
                            "x": 0, "y": 0,
                            "tile_id": "test",
                            "source": {},
                            "flags": ["solid"],
                            "tags": ["test"],
                            "custom": {},
                            "animated": False,
                            "animation_id": "",
                            "terrain_type": "test_terrain",
                        }
                    ],
                }
            ],
        )

        result = tilemap.to_dict()
        self.assertEqual(result["metadata"]["version"], 2)
        self.assertEqual(result["tileset_tile_width"], 32)
        self.assertEqual(result["tileset_columns"], 8)
        self.assertEqual(result["default_layer_name"], "MyLayer")

        layer = result["layers"][0]
        self.assertEqual(layer["locked"], True)
        self.assertEqual(layer["offset_x"], 3.0)
        self.assertEqual(layer["collision_layer"], 1)

        tile = layer["tiles"][0]
        self.assertEqual(tile["animated"], False)
        self.assertEqual(tile["terrain_type"], "test_terrain")

    def test_tilemap_legacy_data_backward_compatible(self) -> None:
        from engine.components.tilemap import Tilemap

        legacy_data = {
            "cell_width": 16,
            "cell_height": 16,
            "orientation": "orthogonal",
            "tileset_path": "assets/legacy.png",
            "layers": [
                {"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "dirt"}]}
            ],
        }

        tilemap = Tilemap.from_dict(legacy_data)
        self.assertEqual(tilemap.cell_width, 16)
        self.assertEqual(tilemap.tileset_tile_width, 16)
        self.assertEqual(tilemap.default_layer_name, "Layer")
        self.assertEqual(tilemap.metadata, {})

        layer = tilemap.get_layer("Ground")
        self.assertIsNotNone(layer)
        self.assertEqual(layer["locked"], False)
        self.assertEqual(layer["offset_x"], 0.0)
        self.assertEqual(layer["collision_layer"], 0)

        tile = tilemap.get_tile("Ground", 0, 0)
        self.assertIsNotNone(tile)
        self.assertEqual(tile["animated"], False)
        self.assertEqual(tile["animation_id"], "")
        self.assertEqual(tile["terrain_type"], "")


if __name__ == "__main__":
    unittest.main()
