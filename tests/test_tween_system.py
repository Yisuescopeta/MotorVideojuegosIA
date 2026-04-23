"""
tests/test_tween_system.py - Tests del TweenSystem.
"""

import unittest

from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.components.tween import Tween
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.events.signals import SignalRuntime
from engine.systems.tween_system import TweenSystem


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

    def test_tween_loop_restarts(self) -> None:
        entity = self._create_entity_with_tween(
            property_path="Transform.y",
            from_value=0.0,
            to_value=10.0,
            duration=1.0,
            autostart=True,
            one_shot=False,
        )
        transform = entity.get_component(Transform)
        assert transform is not None

        self.system.update(self.world, 0.0)
        self.system.update(self.world, 1.5)
        # Se reinicia: 1.5s -> 1 ciclo completo + 0.5 del segundo -> y=5.0
        self.assertAlmostEqual(transform.y, 5.0, places=5)

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
        entity.add_component(Tween(
            property_path="Sprite.tint_3",
            from_value=0.0,
            to_value=255.0,
            duration=1.0,
            autostart=True,
        ))
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


if __name__ == "__main__":
    unittest.main()
