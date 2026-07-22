import unittest

from engine.editor.editor_session import EditorMode, EditorSession
from engine.scenes.refs import EntityRef, OpenDocumentId, OpenSceneRef
from engine.scenes.result import Err, Ok


class EditorSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = EditorSession()
        self.scene_a = OpenSceneRef(OpenDocumentId.new())
        self.scene_b = OpenSceneRef(OpenDocumentId.new())
        self.hero = EntityRef(self.scene_a, "hero-id")

    def test_selection_is_single_and_belongs_to_active_scene(self) -> None:
        self.session.activate_scene(self.scene_a)
        selected = self.session.select(self.hero)

        self.assertIsInstance(selected, Ok)
        self.assertEqual(self.session.snapshot.selection, self.hero)
        self.assertIsInstance(self.session.select(EntityRef(self.scene_b, "other-id")), Err)
        self.assertEqual(self.session.snapshot.selection, self.hero)

    def test_switching_scene_clears_selection_from_previous_scene(self) -> None:
        self.session.activate_scene(self.scene_a)
        self.session.select(self.hero)
        self.session.activate_scene(self.scene_b)

        self.assertIsNone(self.session.snapshot.selection)
        self.assertEqual(self.session.snapshot.active_scene, self.scene_b)

    def test_mode_and_tab_are_session_state_not_world_state(self) -> None:
        self.session.set_mode(EditorMode.PLAY)
        self.session.activate_tab("INSPECTOR")

        snapshot = self.session.snapshot
        self.assertEqual(snapshot.mode, EditorMode.PLAY)
        self.assertEqual(snapshot.active_tab, "INSPECTOR")


if __name__ == "__main__":
    unittest.main()
