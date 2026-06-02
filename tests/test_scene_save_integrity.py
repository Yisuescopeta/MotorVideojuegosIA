import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class SceneSaveIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(
            {
                "name": "SaveIntegrity",
                "entities": [
                    {
                        "name": "Entity_A",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 0.0,
                                "y": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    },
                    {
                        "name": "Entity_B",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {},
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_normal_save_passes_and_file_roundtrips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "integrity_scene.json"

            result = self.manager.save_scene_to_file(scene_path.as_posix())

            self.assertTrue(result)
            self.assertTrue(scene_path.is_file())

            with open(scene_path, "r", encoding="utf-8") as handle:
                on_disk = json.load(handle)
            entities = on_disk.get("entities", [])
            self.assertEqual(len(entities), 2)
            self.assertEqual(entities[0]["name"], "Entity_A")
            self.assertEqual(entities[1]["name"], "Entity_B")

            reloaded = SceneManager(create_default_registry())
            world = reloaded.load_scene_from_file(scene_path.as_posix())
            self.assertIsNotNone(world)
            self.assertEqual(len(reloaded.current_scene.entities_data), 2)

    def test_post_write_validation_failure_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "fail_val.json"

            with patch(
                "engine.scenes.scene_manager.validate_scene_data",
                return_value=["mock_post_write_error"],
            ):
                result = self.manager.save_scene_to_file(scene_path.as_posix())

            self.assertFalse(result)

    def test_post_write_entity_count_mismatch_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "fail_count.json"

            # Mock the storage load to return a payload with wrong entity count.
            # We inject a custom storage that saves correctly but loads corrupted.
            class _CorruptLoadStorage:
                def save(self, path, payload):
                    with open(Path(path), "w", encoding="utf-8") as fh:
                        json.dump(payload, fh, indent=2)

                def load(self, path):
                    with open(Path(path), "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    data["entities"] = []  # corrupt entity count
                    return data

            result = self.manager.save_scene_to_file(
                scene_path.as_posix(),
                storage=_CorruptLoadStorage(),
            )

            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
