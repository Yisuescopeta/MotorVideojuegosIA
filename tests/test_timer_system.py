"""
tests/test_timer_system.py - Tests del TimerSystem integrado con SignalRuntime.
"""

import unittest
from unittest.mock import Mock

from engine.components.timer import Timer
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.events.signals import SignalConnectionFlags, SignalRuntime
from engine.systems.timer_system import TimerSystem


class TimerSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.signal_runtime = SignalRuntime()
        self.system = TimerSystem(self.signal_runtime)

    def _create_entity_with_timer(self, **timer_kwargs: object) -> Entity:
        entity = Entity("TestEntity")
        entity.add_component(Timer(**timer_kwargs))
        self.world.add_entity(entity)
        return entity

    def test_timer_counts_down_and_emits_timeout(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "timeout", lambda: received.append("timeout"))
        self.signal_runtime.connect("TestEntity", "started", lambda: received.append("started"))

        entity = self._create_entity_with_timer(wait_time=1.0, autostart=True)
        timer = entity.get_component(Timer)
        assert timer is not None

        # Primer update con autostart -> emite started
        self.system.update(self.world, 0.0)
        self.assertEqual(received, ["started"])
        self.assertEqual(timer.time_left, 1.0)

        # Avanzar 0.5s
        self.system.update(self.world, 0.5)
        self.assertAlmostEqual(timer.time_left, 0.5, places=5)
        self.assertEqual(received, ["started"])

        # Avanzar 0.6s -> timeout (0.5 + 0.6 = 1.1 > 1.0)
        self.system.update(self.world, 0.6)
        self.assertEqual(received, ["started", "timeout"])
        # Como no es one_shot, reinicia
        self.assertAlmostEqual(timer.time_left, 0.9, places=5)

    def test_one_shot_timer_stops_after_timeout(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "timeout", lambda: received.append("timeout"))
        self.signal_runtime.connect("TestEntity", "stopped", lambda: received.append("stopped"))

        entity = self._create_entity_with_timer(wait_time=1.0, one_shot=True, autostart=True)
        timer = entity.get_component(Timer)
        assert timer is not None

        self.system.update(self.world, 0.0)
        self.system.update(self.world, 1.5)

        self.assertEqual(received, ["timeout", "stopped"])
        self.assertTrue(timer.is_stopped)
        self.assertFalse(timer.is_running)

    def test_manual_start_no_emite_started(self) -> None:
        """El evento started solo se emite con autostart, no con start() manual."""
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "started", lambda: received.append("started"))

        entity = self._create_entity_with_timer(wait_time=2.0)
        timer = entity.get_component(Timer)
        assert timer is not None
        timer.start()

        self.system.update(self.world, 0.0)
        # started solo se emite por autostart; start() manual no genera señal
        self.assertEqual(received, [])

    def test_paused_timer_does_not_count(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "timeout", lambda: received.append("timeout"))

        entity = self._create_entity_with_timer(wait_time=1.0, autostart=True)
        timer = entity.get_component(Timer)
        assert timer is not None

        self.system.update(self.world, 0.0)
        timer.pause()
        self.system.update(self.world, 2.0)
        self.assertEqual(timer.time_left, 1.0)
        self.assertEqual(received, [])

    def test_disabled_timer_skipped(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "timeout", lambda: received.append("timeout"))

        entity = self._create_entity_with_timer(wait_time=0.5, autostart=True)
        timer = entity.get_component(Timer)
        assert timer is not None
        timer.enabled = False

        self.system.update(self.world, 1.0)
        self.assertEqual(received, [])

    def test_ignore_time_scale(self) -> None:
        received: list[str] = []
        self.signal_runtime.connect("TestEntity", "timeout", lambda: received.append("timeout"))

        entity = self._create_entity_with_timer(wait_time=1.0, autostart=True, ignore_time_scale=True)
        timer = entity.get_component(Timer)
        assert timer is not None

        self.system.update(self.world, 0.0)
        self.system.update(self.world, 0.5, time_scale=0.5)
        # Con ignore_time_scale=True, avanza 0.5 aunque time_scale=0.5
        self.assertAlmostEqual(timer.time_left, 0.5, places=5)

    def test_time_scale_affects_normal_timer(self) -> None:
        entity = self._create_entity_with_timer(wait_time=1.0, autostart=True)
        timer = entity.get_component(Timer)
        assert timer is not None

        self.system.update(self.world, 0.0)
        self.system.update(self.world, 0.5, time_scale=0.5)
        # Con time_scale=0.5, avanza 0.5 * 0.5 = 0.25
        self.assertAlmostEqual(timer.time_left, 0.75, places=5)

    def test_no_signal_runtime_does_not_crash(self) -> None:
        system = TimerSystem(signal_runtime=None)
        entity = self._create_entity_with_timer(wait_time=0.5, autostart=True, one_shot=True)
        system.update(self.world, 1.0)
        timer = entity.get_component(Timer)
        assert timer is not None
        self.assertTrue(timer.is_stopped)


if __name__ == "__main__":
    unittest.main()
