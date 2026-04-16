import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.spatial_hash import SpatialHash2D
from engine.systems.physics_system import PhysicsSystem, _SolidCandidate


class PhysicsSystemTests(unittest.TestCase):
    def _solid_candidate(self, entity: Entity) -> _SolidCandidate:
        collider = entity.get_component(Collider)
        assert collider is not None
        return _SolidCandidate(entity=entity, collider=collider)

    def test_record_swept_contact_deduplicates_pairs_while_preserving_first_seen_order(self) -> None:
        physics_system = PhysicsSystem()
        entity_a = Entity("A")
        entity_b = Entity("B")
        entity_c = Entity("C")

        physics_system._record_swept_contact(entity_a, entity_b)
        physics_system._record_swept_contact(entity_b, entity_a)
        physics_system._record_swept_contact(entity_a, entity_c)

        self.assertEqual(
            physics_system.consume_swept_contacts(),
            [
                tuple(sorted((entity_a.id, entity_b.id))),
                tuple(sorted((entity_a.id, entity_c.id))),
            ],
        )

    def test_continuous_body_checks_only_local_candidates(self) -> None:
        world = World()
        bullet = world.create_entity("Bullet")
        bullet.add_component(Transform(x=0.0, y=0.0))
        bullet.add_component(Collider(width=4.0, height=4.0))
        bullet.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=1200.0,
                velocity_y=0.0,
                is_grounded=True,
                collision_detection_mode="continuous",
            )
        )

        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=20.0, y=0.0))
        wall.add_component(Collider(width=4.0, height=20.0))

        for index in range(6):
            far_wall = world.create_entity(f"FarWall{index}")
            far_wall.add_component(Transform(x=400.0 + index * 200.0, y=0.0))
            far_wall.add_component(Collider(width=4.0, height=20.0))

        physics_system = PhysicsSystem()
        physics_system.update(world, 1.0 / 60.0)
        metrics = physics_system.get_step_metrics()

        self.assertLess(bullet.get_component(Transform).x, 20.0)
        self.assertEqual(metrics["ccd_bodies"], 1)
        self.assertLess(metrics["candidate_solids"], 7)
        self.assertLess(metrics["swept_checks"], 7)

    def test_ground_support_uses_local_candidates(self) -> None:
        world = World()
        hero = world.create_entity("Hero")
        hero.add_component(Transform(x=0.0, y=0.0))
        hero.add_component(Collider(width=10.0, height=10.0))
        hero.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=0.0,
                velocity_y=40.0,
                is_grounded=False,
                collision_detection_mode="continuous",
            )
        )

        ground = world.create_entity("Ground")
        ground.add_component(Transform(x=0.0, y=15.0))
        ground.add_component(Collider(width=100.0, height=10.0))

        far_ground = world.create_entity("FarGround")
        far_ground.add_component(Transform(x=500.0, y=15.0))
        far_ground.add_component(Collider(width=100.0, height=10.0))

        physics_system = PhysicsSystem()
        physics_system.update(world, 0.5)
        metrics = physics_system.get_step_metrics()
        rigidbody = hero.get_component(RigidBody)

        self.assertTrue(rigidbody.is_grounded)
        self.assertEqual(metrics["candidate_solids"], 1)
        self.assertLessEqual(metrics["swept_checks"], 1)

    def test_collect_candidate_solids_includes_dynamic_vs_dynamic_bodies_outside_static_grid(self) -> None:
        world = World()

        entity_a = world.create_entity("DynamicA")
        entity_a.add_component(Transform(x=0.0, y=0.0))
        entity_a.add_component(Collider(width=10.0, height=10.0))
        rigidbody_a = RigidBody(
            body_type="dynamic",
            gravity_scale=0.0,
            velocity_x=60.0,
            velocity_y=0.0,
            is_grounded=True,
            collision_detection_mode="continuous",
        )
        entity_a.add_component(rigidbody_a)

        entity_b = world.create_entity("DynamicB")
        entity_b.add_component(Transform(x=16.0, y=0.0))
        entity_b.add_component(Collider(width=10.0, height=10.0))
        rigidbody_b = RigidBody(
            body_type="dynamic",
            gravity_scale=0.0,
            velocity_x=-60.0,
            velocity_y=0.0,
            is_grounded=True,
            collision_detection_mode="continuous",
        )
        entity_b.add_component(rigidbody_b)

        far_static = world.create_entity("FarStatic")
        far_static_transform = Transform(x=500.0, y=0.0)
        far_static_collider = Collider(width=10.0, height=10.0)
        far_static.add_component(far_static_transform)
        far_static.add_component(far_static_collider)

        physics_system = PhysicsSystem()
        grid = SpatialHash2D(cell_size=physics_system._spatial_hash_cell_size)
        static_like_candidates = {int(far_static.id): self._solid_candidate(far_static)}
        grid.insert(far_static.id, far_static_collider.get_bounds(far_static_transform.x, far_static_transform.y))
        moving_candidates = sorted(
            [self._solid_candidate(entity_a), self._solid_candidate(entity_b)],
            key=lambda candidate: int(candidate.entity.id),
        )

        candidates_for_a = physics_system._collect_candidate_solids(
            world,
            entity_a,
            rigidbody_a,
            entity_a.get_component(Collider),
            entity_a.get_component(Transform),
            grid,
            static_like_candidates,
            moving_candidates,
            delta_x=12.0,
            delta_y=0.0,
        )
        candidates_for_b = physics_system._collect_candidate_solids(
            world,
            entity_b,
            rigidbody_b,
            entity_b.get_component(Collider),
            entity_b.get_component(Transform),
            grid,
            static_like_candidates,
            moving_candidates,
            delta_x=-12.0,
            delta_y=0.0,
        )

        self.assertEqual([candidate.entity.name for candidate in candidates_for_a], ["DynamicB"])
        self.assertEqual([candidate.entity.name for candidate in candidates_for_b], ["DynamicA"])

    def test_continuous_body_keeps_local_candidates_with_many_far_statics_and_near_mover(self) -> None:
        world = World()
        bullet = world.create_entity("Bullet")
        bullet.add_component(Transform(x=0.0, y=0.0))
        bullet.add_component(Collider(width=4.0, height=4.0))
        bullet.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=1200.0,
                velocity_y=0.0,
                is_grounded=True,
                collision_detection_mode="continuous",
            )
        )

        near_mover = world.create_entity("NearMover")
        near_mover.add_component(Transform(x=16.0, y=0.0))
        near_mover.add_component(Collider(width=4.0, height=4.0))
        near_mover.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=-120.0,
                velocity_y=0.0,
                is_grounded=True,
                collision_detection_mode="continuous",
            )
        )

        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=20.0, y=0.0))
        wall.add_component(Collider(width=4.0, height=20.0))

        for index in range(20):
            far_wall = world.create_entity(f"FarWall{index}")
            far_wall.add_component(Transform(x=400.0 + index * 200.0, y=0.0))
            far_wall.add_component(Collider(width=4.0, height=20.0))

        physics_system = PhysicsSystem()
        physics_system.update(world, 1.0 / 60.0)
        metrics = physics_system.get_step_metrics()

        self.assertLess(bullet.get_component(Transform).x, 20.0)
        self.assertEqual(metrics["ccd_bodies"], 2)
        self.assertLess(metrics["candidate_solids"], 6)
        self.assertLess(metrics["swept_checks"], 6)


if __name__ == "__main__":
    unittest.main()
