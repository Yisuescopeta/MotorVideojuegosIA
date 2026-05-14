import json
import sys
import types
import unittest

from engine.editor.ui_core.controls.events import Size
from engine.editor.ui_core.controls.text_input import TextInput


class _FakeKeyboardKey:
    KEY_A = "a"
    KEY_BACKSPACE = "backspace"
    KEY_C = "c"
    KEY_DELETE = "delete"
    KEY_LEFT = "left"
    KEY_LEFT_CONTROL = "left_control"
    KEY_LEFT_SHIFT = "left_shift"
    KEY_RIGHT = "right"
    KEY_RIGHT_CONTROL = "right_control"
    KEY_RIGHT_SHIFT = "right_shift"
    KEY_V = "v"
    KEY_X = "x"
    KEY_Y = "y"
    KEY_Z = "z"


class _FakePyray(types.SimpleNamespace):
    def __init__(self, pressed: set[str], down: set[str]) -> None:
        super().__init__(KeyboardKey=_FakeKeyboardKey)
        self.pressed = pressed
        self.down = down

    def is_window_ready(self) -> bool:
        return True

    def get_char_pressed(self) -> int:
        return 0

    def is_key_pressed(self, key: str) -> bool:
        return key in self.pressed

    def is_key_down(self, key: str) -> bool:
        return key in self.down

    def get_clipboard_text(self) -> str:
        return ""

    def set_clipboard_text(self, value: str) -> None:
        del value


class TextInputTests(unittest.TestCase):
    def test_insert_delete_and_cursor(self) -> None:
        model = TextInput(text="ab", cursor=1)

        self.assertTrue(model.insert_text("X"))
        self.assertEqual(model.text, "aXb")
        self.assertEqual(model.cursor, 2)

        self.assertTrue(model.backspace())
        self.assertEqual(model.text, "ab")
        self.assertEqual(model.cursor, 1)

        self.assertTrue(model.delete_forward())
        self.assertEqual(model.text, "a")

    def test_selection_replaced_by_insert(self) -> None:
        model = TextInput(text="hello", cursor=5)
        model.set_cursor(1)
        model.set_cursor(4, selecting=True)

        self.assertEqual(model.selection_range, (1, 4))
        self.assertTrue(model.insert_text("i"))
        self.assertEqual(model.text, "hio")
        self.assertFalse(model.has_selection)

    def test_selection_delete_cut_copy_paste(self) -> None:
        model = TextInput(text="hello", cursor=1, selection_anchor=4)

        self.assertEqual(model.copy_selection(), "ell")
        self.assertEqual(model.cut_selection(), "ell")
        self.assertEqual(model.text, "ho")
        self.assertEqual(model.cursor, 1)
        self.assertTrue(model.paste_text("EL"))
        self.assertEqual(model.text, "hELo")

    def test_single_line_strips_newlines_and_honors_max_length(self) -> None:
        model = TextInput(max_length=5)

        self.assertTrue(model.insert_text("abc\ndef"))
        self.assertEqual(model.text, "abcde")

    def test_readonly_does_not_mutate(self) -> None:
        model = TextInput(text="abc", cursor=3, readonly=True)

        self.assertFalse(model.insert_text("d"))
        self.assertFalse(model.backspace())
        self.assertEqual(model.text, "abc")

    def test_undo_redo_tracks_text_edits(self) -> None:
        model = TextInput(text="ab", cursor=2)

        self.assertTrue(model.insert_text("c"))
        self.assertTrue(model.backspace())
        self.assertEqual(model.text, "ab")

        self.assertTrue(model.undo())
        self.assertEqual(model.text, "abc")
        self.assertEqual(model.cursor, 3)
        self.assertTrue(model.undo())
        self.assertEqual(model.text, "ab")
        self.assertTrue(model.redo())
        self.assertEqual(model.text, "abc")

    def test_command_paste_cut_and_history_clear_redo(self) -> None:
        model = TextInput(text="abc", cursor=1, selection_anchor=3)

        self.assertTrue(model.handle_command("cut"))
        self.assertEqual(model.text, "a")
        self.assertTrue(model.handle_command("undo"))
        self.assertEqual(model.text, "abc")
        self.assertTrue(model.handle_command("paste", "Z"))
        self.assertFalse(model.handle_command("redo"))

    def test_commands_and_serialization(self) -> None:
        model = TextInput(text="abc", cursor=1, password=True)

        self.assertEqual(model.display_text, "***")
        self.assertTrue(model.handle_command("end"))
        self.assertEqual(model.cursor, 3)
        self.assertTrue(model.handle_command("select_all"))
        self.assertEqual(model.selection_range, (0, 3))

        payload = model.to_dict()
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["text"], "abc")
        self.assertIsInstance(json.loads(json.dumps(payload)), dict)
        restored = TextInput.from_dict(json.loads(json.dumps(payload)))
        self.assertEqual(restored.schema_version, 1)
        self.assertEqual(restored.text, "abc")
        self.assertEqual(restored.cursor, 3)

    def test_measure_uses_text_and_min_size(self) -> None:
        model = TextInput(text="abc", custom_min_size=Size(100.0, 20.0))

        size = model.measure(Size(10.0, 10.0))
        self.assertGreaterEqual(size.width, 100.0)
        self.assertGreaterEqual(size.height, 20.0)

    def test_render_shell_wires_shift_arrows_and_ctrl_a(self) -> None:
        from engine.editor.ui.text_input_render import process_text_input

        previous = sys.modules.get("pyray")
        try:
            model = TextInput(text="abc", cursor=1)
            sys.modules["pyray"] = _FakePyray(
                pressed={_FakeKeyboardKey.KEY_RIGHT},
                down={_FakeKeyboardKey.KEY_LEFT_SHIFT},
            )
            self.assertFalse(process_text_input(model))
            self.assertEqual(model.selection_range, (1, 2))

            sys.modules["pyray"] = _FakePyray(
                pressed={_FakeKeyboardKey.KEY_LEFT},
                down={_FakeKeyboardKey.KEY_LEFT_SHIFT},
            )
            self.assertFalse(process_text_input(model))
            self.assertEqual(model.selection_range, (1, 1))

            sys.modules["pyray"] = _FakePyray(
                pressed={_FakeKeyboardKey.KEY_A},
                down={_FakeKeyboardKey.KEY_LEFT_CONTROL},
            )
            self.assertFalse(process_text_input(model))
            self.assertEqual(model.selection_range, (0, 3))
        finally:
            if previous is None:
                sys.modules.pop("pyray", None)
            else:
                sys.modules["pyray"] = previous


if __name__ == "__main__":
    unittest.main()
