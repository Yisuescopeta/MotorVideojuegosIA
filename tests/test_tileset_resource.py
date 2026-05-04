"""
tests/test_tileset_resource.py — Tests para TileSetResource y sus dataclasses asociadas.
"""

import unittest

from engine.resources.tileset_resource import (
    CustomDataLayerDef,
    TileAnimation,
    TileAnimationFrame,
    TileMetaData,
    TileNavigationPolygon,
    TileOcclusionPolygon,
    TilePhysicsShape,
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

    # ── 9. test_remove_source ──────────────────────────────────────────

    def test_remove_source(self) -> None:
        """Verifica añadir source, eliminarlo, verificar len=0."""
        tileset = TileSetResource()
        source = TileSetAtlasSource(
            source_id="src_to_remove",
            texture_region_w=32,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source)
        self.assertEqual(len(tileset.sources), 1)
        self.assertTrue(tileset.remove_source("src_to_remove"))
        self.assertEqual(len(tileset.sources), 0)
        self.assertFalse(tileset.remove_source("non_existent"))

    # ── 10. test_clear_animation ───────────────────────────────────────

    def test_clear_animation(self) -> None:
        """Verifica setear animación, limpiarla, verificar has_animation=False."""
        tileset = TileSetResource()
        frame = TileAnimationFrame(tile_id="tile_01", duration=0.3)
        tileset.set_tile_animation("tile_01", [frame])
        self.assertTrue(tileset.has_animation("tile_01"))
        tileset.clear_animation("tile_01")
        self.assertFalse(tileset.has_animation("tile_01"))
        self.assertEqual(len(tileset.get_tile_animation("tile_01")), 0)

    # ── 11. test_remove_custom_data_layer ──────────────────────────────

    def test_remove_custom_data_layer(self) -> None:
        """Verifica añadir capa, eliminarla, verificar len=0."""
        tileset = TileSetResource()
        layer = CustomDataLayerDef(name="test_layer", layer_type="float", default_value=0.0)
        tileset.add_custom_data_layer(layer)
        self.assertEqual(len(tileset.custom_data_layers), 1)
        self.assertTrue(tileset.remove_custom_data_layer("test_layer"))
        self.assertEqual(len(tileset.custom_data_layers), 0)
        self.assertFalse(tileset.remove_custom_data_layer("non_existent"))

    # ── 12. test_tile_physics_shape_serialization ──────────────────────

    def test_tile_physics_shape_serialization(self) -> None:
        """Verifica roundtrip de TilePhysicsShape."""
        shape = TilePhysicsShape(
            shape_type="box",
            points=[[0, 0], [16, 16]],
            one_way=True,
            one_way_direction=(0, -1),
        )
        data = shape.to_dict()
        self.assertEqual(data["shape_type"], "box")
        self.assertEqual(data["one_way"], True)
        restored = TilePhysicsShape.from_dict(data)
        self.assertEqual(restored.shape_type, "box")
        self.assertEqual(restored.one_way, True)
        self.assertEqual(restored.one_way_direction, (0, -1))
        self.assertEqual(restored.points, [[0, 0], [16, 16]])

    # ── 13. test_tile_navigation_polygon_serialization ─────────────────

    def test_tile_navigation_polygon_serialization(self) -> None:
        """Verifica roundtrip de TileNavigationPolygon."""
        poly = TileNavigationPolygon(points=[(0, 0), (16, 0), (16, 16)])
        data = poly.to_dict()
        self.assertEqual(len(data["points"]), 3)
        restored = TileNavigationPolygon.from_dict(data)
        self.assertEqual(restored.points, [[0, 0], [16, 0], [16, 16]])

    # ── 14. test_tile_occlusion_polygon_serialization ──────────────────

    def test_tile_occlusion_polygon_serialization(self) -> None:
        """Verifica roundtrip de TileOcclusionPolygon."""
        poly = TileOcclusionPolygon(points=[(4, 4), (12, 4), (12, 12), (4, 12)])
        data = poly.to_dict()
        self.assertEqual(len(data["points"]), 4)
        restored = TileOcclusionPolygon.from_dict(data)
        self.assertEqual(len(restored.points), 4)

    # ── 15. test_tile_metadata_serialization ───────────────────────────

    def test_tile_metadata_serialization(self) -> None:
        """Verifica roundtrip de TileMetaData con todos los campos."""
        meta = TileMetaData(
            tile_id="src_0_0",
            physics_layers=[
                TilePhysicsShape(shape_type="box", points=[(0, 0), (16, 16)]),
            ],
            navigation_polygon=TileNavigationPolygon(points=[(0, 0), (16, 16)]),
            occlusion_polygon=TileOcclusionPolygon(points=[(4, 4), (12, 12)]),
            animation=TileAnimation(frames=[("src_1_0", 0.2)], speed=2.0, mode="pingpong"),
            terrain_set=0,
            terrain=1,
            terrain_peering_bits=85,
            probability=0.5,
            z_index=2,
            modulate=(128, 128, 128, 255),
        )
        data = meta.to_dict()
        restored = TileMetaData.from_dict(data)
        self.assertEqual(restored.tile_id, "src_0_0")
        self.assertEqual(len(restored.physics_layers), 1)
        self.assertEqual(restored.physics_layers[0].shape_type, "box")
        self.assertIsNotNone(restored.navigation_polygon)
        self.assertIsNotNone(restored.occlusion_polygon)
        self.assertIsNotNone(restored.animation)
        self.assertEqual(restored.animation.speed, 2.0)
        self.assertEqual(restored.animation.mode, "pingpong")
        self.assertEqual(restored.terrain_set, 0)
        self.assertEqual(restored.terrain, 1)
        self.assertEqual(restored.terrain_peering_bits, 85)
        self.assertEqual(restored.probability, 0.5)
        self.assertEqual(restored.z_index, 2)
        self.assertEqual(restored.modulate, (128, 128, 128, 255))
        self.assertTrue(restored.is_solid)

    # ── 16. test_tile_metadata_not_solid_when_no_physics ───────────────

    def test_tile_metadata_not_solid_when_no_physics(self) -> None:
        """Verifica is_solid es False sin physics_layers."""
        meta = TileMetaData(tile_id="src_0_1")
        self.assertFalse(meta.is_solid)

    # ── 17. test_atlas_source_tile_metadata_storage ────────────────────

    def test_atlas_source_tile_metadata_storage(self) -> None:
        """Verifica set/get de metadata por tile en TileSetAtlasSource."""
        source = TileSetAtlasSource(
            source_id="atlas_test",
            texture_region_w=32,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )
        meta = TileMetaData(
            tile_id="atlas_test_0_0",
            terrain_set=0,
            terrain=1,
            terrain_peering_bits=85,
        )
        source.set_tile_metadata("atlas_test_0_0", meta)
        retrieved = source.get_tile_metadata("atlas_test_0_0")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.terrain_set, 0)
        self.assertEqual(retrieved.terrain, 1)
        self.assertEqual(retrieved.terrain_peering_bits, 85)

        # get by coordinate
        retrieved2 = source.get_tile_metadata_at(0, 0)
        self.assertIsNotNone(retrieved2)
        self.assertEqual(retrieved2.tile_id, "atlas_test_0_0")

        # non-existent tile
        self.assertIsNone(source.get_tile_metadata("non_existent"))

        # non-existent coordinate
        self.assertIsNone(source.get_tile_metadata_at(99, 99))

    # ── 18. test_atlas_source_tile_metadata_roundtrip ──────────────────

    def test_atlas_source_tile_metadata_roundtrip(self) -> None:
        """Verifica que tile_metadata persiste en serialización de AtlasSource."""
        source = TileSetAtlasSource(
            source_id="atlas_meta_test",
            texture_region_w=64,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )
        meta = TileMetaData(
            tile_id="atlas_meta_test_0_0",
            terrain_set=0,
            terrain=0,
            terrain_peering_bits=255,
            physics_layers=[TilePhysicsShape(shape_type="box")],
        )
        source.set_tile_metadata("atlas_meta_test_0_0", meta)
        data = source.to_dict()
        self.assertIn("tile_metadata", data)
        restored = TileSetAtlasSource.from_dict(data)
        restored_meta = restored.get_tile_metadata("atlas_meta_test_0_0")
        self.assertIsNotNone(restored_meta)
        self.assertEqual(restored_meta.terrain_peering_bits, 255)
        self.assertTrue(restored_meta.is_solid)

    # ── 19. test_terrain_peering_bits ──────────────────────────────────

    def test_terrain_peering_bits(self) -> None:
        """Verifica calcular bits de peering para un tile central."""
        tileset = TileSetResource()
        source = TileSetAtlasSource(
            source_id="terrain_src",
            texture_region_w=64,
            texture_region_h=64,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source)

        # Register all tiles with terrain metadata
        # Center: terrain_set=0, terrain=1
        center_meta = TileMetaData(tile_id="terrain_src_1_1", terrain_set=0, terrain=1, terrain_peering_bits=0)
        source.set_tile_metadata("terrain_src_1_1", center_meta)

        # Neighbors with same terrain_set and terrain
        neighbors = {
            (1, 0): "terrain_src_1_0",   # N
            (2, 0): "terrain_src_2_0",   # NE
            (2, 1): "terrain_src_2_1",   # E
            (2, 2): "terrain_src_2_2_other",  # SE — different! terrain=0
            (1, 2): "terrain_src_1_2",   # S
            (0, 2): "terrain_src_0_2",   # SW
            (0, 1): "terrain_src_0_1",   # W
            (0, 0): "terrain_src_0_0",   # NW
        }

        for coord, tid in neighbors.items():
            terrain_val = 1 if tid != "terrain_src_2_2_other" else 0
            n_meta = TileMetaData(tile_id=tid, terrain_set=0, terrain=terrain_val, terrain_peering_bits=0)
            source.set_tile_metadata(tid, n_meta)

        # Build cells dict
        cells = {}
        for coord, tid in neighbors.items():
            cells[coord] = {"tile_id": tid}
        cells[(1, 1)] = {"tile_id": "terrain_src_1_1"}

        bits = tileset.get_terrain_peering_bits("terrain_src", cells, 1, 1, 0, 1)

        # N=1, NE=2, E=4, SE should be 0 (terrain=0), S=16, SW=32, W=64, NW=128
        expected = 1 + 2 + 4 + 0 + 16 + 32 + 64 + 128  # = 247
        self.assertEqual(bits, expected)

    # ── 20. test_terrain_peering_bits_no_neighbors ─────────────────────

    def test_terrain_peering_bits_no_neighbors(self) -> None:
        """Verifica bits=0 cuando no hay vecinos."""
        tileset = TileSetResource()
        source = TileSetAtlasSource(
            source_id="lonely_src",
            texture_region_w=16,
            texture_region_h=16,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source)
        meta = TileMetaData(tile_id="lonely_src_0_0", terrain_set=0, terrain=1, terrain_peering_bits=0)
        source.set_tile_metadata("lonely_src_0_0", meta)
        cells = {(0, 0): {"tile_id": "lonely_src_0_0"}}
        bits = tileset.get_terrain_peering_bits("lonely_src", cells, 0, 0, 0, 1)
        self.assertEqual(bits, 0)

    # ── 21. test_auto_tile_selection ───────────────────────────────────

    def test_auto_tile_selection(self) -> None:
        """Verifica que get_auto_tile_id encuentra tile con bits matching."""
        tileset = TileSetResource()
        source = TileSetAtlasSource(
            source_id="autotile_src",
            texture_region_w=48,
            texture_region_h=16,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source)

        # Register tiles with specific peering bit patterns
        source.set_tile_metadata("autotile_src_0_0", TileMetaData(
            tile_id="autotile_src_0_0", terrain_set=0, terrain=0, terrain_peering_bits=0,  # isolated
        ))
        source.set_tile_metadata("autotile_src_1_0", TileMetaData(
            tile_id="autotile_src_1_0", terrain_set=0, terrain=0, terrain_peering_bits=85,  # 01010101 = all 4 cardinal
        ))
        source.set_tile_metadata("autotile_src_2_0", TileMetaData(
            tile_id="autotile_src_2_0", terrain_set=0, terrain=0, terrain_peering_bits=255,  # all 8
        ))

        result = tileset.get_auto_tile_id("autotile_src", 0, 0)
        self.assertEqual(result, "autotile_src_0_0")

        result = tileset.get_auto_tile_id("autotile_src", 0, 85)
        self.assertEqual(result, "autotile_src_1_0")

        result = tileset.get_auto_tile_id("autotile_src", 0, 255)
        self.assertEqual(result, "autotile_src_2_0")

        # No match
        result = tileset.get_auto_tile_id("autotile_src", 0, 1)
        self.assertIsNone(result)

        # Non-existent source
        result = tileset.get_auto_tile_id("does_not_exist", 0, 0)
        self.assertIsNone(result)

    # ── 22. test_set_cells_terrain_connect ─────────────────────────────

    def test_set_cells_terrain_connect(self) -> None:
        """Verifica set_cells_terrain_connect actualiza tile_ids."""
        tileset = TileSetResource()
        source = TileSetAtlasSource(
            source_id="terrain_conn",
            texture_region_w=48,
            texture_region_h=16,
            tile_width=16,
            tile_height=16,
        )
        tileset.add_source(source)

        # Register terrain tiles
        source.set_tile_metadata("terrain_conn_0_0", TileMetaData(
            tile_id="terrain_conn_0_0", terrain_set=0, terrain=1, terrain_peering_bits=0,
        ))
        source.set_tile_metadata("terrain_conn_1_0", TileMetaData(
            tile_id="terrain_conn_1_0", terrain_set=0, terrain=1, terrain_peering_bits=85,
        ))
        source.set_tile_metadata("terrain_conn_2_0", TileMetaData(
            tile_id="terrain_conn_2_0", terrain_set=0, terrain=1, terrain_peering_bits=255,
        ))

        # Setup cells: center (1,1) with neighbors all having terrain_set=0, terrain=1
        cells = {}
        for y in range(3):
            for x in range(3):
                tid = f"terrain_conn_{x}_{y}" if x < 3 else "other"
                cells[(x, y)] = {"tile_id": tid}
        # Register all neighbor tiles with terrain metadata
        for y in range(3):
            for x in range(3):
                if x == 1 and y == 1:
                    continue  # skip center
                tid = f"terrain_conn_{x}_{y}" if x < 3 else "other"
                # Only register if not already registered (prevent overwriting peering bits)
                if source.get_tile_metadata(tid) is None:
                    source.set_tile_metadata(tid, TileMetaData(
                        tile_id=tid, terrain_set=0, terrain=1, terrain_peering_bits=0,
                    ))

        changes = tileset.set_cells_terrain_connect("terrain_conn", cells, 0, 1)
        # Center tile should be changed (8 neighbors all terrain=1 → bits=255)
        self.assertIn((1, 1), changes)
        self.assertEqual(changes[(1, 1)], "terrain_conn_2_0")  # matches bits=255

    # ── 23. test_tileset_resource_new_fields_serialization ─────────────

    def test_tileset_resource_new_fields_serialization(self) -> None:
        """Verifica roundtrip de terrain_sets, physics/nav/occlusion layers."""
        tileset = TileSetResource(
            resource_id="ts_fields",
            resource_name="Fields Test",
            terrain_sets=[
                {"name": "Ground", "terrains": [
                    {"name": "Grass", "color": "#00ff00"},
                    {"name": "Dirt", "color": "#8b4513"},
                ]},
            ],
            physics_layers=[{"name": "default", "collision_layer": 1, "collision_mask": 1}],
            navigation_layers=[{"name": "walkable"}],
            occlusion_layers=[{"name": "walls"}],
        )
        data = tileset.to_dict()
        self.assertIn("terrain_sets", data)
        self.assertIn("physics_layers", data)
        self.assertIn("navigation_layers", data)
        self.assertIn("occlusion_layers", data)

        restored = TileSetResource.from_dict(data)
        self.assertEqual(len(restored.terrain_sets), 1)
        self.assertEqual(restored.terrain_sets[0]["name"], "Ground")
        self.assertEqual(len(restored.physics_layers), 1)
        self.assertEqual(restored.physics_layers[0]["name"], "default")
        self.assertEqual(len(restored.navigation_layers), 1)
        self.assertEqual(len(restored.occlusion_layers), 1)

    # ── 24. test_tile_animation_dataclass ──────────────────────────────

    def test_tile_animation_dataclass(self) -> None:
        """Verifica TileAnimation dataclass serialization."""
        anim = TileAnimation(
            frames=[("tile_a", 0.1), ("tile_b", 0.2)],
            speed=1.5,
            mode="pingpong",
        )
        data = anim.to_dict()
        self.assertEqual(data["speed"], 1.5)
        self.assertEqual(data["mode"], "pingpong")
        self.assertEqual(len(data["frames"]), 2)

        restored = TileAnimation.from_dict(data)
        self.assertEqual(restored.speed, 1.5)
        self.assertEqual(restored.mode, "pingpong")
        self.assertEqual(len(restored.frames), 2)

        # Defaults
        default_anim = TileAnimation()
        self.assertEqual(default_anim.speed, 1.0)
        self.assertEqual(default_anim.mode, "forward")

    # ── 25. test_source_without_metadata_is_backward_compatible ────────

    def test_source_without_metadata_is_backward_compatible(self) -> None:
        """Verifica que fuentes sin tile_metadata sigan funcionando."""
        source = TileSetAtlasSource(
            source_id="legacy_src",
            texture_region_w=32,
            texture_region_h=32,
            tile_width=16,
            tile_height=16,
        )
        data = source.to_dict()
        self.assertIn("tile_metadata", data)
        self.assertEqual(data["tile_metadata"], {})

        restored = TileSetAtlasSource.from_dict(data)
        self.assertEqual(restored.tile_metadata, {})
        self.assertIsNone(restored.get_tile_metadata("any"))


if __name__ == "__main__":
    unittest.main()
