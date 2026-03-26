import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI


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
            {
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
                            "Collider": {"enabled": True, "width": 10.0, "height": 10.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 18.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 10.0, "height": 40.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
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

        ray_hits = self.api.query_physics_ray(0.0, 0.0, 1.0, 0.0, 50.0)
        aabb_hits = self.api.query_physics_aabb(10.0, -20.0, 30.0, 20.0)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]

        self.assertTrue(ray_hits)
        self.assertEqual(ray_hits[0]["entity"], "Mover")
        self.assertIn("Wall", {item["entity"] for item in aabb_hits})
        self.assertIn("on_collision", event_names)

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
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]

        self.assertLess(bullet["components"]["Transform"]["x"], 40.0)
        self.assertIn("on_collision", event_names)


if __name__ == "__main__":
    unittest.main()
