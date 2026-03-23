import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI
from engine.components.transform import Transform
from engine.debug.golden_run import capture_headless_run, compare_golden_runs
from engine.debug.state_fingerprint import compute_world_hash
from engine.ecs.world import World
from engine.project.project_service import ProjectService


def _scene_payload() -> dict:
    return {
        "name": "GoldenScene",
        "entities": [
            {
                "name": "Player",
                "active": True,
                "tag": "Player",
                "layer": "Gameplay",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 10.0,
                        "y": 20.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    },
                    "RigidBody": {
                        "enabled": True,
                        "body_type": "dynamic",
                        "gravity_scale": 1.0,
                        "velocity_x": 0.0,
                        "velocity_y": 0.0,
                    },
                },
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


class HeadlessHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.level_path = self.root / "levels" / "golden_scene.json"
        self.level_path.write_text(json.dumps(_scene_payload(), indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _run_capture(self, *, seed: int = 7, frames: int = 10) -> dict:
        api = EngineAPI(project_root=self.root.as_posix())
        try:
            api.load_level("levels/golden_scene.json")
            api.set_seed(seed)
            api.play()
            return capture_headless_run(api.game, frames=frames, capture_every=2)
        finally:
            api.shutdown()

    def test_headless_golden_run_is_reproducible_for_same_seed(self) -> None:
        first = self._run_capture(seed=11, frames=12)
        second = self._run_capture(seed=11, frames=12)
        self.assertEqual(compare_golden_runs(first, second), [])

    def test_headless_golden_run_detects_state_drift(self) -> None:
        baseline = self._run_capture(seed=3, frames=8)

        mutated = json.loads(self.level_path.read_text(encoding="utf-8"))
        mutated["entities"][0]["components"]["Transform"]["x"] = 55.0
        self.level_path.write_text(json.dumps(mutated, indent=2), encoding="utf-8")

        changed = self._run_capture(seed=3, frames=8)
        self.assertNotEqual(compare_golden_runs(baseline, changed), [])

    def test_world_hash_is_stable_even_if_entity_creation_order_differs(self) -> None:
        first = World()
        alpha = first.create_entity("Alpha")
        alpha.add_component(Transform(x=1.0, y=2.0))
        beta = first.create_entity("Beta")
        beta.add_component(Transform(x=3.0, y=4.0))

        second = World()
        beta_second = second.create_entity("Beta")
        beta_second.add_component(Transform(x=3.0, y=4.0))
        alpha_second = second.create_entity("Alpha")
        alpha_second.add_component(Transform(x=1.0, y=2.0))

        self.assertEqual(compute_world_hash(first), compute_world_hash(second))


if __name__ == "__main__":
    unittest.main()
