import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.joint2d import Joint2D
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.systems.render_system import RenderSystem


class RenderGraphTests(unittest.TestCase):
    def _make_sprite_entity(
        self,
        world: World,
        name: str,
        *,
        x: float,
        sorting_layer: str = "Default",
        order_in_layer: int = 0,
        render_pass: str = "World",
        texture_path: str = "assets/shared.png",
        material_id: str = "sprite_default",
    ):
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Sprite(texture_path=texture_path, width=32, height=32))
        entity.add_component(RenderOrder2D(sorting_layer=sorting_layer, order_in_layer=order_in_layer, render_pass=render_pass))
        if material_id != "sprite_default":
            entity.add_component(RenderStyle2D(material_id=material_id))
        return entity

    def test_render_graph_splits_world_overlay_and_debug_passes(self) -> None:
        world = World()
        world.feature_metadata = {
            "render_2d": {
                "sorting_layers": ["Default", "Gameplay", "Foreground"],
            }
        }
        self._make_sprite_entity(world, "Ground", x=0.0, sorting_layer="Default", order_in_layer=0, render_pass="World")
        self._make_sprite_entity(world, "Hero", x=10.0, sorting_layer="Gameplay", order_in_layer=3, render_pass="World")
        self._make_sprite_entity(world, "HudMarker", x=20.0, sorting_layer="Foreground", order_in_layer=0, render_pass="Overlay")
        world.selected_entity_name = "Hero"

        render_system = RenderSystem()
        graph = render_system.get_last_render_graph()
        self.assertEqual(graph["totals"]["render_entities"], 0)

        graph = render_system._public_graph(render_system._build_render_graph(world))

        self.assertEqual([pass_data["name"] for pass_data in graph["passes"]], ["World", "Overlay", "Debug"])
        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["Ground", "Hero"])
        self.assertEqual([command["entity_name"] for command in graph["passes"][1]["commands"]], ["HudMarker"])
        self.assertEqual([command["entity_name"] for command in graph["passes"][2]["commands"]], ["Hero"])
        self.assertEqual(graph["totals"]["render_entities"], 3)
        self.assertEqual(graph["totals"]["pass_count"], 3)

    def test_batching_groups_contiguous_entities_by_material_atlas_and_layer(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay", "Foreground"]}}
        self._make_sprite_entity(world, "A", x=0.0, sorting_layer="Gameplay", texture_path="assets/atlas_a.png")
        self._make_sprite_entity(world, "B", x=10.0, sorting_layer="Gameplay", texture_path="assets/atlas_a.png")
        self._make_sprite_entity(world, "C", x=20.0, sorting_layer="Gameplay", texture_path="assets/atlas_b.png")
        self._make_sprite_entity(world, "D", x=30.0, sorting_layer="Foreground", texture_path="assets/atlas_a.png")
        self._make_sprite_entity(world, "E", x=40.0, sorting_layer="Foreground", texture_path="assets/atlas_a.png", material_id="outline")

        render_system = RenderSystem()
        graph = render_system._public_graph(render_system._build_render_graph(world))
        world_pass = graph["passes"][0]

        self.assertEqual([batch["entity_names"] for batch in world_pass["batches"]], [["A", "B"], ["C"], ["D"], ["E"]])
        self.assertEqual(world_pass["stats"]["batches"], 4)
        self.assertEqual(graph["totals"]["draw_calls"], 5)

    def test_headless_profile_reports_stable_metrics_for_large_scene(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay"]}}
        for index in range(5000):
            self._make_sprite_entity(
                world,
                f"Sprite_{index}",
                x=float(index),
                sorting_layer="Gameplay",
                texture_path="assets/bench_shared.png",
            )

        render_system = RenderSystem()
        stats = render_system.profile_world(world)

        self.assertEqual(stats["render_entities"], 5000)
        self.assertEqual(stats["draw_calls"], 5000)
        self.assertEqual(stats["batches"], 1)
        self.assertEqual(stats["passes"]["World"]["batches"], 1)
        self.assertEqual(stats["passes"]["World"]["draw_calls"], 5000)

    def test_debug_graph_includes_joint_commands_when_debug_overlay_is_enabled(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default"]}}
        anchor = world.create_entity("Anchor")
        anchor.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        jointed = world.create_entity("Pendulum")
        jointed.add_component(Transform(x=10.0, y=10.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        jointed.add_component(Joint2D(joint_type="distance", connected_entity="Anchor", rest_length=14.0))

        render_system = RenderSystem()
        render_system.set_debug_options(draw_colliders=True)
        graph = render_system._public_graph(render_system._build_render_graph(world))
        debug_commands = graph["passes"][2]["commands"]

        self.assertEqual([command["debug_kind"] for command in debug_commands], ["joint"])
        self.assertEqual(debug_commands[0]["entity_name"], "Pendulum")

    def test_tilemap_render_graph_chunks_tiles_and_rebuilds_incrementally(self) -> None:
        world = World()
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[
                    {
                        "name": "Ground",
                        "tiles": [
                            {"x": 0, "y": 0, "tile_id": "grass"},
                            {"x": 1, "y": 0, "tile_id": "grass"},
                            {"x": 20, "y": 20, "tile_id": "stone"},
                        ],
                    }
                ],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        first_stats = render_system.profile_world(world)
        self.assertEqual(first_stats["tilemap_chunks"], 2)
        self.assertEqual(first_stats["tilemap_chunk_rebuilds"], 2)

        second_stats = render_system.profile_world(world)
        self.assertEqual(second_stats["tilemap_chunks"], 2)
        self.assertEqual(second_stats["tilemap_chunk_rebuilds"], 0)

        tilemap = tilemap_entity.get_component(Tilemap)
        tilemap.set_tile("Ground", 2, 0, "grass_edge")
        world.touch()
        third_stats = render_system.profile_world(world)
        self.assertEqual(third_stats["tilemap_chunks"], 2)
        self.assertEqual(third_stats["tilemap_chunk_rebuilds"], 1)

    def test_large_tilemap_profile_reports_chunked_batches(self) -> None:
        world = World()
        tilemap_entity = world.create_entity("LargeMap")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        layers = []
        for layer_name in ("Ground", "Deco", "Overlay"):
            tiles = []
            for y in range(256):
                for x in range(256):
                    tiles.append({"x": x, "y": y, "tile_id": f"{layer_name}_{(x + y) % 4}"})
            layers.append({"name": layer_name, "tiles": tiles})
        tilemap_entity.add_component(Tilemap(cell_width=8, cell_height=8, layers=layers))
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        stats = render_system.profile_world(world)

        self.assertEqual(stats["tilemap_chunks"], 768)
        self.assertEqual(stats["tilemap_chunk_rebuilds"], 768)
        self.assertEqual(stats["draw_calls"], 768)
        self.assertEqual(stats["batches"], 768)

    def test_debug_dump_includes_tile_chunks_camera_and_manual_primitives(self) -> None:
        world = World()
        camera_entity = world.create_entity("Camera")
        camera_entity.add_component(Transform(x=64.0, y=64.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        camera_entity.add_component(Camera2D(is_primary=True, zoom=1.0))

        hero = world.create_entity("Hero")
        hero.add_component(Transform(x=16.0, y=16.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        hero.add_component(Collider(width=16.0, height=16.0))
        world.selected_entity_name = "Hero"

        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}]}],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        render_system.set_debug_options(draw_colliders=True, draw_tile_chunks=True, draw_camera=True)
        render_system.set_debug_primitives(
            [
                {
                    "kind": "line",
                    "start": {"x": 0.0, "y": 0.0},
                    "end": {"x": 32.0, "y": 32.0},
                    "color": [255, 0, 255, 255],
                    "entity_name": "Guide",
                }
            ]
        )

        dump = render_system.get_debug_geometry_dump(world, viewport_size=(128.0, 128.0))
        debug_kinds = [command["debug_kind"] for command in dump["commands"]]

        self.assertIn("collider", debug_kinds)
        self.assertIn("selection", debug_kinds)
        self.assertIn("tile_chunk", debug_kinds)
        self.assertIn("camera", debug_kinds)
        self.assertIn("line", debug_kinds)
        self.assertEqual(dump["viewport"], {"width": 128, "height": 128})


if __name__ == "__main__":
    unittest.main()
