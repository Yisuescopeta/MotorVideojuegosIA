import tempfile
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class SceneManagerContractsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {
                "name": "Contracts Probe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 10.0,
                                "y": 20.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_runtime_port_is_memoized_and_preserves_play_stop_semantics(self) -> None:
        port = self.manager.runtime_port

        self.assertIs(port, self.manager.runtime_port)
        self.assertIs(port.current_scene, self.manager.current_scene)
        self.assertIs(port.active_world, self.manager.active_world)

        runtime_world = port.enter_play()

        self.assertIsNotNone(runtime_world)
        self.assertTrue(self.manager.is_playing)
        self.assertIs(runtime_world, self.manager.active_world)

        edit_world = port.exit_play()

        self.assertIsNotNone(edit_world)
        self.assertFalse(self.manager.is_playing)
        self.assertIs(edit_world, self.manager.active_world)

    def test_authoring_and_workspace_ports_delegate_serializable_state(self) -> None:
        authoring = self.manager.authoring_port
        workspace = self.manager.workspace_port

        self.assertIs(authoring, self.manager.authoring_port)
        self.assertIs(workspace, self.manager.workspace_port)
        self.assertTrue(
            authoring.create_entity(
                "Enemy",
                components={
                    "Transform": {
                        "enabled": True,
                        "x": 8.0,
                        "y": 4.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            )
        )
        self.assertTrue(authoring.set_feature_metadata("phase_1", {"enabled": True}))
        self.assertTrue(workspace.set_scene_flow_target("next_scene", "levels/next_scene.json"))
        self.assertEqual(authoring.get_component_data("Enemy", "Transform")["x"], 8.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "contracts_probe.json"

            self.assertTrue(workspace.save_scene_to_file(scene_path.as_posix(), key=workspace.active_scene_key))

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))
            self.assertIsNotNone(reloaded.find_entity_data("Enemy"))
            self.assertEqual(reloaded.get_feature_metadata()["phase_1"], {"enabled": True})
            self.assertEqual(reloaded.get_scene_flow()["next_scene"], "levels/next_scene.json")


if __name__ == "__main__":
    unittest.main()
