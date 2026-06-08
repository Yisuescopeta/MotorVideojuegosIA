import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyray as rl
from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.components.camera2d import Camera2D
from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.polygon2d import Polygon2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.project.project_service import ProjectService
from engine.rendering.render_targets import RenderTargetPool
from engine.rendering.tilemap_chunk_renderer import TilemapChunkRenderer
from engine.systems.render_system import RenderBatchKey, RenderSystem
from engine.utils.viewport import resolve_effective_camera2d


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

    def _make_camera_entity(
        self,
        world: World,
        *,
        x: float = 50.0,
        y: float = 0.0,
        offset_x: float = 50.0,
        offset_y: float = 50.0,
    ):
        entity = world.create_entity("Camera")
        entity.add_component(Transform(x=x, y=y, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Camera2D(offset_x=offset_x, offset_y=offset_y, framing_mode="locked"))
        return entity

    @staticmethod
    def _make_runtime_camera(
        *,
        target_x: float,
        target_y: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        zoom: float = 1.0,
        rotation: float = 0.0,
    ) -> rl.Camera2D:
        camera = rl.Camera2D()
        camera.target = rl.Vector2(target_x, target_y)
        camera.offset = rl.Vector2(offset_x, offset_y)
        camera.zoom = zoom
        camera.rotation = rotation
        return camera

    def _create_temp_render_project(self) -> tuple[ProjectService, AssetService]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name) / "RenderProject"
        project_service = ProjectService(project_root.as_posix())
        return project_service, AssetService(project_service)

    def test_build_camera_from_world_applies_profile_override_target(self) -> None:
        world = World()
        camera_entity = self._make_camera_entity(world, x=0.0, y=0.0, offset_x=320.0, offset_y=180.0)
        camera_component = camera_entity.get_component(Camera2D)
        camera_component.profile_overrides = {
            "desktop_16_9": {
                "target_x": 120.0,
                "target_y": -40.0,
                "offset_x": 640.0,
                "offset_y": 360.0,
                "zoom": 1.5,
                "rotation": 5.0,
            }
        }

        camera = RenderSystem()._build_camera_from_world(
            world,
            viewport_size=(1280.0, 720.0),
            camera_profile_id="desktop_16_9",
        )

        self.assertIsNotNone(camera)
        self.assertEqual((camera.target.x, camera.target.y), (120.0, -40.0))
        self.assertEqual((camera.offset.x, camera.offset.y), (640.0, 360.0))
        self.assertEqual(camera.zoom, 1.5)
        self.assertEqual(camera.rotation, 5.0)

    def test_build_camera_from_world_applies_follow_profile_offset(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=200.0, y=100.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        camera_entity = self._make_camera_entity(world, x=0.0, y=0.0)
        camera_component = camera_entity.get_component(Camera2D)
        camera_component.follow_entity = "Player"
        camera_component.profile_overrides = {
            "mobile_portrait": {
                "target_offset_x": -20.0,
                "target_offset_y": 30.0,
            }
        }

        camera = RenderSystem()._build_camera_from_world(
            world,
            viewport_size=(390.0, 844.0),
            camera_profile_id="mobile_portrait",
        )

        self.assertIsNotNone(camera)
        self.assertEqual((camera.target.x, camera.target.y), (180.0, 130.0))

    def test_camera_debug_geometry_matches_effective_viewport_rect(self) -> None:
        world = World()
        camera_entity = self._make_camera_entity(world, x=0.0, y=0.0, offset_x=320.0, offset_y=180.0)
        camera_component = camera_entity.get_component(Camera2D)
        camera_component.profile_overrides = {
            "desktop_16_9": {
                "target_x": 120.0,
                "target_y": -40.0,
                "offset_x": 640.0,
                "offset_y": 360.0,
                "zoom": 2.0,
            }
        }

        geometry = RenderSystem()._build_camera_geometry(
            world,
            viewport_size=(1280.0, 720.0),
            camera_profile_id="desktop_16_9",
        )
        resolved = resolve_effective_camera2d(
            world,
            viewport_size=(1280.0, 720.0),
            camera_profile_id="desktop_16_9",
        )

        self.assertIsNotNone(geometry)
        self.assertIsNotNone(resolved)
        assert geometry is not None and resolved is not None
        self.assertEqual(geometry["x"], resolved.rect_left)
        self.assertEqual(geometry["y"], resolved.rect_top)
        self.assertEqual(geometry["width"], resolved.rect_width)
        self.assertEqual(geometry["height"], resolved.rect_height)

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

    def test_selection_change_does_not_invalidate_sorted_entities_cache(self) -> None:
        world = World()
        self._make_sprite_entity(world, "Hero", x=0.0)
        self._make_sprite_entity(world, "Enemy", x=10.0)

        render_system = RenderSystem()
        first_graph = render_system._build_render_graph(world)
        first_sort_cache = first_graph["totals"]["sort_cache"]

        world.selected_entity_name = "Hero"
        second_graph = render_system._build_render_graph(world)
        second_sort_cache = second_graph["totals"]["sort_cache"]

        self.assertEqual(first_sort_cache, {"hits": 0, "misses": 1})
        self.assertEqual(second_sort_cache, {"hits": 1, "misses": 1})

    def test_selection_change_invalidates_debug_selection_graph(self) -> None:
        world = World()
        self._make_sprite_entity(world, "Hero", x=0.0)
        render_system = RenderSystem()

        first_graph = render_system._public_graph(render_system._build_render_graph(world))
        first_debug_kinds = [command["debug_kind"] for command in first_graph["passes"][2]["commands"]]

        world.selected_entity_name = "Hero"
        second_graph = render_system._public_graph(render_system._build_render_graph(world))
        second_debug_kinds = [command["debug_kind"] for command in second_graph["passes"][2]["commands"]]

        self.assertNotIn("selection", first_debug_kinds)
        self.assertIn("selection", second_debug_kinds)

    def test_structure_change_invalidates_render_graph(self) -> None:
        world = World()
        self._make_sprite_entity(world, "Hero", x=0.0)
        render_system = RenderSystem()

        first_graph = render_system._public_graph(render_system._build_render_graph(world))
        self._make_sprite_entity(world, "Enemy", x=10.0)
        second_graph = render_system._public_graph(render_system._build_render_graph(world))

        self.assertEqual([command["entity_name"] for command in first_graph["passes"][0]["commands"]], ["Hero"])
        self.assertEqual([command["entity_name"] for command in second_graph["passes"][0]["commands"]], ["Hero", "Enemy"])

    def test_structure_change_invalidates_sorted_entities_cache(self) -> None:
        world = World()
        self._make_sprite_entity(world, "Hero", x=0.0)
        render_system = RenderSystem()

        first_entities = render_system._sorted_render_entities(world)
        self._make_sprite_entity(world, "Enemy", x=10.0)
        second_entities = render_system._sorted_render_entities(world)

        self.assertEqual([entity.name for entity in first_entities], ["Hero"])
        self.assertEqual([entity.name for entity in second_entities], ["Hero", "Enemy"])
        self.assertEqual(render_system._sort_cache_hits, 0)
        self.assertEqual(render_system._sort_cache_misses, 2)

    def test_transform_move_invalidates_render_graph_cache(self) -> None:
        world = World()
        self._make_camera_entity(world)
        self._make_sprite_entity(world, "Near", x=10.0)
        far = self._make_sprite_entity(world, "Far", x=300.0)
        render_system = RenderSystem()

        first_graph = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))
        far_transform = far.get_component(Transform)
        self.assertIsNotNone(far_transform)
        far_transform.x = 20.0
        world.touch_transform()
        second_graph = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))

        self.assertEqual([command["entity_name"] for command in first_graph["passes"][0]["commands"]], ["Camera", "Near"])
        self.assertEqual([command["entity_name"] for command in second_graph["passes"][0]["commands"]], ["Camera", "Near", "Far"])

    def test_render_cache_keys_fallback_to_version_for_legacy_worlds(self) -> None:
        class LegacyWorldProxy:
            def __init__(self, wrapped: World) -> None:
                self._wrapped = wrapped

            @property
            def version(self) -> int:
                return self._wrapped.version

            @property
            def selection_version(self) -> int:
                return self._wrapped.selection_version

            @property
            def selected_entity_name(self) -> str | None:
                return self._wrapped.selected_entity_name

            @property
            def feature_metadata(self) -> dict:
                return self._wrapped.feature_metadata

            def get_entities_with(self, *component_types: type):
                return self._wrapped.get_entities_with(*component_types)

            def get_entity_by_name(self, name: str):
                return self._wrapped.get_entity_by_name(name)

        world = World()
        self._make_sprite_entity(world, "Hero", x=0.0)
        legacy_world = LegacyWorldProxy(world)
        render_system = RenderSystem()

        render_system._sorted_render_entities(legacy_world)
        render_system._sorted_render_entities(legacy_world)
        self.assertEqual(render_system._sort_cache_hits, 1)
        self.assertEqual(render_system._sort_cache_misses, 1)

        world.touch()
        render_system._sorted_render_entities(legacy_world)
        self.assertEqual(render_system._sort_cache_hits, 1)
        self.assertEqual(render_system._sort_cache_misses, 2)

        graph = render_system._public_graph(render_system._build_render_graph(legacy_world))
        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["Hero"])

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
        self.assertEqual(graph["totals"]["draw_calls"], 4)
        self.assertEqual(graph["totals"]["sprite_batches"], 4)
        self.assertEqual(graph["totals"]["batched_sprites"], 5)
        self.assertEqual(graph["totals"]["sprite_batch_fallbacks"], 0)

    def test_simple_sprite_batch_emits_one_rlgl_quad_batch(self) -> None:
        world = World()
        self._make_sprite_entity(world, "A", x=0.0)
        self._make_sprite_entity(world, "B", x=32.0)
        render_system = RenderSystem()
        commands = render_system._build_render_graph(world)["passes"][0]["commands"]
        texture = SimpleNamespace(id=7, width=64, height=64)

        with (
            patch.object(render_system, "_load_texture", return_value=texture),
            patch.object(render_system, "_render_entity") as render_entity,
            patch("pyray.rl_set_texture") as set_texture,
            patch("pyray.rl_begin") as begin,
            patch("pyray.rl_end") as end,
            patch("pyray.rl_color4ub") as color,
            patch("pyray.rl_tex_coord2f") as tex_coord,
            patch("pyray.rl_vertex2f") as vertex,
            patch("pyray.draw_texture_pro") as draw_texture,
        ):
            render_system._execute_render_commands(commands)

        begin.assert_called_once_with(rl.RL_QUADS)
        end.assert_called_once()
        self.assertEqual(set_texture.call_args_list[-1].args, (0,))
        self.assertEqual(color.call_count, 2)
        self.assertEqual(tex_coord.call_count, 8)
        self.assertEqual(vertex.call_count, 8)
        render_entity.assert_not_called()
        draw_texture.assert_not_called()

    def test_sprite_batch_item_preserves_geometry_uv_flip_tint_and_slice(self) -> None:
        world = World()
        entity = self._make_sprite_entity(world, "Slice", x=100.0)
        transform = entity.get_component(Transform)
        transform.y = 50.0
        transform.scale_x = 2.0
        transform.scale_y = 3.0
        sprite = entity.get_component(Sprite)
        sprite.width = 20
        sprite.height = 10
        sprite.origin_x = 0.25
        sprite.origin_y = 0.5
        sprite.flip_x = True
        sprite.tint = (10, 20, 30, 40)
        sprite.source_slice = "piece"

        render_system = RenderSystem()
        render_system._asset_service = SimpleNamespace(
            get_slice_rect=lambda *_args: {"x": 10, "y": 20, "width": 30, "height": 40}
        )
        command = render_system._build_render_graph(world)["passes"][0]["commands"][0]
        texture = SimpleNamespace(id=9, width=128, height=64)

        with patch.object(render_system, "_load_texture", return_value=texture):
            item = render_system._build_sprite_batch_item(command)

        self.assertIsNotNone(item)
        self.assertEqual((item.left, item.top, item.right, item.bottom), (90.0, 35.0, 130.0, 65.0))
        self.assertEqual((item.u_left, item.u_right), (40 / 128, 10 / 128))
        self.assertEqual((item.v_top, item.v_bottom), (20 / 64, 60 / 64))
        self.assertEqual(item.tint, (10, 20, 30, 40))

    def test_sprite_batch_fallbacks_cover_rotation_animation_polygon_texture_and_api(self) -> None:
        cases = ("rotation", "animator", "polygon", "invalid_texture", "missing_api")
        for case in cases:
            with self.subTest(case=case):
                world = World()
                entity = self._make_sprite_entity(world, "Fallback", x=0.0)
                if case == "rotation":
                    entity.get_component(Transform).rotation = 15.0
                elif case == "animator":
                    entity.add_component(Animator(sprite_sheet="assets/animated.png"))
                elif case == "polygon":
                    entity.add_component(Polygon2D(points=[[0, 0], [1, 0], [0, 1]]))

                render_system = RenderSystem()
                command = render_system._build_render_graph(world)["passes"][0]["commands"][0]
                texture = (
                    SimpleNamespace(id=0, width=0, height=0)
                    if case == "invalid_texture"
                    else SimpleNamespace(id=3, width=32, height=32)
                )
                api_available = case != "missing_api"
                with (
                    patch.object(render_system, "_load_texture", return_value=texture),
                    patch.object(render_system, "_sprite_batch_api_available", return_value=api_available),
                    patch.object(render_system, "_draw_sprite_batch") as draw_batch,
                    patch.object(render_system, "_render_entity") as render_entity,
                ):
                    render_system._execute_render_commands([command])

                draw_batch.assert_not_called()
                render_entity.assert_called_once()

    def test_sprite_batch_flushes_around_non_batchable_command_without_reordering(self) -> None:
        world = World()
        self._make_sprite_entity(world, "A", x=0.0)
        middle = self._make_sprite_entity(world, "B", x=32.0)
        middle.get_component(Transform).rotation = 5.0
        self._make_sprite_entity(world, "C", x=64.0)
        render_system = RenderSystem()
        commands = render_system._build_render_graph(world)["passes"][0]["commands"]
        events: list[str] = []

        def draw_batch(_texture, items):
            events.append("batch:" + ",".join(item.entity.name for item in items))
            return True

        def draw_fallback(entity, _transform):
            events.append("fallback:" + entity.name)

        with (
            patch.object(
                render_system,
                "_load_texture",
                return_value=SimpleNamespace(id=4, width=32, height=32),
            ),
            patch.object(render_system, "_draw_sprite_batch", side_effect=draw_batch),
            patch.object(render_system, "_render_entity", side_effect=draw_fallback),
        ):
            render_system._execute_render_commands(commands)

        self.assertEqual(events, ["batch:A", "fallback:B", "batch:C"])

    def test_render_stats_public_graph_and_internal_batch_keys_stay_compatible(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay", "Foreground"]}}
        self._make_sprite_entity(world, "A", x=0.0, sorting_layer="Gameplay", texture_path="assets/atlas_a.png")
        self._make_sprite_entity(world, "B", x=10.0, sorting_layer="Gameplay", texture_path="assets/atlas_a.png")
        self._make_sprite_entity(world, "C", x=20.0, sorting_layer="Gameplay", texture_path="assets/atlas_b.png")
        self._make_sprite_entity(world, "Hud", x=30.0, sorting_layer="Foreground", render_pass="Overlay")
        self._make_tilemap_entity(
            world,
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0"}]}],
            ),
            sorting_layer="Default",
        )
        world.selected_entity_name = "A"

        render_system = RenderSystem()
        internal_graph = render_system._build_render_graph(world)
        public_graph = render_system.get_last_render_graph()

        expected_totals = {
            "render_entities": 4,
            "render_commands": 6,
            "draw_calls": 4,
            "batches": 5,
            "state_changes": 2,
            "sprite_batches": 3,
            "batched_sprites": 4,
            "sprite_batch_fallbacks": 0,
            "tilemap_chunks": 1,
            "tilemap_total_chunks": 1,
            "tilemap_visible_chunks": 1,
            "tilemap_tile_draw_calls": 0,
            "tilemap_chunk_rebuilds": 1,
            "pass_count": 3,
            "render_target_passes": 0,
            "render_target_composites": 0,
            "spatial_culling_enabled": False,
            "spatial_total_entities": 5,
            "spatial_visible_entities": 5,
            "sort_cache": {"hits": 0, "misses": 1},
            "passes": {
                "World": {
                    "render_entities": 3,
                    "render_commands": 4,
                    "draw_calls": 2,
                    "tilemap_tile_draw_calls": 0,
                    "batches": 3,
                    "state_changes": 2,
                    "sprite_batches": 2,
                    "batched_sprites": 3,
                    "sprite_batch_fallbacks": 0,
                },
                "Overlay": {
                    "render_entities": 1,
                    "render_commands": 1,
                    "draw_calls": 1,
                    "tilemap_tile_draw_calls": 0,
                    "batches": 1,
                    "state_changes": 0,
                    "sprite_batches": 1,
                    "batched_sprites": 1,
                    "sprite_batch_fallbacks": 0,
                },
                "Debug": {
                    "render_entities": 0,
                    "render_commands": 1,
                    "draw_calls": 1,
                    "tilemap_tile_draw_calls": 0,
                    "batches": 1,
                    "state_changes": 0,
                    "sprite_batches": 0,
                    "batched_sprites": 0,
                    "sprite_batch_fallbacks": 0,
                },
            },
        }

        self.assertEqual(public_graph["totals"], expected_totals)
        self.assertIsInstance(public_graph["passes"][0]["commands"][0], dict)
        self.assertIsInstance(public_graph["passes"][0]["commands"][0]["batch_key"], dict)
        self.assertIsInstance(public_graph["passes"][0]["batches"][0]["key"], dict)

        first_internal_batch_key = internal_graph["passes"][0]["batches"][0]["key"]
        self.assertIsInstance(first_internal_batch_key, RenderBatchKey)
        self.assertIsInstance(first_internal_batch_key, tuple)
        self.assertNotIsInstance(first_internal_batch_key, dict)
        with self.assertRaises(AttributeError):
            first_internal_batch_key.atlas_id = "mutated"

    def test_spatial_culling_limits_render_commands_to_camera_bounds(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay"]}}
        self._make_camera_entity(world)
        self._make_sprite_entity(world, "Near", x=10.0, sorting_layer="Gameplay")
        self._make_sprite_entity(world, "Far", x=300.0, sorting_layer="Gameplay")

        render_system = RenderSystem()
        graph = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))

        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["Camera", "Near"])
        self.assertTrue(graph["totals"]["spatial_culling_enabled"])
        self.assertLess(graph["totals"]["spatial_visible_entities"], graph["totals"]["spatial_total_entities"])

    def test_spatial_camera_bounds_use_external_camera_transform(self) -> None:
        render_system = RenderSystem()
        camera = self._make_runtime_camera(
            target_x=100.0,
            target_y=50.0,
            offset_x=50.0,
            offset_y=25.0,
            zoom=2.0,
            rotation=90.0,
        )

        bounds = render_system._resolve_spatial_camera_bounds(
            World(),
            (100.0, 50.0),
            (100, 50),
            culling_camera=camera,
        )

        self.assertIsNotNone(bounds)
        assert bounds is not None
        self.assertAlmostEqual(bounds[0], 87.5)
        self.assertAlmostEqual(bounds[1], 25.0)
        self.assertAlmostEqual(bounds[2], 112.5)
        self.assertAlmostEqual(bounds[3], 75.0)

    def test_external_culling_camera_takes_priority_over_world_camera(self) -> None:
        world = World()
        self._make_camera_entity(world, x=0.0, offset_x=50.0, offset_y=50.0)
        self._make_sprite_entity(world, "WorldVisible", x=0.0)
        self._make_sprite_entity(world, "EditorVisible", x=300.0)
        editor_camera = self._make_runtime_camera(target_x=300.0, offset_x=50.0, offset_y=50.0)

        render_system = RenderSystem()
        graph = render_system._public_graph(
            render_system._build_render_graph(
                world,
                viewport_size=(100.0, 100.0),
                culling_camera=editor_camera,
            )
        )

        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["EditorVisible"])

    def test_render_propagates_override_camera_to_frame_plan(self) -> None:
        world = World()
        editor_camera = self._make_runtime_camera(target_x=300.0)
        render_system = RenderSystem()

        with patch.object(render_system, "_build_frame_plan", wraps=render_system._build_frame_plan) as build_frame_plan:
            render_system.render(
                world,
                override_camera=editor_camera,
                use_world_camera=False,
                viewport_size=(100.0, 100.0),
                allow_render_targets=False,
            )

        self.assertIs(build_frame_plan.call_args.kwargs["culling_camera"], editor_camera)

    def test_external_culling_camera_remains_source_when_viewport_changes(self) -> None:
        world = World()
        self._make_camera_entity(world, x=0.0, offset_x=50.0, offset_y=50.0)
        self._make_sprite_entity(world, "WorldVisible", x=0.0)
        self._make_sprite_entity(world, "EditorNear", x=300.0)
        self._make_sprite_entity(world, "EditorWide", x=390.0)
        editor_camera = self._make_runtime_camera(target_x=300.0, offset_x=50.0, offset_y=50.0)
        render_system = RenderSystem()

        small = render_system._public_graph(
            render_system._build_render_graph(
                world,
                viewport_size=(100.0, 100.0),
                culling_camera=editor_camera,
            )
        )
        wide = render_system._public_graph(
            render_system._build_render_graph(
                world,
                viewport_size=(240.0, 100.0),
                culling_camera=editor_camera,
            )
        )

        self.assertEqual([command["entity_name"] for command in small["passes"][0]["commands"]], ["EditorNear"])
        self.assertEqual(
            [command["entity_name"] for command in wide["passes"][0]["commands"]],
            ["EditorNear", "EditorWide"],
        )

    def test_spatial_culling_keeps_transform_only_entities_inside_camera_bounds(self) -> None:
        world = World()
        self._make_camera_entity(world)
        marker = world.create_entity("Marker")
        marker.add_component(Transform(x=10.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))

        render_system = RenderSystem()
        graph = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))

        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["Camera", "Marker"])
        self.assertTrue(graph["totals"]["spatial_culling_enabled"])
        self.assertEqual(graph["totals"]["spatial_total_entities"], 2)
        self.assertEqual(graph["totals"]["spatial_visible_entities"], 2)

    def test_spatial_culling_filters_transform_only_entities_outside_camera_bounds(self) -> None:
        world = World()
        self._make_camera_entity(world)
        marker = world.create_entity("Marker")
        marker.add_component(Transform(x=300.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))

        render_system = RenderSystem()
        graph = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))

        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["Camera"])
        self.assertTrue(graph["totals"]["spatial_culling_enabled"])
        self.assertEqual(graph["totals"]["spatial_total_entities"], 2)
        self.assertEqual(graph["totals"]["spatial_visible_entities"], 1)

    def test_spatial_culling_falls_back_without_camera(self) -> None:
        world = World()
        self._make_sprite_entity(world, "Near", x=10.0)
        self._make_sprite_entity(world, "Far", x=300.0)

        render_system = RenderSystem()
        stats = render_system.profile_world(world, viewport_size=(100.0, 100.0))

        self.assertFalse(stats["spatial_culling_enabled"])
        self.assertEqual(stats["render_entities"], 2)

    def test_spatial_culling_can_be_disabled(self) -> None:
        world = World()
        self._make_camera_entity(world)
        self._make_sprite_entity(world, "Near", x=10.0)
        self._make_sprite_entity(world, "Far", x=300.0)

        render_system = RenderSystem()
        render_system.set_spatial_culling_enabled(False)
        stats = render_system.profile_world(world, viewport_size=(100.0, 100.0))

        self.assertFalse(stats["spatial_culling_enabled"])
        self.assertEqual(stats["render_entities"], 3)

    def test_spatial_culling_preserves_render_sort_order_for_visible_entities(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default", "Gameplay", "Foreground"]}}
        self._make_camera_entity(world)
        self._make_sprite_entity(world, "Gameplay", x=20.0, sorting_layer="Gameplay", order_in_layer=5)
        self._make_sprite_entity(world, "Ground", x=20.0, sorting_layer="Default", order_in_layer=0)
        self._make_sprite_entity(world, "Foreground", x=20.0, sorting_layer="Foreground", order_in_layer=0)
        self._make_sprite_entity(world, "Outside", x=300.0, sorting_layer="Default", order_in_layer=-10)

        render_system = RenderSystem()
        graph = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))

        self.assertEqual([command["entity_name"] for command in graph["passes"][0]["commands"]], ["Camera", "Ground", "Gameplay", "Foreground"])

    def test_spatial_culling_cache_key_tracks_viewport_and_flag(self) -> None:
        world = World()
        self._make_camera_entity(world)
        self._make_sprite_entity(world, "Near", x=10.0)
        self._make_sprite_entity(world, "Far", x=140.0)

        render_system = RenderSystem()
        small = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))
        large = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(240.0, 100.0)))
        render_system.set_spatial_culling_enabled(False)
        disabled = render_system._public_graph(render_system._build_render_graph(world, viewport_size=(100.0, 100.0)))

        self.assertEqual([command["entity_name"] for command in small["passes"][0]["commands"]], ["Camera", "Near"])
        self.assertEqual([command["entity_name"] for command in large["passes"][0]["commands"]], ["Camera", "Near", "Far"])
        self.assertEqual([command["entity_name"] for command in disabled["passes"][0]["commands"]], ["Camera", "Near", "Far"])

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
        self.assertEqual(stats["draw_calls"], 5)
        self.assertEqual(stats["batches"], 1)
        self.assertEqual(stats["sprite_batches"], 5)
        self.assertEqual(stats["batched_sprites"], 5000)
        self.assertEqual(stats["sprite_batch_fallbacks"], 0)
        self.assertEqual(stats["passes"]["World"]["batches"], 1)
        self.assertEqual(stats["passes"]["World"]["render_commands"], 5000)
        self.assertEqual(stats["passes"]["World"]["draw_calls"], 5)

    def test_debug_graph_includes_joint_commands_when_debug_overlay_is_enabled(self) -> None:
        world = World()
        world.feature_metadata = {"render_2d": {"sorting_layers": ["Default"]}}
        anchor = world.create_entity("Anchor")
        anchor.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        jointed = world.create_entity("Pendulum")
        jointed.add_component(Transform(x=10.0, y=10.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        j2d = Joint2D()
        j2d.joint_type = "distance"
        j2d.connected_entity = "Anchor"
        j2d.rest_length = 14.0
        jointed.add_component(j2d)

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
        world._touch_component_specific(Tilemap)
        third_stats = render_system.profile_world(world)
        self.assertEqual(third_stats["tilemap_chunks"], 2)
        self.assertEqual(third_stats["tilemap_chunk_rebuilds"], 1)

    def test_tilemap_render_graph_uses_precomputed_runtime_chunks(self) -> None:
        world = World()
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}, {"x": 20, "y": 0, "tile_id": "stone"}]}],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        with patch.object(render_system, "_partition_tilemap_layer", side_effect=AssertionError("legacy partition should not run")):
            stats = render_system.profile_world(world)

        self.assertEqual(stats["tilemap_chunks"], 2)
        self.assertEqual(stats["tilemap_chunk_rebuilds"], 2)

    def test_tilemap_render_graph_culls_chunks_to_camera_bounds(self) -> None:
        world = World()
        self._make_camera_entity(world)
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}, {"x": 20, "y": 0, "tile_id": "stone"}]}],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        stats = render_system.profile_world(world, viewport_size=(100.0, 100.0))

        self.assertEqual(stats["tilemap_total_chunks"], 2)
        self.assertEqual(stats["tilemap_visible_chunks"], 1)
        self.assertEqual(stats["tilemap_chunks"], 1)
        self.assertEqual(stats["render_commands"], 2)

    def test_tilemap_render_graph_culls_chunks_with_external_camera(self) -> None:
        world = World()
        self._make_camera_entity(world, x=0.0, offset_x=50.0, offset_y=50.0)
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}, {"x": 20, "y": 0, "tile_id": "stone"}]}],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))
        editor_camera = self._make_runtime_camera(target_x=320.0, offset_x=50.0, offset_y=50.0)

        render_system = RenderSystem()
        graph = render_system._build_render_graph(
            world,
            viewport_size=(100.0, 100.0),
            culling_camera=editor_camera,
        )

        self.assertEqual(graph["totals"]["tilemap_total_chunks"], 2)
        self.assertEqual(graph["totals"]["tilemap_visible_chunks"], 1)
        tilemap_commands = [
            command
            for render_pass in graph["passes"]
            for command in render_pass["commands"]
            if command.kind == "tilemap_chunk"
        ]
        self.assertEqual(len(tilemap_commands), 1)
        self.assertEqual(tilemap_commands[0].chunk_id, "Ground/1,0")

    def test_tilemap_render_graph_without_camera_keeps_all_chunks(self) -> None:
        world = World()
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}, {"x": 20, "y": 0, "tile_id": "stone"}]}],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        stats = render_system.profile_world(world, viewport_size=(100.0, 100.0))

        self.assertEqual(stats["tilemap_total_chunks"], 2)
        self.assertEqual(stats["tilemap_visible_chunks"], 2)
        self.assertEqual(stats["tilemap_chunks"], 2)

    def test_tilemap_debug_chunk_draw_keeps_all_chunks(self) -> None:
        world = World()
        self._make_camera_entity(world)
        tilemap_entity = world.create_entity("Map")
        tilemap_entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        tilemap_entity.add_component(
            Tilemap(
                cell_width=16,
                cell_height=16,
                layers=[{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}, {"x": 20, "y": 0, "tile_id": "stone"}]}],
            )
        )
        tilemap_entity.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0, render_pass="World"))

        render_system = RenderSystem()
        render_system.set_debug_options(draw_tile_chunks=True)
        stats = render_system.profile_world(world, viewport_size=(100.0, 100.0))

        self.assertEqual(stats["tilemap_total_chunks"], 2)
        self.assertEqual(stats["tilemap_visible_chunks"], 2)
        self.assertEqual(stats["tilemap_chunks"], 2)

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
