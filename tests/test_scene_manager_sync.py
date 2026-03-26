import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.append(os.getcwd())

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class SceneManagerSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene_manager = SceneManager(create_default_registry())
        self.scene_manager.load_scene(
            {
                "name": "Sync Probe",
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

    def test_sync_from_edit_world_skips_when_nothing_changed(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(edit_world)

        with patch.object(edit_world, "serialize", wraps=edit_world.serialize) as serialize_mock:
            changed = self.scene_manager.sync_from_edit_world()

        self.assertFalse(changed)
        self.assertEqual(serialize_mock.call_count, 0)

    def test_pending_world_changes_are_flushed_before_scene_edit(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(edit_world)
        player = edit_world.get_entity_by_name("Player")
        self.assertIsNotNone(player)

        transform = player.get_component(Transform)
        self.assertIsNotNone(transform)
        transform.x = 144.0
        self.scene_manager.mark_edit_world_dirty()

        updated = self.scene_manager.apply_edit_to_world("Player", "Transform", "y", 88.0)
        self.assertTrue(updated)

        refreshed_world = self.scene_manager.get_edit_world()
        refreshed_player = refreshed_world.get_entity_by_name("Player")
        refreshed_transform = refreshed_player.get_component(Transform)
        self.assertEqual(refreshed_transform.x, 144.0)
        self.assertEqual(refreshed_transform.y, 88.0)

    def test_reload_scene_from_disk_rereads_open_scene_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "scene.json"
            scene_path.write_text(
                json.dumps(
                    {
                        "name": "Disk Scene",
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
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

            self.scene_manager.load_scene_from_file(scene_path.as_posix())
            self.scene_manager.set_selected_entity("Player")

            scene_path.write_text(
                json.dumps(
                    {
                        "name": "Disk Scene",
                        "entities": [
                            {
                                "name": "Player",
                                "active": True,
                                "tag": "Untagged",
                                "layer": "Default",
                                "components": {
                                    "Transform": {
                                        "enabled": True,
                                        "x": 99.0,
                                        "y": 77.0,
                                        "rotation": 0.0,
                                        "scale_x": 1.0,
                                        "scale_y": 1.0,
                                    }
                                },
                            }
                        ],
                        "rules": [],
                        "feature_metadata": {},
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

            cached_world = self.scene_manager.load_scene_from_file(scene_path.as_posix())
            cached_player = cached_world.get_entity_by_name("Player")
            cached_transform = cached_player.get_component(Transform)
            self.assertEqual(cached_transform.x, 10.0)

            reloaded_world = self.scene_manager.reload_scene_from_disk(scene_path.as_posix())

            self.assertIsNotNone(reloaded_world)
            reloaded_player = reloaded_world.get_entity_by_name("Player")
            reloaded_transform = reloaded_player.get_component(Transform)
            self.assertEqual(reloaded_transform.x, 99.0)
            self.assertEqual(reloaded_transform.y, 77.0)
            self.assertEqual(reloaded_world.selected_entity_name, "Player")


if __name__ == "__main__":
    unittest.main()
