import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.api import EngineAPI

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


if __name__ == "__main__":
    unittest.main()
