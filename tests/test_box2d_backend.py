import json
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
class Box2DBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "Box2DProject"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, payload: dict) -> Path:
        path = self.project_root / "levels" / "box2d_scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _run_scene(self) -> dict[str, tuple[float, float]]:
        scene_path = self._write_scene(
            {
                "name": "Box2D Scene",
                "entities": [
                    {
                        "name": "Floor",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 120.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "shape_type": "box", "width": 180.0, "height": 20.0, "friction": 0.4, "restitution": 0.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "BoxA",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": -12.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "velocity_x": 0.0, "velocity_y": 0.0, "is_grounded": False},
                            "Collider": {"enabled": True, "shape_type": "box", "width": 16.0, "height": 16.0, "friction": 0.3, "restitution": 0.0, "density": 1.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "BoxB",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": -12.0, "y": 20.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "velocity_x": 0.0, "velocity_y": 0.0, "is_grounded": False},
                            "Collider": {"enabled": True, "shape_type": "box", "width": 16.0, "height": 16.0, "friction": 0.3, "restitution": 0.0, "density": 1.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Ball",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 36.0, "y": 16.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "velocity_x": 0.0, "velocity_y": 0.0, "is_grounded": False},
                            "Collider": {"enabled": True, "shape_type": "circle", "radius": 8.0, "width": 16.0, "height": 16.0, "friction": 0.2, "restitution": 0.15, "density": 1.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "box2d"}},
            }
        )
        api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())
        try:
            api.load_level(scene_path.as_posix())
            api.play()
            api.step(180)
            return {
                name: (
                    round(api.get_entity(name)["components"]["Transform"]["x"], 3),
                    round(api.get_entity(name)["components"]["Transform"]["y"], 3),
                )
                for name in ("BoxA", "BoxB", "Ball")
            }
        finally:
            api.shutdown()

    def test_box2d_scene_is_reproducible_on_same_machine(self) -> None:
        first = self._run_scene()
        second = self._run_scene()
        self.assertEqual(first, second)

    def test_box2d_continuous_mode_prevents_tunneling(self) -> None:
        scene_path = self._write_scene(
            {
                "name": "Box2D CCD",
                "entities": [
                    {
                        "name": "Bullet",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 0.0, "velocity_x": 5000.0, "velocity_y": 0.0, "collision_detection_mode": "continuous", "is_grounded": True},
                            "Collider": {"enabled": True, "shape_type": "box", "width": 0.2, "height": 0.2, "density": 1.0, "restitution": 0.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 2.1, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "shape_type": "box", "width": 0.2, "height": 2.4, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "box2d"}},
            }
        )
        api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())
        try:
            api.load_level(scene_path.as_posix())
            api.play()
            api.step(1)
            bullet_x = api.get_entity("Bullet")["components"]["Transform"]["x"]
            event_names = [event.name for event in api.game._event_bus.get_recent_events()]
            self.assertLess(bullet_x, 2.1)
            self.assertIn("on_collision", event_names)
        finally:
            api.shutdown()

    def test_box2d_runtime_velocity_changes_sync_into_existing_body(self) -> None:
        scene_path = self._write_scene(
            {
                "name": "Box2D Runtime Sync",
                "entities": [
                    {
                        "name": "Mover",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 0.0, "velocity_x": 0.0, "velocity_y": 0.0, "is_grounded": False},
                            "Collider": {"enabled": True, "shape_type": "box", "width": 8.0, "height": 8.0, "density": 1.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "box2d"}},
            }
        )
        api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state_runtime_sync").as_posix())
        try:
            api.load_level(scene_path.as_posix())
            api.play()
            mover = api.game.world.get_entity_by_name("Mover")
            from engine.components.rigidbody import RigidBody

            mover.get_component(RigidBody).velocity_x = 120.0
            api.step(10)
            self.assertGreater(api.get_entity("Mover")["components"]["Transform"]["x"], 0.0)
        finally:
            api.shutdown()


if __name__ == "__main__":
    unittest.main()
