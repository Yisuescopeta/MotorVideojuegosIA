"""
tests/test_area2d.py - Tests para componente Area2D y Area2DSystem
"""

import unittest

from engine.components.area2d import Area2D
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.levels.component_registry import create_default_registry
from engine.systems.area2d_system import Area2DSystem


class Area2DComponentTests(unittest.TestCase):
    """Tests para el componente Area2D."""

    def test_area2d_creation(self) -> None:
        area = Area2D()
        self.assertTrue(area.monitoring)
        self.assertTrue(area.monitorable)
        self.assertEqual(area.space_override, "disabled")
        self.assertFalse(area.gravity_point)
        self.assertEqual(area.gravity_distance_scale, 0.0)
        self.assertEqual(area.priority, 0)
        self.assertEqual(area._tracked_bodies, set())
        self.assertEqual(area._tracked_areas, set())

    def test_area2d_creation_custom(self) -> None:
        area = Area2D(
            monitoring=False,
            monitorable=False,
            space_override="combine",
            gravity_point=True,
            gravity_distance_scale=2.5,
            priority=10,
        )
        self.assertFalse(area.monitoring)
        self.assertFalse(area.monitorable)
        self.assertEqual(area.space_override, "combine")
        self.assertTrue(area.gravity_point)
        self.assertEqual(area.gravity_distance_scale, 2.5)
        self.assertEqual(area.priority, 10)

    def test_area2d_serialization_roundtrip(self) -> None:
        area = Area2D(
            monitoring=False,
            monitorable=True,
            space_override="replace",
            gravity_point=True,
            gravity_distance_scale=1.5,
            priority=5,
        )
        data = area.to_dict()
        restored = Area2D.from_dict(data)
        self.assertEqual(restored.monitoring, area.monitoring)
        self.assertEqual(restored.monitorable, area.monitorable)
        self.assertEqual(restored.space_override, area.space_override)
        self.assertEqual(restored.gravity_point, area.gravity_point)
        self.assertEqual(restored.gravity_distance_scale, area.gravity_distance_scale)
        self.assertEqual(restored.priority, area.priority)
        # Runtime state no se serializa
        self.assertEqual(restored._tracked_bodies, set())
        self.assertEqual(restored._tracked_areas, set())

    def test_area2d_serialization_defaults(self) -> None:
        area = Area2D()
        data = area.to_dict()
        self.assertEqual(data["monitoring"], True)
        self.assertEqual(data["monitorable"], True)
        self.assertEqual(data["space_override"], "disabled")
        self.assertEqual(data["gravity_point"], False)
        self.assertEqual(data["gravity_distance_scale"], 0.0)
        self.assertEqual(data["priority"], 0)

    def test_area2d_registry(self) -> None:
        registry = create_default_registry()
        area_cls = registry.get("Area2D")
        self.assertIsNotNone(area_cls)
        self.assertEqual(area_cls, Area2D)

    def test_area2d_create_from_registry(self) -> None:
        registry = create_default_registry()
        data = {
            "monitoring": False,
            "monitorable": True,
            "space_override": "combine",
            "gravity_point": True,
            "gravity_distance_scale": 3.0,
            "priority": 7,
        }
        area = registry.create("Area2D", data)
        self.assertIsInstance(area, Area2D)
        self.assertFalse(area.monitoring)
        self.assertTrue(area.monitorable)
        self.assertEqual(area.space_override, "combine")
        self.assertTrue(area.gravity_point)
        self.assertEqual(area.gravity_distance_scale, 3.0)
        self.assertEqual(area.priority, 7)


class Area2DSystemTests(unittest.TestCase):
    """Tests para el sistema Area2DSystem."""

    def _make_body_entity(
        self,
        world: World,
        name: str,
        x: float,
        y: float,
        width: float = 20.0,
        height: float = 20.0,
    ):
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(width=width, height=height))
        entity.add_component(RigidBody())
        return entity

    def _make_area_entity(
        self,
        world: World,
        name: str,
        x: float,
        y: float,
        width: float = 64.0,
        height: float = 64.0,
        monitoring: bool = True,
        monitorable: bool = True,
    ):
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(width=width, height=height))
        entity.add_component(Area2D(monitoring=monitoring, monitorable=monitorable))
        return entity

    def _get_events_by_name(self, event_bus: EventBus, event_name: str):
        return [e for e in event_bus.get_recent_events() if e.name == event_name]

    def test_body_entered(self) -> None:
        """RigidBody entra en area -> evento body_entered."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        area = self._make_area_entity(world, "TriggerZone", x=0.0, y=0.0, width=64.0, height=64.0)
        body = self._make_body_entity(world, "Player", x=10.0, y=10.0)

        system.update(world)

        entered = self._get_events_by_name(event_bus, "body_entered")
        self.assertEqual(len(entered), 1)
        self.assertEqual(entered[0].data["entity_id"], area.id)
        self.assertEqual(entered[0].data["other_entity_id"], body.id)
        self.assertEqual(entered[0].data["entity_name"], "TriggerZone")
        self.assertEqual(entered[0].data["other_entity_name"], "Player")

        # Tracked bodies updated
        area2d = area.get_component(Area2D)
        self.assertIn(body.id, area2d._tracked_bodies)

    def test_body_exited(self) -> None:
        """RigidBody sale del area -> evento body_exited."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        area = self._make_area_entity(world, "TriggerZone", x=0.0, y=0.0, width=64.0, height=64.0)
        body = self._make_body_entity(world, "Player", x=10.0, y=10.0)

        # Frame 1: body inside
        system.update(world)
        event_bus.clear_history()

        # Move body far away
        body.get_component(Transform).x = 500.0
        body.get_component(Transform).y = 500.0

        # Frame 2: body outside
        system.update(world)

        exited = self._get_events_by_name(event_bus, "body_exited")
        self.assertEqual(len(exited), 1)
        self.assertEqual(exited[0].data["entity_id"], area.id)
        self.assertEqual(exited[0].data["other_entity_id"], body.id)

        area2d = area.get_component(Area2D)
        self.assertNotIn(body.id, area2d._tracked_bodies)

    def test_area_entered(self) -> None:
        """Dos areas se solapan -> evento area_entered."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        area_a = self._make_area_entity(world, "ZoneA", x=0.0, y=0.0, width=64.0, height=64.0)
        area_b = self._make_area_entity(world, "ZoneB", x=30.0, y=30.0, width=64.0, height=64.0)

        system.update(world)

        entered = self._get_events_by_name(event_bus, "area_entered")
        # Both areas see each other -> 2 events (one from each area's perspective)
        self.assertEqual(len(entered), 2)

        area2d_a = area_a.get_component(Area2D)
        area2d_b = area_b.get_component(Area2D)
        self.assertIn(area_b.id, area2d_a._tracked_areas)
        self.assertIn(area_a.id, area2d_b._tracked_areas)

    def test_area_exited(self) -> None:
        """Dos areas se separan -> evento area_exited."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        area_a = self._make_area_entity(world, "ZoneA", x=0.0, y=0.0, width=64.0, height=64.0)
        area_b = self._make_area_entity(world, "ZoneB", x=30.0, y=30.0, width=64.0, height=64.0)

        system.update(world)
        event_bus.clear_history()

        # Move area_b away
        area_b.get_component(Transform).x = 500.0
        area_b.get_component(Transform).y = 500.0

        system.update(world)

        exited = self._get_events_by_name(event_bus, "area_exited")
        self.assertEqual(len(exited), 2)

        area2d_a = area_a.get_component(Area2D)
        self.assertNotIn(area_b.id, area2d_a._tracked_areas)

    def test_monitoring_disabled(self) -> None:
        """Area con monitoring=False no emite eventos."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        _area = self._make_area_entity(
            world, "InactiveZone", x=0.0, y=0.0, width=64.0, height=64.0, monitoring=False
        )
        _body = self._make_body_entity(world, "Player", x=10.0, y=10.0)

        system.update(world)

        entered = self._get_events_by_name(event_bus, "body_entered")
        self.assertEqual(len(entered), 0)

    def test_monitorable_false_not_detected(self) -> None:
        """Area con monitorable=False no es detectada por otra area."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        area_a = self._make_area_entity(world, "ZoneA", x=0.0, y=0.0, width=64.0, height=64.0)
        area_b = self._make_area_entity(
            world, "HiddenZone", x=30.0, y=30.0, width=64.0, height=64.0, monitorable=False
        )

        system.update(world)

        # area_a should NOT detect area_b because area_b.monitorable=False
        area2d_a = area_a.get_component(Area2D)
        self.assertNotIn(area_b.id, area2d_a._tracked_areas)

        # area_b (monitoring=True) SHOULD detect area_a (monitorable=True by default)
        area2d_b = area_b.get_component(Area2D)
        self.assertIn(area_a.id, area2d_b._tracked_areas)

    def test_body_not_detected_without_collider(self) -> None:
        """Entidad sin Collider no es detectada."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        _area = self._make_area_entity(world, "TriggerZone", x=0.0, y=0.0, width=64.0, height=64.0)
        body = world.create_entity("Ghost")
        body.add_component(Transform(x=10.0, y=10.0))
        body.add_component(RigidBody())
        # No Collider

        system.update(world)

        entered = self._get_events_by_name(event_bus, "body_entered")
        self.assertEqual(len(entered), 0)

    def test_no_event_bus_does_not_crash(self) -> None:
        """Sistema sin event_bus no crashea."""
        world = World()
        system = Area2DSystem(event_bus=None)

        self._make_area_entity(world, "ZoneA", x=0.0, y=0.0, width=64.0, height=64.0)
        self._make_body_entity(world, "Player", x=10.0, y=10.0)

        system.update(world)
        # No exception = pass

    def test_body_entered_no_duplicate_on_consecutive_frames(self) -> None:
        """body_entered solo se emite la primera vez, no en frames consecutivas."""
        world = World()
        event_bus = EventBus()
        system = Area2DSystem(event_bus=event_bus)

        self._make_area_entity(world, "Zone", x=0.0, y=0.0, width=64.0, height=64.0)
        self._make_body_entity(world, "Player", x=10.0, y=10.0)

        system.update(world)
        event_bus.clear_history()

        # Second frame — body still inside, no new entered
        system.update(world)

        entered = self._get_events_by_name(event_bus, "body_entered")
        self.assertEqual(len(entered), 0)
