import unittest
from unittest.mock import patch

from cli.headless_game import HeadlessGame
from engine.app.runtime_controller import RuntimeController
from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.components.uibutton import UIButton
from engine.core.engine_state import EngineState
from engine.core.runtime_contracts import RuntimeControllerContext
from engine.ecs.world import World
from engine.physics.box2d_backend import Box2DDependencyUnavailable, Box2DPhysicsBackend
from engine.systems.render_system import RenderSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.ui_system import UISystem


class PerformanceInfraTests(unittest.TestCase):
    def _make_transform(self, x: float = 0.0, y: float = 0.0) -> Transform:
        return Transform(x=x, y=y, rotation=0.0, scale_x=1.0, scale_y=1.0)

    def test_world_indices_track_name_parent_and_component_lookup(self) -> None:
        world = World()
        parent = world.create_entity("Parent")
        parent.add_component(self._make_transform())
        child = world.create_entity("Child")
        child.add_component(self._make_transform())
        child.parent_name = "Parent"
        world.selected_entity_name = "Child"

        self.assertIs(world.get_entity_by_name("Child"), child)
        self.assertEqual([entity.name for entity in world.get_children("Parent")], ["Child"])
        self.assertEqual([entity.name for entity in world.get_entities_with(Transform)], ["Parent", "Child"])
        self.assertIs(world.get_entity_by_component_instance(child.get_component(Transform)), child)

        child.name = "ChildRenamed"
        self.assertIsNone(world.get_entity_by_name("Child"))
        self.assertIs(world.get_entity_by_name("ChildRenamed"), child)
        self.assertEqual(world.selected_entity_name, "ChildRenamed")

        child.remove_component(Transform)
        self.assertEqual([entity.name for entity in world.get_entities_with(Transform)], ["Parent"])

    def test_ui_layout_cache_reuses_layout_until_ui_layout_changes(self) -> None:
        world = World()
        canvas = world.create_entity("CanvasRoot")
        canvas.add_component(Canvas())
        canvas.add_component(RectTransform())
        button = world.create_entity("Button")
        button.parent_name = "CanvasRoot"
        button.add_component(
            RectTransform(
                anchor_min_x=0.5,
                anchor_min_y=0.5,
                anchor_max_x=0.5,
                anchor_max_y=0.5,
                pivot_x=0.5,
                pivot_y=0.5,
                width=200.0,
                height=80.0,
            )
        )
        button.add_component(UIButton(label="Play"))

        system = UISystem()

        with patch.object(system, "_layout_children", wraps=system._layout_children) as layout_children:
            system.update(world, (800.0, 600.0))
            first_call_count = layout_children.call_count
            system.update(world, (800.0, 600.0))
            self.assertEqual(layout_children.call_count, first_call_count)

            button.get_component(RectTransform).width = 220.0
            world.touch_ui_layout()
            system.update(world, (800.0, 600.0))
            self.assertGreater(layout_children.call_count, first_call_count)

        snapshot_ref = system.get_layout_snapshot(copy_result=False)
        snapshot_copy = system.get_layout_snapshot()
        self.assertIsNot(snapshot_ref, snapshot_copy)
        self.assertIn("Button", snapshot_ref)

    def test_render_entity_sort_cache_rebuilds_only_when_world_changes(self) -> None:
        world = World()
        first = world.create_entity("A")
        first.add_component(self._make_transform())
        first.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=0))
        second = world.create_entity("B")
        second.add_component(self._make_transform())
        second.add_component(RenderOrder2D(sorting_layer="Default", order_in_layer=10))
        second.add_component(Sprite(texture_path="", width=32, height=32))

        render_system = RenderSystem()

        first_sorted = render_system._sorted_render_entities(world)
        second_sorted = render_system._sorted_render_entities(world)
        self.assertIs(first_sorted, second_sorted)
        self.assertEqual([entity.name for entity in first_sorted], ["A", "B"])

        third = world.create_entity("C")
        third.add_component(self._make_transform())
        updated_sorted = render_system._sorted_render_entities(world)
        self.assertIsNot(updated_sorted, first_sorted)
        self.assertEqual([entity.name for entity in updated_sorted], ["A", "C", "B"])

    def test_tilemap_empty_tileset_resource_path_does_not_import_tileset_loader(self) -> None:
        tilemap = Tilemap()

        def fail_tileset_import(name, *args, **kwargs):
            if name == "engine.resources.tileset":
                raise AssertionError("tileset loader should not be imported without a resource path")
            return original_import(name, *args, **kwargs)

        original_import = __import__
        with patch("builtins.__import__", fail_tileset_import):
            self.assertIsNone(tilemap.get_tileset_resource())

    def test_physics_update_skips_world_scan_without_physics_components(self) -> None:
        world = World()
        for index in range(10):
            entity = world.create_entity(f"Entity_{index}")
            entity.add_component(self._make_transform())

        physics = PhysicsSystem()
        with patch.object(world, "iter_entities", side_effect=AssertionError("unexpected full world scan")):
            physics.update(world, 1.0 / 60.0)

        self.assertEqual(physics.get_step_metrics()["candidate_solids"], 0)

    def test_collision_update_skips_transform_scan_without_collision_components(self) -> None:
        world = World()
        for index in range(10):
            entity = world.create_entity(f"Entity_{index}")
            entity.add_component(self._make_transform())

        collision = CollisionSystem()
        with patch.object(world, "get_entities_with", side_effect=AssertionError("unexpected component scan")):
            collision.update(world)

        self.assertEqual(collision.get_step_metrics()["candidate_pairs"], 0)

    def test_box2d_sync_world_ignores_entities_without_colliders(self) -> None:
        try:
            backend = Box2DPhysicsBackend()
        except Box2DDependencyUnavailable:
            self.skipTest("Box2D dependency is unavailable")

        world = World()
        entity = world.create_entity("NoCollider")
        entity.add_component(self._make_transform())

        with patch.object(backend, "destroy_body", wraps=backend.destroy_body) as destroy_body:
            backend.sync_world(world)

        self.assertEqual(destroy_body.call_count, 0)

    def test_headless_game_keeps_profiler_without_editor_shell(self) -> None:
        game = HeadlessGame()
        try:
            self.assertFalse(game.editor_enabled)
            self.assertIsNone(game.editor_shell)
            game.enable_runtime_metrics = True
            game.reset_profiler(run_label="headless_smoke")
            game.step_frame(1.0 / 60.0)
            self.assertEqual(game.get_profiler_report()["frames"], 1)
        finally:
            game.request_shutdown()

    def test_runtime_gameplay_skips_empty_systems_for_transform_only_world(self) -> None:
        class UnexpectedRuntimeSystem:
            total_particle_count = 0

            def update(self, *args, **kwargs) -> None:
                raise AssertionError("unexpected runtime system update")

            def update_moving_platforms(self, *args, **kwargs) -> None:
                raise AssertionError("unexpected moving platform update")

            def update_enemy_patrols(self, *args, **kwargs) -> None:
                raise AssertionError("unexpected enemy patrol update")

        class UnexpectedPhysicsBackendRegistry:
            def resolve(self, *args, **kwargs):
                raise AssertionError("unexpected physics backend resolve")

        world = World()
        for index in range(10):
            entity = world.create_entity(f"Entity_{index}")
            entity.add_component(self._make_transform())

        unexpected = UnexpectedRuntimeSystem()
        controller = RuntimeController(
            RuntimeControllerContext(
                get_state=lambda: EngineState.PLAY,
                set_state=lambda _state: None,
                get_world=lambda: world,
                set_world=lambda _world: None,
                get_scene_runtime=lambda: None,
                get_rule_system=lambda: None,
                get_script_behaviour_system=lambda: unexpected,
                get_event_bus=lambda: None,
                get_animation_system=lambda: None,
                get_input_system=lambda: unexpected,
                get_mobile_controls_system=lambda: unexpected,
                get_player_controller_system=lambda: unexpected,
                get_character_controller_system=lambda: unexpected,
                get_physics_system=lambda: unexpected,
                get_collision_system=lambda: unexpected,
                get_audio_system=lambda: unexpected,
                get_timer_system=lambda: unexpected,
                get_tween_system=lambda: unexpected,
                get_visible_on_screen_system=lambda: unexpected,
                get_parallax_system=lambda: unexpected,
                get_resource_preloader_system=lambda: None,
                get_particle_system=lambda: unexpected,
                get_gpu_particles_system=lambda: unexpected,
                get_area2d_system=lambda: unexpected,
                get_path_follow_system=lambda: unexpected,
                get_gameplay2d_semantic_system=lambda: unexpected,
                get_navigation_agent_system=lambda: unexpected,
                get_raycast_2d_system=lambda: unexpected,
                get_scene_transition_controller=lambda: unexpected,
                get_physics_backend_registry=lambda: UnexpectedPhysicsBackendRegistry(),
                reset_profiler=lambda **_kwargs: None,
                set_physics_backend=lambda _backend, _name: None,
                edit_animation_speed=1.0,
            )
        )

        controller.update_gameplay(world, 1.0 / 60.0)


if __name__ == "__main__":
    unittest.main()
