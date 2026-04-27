import unittest

from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.rendering.render_spatial_index import RenderSpatialIndex


class RenderSpatialIndexTests(unittest.TestCase):
    def _entity_with_transform(self, world: World, name: str, *, x: float, y: float):
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y, rotation=0.0, scale_x=1.0, scale_y=1.0))
        return entity

    def test_query_returns_only_entities_intersecting_camera_bounds(self) -> None:
        world = World()
        visible = self._entity_with_transform(world, "Visible", x=10.0, y=10.0)
        visible.add_component(Sprite(width=16, height=16))
        outside = self._entity_with_transform(world, "Outside", x=200.0, y=10.0)
        outside.add_component(Sprite(width=16, height=16))

        index = RenderSpatialIndex(cell_size=32.0)
        index.rebuild(world.get_all_entities())

        self.assertEqual(index.query((0.0, 0.0, 32.0, 32.0)), {visible.id})

    def test_transform_only_entities_use_placeholder_bounds(self) -> None:
        world = World()
        entity = self._entity_with_transform(world, "TransformOnly", x=10.0, y=10.0)

        index = RenderSpatialIndex(cell_size=32.0)
        index.rebuild(world.get_all_entities())

        self.assertEqual(index.query((0.0, 0.0, 32.0, 32.0)), {entity.id})
        self.assertEqual(index.query((40.0, 40.0, 50.0, 50.0)), set())

    def test_sprite_bounds_respect_origin_and_negative_scale(self) -> None:
        world = World()
        entity = self._entity_with_transform(world, "Scaled", x=100.0, y=50.0)
        transform = entity.get_component(Transform)
        transform.scale_x = -2.0
        transform.scale_y = 3.0
        entity.add_component(Sprite(width=20, height=10, origin_x=1.0, origin_y=0.0))

        index = RenderSpatialIndex(cell_size=32.0)
        index.rebuild(world.get_all_entities())

        self.assertEqual(index.query((59.0, 49.0, 61.0, 51.0)), {entity.id})
        self.assertEqual(index.query((101.0, 49.0, 110.0, 51.0)), set())

    def test_render_order_only_entity_uses_placeholder_bounds(self) -> None:
        world = World()
        entity = self._entity_with_transform(world, "Placeholder", x=50.0, y=50.0)
        entity.add_component(RenderOrder2D())

        index = RenderSpatialIndex(cell_size=32.0)
        index.rebuild(world.get_all_entities())

        self.assertEqual(index.query((35.0, 35.0, 36.0, 36.0)), {entity.id})
        self.assertEqual(index.query((0.0, 0.0, 10.0, 10.0)), set())

    def test_tilemap_indexes_whole_tilemap_bounds_without_chunk_culling(self) -> None:
        world = World()
        entity = self._entity_with_transform(world, "Map", x=100.0, y=200.0)
        entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0"}, {"x": 3, "y": 2, "tile_id": "1"}]}],
            )
        )

        index = RenderSpatialIndex(cell_size=32.0)
        index.rebuild(world.get_all_entities())

        self.assertEqual(index.query((150.0, 230.0, 151.0, 231.0)), {entity.id})
        self.assertEqual(index.query((10.0, 10.0, 20.0, 20.0)), set())


if __name__ == "__main__":
    unittest.main()
