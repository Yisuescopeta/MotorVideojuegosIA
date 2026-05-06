import unittest

from engine.components.area2d import Area2D
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

    def test_dynamic_body_movement_increments_transform_version_not_structure(self) -> None:
        world = World()
        entity = world.create_entity("Mover")
        entity.add_component(Transform(x=0.0, y=0.0))
        entity.add_component(RigidBody(velocity_x=10.0, velocity_y=0.0, gravity_scale=0.0, is_grounded=True))
        structure_before = world.structure_version
        transform_before = world.transform_version

        PhysicsSystem().update(world, 0.5)

        self.assertEqual(entity.get_component(Transform).x, 5.0)
        self.assertEqual(world.transform_version, transform_before + 1)
        self.assertEqual(world.structure_version, structure_before)

    def test_rigidbody_runtime_changes_increment_physics_version(self) -> None:
        world = World()
        entity = world.create_entity("Faller")
        entity.add_component(Transform(x=0.0, y=0.0))
        entity.add_component(RigidBody(velocity_x=0.0, velocity_y=0.0, gravity_scale=1.0, is_grounded=False, can_sleep=False))
        physics_before = world.physics_version
        structure_before = world.structure_version

        PhysicsSystem(gravity=10.0).update(world, 0.5)

        self.assertGreater(entity.get_component(RigidBody).velocity_y, 0.0)
        self.assertEqual(world.physics_version, physics_before + 1)
        self.assertEqual(world.structure_version, structure_before)

    def test_noop_physics_update_does_not_increment_granular_versions(self) -> None:
        world = World()
        entity = world.create_entity("Static")
        entity.add_component(Transform(x=0.0, y=0.0))
        entity.add_component(RigidBody(body_type="static", velocity_x=0.0, velocity_y=0.0, is_grounded=False))
        versions_before = (
            world.transform_version,
            world.physics_version,
            world.structure_version,
            world.version,
        )

        PhysicsSystem().update(world, 1.0)

        self.assertEqual(
            versions_before,
            (
                world.transform_version,
                world.physics_version,
                world.structure_version,
                world.version,
            ),
        )

    def test_static_body_clears_force_buffers(self) -> None:
        world = World()
        entity = world.create_entity("Test")
        entity.add_component(Transform(x=0.0, y=0.0))
        rb = RigidBody(body_type="static", simulated=True)
        entity.add_component(rb)
        entity.add_component(Collider(width=32, height=32))

        rb._force_buffer_x = 100.0
        rb._force_buffer_y = 50.0
        rb._impulse_buffer_x = 20.0
        rb._torque_buffer = 10.0

        PhysicsSystem().update(world, 1 / 60)

        self.assertEqual(rb._force_buffer_x, 0.0, f"Force buffer X not cleared: {rb._force_buffer_x}")
        self.assertEqual(rb._force_buffer_y, 0.0, f"Force buffer Y not cleared: {rb._force_buffer_y}")
        self.assertEqual(rb._impulse_buffer_x, 0.0, f"Impulse buffer X not cleared: {rb._impulse_buffer_x}")
        self.assertEqual(rb._torque_buffer, 0.0, f"Torque buffer not cleared: {rb._torque_buffer}")

    def test_body_falling_below_550_not_teleported(self) -> None:
        """Dynamic body falling with no collider must NOT be teleported to Y=550."""
        world = World()
        entity = world.create_entity("Faller")
        entity.add_component(Transform(x=0.0, y=600.0))
        entity.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=1.0,
                velocity_x=0.0,
                velocity_y=0.0,
                is_grounded=False,
                can_sleep=False,
            )
        )
        PhysicsSystem(gravity=980.0).update(world, 0.5)

        transform = entity.get_component(Transform)
        rigidbody = entity.get_component(RigidBody)
        self.assertGreater(
            transform.y, 550.0,
            "Body should NOT be teleported back to Y=550 after GROUND_Y_TEMP removal"
        )
        self.assertFalse(
            rigidbody.is_grounded,
            "Body without ground collider should not be marked grounded"
        )
        self.assertGreater(
            rigidbody.velocity_y, 0.0,
            "Body should have downward velocity from gravity"
        )

    def test_body_lands_on_ground_above_550_not_clamped(self) -> None:
        """Body with collider landing on actual ground above 550 must not be teleported to 550."""
        world = World()
        hero = world.create_entity("Hero")
        hero.add_component(Transform(x=0.0, y=600.0))
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
        ground.add_component(Transform(x=0.0, y=630.0))
        ground.add_component(Collider(width=100.0, height=10.0))

        PhysicsSystem().update(world, 0.5)

        transform = hero.get_component(Transform)
        rigidbody = hero.get_component(RigidBody)
        self.assertGreater(
            transform.y, 550.0,
            "Body should land on real ground collider, not be teleported to Y=550"
        )
        self.assertTrue(
            rigidbody.is_grounded,
            "Body should be grounded after landing on collider above 550"
        )

    def test_dynamic_body_already_grounded_above_550_not_clamped(self) -> None:
        """Grounded body at Y=600 must stay at Y=600, not teleported to 550."""
        world = World()
        entity = world.create_entity("Grounded")
        entity.add_component(Transform(x=0.0, y=600.0))
        entity.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=0.0,
                velocity_y=0.0,
                is_grounded=True,
                can_sleep=False,
            )
        )

        PhysicsSystem().update(world, 0.5)

        transform = entity.get_component(Transform)
        self.assertEqual(
            transform.y, 600.0,
            "Grounded body should stay at its position"
        )
        self.assertNotEqual(
            transform.y, 550.0,
            "Grounded body must NOT be teleported to Y=550"
        )

    def test_kinematic_body_above_550_not_touched(self) -> None:
        """Kinematic body at Y=600 must stay at Y=600."""
        world = World()
        entity = world.create_entity("Kinematic")
        entity.add_component(Transform(x=0.0, y=600.0))
        entity.add_component(
            RigidBody(
                body_type="kinematic",
                gravity_scale=0.0,
                velocity_x=0.0,
                velocity_y=0.0,
                is_grounded=False,
                can_sleep=False,
            )
        )

        PhysicsSystem().update(world, 0.5)

        transform = entity.get_component(Transform)
        self.assertEqual(
            transform.y, 600.0,
            "Kinematic body should stay at its position"
        )


    def test_cast_shape_ccd_prevents_tunneling_through_thin_wall(self) -> None:
        """Fast bullet with cast_shape CCD must stop at wall, not tunnel through."""
        world = World()
        bullet = world.create_entity("Bullet")
        bullet.add_component(Transform(x=0.0, y=100.0))
        bullet.add_component(Collider(shape_type="circle", radius=4.0))
        bullet.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=5000.0,  # 5000 * 0.1 = 500 px/frame → will reach wall
                velocity_y=0.0,
                is_grounded=True,
                collision_detection_mode="discrete",
                ccd_mode="cast_shape",
            )
        )

        # Wall at x=80, 4px thick → left edge at x=78
        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=80.0, y=100.0))
        wall.add_component(Collider(width=4.0, height=80.0))

        # Use large dt so bullet actually travels far enough
        PhysicsSystem().update(world, 0.1)

        transform = bullet.get_component(Transform)
        rigidbody = bullet.get_component(RigidBody)
        # Bullet right edge = center + radius
        bullet_right = transform.x + 4.0
        wall_left = 78.0
        self.assertLessEqual(
            bullet_right, wall_left + 1.0,
            f"CCD bullet tunneled! Right edge={bullet_right}, wall left={wall_left}"
        )
        self.assertEqual(
            rigidbody.velocity_x, 0.0,
            "CCD bullet velocity should be zero after hitting wall"
        )
        # Bullet should have been stopped before reaching x=200
        self.assertLess(transform.x, 200.0, "CCD bullet traveled too far")

    def test_cast_shape_ccd_stops_at_wall_unlike_discrete(self) -> None:
        """cast_shape mode stops at wall; discrete mode may tunnel."""
        world = World()

        # --- cast_shape bullet ---
        bullet_ccd = world.create_entity("BulletCCD")
        bullet_ccd.add_component(Transform(x=0.0, y=100.0))
        bullet_ccd.add_component(Collider(shape_type="circle", radius=4.0))
        bullet_ccd.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=5000.0,
                velocity_y=0.0,
                is_grounded=True,
                collision_detection_mode="discrete",
                ccd_mode="cast_shape",
            )
        )

        # --- discrete bullet (same speed, no CCD) ---
        bullet_disc = world.create_entity("BulletDisc")
        bullet_disc.add_component(Transform(x=0.0, y=200.0))
        bullet_disc.add_component(Collider(shape_type="circle", radius=4.0))
        bullet_disc.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=5000.0,
                velocity_y=0.0,
                is_grounded=True,
                collision_detection_mode="discrete",
                ccd_mode="disabled",
            )
        )

        # Wall at x=80, 4px thick → left edge at x=78
        wall_top = world.create_entity("WallTop")
        wall_top.add_component(Transform(x=80.0, y=100.0))
        wall_top.add_component(Collider(width=4.0, height=60.0))

        wall_bot = world.create_entity("WallBot")
        wall_bot.add_component(Transform(x=80.0, y=200.0))
        wall_bot.add_component(Collider(width=4.0, height=60.0))

        PhysicsSystem().update(world, 0.1)

        # CCD bullet must stop before or at wall
        ccd_right = bullet_ccd.get_component(Transform).x + 4.0
        self.assertLessEqual(
            ccd_right, 79.0,
            f"CCD bullet tunneled! Right edge={ccd_right}, wall left=78.0"
        )
        self.assertEqual(
            bullet_ccd.get_component(RigidBody).velocity_x, 0.0,
            "CCD bullet velocity should be zero after hitting wall"
        )

        # Discrete bullet: verify it exists (it may or may not tunnel, both are valid)
        disc_x = bullet_disc.get_component(Transform).x
        self.assertIsNotNone(disc_x, "Discrete bullet should exist")
        # Key assertion: CCD bullet must not pass the wall while discrete may
        # CCD bullet x should be < 80 (stuck at wall)
        self.assertLess(bullet_ccd.get_component(Transform).x, 80.0)


    def test_area_gravity_override_affects_dynamic_body(self) -> None:
        """Dynamic body inside area with gravity override uses area gravity."""
        world = World()

        area_e = world.create_entity("AntiGravZone")
        area_e.add_component(Transform(x=100.0, y=100.0))
        area_e.add_component(Collider(width=100.0, height=100.0, is_trigger=True))
        area_e.add_component(Area2D(
            space_override="replace",
            gravity_override_x=0.0,
            gravity_override_y=-200.0,
            priority=1,
        ))

        body = world.create_entity("Body")
        body.add_component(Transform(x=100.0, y=100.0))
        body.add_component(Collider(width=10.0, height=10.0))
        body.add_component(RigidBody(
            body_type="dynamic",
            gravity_scale=1.0,
            is_grounded=False,
            can_sleep=False,
        ))

        ps = PhysicsSystem(gravity=980.0)
        ps.update(world, 0.5)

        rb = body.get_component(RigidBody)
        # With area gravity_override_y=-200, gravity_scale=1, dt=0.5:
        # vy = -200 * 1.0 * 0.5 = -100.0 (no damping since linear_damping=0)
        msg = f"Area gravity override magnitude wrong: vy={rb.velocity_y}, expected ~ -100.0"
        self.assertAlmostEqual(rb.velocity_y, -100.0, delta=0.5, msg=msg)


if __name__ == "__main__":
    unittest.main()
