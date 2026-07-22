import unittest

from engine.editor.editor_shell_actions import EditorShellActionInbox, SceneTabActionKind
from engine.editor.editor_shell_state import EditorShellState


class EditorShellActionTests(unittest.TestCase):
    def test_scene_tab_actions_are_typed_and_consumed_once(self) -> None:
        inbox = EditorShellActionInbox()
        inbox.activate_scene_tab("scene-a")
        inbox.close_scene_tab("scene-b")

        actions = inbox.drain_scene_tab_actions()

        self.assertEqual([action.kind for action in actions], [SceneTabActionKind.ACTIVATE, SceneTabActionKind.CLOSE])
        self.assertEqual([action.scene_key for action in actions], ["scene-a", "scene-b"])
        self.assertEqual(inbox.drain_scene_tab_actions(), ())

    def test_shell_state_owns_the_inbox_without_serializing_it_as_a_flag(self) -> None:
        state = EditorShellState()
        state.actions.activate_scene_tab("scene-a")

        self.assertEqual(state.actions.drain_scene_tab_actions()[0].scene_key, "scene-a")
        self.assertFalse(hasattr(state, "request_scene_tab_action"))


if __name__ == "__main__":
    unittest.main()
