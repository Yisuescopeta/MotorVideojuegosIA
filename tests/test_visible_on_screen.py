"""
tests/test_visible_on_screen.py - Tests de VisibleOnScreenNotifier2D/Enabler2D.
"""

import unittest

from engine.components.transform import Transform
from engine.components.visible_on_screen_notifier_2d import (
    VisibleOnScreenEnabler2D,
    VisibleOnScreenNotifier2D,
)
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.events.signals import SignalRuntime
from engine.systems.visible_on_screen_system import VisibleOnScreenSystem


class VisibleOnScreenSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.signal_runtime = SignalRuntime()
        self.system = VisibleOnScreenSystem(self.signal_runtime)

    def _create_notifier(self, x: float = 0.0, y: float = 0.0, **kwargs: object) -> Entity:
        entity = Entity("Notifier")
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(VisibleOnScreenNotifier2D(**kwargs))
        self.world.add_entity(entity)
        return entity

    def test_enters_screen_emits_signal(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("Notifier", "screen_entered", lambda: received.append("entered"))

        entity = self._create_notifier(x=50.0, y=50.0, rect_width=20.0, rect_height=20.0)
        notifier = entity.get_component(VisibleOnScreenNotifier2D)
        assert notifier is not None

        # Primera vez fuera de pantalla
        self.system.update(self.world, (0.0, 0.0, 40.0, 40.0))
        self.assertFalse(notifier.is_on_screen)
        self.assertEqual(received, [])

        # Mover viewport para incluir la entidad
        self.system.update(self.world, (0.0, 0.0, 100.0, 100.0))
        self.assertTrue(notifier.is_on_screen)
        self.assertEqual(received, ["entered"])

    def test_exits_screen_emits_signal(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("Notifier", "screen_exited", lambda: received.append("exited"))

        entity = self._create_notifier(x=50.0, y=50.0, rect_width=20.0, rect_height=20.0)
        notifier = entity.get_component(VisibleOnScreenNotifier2D)
        assert notifier is not None

        # Dentro
        self.system.update(self.world, (0.0, 0.0, 100.0, 100.0))
        self.assertTrue(notifier.is_on_screen)
        self.assertEqual(received, [])

        # Mover fuera
        self.system.update(self.world, (0.0, 0.0, 40.0, 40.0))
        self.assertFalse(notifier.is_on_screen)
        self.assertEqual(received, ["exited"])

    def test_disabled_notifier_skipped(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("Notifier", "screen_entered", lambda: received.append("entered"))

        entity = self._create_notifier(x=50.0, y=50.0, rect_width=20.0, rect_height=20.0)
        notifier = entity.get_component(VisibleOnScreenNotifier2D)
        assert notifier is not None
        notifier.enabled = False

        self.system.update(self.world, (0.0, 0.0, 100.0, 100.0))
        self.assertEqual(received, [])

    def test_no_viewport_does_nothing(self) -> None:
        entity = self._create_notifier(x=50.0, y=50.0, rect_width=20.0, rect_height=20.0)
        notifier = entity.get_component(VisibleOnScreenNotifier2D)
        assert notifier is not None

        self.system.update(self.world, None)
        self.assertFalse(notifier.is_on_screen)

    def test_enabler_disables_entity(self) -> None:
        entity = Entity("Target")
        entity.add_component(Transform(x=50.0, y=50.0))
        entity.add_component(VisibleOnScreenEnabler2D(
            rect_width=20.0,
            rect_height=20.0,
            enable_node_path="",
        ))
        self.world.add_entity(entity)

        # Dentro -> activa
        self.system.update(self.world, (0.0, 0.0, 100.0, 100.0))
        self.assertTrue(entity.active)

        # Fuera -> desactiva
        self.system.update(self.world, (0.0, 0.0, 40.0, 40.0))
        self.assertFalse(entity.active)

    def test_enabler_target_by_name(self) -> None:
        target = Entity("TargetByName")
        target.active = True
        self.world.add_entity(target)

        enabler_entity = Entity("Enabler")
        enabler_entity.add_component(Transform(x=50.0, y=50.0))
        enabler_entity.add_component(VisibleOnScreenEnabler2D(
            rect_width=20.0,
            rect_height=20.0,
            enable_node_path="TargetByName",
        ))
        self.world.add_entity(enabler_entity)

        # Fuera -> desactiva target
        self.system.update(self.world, (0.0, 0.0, 40.0, 40.0))
        self.assertFalse(target.active)

        # Dentro -> activa target
        self.system.update(self.world, (0.0, 0.0, 100.0, 100.0))
        self.assertTrue(target.active)

    def test_serialization_notifier(self) -> None:
        notifier = VisibleOnScreenNotifier2D(rect_x=10.0, rect_y=20.0, rect_width=30.0, rect_height=40.0, show_rect=True)
        notifier.enabled = False
        data = notifier.to_dict()
        restored = VisibleOnScreenNotifier2D.from_dict(data)
        self.assertEqual(restored.rect_x, 10.0)
        self.assertEqual(restored.rect_y, 20.0)
        self.assertEqual(restored.rect_width, 30.0)
        self.assertEqual(restored.rect_height, 40.0)
        self.assertTrue(restored.show_rect)
        self.assertFalse(restored.enabled)

    def test_serialization_enabler(self) -> None:
        enabler = VisibleOnScreenEnabler2D(
            rect_x=5.0, rect_y=5.0, rect_width=10.0, rect_height=10.0,
            enable_mode="always", enable_node_path="Player",
        )
        data = enabler.to_dict()
        restored = VisibleOnScreenEnabler2D.from_dict(data)
        self.assertEqual(restored.enable_mode, "always")
        self.assertEqual(restored.enable_node_path, "Player")


if __name__ == "__main__":
    unittest.main()
