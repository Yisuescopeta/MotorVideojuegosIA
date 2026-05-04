"""
tests/test_ui_controls.py — Tests for new UI controls: LineEdit, Slider, ProgressBar, CheckBox, SpinBox, Label, TextEdit.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.uicheckbox import CheckBox
from engine.components.uilabel import Label
from engine.components.uilineedit import LineEdit
from engine.components.uiprogressbar import ProgressBar
from engine.components.uislider import Slider
from engine.components.uispinbox import SpinBox
from engine.components.uitextedit import TextEdit
from engine.levels.component_registry import create_default_registry


class TestLineEdit(unittest.TestCase):
    def test_create_lineedit(self) -> None:
        le = LineEdit()
        self.assertTrue(le.enabled)
        self.assertEqual(le.text, "")
        self.assertEqual(le.placeholder, "")
        self.assertEqual(le.max_length, 0)
        self.assertFalse(le.secret)
        self.assertTrue(le.editable)
        self.assertEqual(le.font_size, 16)
        self.assertEqual(le.color, (255, 255, 255, 255))
        self.assertEqual(le.placeholder_color, (128, 128, 128, 255))
        self.assertEqual(le.alignment, "left")
        self.assertFalse(le.focused)

    def test_lineedit_serialization(self) -> None:
        le = LineEdit(
            text="hello",
            placeholder="type here",
            max_length=100,
            secret=True,
            editable=False,
            font_size=20,
            color=(200, 100, 50, 255),
            alignment="center",
        )
        data = le.to_dict()
        restored = LineEdit.from_dict(data)
        self.assertEqual(restored.text, le.text)
        self.assertEqual(restored.placeholder, le.placeholder)
        self.assertEqual(restored.max_length, le.max_length)
        self.assertTrue(restored.secret)
        self.assertFalse(restored.editable)
        self.assertEqual(restored.font_size, 20)
        self.assertEqual(restored.color, (200, 100, 50, 255))
        self.assertEqual(restored.alignment, "center")

    def test_lineedit_cursor(self) -> None:
        le = LineEdit(text="hello")
        le.cursor_position = 2
        self.assertEqual(le.cursor_position, 2)
        le.cursor_position = 10
        self.assertEqual(le.cursor_position, 5)
        le.cursor_position = -1
        self.assertEqual(le.cursor_position, 0)

    def test_lineedit_selection(self) -> None:
        le = LineEdit(text="world")
        le.selection_start = 1
        le.selection_end = 3
        self.assertEqual(le.selection_start, 1)
        self.assertEqual(le.selection_end, 3)

    def test_lineedit_from_dict_defaults(self) -> None:
        le = LineEdit.from_dict({})
        self.assertTrue(le.enabled)
        self.assertEqual(le.text, "")

    def test_lineedit_focused_runtime_not_serialized(self) -> None:
        le = LineEdit(text="test")
        le.focused = True
        data = le.to_dict()
        self.assertNotIn("_focused", data)
        self.assertNotIn("_cursor_position", data)


class TestSlider(unittest.TestCase):
    def test_create_slider(self) -> None:
        s = Slider()
        self.assertTrue(s.enabled)
        self.assertEqual(s.value, 0.0)
        self.assertEqual(s.min_value, 0.0)
        self.assertEqual(s.max_value, 100.0)
        self.assertEqual(s.step, 1.0)
        self.assertTrue(s.horizontal)
        self.assertTrue(s.editable)

    def test_slider_value_range(self) -> None:
        s = Slider(value=50.0, min_value=0.0, max_value=100.0)
        self.assertAlmostEqual(s.ratio, 0.5)
        s.set_value(150.0)
        self.assertEqual(s.value, 100.0)
        s.set_value(-10.0)
        self.assertEqual(s.value, 0.0)

    def test_slider_step(self) -> None:
        s = Slider(value=0.0, step=10.0)
        s.set_value(15.0)
        self.assertEqual(s.value, 20.0)
        s.set_value(14.0)
        self.assertEqual(s.value, 10.0)

    def test_slider_ratio_zero_range(self) -> None:
        s = Slider(value=5.0, min_value=5.0, max_value=5.0)
        self.assertEqual(s.ratio, 0.0)

    def test_slider_serialization(self) -> None:
        s = Slider(value=30, min_value=0, max_value=60, step=5, horizontal=False, editable=False)
        data = s.to_dict()
        restored = Slider.from_dict(data)
        self.assertEqual(restored.value, 30)
        self.assertEqual(restored.horizontal, False)
        self.assertEqual(restored.step, 5)

    def test_slider_from_dict_defaults(self) -> None:
        s = Slider.from_dict({})
        self.assertTrue(s.enabled)
        self.assertEqual(s.value, 0.0)


class TestProgressBar(unittest.TestCase):
    def test_create_progressbar(self) -> None:
        pb = ProgressBar()
        self.assertTrue(pb.enabled)
        self.assertEqual(pb.value, 0.0)
        self.assertEqual(pb.max_value, 100.0)
        self.assertTrue(pb.percent_visible)
        self.assertTrue(pb.horizontal)
        self.assertEqual(pb.fill_color, (0, 200, 0, 255))
        self.assertEqual(pb.bg_color, (60, 60, 60, 255))

    def test_progressbar_fill_ratio(self) -> None:
        pb = ProgressBar(value=25, max_value=100)
        self.assertAlmostEqual(pb.ratio, 0.25)
        self.assertAlmostEqual(pb.percent, 25.0)
        pb.value = 100
        self.assertAlmostEqual(pb.ratio, 1.0)
        self.assertAlmostEqual(pb.percent, 100.0)

    def test_progressbar_zero_range(self) -> None:
        pb = ProgressBar(value=5, min_value=5, max_value=5)
        self.assertEqual(pb.ratio, 0.0)

    def test_progressbar_serialization(self) -> None:
        pb = ProgressBar(value=50, percent_visible=False, horizontal=False, fill_color=(255, 0, 0, 255))
        data = pb.to_dict()
        restored = ProgressBar.from_dict(data)
        self.assertEqual(restored.value, 50)
        self.assertFalse(restored.percent_visible)
        self.assertFalse(restored.horizontal)
        self.assertEqual(restored.fill_color, (255, 0, 0, 255))

    def test_progressbar_from_dict_defaults(self) -> None:
        pb = ProgressBar.from_dict({})
        self.assertTrue(pb.enabled)
        self.assertEqual(pb.value, 0.0)


class TestCheckBox(unittest.TestCase):
    def test_create_checkbox(self) -> None:
        cb = CheckBox()
        self.assertTrue(cb.enabled)
        self.assertEqual(cb.text, "")
        self.assertFalse(cb.checked)
        self.assertTrue(cb.toggle_mode)

    def test_checkbox_toggle(self) -> None:
        cb = CheckBox(checked=False)
        cb.toggle()
        self.assertTrue(cb.checked)
        cb.toggle()
        self.assertFalse(cb.checked)

    def test_checkbox_serialization(self) -> None:
        cb = CheckBox(text="Accept terms", checked=True, toggle_mode=False)
        data = cb.to_dict()
        restored = CheckBox.from_dict(data)
        self.assertEqual(restored.text, "Accept terms")
        self.assertTrue(restored.checked)
        self.assertFalse(restored.toggle_mode)

    def test_checkbox_from_dict_defaults(self) -> None:
        cb = CheckBox.from_dict({})
        self.assertTrue(cb.enabled)
        self.assertFalse(cb.checked)


class TestSpinBox(unittest.TestCase):
    def test_create_spinbox(self) -> None:
        sb = SpinBox()
        self.assertTrue(sb.enabled)
        self.assertEqual(sb.value, 0.0)
        self.assertEqual(sb.min_value, 0.0)
        self.assertEqual(sb.max_value, 100.0)
        self.assertEqual(sb.step, 1.0)
        self.assertEqual(sb.prefix, "")
        self.assertEqual(sb.suffix, "")
        self.assertTrue(sb.editable)

    def test_spinbox_increment_decrement(self) -> None:
        sb = SpinBox(value=50.0, step=5.0)
        sb.increment()
        self.assertEqual(sb.value, 55.0)
        sb.decrement()
        self.assertEqual(sb.value, 50.0)

    def test_spinbox_clamp(self) -> None:
        sb = SpinBox(value=100.0, max_value=100.0)
        sb.increment()
        self.assertEqual(sb.value, 100.0)
        sb = SpinBox(value=0.0, min_value=0.0)
        sb.decrement()
        self.assertEqual(sb.value, 0.0)

    def test_spinbox_display_text(self) -> None:
        sb = SpinBox(value=42.0, prefix="$", suffix=" USD")
        self.assertEqual(sb.display_text, "$42.0 USD")

    def test_spinbox_serialization(self) -> None:
        sb = SpinBox(value=10.0, prefix="Lv: ", suffix=" pts", editable=False)
        data = sb.to_dict()
        restored = SpinBox.from_dict(data)
        self.assertEqual(restored.value, 10.0)
        self.assertEqual(restored.prefix, "Lv: ")
        self.assertEqual(restored.suffix, " pts")
        self.assertFalse(restored.editable)

    def test_spinbox_from_dict_defaults(self) -> None:
        sb = SpinBox.from_dict({})
        self.assertTrue(sb.enabled)
        self.assertEqual(sb.value, 0.0)


class TestLabel(unittest.TestCase):
    def test_create_label(self) -> None:
        lbl = Label()
        self.assertTrue(lbl.enabled)
        self.assertEqual(lbl.text, "")
        self.assertEqual(lbl.font_size, 16)
        self.assertEqual(lbl.color, (255, 255, 255, 255))
        self.assertEqual(lbl.alignment, "left")
        self.assertFalse(lbl.autowrap)
        self.assertFalse(lbl.clip_text)

    def test_label_serialization(self) -> None:
        lbl = Label(text="Hello World", font_size=24, color=(100, 200, 50, 255), alignment="center", autowrap=True)
        data = lbl.to_dict()
        restored = Label.from_dict(data)
        self.assertEqual(restored.text, "Hello World")
        self.assertEqual(restored.font_size, 24)
        self.assertEqual(restored.color, (100, 200, 50, 255))
        self.assertEqual(restored.alignment, "center")
        self.assertTrue(restored.autowrap)

    def test_label_from_dict_defaults(self) -> None:
        lbl = Label.from_dict({})
        self.assertTrue(lbl.enabled)
        self.assertEqual(lbl.text, "")


class TestTextEdit(unittest.TestCase):
    def test_create_textedit(self) -> None:
        te = TextEdit()
        self.assertTrue(te.enabled)
        self.assertEqual(te.text, "")
        self.assertEqual(te.font_size, 14)
        self.assertTrue(te.editable)
        self.assertFalse(te.line_numbers)
        self.assertTrue(te.word_wrap)
        self.assertEqual(te.max_lines, 0)
        self.assertFalse(te.focused)

    def test_textedit_serialization(self) -> None:
        te = TextEdit(text="line1\nline2", editable=False, line_numbers=True, max_lines=100)
        data = te.to_dict()
        restored = TextEdit.from_dict(data)
        self.assertEqual(restored.text, "line1\nline2")
        self.assertFalse(restored.editable)
        self.assertTrue(restored.line_numbers)
        self.assertEqual(restored.max_lines, 100)

    def test_textedit_runtime_not_serialized(self) -> None:
        te = TextEdit(text="hello")
        te.focused = True
        te.cursor_line = 1
        te.scroll_y = 50.0
        data = te.to_dict()
        self.assertNotIn("_focused", data)
        self.assertNotIn("_cursor_line", data)
        self.assertNotIn("_scroll_y", data)

    def test_textedit_cursor(self) -> None:
        te = TextEdit(text="a\nb\nc")
        te.cursor_line = 1
        self.assertEqual(te.cursor_line, 1)
        te.cursor_line = 5
        self.assertEqual(te.cursor_line, 5)
        te.cursor_line = -1
        self.assertEqual(te.cursor_line, 0)

    def test_textedit_scroll(self) -> None:
        te = TextEdit()
        te.scroll_y = 100.0
        self.assertEqual(te.scroll_y, 100.0)
        te.scroll_y = -50.0
        self.assertEqual(te.scroll_y, 0.0)

    def test_textedit_from_dict_defaults(self) -> None:
        te = TextEdit.from_dict({})
        self.assertTrue(te.enabled)
        self.assertEqual(te.text, "")


class TestComponentRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()

    def _check_component(self, name: str, cls: type, tag: str) -> None:
        component_cls = self.registry.get(name)
        self.assertIsNotNone(component_cls, f"{name} not registered")
        self.assertIs(component_cls, cls)
        descriptor = self.registry.get_descriptor(name)
        self.assertIsNotNone(descriptor)
        self.assertIn(tag, descriptor.editor_tags)
        created = self.registry.create(name, {})
        self.assertIsInstance(created, cls)

    def test_registry_lineedit(self) -> None:
        self._check_component("LineEdit", LineEdit, "input")

    def test_registry_slider(self) -> None:
        self._check_component("Slider", Slider, "slider")

    def test_registry_progressbar(self) -> None:
        self._check_component("ProgressBar", ProgressBar, "progress")

    def test_registry_checkbox(self) -> None:
        self._check_component("CheckBox", CheckBox, "toggle")

    def test_registry_spinbox(self) -> None:
        self._check_component("SpinBox", SpinBox, "numeric")

    def test_registry_label(self) -> None:
        self._check_component("Label", Label, "text")

    def test_registry_textedit(self) -> None:
        self._check_component("TextEdit", TextEdit, "multiline")


class TestAPIEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "Project"
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=(self.root / "global_state").as_posix(),
        )

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def test_api_create_lineedit(self) -> None:
        self._write_scene(
            "le_test.json",
            {"name": "LE Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "le_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_lineedit("MyLineEdit", "MainCanvas", text="hello", placeholder="type...")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyLineEdit")
        self.assertIsNotNone(entity)

    def test_api_create_slider(self) -> None:
        self._write_scene(
            "slider_test.json",
            {"name": "Slider Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "slider_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_slider("MySlider", "MainCanvas", value=50)
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MySlider")
        self.assertIsNotNone(entity)

    def test_api_create_progressbar(self) -> None:
        self._write_scene(
            "pb_test.json",
            {"name": "PB Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "pb_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_progressbar("MyBar", "MainCanvas", value=30)
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyBar")
        self.assertIsNotNone(entity)

    def test_api_create_checkbox(self) -> None:
        self._write_scene(
            "cb_test.json",
            {"name": "CB Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "cb_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_checkbox("MyCheck", "MainCanvas", text="Yes", checked=True)
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyCheck")
        self.assertIsNotNone(entity)

    def test_api_create_spinbox(self) -> None:
        self._write_scene(
            "sb_test.json",
            {"name": "SB Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "sb_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_spinbox("MySpinBox", "MainCanvas", value=10, prefix="Lv:", suffix=" pts")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MySpinBox")
        self.assertIsNotNone(entity)

    def test_api_create_label(self) -> None:
        self._write_scene(
            "lbl_test.json",
            {"name": "Lbl Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "lbl_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_label("MyLabel", "MainCanvas", text="Rich text here", font_size=20)
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyLabel")
        self.assertIsNotNone(entity)

    def test_api_create_textedit(self) -> None:
        self._write_scene(
            "te_test.json",
            {"name": "TE Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "te_test.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        result = self.api.create_ui_textedit("MyTextEdit", "MainCanvas", text="line1\nline2")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyTextEdit")
        self.assertIsNotNone(entity)

    def test_set_slider_value(self) -> None:
        self._write_scene(
            "slider_val.json",
            {"name": "Slider Val", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "slider_val.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        self.api.create_ui_slider("MySlider", "MainCanvas", value=10)
        result = self.api.set_slider_value("MySlider", 75.0)
        self.assertTrue(result["success"])

    def test_set_progressbar_value(self) -> None:
        self._write_scene(
            "pb_val.json",
            {"name": "PB Val", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "pb_val.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        self.api.create_ui_progressbar("MyBar", "MainCanvas", value=0)
        result = self.api.set_progressbar_value("MyBar", 80.0)
        self.assertTrue(result["success"])

    def test_list_ui_nodes_includes_new_controls(self) -> None:
        self._write_scene(
            "all_ui.json",
            {"name": "All UI", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level((self.project_root / "levels" / "all_ui.json").as_posix())
        self.api.create_canvas(name="MainCanvas")
        self.api.create_ui_slider("MySlider", "MainCanvas")
        self.api.create_ui_checkbox("MyCheck", "MainCanvas")
        self.api.create_ui_label("MyLabel", "MainCanvas", text="x")
        nodes = self.api.list_ui_nodes()
        names = [n["name"] for n in nodes]
        self.assertIn("MySlider", names)
        self.assertIn("MyCheck", names)
        self.assertIn("MyLabel", names)


class TestStyleBoxFlat(unittest.TestCase):
    def test_create_stylebox_flat(self) -> None:
        from engine.resources.stylebox_flat import StyleBoxFlat
        sbf = StyleBoxFlat()
        self.assertEqual(sbf.name, "StyleBoxFlat")
        self.assertEqual(sbf.bg_color, (40, 40, 40, 255))
        self.assertEqual(sbf.border_color, (80, 80, 80, 255))
        self.assertEqual(sbf.border_width, 1)
        self.assertEqual(sbf.corner_radius, 0)
        self.assertFalse(sbf.has_shadow)

    def test_stylebox_flat_shadow(self) -> None:
        from engine.resources.stylebox_flat import StyleBoxFlat
        sbf = StyleBoxFlat(shadow_size=10, shadow_color=(0, 0, 0, 50))
        self.assertTrue(sbf.has_shadow)
        sbf2 = StyleBoxFlat(shadow_size=10, shadow_color=(0, 0, 0, 0))
        self.assertFalse(sbf2.has_shadow)

    def test_stylebox_flat_corner_radius_overrides(self) -> None:
        from engine.resources.stylebox_flat import StyleBoxFlat
        sbf = StyleBoxFlat(corner_radius=5, corner_radius_top_left=10)
        self.assertEqual(sbf.get_corner_radius("top_left"), 10)
        self.assertEqual(sbf.get_corner_radius("top_right"), 5)

    def test_stylebox_flat_serialization(self) -> None:
        from engine.resources.stylebox_flat import StyleBoxFlat
        sbf = StyleBoxFlat(
            bg_color=(30, 30, 30, 200),
            border_color=(100, 100, 255, 255),
            border_width=2,
            corner_radius=8,
            shadow_size=5,
            shadow_offset_x=2,
            shadow_offset_y=2,
            anti_aliasing=False,
            expand_margin_left=4,
            expand_margin_right=4,
        )
        data = sbf.to_dict()
        restored = StyleBoxFlat.from_dict(data)
        self.assertEqual(restored.bg_color, sbf.bg_color)
        self.assertEqual(restored.border_width, 2)
        self.assertEqual(restored.corner_radius, 8)
        self.assertEqual(restored.shadow_size, 5)
        self.assertFalse(restored.anti_aliasing)
        self.assertEqual(restored.expand_margin_left, 4)

    def test_stylebox_flat_from_dict_defaults(self) -> None:
        from engine.resources.stylebox_flat import StyleBoxFlat
        sbf = StyleBoxFlat.from_dict({})
        self.assertEqual(sbf.name, "StyleBoxFlat")
        self.assertEqual(sbf.bg_color, (40, 40, 40, 255))

    def test_stylebox_flat_expand_size(self) -> None:
        from engine.resources.stylebox_flat import StyleBoxFlat
        sbf = StyleBoxFlat(expand_margin_left=2, expand_margin_top=3, expand_margin_right=4, expand_margin_bottom=5)
        self.assertEqual(sbf.expand_size, (2, 3, 4, 5))


if __name__ == "__main__":
    unittest.main()
