from __future__ import annotations

import unittest

from engine.components.animatable_body_2d import AnimatableBody2D
from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.static_body_2d import StaticBody2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.systems.physics_system import PhysicsSystem


class StaticBodyVelocityTests(unittest.TestCase):
    """Test that StaticBody2D constant velocity moves the entity."""

    def setUp(self):
        self.world = World()

    def test_static_body_moves_with_constant_velocity(self) -> None:
        """StaticBody2D with velocity moves its Transform each frame."""
        platform = self.world.create_entity("Platform")
        platform.add_component(Transform(x=100.0, y=200.0))
        platform.add_component(StaticBody2D(
            constant_linear_velocity_x=50.0,
            constant_linear_velocity_y=0.0,
        ))

        ps = PhysicsSystem(gravity=0.0)
        ps.update(self.world, 1.0)

        t = platform.get_component(Transform)
        self.assertAlmostEqual(t.x, 150.0, delta=0.01,
                               msg="StaticBody2D should move right by 50px in 1s")
        self.assertAlmostEqual(t.y, 200.0, delta=0.01,
                               msg="StaticBody2D should not move vertically")

    def test_static_body_zero_velocity_stays_put(self) -> None:
        """StaticBody2D with zero velocity doesn't move."""
        platform = self.world.create_entity("Platform")
        platform.add_component(Transform(x=100.0, y=200.0))
        platform.add_component(StaticBody2D(
            constant_linear_velocity_x=0.0,
            constant_linear_velocity_y=0.0,
        ))

        ps = PhysicsSystem(gravity=0.0)
        ps.update(self.world, 0.5)

        t = platform.get_component(Transform)
        self.assertAlmostEqual(t.x, 100.0, delta=0.01)


class AnimatableBodySyncTests(unittest.TestCase):
    """Test AnimatableBody2D.sync_to_physics behavior."""

    def setUp(self):
        self.world = World()

    def test_animatable_body_sync_to_physics_true_is_static(self) -> None:
        """AnimatableBody2D with sync_to_physics=True treated as static."""
        entity = self.world.create_entity("Anim")
        entity.add_component(Transform(x=50.0, y=50.0))
        entity.add_component(Collider(width=16.0, height=16.0))
        entity.add_component(AnimatableBody2D(sync_to_physics=True))

        effective = PhysicsSystem._get_effective_body_type(entity)
        self.assertEqual(effective, "static",
                         "sync_to_physics=True should be treated as static")

    def test_animatable_body_sync_to_physics_false_is_kinematic(self) -> None:
        """AnimatableBody2D with sync_to_physics=False treated as kinematic."""
        entity = self.world.create_entity("Anim")
        entity.add_component(Transform(x=50.0, y=50.0))
        entity.add_component(Collider(width=16.0, height=16.0))
        entity.add_component(AnimatableBody2D(sync_to_physics=False))

        effective = PhysicsSystem._get_effective_body_type(entity)
        self.assertEqual(effective, "kinematic",
                         "sync_to_physics=False without RigidBody should be kinematic")


class CharacterOnPlatformTests(unittest.TestCase):
    """Test character inherits platform velocity."""

    def setUp(self):
        self.world = World()
        self.backend = LegacyAABBPhysicsBackend(None, None)

    def test_move_result_reports_platform_on_floor(self) -> None:
        """When character lands on floor, MoveResult2D includes platform info."""
        platform = self.world.create_entity("MovingPlatform")
        platform.add_component(Transform(x=100.0, y=100.0))
        platform.add_component(Collider(width=64.0, height=8.0))
        platform.add_component(StaticBody2D(
            constant_linear_velocity_x=30.0,
            constant_linear_velocity_y=0.0,
        ))

        player = self.world.create_entity("Player")
        player.add_component(Transform(x=100.0, y=70.0))
        player.add_component(Collider(width=16.0, height=16.0))

        result = self.backend.move_and_slide(
            world=self.world, entity=player,
            velocity=(0.0, 200.0),  # fall down
            delta_time=0.5,
            max_slides=4,
        )

        self.assertTrue(result.on_floor, "Player should land on platform")
        self.assertGreater(result.platform_entity_id, 0,
                           "Should report platform entity ID")
        self.assertGreater(abs(result.platform_velocity_x), 0.0,
                           "Should capture platform horizontal velocity")

    def test_platform_on_leave_add_velocity(self) -> None:
        """Jumping off moving platform adds velocity."""
        controller = CharacterController2D(
            platform_on_leave="add_velocity",
            platform_entity_name="MovingPlatform",
        )
        self.assertEqual(controller.platform_on_leave, "add_velocity")

    def test_platform_on_leave_add_upward(self) -> None:
        """Platform on leave with upward only mode."""
        controller = CharacterController2D(
            platform_on_leave="add_upward_velocity",
        )
        self.assertEqual(controller.platform_on_leave, "add_upward_velocity")

    def test_platform_on_leave_do_nothing(self) -> None:
        """Platform on leave with do_nothing mode."""
        controller = CharacterController2D(
            platform_on_leave="do_nothing",
        )
        self.assertEqual(controller.platform_on_leave, "do_nothing")

    def test_platform_on_leave_invalid_defaults(self) -> None:
        """Invalid platform_on_leave value defaults to add_velocity."""
        controller = CharacterController2D(
            platform_on_leave="invalid_mode",
        )
        self.assertEqual(controller.platform_on_leave, "add_velocity")

    def test_platform_fields_serialize_roundtrip(self) -> None:
        """platform_on_leave and platform_entity_name survive serialization."""
        controller = CharacterController2D(
            platform_on_leave="do_nothing",
            platform_entity_name="Elevator_A",
        )
        data = controller.to_dict()
        restored = CharacterController2D.from_dict(data)
        self.assertEqual(restored.platform_on_leave, "do_nothing")
        self.assertEqual(restored.platform_entity_name, "Elevator_A")
