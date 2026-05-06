from __future__ import annotations

import unittest

from engine.components.collider import Collider
from engine.components.collision_shape_set_2d import CollisionShape2DDef, CollisionShapeSet2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend


class BodyTestMotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.backend = LegacyAABBPhysicsBackend(None, None)

    # ------------------------------------------------------------------
    # test_01: no collision returns full travel
    # ------------------------------------------------------------------
    def test_01_no_collision_returns_full_travel(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=100.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        result = self.backend.body_test_motion(self.world, mover, (200.0, 0.0))

        self.assertEqual(result.travel_x, 200.0)
        self.assertEqual(result.travel_y, 0.0)
        self.assertEqual(result.remainder_x, 0.0)
        self.assertEqual(result.remainder_y, 0.0)
        self.assertEqual(result.collision_safe_fraction, 1.0)
        self.assertEqual(result.collider_id, 0)

    # ------------------------------------------------------------------
    # test_02: hits wall from left
    # ------------------------------------------------------------------
    def test_02_hits_wall_from_left(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody(velocity_x=0.0, velocity_y=0.0))
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertLess(result.collision_safe_fraction, 1.0,
                        "Should detect collision (safe_fraction < 1.0)")
        # gap = wall_left(42) - mover_right(8) = 34
        self.assertAlmostEqual(result.travel_x, 34.0, delta=0.5)
        # normal should point left (against motion)
        self.assertAlmostEqual(result.collision_normal_x, -1.0, delta=0.01)
        self.assertEqual(result.collider_entity_name, "Wall")

    # ------------------------------------------------------------------
    # test_03: hits floor from above
    # ------------------------------------------------------------------
    def test_03_hits_floor_from_above(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=100.0, y=0.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        floor = self.world.create_entity("Floor")
        floor.add_component(Transform(x=0.0, y=50.0))
        floor.add_component(RigidBody(velocity_x=0.0, velocity_y=0.0))
        floor.add_component(Collider(width=200.0, height=16.0))

        result = self.backend.body_test_motion(self.world, mover, (0.0, 100.0))

        self.assertLess(result.collision_safe_fraction, 1.0)
        self.assertLess(result.travel_y, 100.0, "Should stop before full 100px sweep")
        self.assertAlmostEqual(result.collision_normal_y, -1.0, delta=0.01,
                               msg="Normal should point up")

    # ------------------------------------------------------------------
    # test_04: does not mutate transform
    # ------------------------------------------------------------------
    def test_04_does_not_mutate_transform(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=0.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        transform = mover.get_component(Transform)
        assert transform is not None
        x_before = transform.x
        y_before = transform.y

        self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertEqual(transform.x, x_before,
                         "body_test_motion must NOT mutate transform.x")
        self.assertEqual(transform.y, y_before,
                         "body_test_motion must NOT mutate transform.y")

    # ------------------------------------------------------------------
    # test_05: safe_fraction between 0 and 1 when collision occurs
    # ------------------------------------------------------------------
    def test_05_safe_fraction_between_0_and_1(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertGreater(result.collision_safe_fraction, 0.0)
        self.assertLess(result.collision_safe_fraction, 1.0)

    # ------------------------------------------------------------------
    # test_06: remainder + travel == total motion
    # ------------------------------------------------------------------
    def test_06_remainder_plus_travel_equals_motion(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertAlmostEqual(result.travel_x + result.remainder_x, 100.0, delta=0.001,
                               msg="travel_x + remainder_x must equal motion_x")
        self.assertAlmostEqual(result.travel_y + result.remainder_y, 0.0, delta=0.001,
                               msg="travel_y + remainder_y must equal motion_y")

    # ------------------------------------------------------------------
    # test_07: zero motion returns zero travel
    # ------------------------------------------------------------------
    def test_07_zero_motion_returns_zero_travel(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=0.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        result = self.backend.body_test_motion(self.world, mover, (0.0, 0.0))

        self.assertEqual(result.travel_x, 0.0)
        self.assertEqual(result.travel_y, 0.0)
        self.assertEqual(result.collision_safe_fraction, 1.0)

    # ------------------------------------------------------------------
    # test_08: no transform returns full travel
    # ------------------------------------------------------------------
    def test_08_no_transform_returns_full_travel(self) -> None:
        entity = self.world.create_entity("Ghost")
        # No Transform added

        result = self.backend.body_test_motion(self.world, entity, (50.0, 30.0))

        self.assertEqual(result.travel_x, 50.0)
        self.assertEqual(result.travel_y, 30.0)
        self.assertEqual(result.collision_safe_fraction, 1.0)

    # ------------------------------------------------------------------
    # test_09: no collider returns full travel
    # ------------------------------------------------------------------
    def test_09_no_collider_returns_full_travel(self) -> None:
        entity = self.world.create_entity("Ghost")
        entity.add_component(Transform(x=100.0, y=100.0))
        # No Collider added

        result = self.backend.body_test_motion(self.world, entity, (50.0, 0.0))

        self.assertEqual(result.travel_x, 50.0)
        self.assertEqual(result.travel_y, 0.0)
        self.assertEqual(result.collision_safe_fraction, 1.0)

    # ------------------------------------------------------------------
    # test_10: trigger ignored by default
    # ------------------------------------------------------------------
    def test_10_trigger_ignored_by_default(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        triggers = self.world.create_entity("TriggerZone")
        triggers.add_component(Transform(x=50.0, y=0.0))
        triggers.add_component(RigidBody())
        triggers.add_component(Collider(width=16.0, height=200.0, is_trigger=True))

        result = self.backend.body_test_motion(
            self.world, mover, (100.0, 0.0),
            collide_with_areas=False,
        )

        self.assertEqual(result.collision_safe_fraction, 1.0,
                         "Trigger should be ignored by default")

    # ------------------------------------------------------------------
    # test_11: collider velocity returned from target RigidBody
    # ------------------------------------------------------------------
    def test_11_collider_velocity_returned(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("MovingWall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody(velocity_x=50.0, velocity_y=12.0))
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertAlmostEqual(result.collider_velocity_x, 50.0, delta=0.01,
                               msg="Should return target's RigidBody velocity_x")

    # ------------------------------------------------------------------
    # test_12: collision_depth field exists and is a float
    # ------------------------------------------------------------------
    def test_12_collision_depth(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertIsInstance(result.collision_depth, float,
                              "collision_depth must be a float")

    # ------------------------------------------------------------------
    # test_13: target uses CollisionShapeSet2D (not Collider)
    # ------------------------------------------------------------------
    def test_13_collision_shape_set_2d_target(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        target = self.world.create_entity("ShapeSetTarget")
        target.add_component(Transform(x=50.0, y=0.0))
        target.add_component(RigidBody())
        target.add_component(CollisionShapeSet2D(
            shapes=[CollisionShape2DDef(shape_type="box", width=16.0, height=200.0)]
        ))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertLess(result.collision_safe_fraction, 1.0,
                        "Should detect collision with CollisionShapeSet2D target")
        self.assertEqual(result.collider_entity_name, "ShapeSetTarget")

    # ------------------------------------------------------------------
    # test_14: mover uses CollisionShapeSet2D (not Collider)
    # ------------------------------------------------------------------
    def test_14_collision_shape_set_2d_mover(self) -> None:
        mover = self.world.create_entity("ShapeSetMover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(CollisionShapeSet2D(
            shapes=[CollisionShape2DDef(shape_type="box", width=16.0, height=16.0)]
        ))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertLess(result.collision_safe_fraction, 1.0,
                        "Should detect collision with CollisionShapeSet2D mover")
        self.assertEqual(result.collider_entity_name, "Wall")

    # ------------------------------------------------------------------
    # test_15: exclude_ids prevents collision with specified entity
    # ------------------------------------------------------------------
    def test_15_exclude_ids_prevents_collision(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(
            self.world, mover, (100.0, 0.0),
            exclude_ids=[wall.id],
        )

        self.assertEqual(result.collision_safe_fraction, 1.0,
                         "Wall in exclude_ids should not cause collision")

    # ------------------------------------------------------------------
    # test_16: two targets, hits nearest
    # ------------------------------------------------------------------
    def test_16_two_targets_hits_nearest(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        near_wall = self.world.create_entity("NearWall")
        near_wall.add_component(Transform(x=30.0, y=0.0))
        near_wall.add_component(RigidBody())
        near_wall.add_component(Collider(width=16.0, height=200.0))

        far_wall = self.world.create_entity("FarWall")
        far_wall.add_component(Transform(x=80.0, y=0.0))
        far_wall.add_component(RigidBody())
        far_wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertLess(result.collision_safe_fraction, 1.0)
        self.assertEqual(result.collider_entity_name, "NearWall",
                         "Should hit nearer wall at x=30, not farther wall at x=80")

    # ------------------------------------------------------------------
    # test_17: collision normal correct direction (against motion)
    # ------------------------------------------------------------------
    def test_17_collision_normal_correct_direction(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        wall = self.world.create_entity("Wall")
        wall.add_component(Transform(x=50.0, y=0.0))
        wall.add_component(RigidBody())
        wall.add_component(Collider(width=16.0, height=200.0))

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        # Motion is +x (right), normal should point -x (left, against motion)
        self.assertLess(result.collision_normal_x, 0.0,
                        "Normal x should be negative (pointing against rightward motion)")

    # ------------------------------------------------------------------
    # test_18: disabled collider ignored
    # ------------------------------------------------------------------
    def test_18_disabled_collider_ignored(self) -> None:
        mover = self.world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        disabled = self.world.create_entity("DisabledWall")
        disabled.add_component(Transform(x=50.0, y=0.0))
        disabled.add_component(RigidBody())
        disabled_collider = Collider(width=16.0, height=200.0)
        disabled_collider.enabled = False
        disabled.add_component(disabled_collider)

        result = self.backend.body_test_motion(self.world, mover, (100.0, 0.0))

        self.assertEqual(result.collision_safe_fraction, 1.0,
                         "Disabled collider should be ignored")

    # ------------------------------------------------------------------
    # test_19: CollisionShapeSet2D target without RigidBody is solid
    # ------------------------------------------------------------------
    def test_19_collision_shape_set_2d_target_no_rigidbody(self) -> None:
        """CollisionShapeSet2D target without RigidBody is treated as solid body."""
        world = self.world
        backend = self.backend

        target = world.create_entity("ShapeWall")
        target.add_component(Transform(x=200.0, y=100.0))
        shape_set = CollisionShapeSet2D(shapes=[
            CollisionShape2DDef(
                shape_type="box",
                width=32.0,
                height=32.0,
                disabled=False,
                is_trigger=False,
            )
        ])
        target.add_component(shape_set)
        # NO Collider, NO RigidBody added

        mover = world.create_entity("Mover")
        mover.add_component(Transform(x=0.0, y=100.0))
        mover.add_component(Collider(width=16.0, height=16.0))

        result = backend.body_test_motion(
            world=world,
            entity=mover,
            motion=(500.0, 0.0),
        )

        self.assertLess(
            result.collision_safe_fraction, 1.0,
            "CollisionShapeSet2D target without RigidBody should be solid, not ignored"
        )
        self.assertEqual(
            result.collider_entity_name, "ShapeWall",
            "Should collide with the ShapeWall entity"
        )


if __name__ == "__main__":
    unittest.main()
