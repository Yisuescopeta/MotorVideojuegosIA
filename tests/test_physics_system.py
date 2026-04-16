import unittest

from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.physics_system import PhysicsSystem


class PhysicsSystemTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
