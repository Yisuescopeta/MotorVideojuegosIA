import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.api import EngineAPI
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend

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

    def test_legacy_backend_registers_collider_after_structure_version_change(self) -> None:
        world = World()
        entity = world.create_entity("Actor")
        entity.add_component(Transform())
        backend = LegacyAABBPhysicsBackend(None, None)

        backend.sync_world(world)

        self.assertNotIn(entity.id, backend._registered_shapes)
        structure_before = world.structure_version

        entity.add_component(Collider())
        backend.sync_world(world)

        self.assertGreater(world.structure_version, structure_before)
        self.assertIn(entity.id, backend._registered_shapes)

    def test_legacy_backend_sync_skips_scan_when_structure_version_is_unchanged(self) -> None:
        class CountingWorld(World):
            def __init__(self) -> None:
                super().__init__()
                self.get_all_entities_calls = 0

            def get_all_entities(self) -> list[Entity]:
                self.get_all_entities_calls += 1
                return super().get_all_entities()

        world = CountingWorld()
        entity = world.create_entity("Mover")
        transform = Transform()
        rigidbody = RigidBody(velocity_x=12.0)
        entity.add_component(transform)
        entity.add_component(rigidbody)
        entity.add_component(Collider())
        backend = LegacyAABBPhysicsBackend(None, None)

        backend.sync_world(world)
        transform.x = 25.0
        rigidbody.velocity_x = 48.0
        backend.sync_world(world)

        self.assertEqual(world.get_all_entities_calls, 1)
        self.assertIn(entity.id, backend._registered_bodies)
        self.assertIn(entity.id, backend._registered_shapes)

    def test_legacy_backend_sync_keeps_full_scan_fallback_without_structure_version(self) -> None:
        entity = Entity("Legacy")
        entity.add_component(Transform())
        entity.add_component(Collider())

        class LegacyWorld:
            def __init__(self) -> None:
                self.get_all_entities_calls = 0

            def get_all_entities(self) -> list[Entity]:
                self.get_all_entities_calls += 1
                return [entity]

        world = LegacyWorld()
        backend = LegacyAABBPhysicsBackend(None, None)

        backend.sync_world(world)
        backend.sync_world(world)

        self.assertEqual(world.get_all_entities_calls, 2)
        self.assertIn(entity.id, backend._registered_shapes)

    def test_legacy_backend_unregisters_collider_after_structure_version_change(self) -> None:
        world = World()
        entity = world.create_entity("Actor")
        entity.add_component(Transform())
        entity.add_component(Collider())
        backend = LegacyAABBPhysicsBackend(None, None)

        backend.sync_world(world)
        self.assertIn(entity.id, backend._registered_shapes)
        structure_before = world.structure_version

        entity.remove_component(Collider)
        backend.sync_world(world)

        self.assertGreater(world.structure_version, structure_before)
        self.assertNotIn(entity.id, backend._registered_shapes)

    def test_legacy_backend_swept_contacts_use_world_get_entity(self) -> None:
        bullet = SimpleNamespace(id=101, name="Bullet", get_component=lambda _component_type: None)
        wall = SimpleNamespace(id=202, name="Wall", get_component=lambda _component_type: None)

        class SweptPhysicsSystem:
            def update(self, _world, _dt: float) -> None:
                pass

            def consume_swept_contacts(self) -> list[tuple[int, int]]:
                return [(bullet.id, wall.id)]

        class IndexedWorld:
            def __init__(self) -> None:
                self.get_entity_calls: list[int] = []

            def get_all_entities(self) -> list[SimpleNamespace]:
                return [bullet, wall]

            def get_entity(self, entity_id: int) -> SimpleNamespace | None:
                self.get_entity_calls.append(entity_id)
                return {bullet.id: bullet, wall.id: wall}.get(entity_id)

        world = IndexedWorld()
        backend = LegacyAABBPhysicsBackend(SweptPhysicsSystem(), None)

        backend.step(world, 1.0 / 60.0)
        contacts = backend.collect_contacts(world)

        self.assertEqual(world.get_entity_calls, [bullet.id, wall.id])
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].entity_a, "Bullet")
        self.assertEqual(contacts[0].entity_b, "Wall")
        self.assertEqual(contacts[0].entity_a_id, bullet.id)
        self.assertEqual(contacts[0].entity_b_id, wall.id)
        self.assertFalse(contacts[0].is_trigger)

    def test_legacy_backend_swept_contacts_fall_back_without_world_get_entity(self) -> None:
        bullet = SimpleNamespace(id=303, name="Bullet", get_component=lambda _component_type: None)
        wall = SimpleNamespace(id=404, name="Wall", get_component=lambda _component_type: None)

        class SweptPhysicsSystem:
            def update(self, _world, _dt: float) -> None:
                pass

            def consume_swept_contacts(self) -> list[tuple[int, int]]:
                return [(bullet.id, wall.id)]

        class LegacyWorld:
            def get_all_entities(self) -> list[SimpleNamespace]:
                return [bullet, wall]

        world = LegacyWorld()
        backend = LegacyAABBPhysicsBackend(SweptPhysicsSystem(), None)

        backend.step(world, 1.0 / 60.0)
        contacts = backend.collect_contacts(world)

        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].entity_a, "Bullet")
        self.assertEqual(contacts[0].entity_b, "Wall")
        self.assertEqual(contacts[0].entity_a_id, bullet.id)
        self.assertEqual(contacts[0].entity_b_id, wall.id)
        self.assertFalse(contacts[0].is_trigger)

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


    def test_legacy_ray_normal_aabb(self) -> None:
        """Legacy query_ray returns correct normal for AABB hits from all 4 directions."""
        world = World()
        backend = LegacyAABBPhysicsBackend(None, None)

        entity = world.create_entity("Box")
        entity.add_component(Transform(x=100.0, y=100.0))
        entity.add_component(Collider(shape_type="box", width=20.0, height=20.0))
        backend.sync_world(world)

        # Ray from left
        hits = backend.query_ray(world, (80.0, 100.0), (1.0, 0.0), 50.0)
        self.assertTrue(hits, "Ray from left should hit")
        self.assertIn("normal", hits[0], "Hit must include normal field")
        self.assertAlmostEqual(hits[0]["normal"]["x"], -1.0, delta=0.01)
        self.assertAlmostEqual(hits[0]["normal"]["y"], 0.0, delta=0.01)

        # Ray from right
        hits = backend.query_ray(world, (120.0, 100.0), (-1.0, 0.0), 50.0)
        self.assertTrue(hits, "Ray from right should hit")
        self.assertAlmostEqual(hits[0]["normal"]["x"], 1.0, delta=0.01)
        self.assertAlmostEqual(hits[0]["normal"]["y"], 0.0, delta=0.01)

        # Ray from top
        hits = backend.query_ray(world, (100.0, 80.0), (0.0, 1.0), 50.0)
        self.assertTrue(hits, "Ray from top should hit")
        self.assertAlmostEqual(hits[0]["normal"]["x"], 0.0, delta=0.01)
        self.assertAlmostEqual(hits[0]["normal"]["y"], -1.0, delta=0.01)

        # Ray from bottom
        hits = backend.query_ray(world, (100.0, 120.0), (0.0, -1.0), 50.0)
        self.assertTrue(hits, "Ray from bottom should hit")
        self.assertAlmostEqual(hits[0]["normal"]["x"], 0.0, delta=0.01)
        self.assertAlmostEqual(hits[0]["normal"]["y"], 1.0, delta=0.01)

    def test_legacy_ray_normal_capsule(self) -> None:
        """Legacy query_ray returns normal for capsule hits (body and caps)."""
        world = World()
        backend = LegacyAABBPhysicsBackend(None, None)

        entity = world.create_entity("Capsule")
        entity.add_component(Transform(x=100.0, y=100.0))
        entity.add_component(
            Collider(shape_type="capsule", radius=10.0, capsule_height=40.0)
        )
        backend.sync_world(world)

        # Ray hitting body from left
        hits = backend.query_ray(world, (80.0, 100.0), (1.0, 0.0), 50.0)
        self.assertTrue(hits, "Ray should hit capsule body from left")
        self.assertIn("normal", hits[0])
        self.assertAlmostEqual(hits[0]["normal"]["x"], -1.0, delta=0.01)

        # Ray hitting top cap
        hits = backend.query_ray(world, (100.0, 60.0), (0.0, 1.0), 50.0)
        self.assertTrue(hits, "Ray should hit capsule top cap")
        self.assertIn("normal", hits[0])
        self.assertLess(hits[0]["normal"]["y"], 0.0, "Top cap normal should point up")

        # Ray hitting bottom cap
        hits = backend.query_ray(world, (100.0, 140.0), (0.0, -1.0), 50.0)
        self.assertTrue(hits, "Ray should hit capsule bottom cap")
        self.assertIn("normal", hits[0])
        self.assertGreater(hits[0]["normal"]["y"], 0.0, "Bottom cap normal should point down")

    def test_legacy_ray_normal_points_away_from_hit_object(self) -> None:
        """Normal must point from surface toward ray origin (opposite ray direction)."""
        world = World()
        backend = LegacyAABBPhysicsBackend(None, None)

        entity = world.create_entity("Box")
        entity.add_component(Transform(x=100.0, y=100.0))
        entity.add_component(Collider(shape_type="box", width=20.0, height=20.0))
        backend.sync_world(world)

        # Ray from left hits left face → normal should be (-1, 0) pointing toward origin
        hits = backend.query_ray(world, (80.0, 95.0), (1.0, 0.0), 50.0)
        self.assertTrue(hits)
        nx, ny = hits[0]["normal"]["x"], hits[0]["normal"]["y"]
        hx, hy = hits[0]["point"]["x"], hits[0]["point"]["y"]
        to_origin_x = 80.0 - hx
        to_origin_y = 95.0 - hy
        dot = nx * to_origin_x + ny * to_origin_y
        self.assertGreater(dot, 0.0, f"Normal must point toward ray origin, dot={dot}")

        # Ray from right hits right face
        hits = backend.query_ray(world, (120.0, 95.0), (-1.0, 0.0), 50.0)
        self.assertTrue(hits)
        nx, ny = hits[0]["normal"]["x"], hits[0]["normal"]["y"]
        hx, hy = hits[0]["point"]["x"], hits[0]["point"]["y"]
        to_origin_x = 120.0 - hx
        to_origin_y = 95.0 - hy
        dot = nx * to_origin_x + ny * to_origin_y
        self.assertGreater(dot, 0.0, f"Normal must point toward ray origin, dot={dot}")

        # Ray from top hits top face
        hits = backend.query_ray(world, (95.0, 80.0), (0.0, 1.0), 50.0)
        self.assertTrue(hits)
        nx, ny = hits[0]["normal"]["x"], hits[0]["normal"]["y"]
        hx, hy = hits[0]["point"]["x"], hits[0]["point"]["y"]
        to_origin_x = 95.0 - hx
        to_origin_y = 80.0 - hy
        dot = nx * to_origin_x + ny * to_origin_y
        self.assertGreater(dot, 0.0, f"Normal must point toward ray origin, dot={dot}")

    def test_query_aabb_hits_collision_shape_2d(self) -> None:
        """query_aabb finds entity with CollisionShape2D (no Collider)."""
        from engine.components.collision_shape_2d import CollisionShape2D
        world = World()
        backend = LegacyAABBPhysicsBackend(None, None)

        target = world.create_entity("ShapeTarget")
        target.add_component(Transform(x=200.0, y=100.0))
        target.add_component(CollisionShape2D(width=32.0, height=32.0))

        hits = backend.query_aabb(world, (180.0, 80.0, 220.0, 120.0))
        names = [h["entity"] for h in hits]
        self.assertIn("ShapeTarget", names,
                      "query_aabb should find CollisionShape2D entity without Collider")

    def test_query_ray_hits_collision_polygon_2d(self) -> None:
        """query_ray finds entity with CollisionPolygon2D (no Collider)."""
        from engine.components.collision_polygon_2d import CollisionPolygon2D
        world = World()
        backend = LegacyAABBPhysicsBackend(None, None)

        target = world.create_entity("PolyTarget")
        target.add_component(Transform(x=200.0, y=100.0))
        target.add_component(CollisionPolygon2D(
            polygon=[[-16, -16], [16, -16], [16, 16], [-16, 16]]
        ))

        hits = backend.query_ray(
            world=world,
            origin=(100.0, 100.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        names = [h["entity"] for h in hits]
        self.assertIn("PolyTarget", names,
                      "query_ray should find CollisionPolygon2D entity without Collider")

    def test_query_shape_cast_hits_collision_shape_set(self) -> None:
        """query_shape_cast finds entity with CollisionShapeSet2D (no Collider)."""
        from engine.components.collision_shape_set_2d import CollisionShape2DDef, CollisionShapeSet2D
        world = World()
        backend = LegacyAABBPhysicsBackend(None, None)

        target = world.create_entity("ShapeSetTarget")
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

        hits = backend.query_shape_cast(
            world=world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(100.0, 100.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertGreater(len(hits), 0,
                           "query_shape_cast should find CollisionShapeSet2D entity without Collider")

if __name__ == "__main__":
    unittest.main()
