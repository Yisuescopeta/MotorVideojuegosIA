"""
Tests para contact_monitor de RigidBody (Godot-like).
"""

import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.systems.collision_system import CollisionSystem


class RigidBodyContactsTests(unittest.TestCase):
    """Tests para monitoreo de contactos en RigidBody."""

    def _make_entity(
        self,
        world: World,
        name: str,
        *,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 10.0,
        height: float = 10.0,
        is_trigger: bool = False,
        layer: str = "Gameplay",
        contact_monitor: bool = False,
        max_contacts_reported: int = 0,
    ):
        entity = world.create_entity(name)
        entity.layer = layer
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(width=width, height=height, is_trigger=is_trigger))
        rb = RigidBody(contact_monitor=contact_monitor, max_contacts_reported=max_contacts_reported)
        entity.add_component(rb)
        return entity

    # --- No contacts when disabled (max_contacts_reported=0) ---

    def test_no_contacts_when_disabled(self) -> None:
        """Contact monitor deshabilitado (max_contacts_reported=0) no reporta contactos."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        cs = CollisionSystem()

        a = self._make_entity(world, "A", x=0.0)
        b = self._make_entity(world, "B", x=5.0)

        cs.update(world)

        rb_a = a.get_component(RigidBody)
        rb_b = b.get_component(RigidBody)
        self.assertEqual(rb_a.get_contact_count(), 0)
        self.assertEqual(rb_b.get_contact_count(), 0)
        self.assertEqual(rb_a.get_colliding_bodies(), [])
        self.assertEqual(rb_b.get_colliding_bodies(), [])

    def test_contact_monitor_true_but_max_zero_reports_none(self) -> None:
        """contact_monitor=True pero max_contacts_reported=0 reporta 0 contactos."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        cs = CollisionSystem()

        a = self._make_entity(world, "A", x=0.0, contact_monitor=True, max_contacts_reported=0)
        self._make_entity(world, "B", x=5.0)

        cs.update(world)

        rb_a = a.get_component(RigidBody)
        self.assertEqual(rb_a.get_contact_count(), 0)

    # --- Enabled tracks colliding bodies ---

    def test_enabled_tracks_colliding_body(self) -> None:
        """contact_monitor=True con max_contacts_reported>0 registra IDs de entidades en colisión."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        cs = CollisionSystem()

        a = self._make_entity(world, "A", x=0.0, contact_monitor=True, max_contacts_reported=10)
        b = self._make_entity(world, "B", x=5.0, contact_monitor=True, max_contacts_reported=10)

        cs.update(world)

        rb_a = a.get_component(RigidBody)
        rb_b = b.get_component(RigidBody)
        self.assertEqual(rb_a.get_contact_count(), 1)
        self.assertEqual(rb_b.get_contact_count(), 1)
        self.assertIn(int(b.id), rb_a.get_colliding_bodies())
        self.assertIn(int(a.id), rb_b.get_colliding_bodies())

    # --- max_contacts_reported limits ---

    def test_max_contacts_reported_limits(self) -> None:
        """max_contacts_reported limita el número de contactos registrados."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        cs = CollisionSystem()

        a = self._make_entity(world, "A", x=0.0, contact_monitor=True, max_contacts_reported=1)
        # Tres entidades que colisionan con A
        self._make_entity(world, "B", x=5.0)
        self._make_entity(world, "C", x=-5.0)
        self._make_entity(world, "D", y=5.0)

        cs.update(world)

        rb_a = a.get_component(RigidBody)
        self.assertEqual(rb_a.get_contact_count(), 1)

    # --- Runtime contact list not serialized ---

    def test_runtime_contacts_not_serialized(self) -> None:
        """Estado runtime _contact_bodies no se incluye en to_dict()."""
        rb = RigidBody(contact_monitor=True, max_contacts_reported=5)
        # Simular contacto registrado
        rb._register_contact(42)
        rb._register_contact(99)

        data = rb.to_dict()
        self.assertNotIn("_contact_bodies", data)
        self.assertIn("contact_monitor", data)
        self.assertIn("max_contacts_reported", data)
        self.assertEqual(data["contact_monitor"], True)
        self.assertEqual(data["max_contacts_reported"], 5)

    def test_contacts_clear_after_update(self) -> None:
        """Contactos se limpian al inicio del siguiente update."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        cs = CollisionSystem()

        a = self._make_entity(world, "A", x=0.0, contact_monitor=True, max_contacts_reported=10)
        b = self._make_entity(world, "B", x=5.0)

        # Frame 1: colisionan
        cs.update(world)
        rb_a = a.get_component(RigidBody)
        self.assertEqual(rb_a.get_contact_count(), 1)

        # Mover B lejos
        b.get_component(Transform).x = 100.0

        # Frame 2: ya no colisionan — contactos deben limpiarse
        cs.update(world)
        self.assertEqual(rb_a.get_contact_count(), 0)
        self.assertEqual(rb_a.get_colliding_bodies(), [])

    # --- Triggers no registran contacts en contact_monitor ---

    def test_trigger_does_not_register_contact(self) -> None:
        """Colisiones trigger no registran contactos en contact_monitor."""
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        cs = CollisionSystem()

        a = self._make_entity(world, "A", x=0.0, contact_monitor=True, max_contacts_reported=10)
        self._make_entity(world, "Trigger", x=5.0, is_trigger=True)

        cs.update(world)

        rb_a = a.get_component(RigidBody)
        self.assertEqual(rb_a.get_contact_count(), 0)

    # --- Default values ---

    def test_default_contact_monitor_off(self) -> None:
        """Por defecto contact_monitor=False y max_contacts_reported=0."""
        rb = RigidBody()
        self.assertFalse(rb.contact_monitor)
        self.assertEqual(rb.max_contacts_reported, 0)

    # --- from_dict legacy data (sin campos nuevos) ---

    def test_from_dict_legacy_no_contacts(self) -> None:
        """from_dict con datos legacy sin contact_monitor usa defaults."""
        rb = RigidBody.from_dict({"velocity_x": 10.0})
        self.assertFalse(rb.contact_monitor)
        self.assertEqual(rb.max_contacts_reported, 0)
        self.assertEqual(rb.get_contact_count(), 0)


if __name__ == "__main__":
    unittest.main()
