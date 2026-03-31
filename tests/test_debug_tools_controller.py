import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pyray as rl

from engine.app.debug_tools_controller import DebugToolsController
from engine.components.transform import Transform
from engine.core.engine_state import EngineState
from engine.core.time_manager import TimeManager
from engine.debug.profiler import EngineProfiler
from engine.debug.timeline import Timeline
from engine.ecs.world import World
from engine.physics.registry import PhysicsBackendRegistry


class _FakeSceneManager:
    def __init__(self) -> None:
        self.active_world = None
        self.scene_name = "DebugScene"

    def restore_world(self, world) -> None:
        self.active_world = world


class _FakePerfWorld:
    def __init__(self) -> None:
        self.feature_metadata = {"physics_2d": {"backend": "stub_backend"}}

    def entity_count(self) -> int:
        return 6

    def get_entities_with(self, component_type):
        mapping = {
            "Canvas": [object()],
            "UIButton": [object(), object()],
            "ScriptBehaviour": [object(), object(), object()],
        }
        return list(mapping.get(component_type.__name__, []))

    def serialize(self) -> dict:
        return {"entities": [1, 2, 3], "rules": []}


class DebugToolsControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.time_manager = TimeManager()
        self.time_manager.update_manual(1.0 / 60.0)
        self.timeline = Timeline()
        self.profiler = EngineProfiler()
        self.hot_reload_manager = Mock()
        self.hot_reload_manager.check_for_changes.return_value = []
        self.hot_reload_manager.get_errors.return_value = []
        self.perf_stats = {
            "frame": 16.5,
            "render": 4.0,
            "inspector": 1.0,
            "hierarchy": 1.5,
            "ui": 2.0,
            "scripts": 3.0,
            "selection_gizmo": 0.75,
            "animation": 1.25,
            "gameplay": 2.5,
        }
        self.perf_counters: dict[str, int] = {}
        self.state = {"value": EngineState.PLAY}
        self.flags = {
            "show_overlay": False,
            "draw_colliders": False,
            "draw_labels": False,
        }
        self.world_holder = {"world": None}
        self.scene_manager = _FakeSceneManager()
        self.rule_system = Mock()
        self.render_system = Mock()
        self.render_system.get_last_render_stats.return_value = {
            "render_entities": 5,
            "draw_calls": 9,
            "batches": 3,
            "tilemap_chunks": 2,
            "tilemap_chunk_rebuilds": 1,
            "render_target_passes": 4,
        }
        self.backend = Mock()
        self.backend.backend_name = "stub_backend"
        self.backend.get_step_metrics.return_value = {"ccd_bodies": 8, "contacts": 7}
        self.physics_backend_registry = PhysicsBackendRegistry(default_backend_name="stub_backend")
        self.physics_backend_registry.register_backend(self.backend, backend_name="stub_backend")
        self.controller = DebugToolsController(
            time_manager=self.time_manager,
            timeline=self.timeline,
            profiler=self.profiler,
            hot_reload_manager=self.hot_reload_manager,
            perf_stats=self.perf_stats,
            perf_counters=self.perf_counters,
            get_state=lambda: self.state["value"],
            get_world=lambda: self.world_holder["world"],
            set_world=lambda world: self.world_holder.__setitem__("world", world),
            get_scene_manager=lambda: self.scene_manager,
            get_level_loader=lambda: None,
            get_rule_system=lambda: self.rule_system,
            get_collision_system=lambda: None,
            get_render_system=lambda: self.render_system,
            get_physics_backend_registry=lambda: self.physics_backend_registry,
            get_width=lambda: 1280,
            get_show_performance_overlay=lambda: self.flags["show_overlay"],
            set_show_performance_overlay=lambda value: self.flags.__setitem__("show_overlay", value),
            get_debug_draw_colliders=lambda: self.flags["draw_colliders"],
            set_debug_draw_colliders=lambda value: self.flags.__setitem__("draw_colliders", value),
            get_debug_draw_labels=lambda: self.flags["draw_labels"],
            set_debug_draw_labels=lambda value: self.flags.__setitem__("draw_labels", value),
        )

    def test_snapshot_round_trip_restores_world_and_rule_system(self) -> None:
        original_world = World()
        hero = original_world.create_entity("Hero")
        hero.add_component(Transform(x=24.0, y=48.0))
        self.world_holder["world"] = original_world

        self.controller.save_snapshot()
        self.world_holder["world"] = None

        self.controller.load_last_snapshot()

        restored_world = self.world_holder["world"]
        self.assertIsNotNone(restored_world)
        self.assertIs(restored_world, self.scene_manager.active_world)
        self.assertIsNot(restored_world, original_world)
        self.assertIsNotNone(restored_world.get_entity_by_name("Hero"))
        self.rule_system.set_world.assert_called_once_with(restored_world)

    def test_handle_debug_shortcuts_updates_debug_flags_and_render_options(self) -> None:
        pressed_keys: set[int] = set()
        down_keys: set[int] = set()

        with patch("pyray.is_key_pressed", side_effect=lambda key: key in pressed_keys), patch(
            "pyray.is_key_down", side_effect=lambda key: key in down_keys
        ):
            pressed_keys = {rl.KEY_F7}
            self.controller.handle_debug_shortcuts(
                step_callback=Mock(),
                toggle_fullscreen_callback=Mock(),
            )
            self.assertTrue(self.flags["draw_colliders"])
            self.render_system.set_debug_options.assert_called_with(draw_colliders=True)

            self.render_system.set_debug_options.reset_mock()
            pressed_keys = {rl.KEY_F7}
            down_keys = {rl.KEY_LEFT_CONTROL}
            self.controller.handle_debug_shortcuts(
                step_callback=Mock(),
                toggle_fullscreen_callback=Mock(),
            )
            self.assertTrue(self.flags["draw_labels"])
            self.render_system.set_debug_options.assert_called_with(draw_labels=True)

    def test_record_profiler_frame_preserves_backend_metrics_and_counters(self) -> None:
        self.controller.reset_profiler("controller-pass")
        world = _FakePerfWorld()

        self.controller.update_perf_counters(world)
        self.controller.record_profiler_frame(world, frame_time_ms=16.5)
        report = self.controller.get_profiler_report()

        self.assertEqual(report["run_label"], "controller-pass")
        self.assertEqual(report["frames"], 1)
        self.assertEqual(report["last_frame"]["backend"], "stub_backend")
        self.assertEqual(report["last_frame"]["backend_metrics"]["contacts"], 7)
        self.assertEqual(report["last_frame"]["counters"]["draw_calls"], 9)
        self.assertEqual(report["last_frame"]["counters"]["canvases"], 1)
        self.assertEqual(report["last_frame"]["counters"]["buttons"], 2)
        self.assertEqual(report["last_frame"]["counters"]["scripts"], 3)


if __name__ == "__main__":
    unittest.main()
