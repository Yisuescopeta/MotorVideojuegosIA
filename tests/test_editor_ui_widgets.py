import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from engine.editor.ui import widgets
from engine.editor.ui.widget_state import WidgetResult


class _TupleTextRL:
    def Rectangle(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (x, y, w, h)

    def gui_text_box(self, rect: object, text: str, max_length: int, edit_mode: bool) -> tuple[str, bool]:
        return ("edited", True)


class _TupleDropdownRL:
    def Rectangle(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (x, y, w, h)

    def gui_dropdown_box(self, rect: object, text: str, active: int, edit_mode: bool) -> tuple[bool, int]:
        return (True, 2)


class _FakeTextFFI:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def new(self, cdecl: str, size: int) -> bytearray:
        self.buffer = bytearray(size)
        return self.buffer

    def string(self, buffer: bytearray) -> bytes:
        end = buffer.find(0)
        if end < 0:
            end = len(buffer)
        return bytes(buffer[:end])


class _BoolTextRL:
    def __init__(self) -> None:
        self.ffi = _FakeTextFFI()

    def Rectangle(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (x, y, w, h)

    def gui_text_box(self, rect: object, text: bytearray, max_length: int, edit_mode: bool) -> bool:
        text[:5] = b"typed"
        text[5] = 0
        return True


class _FakeIntPointer:
    def __init__(self, value: int) -> None:
        self.value = value

    def __getitem__(self, index: int) -> int:
        if index != 0:
            raise IndexError(index)
        return self.value

    def __setitem__(self, index: int, value: int) -> None:
        if index != 0:
            raise IndexError(index)
        self.value = value


class _FakeDropdownFFI:
    def new(self, cdecl: str, value: int) -> _FakeIntPointer:
        return _FakeIntPointer(value)


class _BoolDropdownRL:
    def __init__(self) -> None:
        self.ffi = _FakeDropdownFFI()

    def Rectangle(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (x, y, w, h)

    def gui_dropdown_box(self, rect: object, text: str, active: _FakeIntPointer, edit_mode: bool) -> bool:
        active[0] = 1
        return True


class EditorUIWidgetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        for name in (
            "draw_border",
            "draw_focus_outline",
            "draw_panel_background",
            "draw_panel_header_background",
            "draw_rounded_rect",
            "draw_separator",
            "draw_text_clipped",
            "draw_icon",
        ):
            self.stack.enter_context(patch.object(widgets, name, Mock()))
        self.is_hovered = self.stack.enter_context(patch.object(widgets.ui_input, "is_hovered", Mock(return_value=False)))
        self.is_pressed = self.stack.enter_context(patch.object(widgets.ui_input, "is_pressed", Mock(return_value=False)))
        self.is_clicked = self.stack.enter_context(patch.object(widgets.ui_input, "is_clicked", Mock(return_value=False)))
        self.is_right_clicked = self.stack.enter_context(
            patch.object(widgets.ui_input, "is_right_clicked", Mock(return_value=False))
        )
        self.mouse_position = self.stack.enter_context(
            patch.object(widgets.ui_input, "mouse_position", Mock(return_value=(0.0, 0.0)))
        )

    def tearDown(self) -> None:
        self.stack.close()

    def assert_widget_result(self, result: WidgetResult) -> None:
        self.assertIsInstance(result, WidgetResult)

    def test_smoke_static_widgets_return_widget_result(self) -> None:
        rect = (0.0, 0.0, 100.0, 24.0)
        cases = (
            widgets.editor_label(rect, "Label"),
            widgets.editor_icon_button(rect, "play"),
            widgets.editor_tab(rect, "Tab"),
            widgets.editor_panel(rect),
            widgets.editor_panel_header(rect, "Header"),
            widgets.editor_separator(rect),
            widgets.editor_badge(rect, "Badge"),
            widgets.editor_status_pill(rect, "OK"),
            widgets.editor_text_field_simple(rect, "text", focused=True),
        )
        for result in cases:
            with self.subTest(result=result):
                self.assert_widget_result(result)

    def test_button_reports_click(self) -> None:
        self.is_clicked.return_value = True

        result = widgets.editor_button((0, 0, 100, 24), "Run")

        self.assert_widget_result(result)
        self.assertTrue(result.clicked)
        self.assertEqual(result.value, "Run")

    def test_toggle_button_reports_changed_value(self) -> None:
        self.is_clicked.return_value = True

        result = widgets.editor_toggle_button((0, 0, 100, 24), "Mute", False)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertTrue(result.value)

    def test_checkbox_reports_changed_value(self) -> None:
        self.is_clicked.return_value = True

        result = widgets.editor_checkbox((0, 0, 100, 24), "Visible", True)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertFalse(result.value)

    def test_tab_bar_reports_selected_index(self) -> None:
        self.is_clicked.side_effect = (False, True, False)

        result = widgets.editor_tab_bar((0, 0, 300, 24), ["A", "B", "C"], 0)

        self.assert_widget_result(result)
        self.assertTrue(result.clicked)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 1)

    def test_tab_accepts_active_alias(self) -> None:
        result = widgets.editor_tab((0, 0, 100, 24), "Tab", active=True)

        self.assert_widget_result(result)
        self.assertEqual(result.value, "Tab")

    def test_tab_bar_accepts_dict_tabs_and_active_index(self) -> None:
        self.is_clicked.side_effect = (False, True)
        tabs: list[dict[str, object]] = [{"text": "A", "icon": "play"}, {"text": "B", "closeable": True}]

        result = widgets.editor_tab_bar(
            (0, 0, 200, 24),
            tabs,
            active_index=0,
        )

        self.assert_widget_result(result)
        self.assertTrue(result.clicked)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 1)

    def test_panel_collapsible_click_reports_collapsed_value(self) -> None:
        self.is_clicked.return_value = True

        result = widgets.editor_panel((0, 0, 100, 80), "Panel", collapsible=True, collapsed=False)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, {"collapsed": True})

    def test_panel_header_collapsible_click_reports_collapsed_value(self) -> None:
        self.is_clicked.return_value = True

        result = widgets.editor_panel_header((0, 0, 100, 24), "Header", collapsible=True, collapsed=True)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, {"collapsed": False})

    def test_status_pill_kind_variants_smoke(self) -> None:
        rect = (0.0, 0.0, 100.0, 24.0)

        for kind in ("success", "warning", "error"):
            with self.subTest(kind=kind):
                self.assert_widget_result(widgets.editor_status_pill(rect, kind, kind=kind))

    def test_slider_float_reports_changed_with_epsilon(self) -> None:
        self.is_pressed.return_value = True
        self.mouse_position.return_value = (75.0, 0.0)

        result = widgets.editor_slider_float((0, 0, 100, 24), 0.5, 0.0, 1.0)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 0.75)

    def test_slider_float_snaps_to_step(self) -> None:
        self.is_pressed.return_value = True
        self.mouse_position.return_value = (74.0, 0.0)

        result = widgets.editor_slider_float((0, 0, 100, 24), 0.5, 0.0, 1.0, step=0.25)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 0.75)

    def test_slider_float_ignores_sub_epsilon_delta(self) -> None:
        self.is_pressed.return_value = True
        self.mouse_position.return_value = (50.00000001, 0.0)

        result = widgets.editor_slider_float((0, 0, 100, 24), 0.5, 0.0, 1.0)

        self.assert_widget_result(result)
        self.assertFalse(result.changed)

    def test_raygui_textbox_bridge_captures_tuple_return(self) -> None:
        with patch.object(widgets, "_rl", return_value=_TupleTextRL()):
            result = widgets.raygui_textbox_bridge((0, 0, 100, 24), "old")

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, "edited")

    def test_raygui_textbox_bridge_accepts_max_chars_alias(self) -> None:
        with patch.object(widgets, "_rl", return_value=_TupleTextRL()):
            result = widgets.raygui_textbox_bridge((0, 0, 100, 24), "old", max_chars=3)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, "edi")

    def test_raygui_textbox_bridge_captures_ffi_buffer(self) -> None:
        with patch.object(widgets, "_rl", return_value=_BoolTextRL()):
            result = widgets.raygui_textbox_bridge((0, 0, 100, 24), "old")

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, "typed")

    def test_raygui_dropdown_bridge_captures_tuple_return(self) -> None:
        with patch.object(widgets, "_rl", return_value=_TupleDropdownRL()):
            result = widgets.raygui_dropdown_bridge((0, 0, 100, 24), ["A", "B", "C"], 0)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 2)

    def test_raygui_dropdown_bridge_accepts_active_index_alias(self) -> None:
        with patch.object(widgets, "_rl", return_value=_TupleDropdownRL()):
            result = widgets.raygui_dropdown_bridge((0, 0, 100, 24), ["A", "B", "C"], active_index=1)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 2)

    def test_raygui_dropdown_bridge_captures_ffi_pointer(self) -> None:
        with patch.object(widgets, "_rl", return_value=_BoolDropdownRL()):
            result = widgets.raygui_dropdown_bridge((0, 0, 100, 24), ["A", "B"], 0)

        self.assert_widget_result(result)
        self.assertTrue(result.changed)
        self.assertEqual(result.value, 1)


if __name__ == "__main__":
    unittest.main()
