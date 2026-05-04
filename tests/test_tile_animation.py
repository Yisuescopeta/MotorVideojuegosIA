"""
tests/test_tile_animation.py - Tests del sistema de animacion de tiles.
"""

import unittest

from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.tile_animation_system import TileAnimationSystem


class TileAnimationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = TileAnimationSystem()

    def _create_animated_tile_entity(
        self,
        anim_frames: list[dict],
        *,
        initial_tile_id: str = "water_0",
        animation_id: str = "water",
    ) -> Entity:
        """Crea una entidad con Tilemap + Transform y un tile animado."""
        entity = Entity("TestTileEntity")
        entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))

        tilemap = Tilemap(cell_width=16, cell_height=16)
        tilemap.layers = [{"name": "TestLayer", "tiles": {}}]
        tilemap.add_layer("TestLayer")
        tile = {
            "tile_id": initial_tile_id,
            "source": {},
            "flags": [],
            "tags": [],
            "custom": {"_anim_frames": anim_frames, "_anim_timer": 0.0, "_anim_frame_index": 0},
            "animated": True,
            "animation_id": animation_id,
            "terrain_type": "",
            "physics_layer": 0,
            "navigation_layer": 0,
            "custom_data": {},
        }
        tilemap.layers[0]["tiles"][(0, 0)] = tile
        entity.add_component(tilemap)
        self.world.add_entity(entity)
        return entity

    def _get_tile(self, entity: Entity) -> dict | None:
        tilemap = entity.get_component(Tilemap)
        if tilemap is None:
            return None
        return tilemap.layers[0].get("tiles", {}).get((0, 0))

    # -------------------------------------------------------
    # test_tile_animation_cycles_frames
    # -------------------------------------------------------
    def test_tile_animation_cycles_frames(self) -> None:
        frames = [
            {"tile_id": "water_0", "duration": 0.2},
            {"tile_id": "water_1", "duration": 0.2},
            {"tile_id": "water_2", "duration": 0.2},
        ]
        entity = self._create_animated_tile_entity(frames, initial_tile_id="water_0")

        # Frame 0 → 1 con 0.2s
        self.system.update(self.world, 0.2)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "water_1")
        self.assertEqual(tile["custom"]["_anim_frame_index"], 1)

        # Frame 1 → 2 con 0.25s
        self.system.update(self.world, 0.25)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "water_2")
        self.assertEqual(tile["custom"]["_anim_frame_index"], 2)

        # Frame 2 → 0 (loop) con 0.3s
        self.system.update(self.world, 0.3)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "water_0")
        self.assertEqual(tile["custom"]["_anim_frame_index"], 0)

    # -------------------------------------------------------
    # test_tile_animation_timer
    # -------------------------------------------------------
    def test_tile_animation_timer(self) -> None:
        frames = [
            {"tile_id": "lava_0", "duration": 0.5},
            {"tile_id": "lava_1", "duration": 0.5},
        ]
        entity = self._create_animated_tile_entity(frames, initial_tile_id="lava_0")

        # Avanzar 0.3s → timer = 0.3, no cruza threshold
        self.system.update(self.world, 0.3)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertAlmostEqual(tile["custom"]["_anim_timer"], 0.3, places=5)
        self.assertEqual(tile["custom"]["_anim_frame_index"], 0)
        self.assertEqual(tile["tile_id"], "lava_0")  # no cambio aun

        # Avanzar otros 0.3s → timer cruza 0.5, avanza a frame 1
        self.system.update(self.world, 0.3)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["custom"]["_anim_frame_index"], 1)
        self.assertEqual(tile["tile_id"], "lava_1")
        self.assertAlmostEqual(tile["custom"]["_anim_timer"], 0.0, places=5)  # reset

    # -------------------------------------------------------
    # test_tile_animation_loops
    # -------------------------------------------------------
    def test_tile_animation_loops(self) -> None:
        frames = [
            {"tile_id": "a", "duration": 0.1},
            {"tile_id": "b", "duration": 0.1},
        ]
        entity = self._create_animated_tile_entity(frames, initial_tile_id="a")

        # Ciclo 1: a → b
        self.system.update(self.world, 0.1)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "b")

        # Ciclo 1: b → a
        self.system.update(self.world, 0.1)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "a")

        # Ciclo 2: a → b
        self.system.update(self.world, 0.1)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "b")

        # Ciclo 2: b → a
        self.system.update(self.world, 0.1)
        tile = self._get_tile(entity)
        assert tile is not None
        self.assertEqual(tile["tile_id"], "a")

    # -------------------------------------------------------
    # test_tile_animation_skips_non_animated
    # -------------------------------------------------------
    def test_tile_animation_skips_non_animated(self) -> None:
        """Tiles sin animated=True no deben ser modificados."""
        entity = Entity("TestNonAnimated")
        entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))

        tilemap = Tilemap(cell_width=16, cell_height=16)
        tilemap.layers = [{"name": "Static", "tiles": {}}]
        tilemap.add_layer("Static")
        static_tile = {
            "tile_id": "static_grass",
            "source": {},
            "flags": [],
            "tags": [],
            "custom": {},
            "animated": False,
            "animation_id": "",
            "terrain_type": "",
            "physics_layer": 0,
            "navigation_layer": 0,
            "custom_data": {},
        }
        tilemap.layers[0]["tiles"][(0, 0)] = static_tile
        entity.add_component(tilemap)
        self.world.add_entity(entity)

        self.system.update(self.world, 2.0)
        tile = tilemap.layers[0]["tiles"].get((0, 0))
        assert tile is not None
        self.assertEqual(tile["tile_id"], "static_grass")
        self.assertFalse(tile["animated"])

    # -------------------------------------------------------
    # test_tile_animation_no_frames
    # -------------------------------------------------------
    def test_tile_animation_no_frames(self) -> None:
        """Tile con animated=True pero sin _anim_frames no debe crashear."""
        entity = Entity("TestNoFrames")
        entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))

        tilemap = Tilemap(cell_width=16, cell_height=16)
        tilemap.layers = [{"name": "BadAnim", "tiles": {}}]
        tilemap.add_layer("BadAnim")
        noframe_tile = {
            "tile_id": "orphan",
            "source": {},
            "flags": [],
            "tags": [],
            "custom": {},
            "animated": True,
            "animation_id": "missing",
            "terrain_type": "",
            "physics_layer": 0,
            "navigation_layer": 0,
            "custom_data": {},
        }
        tilemap.layers[0]["tiles"][(0, 0)] = noframe_tile
        entity.add_component(tilemap)
        self.world.add_entity(entity)

        # No debe lanzar excepción
        self.system.update(self.world, 1.0)
        tile = tilemap.layers[0]["tiles"].get((0, 0))
        assert tile is not None
        self.assertEqual(tile["tile_id"], "orphan")  # tile_id no cambia


if __name__ == "__main__":
    unittest.main()
