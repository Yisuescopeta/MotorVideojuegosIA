import unittest

from engine.components.animator import (
    AnimationCondition,
    AnimationData,
    AnimationParameterDefinition,
    AnimationStateDefinition,
    AnimationStateMachine,
    AnimationTransition,
    Animator,
)


class AnimatorComponentTests(unittest.TestCase):
    def test_animator_default_values(self) -> None:
        animator = Animator()
        self.assertEqual(animator.default_state, "idle")
        self.assertEqual(animator.current_state, "idle")
        self.assertEqual(animator.current_frame, 0)
        self.assertEqual(animator.elapsed_time, 0.0)
        self.assertFalse(animator.is_finished)
        self.assertTrue(animator.enabled)
        self.assertFalse(animator.flip_x)
        self.assertFalse(animator.flip_y)
        self.assertEqual(animator.speed, 1.0)

    def test_animator_flip_y_and_speed_initialization(self) -> None:
        animator = Animator(flip_y=True, speed=2.0)
        self.assertTrue(animator.flip_y)
        self.assertEqual(animator.speed, 2.0)

    def test_animator_speed_minimum(self) -> None:
        animator = Animator(speed=0.0)
        self.assertEqual(animator.speed, 0.01)
        animator = Animator(speed=-5.0)
        self.assertEqual(animator.speed, 0.01)

    def test_animator_play_returns_previous_state(self) -> None:
        animator = Animator(animations={"idle": AnimationData(), "run": AnimationData()})
        prev = animator.play("run")
        self.assertEqual(prev, "idle")
        self.assertEqual(animator.current_state, "run")

    def test_animator_play_same_state_no_force_restart(self) -> None:
        animator = Animator(animations={"idle": AnimationData()})
        animator.current_frame = 5
        animator.elapsed_time = 1.0
        prev = animator.play("idle")
        self.assertEqual(prev, "idle")
        self.assertEqual(animator.current_frame, 5)
        self.assertEqual(animator.elapsed_time, 1.0)

    def test_animator_play_force_restart(self) -> None:
        animator = Animator(animations={"idle": AnimationData()})
        animator.current_frame = 5
        animator.elapsed_time = 1.0
        prev = animator.play("idle", force_restart=True)
        self.assertEqual(prev, "idle")
        self.assertEqual(animator.current_frame, 0)
        self.assertEqual(animator.elapsed_time, 0.0)

    def test_animator_play_nonexistent_state(self) -> None:
        animator = Animator(animations={"idle": AnimationData()})
        prev = animator.play("nonexistent")
        self.assertEqual(prev, "idle")
        self.assertEqual(animator.current_state, "idle")

    def test_animator_stop(self) -> None:
        animator = Animator(animations={"idle": AnimationData()})
        animator.is_finished = False
        animator.stop()
        self.assertTrue(animator.is_finished)

    def test_animator_resume_from_finished_non_loop(self) -> None:
        animator = Animator(animations={"idle": AnimationData(loop=False)})
        animator.is_finished = True
        animator.resume()
        self.assertFalse(animator.is_finished)

    def test_animator_is_playing(self) -> None:
        animator = Animator(animations={"idle": AnimationData(loop=True)})
        self.assertTrue(animator.is_playing)
        animator.is_finished = True
        self.assertFalse(animator.is_playing)

    def test_animator_is_playing_non_loop_finished(self) -> None:
        animator = Animator(animations={"idle": AnimationData(loop=False)})
        animator.is_finished = True
        self.assertFalse(animator.is_playing)

    def test_animator_is_playing_non_loop_active(self) -> None:
        animator = Animator(animations={"idle": AnimationData(loop=False, slice_names=["a", "b", "c"])})
        self.assertTrue(animator.is_playing)
        animator.current_frame = 1
        self.assertTrue(animator.is_playing)
        animator.is_finished = True
        self.assertFalse(animator.is_playing)

    def test_animator_is_playing_no_animations(self) -> None:
        animator = Animator()
        self.assertFalse(animator.is_playing)

    def test_animator_normalized_time(self) -> None:
        animator = Animator(
            animations={"idle": AnimationData(slice_names=["a", "b", "c"])},
            default_state="idle",
        )
        self.assertEqual(animator.normalized_time, 0.0)
        animator.current_frame = 1
        self.assertAlmostEqual(animator.normalized_time, 0.5, places=2)
        animator.current_frame = 2
        self.assertEqual(animator.normalized_time, 1.0)

    def test_animator_normalized_time_no_animations(self) -> None:
        animator = Animator()
        self.assertEqual(animator.normalized_time, 0.0)

    def test_animator_to_dict_includes_flip_y_and_speed(self) -> None:
        animator = Animator(flip_x=True, flip_y=True, speed=1.5)
        data = animator.to_dict()
        self.assertTrue(data["flip_x"])
        self.assertTrue(data["flip_y"])
        self.assertEqual(data["speed"], 1.5)

    def test_animator_from_dict_flip_y_and_speed(self) -> None:
        data = {
            "enabled": True,
            "sprite_sheet": "",
            "frame_width": 32,
            "frame_height": 32,
            "flip_x": True,
            "flip_y": True,
            "speed": 2.0,
            "animations": {},
            "default_state": "idle",
            "current_state": "idle",
            "current_frame": 0,
            "is_finished": False,
        }
        animator = Animator.from_dict(data)
        self.assertTrue(animator.flip_x)
        self.assertTrue(animator.flip_y)
        self.assertEqual(animator.speed, 2.0)

    def test_animator_from_dict_default_flip_y_and_speed(self) -> None:
        data = {
            "enabled": True,
            "sprite_sheet": "",
            "frame_width": 32,
            "frame_height": 32,
            "animations": {},
            "default_state": "idle",
            "current_state": "idle",
            "current_frame": 0,
            "is_finished": False,
        }
        animator = Animator.from_dict(data)
        self.assertFalse(animator.flip_y)
        self.assertEqual(animator.speed, 1.0)

    def test_animator_roundtrip_with_new_fields(self) -> None:
        animator = Animator(
            sprite_sheet="test.png",
            frame_width=64,
            frame_height=64,
            flip_x=True,
            flip_y=True,
            speed=1.5,
            animations={
                "run": AnimationData(slice_names=["run_0", "run_1"], fps=12.0, loop=True),
            },
            default_state="run",
        )
        data = animator.to_dict()
        restored = Animator.from_dict(data)
        self.assertEqual(restored.flip_x, True)
        self.assertEqual(restored.flip_y, True)
        self.assertEqual(restored.speed, 1.5)
        self.assertEqual(restored.default_state, "run")
        self.assertEqual(restored.animations["run"].fps, 12.0)
        self.assertEqual(restored.animations["run"].slice_names, ["run_0", "run_1"])

    def test_animator_parameter_runtime_defaults(self) -> None:
        animator = Animator(
            parameters={
                "is_moving": AnimationParameterDefinition(type="bool", default=True),
                "speed": AnimationParameterDefinition(type="float", default=2.5),
                "combo": AnimationParameterDefinition(type="int", default=3),
                "attack": AnimationParameterDefinition(type="trigger", default=False),
            }
        )

        self.assertTrue(animator.get_parameter("is_moving"))
        self.assertEqual(animator.get_parameter("speed"), 2.5)
        self.assertEqual(animator.get_parameter("combo"), 3)
        self.assertFalse(animator.get_parameter("attack"))

    def test_animator_trigger_runtime_state_is_not_serialized(self) -> None:
        animator = Animator(
            parameters={
                "attack": AnimationParameterDefinition(type="trigger", default=False),
            }
        )
        self.assertTrue(animator.set_trigger("attack"))
        self.assertTrue(animator.get_parameter("attack"))

        data = animator.to_dict()
        self.assertIn("parameters", data)
        self.assertNotIn("parameter_values", data)
        self.assertFalse(data["parameters"]["attack"]["default"])

        restored = Animator.from_dict(data)
        self.assertFalse(restored.get_parameter("attack"))

    def test_animator_state_machine_roundtrip(self) -> None:
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["idle_0"]),
                "run": AnimationData(slice_names=["run_0"]),
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
                                conditions=[
                                    AnimationCondition(
                                        parameter="is_moving",
                                        operator="==",
                                        value=True,
                                    )
                                ],
                                force_restart=True,
                            )
                        ]
                    )
                },
            ),
        )

        data = animator.to_dict()
        restored = Animator.from_dict(data)

        self.assertIn("state_machine", data)
        self.assertEqual(restored.state_machine.entry_state, "idle")
        self.assertEqual(len(restored.get_state_transitions("idle")), 1)
        self.assertEqual(restored.get_state_transitions("idle")[0].to, "run")

    def test_animator_play_stays_compatible_with_state_machine(self) -> None:
        animator = Animator(
            animations={
                "idle": AnimationData(),
                "run": AnimationData(),
            },
            default_state="idle",
            state_machine=AnimationStateMachine(
                entry_state="idle",
                states={
                    "idle": AnimationStateDefinition(
                        transitions=[AnimationTransition(to="run")]
                    )
                },
            ),
        )

        previous_state = animator.play("run")

        self.assertEqual(previous_state, "idle")
        self.assertEqual(animator.current_state, "run")

    def test_animator_uses_state_machine_entry_when_default_state_is_missing(self) -> None:
        animator = Animator(
            animations={
                "idle": AnimationData(),
            },
            default_state="missing",
            state_machine=AnimationStateMachine(
                entry_state="idle",
                states={"idle": AnimationStateDefinition()},
            ),
        )

        self.assertEqual(animator.current_state, "idle")


class AnimationDataTests(unittest.TestCase):
    def test_animation_data_default_values(self) -> None:
        anim = AnimationData()
        self.assertEqual(anim.frames, [0])
        self.assertEqual(anim.slice_names, [])
        self.assertEqual(anim.fps, 8.0)
        self.assertTrue(anim.loop)
        self.assertIsNone(anim.on_complete)

    def test_animation_data_get_frame_count_with_slices(self) -> None:
        anim = AnimationData(slice_names=["a", "b", "c"])
        self.assertEqual(anim.get_frame_count(), 3)

    def test_animation_data_get_frame_count_with_frames_only(self) -> None:
        anim = AnimationData(frames=[0, 1, 2])
        self.assertEqual(anim.get_frame_count(), 3)

    def test_animation_data_get_frame_count_prioritizes_slices(self) -> None:
        anim = AnimationData(frames=[0, 1], slice_names=["a", "b", "c"])
        self.assertEqual(anim.get_frame_count(), 3)

    def test_animation_data_to_dict(self) -> None:
        anim = AnimationData(
            frames=[0, 1],
            slice_names=["a", "b"],
            fps=12.0,
            loop=False,
            on_complete="next",
        )
        data = anim.to_dict()
        self.assertEqual(data["frames"], [0, 1])
        self.assertEqual(data["slice_names"], ["a", "b"])
        self.assertEqual(data["fps"], 12.0)
        self.assertFalse(data["loop"])
        self.assertEqual(data["on_complete"], "next")

    def test_animation_data_to_dict_omits_on_complete_when_none(self) -> None:
        anim = AnimationData()
        data = anim.to_dict()
        self.assertNotIn("on_complete", data)

    def test_animation_data_from_dict(self) -> None:
        data = {
            "frames": [1, 2, 3],
            "slice_names": ["x", "y"],
            "fps": 24.0,
            "loop": False,
            "on_complete": "done",
        }
        anim = AnimationData.from_dict(data)
        self.assertEqual(anim.frames, [1, 2, 3])
        self.assertEqual(anim.slice_names, ["x", "y"])
        self.assertEqual(anim.fps, 24.0)
        self.assertFalse(anim.loop)
        self.assertEqual(anim.on_complete, "done")

    def test_animation_data_from_dict_defaults(self) -> None:
        anim = AnimationData.from_dict({})
        self.assertEqual(anim.frames, [0])
        self.assertEqual(anim.slice_names, [])
        self.assertEqual(anim.fps, 8.0)
        self.assertTrue(anim.loop)
        self.assertIsNone(anim.on_complete)


if __name__ == "__main__":
    unittest.main()
