import unittest

from engine.components.tilemap import Tilemap
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

    def test_tilemap_to_dict_resyncs_from_external_surface_mutations(self) -> None:
        tilemap = Tilemap(
            cell_width=16,
            cell_height=16,
            layers=[{"name": "Ground", "tiles": []}],
        )

        tilemap.metadata["theme"] = "cave"
        tilemap.layers[0]["metadata"] = {"purpose": "terrain"}
        tilemap.layers[0]["tiles"] = {
            "3,4": {
                "tile_id": "wall",
                "flags": ["solid"],
            }
        }

        payload = tilemap.to_dict()

        self.assertEqual(payload["metadata"]["theme"], "cave")
        self.assertEqual(payload["layers"][0]["metadata"]["purpose"], "terrain")
        self.assertEqual(payload["layers"][0]["tiles"][0]["x"], 3)
        self.assertEqual(payload["layers"][0]["tiles"][0]["y"], 4)
        self.assertEqual(payload["layers"][0]["tiles"][0]["tile_id"], "wall")
        self.assertEqual(payload["layers"][0]["tiles"][0]["flags"], ["solid"])

    def test_tilemap_followup_operations_preserve_external_layer_changes(self) -> None:
        tilemap = Tilemap(
            default_layer_name="Ground",
            layers=[{"name": "Ground", "tiles": []}],
        )

        tilemap.layers[0]["metadata"] = {"purpose": "terrain"}
        tilemap.set_tile("Ground", 1, 2, "grass", custom={"biome": "forest"})

        layer = tilemap.get_layer("Ground")
        tile = tilemap.get_tile("Ground", 1, 2)

        self.assertEqual(layer["metadata"]["purpose"], "terrain")
        self.assertEqual(tile["tile_id"], "grass")
        self.assertEqual(tile["custom"]["biome"], "forest")


if __name__ == "__main__":
    unittest.main()
