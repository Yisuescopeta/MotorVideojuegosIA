import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
