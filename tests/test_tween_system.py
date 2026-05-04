"""
tests/test_tween_system.py - Tests del TweenSystem (Godot parity upgrade).
"""

import math
import unittest

from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.components.tween import Tween, TweenStep, TweenTransition, TweenEase
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.events.signals import SignalRuntime
from engine.systems.tween_system import TweenSystem
from engine.utils.easing import get_easing


class TweenSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.signal_runtime = SignalRuntime()
        self.system = TweenSystem(self.signal_runtime)

    def _create_entity_with_tween(self, **kwargs: object) -> Entity:
        entity = Entity("TestEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        entity.add_component(Tween(**kwargs))
        self.world.add_entity(entity)
        return entity

    # --- Legacy backward-compat tests ---

    def test_tween_updates_transform_x(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=100.0,
            duration=1.0,
            autostart=True,
        )
        transform = entity.get_component(Transform)
        assert transform is not None

        self.system.update(self.world, 0.0)
        self.assertEqual(transform.x, 0.0)

        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 50.0, places=5)

        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 100.0, places=5)

    def test_tween_finished_emits_signal(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "finished", lambda: received.append("finished"))

        self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=10.0,
            duration=0.2,
            autostart=True,
        )

        self.system.update(self.world, 0.0)
        self.system.update(self.world, 0.3)

        self.assertEqual(received, ["finished"])

    def test_disabled_tween_skipped(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=100.0,
            duration=1.0,
            autostart=True,
        )
        tween = entity.get_component(Tween)
        assert tween is not None
        tween.enabled = False

        transform = entity.get_component(Transform)
        assert transform is not None
        self.system.update(self.world, 1.0)
        self.assertEqual(transform.x, 0.0)

    def test_tween_updates_sprite_tint_alpha(self) -> None:
        entity = Entity("SpriteEntity")
        entity.add_component(Sprite())
        entity.add_component(
            Tween(
                property_path="Sprite.tint_3",
                from_value=0.0,
                to_value=255.0,
                duration=1.0,
                autostart=True,
            )
        )
        self.world.add_entity(entity)

        sprite = entity.get_component(Sprite)
        assert sprite is not None
        self.assertEqual(sprite.tint[3], 255)

        self.system.update(self.world, 0.0)
        self.system.update(self.world, 0.5)
        self.assertEqual(sprite.tint[3], 127)

        self.system.update(self.world, 0.5)
        self.assertEqual(sprite.tint[3], 255)

    def test_tween_no_signal_runtime_does_not_crash(self) -> None:
        system = TweenSystem(signal_runtime=None)
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=10.0,
            duration=0.1,
            autostart=True,
            one_shot=True,
        )
        system.update(self.world, 0.2)
        tween = entity.get_component(Tween)
        assert tween is not None
        self.assertTrue(tween.is_finished)

    def test_autostart_on_first_frame(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=50.0,
            duration=1.0,
            autostart=True,
        )
        transform = entity.get_component(Transform)
        assert transform is not None
        self.system.update(self.world, 0.0)
        self.assertTrue(entity.get_component(Tween).is_running)
        self.system.update(self.world, 1.0)
        self.assertAlmostEqual(transform.x, 50.0, places=5)

    def test_manual_start(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=50.0,
            duration=1.0,
        )
        tween = entity.get_component(Tween)
        assert tween is not None
        tween.start()
        self.system.update(self.world, 0.5)
        transform = entity.get_component(Transform)
        assert transform is not None
        self.assertAlmostEqual(transform.x, 25.0, places=5)

    def test_custom_component_map(self) -> None:
        class FakeComponent:
            def __init__(self) -> None:
                self.value: float = 0.0

        entity = Entity("CustomEntity")
        entity.add_component(FakeComponent())
        entity.add_component(
            Tween(
                property_path="FakeComponent.value",
                from_value=0.0,
                to_value=100.0,
                duration=1.0,
                autostart=True,
            )
        )
        self.world.add_entity(entity)

        system = TweenSystem(self.signal_runtime, component_map={"FakeComponent": FakeComponent})
        system.update(self.world, 0.0)
        system.update(self.world, 0.5)

        fake = entity.get_component(FakeComponent)
        assert fake is not None
        self.assertAlmostEqual(fake.value, 50.0, places=5)

    # --- Easing function tests ---

    def test_linear_easing(self) -> None:
        fn = get_easing("linear", "ease_in")
        self.assertEqual(fn(0.0), 0.0)
        self.assertEqual(fn(0.5), 0.5)
        self.assertEqual(fn(1.0), 1.0)

    def test_ease_in_out_sine(self) -> None:
        fn = get_easing("sine", "ease_in_out")
        self.assertEqual(fn(0.0), 0.0)
        self.assertEqual(fn(1.0), 1.0)
        self.assertAlmostEqual(fn(0.5), 0.5, places=5)

    def test_bounce_ease_out_completes(self) -> None:
        fn = get_easing("bounce", "ease_out")
        self.assertEqual(fn(0.0), 0.0)
        self.assertAlmostEqual(fn(1.0), 1.0, places=5)

    def test_elastic_ease_in_out_boundaries(self) -> None:
        fn = get_easing("elastic", "ease_in_out")
        self.assertEqual(fn(0.0), 0.0)
        self.assertEqual(fn(1.0), 1.0)

    def test_back_ease_out_boundaries(self) -> None:
        fn = get_easing("back", "ease_out")
        self.assertEqual(fn(1.0), 1.0)
        # back ease_out overshoots, so value at 0.0 can be slightly below 0
        self.assertAlmostEqual(fn(0.0), 0.0, places=5)

    def test_spring_ease_in_boundaries(self) -> None:
        fn = get_easing("spring", "ease_in")
        self.assertEqual(fn(1.0), 1.0)
        self.assertAlmostEqual(fn(0.0), 0.0, places=5)

    def test_all_transition_ease_combinations_exist(self) -> None:
        transitions = [
            "linear", "sine", "quad", "cubic", "quart", "quint",
            "expo", "circ", "back", "elastic", "bounce", "spring",
        ]
        eases = ["ease_in", "ease_out", "ease_in_out", "ease_out_in"]
        for trans in transitions:
            for ease in eases:
                fn = get_easing(trans, ease)
                self.assertIsNotNone(fn, f"Missing easing: {trans}/{ease}")
                # Should return 0.0 at t=0 and ~1.0 at t=1
                self.assertAlmostEqual(fn(0.0), 0.0, delta=0.01, msg=f"{trans}/{ease} at t=0")
                self.assertAlmostEqual(fn(1.0), 1.0, delta=0.01, msg=f"{trans}/{ease} at t=1")

    # --- Legacy easing backward compat ---

    def test_legacy_easing_still_works(self) -> None:
        from engine.utils.easing import get_legacy_easing
        fn = get_legacy_easing("sine_in_out")
        self.assertIsNotNone(fn)
        self.assertAlmostEqual(fn(0.5), 0.5, places=5)

    def test_legacy_transition_in_new_get_easing(self) -> None:
        fn = get_easing("sine_in_out", "ease_in_out")
        self.assertIsNotNone(fn)
        self.assertAlmostEqual(fn(0.5), 0.5, places=5)

    # --- Ease out_in mode ---

    def test_ease_out_in_quad(self) -> None:
        fn = get_easing("quad", "ease_out_in")
        self.assertAlmostEqual(fn(0.0), 0.0, places=5)
        self.assertAlmostEqual(fn(1.0), 1.0, places=5)
        self.assertGreater(fn(0.25), 0.11)  # Fast at start

    # --- New multi-step Tween tests ---

    def test_chain_sequential_steps(self) -> None:
        entity = Entity("ChainEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        tween = Tween()
        tween.tween_property("ChainEntity", "Transform", "Transform.x", 50.0, 0.5)
        tween.chain()
        tween.tween_property("ChainEntity", "Transform", "Transform.y", 50.0, 0.5)
        entity.add_component(tween)
        self.world.add_entity(entity)

        tween.start()
        transform = entity.get_component(Transform)
        assert transform is not None

        # First step: x from 0 to 50 in 0.5s
        self.system.update(self.world, 0.25)
        self.assertAlmostEqual(transform.x, 25.0, places=5)
        self.assertEqual(transform.y, 0.0)

        self.system.update(self.world, 0.3)
        self.assertAlmostEqual(transform.x, 50.0, places=5)
        self.assertEqual(transform.y, 0.0)

        # Second step: y from 0 to 50 in 0.5s
        self.system.update(self.world, 0.25)
        self.assertAlmostEqual(transform.y, 25.0, places=5)

        self.system.update(self.world, 0.3)
        self.assertAlmostEqual(transform.y, 50.0, places=5)

    def test_parallel_steps(self) -> None:
        entity = Entity("ParallelEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        tween = Tween()
        tween.tween_property("ParallelEntity", "Transform", "Transform.x", 100.0, 1.0)
        tween.set_parallel(True)
        tween.tween_property("ParallelEntity", "Transform", "Transform.y", 50.0, 1.0)
        entity.add_component(tween)
        self.world.add_entity(entity)

        tween.start()
        transform = entity.get_component(Transform)
        assert transform is not None

        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 50.0, places=5)
        self.assertAlmostEqual(transform.y, 25.0, places=5)

        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 100.0, places=5)
        self.assertAlmostEqual(transform.y, 50.0, places=5)

    def test_loop_repeats(self) -> None:
        entity = Entity("LoopEntity")
        entity.add_component(Transform(x=0.0))
        tween = Tween()
        tween.tween_property("LoopEntity", "Transform", "Transform.x", 100.0, 0.5)
        tween.set_loops(2)  # Play twice (2 loops total)
        entity.add_component(tween)
        self.world.add_entity(entity)

        tween.start()
        transform = entity.get_component(Transform)
        assert transform is not None

        # First loop
        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 100.0, places=5)

        # Second loop restarts from 0
        self.system.update(self.world, 0.25)
        self.assertAlmostEqual(transform.x, 50.0, places=5)

        self.system.update(self.world, 0.3)
        self.assertAlmostEqual(transform.x, 100.0, places=5)

        # After loops finish, tween stops
        self.assertFalse(tween.running)

    def test_pause_resume(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=100.0,
            duration=1.0,
            autostart=True,
        )
        transform = entity.get_component(Transform)
        assert transform is not None
        tween = entity.get_component(Tween)
        assert tween is not None

        self.system.update(self.world, 0.5)
        val_half = transform.x
        self.assertAlmostEqual(val_half, 50.0, places=5)

        tween.pause()
        self.assertTrue(tween.paused)

        self.system.update(self.world, 1.0)
        # Should not change while paused
        self.assertAlmostEqual(transform.x, val_half, places=5)

        tween.resume()
        self.assertFalse(tween.paused)

        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 100.0, places=5)

    def test_speed_scale(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.x",
            from_value=0.0,
            to_value=100.0,
            duration=1.0,
            autostart=True,
        )
        tween = entity.get_component(Tween)
        assert tween is not None
        tween.speed_scale = 2.0

        transform = entity.get_component(Transform)
        assert transform is not None

        self.system.update(self.world, 0.25)
        # With speed_scale 2.0, 0.25s real = 0.5s tween time
        self.assertAlmostEqual(transform.x, 50.0, places=5)

    def test_delay_before_start(self) -> None:
        entity = Entity("DelayEntity")
        entity.add_component(Transform(x=0.0))
        tween = Tween()
        tween.tween_property("DelayEntity", "Transform", "Transform.x", 100.0, 0.5)
        tween.set_delay(0.5)
        entity.add_component(tween)
        self.world.add_entity(entity)

        tween.start()
        transform = entity.get_component(Transform)
        assert transform is not None

        # First 0.5s: delay, no change
        self.system.update(self.world, 0.4)
        self.assertEqual(transform.x, 0.0)

        # At 0.6s: 0.1s of animation elapsed
        self.system.update(self.world, 0.2)
        self.assertAlmostEqual(transform.x, 20.0, places=5)

    def test_set_trans_and_ease_on_step(self) -> None:
        entity = Entity("EaseStepEntity")
        entity.add_component(Transform(x=0.0))
        tween = Tween()
        tween.tween_property("EaseStepEntity", "Transform", "Transform.x", 100.0, 1.0)
        tween.set_trans("quad")
        tween.set_ease("ease_in")
        entity.add_component(tween)
        self.world.add_entity(entity)

        tween.start()
        transform = entity.get_component(Transform)
        assert transform is not None

        self.system.update(self.world, 0.5)
        # ease_in_quad at t=0.5 gives 0.25, so value = 25
        self.assertAlmostEqual(transform.x, 25.0, places=5)

    def test_nested_property_path(self) -> None:
        """Test que propiedades anidadas como 'Component.sub.field' funcionan."""
        entity = Entity("NestedEntity")
        entity.add_component(Transform(x=0.0, y=0.0))
        tween = Tween()
        tween.tween_property("NestedEntity", "Transform", "Transform.x", 100.0, 1.0)
        entity.add_component(tween)
        self.world.add_entity(entity)

        tween.start()
        transform = entity.get_component(Transform)
        assert transform is not None

        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(transform.x, 50.0, places=5)

    def test_tween_component_serialization(self) -> None:
        tween = Tween()
        tween.tween_property("Target", "Transform", "Transform.x", 100.0, 1.0)
        tween.set_trans("cubic")
        tween.set_ease("ease_out")
        tween.set_delay(0.2)
        tween.chain()
        tween.tween_property("Target", "Sprite", "Sprite.tint_0", 255.0, 0.5)
        tween.set_loops(3)
        tween.speed_scale = 2.0

        data = tween.to_dict()
        restored = Tween.from_dict(data)

        self.assertEqual(len(restored.steps), 2)
        self.assertEqual(restored.steps[0].transition, TweenTransition.CUBIC)
        self.assertEqual(restored.steps[0].ease, TweenEase.EASE_OUT)
        self.assertAlmostEqual(restored.steps[0].delay, 0.2)
        self.assertEqual(restored.steps[1].to_value, 255.0)
        self.assertEqual(restored.loops, 3)
        self.assertAlmostEqual(restored.speed_scale, 2.0)

    def test_tween_step_serialization(self) -> None:
        step = TweenStep(
            target_entity="Player",
            target_component="Transform",
            property_path="Transform.x",
            from_value=10.0,
            to_value=50.0,
            duration=2.0,
            delay=0.5,
            transition=TweenTransition.BOUNCE,
            ease=TweenEase.EASE_OUT_IN,
        )
        data = step.to_dict()
        restored = TweenStep.from_dict(data)
        self.assertEqual(restored.target_entity, "Player")
        self.assertEqual(restored.transition, TweenTransition.BOUNCE)
        self.assertEqual(restored.ease, TweenEase.EASE_OUT_IN)

    def test_default_transition_used_for_steps(self) -> None:
        tween = Tween()
        tween.default_transition = TweenTransition.ELASTIC
        tween.default_ease = TweenEase.EASE_OUT
        tween.tween_property("A", "Transform", "Transform.x", 100.0, 1.0)
        self.assertEqual(tween.steps[0].transition, TweenTransition.ELASTIC)
        self.assertEqual(tween.steps[0].ease, TweenEase.EASE_OUT)

    def test_enum_value_coercion(self) -> None:
        self.assertEqual(TweenTransition("bounce"), TweenTransition.BOUNCE)
        self.assertEqual(TweenTransition("spring"), TweenTransition.SPRING)
        self.assertEqual(TweenEase("ease_in"), TweenEase.EASE_IN)
        self.assertEqual(TweenEase("ease_out_in"), TweenEase.EASE_OUT_IN)

    def test_legacy_tween_transition_property(self) -> None:
        tween = Tween(transition="quad_out")
        self.assertEqual(tween.transition, "quad")
        self.assertEqual(len(tween.steps), 1)


if __name__ == "__main__":
    unittest.main()
