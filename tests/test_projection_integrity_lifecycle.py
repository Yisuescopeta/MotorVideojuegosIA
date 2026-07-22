from __future__ import annotations

import unittest

from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.projection_integrity import ProjectionIntegrityCode
from engine.scenes.scene_manager import SceneManager


def _scene_payload(name: str, x: float = 0.0) -> dict[str, object]:
    return {
        "name": name,
        "entities": [
            {
                "id": f"{name}-actor",
                "name": "Actor",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": x,
                        "y": 0.0,
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


class ProjectionIntegrityLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(_scene_payload("Primary"))

    def _mutate_edit_world_directly(self) -> None:
        world = self.manager.get_edit_world()
        assert world is not None
        actor = world.get_entity_by_name("Actor")
        assert actor is not None
        transform = actor.get_component(Transform)
        assert transform is not None
        transform.x = 99.0

    def test_play_rejects_unregistered_projection_divergence(self) -> None:
        self._mutate_edit_world_directly()

        self.assertIsNone(self.manager.enter_play())
        self.assertFalse(self.manager.is_playing)
        report = self.manager._edit_sync.last_integrity_report
        assert report is not None
        self.assertEqual(report.code, ProjectionIntegrityCode.UNREGISTERED_EDIT_WORLD_MUTATION)

    def test_reload_rejects_unregistered_projection_divergence(self) -> None:
        self._mutate_edit_world_directly()

        self.assertIsNone(self.manager.reload_scene())
        self.assertEqual(
            self.manager.get_edit_world().get_entity_by_name("Actor").get_component(Transform).x,
            99.0,
        )
        self.assertEqual(
            self.manager.current_scene.find_entity("Actor")["components"]["Transform"]["x"],
            0.0,
        )

    def test_activation_rejects_active_scene_divergence(self) -> None:
        self.manager.create_new_scene("Secondary", activate=False)
        self.manager.activate_scene("untitled:1:Primary")
        self._mutate_edit_world_directly()

        self.assertIsNone(self.manager.activate_scene("untitled:2:Secondary"))
        self.assertEqual(self.manager.active_scene_key, "untitled:1:Primary")

    def test_close_rejects_divergence_even_when_discard_is_requested(self) -> None:
        entry = self.manager.resolve_entry(None)
        assert entry is not None
        self._mutate_edit_world_directly()

        self.assertFalse(self.manager.close_scene(entry.key, discard_changes=True))
        self.assertIsNotNone(self.manager.resolve_entry(entry.key))

    def test_export_check_rejects_open_scene_divergence(self) -> None:
        self._mutate_edit_world_directly()

        self.assertFalse(self.manager.projection_integrity_allows())


if __name__ == "__main__":
    unittest.main()
