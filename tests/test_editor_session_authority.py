import tempfile
import unittest
from pathlib import Path

from engine.editor.editor_session import EditorMode, EditorSession
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


def _scene(name: str, entity_id: str, entity_name: str) -> dict[str, object]:
    return {
        "name": name,
        "entities": [
            {
                "id": entity_id,
                "name": entity_name,
                "components": {
                    "Transform": {
                        "x": 0.0,
                        "y": 0.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    }
                },
            }
        ],
    }


class EditorSessionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = SceneManager(create_default_registry())
        self.manager.load_scene(_scene("Main", "hero-id", "Hero"))
        self.session = EditorSession()
        active = self.manager.active_scene_ref
        assert active is not None
        self.session.activate_scene(active)
        selected = self.manager.entity_ref_by_name("Hero")
        assert selected is not None
        self.session.select(selected)

    def test_selection_is_entity_ref_and_rename_preserves_it(self) -> None:
        selected = self.session.snapshot.selection
        assert selected is not None
        self.assertEqual(selected.entity_id, "hero-id")

        self.assertTrue(self.manager.update_entity_property_by_id("hero-id", "name", "Renamed"))

        self.assertEqual(self.session.snapshot.selection, selected)

    def test_save_rekey_preserves_open_document_and_selection(self) -> None:
        selected = self.session.snapshot.selection
        active = self.session.snapshot.active_scene
        assert selected is not None and active is not None
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "renamed_scene.json"
            self.assertTrue(self.manager.save_scene_to_file(str(target)))

        self.assertEqual(self.session.snapshot.active_scene, active)
        self.assertEqual(self.session.snapshot.selection, selected)

    def test_switch_clears_incompatible_selection_and_play_does_not_change_authority(self) -> None:
        selected = self.session.snapshot.selection
        assert selected is not None
        self.manager.load_scene(_scene("Other", "other-id", "Other"), activate=False)
        other_key = next(key for key in self.manager._workspace.entries if "Other" in key)
        self.assertIsNotNone(self.manager.activate_scene(other_key))
        other_ref = self.manager.active_scene_ref
        assert other_ref is not None
        self.session.activate_scene(other_ref)
        self.assertIsNone(self.session.snapshot.selection)

        self.session.activate_scene(selected.scene)
        self.session.select(selected)
        self.assertIsNotNone(self.manager.enter_play())
        self.session.set_mode(EditorMode.PLAY)
        self.assertEqual(self.session.snapshot.selection, selected)
        self.manager.exit_play()
        self.session.set_mode(EditorMode.EDIT)

    def test_mutating_world_visual_selection_does_not_mutate_session(self) -> None:
        entry = self.manager.resolve_entry(None)
        assert entry is not None and entry.edit_world is not None
        selected = self.session.snapshot.selection
        assert selected is not None
        entry.edit_world.selected_entity_name = "Other visual label"
        self.assertEqual(self.session.snapshot.selection, selected)


if __name__ == "__main__":
    unittest.main()
