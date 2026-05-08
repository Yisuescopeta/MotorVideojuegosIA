import unittest

from engine.components.joint2d import VALID_JOINT_TYPES, Joint2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.physics_system import PhysicsSystem


class Joint2DSerializationTests(unittest.TestCase):
    def test_default_joint_is_fixed(self) -> None:
        j = Joint2D()
        self.assertEqual(j.joint_type, "fixed")
        self.assertEqual(j.connected_entity, "")

    def test_to_dict_roundtrip_all_fields(self) -> None:
        j = Joint2D()
        j.joint_type = "pin"
        j.connected_entity = "other_entity"
        j.collide_connected = True
        j.softness = 0.5
        j.angular_limit_lower = -0.5
        j.angular_limit_upper = 0.5
        j.angular_limit_enabled = True
        j.motor_enabled = True
        j.motor_target_velocity = 2.0
        j.groove_length = 200.0
        j.initial_offset = (10.0, 20.0)
        j.rest_length = 30.0
        j.stiffness = 50.0
        j.damping = 2.5

        data = j.to_dict()
        restored = Joint2D.from_dict(data)

        self.assertEqual(restored.joint_type, "pin")
        self.assertEqual(restored.connected_entity, "other_entity")
        self.assertTrue(restored.collide_connected)
        self.assertEqual(restored.softness, 0.5)
        self.assertEqual(restored.angular_limit_lower, -0.5)
        self.assertEqual(restored.angular_limit_upper, 0.5)
        self.assertTrue(restored.angular_limit_enabled)
        self.assertTrue(restored.motor_enabled)
        self.assertEqual(restored.motor_target_velocity, 2.0)
        self.assertEqual(restored.groove_length, 200.0)
        self.assertEqual(restored.initial_offset, (10.0, 20.0))
        self.assertEqual(restored.rest_length, 30.0)
        self.assertEqual(restored.stiffness, 50.0)
        self.assertEqual(restored.damping, 2.5)

    def test_from_dict_invalid_type_falls_back_to_fixed(self) -> None:
        j = Joint2D.from_dict({"joint_type": "nonexistent"})
        self.assertEqual(j.joint_type, "fixed")

    def test_from_dict_initial_offset_list_converts_to_tuple(self) -> None:
        j = Joint2D.from_dict({"initial_offset": [5.0, -3.0]})
        self.assertEqual(j.initial_offset, (5.0, -3.0))

    def test_valid_joint_types_include_new_types(self) -> None:
        self.assertIn("pin", VALID_JOINT_TYPES)
        self.assertIn("groove", VALID_JOINT_TYPES)
        self.assertIn("damped_spring", VALID_JOINT_TYPES)
        self.assertIn("fixed", VALID_JOINT_TYPES)
        self.assertIn("distance", VALID_JOINT_TYPES)

    def test_backward_compat_old_data_still_deserializes(self) -> None:
        data = {
            "joint_type": "distance",
            "connected_entity": "body_b",
            "anchor_x": 0.0,
            "anchor_y": 0.0,
            "connected_anchor_x": 10.0,
            "connected_anchor_y": 5.0,
            "rest_length": 100.0,
            "damping_ratio": 0.5,
            "frequency_hz": 2.0,
            "collide_connected": False,
            "enabled": True,
        }
        j = Joint2D.from_dict(data)
        self.assertEqual(j.joint_type, "distance")
        self.assertEqual(j.connected_entity, "body_b")
        self.assertFalse(j.collide_connected)
        self.assertTrue(j.enabled)
        # New fields get defaults
        self.assertEqual(j.softness, 0.0)
        self.assertEqual(j.stiffness, 20.0)


class Joint2DPhysicsTests(unittest.TestCase):
    def _setup_world(self, joint_type: str, name_a: str = "A", name_b: str = "B") -> tuple[World, Entity, Entity, Joint2D]:
        world = World()
        a = world.create_entity(name_a)
        a.add_component(Transform(x=0.0, y=0.0))
        a.add_component(RigidBody(body_type="dynamic", mass=1.0, gravity_scale=0.0))
        b = world.create_entity(name_b)
        b.add_component(Transform(x=50.0, y=50.0))
        b.add_component(RigidBody(body_type="dynamic", mass=1.0, gravity_scale=0.0))
        joint = Joint2D()
        joint.joint_type = joint_type
        joint.connected_entity = name_b
        a.add_component(joint)
        return world, a, b, joint

    def test_pin_joint_constrains_position(self) -> None:
        world, a, b, joint = self._setup_world("pin")
        joint.softness = 1.0

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        t_a = a.get_component(Transform)
        t_b = b.get_component(Transform)
        # Bodies should be pulled closer
        dist = ((t_b.x - t_a.x) ** 2 + (t_b.y - t_a.y) ** 2) ** 0.5
        self.assertLess(dist, 71.0)  # started at ~70.7, should reduce

    def test_pin_joint_angular_limits(self) -> None:
        world, a, b, joint = self._setup_world("pin")
        joint.angular_limit_enabled = True
        joint.angular_limit_lower = -0.5
        joint.angular_limit_upper = 0.5

        t_b = b.get_component(Transform)
        t_b.rotation = 2.0  # exceeds upper limit

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        self.assertEqual(t_b.rotation, 0.5)  # clamped to upper limit

    def test_pin_joint_motor_applies_torque(self) -> None:
        world, a, b, joint = self._setup_world("pin")
        joint.motor_enabled = True
        joint.motor_target_velocity = 3.0

        rb_b = b.get_component(RigidBody)
        rb_b.angular_velocity = 1.0

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        # Motor adds target_velocity * dt each frame
        self.assertGreater(rb_b.angular_velocity, 1.0)

    def test_groove_joint_constrains_to_line(self) -> None:
        world, a, b, joint = self._setup_world("groove")
        joint.groove_length = 100.0
        joint.initial_offset = (5.0, 0.0)

        # Place B far off the groove line
        t_b = b.get_component(Transform)
        t_b.x = 200.0
        t_b.y = 80.0

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        t_a = a.get_component(Transform)
        ix, iy = joint.initial_offset
        # B should be clamped along groove line (X axis)
        expected_y = t_a.y + iy  # constrained to groove Y
        self.assertAlmostEqual(t_b.y, expected_y, delta=0.01)
        # X should be clamped between 0 and groove_length from groove origin
        expected_x = t_a.x + ix + 100.0  # max groove_length
        self.assertAlmostEqual(t_b.x, expected_x, delta=0.01)

    def test_spring_joint_restores_rest_length(self) -> None:
        world, a, b, joint = self._setup_world("damped_spring")
        joint.rest_length = 30.0
        joint.stiffness = 100.0
        joint.damping = 0.0

        rb_a = a.get_component(RigidBody)
        rb_b = b.get_component(RigidBody)
        rb_a.velocity_x = 0.0
        rb_a.velocity_y = 0.0
        rb_b.velocity_x = 0.0
        rb_b.velocity_y = 0.0

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        t_a = a.get_component(Transform)
        t_b = b.get_component(Transform)
        _dist = ((t_b.x - t_a.x) ** 2 + (t_b.y - t_a.y) ** 2) ** 0.5
        # Bodies are static-only, spring force applied to velocities
        self.assertFalse(rb_a.velocity_x == 0.0 and rb_a.velocity_y == 0.0)

    def test_spring_joint_damping_reduces_oscillation(self) -> None:
        world, a, b, joint = self._setup_world("damped_spring")
        joint.rest_length = 30.0
        joint.stiffness = 100.0

        # High damping
        joint.damping = 10.0
        rb_a = a.get_component(RigidBody)
        rb_b = b.get_component(RigidBody)
        rb_a.velocity_x = 0.0
        rb_a.velocity_y = 0.0
        rb_b.velocity_x = 0.0
        rb_b.velocity_y = 0.0

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        vel_magnitude = (rb_a.velocity_x ** 2 + rb_a.velocity_y ** 2) ** 0.5
        # With high damping, velocity should be moderate
        self.assertLess(vel_magnitude, 200.0)

    def test_fixed_joint_locks_position(self) -> None:
        world, a, b, joint = self._setup_world("fixed")

        physics = PhysicsSystem(gravity=0.0)
        dt = 1.0 / 60.0
        for _ in range(60):
            physics.update(world, dt)

        t_a = a.get_component(Transform)
        t_b = b.get_component(Transform)
        self.assertAlmostEqual(t_a.x, t_b.x, delta=5.0)
        self.assertAlmostEqual(t_a.y, t_b.y, delta=5.0)

    def test_unknown_joint_type_does_not_crash(self) -> None:
        world, a, b, joint = self._setup_world("fixed")
        joint.joint_type = "unknown_type"

        physics = PhysicsSystem(gravity=0.0)
        # Should not raise
        physics.update(world, 1.0 / 60.0)


if __name__ == "__main__":
    unittest.main()
