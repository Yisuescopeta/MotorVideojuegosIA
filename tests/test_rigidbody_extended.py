"""
Tests para propiedades extendidas de RigidBody:
mass, damping, inertia, center_of_mass, angular_velocity.
"""

import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.physics_system import PhysicsSystem


class RigidBodyExtendedTests(unittest.TestCase):
    """Tests unitarios para las nuevas propiedades del RigidBody."""

    def test_default_values(self) -> None:
        """Creación con mass, damping defaults."""
        rb = RigidBody()
        self.assertEqual(rb.mass, 1.0)
        self.assertEqual(rb.linear_damping, 0.0)
        self.assertEqual(rb.angular_damping, 0.0)
        self.assertEqual(rb.angular_velocity, 0.0)
        self.assertEqual(rb.inertia, 1.0)
        self.assertEqual(rb.center_of_mass_x, 0.0)
        self.assertEqual(rb.center_of_mass_y, 0.0)

    def test_custom_values(self) -> None:
        """Creación con valores personalizados."""
        rb = RigidBody(
            mass=5.0,
            linear_damping=0.2,
            angular_damping=0.1,
            angular_velocity=3.14,
            inertia=10.0,
            center_of_mass_x=1.5,
            center_of_mass_y=-2.0,
        )
        self.assertEqual(rb.mass, 5.0)
        self.assertEqual(rb.linear_damping, 0.2)
        self.assertEqual(rb.angular_damping, 0.1)
        self.assertEqual(rb.angular_velocity, 3.14)
        self.assertEqual(rb.inertia, 10.0)
        self.assertEqual(rb.center_of_mass_x, 1.5)
        self.assertEqual(rb.center_of_mass_y, -2.0)

    def test_serialization_roundtrip(self) -> None:
        """Serialización roundtrip con nuevos campos."""
        rb = RigidBody(
            mass=3.0,
            linear_damping=0.05,
            angular_damping=0.03,
            angular_velocity=1.5,
            inertia=4.0,
            center_of_mass_x=0.5,
            center_of_mass_y=-0.5,
        )
        data = rb.to_dict()
        restored = RigidBody.from_dict(data)
        self.assertEqual(restored.mass, rb.mass)
        self.assertEqual(restored.linear_damping, rb.linear_damping)
        self.assertEqual(restored.angular_damping, rb.angular_damping)
        self.assertEqual(restored.angular_velocity, rb.angular_velocity)
        self.assertEqual(restored.inertia, rb.inertia)
        self.assertEqual(restored.center_of_mass_x, rb.center_of_mass_x)
        self.assertEqual(restored.center_of_mass_y, rb.center_of_mass_y)

    def test_from_dict_legacy_data(self) -> None:
        """Cargar RigidBody antiguo sin campos nuevos."""
        legacy_data = {
            "velocity_x": 100.0,
            "velocity_y": -50.0,
            "gravity_scale": 1.0,
            "is_grounded": False,
            "enabled": True,
        }
        rb = RigidBody.from_dict(legacy_data)
        self.assertEqual(rb.velocity_x, 100.0)
        self.assertEqual(rb.velocity_y, -50.0)
        self.assertEqual(rb.gravity_scale, 1.0)
        self.assertEqual(rb.mass, 1.0)
        self.assertEqual(rb.linear_damping, 0.0)
        self.assertEqual(rb.angular_damping, 0.0)
        self.assertEqual(rb.angular_velocity, 0.0)
        self.assertEqual(rb.inertia, 1.0)
        self.assertEqual(rb.center_of_mass_x, 0.0)
        self.assertEqual(rb.center_of_mass_y, 0.0)

    def test_linear_damping_reduces_velocity(self) -> None:
        """linear_damping aplicado correctamente en PhysicsSystem."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("TestEntity")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        entity.add_component(
            RigidBody(
                gravity_scale=0.0,
                velocity_x=100.0,
                velocity_y=50.0,
                linear_damping=0.5,
                is_grounded=True,
            )
        )
        entity.add_component(Collider(width=10, height=10))

        physics.update(world, 0.016)

        rb = entity.get_component(RigidBody)
        assert rb is not None
        expected_factor = max(0.0, 1.0 - 0.5 * 0.016)
        self.assertAlmostEqual(rb.velocity_x, 100.0 * expected_factor, places=3)
        self.assertAlmostEqual(rb.velocity_y, 50.0 * expected_factor, places=3)

    def test_damping_does_not_go_negative(self) -> None:
        """Damping no hace que velocidad sea negativa (clamped a 0)."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("TestEntity")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        entity.add_component(
            RigidBody(
                gravity_scale=0.0,
                velocity_x=10.0,
                velocity_y=5.0,
                linear_damping=100.0,
                is_grounded=True,
            )
        )
        entity.add_component(Collider(width=10, height=10))

        physics.update(world, 0.016)

        rb = entity.get_component(RigidBody)
        assert rb is not None
        self.assertGreaterEqual(rb.velocity_x, 0.0)
        self.assertGreaterEqual(rb.velocity_y, 0.0)

    def test_angular_velocity_rotates_transform(self) -> None:
        """angular_velocity rota el transform."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("TestEntity")
        transform = Transform(x=0, y=0, rotation=0.0)
        entity.add_component(transform)
        entity.add_component(
            RigidBody(
                gravity_scale=0.0,
                angular_velocity=2.0,
                linear_damping=0.0,
                is_grounded=True,
            )
        )
        entity.add_component(Collider(width=10, height=10))

        physics.update(world, 0.016)

        self.assertAlmostEqual(transform.rotation, 2.0 * 0.016, places=4)

    def test_angular_damping_reduces_angular_velocity(self) -> None:
        """angular_damping amortigua velocidad angular."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("TestEntity")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        entity.add_component(
            RigidBody(
                gravity_scale=0.0,
                angular_velocity=10.0,
                angular_damping=0.5,
                is_grounded=True,
            )
        )
        entity.add_component(Collider(width=10, height=10))

        physics.update(world, 0.016)

        rb = entity.get_component(RigidBody)
        assert rb is not None
        expected_av = 10.0 * max(0.0, 1.0 - 0.5 * 0.016)
        self.assertAlmostEqual(rb.angular_velocity, expected_av, places=4)

    def test_static_body_not_affected_by_damping(self) -> None:
        """Cuerpo static no es afectado por damping."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("StaticEntity")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        entity.add_component(
            RigidBody(
                body_type="static",
                gravity_scale=0.0,
                velocity_x=100.0,
                velocity_y=50.0,
                linear_damping=0.5,
                is_grounded=True,
            )
        )

        physics.update(world, 0.016)

        rb = entity.get_component(RigidBody)
        assert rb is not None
        self.assertEqual(rb.velocity_x, 0.0)
        self.assertEqual(rb.velocity_y, 0.0)


if __name__ == "__main__":
    unittest.main()
