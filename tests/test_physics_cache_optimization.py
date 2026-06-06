import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.debug.benchmark_runner import run_benchmark
from engine.ecs.world import World
from engine.systems.collision_system import CollisionSystem
from engine.systems.physics_system import PhysicsSystem


class PhysicsCacheOptimizationTests(unittest.TestCase):
    def _make_overlapping_world(self) -> tuple[World, Collider, Transform]:
        world = World()
        body = world.create_entity("Body")
        transform = Transform(x=0.0, y=0.0)
        collider = Collider(width=16.0, height=16.0)
        body.add_component(transform)
        body.add_component(collider)
        body.add_component(
            RigidBody(
                body_type="dynamic",
                mass=0.0,
                gravity_scale=0.0,
                is_grounded=True,
                can_sleep=False,
            )
        )

        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=4.0, y=0.0))
        wall.add_component(Collider(width=16.0, height=16.0))
        return world, collider, transform

    def test_hot_frame_reuses_aabbs_and_shapes(self) -> None:
        world, _collider, _transform = self._make_overlapping_world()
        physics = PhysicsSystem()

        physics.update(world, 1.0 / 60.0)
        cold = physics.get_step_metrics()
        physics.update(world, 1.0 / 60.0)
        hot = physics.get_step_metrics()

        self.assertGreater(cold["aabb_builds"], 0)
        self.assertGreater(cold["shape_builds"], 0)
        self.assertEqual(hot["aabb_builds"], 0)
        self.assertEqual(hot["shape_builds"], 0)
        self.assertGreater(hot["aabb_cache_hits"], 0)
        self.assertGreater(hot["shape_cache_hits"], 0)

    def test_collider_geometry_fields_invalidate_shape_and_aabb_cache(self) -> None:
        mutations = {
            "shape_type": lambda collider: setattr(collider, "shape_type", "circle"),
            "points": lambda collider: (
                setattr(collider, "shape_type", "polygon"),
                setattr(collider, "points", [[-8.0, -8.0], [8.0, -8.0], [0.0, 8.0]]),
            ),
            "radius": lambda collider: setattr(collider, "radius", collider.radius + 1.0),
            "width": lambda collider: setattr(collider, "width", collider.width + 2.0),
            "height": lambda collider: setattr(collider, "height", collider.height + 2.0),
            "capsule_height": lambda collider: setattr(
                collider, "capsule_height", collider.capsule_height + 2.0
            ),
            "offset_x": lambda collider: setattr(collider, "offset_x", collider.offset_x + 1.0),
            "offset_y": lambda collider: setattr(collider, "offset_y", collider.offset_y + 1.0),
        }

        for field, mutate in mutations.items():
            with self.subTest(field=field):
                world, collider, _transform = self._make_overlapping_world()
                physics = PhysicsSystem()
                physics.update(world, 1.0 / 60.0)
                physics.update(world, 1.0 / 60.0)

                mutate(collider)
                physics.update(world, 1.0 / 60.0)
                metrics = physics.get_step_metrics()

                self.assertGreater(metrics["aabb_builds"], 0)
                self.assertGreater(metrics["shape_builds"], 0)

    def test_points_mutated_in_place_invalidate_cache(self) -> None:
        world, collider, _transform = self._make_overlapping_world()
        collider.shape_type = "polygon"
        collider.points = [[-8.0, -8.0], [8.0, -8.0], [0.0, 8.0]]
        physics = PhysicsSystem()
        physics.update(world, 1.0 / 60.0)
        physics.update(world, 1.0 / 60.0)

        collider.points[0][0] = -10.0
        physics.update(world, 1.0 / 60.0)

        metrics = physics.get_step_metrics()
        self.assertGreater(metrics["aabb_builds"], 0)
        self.assertGreater(metrics["shape_builds"], 0)

    def test_transform_and_enabled_changes_invalidate_cache(self) -> None:
        transform_mutations = {
            "position": lambda transform: setattr(transform, "x", transform.x + 1.0),
            "rotation": lambda transform: setattr(transform, "rotation", transform.rotation + 15.0),
            "scale": lambda transform: setattr(transform, "scale_x", transform.scale_x + 0.5),
        }
        for field, mutate in transform_mutations.items():
            with self.subTest(field=field):
                world, _collider, transform = self._make_overlapping_world()
                physics = PhysicsSystem()
                physics.update(world, 1.0 / 60.0)
                physics.update(world, 1.0 / 60.0)

                mutate(transform)
                physics.update(world, 1.0 / 60.0)
                self.assertGreater(physics.get_step_metrics()["shape_builds"], 0)

        world, collider, transform = self._make_overlapping_world()
        physics = PhysicsSystem()
        physics.update(world, 1.0 / 60.0)
        physics.update(world, 1.0 / 60.0)
        collider.enabled = False
        physics.update(world, 1.0 / 60.0)
        collider.enabled = True
        physics.update(world, 1.0 / 60.0)
        self.assertGreater(physics.get_step_metrics()["shape_builds"], 0)

        transform.enabled = False
        physics.update(world, 1.0 / 60.0)
        transform.enabled = True
        physics.update(world, 1.0 / 60.0)
        self.assertGreater(physics.get_step_metrics()["shape_builds"], 0)

    def test_trigger_collisions_survive_hot_shape_cache(self) -> None:
        world = World()
        body = world.create_entity("Body")
        body.add_component(Transform(x=0.0, y=0.0))
        body.add_component(Collider(width=16.0, height=16.0))

        trigger = world.create_entity("Trigger")
        trigger.add_component(Transform(x=4.0, y=0.0))
        trigger.add_component(Collider(width=16.0, height=16.0, is_trigger=True))

        collision = CollisionSystem()
        collision.update(world)
        cold = collision.get_step_metrics()
        collision.update(world)
        hot = collision.get_step_metrics()

        self.assertEqual(len(collision.get_collisions()), 1)
        self.assertTrue(collision.get_collisions()[0].is_trigger)
        self.assertGreater(cold["shape_builds"], 0)
        self.assertEqual(hot["shape_builds"], 0)
        self.assertGreater(hot["shape_cache_hits"], 0)

    def test_dynamic_static_and_dynamic_dynamic_keep_candidates_on_hot_frames(self) -> None:
        for other_is_dynamic in (False, True):
            with self.subTest(other_is_dynamic=other_is_dynamic):
                world, _collider, _transform = self._make_overlapping_world()
                if other_is_dynamic:
                    wall = world.get_entity_by_name("Wall")
                    assert wall is not None
                    wall.add_component(
                        RigidBody(
                            body_type="dynamic",
                            mass=0.0,
                            gravity_scale=0.0,
                            is_grounded=True,
                            can_sleep=False,
                        )
                    )
                physics = PhysicsSystem()
                physics.update(world, 1.0 / 60.0)
                cold = physics.get_step_metrics()
                physics.update(world, 1.0 / 60.0)
                hot = physics.get_step_metrics()

                self.assertEqual(hot["candidate_solids"], cold["candidate_solids"])
                self.assertGreater(hot["candidate_solids"], 0)
                self.assertGreater(hot["shape_cache_hits"], 0)
                if not other_is_dynamic:
                    self.assertEqual(hot["shape_builds"], 0)

    def test_cast_shape_ccd_still_blocks_thin_wall_with_cache_enabled(self) -> None:
        world = World()
        bullet = world.create_entity("Bullet")
        bullet.add_component(Transform(x=0.0, y=0.0))
        bullet.add_component(Collider(shape_type="circle", radius=4.0))
        bullet.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=5000.0,
                is_grounded=True,
                ccd_mode="cast_shape",
                can_sleep=False,
            )
        )
        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=80.0, y=0.0))
        wall.add_component(Collider(width=4.0, height=40.0))

        physics = PhysicsSystem()
        physics.update(world, 0.1)

        bullet_transform = bullet.get_component(Transform)
        bullet_body = bullet.get_component(RigidBody)
        assert bullet_transform is not None
        assert bullet_body is not None
        self.assertLessEqual(bullet_transform.x + 4.0, 79.0)
        self.assertEqual(bullet_body.velocity_x, 0.0)
        self.assertEqual(physics.get_step_metrics()["ccd_bodies"], 1)
        self.assertEqual(physics.get_step_metrics()["candidate_solids"], 1)

    def test_sleeping_body_does_not_rebuild_unchanged_geometry(self) -> None:
        world, _collider, _transform = self._make_overlapping_world()
        body = world.get_entity_by_name("Body")
        assert body is not None
        rigidbody = body.get_component(RigidBody)
        assert rigidbody is not None
        rigidbody.sleeping = True

        physics = PhysicsSystem()
        physics.update(world, 1.0 / 60.0)
        physics.update(world, 1.0 / 60.0)

        metrics = physics.get_step_metrics()
        self.assertTrue(rigidbody.sleeping)
        self.assertEqual(metrics["shape_builds"], 0)
        self.assertGreater(metrics["aabb_cache_hits"], 0)

    def test_sleeping_body_keeps_ground_support(self) -> None:
        world = World()
        floor = world.create_entity("Floor")
        floor.add_component(Transform(x=100.0, y=108.0))
        floor.add_component(Collider(width=200.0, height=16.0))

        body = world.create_entity("Body")
        body.add_component(Transform(x=100.0, y=84.0))
        body.add_component(Collider(width=32.0, height=32.0))
        rigidbody = RigidBody(body_type="dynamic", mass=1.0, gravity_scale=1.0)
        body.add_component(rigidbody)

        physics = PhysicsSystem(gravity=980.0)
        for _ in range(120):
            physics.update(world, 1.0 / 60.0)

        self.assertTrue(rigidbody.sleeping)
        self.assertTrue(rigidbody.is_grounded)

    def test_synthetic_benchmark_reports_cold_to_hot_cache_reduction(self) -> None:
        report = run_benchmark(
            scenario="many_dynamic_and_static",
            backend="legacy_aabb",
            frames=3,
            static_count=40,
            dynamic_count=12,
            columns=10,
            spacing=24.0,
            velocity=0.0,
        )

        comparison = report["operations"]["physics_cache_metrics"]
        cold = comparison["cold_frame"]
        hot = comparison["hot_frame"]
        naive_candidates = 12 * (40 + 12 - 1)

        self.assertGreater(cold["aabb_builds"], hot["aabb_builds"])
        self.assertGreaterEqual(cold["shape_builds"], hot["shape_builds"])
        self.assertGreater(hot["aabb_cache_hits"], 0)
        self.assertLess(hot["candidate_solids"], naive_candidates)


if __name__ == "__main__":
    unittest.main()
