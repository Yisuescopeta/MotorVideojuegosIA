import unittest

from engine.tilemap.model import TileCoord, TileData, TilemapData


class TilemapFoundationTests(unittest.TestCase):
    def test_tilemap_data_roundtrip_preserves_layer_order_and_canonical_tiles(self) -> None:
        payload = {
            "cell_width": 16,
            "cell_height": 16,
            "tileset_path": "assets/tiles.png",
            "default_layer_name": "Ground",
            "layers": [
                {
                    "name": "Ground",
                    "tiles": {
                        "2,1": {"tile_id": "b"},
                        "0,0": {"tile_id": "a"},
                    },
                },
                {
                    "name": "Decor",
                    "tiles": [
                        {"x": 4, "y": 3, "tile_id": "flower"},
                    ],
                },
            ],
        }

        model = TilemapData.from_payload(payload)

        self.assertEqual([layer.name for layer in model.layers], ["Ground", "Decor"])
        self.assertEqual(model.layers[0].get_tile(TileCoord(0, 0)).tile_id, "a")
        self.assertEqual(model.layers[0].get_tile(TileCoord(2, 1)).tile_id, "b")

        serialized = model.to_component_payload(enabled=True)
        self.assertEqual([layer["name"] for layer in serialized["layers"]], ["Ground", "Decor"])
        self.assertEqual(
            [(tile["x"], tile["y"], tile["tile_id"]) for tile in serialized["layers"][0]["tiles"]],
            [(0, 0, "a"), (2, 1, "b")],
        )

    def test_tilemap_data_accepts_legacy_list_and_dict_tile_shapes(self) -> None:
        payload = {
            "tileset": {"path": "assets/tiles.png"},
            "layers": [
                {
                    "name": "Ground",
                    "tiles": [
                        {"x": 1, "y": 2, "tile_id": "grass"},
                    ],
                },
                {
                    "name": "Decor",
                    "tiles": {
                        "3,4": {"tile_id": "flower"},
                    },
                },
            ],
        }

        model = TilemapData.from_payload(payload)

        self.assertEqual(model.layers[0].get_tile(TileCoord(1, 2)).tile_id, "grass")
        self.assertEqual(model.layers[1].get_tile(TileCoord(3, 4)).tile_id, "flower")

        serialized = model.to_component_payload(enabled=True)
        self.assertEqual(serialized["layers"][0]["tiles"][0]["tile_id"], "grass")
        self.assertEqual(serialized["layers"][1]["tiles"][0]["tile_id"], "flower")

    def test_tilemap_data_normalizes_tileset_reference_consistency(self) -> None:
        payload = {
            "tileset": {"guid": "abc", "path": "assets/old.png"},
            "tileset_path": "assets/new.png",
            "layers": [],
        }

        model = TilemapData.from_payload(payload)

        self.assertEqual(model.tileset["guid"], "abc")
        self.assertEqual(model.tileset["path"], "assets/new.png")
        self.assertEqual(model.tileset_path, "assets/new.png")


    def test_tile_custom_data_layers(self) -> None:
        tile = TileData(
            tile_id="water",
            physics_layer=1,
            navigation_layer=2,
            custom_data={"flow_speed": 5, "depth": 3},
        )
        self.assertEqual(tile.physics_layer, 1)
        self.assertEqual(tile.navigation_layer, 2)
        self.assertEqual(tile.custom_data, {"flow_speed": 5, "depth": 3})

    def test_tile_custom_data_roundtrip(self) -> None:
        payload = {
            "tile_id": "lava",
            "physics_layer": 3,
            "navigation_layer": 0,
            "custom_data": {"damage": 10, "heat": 100},
        }
        tile = TileData.from_payload(payload)
        self.assertEqual(tile.physics_layer, 3)
        self.assertEqual(tile.navigation_layer, 0)
        self.assertEqual(tile.custom_data, {"damage": 10, "heat": 100})

        runtime = tile.to_runtime_dict()
        self.assertEqual(runtime["physics_layer"], 3)
        self.assertEqual(runtime["navigation_layer"], 0)
        self.assertEqual(runtime["custom_data"], {"damage": 10, "heat": 100})

        roundtrip = TileData.from_payload(runtime)
        self.assertEqual(roundtrip.physics_layer, 3)
        self.assertEqual(roundtrip.navigation_layer, 0)
        self.assertEqual(roundtrip.custom_data, {"damage": 10, "heat": 100})

    def test_tilemap_set_tile_with_custom_data_layers(self) -> None:
        model = TilemapData.from_payload(
            {
                "cell_width": 16,
                "cell_height": 16,
                "layers": [{"name": "Ground", "tiles": []}],
            }
        )
        model.set_tile(
            "Ground", 0, 0, "ice",
            physics_layer=2,
            navigation_layer=1,
            custom_data={"slipperiness": 0.8},
        )
        tile = model.layers[0].get_tile(TileCoord(0, 0))
        self.assertIsNotNone(tile)
        self.assertEqual(tile.physics_layer, 2)
        self.assertEqual(tile.navigation_layer, 1)
        self.assertEqual(tile.custom_data, {"slipperiness": 0.8})


if __name__ == "__main__":
    unittest.main()
