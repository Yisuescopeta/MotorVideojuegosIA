import unittest

from engine.components.animator import AnimationData, Animator
from engine.ecs.world import World
from engine.systems.animation_system import AnimationSystem


class BlendDefaultTests(unittest.TestCase):
    def test_blend_duration_default(self) -> None:
        anim = AnimationData()
        self.assertEqual(anim.blend_duration, 0.0)

    def test_blend_progress_starts_at_zero(self) -> None:
        animator = Animator()
        self.assertEqual(animator._blend_progress, 0.0)
        self.assertEqual(animator._blend_from_frame, 0)
        self.assertEqual(animator._blend_from_sprite_name, "")


class BlendSerializationTests(unittest.TestCase):
    def test_blend_duration_to_dict(self) -> None:
        anim = AnimationData(blend_duration=0.0)
        data = anim.to_dict()
        self.assertIn("blend_duration", data)
        self.assertEqual(data["blend_duration"], 0.0)

    def test_blend_duration_roundtrip(self) -> None:
        anim = AnimationData(blend_duration=0.5)
        data = anim.to_dict()
        restored = AnimationData.from_dict(data)
        self.assertEqual(restored.blend_duration, 0.5)

    def test_blend_duration_default_not_serialized_differently(self) -> None:
        anim = AnimationData()
        data = anim.to_dict()
        self.assertIn("blend_duration", data)
        self.assertEqual(data["blend_duration"], 0.0)


class BlendInitTests(unittest.TestCase):
    def test_play_initiates_blend_when_duration_positive(self) -> None:
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["i0"], blend_duration=0.0),
                "run": AnimationData(slice_names=["r0", "r1"], blend_duration=0.3),
            },
            default_state="idle",
        )
        animator.current_frame = 2
        animator._blend_from_sprite_name = "should_be_overwritten"
        animator.play("run")
        self.assertEqual(animator._blend_progress, 0.0)
        self.assertEqual(animator._blend_from_frame, 2)
        self.assertNotEqual(animator._blend_from_sprite_name, "should_be_overwritten")

    def test_play_does_not_initiate_blend_when_duration_zero(self) -> None:
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["i0"]),
                "run": AnimationData(slice_names=["r0"]),
            },
            default_state="idle",
        )
        animator._blend_progress = 0.5
        animator._blend_from_frame = 99
        animator._blend_from_sprite_name = "keep_this"
        animator.play("run")
        self.assertEqual(animator._blend_progress, 0.5)
        self.assertEqual(animator._blend_from_frame, 99)
        self.assertEqual(animator._blend_from_sprite_name, "keep_this")


class BlendProgressTests(unittest.TestCase):
    def test_blend_progress_advances(self) -> None:
        world = World()
        entity = world.create_entity("BlendAdvance")
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["i0"], fps=8.0, loop=True, blend_duration=0.5),
            },
            default_state="idle",
        )
        entity.add_component(animator)
        system = AnimationSystem()

        animator.play("idle", force_restart=True)
        self.assertEqual(animator._blend_progress, 0.0)
        self.assertEqual(animator._blend_from_frame, 0)
        self.assertEqual(animator._blend_from_sprite_name, "i0")

        system.update(world, delta_time=0.1)
        self.assertGreater(animator._blend_progress, 0.0)
        self.assertAlmostEqual(animator._blend_progress, 0.1 / 0.5, places=3)

    def test_blend_completes(self) -> None:
        world = World()
        entity = world.create_entity("BlendComplete")
        animator = Animator(
            animations={
                "run": AnimationData(slice_names=["r0", "r1"], fps=4.0, loop=True, blend_duration=0.4),
            },
            default_state="run",
        )
        entity.add_component(animator)
        system = AnimationSystem()

        animator.play("run", force_restart=True)
        self.assertEqual(animator._blend_progress, 0.0)

        system.update(world, delta_time=0.5)
        self.assertEqual(animator._blend_progress, 1.0)

    def test_blend_stays_at_one_after_completion(self) -> None:
        world = World()
        entity = world.create_entity("BlendMax")
        animator = Animator(
            animations={
                "run": AnimationData(slice_names=["r0"], fps=8.0, loop=True, blend_duration=0.1),
            },
            default_state="run",
        )
        entity.add_component(animator)
        system = AnimationSystem()

        animator.play("run", force_restart=True)
        system.update(world, delta_time=1.0)
        self.assertEqual(animator._blend_progress, 1.0)
        system.update(world, delta_time=1.0)
        self.assertEqual(animator._blend_progress, 1.0)

    def test_blend_clears_on_second_transition(self) -> None:
        world = World()
        entity = world.create_entity("BlendChain")
        animator = Animator(
            animations={
                "idle": AnimationData(slice_names=["i0"], fps=8.0, loop=True),
                "run": AnimationData(slice_names=["r0", "r1"], fps=4.0, loop=True, blend_duration=0.3),
                "jump": AnimationData(slice_names=["j0"], fps=8.0, loop=True, blend_duration=0.5),
            },
            default_state="idle",
        )
        entity.add_component(animator)
        system = AnimationSystem()

        animator.play("run")
        self.assertEqual(animator._blend_progress, 0.0)
        system.update(world, delta_time=0.1)
        first_blend = animator._blend_progress
        self.assertGreater(first_blend, 0.0)
        self.assertLess(first_blend, 1.0)

        animator.play("jump")
        self.assertEqual(animator._blend_progress, 0.0)
        self.assertEqual(animator._blend_from_frame, 0)


class BlendCurrentSpriteNameTests(unittest.TestCase):
    def test_current_sprite_name_with_slices(self) -> None:
        animator = Animator(
            animations={"walk": AnimationData(slice_names=["walk_0", "walk_1"])},
            default_state="walk",
        )
        self.assertEqual(animator.current_sprite_name, "walk_0")
        animator.current_frame = 1
        self.assertEqual(animator.current_sprite_name, "walk_1")

    def test_current_sprite_name_with_frames_only(self) -> None:
        animator = Animator(
            animations={"idle": AnimationData(frames=[5, 6])},
            default_state="idle",
        )
        self.assertEqual(animator.current_sprite_name, "5")
        animator.current_frame = 1
        self.assertEqual(animator.current_sprite_name, "6")


if __name__ == "__main__":
    unittest.main()
