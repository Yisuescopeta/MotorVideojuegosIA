import json
import tempfile
import unittest
from pathlib import Path

from engine.resources.tileset import (
    TileAtlasSource,
    TileMetadata,
    TilePhysicsShape,
    TileSet,
    TerrainSet,
    clear_tileset_cache,
    load_tileset,
)


class TileSetRoundtripTests(unittest.TestCase):
    def test_tileset_to_dict_and_from_dict_roundtrip(self) -> None:
        ts = TileSet(
            resource_id="test_tileset",
            resource_name="Test Tileset",
            schema_version=1,
            atlas=TileAtlasSource(
                texture_path="assets/tiles.png",
                tile_width=32,
                tile_height=32,
                columns=8,
                margin=1,
                spacing=2,
            ),
            tile_metadata={
                "grass_0_0": TileMetadata(
                    tile_id="grass_0_0",
                    physics_layers=[
                        TilePhysicsShape(
                            shape_type="box",
                            points=[[0.0, 0.0], [32.0, 32.0]],
                        )
                    ],
                    custom_data={"weight": 1},
                    terrain_id=0,
                ),
            },
            terrain_sets=[
                TerrainSet(name="grass", color="#00ff00", mode=0),
                TerrainSet(name="dirt", color="#8b4513", mode=0),
            ],
            terrain_peering={
                "grass": {
                    "grass_0_0": 0b00000000,
                    "grass_1_0": 0b00001111,
                    "grass_2_0": 0b11110000,
                    "grass_3_0": 0b11111111,
                },
            },
        )

        data = ts.to_dict()
        restored = TileSet.from_dict(data)

        self.assertEqual(restored.resource_id, "test_tileset")
        self.assertEqual(restored.atlas.texture_path, "assets/tiles.png")
        self.assertEqual(restored.atlas.tile_width, 32)
        self.assertEqual(restored.atlas.columns, 8)
        self.assertEqual(restored.atlas.margin, 1)
        self.assertEqual(restored.atlas.spacing, 2)
        self.assertEqual(len(restored.tile_metadata), 1)
        self.assertIn("grass_0_0", restored.tile_metadata)
        meta = restored.tile_metadata["grass_0_0"]
        self.assertEqual(meta.terrain_id, 0)
        self.assertEqual(len(meta.physics_layers), 1)
        self.assertEqual(meta.physics_layers[0].shape_type, "box")
        self.assertEqual(meta.physics_layers[0].points, [[0.0, 0.0], [32.0, 32.0]])
        self.assertEqual(meta.custom_data["weight"], 1)
        self.assertEqual(len(restored.terrain_sets), 2)
        self.assertEqual(restored.terrain_sets[0].name, "grass")
        self.assertEqual(restored.terrain_sets[0].color, "#00ff00")
        self.assertEqual(restored.terrain_sets[1].name, "dirt")
        self.assertEqual(len(restored.terrain_peering["grass"]), 4)
        self.assertEqual(restored.terrain_peering["grass"]["grass_0_0"], 0)
        self.assertEqual(restored.terrain_peering["grass"]["grass_3_0"], 0b11111111)


class TileAtlasSourceTests(unittest.TestCase):
    def test_get_tile_region_zero_columns_returns_default(self) -> None:
        atlas = TileAtlasSource(
            texture_path="test.png",
            tile_width=32,
            tile_height=32,
            columns=0,
        )
        sx, sy, sw, sh = atlas.get_tile_region(5)
        self.assertEqual((sx, sy, sw, sh), (0, 0, 32, 32))

    def test_get_tile_region_with_columns(self) -> None:
        atlas = TileAtlasSource(
            texture_path="test.png",
            tile_width=16,
            tile_height=16,
            columns=4,
            margin=1,
            spacing=2,
        )
        sx, sy, sw, sh = atlas.get_tile_region(0)
        self.assertEqual((sx, sy, sw, sh), (1, 1, 16, 16))

        sx, sy, sw, sh = atlas.get_tile_region(1)
        self.assertEqual(sx, 1 + 1 * (16 + 2))
        self.assertEqual(sy, 1)
        self.assertEqual(sw, 16)
        self.assertEqual(sh, 16)

        sx, sy, sw, sh = atlas.get_tile_region(4)
        self.assertEqual(sx, 1)
        self.assertEqual(sy, 1 + 1 * (16 + 2))
        self.assertEqual(sw, 16)
        self.assertEqual(sh, 16)

    def test_get_tile_region_last_column_wraps(self) -> None:
        atlas = TileAtlasSource(
            texture_path="test.png",
            tile_width=16,
            tile_height=16,
            columns=4,
            margin=0,
            spacing=0,
        )
        sx, sy, sw, sh = atlas.get_tile_region(7)
        self.assertEqual(sx, 3 * 16)
        self.assertEqual(sy, 1 * 16)
        self.assertEqual(sw, 16)
        self.assertEqual(sh, 16)


class TerrainPeeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tileset = TileSet(
            resource_id="terrain_test",
            terrain_sets=[TerrainSet(name="grass", color="#00ff00", mode=0)],
            terrain_peering={
                "grass": {
                    "tile_empty": 0b00000000,
                    "tile_full": 0b11111111,
                    "tile_horiz": 0b01000100,  # E + W
                    "tile_vert": 0b00010001,   # N + S
                    "tile_corner": 0b10000010,  # NW + NE
                },
            },
        )

    def test_get_tile_metadata_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.tileset.get_tile_metadata("missing"))
        self.assertIsNone(self.tileset.get_tile_metadata("", "missing"))

    def test_get_tile_metadata_returns_for_existing(self) -> None:
        ts = TileSet(
            tile_metadata={
                "dirt_0_0": TileMetadata(tile_id="dirt_0_0", terrain_id=1),
            }
        )
        meta = ts.get_tile_metadata("dirt", "0_0")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.terrain_id, 1)

        meta2 = ts.get_tile_metadata("dirt")
        self.assertIsNotNone(meta2)
        self.assertEqual(meta2.terrain_id, 1)

    def test_get_autotile_tile_exact_match(self) -> None:
        result = self.tileset.get_autotile_tile("grass", 0b11111111)
        self.assertEqual(result, "tile_full")

    def test_get_autotile_tile_exact_match_empty(self) -> None:
        result = self.tileset.get_autotile_tile("grass", 0b00000000)
        self.assertEqual(result, "tile_empty")

    def test_get_autotile_tile_fallback_weighted(self) -> None:
        result = self.tileset.get_autotile_tile("grass", 0b11111110)
        self.assertEqual(result, "tile_full")

    def test_get_autotile_tile_no_match_returns_none(self) -> None:
        empty = TileSet()
        result = empty.get_autotile_tile("grass", 0)
        self.assertIsNone(result)

    def test_get_autotile_tile_missing_terrain_returns_none(self) -> None:
        result = self.tileset.get_autotile_tile("water", 0)
        self.assertIsNone(result)

    def test_compute_terrain_mask_empty_layer(self) -> None:
        layer_tiles: dict[tuple[int, int], dict] = {}
        mask = self.tileset.compute_terrain_mask(layer_tiles, 0, 0, "grass")
        self.assertEqual(mask, 0)

    def test_compute_terrain_mask_neighbors_detected(self) -> None:
        layer_tiles: dict[tuple[int, int], dict] = {
            (0, -1): {"tile_id": "tile_full", "terrain_type": "grass"},
            (1, 0): {"tile_id": "tile_full", "terrain_type": "grass"},
        }
        mask = self.tileset.compute_terrain_mask(layer_tiles, 0, 0, "grass")
        self.assertTrue(mask & (1 << 0))
        self.assertTrue(mask & (1 << 2))
        self.assertFalse(mask & (1 << 4))

    def test_compute_terrain_mask_uses_terrain_type_fallback(self) -> None:
        ts = TileSet(
            terrain_sets=[TerrainSet(name="grass", color="#00ff00")],
        )
        layer_tiles: dict[tuple[int, int], dict] = {
            (0, -1): {"tile_id": "any_tile", "terrain_type": "grass"},
        }
        mask = ts.compute_terrain_mask(layer_tiles, 0, 0, "grass")
        self.assertTrue(mask & (1 << 0))

    def test_set_cells_terrain_connect_modifies_cells(self) -> None:
        tile_map: dict[tuple[int, int], dict[str, str]] = {
            (0, 0): {"tile_id": "tile_empty"},
            (0, -1): {"tile_id": "tile_full", "terrain_type": "grass"},
            (0, 1): {"tile_id": "tile_full", "terrain_type": "grass"},
        }

        def getter(x: int, y: int) -> dict | None:
            return tile_map.get((x, y))

        def setter(x: int, y: int, tid: str) -> None:
            tile_map[(x, y)] = {"tile_id": tid}

        count = self.tileset.set_cells_terrain_connect(
            cells=[{"x": 0, "y": 0}],
            terrain_name="grass",
            get_tile_at=getter,
            set_tile_at=setter,
        )
        self.assertEqual(count, 1)
        self.assertEqual(tile_map[(0, 0)]["tile_id"], "tile_vert")


class TileSetLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_tileset_cache()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)

    def tearDown(self) -> None:
        clear_tileset_cache()
        self._temp_dir.cleanup()

    def _write_tileset(self, data: dict) -> Path:
        path = self.root / "test_tileset.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_load_tileset_returns_none_for_empty_path(self) -> None:
        self.assertIsNone(load_tileset(""))
        self.assertIsNone(load_tileset("   "))

    def test_load_tileset_returns_none_for_nonexistent_file(self) -> None:
        self.assertIsNone(load_tileset("/nonexistent/path/tileset.json"))

    def test_load_tileset_loads_valid_json(self) -> None:
        data = {
            "resource_id": "test",
            "resource_name": "Test",
            "schema_version": 1,
            "atlas": {
                "texture_path": "assets/tiles.png",
                "tile_width": 32,
                "tile_height": 32,
                "columns": 8,
                "margin": 1,
                "spacing": 2,
            },
            "tile_metadata": {},
            "terrain_sets": [
                {"name": "grass", "color": "#00ff00", "mode": 0}
            ],
            "terrain_peering": {
                "grass": {"tile_0": 0, "tile_1": 255}
            },
        }
        path = self._write_tileset(data)
        ts = load_tileset(path.as_posix())
        self.assertIsNotNone(ts)
        self.assertEqual(ts.resource_id, "test")
        self.assertEqual(ts.atlas.columns, 8)
        self.assertEqual(len(ts.terrain_sets), 1)
        self.assertEqual(ts.terrain_peering["grass"]["tile_1"], 255)

    def test_load_tileset_uses_cache(self) -> None:
        data = {"resource_id": "cached", "atlas": {}, "tile_metadata": {}, "terrain_sets": [], "terrain_peering": {}}
        path = self._write_tileset(data)
        ts1 = load_tileset(path.as_posix())
        ts2 = load_tileset(path.as_posix())
        self.assertIs(ts1, ts2)

    def test_load_tileset_caches_none_on_failure(self) -> None:
        path = self._write_tileset({"not": "valid"})
        result = load_tileset(path.as_posix())
        self.assertIsNotNone(result)
        clear_tileset_cache()
        path_bad = self.root / "bad.json"
        path_bad.write_text("not json", encoding="utf-8")
        result = load_tileset(path_bad.as_posix())
        self.assertIsNone(result)
        result2 = load_tileset(path_bad.as_posix())
        self.assertIsNone(result2)

    def test_clear_tileset_cache(self) -> None:
        data = {"resource_id": "clear_test", "atlas": {}, "tile_metadata": {}, "terrain_sets": [], "terrain_peering": {}}
        path = self._write_tileset(data)
        load_tileset(path.as_posix())
        clear_tileset_cache()
        from engine.resources.tileset import _tileset_cache
        self.assertEqual(len(_tileset_cache), 0)


class TileSetEmptyStatesTests(unittest.TestCase):
    def test_empty_tileset_to_dict_from_dict(self) -> None:
        ts = TileSet()
        data = ts.to_dict()
        restored = TileSet.from_dict(data)
        self.assertEqual(restored.resource_id, "")
        self.assertEqual(restored.atlas.texture_path, "")
        self.assertEqual(restored.tile_metadata, {})
        self.assertEqual(restored.terrain_sets, [])
        self.assertEqual(restored.terrain_peering, {})

    def test_get_tile_metadata_empty(self) -> None:
        ts = TileSet()
        self.assertIsNone(ts.get_tile_metadata("any"))

    def test_get_autotile_tile_empty_peering(self) -> None:
        ts = TileSet(terrain_peering={"grass": {}})
        self.assertIsNone(ts.get_autotile_tile("grass", 255))


class TerrainSetModeTests(unittest.TestCase):
    def test_terrain_set_default_mode(self) -> None:
        ts = TerrainSet(name="test")
        self.assertEqual(ts.mode, 0)

    def test_terrain_set_invalid_mode_clamped(self) -> None:
        data = {"name": "test", "color": "#fff", "mode": 99}
        ts = TerrainSet.from_dict(data)
        self.assertEqual(ts.mode, 0)

    def test_terrain_set_valid_modes(self) -> None:
        for mode in (0, 1, 2):
            data = {"name": "test", "mode": mode}
            ts = TerrainSet.from_dict(data)
            self.assertEqual(ts.mode, mode)


if __name__ == "__main__":
    unittest.main()
