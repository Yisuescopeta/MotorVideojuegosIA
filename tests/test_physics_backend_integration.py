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


class _PhysicsBackendIntegrationHarness:
    def __init__(self, test_case: unittest.TestCase) -> None:
        self._test_case = test_case
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "PhysicsIntegrationProject"

    def cleanup(self) -> None:
        self._temp_dir.cleanup()

    def write_scene(self, filename: str, *, backend_name: str) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._scene_payload(backend_name), indent=2), encoding="utf-8")
        return path

    def make_api(self, global_state_name: str) -> EngineAPI:
        api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=(self.root / global_state_name).as_posix(),
        )
        self._test_case.addCleanup(api.shutdown)
        return api

    def _scene_payload(self, backend_name: str) -> dict:
        return {
            "name": "Physics Backend Integration",
            "entities": [
                {
                    "name": "Mover",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 12.0,
                            "y": 0.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        },
                        "RigidBody": {
                            "enabled": True,
                            "body_type": "dynamic",
                            "gravity_scale": 0.0,
                            "velocity_x": 0.0,
                            "velocity_y": 0.0,
                            "is_grounded": True,
                        },
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
                        "Transform": {
                            "enabled": True,
                            "x": 18.0,
                            "y": 0.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        },
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


class PhysicsBackendIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = _PhysicsBackendIntegrationHarness(self)

    def tearDown(self) -> None:
        self.harness.cleanup()

    def _assert_engine_api_contract(
        self,
        api: EngineAPI,
        *,
        requested_backend: str,
        effective_backend: str,
    ) -> None:
        selection_before = api.get_physics_backend_selection()
        backend_infos = {item["name"]: item for item in api.list_physics_backends()}
        status_before = api.get_status()

        self.assertEqual(selection_before["requested_backend"], requested_backend)
        self.assertEqual(selection_before["effective_backend"], effective_backend)
        self.assertIn("legacy_aabb", backend_infos)
        self.assertIn(requested_backend, backend_infos)
        self.assertGreaterEqual(status_before["entity_count"], 2)

        api.play()
        api.step(1)

        aabb_hits = api.query_physics_aabb(10.0, -20.0, 30.0, 20.0)
        ray_hits = api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0)
        selection_after = api.get_physics_backend_selection()
        status_after = api.get_status()

        self.assertTrue(aabb_hits)
        self.assertTrue(ray_hits)
        self.assertEqual(selection_after["requested_backend"], requested_backend)
        self.assertEqual(selection_after["effective_backend"], effective_backend)
        self.assertGreaterEqual(status_after["frame"], status_before["frame"])
        self.assertEqual(status_after["entity_count"], status_before["entity_count"])

        aabb_hit = aabb_hits[0]
        self.assertIn("entity", aabb_hit)
        self.assertIn("entity_id", aabb_hit)
        self.assertIn("is_trigger", aabb_hit)

        ray_hit = ray_hits[0]
        self.assertIn("entity", ray_hit)
        self.assertIn("entity_id", ray_hit)
        self.assertIn("distance", ray_hit)
        self.assertIn("point", ray_hit)
        self.assertIn("is_trigger", ray_hit)
        self.assertIsInstance(ray_hit["point"], dict)
        self.assertIn("x", ray_hit["point"])
        self.assertIn("y", ray_hit["point"])

        api.stop()
        selection_after_stop = api.get_physics_backend_selection()
        self.assertEqual(selection_after_stop["requested_backend"], requested_backend)
        self.assertEqual(selection_after_stop["effective_backend"], effective_backend)

    def test_legacy_backend_integration_contract_is_stable(self) -> None:
        api = self.harness.make_api("global_state_legacy")
        scene_path = self.harness.write_scene("legacy_integration_scene.json", backend_name="legacy_aabb")

        api.load_level(scene_path.as_posix())

        self._assert_engine_api_contract(
            api,
            requested_backend="legacy_aabb",
            effective_backend="legacy_aabb",
        )

    @unittest.skipIf(Box2D is None, "Box2D optional dependency not available")
    def test_box2d_backend_integration_contract_is_stable(self) -> None:
        api = self.harness.make_api("global_state_box2d")
        scene_path = self.harness.write_scene("box2d_integration_scene.json", backend_name="box2d")

        api.load_level(scene_path.as_posix())

        self._assert_engine_api_contract(
            api,
            requested_backend="box2d",
            effective_backend="box2d",
        )

    def test_switching_backends_keeps_engine_api_stable(self) -> None:
        api = self.harness.make_api("global_state_switch")
        scene_path = self.harness.write_scene("switch_integration_scene.json", backend_name="legacy_aabb")

        api.load_level(scene_path.as_posix())
        initial_infos = {item["name"]: item for item in api.list_physics_backends()}

        legacy_result = api.set_physics_backend("legacy_aabb")
        self.assertTrue(legacy_result["success"])
        legacy_selection = api.get_physics_backend_selection()
        self.assertEqual(legacy_selection["requested_backend"], "legacy_aabb")
        self.assertEqual(legacy_selection["effective_backend"], "legacy_aabb")

        box2d_result = api.set_physics_backend("box2d")
        self.assertTrue(box2d_result["success"])
        box2d_selection = api.get_physics_backend_selection()
        expected_effective_backend = "box2d" if initial_infos["box2d"]["available"] else "legacy_aabb"
        self.assertEqual(box2d_selection["requested_backend"], "box2d")
        self.assertEqual(box2d_selection["effective_backend"], expected_effective_backend)

        api.play()
        api.step(1)
        self.assertTrue(api.query_physics_aabb(10.0, -20.0, 30.0, 20.0))
        self.assertTrue(api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0))
        api.stop()


class PhysicsBackendFallbackIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = _PhysicsBackendIntegrationHarness(self)

    def tearDown(self) -> None:
        self.harness.cleanup()

    @patch("engine.api.engine_api.Box2DPhysicsBackend", side_effect=RuntimeError("box2d init failed"))
    def test_box2d_unavailable_falls_back_without_crashing_engine_api(self, _box2d_backend_mock) -> None:
        api = self.harness.make_api("global_state_fallback")
        scene_path = self.harness.write_scene("box2d_fallback_integration_scene.json", backend_name="box2d")

        api.load_level(scene_path.as_posix())

        backend_infos = {item["name"]: item for item in api.list_physics_backends()}
        selection_before = api.get_physics_backend_selection()

        self.assertIn("box2d", backend_infos)
        self.assertFalse(backend_infos["box2d"]["available"])
        self.assertEqual(backend_infos["box2d"]["unavailable_reason"], "box2d init failed")
        self.assertEqual(selection_before["requested_backend"], "box2d")
        self.assertEqual(selection_before["effective_backend"], "legacy_aabb")
        self.assertTrue(selection_before["used_fallback"])

        api.play()
        api.step(1)

        aabb_hits = api.query_physics_aabb(10.0, -20.0, 30.0, 20.0)
        ray_hits = api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0)
        selection_after = api.get_physics_backend_selection()

        self.assertTrue(aabb_hits)
        self.assertTrue(ray_hits)
        self.assertEqual(selection_after["requested_backend"], "box2d")
        self.assertEqual(selection_after["effective_backend"], "legacy_aabb")
        self.assertTrue(selection_after["used_fallback"])
        self.assertEqual(api.get_feature_metadata()["physics_2d"]["backend"], "box2d")

        api.stop()

