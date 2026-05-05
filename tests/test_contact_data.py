import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.physics.contact_data import ContactManifold2D, ContactPoint2D
from engine.physics.shapes import AABBShape, CapsuleShape, CircleShape, PolygonShape
from engine.systems.collision_system import CollisionSystem


class ContactDataTests(unittest.TestCase):
    def test_contact_point_creation(self) -> None:
        cp = ContactPoint2D(point_x=10.0, point_y=20.0, normal_x=1.0, normal_y=0.0, depth=5.0)
        self.assertEqual(cp.point_x, 10.0)
        self.assertEqual(cp.point_y, 20.0)
        self.assertEqual(cp.normal_x, 1.0)
        self.assertEqual(cp.normal_y, 0.0)
        self.assertEqual(cp.depth, 5.0)

    def test_contact_point_defaults(self) -> None:
        cp = ContactPoint2D()
        self.assertEqual(cp.point_x, 0.0)
        self.assertEqual(cp.point_y, 0.0)
        self.assertEqual(cp.normal_x, 0.0)
        self.assertEqual(cp.normal_y, 0.0)
        self.assertEqual(cp.depth, 0.0)

    def test_contact_manifold_creation(self) -> None:
        cp = ContactPoint2D(point_x=5.0, point_y=5.0, depth=3.0)
        manifold = ContactManifold2D(
            entity_a_id=1,
            entity_b_id=2,
            entity_a_name="Player",
            entity_b_name="Wall",
            normal_x=-1.0,
            normal_y=0.0,
            depth=3.0,
            impulse_x=10.0,
            impulse_y=0.0,
            relative_velocity_x=-5.0,
            relative_velocity_y=0.0,
            contact_count=1,
            contacts=[cp],
            is_trigger=False,
        )
        self.assertEqual(manifold.entity_a_id, 1)
        self.assertEqual(manifold.entity_b_id, 2)
        self.assertEqual(manifold.entity_a_name, "Player")
        self.assertEqual(manifold.entity_b_name, "Wall")
        self.assertEqual(manifold.normal_x, -1.0)
        self.assertEqual(manifold.normal_y, 0.0)
        self.assertEqual(manifold.depth, 3.0)
        self.assertEqual(manifold.impulse_x, 10.0)
        self.assertEqual(manifold.impulse_y, 0.0)
        self.assertEqual(manifold.relative_velocity_x, -5.0)
        self.assertEqual(manifold.relative_velocity_y, 0.0)
        self.assertEqual(manifold.contact_count, 1)
        self.assertEqual(len(manifold.contacts), 1)
        self.assertEqual(manifold.contacts[0].point_x, 5.0)
        self.assertFalse(manifold.is_trigger)

    def test_contact_manifold_defaults(self) -> None:
        manifold = ContactManifold2D()
        self.assertEqual(manifold.entity_a_id, 0)
        self.assertEqual(manifold.entity_b_id, 0)
        self.assertEqual(manifold.entity_a_name, "")
        self.assertEqual(manifold.entity_b_name, "")
        self.assertEqual(manifold.normal_x, 0.0)
        self.assertEqual(manifold.normal_y, 0.0)
        self.assertEqual(manifold.depth, 0.0)
        self.assertEqual(manifold.impulse_x, 0.0)
        self.assertEqual(manifold.impulse_y, 0.0)
        self.assertEqual(manifold.relative_velocity_x, 0.0)
        self.assertEqual(manifold.relative_velocity_y, 0.0)
        self.assertEqual(manifold.contact_count, 0)
        self.assertEqual(manifold.contacts, [])
        self.assertFalse(manifold.is_trigger)

    def test_contact_manifold_serialization_roundtrip(self) -> None:
        cp = ContactPoint2D(point_x=5.0, point_y=5.0, depth=3.0)
        manifold = ContactManifold2D(
            entity_a_id=1,
            entity_b_id=2,
            entity_a_name="Player",
            entity_b_name="Wall",
            normal_x=-1.0,
            normal_y=0.0,
            depth=3.0,
            contact_count=1,
            contacts=[cp],
        )
        d = manifold.to_dict()
        self.assertEqual(d["entity_a_id"], 1)
        self.assertEqual(d["entity_b_id"], 2)
        self.assertEqual(d["entity_a_name"], "Player")
        self.assertEqual(d["entity_b_name"], "Wall")
        self.assertEqual(d["normal_x"], -1.0)
        self.assertEqual(d["normal_y"], 0.0)
        self.assertEqual(d["depth"], 3.0)
        self.assertEqual(d["contact_count"], 1)
        self.assertEqual(len(d["contacts"]), 1)
        self.assertEqual(d["contacts"][0]["point_x"], 5.0)
        self.assertFalse(d["is_trigger"])

    def test_collision_normal_horizontal(self) -> None:
        """Two AABBs colliding horizontally: normal points correctly."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        a = world.create_entity("A")
        a.layer = "Gameplay"
        a.add_component(Transform(x=0.0, y=0.0))
        a.add_component(Collider(width=10.0, height=10.0))

        b = world.create_entity("B")
        b.layer = "Gameplay"
        b.add_component(Transform(x=6.0, y=0.0))
        b.add_component(Collider(width=10.0, height=10.0))

        collision_system.update(world)

        contact_events = [e for e in event_bus.get_recent_events() if e.name == "collision_contact"]
        self.assertEqual(len(contact_events), 1)
        data = contact_events[0].data

        self.assertNotEqual(data["normal_x"], 0.0)
        self.assertEqual(data["normal_y"], 0.0)
        self.assertGreater(data["depth"], 0.0)

        collision_events = [e for e in event_bus.get_recent_events() if e.name == "on_collision"]
        self.assertEqual(len(collision_events), 1)

    def test_collision_normal_vertical(self) -> None:
        """Two AABBs colliding vertically: normal points correctly."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        a = world.create_entity("A")
        a.layer = "Gameplay"
        a.add_component(Transform(x=0.0, y=0.0))
        a.add_component(Collider(width=10.0, height=10.0))

        b = world.create_entity("B")
        b.layer = "Gameplay"
        b.add_component(Transform(x=0.0, y=6.0))
        b.add_component(Collider(width=10.0, height=10.0))

        collision_system.update(world)

        contact_events = [e for e in event_bus.get_recent_events() if e.name == "collision_contact"]
        self.assertEqual(len(contact_events), 1)
        data = contact_events[0].data

        self.assertEqual(data["normal_x"], 0.0)
        self.assertNotEqual(data["normal_y"], 0.0)
        self.assertGreater(data["depth"], 0.0)

    def test_collision_relative_velocity(self) -> None:
        """Two bodies with opposite velocities produce correct relative velocity."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        a = world.create_entity("A")
        a.layer = "Gameplay"
        a.add_component(Transform(x=0.0, y=0.0))
        a.add_component(Collider(width=10.0, height=10.0))
        a.add_component(RigidBody(velocity_x=100.0, velocity_y=50.0))

        b = world.create_entity("B")
        b.layer = "Gameplay"
        b.add_component(Transform(x=6.0, y=0.0))
        b.add_component(Collider(width=10.0, height=10.0))
        b.add_component(RigidBody(velocity_x=-30.0, velocity_y=20.0))

        collision_system.update(world)

        contact_events = [e for e in event_bus.get_recent_events() if e.name == "collision_contact"]
        self.assertEqual(len(contact_events), 1)
        data = contact_events[0].data

        self.assertEqual(data["relative_velocity_x"], 130.0)  # 100 - (-30)
        self.assertEqual(data["relative_velocity_y"], 30.0)   # 50 - 20

    def test_collision_contact_event_fields(self) -> None:
        """Verify collision_contact event contains all expected fields."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        a = world.create_entity("Player")
        a.layer = "Gameplay"
        a.add_component(Transform(x=0.0, y=0.0))
        a.add_component(Collider(width=10.0, height=10.0))

        b = world.create_entity("Wall")
        b.layer = "Gameplay"
        b.add_component(Transform(x=6.0, y=0.0))
        b.add_component(Collider(width=10.0, height=10.0))

        collision_system.update(world)

        contact_events = [e for e in event_bus.get_recent_events() if e.name == "collision_contact"]
        self.assertEqual(len(contact_events), 1)
        data = contact_events[0].data

        self.assertIn("entity_a_id", data)
        self.assertIn("entity_b_id", data)
        self.assertIn("entity_a_name", data)
        self.assertIn("entity_b_name", data)
        self.assertIn("normal_x", data)
        self.assertIn("normal_y", data)
        self.assertIn("depth", data)
        self.assertIn("impulse_x", data)
        self.assertIn("impulse_y", data)
        self.assertIn("relative_velocity_x", data)
        self.assertIn("relative_velocity_y", data)
        self.assertIn("contact_count", data)
        self.assertIn("contacts", data)
        self.assertIn("is_trigger", data)

        self.assertGreater(data["contact_count"], 0)
        self.assertEqual(len(data["contacts"]), data["contact_count"])
        self.assertFalse(data["is_trigger"])

    def test_capsule_manifold_to_dict(self) -> None:
        """CapsuleShape manifold to_dict tiene campos completos."""
        cap = CapsuleShape(0, 0, 8, 32)
        box = AABBShape(14, 0, 10, 10)
        m = cap.collide_shape(box)
        assert m is not None
        d = m.to_dict()
        assert d["depth"] > 0
        assert abs(d["normal_x"]) > 0 or abs(d["normal_y"]) > 0
        assert d["contact_count"] >= 1
        assert len(d["contacts"]) == d["contact_count"]
        cp = d["contacts"][0]
        assert "point_x" in cp
        assert "point_y" in cp
        assert "depth" in cp

    def test_polygon_manifold_to_dict(self) -> None:
        """PolygonShape manifold to_dict tiene campos completos."""
        a = PolygonShape([(0, 0), (20, 0), (20, 20), (0, 20)])
        b = PolygonShape([(10, 10), (30, 10), (30, 30), (10, 30)])
        m = a.collide_shape(b)
        assert m is not None
        d = m.to_dict()
        assert d["depth"] > 0
        assert abs(d["normal_x"]) > 0 or abs(d["normal_y"]) > 0
        assert d["contact_count"] >= 1
        assert len(d["contacts"]) == d["contact_count"]

    def test_capsule_manifold_roundtrip(self) -> None:
        """Capsule manifold a dict y reconstrucción mantiene depth."""
        cap = CapsuleShape(0, 0, 5, 20)
        circle = CircleShape(8, 0, 5)
        m = cap.collide_shape(circle)
        assert m is not None
        d = m.to_dict()
        assert "depth" in d
        assert d["depth"] > 0

    def test_trigger_emits_collision_contact(self) -> None:
        """Trigger collisions also emit collision_contact with is_trigger=True."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        a = world.create_entity("A")
        a.layer = "Gameplay"
        a.add_component(Transform(x=0.0, y=0.0))
        a.add_component(Collider(width=10.0, height=10.0, is_trigger=True))

        b = world.create_entity("B")
        b.layer = "Gameplay"
        b.add_component(Transform(x=6.0, y=0.0))
        b.add_component(Collider(width=10.0, height=10.0))

        collision_system.update(world)

        contact_events = [e for e in event_bus.get_recent_events() if e.name == "collision_contact"]
        self.assertEqual(len(contact_events), 1)
        self.assertTrue(contact_events[0].data["is_trigger"])


if __name__ == "__main__":
    unittest.main()
