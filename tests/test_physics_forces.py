"""
Tests para apply_force, apply_impulse y apply_torque en RigidBody y EngineAPI.
"""
import unittest

from engine.api._context import EngineAPIContext
from engine.api._runtime_api import RuntimeAPI
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.physics_system import PhysicsSystem


class PhysicsForcesTests(unittest.TestCase):
    """Tests para fuerzas, impulsos y torque."""

    def _make_world_with_entity(self, **kwargs) -> tuple[World, Entity, Transform, RigidBody]:
        world = World()
        entity = world.create_entity("TestEntity")
        transform = Transform(x=0, y=0)
        entity.add_component(transform)
        defaults = {
            "gravity_scale": 0.0,
            "mass": 1.0,
            "inertia": 1.0,
            "linear_damping": 0.0,
            "angular_damping": 0.0,
            "is_grounded": True,
        }
        defaults.update(kwargs)
        rb = RigidBody(**defaults)
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))
        return world, entity, transform, rb

    def test_apply_force_changes_velocity(self) -> None:
        """Aplicar fuerza a cuerpo con mass=1, verificar velocidad aumenta."""
        physics = PhysicsSystem()
        world, entity, transform, rb = self._make_world_with_entity()

        rb.apply_force(100.0, 0.0)
        physics.update(world, 0.016)

        self.assertGreater(rb.velocity_x, 0.0)
        self.assertAlmostEqual(rb.velocity_x, 100.0 * 0.016, places=4)

    def test_apply_impulse_immediate(self) -> None:
        """Impulso cambia velocidad inmediatamente (no depende de dt)."""
        physics = PhysicsSystem()
        world, entity, transform, rb = self._make_world_with_entity()

        rb.apply_impulse(50.0, 25.0)
        physics.update(world, 0.016)

        self.assertAlmostEqual(rb.velocity_x, 50.0, places=4)
        self.assertAlmostEqual(rb.velocity_y, 25.0, places=4)

    def test_apply_torque_angular(self) -> None:
        """Torque afecta angular_velocity."""
        physics = PhysicsSystem()
        world, entity, transform, rb = self._make_world_with_entity()

        rb.apply_torque(10.0)
        physics.update(world, 0.016)

        self.assertAlmostEqual(rb.angular_velocity, 10.0 * 0.016, places=4)

    def test_force_respects_mass(self) -> None:
        """Masa mayor → menor aceleración para misma fuerza."""
        physics = PhysicsSystem()
        world = World()

        # Entidad 1: mass=2
        e1 = world.create_entity("HeavyEntity")
        t1 = Transform(x=0, y=0)
        e1.add_component(t1)
        rb1 = RigidBody(mass=2.0, gravity_scale=0.0, is_grounded=True, linear_damping=0.0)
        e1.add_component(rb1)
        e1.add_component(Collider(width=10, height=10))

        # Entidad 2: mass=1
        e2 = world.create_entity("LightEntity")
        t2 = Transform(x=0, y=100)
        e2.add_component(t2)
        rb2 = RigidBody(mass=1.0, gravity_scale=0.0, is_grounded=True, linear_damping=0.0)
        e2.add_component(rb2)
        e2.add_component(Collider(width=10, height=10))

        rb1.apply_force(100.0, 0.0)
        rb2.apply_force(100.0, 0.0)

        physics.update(world, 0.016)

        # v1 = F/m*dt = 100/2*0.016 = 0.8
        # v2 = 100/1*0.016 = 1.6
        self.assertAlmostEqual(rb1.velocity_x, 0.8, places=4)
        self.assertAlmostEqual(rb2.velocity_x, 1.6, places=4)

    def test_force_buffers_cleared(self) -> None:
        """Después de step, buffers están en 0."""
        physics = PhysicsSystem()
        world, entity, transform, rb = self._make_world_with_entity()

        rb.apply_force(10.0, 5.0)
        rb.apply_impulse(3.0, 2.0)
        rb.apply_torque(1.0)

        physics.update(world, 0.016)

        self.assertEqual(rb._force_buffer_x, 0.0)
        self.assertEqual(rb._force_buffer_y, 0.0)
        self.assertEqual(rb._impulse_buffer_x, 0.0)
        self.assertEqual(rb._impulse_buffer_y, 0.0)
        self.assertEqual(rb._torque_buffer, 0.0)

    def test_api_apply_force(self) -> None:
        """Aplicar fuerza vía EngineAPI RuntimeAPI."""
        world = World()
        entity = world.create_entity("ForceEntity")
        entity.add_component(Transform(x=0, y=0))
        rb = RigidBody(gravity_scale=0.0, mass=1.0, is_grounded=True, linear_damping=0.0)
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        class MockAPI:
            def __init__(self):
                self.game = None
                self.scene_manager = None
                self._project_root = "."
                self._global_state_dir = None
                self._sandbox_paths = False

        mock_api = MockAPI()
        ctx = EngineAPIContext(api=mock_api)
        api = RuntimeAPI(ctx)
        api.require_entity = lambda name: entity

        result = api.apply_force("ForceEntity", 50.0, 0.0)
        self.assertTrue(result)

        physics = PhysicsSystem()
        physics.update(world, 0.016)

        self.assertAlmostEqual(rb.velocity_x, 50.0 * 0.016, places=4)

    def test_api_apply_impulse(self) -> None:
        """Aplicar impulso vía API."""
        world = World()
        entity = world.create_entity("ImpulseEntity")
        entity.add_component(Transform(x=0, y=0))
        rb = RigidBody(gravity_scale=0.0, mass=1.0, is_grounded=True, linear_damping=0.0)
        entity.add_component(rb)
        entity.add_component(Collider(width=10, height=10))

        class MockAPI:
            def __init__(self):
                self.game = None
                self.scene_manager = None
                self._project_root = "."
                self._global_state_dir = None
                self._sandbox_paths = False

        mock_api = MockAPI()
        ctx = EngineAPIContext(api=mock_api)
        api = RuntimeAPI(ctx)
        api.require_entity = lambda name: entity

        result = api.apply_impulse("ImpulseEntity", 30.0, 15.0)
        self.assertTrue(result)

        physics = PhysicsSystem()
        physics.update(world, 0.016)

        self.assertAlmostEqual(rb.velocity_x, 30.0, places=4)
        self.assertAlmostEqual(rb.velocity_y, 15.0, places=4)

    def test_force_on_static_body_ignored(self) -> None:
        """Static body no procesa fuerzas."""
        physics = PhysicsSystem()
        world, entity, transform, rb = self._make_world_with_entity(body_type="static")

        rb.apply_force(100.0, 50.0)
        rb.apply_impulse(20.0, 10.0)
        physics.update(world, 0.016)

        self.assertEqual(rb.velocity_x, 0.0)
        self.assertEqual(rb.velocity_y, 0.0)

    def test_force_serialization_excluded(self) -> None:
        """to_dict NO incluye _force_buffer (runtime-only)."""
        rb = RigidBody()
        rb.apply_force(10.0, 5.0)
        rb.apply_impulse(3.0, 2.0)
        rb.apply_torque(1.0)

        data = rb.to_dict()

        self.assertNotIn("_force_buffer_x", data)
        self.assertNotIn("_force_buffer_y", data)
        self.assertNotIn("_impulse_buffer_x", data)
        self.assertNotIn("_impulse_buffer_y", data)
        self.assertNotIn("_torque_buffer", data)

    def test_force_accumulates_over_frames(self) -> None:
        """Fuerza se acumula entre frames si no se limpia (solo se limpia en step de física)."""
        rb = RigidBody()
        rb.apply_force(10.0, 0.0)
        rb.apply_force(5.0, 0.0)
        self.assertEqual(rb._force_buffer_x, 15.0)
        self.assertEqual(rb._force_buffer_y, 0.0)

    def test_impulse_accumulates_before_step(self) -> None:
        """Múltiples impulsos se acumulan antes del step."""
        rb = RigidBody()
        rb.apply_impulse(10.0, 0.0)
        rb.apply_impulse(5.0, 0.0)
        self.assertEqual(rb._impulse_buffer_x, 15.0)


if __name__ == "__main__":
    unittest.main()
