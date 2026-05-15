import unittest
from unittest.mock import patch

from engine.editor.toast_notifications import (
    TOAST_MANAGER,
    ToastManager,
    ToastMessage,
    toast_debug,
    toast_err,
    toast_info,
    toast_warn,
)


class ToastNotificationTests(unittest.TestCase):
    def tearDown(self) -> None:
        TOAST_MANAGER.clear()

    def test_dataclass_and_add_normalizes_level(self) -> None:
        manager = ToastManager()
        with patch("engine.editor.toast_notifications.time.monotonic", return_value=1.0):
            toast_id = manager.add("warning", "careful", 123)

        toast = manager.visible_toasts(now=1.0)[0]
        self.assertIsInstance(toast, ToastMessage)
        self.assertEqual(toast.id, toast_id)
        self.assertEqual(toast.level, "WARN")
        self.assertEqual(toast.message, "careful")
        self.assertEqual(toast.created_at, 1.0)
        self.assertEqual(toast.duration_ms, 123)

    def test_dismiss_clear_and_update_expiry(self) -> None:
        manager = ToastManager()
        with patch("engine.editor.toast_notifications.time.monotonic", return_value=2.0):
            first = manager.add("info", "one", 100)
            manager.add("err", "two", 1000)

        manager.dismiss(first)
        self.assertEqual([toast.message for toast in manager.visible_toasts(now=2.0)], ["two"])
        manager.update(now=3.1)
        self.assertEqual(manager.visible_toasts(now=3.1), [])

        manager.add("debug", "three")
        manager.clear()
        self.assertEqual(manager.visible_toasts(), [])

    def test_visible_toasts_respects_max_visible(self) -> None:
        manager = ToastManager(max_visible=2)
        with patch("engine.editor.toast_notifications.time.monotonic", return_value=3.0):
            manager.add("info", "one")
            manager.add("info", "two")
            manager.add("info", "three")

        self.assertEqual([toast.message for toast in manager.visible_toasts(now=3.0)], ["two", "three"])

    def test_shortcuts_use_global_manager(self) -> None:
        TOAST_MANAGER.clear()
        ids = [toast_info("i"), toast_warn("w"), toast_err("e"), toast_debug("d")]
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual([toast.level for toast in TOAST_MANAGER.visible_toasts()], ["INFO", "WARN", "ERR", "DEBUG"])

    def test_render_is_safe_when_empty_and_draws_when_visible(self) -> None:
        manager = ToastManager()
        with patch("pyray.draw_rectangle_rec") as fill, patch("pyray.draw_rectangle_lines_ex") as outline, patch(
            "pyray.draw_text"
        ) as text:
            manager.render(800, 600)
        fill.assert_not_called()
        outline.assert_not_called()
        text.assert_not_called()

        with patch("engine.editor.toast_notifications.time.monotonic", return_value=4.0):
            manager.add("info", "hello")
        with patch("engine.editor.toast_notifications.time.monotonic", return_value=4.1), patch(
            "pyray.draw_rectangle_rec"
        ) as fill, patch("pyray.draw_rectangle_lines_ex") as outline, patch("pyray.draw_text") as text:
            manager.render(800, 600)

        fill.assert_called()
        outline.assert_called()
        self.assertGreaterEqual(text.call_count, 2)


if __name__ == "__main__":
    unittest.main()
