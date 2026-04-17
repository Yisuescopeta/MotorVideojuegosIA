import unittest

from engine.tilemap.model import TileCoord, TilemapData


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


if __name__ == "__main__":
    unittest.main()
