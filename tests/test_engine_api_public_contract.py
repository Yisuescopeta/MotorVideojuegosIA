import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI


class EngineAPIPublicContractTests(unittest.TestCase):
    def test_inject_input_state_applies_runtime_override(self) -> None:
        api = EngineAPI()
        api.load_level("levels/platformer_test_scene.json")
        api.play()

        result = api.inject_input_state(
            "Player",
            {"horizontal": 1.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0},
            frames=2,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["frames"], 2)

        api.step(1)
        input_state = api.get_input_state("Player")
        self.assertEqual(input_state["horizontal"], 1.0)
        self.assertEqual(input_state["action_1"], 0.0)
        api.shutdown()

    def test_inject_input_state_fails_without_runtime(self) -> None:
        api = EngineAPI()
        api.game = None

        result = api.inject_input_state("Player", {"horizontal": 1.0}, frames=0)

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Engine not initialized")

    def test_inject_input_state_fails_without_input_system(self) -> None:
        api = EngineAPI()
        self.assertIsNotNone(api.game)
        api.game._input_system = None

        result = api.inject_input_state("Player", {"horizontal": 1.0}, frames=0)

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Input system not ready")

    def test_get_recent_events_returns_serializable_payloads(self) -> None:
        api = EngineAPI()
        self.assertIsNotNone(api.game)
        self.assertIsNotNone(api.game._event_bus)
        api.game._event_bus.clear_history()
        api.game._event_bus.emit("event_a", {"value": 1})
        api.game._event_bus.emit("event_b", {"value": 2})

        events = api.get_recent_events(count=1)

        self.assertEqual(events, [{"name": "event_b", "data": {"value": 2}}])


class RLPublicContractRegressionTests(unittest.TestCase):
    def test_rl_modules_do_not_touch_private_runtime_hooks(self) -> None:
        forbidden_tokens = ("_input_system", "_event_bus")
        targets = [
            Path("engine/rl/gym_env.py"),
            Path("engine/rl/pettingzoo_env.py"),
            Path("engine/rl/scenario_dataset.py"),
        ]

        for path in targets:
            source = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, source, msg=f"{path.as_posix()} still references {token}")


class EngineAPISandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.outside_root = self.workspace / "outside"
        self.outside_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, base: Path, relative_path: str, name: str = "Scene") -> Path:
        path = base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "name": name,
                    "entities": [],
                    "rules": [],
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        return path

    def _write_prefab(self, base: Path, relative_path: str) -> Path:
        path = base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "root_name": "SandboxPrefab",
                    "entities": [],
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        return path

    def test_load_level_allows_paths_inside_project_when_sandbox_enabled(self) -> None:
        self._write_scene(self.project_root, "levels/inside.json", name="Inside Scene")
        api = EngineAPI(project_root=self.project_root.as_posix(), sandbox_paths=True)
        self.addCleanup(api.shutdown)

        api.load_level("levels/inside.json")

        self.assertEqual(api.scene_manager.scene_name, "Inside Scene")

    def test_load_level_blocks_absolute_path_outside_project_when_sandbox_enabled(self) -> None:
        outside_scene = self._write_scene(self.outside_root, "external.json", name="External Scene")
        api = EngineAPI(project_root=self.project_root.as_posix(), sandbox_paths=True)
        self.addCleanup(api.shutdown)

        with self.assertRaisesRegex(Exception, "Sandbox blocked path outside project root"):
            api.load_level(outside_scene.as_posix())

    def test_instantiate_prefab_blocks_outside_project_when_sandbox_enabled(self) -> None:
        self._write_scene(self.project_root, "levels/inside.json", name="Inside Scene")
        outside_prefab = self._write_prefab(self.outside_root, "prefabs/external_prefab.json")
        api = EngineAPI(project_root=self.project_root.as_posix(), sandbox_paths=True)
        self.addCleanup(api.shutdown)
        api.load_level("levels/inside.json")

        result = api.instantiate_prefab(outside_prefab.as_posix())

        self.assertFalse(result["success"])
        self.assertIn("Sandbox blocked path outside project root", result["message"])

    def test_save_scene_blocks_outside_project_when_sandbox_enabled(self) -> None:
        self._write_scene(self.project_root, "levels/inside.json", name="Inside Scene")
        outside_scene = self.outside_root / "saved_elsewhere.json"
        api = EngineAPI(project_root=self.project_root.as_posix(), sandbox_paths=True)
        self.addCleanup(api.shutdown)
        api.load_level("levels/inside.json")

        result = api.save_scene(path=outside_scene.as_posix())

        self.assertFalse(result["success"])
        self.assertIn("Sandbox blocked path outside project root", result["message"])

    def test_load_level_outside_project_remains_allowed_when_sandbox_disabled(self) -> None:
        outside_scene = self._write_scene(self.outside_root, "external.json", name="External Scene")
        api = EngineAPI(project_root=self.project_root.as_posix(), sandbox_paths=False)
        self.addCleanup(api.shutdown)

        api.load_level(outside_scene.as_posix())

        self.assertEqual(api.scene_manager.scene_name, "External Scene")


if __name__ == "__main__":
    unittest.main()
