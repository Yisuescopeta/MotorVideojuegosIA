import json
import tempfile
import unittest
from pathlib import Path

from engine.assets.prefab import PrefabManager
from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry
from engine.serialization.schema import (
    CURRENT_PREFAB_SCHEMA_VERSION,
    CURRENT_SCENE_SCHEMA_VERSION,
    migrate_scene_data,
    validate_scene_data,
)


class SchemaValidationTests(unittest.TestCase):
    def test_legacy_scene_payload_migrates_to_current_schema(self) -> None:
        legacy = {"name": "Legacy", "entities": [], "rules": []}
        migrated = migrate_scene_data(legacy)
        self.assertEqual(migrated["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)
        self.assertEqual(validate_scene_data(migrated), [])

    def test_scene_manager_save_includes_schema_version(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene({"name": "SaveMe", "entities": [], "rules": [], "feature_metadata": {}})
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            payload = json.loads(scene_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)

    def test_prefab_manager_loads_legacy_prefab_and_assigns_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prefab_path = Path(temp_dir) / "enemy.prefab"
            prefab_path.write_text(
                json.dumps(
                    {
                        "name": "Enemy",
                        "components": {"Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}}
                    }
                ),
                encoding="utf-8",
            )
            payload = PrefabManager.load_prefab_data(prefab_path.as_posix())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["schema_version"], CURRENT_PREFAB_SCHEMA_VERSION)

    def test_tilemap_payload_migrates_and_validates(self) -> None:
        legacy = {
            "name": "TilemapScene",
            "entities": [
                {
                    "name": "Grid",
                    "components": {
                        "Tilemap": {
                            "layers": [
                                {
                                    "name": "Ground",
                                    "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}],
                                }
                            ]
                        }
                    },
                }
            ],
            "rules": [],
        }
        migrated = migrate_scene_data(legacy)
        self.assertEqual(validate_scene_data(migrated), [])


if __name__ == "__main__":
    unittest.main()
