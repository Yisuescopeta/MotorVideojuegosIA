"""
Tests para propiedades extendidas de RigidBody:
mass, damping, inertia, center_of_mass, angular_velocity.
"""

import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
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


class RigidBodySleepingTests(unittest.TestCase):
    """Tests para el sistema de sleeping (Godot parity)."""

    def test_sleeping_threshold(self) -> None:
        """Body with very low velocity should eventually sleep."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("Sleepy")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=0.1,
            velocity_y=0.0,
            can_sleep=True,
            sleep_linear_threshold=0.5,
            sleep_angular_threshold=0.1,
            time_to_sleep=0.3,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        # Before threshold: not sleeping
        physics.update(world, 0.1)
        self.assertFalse(rb.sleeping)
        self.assertGreater(rb._sleep_timer, 0.0)

        # After time_to_sleep accumulated: should sleep
        physics.update(world, 0.1)
        physics.update(world, 0.1)
        self.assertTrue(rb.sleeping)
        self.assertEqual(rb.velocity_x, 0.0)
        self.assertEqual(rb.velocity_y, 0.0)
        self.assertEqual(rb.angular_velocity, 0.0)

    def test_high_velocity_prevents_sleep(self) -> None:
        """Fast-moving body never sleeps."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("Speedy")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=100.0,
            velocity_y=0.0,
            can_sleep=True,
            sleep_linear_threshold=0.5,
            time_to_sleep=0.1,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        for _ in range(10):
            physics.update(world, 0.1)
        self.assertFalse(rb.sleeping)
        self.assertEqual(rb._sleep_timer, 0.0)

    def test_wake_on_force(self) -> None:
        """Applying force wakes a sleeping body."""
        _physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("Waker")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=0.0,
            velocity_y=0.0,
            can_sleep=True,
            sleeping=True,
            time_to_sleep=0.1,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        self.assertTrue(rb.sleeping)
        rb.apply_force(10.0, 0.0)
        self.assertFalse(rb.sleeping)
        self.assertEqual(rb._sleep_timer, 0.0)

    def test_can_sleep_disabled(self) -> None:
        """can_sleep=False prevents sleeping entirely."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("Insomniac")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=0.0,
            velocity_y=0.0,
            can_sleep=False,
            time_to_sleep=0.1,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        for _ in range(10):
            physics.update(world, 0.1)
        self.assertFalse(rb.sleeping)


class RigidBodyConstantForceTests(unittest.TestCase):
    """Tests para fuerzas constantes (applied every frame)."""

    def test_constant_force_accelerates_body(self) -> None:
        """Constant force should accelerate body each frame."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("ConstForce")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=0.0,
            velocity_y=0.0,
            mass=2.0,
            constant_force_x=10.0,
            constant_force_y=0.0,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        dt = 0.016
        physics.update(world, dt)
        expected_vx = (10.0 / 2.0) * dt  # F/m * dt
        self.assertAlmostEqual(rb.velocity_x, expected_vx, places=5)

    def test_constant_force_not_consumed(self) -> None:
        """Constant force is reapplied every frame (not consumed)."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("ConstForce2")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=0.0,
            velocity_y=0.0,
            mass=1.0,
            constant_force_x=5.0,
            constant_force_y=0.0,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        dt = 0.016
        physics.update(world, dt)
        vx_after_1 = rb.velocity_x
        physics.update(world, dt)
        vx_after_2 = rb.velocity_x
        # Each frame adds the same amount
        self.assertAlmostEqual(vx_after_2 - vx_after_1, vx_after_1, places=5)

    def test_constant_torque_spins_body(self) -> None:
        """Constant torque accelerates angular velocity each frame."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("TorqueBody")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            angular_velocity=0.0,
            inertia=2.0,
            constant_torque=4.0,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        dt = 0.016
        physics.update(world, dt)
        expected_av = (4.0 / 2.0) * dt  # torque / inertia * dt
        self.assertAlmostEqual(rb.angular_velocity, expected_av, places=5)


class RigidBodyLockRotationTests(unittest.TestCase):
    """Tests para lock_rotation."""

    def test_lock_rotation_zeroes_angular_velocity(self) -> None:
        """lock_rotation=True keeps angular_velocity at 0 after integration."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("Locked")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            angular_velocity=5.0,
            lock_rotation=True,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        physics.update(world, 0.016)
        self.assertEqual(rb.angular_velocity, 0.0)

    def test_lock_rotation_off_allows_spin(self) -> None:
        """lock_rotation=False allows angular velocity."""
        physics = PhysicsSystem()
        world = World()
        entity = world.create_entity("FreeSpinner")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        rb = RigidBody(
            gravity_scale=0.0,
            angular_velocity=5.0,
            lock_rotation=False,
            angular_damping=0.0,
            is_grounded=True,
        )
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        physics.update(world, 0.016)
        self.assertEqual(rb.angular_velocity, 5.0)


class RigidBodyCCDTests(unittest.TestCase):
    """Tests para CCD (continuous collision detection)."""

    def test_ccd_mode_default(self) -> None:
        """Default ccd_mode is 'disabled'."""
        rb = RigidBody()
        self.assertEqual(rb.ccd_mode, "disabled")

    def test_ccd_mode_custom(self) -> None:
        """Can set ccd_mode."""
        rb = RigidBody(ccd_mode="cast_ray")
        self.assertEqual(rb.ccd_mode, "cast_ray")

    def test_ccd_mode_invalid_falls_back(self) -> None:
        """Invalid ccd_mode falls back to disabled."""
        rb = RigidBody(ccd_mode="invalid")
        self.assertEqual(rb.ccd_mode, "disabled")

    def test_ccd_uses_sweeping(self) -> None:
        """ccd_mode != 'disabled' activates swept motion — body stops at wall,
        not tunneling through. Velocity zeroes when overlap resolves."""
        physics = PhysicsSystem()
        world = World()
        # Static wall
        wall = world.create_entity("Wall")
        wall_transform = Transform(x=10, y=0)
        wall.add_component(wall_transform)
        wall_collider = Collider(width=100, height=200)
        wall.add_component(wall_collider)
        wall.add_component(RigidBody(body_type="static"))

        # Fast body placed inside wall's vertical extent
        body = world.create_entity("Bullet")
        body_transform = Transform(x=12, y=50)  # already slightly inside wall
        body.add_component(body_transform)
        body_collider = Collider(width=5, height=5)
        body.add_component(body_collider)
        body_rb = RigidBody(
            gravity_scale=0.0,
            velocity_x=500.0,
            ccd_mode="cast_ray",
            is_grounded=True,
            body_type="dynamic",
        )
        body.add_component(body_rb)

        physics.update(world, 0.016)
        # With CCD active, the_resolve_horizontal pushes body back and zeroes vx
        # Body was at x=12 (right edge 17), wall starts at x=10
        # resolve pushes it left so right edge ≤ 10
        self.assertLessEqual(body_transform.x + 5, 10)
        self.assertEqual(body_rb.velocity_x, 0.0)


class RigidBodySerializationTests(unittest.TestCase):
    """Tests de serialización para nuevos campos."""

    def test_new_fields_roundtrip(self) -> None:
        """All new fields survive to_dict/from_dict roundtrip."""
        rb = RigidBody(
            ccd_mode="cast_shape",
            can_sleep=False,
            sleeping=True,
            sleep_linear_threshold=0.3,
            sleep_angular_threshold=0.05,
            time_to_sleep=1.0,
            custom_integrator=True,
            constant_force_x=100.0,
            constant_force_y=-9.8,
            constant_torque=0.5,
            center_of_mass_mode="custom",
            linear_damp_mode="replace",
            angular_damp_mode="replace",
            lock_rotation=True,
        )
        data = rb.to_dict()
        restored = RigidBody.from_dict(data)

        self.assertEqual(restored.ccd_mode, "cast_shape")
        self.assertFalse(restored.can_sleep)
        self.assertTrue(restored.sleeping)
        self.assertEqual(restored.sleep_linear_threshold, 0.3)
        self.assertEqual(restored.sleep_angular_threshold, 0.05)
        self.assertEqual(restored.time_to_sleep, 1.0)
        self.assertTrue(restored.custom_integrator)
        self.assertEqual(restored.constant_force_x, 100.0)
        self.assertEqual(restored.constant_force_y, -9.8)
        self.assertEqual(restored.constant_torque, 0.5)
        self.assertEqual(restored.center_of_mass_mode, "custom")
        self.assertEqual(restored.linear_damp_mode, "replace")
        self.assertEqual(restored.angular_damp_mode, "replace")
        self.assertTrue(restored.lock_rotation)

    def test_new_fields_defaults_from_legacy_data(self) -> None:
        """Legacy data without new fields gets correct defaults."""
        legacy = {"velocity_x": 42.0, "velocity_y": 7.0}
        rb = RigidBody.from_dict(legacy)
        self.assertEqual(rb.ccd_mode, "disabled")
        self.assertTrue(rb.can_sleep)
        self.assertFalse(rb.sleeping)
        self.assertEqual(rb.sleep_linear_threshold, 0.5)
        self.assertEqual(rb.sleep_angular_threshold, 0.1)
        self.assertEqual(rb.time_to_sleep, 0.5)
        self.assertFalse(rb.custom_integrator)
        self.assertEqual(rb.constant_force_x, 0.0)
        self.assertEqual(rb.constant_force_y, 0.0)
        self.assertEqual(rb.constant_torque, 0.0)
        self.assertEqual(rb.center_of_mass_mode, "auto")
        self.assertEqual(rb.linear_damp_mode, "combine")
        self.assertEqual(rb.angular_damp_mode, "combine")
        self.assertFalse(rb.lock_rotation)


if __name__ == "__main__":
    unittest.main()
