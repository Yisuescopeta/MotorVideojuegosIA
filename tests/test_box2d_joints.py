import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI

try:
    import Box2D  # noqa: F401
except Exception:  # pragma: no cover
    Box2D = None


@unittest.skipIf(Box2D is None, "Box2D optional dependency not available")
class Box2DJointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "JointProject"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self) -> Path:
        scene = {
            "name": "Pendulum Joint",
            "entities": [
                {
                    "name": "Anchor",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Collider": {"enabled": True, "shape_type": "box", "width": 2.0, "height": 2.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                    },
                },
                {
                    "name": "Bob",
                    "active": True,
                    "tag": "",
                    "layer": "Gameplay",
                    "components": {
                        "Transform": {"enabled": True, "x": 30.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "velocity_x": 0.0, "velocity_y": 0.0},
                        "Collider": {"enabled": True, "shape_type": "circle", "radius": 4.0, "width": 8.0, "height": 8.0, "density": 1.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        "Joint2D": {"enabled": True, "joint_type": "distance", "connected_entity": "Anchor", "rest_length": 30.0, "frequency_hz": 0.0, "damping_ratio": 0.0},
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {"physics_2d": {"backend": "box2d"}},
        }
        path = self.project_root / "levels" / "pendulum_scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(scene, indent=2), encoding="utf-8")
        return path

    def test_box2d_distance_joint_keeps_pendulum_length(self) -> None:
        api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())
        try:
            api.load_level(self._write_scene().as_posix())
            api.play()
            api.step(120)
            bob = api.get_entity("Bob")["components"]["Transform"]
            distance = math.hypot(float(bob["x"]), float(bob["y"]))
            metrics = api.game._physics_backends["box2d"].get_step_metrics()
            self.assertAlmostEqual(distance, 30.0, delta=1.5)
            self.assertEqual(int(metrics.get("joints", 0)), 1)
        finally:
            api.shutdown()


if __name__ == "__main__":
    unittest.main()
