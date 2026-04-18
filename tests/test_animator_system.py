import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.animator import (
    AnimationCondition,
    AnimationData,
    AnimationParameterDefinition,
    AnimationStateDefinition,
    AnimationStateMachine,
    AnimationTransition,
    Animator,
)
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.systems.animation_system import AnimationSystem


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

    def test_animation_system_applies_bool_transition(self) -> None:
        world = World()
        entity = world.create_entity("BoolTransitionTest")
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["idle_0"], fps=8.0, loop=True),
                "run": AnimationData(slice_names=["run_0"], fps=8.0, loop=True),
            },
            default_state="idle",
            parameters={
                "is_moving": AnimationParameterDefinition(type="bool", default=False),
            },
            state_machine=AnimationStateMachine(
                entry_state="idle",
                states={
                    "idle": AnimationStateDefinition(
                        transitions=[
                            AnimationTransition(
                                name="idle_to_run",
                                to="run",
                                conditions=[AnimationCondition(parameter="is_moving", operator="==", value=True)],
                                force_restart=True,
                            )
                        ]
                    )
                },
            ),
        )
        entity.add_component(animator)
        animator.set_parameter("is_moving", True)

        event_bus = EventBus()
        transition_events = []
        state_change_events = []
        event_bus.subscribe("on_animation_transition", lambda evt: transition_events.append(evt.data))
        event_bus.subscribe("on_state_changed", lambda evt: state_change_events.append(evt.data))

        system = AnimationSystem(event_bus)
        system.update(world, delta_time=0.1)

        self.assertEqual(animator.current_state, "run")
        self.assertEqual(len(transition_events), 1)
        self.assertEqual(transition_events[0]["transition_name"], "idle_to_run")
        self.assertEqual(len(state_change_events), 1)
        self.assertEqual(state_change_events[0]["from_state"], "idle")
        self.assertEqual(state_change_events[0]["to_state"], "run")

    def test_animation_system_applies_float_and_int_transitions(self) -> None:
        world = World()
        entity = world.create_entity("NumericTransitionTest")
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["idle_0"], fps=8.0, loop=True),
                "run": AnimationData(slice_names=["run_0"], fps=8.0, loop=True),
                "combo": AnimationData(slice_names=["combo_0"], fps=8.0, loop=True),
            },
            default_state="idle",
            parameters={
                "speed": AnimationParameterDefinition(type="float", default=0.0),
                "combo_step": AnimationParameterDefinition(type="int", default=0),
            },
            state_machine=AnimationStateMachine(
                entry_state="idle",
                states={
                    "idle": AnimationStateDefinition(
                        transitions=[
                            AnimationTransition(
                                to="run",
                                conditions=[AnimationCondition(parameter="speed", operator=">", value=0.5)],
                            )
                        ]
                    ),
                    "run": AnimationStateDefinition(
                        transitions=[
                            AnimationTransition(
                                to="combo",
                                conditions=[AnimationCondition(parameter="combo_step", operator=">=", value=2)],
                            )
                        ]
                    ),
                },
            ),
        )
        entity.add_component(animator)
        system = AnimationSystem()

        animator.set_parameter("speed", 1.25)
        system.update(world, delta_time=0.01)
        self.assertEqual(animator.current_state, "run")

        animator.set_parameter("combo_step", 2)
        system.update(world, delta_time=0.01)
        self.assertEqual(animator.current_state, "combo")

    def test_animation_system_consumes_trigger_transition(self) -> None:
        world = World()
        entity = world.create_entity("TriggerTransitionTest")
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["idle_0"], fps=8.0, loop=True),
                "attack": AnimationData(slice_names=["attack_0"], fps=8.0, loop=False),
            },
            default_state="idle",
            parameters={
                "attack": AnimationParameterDefinition(type="trigger", default=False),
            },
            state_machine=AnimationStateMachine(
                entry_state="idle",
                states={
                    "idle": AnimationStateDefinition(
                        transitions=[
                            AnimationTransition(
                                name="idle_to_attack",
                                to="attack",
                                conditions=[AnimationCondition(parameter="attack", operator="==", value=True)],
                                force_restart=True,
                            )
                        ]
                    )
                },
            ),
        )
        entity.add_component(animator)
        animator.set_trigger("attack")

        system = AnimationSystem()
        system.update(world, delta_time=0.01)

        self.assertEqual(animator.current_state, "attack")
        self.assertFalse(animator.get_parameter("attack"))

    def test_animation_system_applies_exit_time_transition_before_on_complete(self) -> None:
        world = World()
        entity = world.create_entity("ExitTimeTransitionTest")
        animator = Animator(
            animations={
                "attack": AnimationData(slice_names=["a0", "a1"], fps=2.0, loop=False, on_complete="run"),
                "idle": AnimationData(slice_names=["i0"], fps=8.0, loop=True),
                "run": AnimationData(slice_names=["r0"], fps=8.0, loop=True),
            },
            default_state="attack",
            state_machine=AnimationStateMachine(
                entry_state="attack",
                states={
                    "attack": AnimationStateDefinition(
                        transitions=[
                            AnimationTransition(
                                name="attack_to_idle",
                                to="idle",
                                has_exit_time=True,
                                exit_time=1.0,
                            )
                        ]
                    )
                },
            ),
        )
        entity.add_component(animator)

        event_bus = EventBus()
        transition_events = []
        end_events = []
        event_bus.subscribe("on_animation_transition", lambda evt: transition_events.append(evt.data))
        event_bus.subscribe("on_animation_end", lambda evt: end_events.append(evt.data))

        system = AnimationSystem(event_bus)
        system.update(world, delta_time=1.0)

        self.assertEqual(animator.current_state, "idle")
        self.assertEqual(len(transition_events), 1)
        self.assertEqual(transition_events[0]["transition_name"], "attack_to_idle")
        self.assertEqual(len(end_events), 1)
        self.assertEqual(end_events[0]["animation"], "attack")

    def test_animation_system_keeps_on_complete_compatibility_without_transition(self) -> None:
        world = World()
        entity = world.create_entity("OnCompleteCompatTest")
        animator = Animator(
            animations={
                "attack": AnimationData(slice_names=["a0", "a1"], fps=2.0, loop=False, on_complete="idle"),
                "idle": AnimationData(slice_names=["i0"], fps=8.0, loop=True),
            },
            default_state="attack",
        )
        entity.add_component(animator)

        event_bus = EventBus()
        state_change_events = []
        event_bus.subscribe("on_state_changed", lambda evt: state_change_events.append(evt.data))

        system = AnimationSystem(event_bus)
        system.update(world, delta_time=1.0)

        self.assertEqual(animator.current_state, "idle")
        self.assertEqual(len(state_change_events), 1)
        self.assertEqual(state_change_events[0]["from_state"], "attack")
        self.assertEqual(state_change_events[0]["to_state"], "idle")


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
