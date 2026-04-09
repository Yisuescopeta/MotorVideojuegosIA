import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.api import EngineAPI
from engine.components.animator import AnimationData, Animator
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.systems.animation_system import AnimationSystem
from engine.systems.render_system import RenderSystem


class _FakeSliceAssetService:
    def __init__(self, slices: dict[str, dict]) -> None:
        self._slices = slices

    def get_slice_rect(self, _reference, slice_name: str):
        return self._slices.get(slice_name)


class AnimationSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        self._previous_cwd = Path.cwd()
        self._change_cwd(self.project_root)
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self._temp_files = []

    def tearDown(self) -> None:
        self.api.shutdown()
        self._change_cwd(self._previous_cwd)
        self._temp_dir.cleanup()

    def _change_cwd(self, path: Path) -> None:
        import os
        os.chdir(path)

    def test_animation_system_speed_multiplier(self) -> None:
        world = World()
        entity = world.create_entity("SpeedTest")

        anim_data = AnimationData(
            slice_names=["a", "b", "c", "d"],
            fps=4.0,
            loop=True,
        )
        animator = Animator(
            animations={"test": anim_data},
            default_state="test",
            speed=2.0,
        )
        entity.add_component(animator)

        event_bus = EventBus()
        system = AnimationSystem(event_bus)
        system.set_event_bus(event_bus)

        system.update(world, delta_time=0.125)

        self.assertEqual(animator.current_frame, 1)
        self.assertAlmostEqual(animator.elapsed_time, 0.0, places=3)

    def test_animation_system_normalized_time(self) -> None:
        world = World()
        entity = world.create_entity("NormTimeTest")

        anim_data = AnimationData(
            slice_names=["a", "b", "c", "d"],
            fps=4.0,
            loop=True,
        )
        animator = Animator(
            animations={"test": anim_data},
            default_state="test",
        )
        entity.add_component(animator)

        system = AnimationSystem()

        system.update(world, delta_time=0.5)
        self.assertEqual(animator.current_frame, 2)
        self.assertAlmostEqual(animator.normalized_time, 0.666, places=2)

    def test_animation_system_state_changed_event(self) -> None:
        world = World()
        entity = world.create_entity("StateChangeTest")

        anim_idle = AnimationData(slice_names=["i"], fps=1.0, loop=False, on_complete="run")
        anim_run = AnimationData(slice_names=["r"], fps=1.0, loop=True)

        animator = Animator(
            animations={"idle": anim_idle, "run": anim_run},
            default_state="idle",
        )
        entity.add_component(animator)

        events_received = []
        event_bus = EventBus()
        event_bus.subscribe("on_state_changed", lambda evt: events_received.append(evt.data))
        event_bus.subscribe("on_animation_end", lambda evt: events_received.append(evt.data))

        system = AnimationSystem(event_bus)
        system.set_event_bus(event_bus)

        system.update(world, delta_time=1.5)
        self.assertTrue(len(events_received) >= 1)

    def test_animation_system_is_playing(self) -> None:
        world = World()
        entity = world.create_entity("IsPlayingTest")

        anim_data = AnimationData(slice_names=["a"], fps=1.0, loop=True)
        animator = Animator(animations={"test": anim_data}, default_state="test")
        entity.add_component(animator)

        self.assertTrue(animator.is_playing)

        animator.stop()
        self.assertFalse(animator.is_playing)

    def test_animator_from_dict_defaults_to_legacy_anchor_mode(self) -> None:
        animator = Animator.from_dict(
            {
                "enabled": True,
                "sprite_sheet": "test.png",
                "animations": {"idle": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True}},
                "default_state": "idle",
            }
        )

        self.assertEqual(animator.anchor_mode, "legacy_center")

    def test_selection_bounds_keep_slice_pivot_anchor_stable(self) -> None:
        world = World()
        entity = world.create_entity("PivotHero")
        entity.add_component(Transform(x=100.0, y=200.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(
            Animator(
                sprite_sheet="hero.png",
                animations={"idle": AnimationData(slice_names=["idle_small", "idle_big"], fps=6.0, loop=True)},
                default_state="idle",
                anchor_mode="slice_pivot",
            )
        )

        render_system = RenderSystem()
        render_system._asset_service = _FakeSliceAssetService(
            {
                "idle_small": {"x": 0, "y": 0, "width": 20, "height": 30, "pivot_x": 0.5, "pivot_y": 1.0},
                "idle_big": {"x": 20, "y": 0, "width": 36, "height": 48, "pivot_x": 0.5, "pivot_y": 1.0},
            }
        )
        animator = entity.get_component(Animator)
        self.assertIsNotNone(animator)

        bounds_small = render_system._selection_bounds(entity)
        animator.current_frame = 1
        bounds_big = render_system._selection_bounds(entity)

        self.assertIsNotNone(bounds_small)
        self.assertIsNotNone(bounds_big)
        self.assertAlmostEqual(bounds_small["left"] + (bounds_small["width"] * 0.5), 100.0, places=4)
        self.assertAlmostEqual(bounds_big["left"] + (bounds_big["width"] * 0.5), 100.0, places=4)
        self.assertAlmostEqual(bounds_small["top"] + bounds_small["height"], 200.0, places=4)
        self.assertAlmostEqual(bounds_big["top"] + bounds_big["height"], 200.0, places=4)

    def test_draw_animated_sprite_keeps_slice_pivot_anchor_stable_across_variable_sizes(self) -> None:
        transform = Transform(x=100.0, y=200.0, rotation=0.0, scale_x=1.0, scale_y=1.0)
        animator = Animator(
            sprite_sheet="hero.png",
            animations={"idle": AnimationData(slice_names=["idle_small", "idle_big"], fps=6.0, loop=True)},
            default_state="idle",
            anchor_mode="slice_pivot",
        )

        render_system = RenderSystem()
        render_system._asset_service = _FakeSliceAssetService(
            {
                "idle_small": {"x": 0, "y": 0, "width": 20, "height": 30, "pivot_x": 0.5, "pivot_y": 1.0},
                "idle_big": {"x": 20, "y": 0, "width": 36, "height": 48, "pivot_x": 0.5, "pivot_y": 1.0},
            }
        )
        render_system._load_texture = lambda *_args, **_kwargs: SimpleNamespace(id=1, width=128, height=128)

        draw_calls: list[dict[str, float]] = []

        def _capture_draw(_texture, _source, dest, _origin, _rotation, _tint) -> None:
            draw_calls.append(
                {
                    "x": float(dest.x),
                    "y": float(dest.y),
                    "width": float(dest.width),
                    "height": float(dest.height),
                }
            )

        with patch("engine.systems.render_system.rl.draw_texture_pro", side_effect=_capture_draw):
            render_system._draw_animated_sprite(transform, animator)
            animator.current_frame = 1
            render_system._draw_animated_sprite(transform, animator)

        self.assertEqual(len(draw_calls), 2)
        for payload in draw_calls:
            self.assertAlmostEqual(payload["x"] + (payload["width"] * 0.5), 100.0, places=4)
            self.assertAlmostEqual(payload["y"] + payload["height"], 200.0, places=4)

    def test_draw_animated_sprite_falls_back_to_legacy_center_without_slice_pivot_metadata(self) -> None:
        transform = Transform(x=64.0, y=96.0, rotation=0.0, scale_x=1.0, scale_y=1.0)
        animator = Animator(
            sprite_sheet="hero.png",
            animations={"idle": AnimationData(slice_names=["idle"], fps=6.0, loop=True)},
            default_state="idle",
            anchor_mode="slice_pivot",
        )

        render_system = RenderSystem()
        render_system._asset_service = _FakeSliceAssetService(
            {
                "idle": {"x": 0, "y": 0, "width": 20, "height": 30},
            }
        )
        render_system._load_texture = lambda *_args, **_kwargs: SimpleNamespace(id=1, width=128, height=128)

        draw_calls: list[dict[str, float]] = []

        def _capture_draw(_texture, _source, dest, _origin, _rotation, _tint) -> None:
            draw_calls.append(
                {
                    "x": float(dest.x),
                    "y": float(dest.y),
                    "width": float(dest.width),
                    "height": float(dest.height),
                }
            )

        with patch("engine.systems.render_system.rl.draw_texture_pro", side_effect=_capture_draw):
            render_system._draw_animated_sprite(transform, animator)

        self.assertEqual(len(draw_calls), 1)
        payload = draw_calls[0]
        self.assertAlmostEqual(payload["x"] + (payload["width"] * 0.5), 64.0, places=4)
        self.assertAlmostEqual(payload["y"] + (payload["height"] * 0.5), 96.0, places=4)

    def test_draw_and_selection_bounds_mirror_slice_pivot_when_flipped(self) -> None:
        world = World()
        entity = world.create_entity("FlipPivotHero")
        transform = Transform(x=100.0, y=200.0, rotation=0.0, scale_x=1.0, scale_y=1.0)
        entity.add_component(transform)
        animator = Animator(
            sprite_sheet="hero.png",
            animations={"idle": AnimationData(slice_names=["idle"], fps=6.0, loop=True)},
            default_state="idle",
            flip_x=True,
            flip_y=True,
            anchor_mode="slice_pivot",
        )
        entity.add_component(animator)

        render_system = RenderSystem()
        render_system._asset_service = _FakeSliceAssetService(
            {
                "idle": {"x": 0, "y": 0, "width": 40, "height": 20, "pivot_x": 0.25, "pivot_y": 0.75},
            }
        )
        render_system._load_texture = lambda *_args, **_kwargs: SimpleNamespace(id=1, width=128, height=128)

        draw_calls: list[dict[str, float]] = []

        def _capture_draw(_texture, _source, dest, _origin, _rotation, _tint) -> None:
            draw_calls.append(
                {
                    "x": float(dest.x),
                    "y": float(dest.y),
                    "width": float(dest.width),
                    "height": float(dest.height),
                }
            )

        with patch("engine.systems.render_system.rl.draw_texture_pro", side_effect=_capture_draw):
            render_system._draw_animated_sprite(transform, animator)

        self.assertEqual(len(draw_calls), 1)
        payload = draw_calls[0]
        self.assertAlmostEqual(payload["x"] + (payload["width"] * 0.75), 100.0, places=4)
        self.assertAlmostEqual(payload["y"] + (payload["height"] * 0.25), 200.0, places=4)

        bounds = render_system._selection_bounds(entity)
        self.assertIsNotNone(bounds)
        self.assertAlmostEqual(bounds["left"], payload["x"], places=4)
        self.assertAlmostEqual(bounds["top"], payload["y"], places=4)
        self.assertAlmostEqual(bounds["left"] + (bounds["width"] * 0.75), 100.0, places=4)
        self.assertAlmostEqual(bounds["top"] + (bounds["height"] * 0.25), 200.0, places=4)


class AuthoringAPIAnimatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        self._previous_cwd = Path.cwd()
        self._copy_repo_file("levels/demo_level.json")
        self._change_cwd(self.project_root)
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._change_cwd(self._previous_cwd)
        self._temp_dir.cleanup()

    def _change_cwd(self, path: Path) -> None:
        import os
        os.chdir(path)

    def _copy_repo_file(self, relative_path: str) -> Path:
        source = Path(__file__).resolve().parents[1] / relative_path
        target = self.project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def _create_animator_entity(self, name: str) -> None:
        self.api.create_entity(
            name,
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Animator": {
                    "enabled": True,
                    "sprite_sheet": "test.png",
                    "frame_width": 32,
                    "frame_height": 32,
                    "animations": {
                        "idle": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None},
                        "run": {"frames": [1], "slice_names": ["run_0"], "fps": 12.0, "loop": False, "on_complete": "idle"},
                    },
                    "default_state": "idle",
                    "current_state": "idle",
                    "current_frame": 0,
                    "is_finished": False,
                    "flip_x": False,
                    "flip_y": False,
                    "speed": 1.0,
                },
            },
        )

    def test_duplicate_animator_state(self) -> None:
        self._create_animator_entity("DupTest")

        result = self.api.duplicate_animator_state("DupTest", "idle")
        self.assertTrue(result["success"])

        animator = self.api.get_entity("DupTest")["components"]["Animator"]
        self.assertIn("idle_copy", animator["animations"])
        self.assertEqual(animator["animations"]["idle_copy"]["fps"], 8.0)

    def test_duplicate_animator_state_with_custom_name(self) -> None:
        self._create_animator_entity("DupTest2")

        result = self.api.duplicate_animator_state("DupTest2", "idle", "idle_fast")
        self.assertTrue(result["success"])

        animator = self.api.get_entity("DupTest2")["components"]["Animator"]
        self.assertIn("idle_fast", animator["animations"])

    def test_duplicate_animator_state_renames_on_complete_refs(self) -> None:
        self._create_animator_entity("DupTest3")

        result = self.api.duplicate_animator_state("DupTest3", "run", "dash")
        self.assertTrue(result["success"])

        animator = self.api.get_entity("DupTest3")["components"]["Animator"]
        self.assertEqual(animator["animations"]["dash"]["on_complete"], "idle")

    def test_rename_animator_state(self) -> None:
        self._create_animator_entity("RenameTest")

        result = self.api.rename_animator_state("RenameTest", "idle", "idle_alt")
        self.assertTrue(result["success"])

        animator = self.api.get_entity("RenameTest")["components"]["Animator"]
        self.assertIn("idle_alt", animator["animations"])
        self.assertNotIn("idle", animator["animations"])
        self.assertEqual(animator["default_state"], "idle_alt")

    def test_rename_animator_state_updates_on_complete_refs(self) -> None:
        self._create_animator_entity("RenameTest2")

        result = self.api.rename_animator_state("RenameTest2", "idle", "idle_new")
        self.assertTrue(result["success"])

        animator = self.api.get_entity("RenameTest2")["components"]["Animator"]
        self.assertEqual(animator["animations"]["run"]["on_complete"], "idle_new")

    def test_rename_animator_state_same_name(self) -> None:
        self._create_animator_entity("RenameTest3")

        result = self.api.rename_animator_state("RenameTest3", "idle", "idle")
        self.assertTrue(result["success"])

    def test_set_animator_flip(self) -> None:
        self._create_animator_entity("FlipTest")

        result = self.api.set_animator_flip("FlipTest", flip_x=True, flip_y=True)
        self.assertTrue(result["success"])

        animator = self.api.get_entity("FlipTest")["components"]["Animator"]
        self.assertTrue(animator["flip_x"])
        self.assertTrue(animator["flip_y"])

    def test_set_animator_flip_partial(self) -> None:
        self._create_animator_entity("FlipTest2")

        self.api.set_animator_flip("FlipTest2", flip_x=True, flip_y=True)
        result = self.api.set_animator_flip("FlipTest2", flip_x=False)
        self.assertTrue(result["success"])

        animator = self.api.get_entity("FlipTest2")["components"]["Animator"]
        self.assertFalse(animator["flip_x"])
        self.assertTrue(animator["flip_y"])

    def test_set_animator_speed(self) -> None:
        self._create_animator_entity("SpeedTest")

        result = self.api.set_animator_speed("SpeedTest", 2.5)
        self.assertTrue(result["success"])

        animator = self.api.get_entity("SpeedTest")["components"]["Animator"]
        self.assertEqual(animator["speed"], 2.5)

    def test_set_animator_speed_minimum(self) -> None:
        self._create_animator_entity("SpeedTest2")

        result = self.api.set_animator_speed("SpeedTest2", 0.0)
        self.assertTrue(result["success"])

        animator = self.api.get_entity("SpeedTest2")["components"]["Animator"]
        self.assertEqual(animator["speed"], 0.01)

    def test_set_animator_anchor_mode(self) -> None:
        self._create_animator_entity("AnchorModeTest")

        result = self.api.set_animator_anchor_mode("AnchorModeTest", "slice_pivot")

        self.assertTrue(result["success"])
        animator = self.api.get_entity("AnchorModeTest")["components"]["Animator"]
        self.assertEqual(animator["anchor_mode"], "slice_pivot")

    def test_animator_anchor_mode_persists_after_save_and_reload(self) -> None:
        self._create_animator_entity("AnchorPersist")

        result = self.api.set_animator_anchor_mode("AnchorPersist", "slice_pivot")
        self.assertTrue(result["success"])

        save_path = self.project_root / "levels" / "animator_anchor_roundtrip.json"
        save_result = self.api.save_scene(path=save_path.as_posix())
        self.assertTrue(save_result["success"])

        persisted = json.loads(save_path.read_text(encoding="utf-8"))
        saved_entity = next(entry for entry in persisted["entities"] if entry["name"] == "AnchorPersist")
        self.assertEqual(saved_entity["components"]["Animator"]["anchor_mode"], "slice_pivot")

        self.api.load_level(save_path.as_posix())
        animator = self.api.get_entity("AnchorPersist")["components"]["Animator"]
        self.assertEqual(animator["anchor_mode"], "slice_pivot")

    def test_get_animator_info(self) -> None:
        self._create_animator_entity("InfoTest")

        info = self.api.get_animator_info("InfoTest")
        self.assertTrue(info["exists"])
        self.assertEqual(info["default_state"], "idle")
        self.assertEqual(info["current_state"], "idle")
        self.assertEqual(info["flip_x"], False)
        self.assertEqual(info["flip_y"], False)
        self.assertEqual(info["speed"], 1.0)
        self.assertEqual(len(info["states"]), 2)

        state_names = {s["name"] for s in info["states"]}
        self.assertIn("idle", state_names)
        self.assertIn("run", state_names)

    def test_get_animator_info_nonexistent(self) -> None:
        info = self.api.get_animator_info("NonExistent")
        self.assertFalse(info["exists"])

    def test_get_animator_info_duration(self) -> None:
        self._create_animator_entity("DurationTest")

        info = self.api.get_animator_info("DurationTest")
        idle_state = next(s for s in info["states"] if s["name"] == "idle")
        self.assertEqual(idle_state["fps"], 8.0)
        self.assertEqual(idle_state["frame_count"], 1)
        self.assertAlmostEqual(idle_state["duration_seconds"], 0.125, places=2)

    def test_list_animator_states(self) -> None:
        self._create_animator_entity("ListTest")

        states = self.api.list_animator_states("ListTest")
        self.assertEqual(len(states), 2)
        state_names = {s["state_name"] for s in states}
        self.assertIn("idle", state_names)
        self.assertIn("run", state_names)

    def test_remove_animator_state_clears_on_complete_refs(self) -> None:
        self._create_animator_entity("RemoveTest")

        result = self.api.remove_animator_state("RemoveTest", "idle")
        self.assertTrue(result["success"])

        animator = self.api.get_entity("RemoveTest")["components"]["Animator"]
        self.assertNotIn("idle", animator["animations"])
        run_on_complete = animator["animations"]["run"].get("on_complete")
        self.assertIsNone(run_on_complete)


if __name__ == "__main__":
    unittest.main()
