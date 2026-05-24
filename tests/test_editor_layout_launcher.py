import unittest
from unittest.mock import patch

from engine.editor.editor_layout import EditorLayout


class EditorLayoutLauncherTests(unittest.TestCase):
    def test_open_create_project_modal_prefills_first_available_name(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1024, 768)
        layout.set_launcher_project_name_suggester(lambda: "NewProject3")
        layout.set_launcher_feedback("stale", is_error=True)

        layout.open_create_project_modal()

        self.assertTrue(layout.show_create_project_modal)
        self.assertEqual(layout.launcher_create_name, "NewProject3")
        self.assertTrue(layout.launcher_create_name_focused)
        self.assertEqual(layout.launcher_feedback_text, "")

    def test_create_project_modal_feedback_uses_visible_text_and_color(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1024, 768)
        layout.set_launcher_feedback("Project created as NewProject2")

        feedback = layout.get_create_project_modal_feedback()

        self.assertIsNotNone(feedback)
        assert feedback is not None
        self.assertEqual(feedback[0], "Project created as NewProject2")
        self.assertEqual(feedback[1], layout.UNITY_TEXT_BRIGHT)


if __name__ == "__main__":
    unittest.main()
