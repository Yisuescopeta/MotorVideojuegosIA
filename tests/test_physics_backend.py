import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.api import EngineAPI
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.systems.physics_system import PhysicsSystem

try:
    import Box2D  # noqa: F401
except Exception:  # pragma: no cover
    Box2D = None


class PhysicsBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "PhysicsProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _physics_scene_payload(self, backend_name: str) -> dict:
        return {
            "name": "Physics Scene",
            "entities": [
                {
                    "name": "Mover",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {"enabled": True, "x": 12.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 0.0, "velocity_x": 0.0, "velocity_y": 0.0, "is_grounded": True},
                        "Collider": {
                            "enabled": True,
                            "shape_type": "box",
                            "width": 10.0,
                            "height": 10.0,
                            "offset_x": 0.0,
                            "offset_y": 0.0,
                            "is_trigger": False,
                        },
                    },
                },
                {
                    "name": "Wall",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {"enabled": True, "x": 18.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Collider": {
                            "enabled": True,
                            "shape_type": "box",
                            "width": 10.0,
                            "height": 40.0,
                            "offset_x": 0.0,
                            "offset_y": 0.0,
                            "is_trigger": False,
                        },
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {"physics_2d": {"backend": backend_name}},
        }

    def _assert_query_contract(self, ray_hits: list[dict], aabb_hits: list[dict]) -> None:
        self.assertTrue(ray_hits)
        self.assertTrue(aabb_hits)
        ray_hit = ray_hits[0]
        self.assertIn("entity", ray_hit)
        self.assertIn("entity_id", ray_hit)
        self.assertIn("distance", ray_hit)
        self.assertIn("point", ray_hit)
        self.assertIn("is_trigger", ray_hit)
        self.assertIsInstance(ray_hit["point"], dict)
        self.assertIn("x", ray_hit["point"])
        self.assertIn("y", ray_hit["point"])

        aabb_hit = aabb_hits[0]
        self.assertIn("entity", aabb_hit)
        self.assertIn("entity_id", aabb_hit)
        self.assertIn("is_trigger", aabb_hit)

    def _contacts_for(self, physics: PhysicsSystem, entity_name: str, contact_type: str | None = None) -> list:
        contacts = [contact for contact in physics.get_frame_contacts() if contact.entity_a == entity_name]
        if contact_type is not None:
            contacts = [contact for contact in contacts if contact.contact_type == contact_type]
        return contacts

    def test_legacy_backend_selection_persists_in_feature_metadata(self) -> None:
        scene_path = self._write_scene(
            "backend_scene.json",
            {"name": "Backend Scene", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level(scene_path.as_posix())

        result = self.api.set_physics_backend("legacy_aabb")

        self.assertTrue(result["success"])
        metadata = self.api.get_feature_metadata()
        self.assertEqual(metadata["physics_2d"]["backend"], "legacy_aabb")

    def test_legacy_backend_queries_and_contact_events_work(self) -> None:
        scene_path = self._write_scene(
            "physics_scene.json",
            self._physics_scene_payload("legacy_aabb"),
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(1)

        ray_hits = self.api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0)
        aabb_hits = self.api.query_physics_aabb(10.0, -20.0, 30.0, 20.0)
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]

        self._assert_query_contract(ray_hits, aabb_hits)
        self.assertEqual(ray_hits[0]["entity"], "Mover")
        self.assertIn("Wall", {item["entity"] for item in aabb_hits})
        self.assertIn("on_collision", event_names)

    def test_legacy_backend_query_contract_is_stable(self) -> None:
        scene_path = self._write_scene("legacy_contract_scene.json", self._physics_scene_payload("legacy_aabb"))
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(1)

        self._assert_query_contract(
            self.api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0),
            self.api.query_physics_aabb(10.0, -20.0, 30.0, 20.0),
        )

    @unittest.skipIf(Box2D is None, "Box2D optional dependency not available")
    def test_box2d_backend_query_contract_matches_public_shape(self) -> None:
        scene_path = self._write_scene("box2d_contract_scene.json", self._physics_scene_payload("box2d"))
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(1)

        ray_hits = self.api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0)
        aabb_hits = self.api.query_physics_aabb(10.0, -20.0, 30.0, 20.0)

        self._assert_query_contract(ray_hits, aabb_hits)

    @patch("engine.api.engine_api.Box2DPhysicsBackend", side_effect=RuntimeError("box2d init failed"))
    def test_requested_box2d_falls_back_to_legacy_backend_without_mutating_metadata(self, _box2d_backend_mock) -> None:
        self.api.shutdown()
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_fallback").as_posix())
        scene_path = self._write_scene("fallback_scene.json", self._physics_scene_payload("box2d"))

        self.api.load_level(scene_path.as_posix())
        selection_before_play = self.api.get_physics_backend_selection()
        self.api.play()
        self.api.step(1)

        ray_hits = self.api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0)
        selection_after_play = self.api.get_physics_backend_selection()
        backend_infos = {item["name"]: item for item in self.api.list_physics_backends()}

        self.assertEqual(self.api.get_feature_metadata()["physics_2d"]["backend"], "box2d")
        self.assertEqual(selection_before_play["requested_backend"], "box2d")
        self.assertEqual(selection_before_play["effective_backend"], "legacy_aabb")
        self.assertTrue(selection_before_play["used_fallback"])
        self.assertEqual(selection_after_play["effective_backend"], "legacy_aabb")
        self.assertTrue(ray_hits)
        self.assertIn("box2d", backend_infos)
        self.assertFalse(backend_infos["box2d"]["available"])
        self.assertEqual(backend_infos["box2d"]["unavailable_reason"], "box2d init failed")

    @patch("engine.api.engine_api.Box2DPhysicsBackend", side_effect=RuntimeError("box2d init failed"))
    def test_authoring_can_select_known_unavailable_backend(self, _box2d_backend_mock) -> None:
        self.api.shutdown()
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_authoring").as_posix())
        scene_path = self._write_scene(
            "authoring_backend_scene.json",
            {"name": "Backend Scene", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level(scene_path.as_posix())

        result = self.api.set_physics_backend("box2d")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.get_feature_metadata()["physics_2d"]["backend"], "box2d")
        selection = self.api.get_physics_backend_selection()
        self.assertEqual(selection["requested_backend"], "box2d")
        self.assertEqual(selection["effective_backend"], "legacy_aabb")
        self.assertTrue(selection["used_fallback"])

    def test_legacy_backend_continuous_mode_prevents_tunneling(self) -> None:
        scene_path = self._write_scene(
            "ccd_scene.json",
            {
                "name": "CCD Scene",
                "entities": [
                    {
                        "name": "Bullet",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 0.0, "velocity_x": 5000.0, "velocity_y": 0.0, "collision_detection_mode": "continuous", "is_grounded": True},
                            "Collider": {"enabled": True, "width": 2.0, "height": 2.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 40.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 4.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(1)

        bullet = self.api.get_entity("Bullet")
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]

        self.assertLess(bullet["components"]["Transform"]["x"], 40.0)
        self.assertIn("on_collision", event_names)

    def test_legacy_backend_respects_freeze_position_axes(self) -> None:
        scene_path = self._write_scene(
            "freeze_scene.json",
            {
                "name": "Freeze Scene",
                "entities": [
                    {
                        "name": "Constrained",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 10.0, "y": 15.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {
                                "enabled": True,
                                "body_type": "dynamic",
                                "gravity_scale": 1.0,
                                "velocity_x": 120.0,
                                "velocity_y": 80.0,
                                "constraints": ["FreezePositionX"],
                                "is_grounded": False,
                            },
                            "Collider": {"enabled": True, "width": 8.0, "height": 8.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(15)

        constrained = self.api.get_entity("Constrained")
        transform = constrained["components"]["Transform"]
        rigidbody = constrained["components"]["RigidBody"]

        self.assertAlmostEqual(transform["x"], 10.0, places=4)
        self.assertGreater(transform["y"], 15.0)
        self.assertEqual(rigidbody["velocity_x"], 0.0)

    def test_legacy_backend_keeps_grounded_across_adjacent_ground_seams(self) -> None:
        scene_path = self._write_scene(
            "ground_seam_scene.json",
            {
                "name": "Ground Seam Scene",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 25.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "velocity_x": 60.0, "velocity_y": 0.0, "is_grounded": True},
                            "Collider": {"enabled": True, "width": 12.0, "height": 10.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "GroundA",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 40.0, "height": 20.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "GroundB",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 40.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 40.0, "height": 20.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(40)

        player = self.api.get_entity("Player")
        transform = player["components"]["Transform"]
        rigidbody = player["components"]["RigidBody"]

        self.assertTrue(rigidbody["is_grounded"])
        self.assertAlmostEqual(transform["y"], 25.0, places=2)
        self.assertGreater(transform["x"], 20.0)

    def test_substeps_reduce_variable_dt_drift_for_ground_contacts(self) -> None:
        world_a = World()
        player_a = world_a.create_entity("Player")
        player_a.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player_a.add_component(RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_x=0.0, velocity_y=0.0, is_grounded=False))
        player_a.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        ground_a = world_a.create_entity("Ground")
        ground_a.add_component(Transform(x=0.0, y=40.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        ground_a.add_component(Collider(width=120.0, height=20.0, is_trigger=False))

        world_b = World()
        player_b = world_b.create_entity("Player")
        player_b.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player_b.add_component(RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_x=0.0, velocity_y=0.0, is_grounded=False))
        player_b.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        ground_b = world_b.create_entity("Ground")
        ground_b.add_component(Transform(x=0.0, y=40.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        ground_b.add_component(Collider(width=120.0, height=20.0, is_trigger=False))

        physics = PhysicsSystem(gravity=600.0)
        for _ in range(24):
            physics.update(world_a, 1.0 / 60.0)
        physics.update(world_b, 0.4)

        transform_a = player_a.get_component(Transform)
        rigidbody_a = player_a.get_component(RigidBody)
        transform_b = player_b.get_component(Transform)
        rigidbody_b = player_b.get_component(RigidBody)

        self.assertIsNotNone(transform_a)
        self.assertIsNotNone(rigidbody_a)
        self.assertIsNotNone(transform_b)
        self.assertIsNotNone(rigidbody_b)
        self.assertTrue(rigidbody_a.is_grounded)
        self.assertTrue(rigidbody_b.is_grounded)
        self.assertAlmostEqual(transform_a.y, transform_b.y, places=2)

    def test_direct_physics_landing_reports_floor_contact_and_grounded(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_x=0.0, velocity_y=0.0, is_grounded=False))
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        ground = world.create_entity("Ground")
        ground.add_component(Transform(x=0.0, y=40.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        ground.add_component(Collider(width=120.0, height=20.0, is_trigger=False))

        physics = PhysicsSystem(gravity=600.0)
        for _ in range(24):
            physics.update(world, 1.0 / 60.0)

        rigidbody = player.get_component(RigidBody)
        transform = player.get_component(Transform)
        state = physics.get_body_contact_state(player.id)
        floor_contacts = self._contacts_for(physics, "Player", "floor")

        self.assertIsNotNone(rigidbody)
        self.assertIsNotNone(transform)
        self.assertTrue(rigidbody.is_grounded)
        self.assertAlmostEqual(transform.y, 25.0, places=2)
        self.assertEqual(state["ground_entity"], "Ground")
        self.assertEqual(state["ground_normal"]["y"], -1.0)
        self.assertTrue(floor_contacts)
        self.assertTrue(any(contact.normal_y == -1.0 for contact in floor_contacts))
        self.assertTrue(any(contact.source in {"overlap", "snap_probe", "swept"} for contact in floor_contacts))

    def test_direct_physics_wall_contact_reports_wall_state(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=2000.0,
                velocity_y=0.0,
                is_grounded=False,
                collision_detection_mode="continuous",
            )
        )
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=20.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        wall.add_component(Collider(width=10.0, height=60.0, is_trigger=False))

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        rigidbody = player.get_component(RigidBody)
        state = physics.get_body_contact_state(player.id)
        wall_contacts = self._contacts_for(physics, "Player", "wall")

        self.assertIsNotNone(rigidbody)
        self.assertEqual(rigidbody.velocity_x, 0.0)
        self.assertFalse(rigidbody.is_grounded)
        self.assertTrue(state["touching_wall_right"])
        self.assertTrue(wall_contacts)
        self.assertEqual(wall_contacts[0].normal_x, -1.0)
        self.assertEqual(wall_contacts[0].contact_type, "wall")

    def test_direct_physics_ceiling_contact_reports_ceiling_state(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=20.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=0.0,
                velocity_y=-1000.0,
                is_grounded=False,
                collision_detection_mode="continuous",
            )
        )
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        ceiling = world.create_entity("Ceiling")
        ceiling.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        ceiling.add_component(Collider(width=120.0, height=10.0, is_trigger=False))

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        rigidbody = player.get_component(RigidBody)
        state = physics.get_body_contact_state(player.id)
        ceiling_contacts = self._contacts_for(physics, "Player", "ceiling")

        self.assertIsNotNone(rigidbody)
        self.assertEqual(rigidbody.velocity_y, 0.0)
        self.assertFalse(rigidbody.is_grounded)
        self.assertTrue(state["touching_ceiling"])
        self.assertTrue(ceiling_contacts)
        self.assertEqual(ceiling_contacts[0].normal_y, 1.0)

    def test_direct_physics_platform_edge_keeps_grounded_until_support_is_lost(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=12.0, y=25.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(RigidBody(body_type="dynamic", gravity_scale=0.0, velocity_x=60.0, velocity_y=0.0, is_grounded=True))
        player.add_component(Collider(width=12.0, height=10.0, is_trigger=False))
        ground = world.create_entity("Ground")
        ground.add_component(Transform(x=0.0, y=40.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        ground.add_component(Collider(width=40.0, height=20.0, is_trigger=False))

        physics = PhysicsSystem(gravity=0.0)
        grounded_prefix: list[bool] = []
        for _ in range(14):
            physics.update(world, 1.0 / 60.0)
            rigidbody = player.get_component(RigidBody)
            self.assertIsNotNone(rigidbody)
            grounded_prefix.append(bool(rigidbody.is_grounded))

        self.assertTrue(all(grounded_prefix[:12]))
        self.assertFalse(grounded_prefix[-1])

    def test_direct_physics_ground_state_is_stable_across_multiple_frames(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=25.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_x=0.0, velocity_y=0.0, is_grounded=True))
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        ground = world.create_entity("Ground")
        ground.add_component(Transform(x=0.0, y=40.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        ground.add_component(Collider(width=120.0, height=20.0, is_trigger=False))

        physics = PhysicsSystem(gravity=600.0)
        observed_y: list[float] = []
        observed_grounded: list[bool] = []
        for _ in range(20):
            physics.update(world, 1.0 / 60.0)
            rigidbody = player.get_component(RigidBody)
            transform = player.get_component(Transform)
            self.assertIsNotNone(rigidbody)
            self.assertIsNotNone(transform)
            observed_y.append(float(transform.y))
            observed_grounded.append(bool(rigidbody.is_grounded))

        self.assertTrue(all(observed_grounded))
        self.assertLess(max(observed_y) - min(observed_y), 0.05)

    def test_direct_physics_fast_body_does_not_tunnel_through_thin_platform(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=0.0,
                velocity_y=8000.0,
                is_grounded=False,
                collision_detection_mode="continuous",
            )
        )
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        platform = world.create_entity("ThinPlatform")
        platform.add_component(Transform(x=0.0, y=50.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        platform.add_component(Collider(width=60.0, height=1.0, is_trigger=False))

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        rigidbody = player.get_component(RigidBody)
        transform = player.get_component(Transform)
        floor_contacts = self._contacts_for(physics, "Player", "floor")

        self.assertIsNotNone(rigidbody)
        self.assertIsNotNone(transform)
        self.assertTrue(rigidbody.is_grounded)
        self.assertLess(transform.y, 50.0)
        self.assertTrue(any(contact.source == "swept" for contact in floor_contacts))
        self.assertTrue(any(contact.separation <= physics.skin_width * 1.5 for contact in floor_contacts if contact.source == "swept"))

    def test_direct_physics_fast_body_does_not_tunnel_through_thin_ceiling(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=80.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=0.0,
                velocity_y=-8000.0,
                is_grounded=False,
                collision_detection_mode="continuous",
            )
        )
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        platform = world.create_entity("ThinCeiling")
        platform.add_component(Transform(x=0.0, y=50.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        platform.add_component(Collider(width=60.0, height=1.0, is_trigger=False))

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        rigidbody = player.get_component(RigidBody)
        transform = player.get_component(Transform)
        ceiling_contacts = self._contacts_for(physics, "Player", "ceiling")

        self.assertIsNotNone(rigidbody)
        self.assertIsNotNone(transform)
        self.assertEqual(rigidbody.velocity_y, 0.0)
        self.assertGreater(transform.y, 50.0)
        self.assertTrue(any(contact.source == "swept" for contact in ceiling_contacts))
        self.assertTrue(any(contact.separation <= physics.skin_width * 1.5 for contact in ceiling_contacts if contact.source == "swept"))

    def test_direct_physics_fast_body_does_not_tunnel_through_thin_wall(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        player.add_component(
            RigidBody(
                body_type="dynamic",
                gravity_scale=0.0,
                velocity_x=8000.0,
                velocity_y=0.0,
                is_grounded=False,
                collision_detection_mode="continuous",
            )
        )
        player.add_component(Collider(width=10.0, height=10.0, is_trigger=False))
        wall = world.create_entity("ThinWall")
        wall.add_component(Transform(x=50.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        wall.add_component(Collider(width=1.0, height=60.0, is_trigger=False))

        physics = PhysicsSystem(gravity=0.0)
        physics.update(world, 1.0 / 60.0)

        rigidbody = player.get_component(RigidBody)
        transform = player.get_component(Transform)
        wall_contacts = self._contacts_for(physics, "Player", "wall")

        self.assertIsNotNone(rigidbody)
        self.assertIsNotNone(transform)
        self.assertEqual(rigidbody.velocity_x, 0.0)
        self.assertLess(transform.x, 50.0)
        self.assertTrue(any(contact.source == "swept" for contact in wall_contacts))
        self.assertTrue(any(contact.separation <= physics.skin_width * 1.5 for contact in wall_contacts if contact.source == "swept"))


if __name__ == "__main__":
    unittest.main()
