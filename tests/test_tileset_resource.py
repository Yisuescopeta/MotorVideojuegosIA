"""
tests/test_tileset_resource.py — Tests para TileSetResource y sus dataclasses asociadas.
"""

import unittest

from engine.resources.tileset_resource import (
    CustomDataLayerDef,
    TileAnimationFrame,
    TileSetAtlasSource,
    TileSetResource,
)


class TestTileSetResource(unittest.TestCase):
    """Tests del recurso TileSetResource y sus dataclasses auxiliares."""

    # ── 1. test_create_empty_tileset ───────────────────────────────────

    def test_create_empty_tileset(self) -> None:
        """Verifica creación de tileset vacío con valores por defecto."""
        tileset = TileSetResource()
        self.assertEqual(tileset.resource_id, "")
        self.assertEqual(tileset.resource_name, "New TileSet")
        self.assertEqual(tileset.tile_width, 16)
        self.assertEqual(tileset.tile_height, 16)
        self.assertEqual(tileset.texture_ref, {})
        self.assertEqual(tileset.columns, 0)
        self.assertEqual(tileset.margin, 0)
        self.assertEqual(tileset.spacing, 0)
        self.assertEqual(tileset.sources, [])
        self.assertEqual(tileset.tile_animations, {})
        self.assertEqual(tileset.custom_data_layers, [])
        self.assertEqual(tileset.total_tile_count(), 0)

    # ── 2. test_tileset_serialization_roundtrip ────────────────────────

    def test_tileset_serialization_roundtrip(self) -> None:
        """Verifica roundtrip to_dict/from_dict con datos completos."""
        source = TileSetAtlasSource(
            source_id="atlas_01",
            texture_region_x=0,
            texture_region_y=0,
            texture_region_w=64,
            texture_region_h=64,
            tile_width=16,
            tile_height=16,
            columns=4,
            margin=2,
            spacing=1,
        )
        layer = CustomDataLayerDef(name="collision", layer_type="bool", default_value=False)
        frame = TileAnimationFrame(tile_id="atlas_01_0_0", duration=0.2)

        original = TileSetResource(
            resource_id="ts_test_001",
            resource_name="Test TileSet",
            tile_width=32,
            tile_height=32,
            texture_ref={"path": "assets/tiles.png"},
            columns=8,
            margin=1,
            spacing=2,
            sources=[source],
            tile_animations={"atlas_01_0_0": [frame]},
            custom_data_layers=[layer],
        )

        data = original.to_dict()
        restored = TileSetResource.from_dict(data)

        self.assertEqual(restored.resource_id, "ts_test_001")
        self.assertEqual(restored.resource_name, "Test TileSet")
        self.assertEqual(restored.tile_width, 32)
        self.assertEqual(restored.tile_height, 32)
        self.assertEqual(restored.texture_ref, {"path": "assets/tiles.png"})
        self.assertEqual(restored.columns, 8)
        self.assertEqual(restored.margin, 1)
        self.assertEqual(restored.spacing, 2)
        self.assertEqual(len(restored.sources), 1)
        self.assertEqual(len(restored.custom_data_layers), 1)
        self.assertIn("atlas_01_0_0", restored.tile_animations)
        self.assertEqual(len(restored.tile_animations["atlas_01_0_0"]), 1)
        self.assertEqual(restored.tile_animations["atlas_01_0_0"][0].duration, 0.2)

    # ── 3. test_add_atlas_source ───────────────────────────────────────

    def test_add_atlas_source(self) -> None:
        """Verifica add_source añade fuente y total_tile_count refleja cambio."""
        tileset = TileSetResource()
        source = TileSetAtlasSource(
            source_id="src1",
            texture_region_w=32,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source)
        self.assertEqual(len(tileset.sources), 1)
        self.assertEqual(tileset.total_tile_count(), 4)  # 2x2 grid

        source2 = TileSetAtlasSource(
            source_id="src2",
            texture_region_w=48,
            texture_region_h=16,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source2)
        self.assertEqual(len(tileset.sources), 2)
        self.assertEqual(tileset.total_tile_count(), 7)  # 4 + 3

    # ── 4. test_atlas_source_coordinates ────────────────────────────────

    def test_atlas_source_coordinates(self) -> None:
        """Verifica tile_id_at y tile_coords_from_id ida y vuelta."""
        source = TileSetAtlasSource(
            source_id="atlas_main",
            texture_region_w=48,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )

        tid = source.tile_id_at(2, 1)
        self.assertEqual(tid, "atlas_main_2_1")

        coords = source.tile_coords_from_id(tid)
        self.assertEqual(coords, (2, 1))

        # Coordenadas inválidas
        self.assertEqual(source.tile_coords_from_id("other_2_1"), (-1, -1))
        self.assertEqual(source.tile_coords_from_id("bad_format"), (-1, -1))

    # ── 5. test_alternative_tiles ───────────────────────────────────────

    def test_alternative_tiles(self) -> None:
        """Verifica add/remove/get_alternative y serialización de alternative_tiles."""
        source = TileSetAtlasSource(
            source_id="atlas_alt",
            texture_region_w=32,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )

        source.add_alternative(0, 0, "alt_001")
        source.add_alternative(0, 0, "alt_002")
        source.add_alternative(1, 0, "alt_010")

        alts = source.get_alternatives(0, 0)
        self.assertEqual(len(alts), 2)
        self.assertIn("alt_001", alts)
        self.assertIn("alt_002", alts)

        source.remove_alternative(0, 0, "alt_001")
        self.assertEqual(len(source.get_alternatives(0, 0)), 1)
        self.assertEqual(source.get_alternatives(0, 0), ["alt_002"])

        # Serialización de alternative_tiles
        data = source.to_dict()
        self.assertIn("alternative_tiles", data)
        self.assertEqual(data["alternative_tiles"]["0,0"], ["alt_002"])

        restored = TileSetAtlasSource.from_dict(data)
        self.assertEqual(restored.get_alternatives(0, 0), ["alt_002"])

    # ── 6. test_tile_animation_frames ───────────────────────────────────

    def test_tile_animation_frames(self) -> None:
        """Verifica creación y serialización de TileAnimationFrame."""
        frame = TileAnimationFrame(tile_id="tile_a", duration=0.5)
        self.assertEqual(frame.tile_id, "tile_a")
        self.assertEqual(frame.duration, 0.5)

        data = frame.to_dict()
        self.assertEqual(data["tile_id"], "tile_a")
        self.assertEqual(data["duration"], 0.5)

        restored = TileAnimationFrame.from_dict(data)
        self.assertEqual(restored.tile_id, "tile_a")
        self.assertEqual(restored.duration, 0.5)

        # Defaults
        default_frame = TileAnimationFrame()
        self.assertEqual(default_frame.tile_id, "")
        self.assertEqual(default_frame.duration, 0.1)

        # from_dict con dict vacío
        empty_frame = TileAnimationFrame.from_dict({})
        self.assertEqual(empty_frame.tile_id, "")
        self.assertEqual(empty_frame.duration, 0.1)

    # ── 7. test_custom_data_layer_def ──────────────────────────────────

    def test_custom_data_layer_def(self) -> None:
        """Verifica creación y serialización de CustomDataLayerDef."""
        layer = CustomDataLayerDef(name="physics", layer_type="int", default_value=1)
        self.assertEqual(layer.name, "physics")
        self.assertEqual(layer.layer_type, "int")
        self.assertEqual(layer.default_value, 1)

        data = layer.to_dict()
        self.assertEqual(data["name"], "physics")
        self.assertEqual(data["layer_type"], "int")
        self.assertEqual(data["default_value"], 1)

        restored = CustomDataLayerDef.from_dict(data)
        self.assertEqual(restored.name, "physics")
        self.assertEqual(restored.layer_type, "int")
        self.assertEqual(restored.default_value, 1)

        # Tipos variados
        str_layer = CustomDataLayerDef(name="terrain", layer_type="string", default_value="grass")
        self.assertEqual(str_layer.default_value, "grass")

        bool_layer = CustomDataLayerDef(name="walkable", layer_type="bool", default_value=True)
        self.assertTrue(bool_layer.default_value)

        float_layer = CustomDataLayerDef(name="speed", layer_type="float", default_value=1.5)
        self.assertAlmostEqual(float_layer.default_value, 1.5)

    # ── 8. test_tileset_with_multiple_sources ──────────────────────────

    def test_tileset_with_multiple_sources(self) -> None:
        """Verifica tileset con múltiples fuentes, animaciones y capas serializa completo."""
        src1 = TileSetAtlasSource(
            source_id="terrain",
            texture_region_x=0,
            texture_region_y=0,
            texture_region_w=128,
            texture_region_h=64,
            tile_width=32,
            tile_height=32,
        )
        src2 = TileSetAtlasSource(
            source_id="props",
            texture_region_x=128,
            texture_region_y=0,
            texture_region_w=64,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )
        src2.add_alternative(0, 0, "props_alt_0")

        layer1 = CustomDataLayerDef(name="z_index", layer_type="int", default_value=0)
        layer2 = CustomDataLayerDef(name="terrain_type", layer_type="string", default_value="default")

        frame1 = TileAnimationFrame(tile_id="terrain_1_0", duration=0.15)
        frame2 = TileAnimationFrame(tile_id="terrain_1_1", duration=0.15)

        tileset = TileSetResource(
            resource_id="full_tileset",
            resource_name="Complete TileSet",
            tile_width=16,
            tile_height=16,
            texture_ref={"path": "spritesheet.png"},
            columns=8,
            margin=1,
            spacing=0,
            sources=[src1, src2],
            tile_animations={
                "water": [frame1, frame2],
            },
            custom_data_layers=[layer1, layer2],
        )

        self.assertEqual(len(tileset.sources), 2)
        self.assertEqual(len(tileset.custom_data_layers), 2)
        self.assertEqual(tileset.total_tile_count(), 16)  # src1: 8 tiles + src2: 8 tiles

        data = tileset.to_dict()
        self.assertEqual(len(data["sources"]), 2)
        self.assertEqual(len(data["custom_data_layers"]), 2)
        self.assertEqual(len(data["tile_animations"]), 1)
        self.assertEqual(len(data["tile_animations"]["water"]), 2)

        restored = TileSetResource.from_dict(data)
        self.assertEqual(len(restored.sources), 2)
        self.assertEqual(len(restored.custom_data_layers), 2)
        self.assertEqual(len(restored.tile_animations["water"]), 2)
        self.assertEqual(restored.sources[0].source_id, "terrain")
        self.assertEqual(restored.sources[1].source_id, "props")
        self.assertEqual(restored.custom_data_layers[0].name, "z_index")
        self.assertEqual(restored.custom_data_layers[1].name, "terrain_type")


if __name__ == "__main__":
    unittest.main()
