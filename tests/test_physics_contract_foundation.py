import unittest

from engine.components.collider import Collider
from engine.components.joint2d import Joint2D
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.physics.backend import PhysicsBackend
from engine.physics.capabilities import get_backend_capabilities, list_backend_capabilities
from engine.physics.ecs_adapter import build_body_signature, build_joint_signature, snapshot_entity


class _StubRuntimeBackend(PhysicsBackend):
    backend_name = "stub"

    def step(self, world, dt):  # type: ignore[override]
        self.last_step = (world, dt)

    def query_ray(self, world, origin, direction, max_distance):  # type: ignore[override]
        return []

    def query_aabb(self, world, bounds):  # type: ignore[override]
        return []

    def collect_contacts(self, world):  # type: ignore[override]
        return []

    def sync_world(self, world):  # type: ignore[override]
        self.last_sync_world = world


class PhysicsContractFoundationTests(unittest.TestCase):
    def test_runtime_backend_contract_requires_only_runtime_surface(self) -> None:
        backend = _StubRuntimeBackend()

        backend.sync_world("world")
        backend.step("world", 0.25)

        self.assertEqual(backend.last_sync_world, "world")
        self.assertEqual(backend.last_step, ("world", 0.25))
        self.assertFalse(hasattr(PhysicsBackend, "create_body"))
        self.assertFalse(hasattr(PhysicsBackend, "create_shape"))
        self.assertFalse(hasattr(PhysicsBackend, "destroy_body"))

    def test_ecs_adapter_normalizes_runtime_physics_components(self) -> None:
        world = World()

        anchor = world.create_entity("Anchor")
        anchor.layer = "Gameplay"
        anchor.add_component(Transform(x=5.0, y=6.0, rotation=15.0))
        anchor.add_component(Collider(width=12.0, height=4.0, is_trigger=True))

        pendulum = world.create_entity("Pendulum")
        pendulum.layer = "Gameplay"
        pendulum.add_component(Transform(x=10.0, y=20.0, rotation=30.0))
        pendulum.add_component(
            RigidBody(
                body_type="kinematic",
                gravity_scale=0.5,
                velocity_x=7.0,
                velocity_y=9.0,
                freeze_x=True,
                collision_detection_mode="continuous",
                use_full_kinematic_contacts=True,
            )
        )
        pendulum.add_component(
            Collider(
                shape_type="polygon",
                width=16.0,
                height=8.0,
                offset_x=1.0,
                offset_y=2.0,
                points=[[0.0, 0.0], [3.0, 0.0], [1.5, 2.0]],
                friction=0.4,
                restitution=0.1,
                density=2.0,
            )
        )
        pendulum.add_component(
            Joint2D(
                joint_type="distance",
                connected_entity="Anchor",
                anchor_x=1.0,
                anchor_y=2.0,
                connected_anchor_x=3.0,
                connected_anchor_y=4.0,
                rest_length=25.0,
                damping_ratio=0.3,
                frequency_hz=2.0,
                collide_connected=True,
            )
        )

        snapshot = snapshot_entity(pendulum)

        self.assertTrue(snapshot.has_transform)
        self.assertEqual(snapshot.entity_name, "Pendulum")
        self.assertEqual(snapshot.layer, "Gameplay")
        self.assertEqual(snapshot.body.body_type, "kinematic")
        self.assertTrue(snapshot.body.freeze_x)
        self.assertEqual(snapshot.body.collision_detection_mode, "continuous")
        self.assertEqual(snapshot.shape.shape_type, "polygon")
        self.assertEqual(snapshot.shape.points, ((0.0, 0.0), (3.0, 0.0), (1.5, 2.0)))
        self.assertEqual(snapshot.shape.filter.layer, "Gameplay")
        self.assertFalse(snapshot.shape.filter.is_sensor)
        self.assertEqual(snapshot.joint.connected_entity, "Anchor")
        self.assertEqual(snapshot.joint.joint_type, "distance")

        body_signature = build_body_signature(snapshot)
        joint_signature = build_joint_signature(snapshot)
        self.assertIsNotNone(body_signature)
        self.assertIsNotNone(joint_signature)
        self.assertIn("Pendulum", body_signature)
        self.assertIn("Anchor", joint_signature)

    def test_backend_capabilities_only_declare_current_support(self) -> None:
        capabilities = {item.backend_name: item for item in list_backend_capabilities()}

        self.assertEqual(set(capabilities), {"box2d", "legacy_aabb"})
        self.assertEqual(capabilities["legacy_aabb"].shape_types, ("box",))
        self.assertEqual(capabilities["legacy_aabb"].joint_types, ())
        self.assertFalse(capabilities["legacy_aabb"].supports_collision_masks)
        self.assertFalse(capabilities["legacy_aabb"].supports_shape_queries)
        self.assertEqual(capabilities["box2d"].joint_types, ("distance", "fixed"))
        self.assertTrue(capabilities["box2d"].supports_contact_normals)
        self.assertFalse(capabilities["box2d"].supports_collision_masks)
        self.assertIs(get_backend_capabilities("box2d"), capabilities["box2d"])


if __name__ == "__main__":
    unittest.main()
