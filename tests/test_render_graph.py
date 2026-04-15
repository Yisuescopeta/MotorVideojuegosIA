import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.assets.asset_service import AssetService
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.project.project_service import ProjectService
from engine.rendering.render_targets import RenderTargetPool
from engine.rendering.tilemap_chunk_renderer import TilemapChunkRenderer
from engine.systems.render_system import RenderSystem


class RenderGraphTests(unittest.TestCase):
    REPO_ROOT = Path(__file__).resolve().parents[1]

    @staticmethod
    def _rgba_tuple(color) -> tuple[int, int, int, int]:
        if hasattr(color, "r"):
            return (int(color.r), int(color.g), int(color.b), int(color.a))
        return tuple(color)

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

    def _make_tilemap_entity(
        self,
        world: World,
        tilemap: Tilemap,
        *,
        name: str = "Map",
        x: float = 0.0,
        y: float = 0.0,
        sorting_layer: str = "Default",
        order_in_layer: int = 0,
        render_pass: str = "World",
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ):
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y, rotation=rotation, scale_x=scale_x, scale_y=scale_y))
        entity.add_component(tilemap)
        entity.add_component(RenderOrder2D(sorting_layer=sorting_layer, order_in_layer=order_in_layer, render_pass=render_pass))
        return entity

    def _create_temp_render_project(self) -> tuple[ProjectService, AssetService]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name) / "RenderProject"
        project_service = ProjectService(project_root.as_posix())
        return project_service, AssetService(project_service)

    def _copy_fixture_asset(self, project_service: ProjectService, source_relative_path: str, target_relative_path: str) -> str:
        source_path = self.REPO_ROOT / source_relative_path
        target_path = project_service.resolve_path(target_relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        return target_relative_path

    def _first_public_tilemap_command(self, render_system: RenderSystem, world: World) -> dict:
        graph = render_system._public_graph(render_system._build_render_graph(world))
        for pass_data in graph["passes"]:
            for command in pass_data["commands"]:
                if command["kind"] == "tilemap_chunk":
                    return command
        raise AssertionError("No tilemap chunk command found in public graph")

    def _first_private_tilemap_command(self, render_system: RenderSystem, world: World) -> dict:
        graph = render_system._build_render_graph(world)
        for pass_data in graph["passes"]:
            for command in pass_data["commands"]:
                if command["kind"] == "tilemap_chunk":
                    return command
        raise AssertionError("No tilemap chunk command found in private graph")

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
        self.assertEqual(graph["totals"]["render_commands"], 5)
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
        self.assertEqual(stats["render_commands"], 5000)
        self.assertEqual(stats["draw_calls"], 5000)
        self.assertEqual(stats["batches"], 1)
        self.assertEqual(stats["passes"]["World"]["batches"], 1)
        self.assertEqual(stats["passes"]["World"]["render_commands"], 5000)
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
        self.assertEqual(first_stats["render_commands"], 2)
        self.assertEqual(first_stats["draw_calls"], 0)
        self.assertEqual(first_stats["tilemap_tile_draw_calls"], 0)

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
        self.assertEqual(stats["render_commands"], 768)
        self.assertEqual(stats["draw_calls"], 0)
        self.assertEqual(stats["tilemap_tile_draw_calls"], 0)
        self.assertEqual(stats["batches"], 768)

    def test_tilemap_profile_reports_chunk_draw_calls_separate_from_tile_rebuild_work(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/draw_metrics.png")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[
                    {
                        "name": "Ground",
                        "tiles": [
                            {"x": 0, "y": 0, "tile_id": "0"},
                            {"x": 1, "y": 0, "tile_id": "1"},
                            {"x": 2, "y": 0, "tile_id": "not-a-grid-index"},
                        ],
                    }
                ],
            ),
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        stats = render_system.profile_world(world)

        self.assertEqual(stats["tilemap_chunks"], 1)
        self.assertEqual(stats["render_commands"], 1)
        self.assertEqual(stats["draw_calls"], 1)
        self.assertEqual(stats["tilemap_tile_draw_calls"], 2)
        self.assertEqual(stats["passes"]["World"]["render_commands"], 1)
        self.assertEqual(stats["passes"]["World"]["draw_calls"], 1)
        self.assertEqual(stats["passes"]["World"]["tilemap_tile_draw_calls"], 2)

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

    def test_tilemap_render_graph_uses_slice_rect_payload_when_named_slice_exists(self) -> None:
        project_service, asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/test_spritesheet.png")
        asset_service.generate_sprite_grid_slices(asset_path, cell_width=16, cell_height=16, naming_prefix="tile")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "tile_9"}]}],
            ),
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_public_tilemap_command(render_system, world)
        tile_payload = command["chunk_data"]["tiles"][0]

        self.assertTrue(tile_payload["resolved"])
        self.assertEqual(tile_payload["resolution"], "slice")
        self.assertEqual(tile_payload["texture"]["path"], asset_path)
        self.assertEqual(tile_payload["source_rect"], {"x": 16, "y": 16, "width": 16, "height": 16})
        self.assertEqual(command["chunk_data"]["unresolved_tiles"], 0)

    def test_tilemap_render_graph_falls_back_to_grid_when_slice_metadata_is_missing(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/grid_only.png")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 1, "y": 2, "tile_id": "9"}]}],
            ),
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_public_tilemap_command(render_system, world)
        tile_payload = command["chunk_data"]["tiles"][0]

        self.assertTrue(tile_payload["resolved"])
        self.assertEqual(tile_payload["resolution"], "grid")
        self.assertEqual(tile_payload["source_rect"], {"x": 16, "y": 16, "width": 16, "height": 16})
        self.assertEqual(tile_payload["dest"], {"x": 16.0, "y": 32.0, "width": 16, "height": 16})

    def test_tilemap_render_graph_prefers_tile_source_over_component_tileset(self) -> None:
        project_service, asset_service = self._create_temp_render_project()
        component_tileset = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/component.png")
        override_tileset = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/override.png")
        asset_service.generate_sprite_grid_slices(override_tileset, cell_width=16, cell_height=16, naming_prefix="override")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=component_tileset,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[
                    {
                        "name": "Ground",
                        "tiles": [{"x": 0, "y": 0, "tile_id": "override_5", "source": {"path": override_tileset, "guid": ""}}],
                    }
                ],
            ),
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_public_tilemap_command(render_system, world)
        tile_payload = command["chunk_data"]["tiles"][0]

        self.assertTrue(tile_payload["resolved"])
        self.assertEqual(tile_payload["resolution"], "slice")
        self.assertEqual(tile_payload["texture"]["path"], override_tileset)
        self.assertEqual(tile_payload["source_rect"], {"x": 80, "y": 0, "width": 16, "height": 16})

    def test_tilemap_multilayer_commands_preserve_layer_sorting_order(self) -> None:
        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[
                    {"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0"}]},
                    {"name": "Overlay", "tiles": [{"x": 0, "y": 0, "tile_id": "1"}]},
                ],
            ),
            order_in_layer=7,
        )

        render_system = RenderSystem()
        graph = render_system._public_graph(render_system._build_render_graph(world))
        world_pass_commands = [command for command in graph["passes"][0]["commands"] if command["kind"] == "tilemap_chunk"]

        self.assertEqual([command["chunk_id"] for command in world_pass_commands], ["Ground/0,0", "Overlay/0,0"])
        self.assertEqual([command["order_in_layer"] for command in world_pass_commands], [7, 8])

    def test_tilemap_render_graph_supports_demo_scene_tileset_paths_outside_catalog(self) -> None:
        scene_path = self.REPO_ROOT / "levels" / "platformer_vertical_slice.json"
        scene_payload = json.loads(scene_path.read_text(encoding="utf-8"))
        tilemap_payload = next(
            entity["components"]["Tilemap"]
            for entity in scene_payload["entities"]
            if entity.get("name") == "LevelTilemap"
        )
        project_service, _asset_service = self._create_temp_render_project()
        demo_tileset_path = self._copy_fixture_asset(
            project_service,
            "demo/platformer_demo_package/assets/tilesets/grassMid.png",
            "demo/platformer_demo_package/assets/tilesets/grassMid.png",
        )
        tilemap_payload["tileset"]["path"] = demo_tileset_path
        tilemap_payload["tileset_path"] = demo_tileset_path
        for layer in tilemap_payload.get("layers", []):
            for tile in layer.get("tiles", []):
                tile.setdefault("source", {})
                tile["source"]["path"] = demo_tileset_path

        world = World()
        self._make_tilemap_entity(world, Tilemap.from_dict(tilemap_payload))

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_public_tilemap_command(render_system, world)
        tile_payload = command["chunk_data"]["tiles"][0]

        self.assertTrue(tile_payload["resolved"])
        self.assertEqual(tile_payload["resolution"], "grid")
        self.assertEqual(tile_payload["texture"]["path"], demo_tileset_path)
        self.assertEqual(tile_payload["source_rect"], {"x": 0, "y": 0, "width": 64, "height": 64})

    def test_tilemap_chunk_draw_uses_texture_subrects(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/grid_draw.png")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 2, "y": 3, "tile_id": "9"}]}],
            ),
            x=10.0,
            y=20.0,
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_private_tilemap_command(render_system, world)

        with patch.object(render_system, "_load_texture", return_value=SimpleNamespace(id=1)), patch("pyray.draw_texture_pro") as draw_texture_pro:
            render_system._draw_tilemap_chunk(command)

        draw_texture_pro.assert_called_once()
        _, source_rect, dest_rect, _, rotation, tint = draw_texture_pro.call_args.args
        self.assertEqual((source_rect.x, source_rect.y, source_rect.width, source_rect.height), (16.0, 16.0, 16.0, 16.0))
        self.assertEqual((dest_rect.x, dest_rect.y, dest_rect.width, dest_rect.height), (42.0, 68.0, 16.0, 16.0))
        self.assertEqual(rotation, 0.0)
        self.assertEqual(self._rgba_tuple(tint), (255, 255, 255, 255))

    def test_tilemap_chunk_materializes_target_and_composes_once(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/chunk_target.png")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0"}, {"x": 1, "y": 0, "tile_id": "1"}]}],
            ),
            x=10.0,
            y=20.0,
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_private_tilemap_command(render_system, world)
        target_texture = SimpleNamespace(width=32, height=16)
        target_handle = SimpleNamespace(width=32, height=16, render_texture=SimpleNamespace(texture=target_texture), dry_run=False)

        with (
            patch.object(render_system, "_load_texture", return_value=SimpleNamespace(id=1)),
            patch.object(render_system._render_targets, "get", side_effect=[None, target_handle]),
            patch.object(render_system._render_targets, "begin", return_value=target_handle) as begin_target,
            patch.object(render_system._render_targets, "end") as end_target,
            patch("pyray.draw_texture_pro") as draw_texture_pro,
        ):
            render_system._prepare_tilemap_chunk_targets({"passes": [{"commands": [command]}]})

            begin_target.assert_called_once()
            end_target.assert_called_once()
            self.assertEqual(draw_texture_pro.call_count, 2)
            self.assertFalse(command["render_target_dirty"])

            draw_texture_pro.reset_mock()
            render_system._draw_tilemap_chunk(command)

        draw_texture_pro.assert_called_once()
        texture, source_rect, dest_rect, _, rotation, tint = draw_texture_pro.call_args.args
        self.assertIs(texture, target_texture)
        self.assertEqual((source_rect.x, source_rect.y, source_rect.width, source_rect.height), (0.0, 0.0, 32.0, -16.0))
        self.assertEqual((dest_rect.x, dest_rect.y, dest_rect.width, dest_rect.height), (10.0, 20.0, 32.0, 16.0))
        self.assertEqual(rotation, 0.0)
        self.assertEqual(self._rgba_tuple(tint), (255, 255, 255, 255))

    def test_tilemap_chunk_renderer_helper_materializes_target_directly(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/helper_target.png")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0"}, {"x": 1, "y": 0, "tile_id": "1"}]}],
            ),
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        command = self._first_private_tilemap_command(render_system, world)
        render_targets = RenderTargetPool()
        target_texture = SimpleNamespace(width=32, height=16)
        target_handle = SimpleNamespace(width=32, height=16, render_texture=SimpleNamespace(texture=target_texture), dry_run=False)
        helper = TilemapChunkRenderer(render_targets, lambda _reference, _fallback_path: SimpleNamespace(id=1))

        with (
            patch.object(render_targets, "get", side_effect=[None, target_handle]),
            patch.object(render_targets, "begin", return_value=target_handle) as begin_target,
            patch.object(render_targets, "end") as end_target,
            patch("pyray.draw_texture_pro") as draw_texture_pro,
        ):
            helper.prepare_targets({"passes": [{"commands": [command]}]}, render_system._tilemap_chunk_cache)
            begin_target.assert_called_once()
            end_target.assert_called_once()
            self.assertEqual(draw_texture_pro.call_count, 2)
            self.assertEqual(helper.command_draw_call_count(command), 1)
            self.assertEqual(helper.tile_draw_call_count(command), 2)

    def test_tilemap_render_without_targets_reports_fallback_tile_draws(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/no_targets.png")

        world = World()
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0"}, {"x": 1, "y": 0, "tile_id": "1"}]}],
            ),
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)

        with (
            patch("pyray.is_window_ready", return_value=True),
            patch.object(render_system, "_load_texture", return_value=SimpleNamespace(id=1)),
            patch("pyray.draw_texture_pro") as draw_texture_pro,
        ):
            render_system.render(world, use_world_camera=False, allow_render_targets=False)

        stats = render_system.get_last_render_stats()
        self.assertEqual(draw_texture_pro.call_count, 2)
        self.assertEqual(stats["render_commands"], 1)
        self.assertEqual(stats["draw_calls"], 2)
        self.assertEqual(stats["tilemap_tile_draw_calls"], 2)
        self.assertEqual(stats["render_target_passes"], 0)
        self.assertEqual(stats["render_target_composites"], 0)

    def test_tilemap_chunk_draw_applies_transform_rotation_and_scale_without_rebuild(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/grid_transform.png")

        world = World()
        entity = self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 1, "y": 2, "tile_id": "9"}]}],
            ),
            x=10.0,
            y=20.0,
            rotation=90.0,
            scale_x=2.0,
            scale_y=3.0,
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        first_stats = render_system.profile_world(world)
        self.assertEqual(first_stats["tilemap_chunk_rebuilds"], 1)
        entity.get_component(Transform).rotation = 45.0
        entity.get_component(Transform).scale_x = 1.5
        world.touch()
        second_stats = render_system.profile_world(world)
        self.assertEqual(second_stats["tilemap_chunk_rebuilds"], 0)

        command = self._first_private_tilemap_command(render_system, world)
        entity.get_component(Transform).rotation = 90.0
        entity.get_component(Transform).scale_x = 2.0
        entity.get_component(Transform).scale_y = 3.0
        with patch.object(render_system, "_load_texture", return_value=SimpleNamespace(id=1)), patch("pyray.draw_texture_pro") as draw_texture_pro:
            render_system._draw_tilemap_chunk(command)

        _, _source_rect, dest_rect, _, rotation, _tint = draw_texture_pro.call_args.args
        self.assertAlmostEqual(dest_rect.x, -86.0)
        self.assertAlmostEqual(dest_rect.y, 52.0)
        self.assertEqual((dest_rect.width, dest_rect.height), (32.0, 48.0))
        self.assertEqual(rotation, 90.0)

    def test_tilemap_chunk_draw_mirrors_negative_scale_without_rebuild(self) -> None:
        project_service, _asset_service = self._create_temp_render_project()
        asset_path = self._copy_fixture_asset(project_service, "assets/test_spritesheet.png", "assets/tiles/grid_mirror.png")

        world = World()
        entity = self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                tileset_path=asset_path,
                tileset_tile_width=16,
                tileset_tile_height=16,
                tileset_columns=8,
                layers=[{"name": "Ground", "tiles": [{"x": 1, "y": 2, "tile_id": "9"}]}],
            ),
            x=10.0,
            y=20.0,
            scale_x=2.0,
            scale_y=3.0,
        )

        render_system = RenderSystem()
        render_system.set_project_service(project_service)
        first_stats = render_system.profile_world(world)
        self.assertEqual(first_stats["tilemap_chunk_rebuilds"], 1)
        entity.get_component(Transform).scale_x = -2.0
        entity.get_component(Transform).scale_y = -3.0
        world.touch()
        second_stats = render_system.profile_world(world)
        self.assertEqual(second_stats["tilemap_chunk_rebuilds"], 0)

        command = self._first_private_tilemap_command(render_system, world)
        with patch.object(render_system, "_load_texture", return_value=SimpleNamespace(id=1)), patch("pyray.draw_texture_pro") as draw_texture_pro:
            render_system._draw_tilemap_chunk(command)

        _, source_rect, dest_rect, _, rotation, _tint = draw_texture_pro.call_args.args
        self.assertEqual((source_rect.x, source_rect.y, source_rect.width, source_rect.height), (32.0, 32.0, -16.0, -16.0))
        self.assertEqual((dest_rect.x, dest_rect.y, dest_rect.width, dest_rect.height), (-54.0, -124.0, 32.0, 48.0))
        self.assertEqual(rotation, 0.0)


if __name__ == "__main__":
    unittest.main()
