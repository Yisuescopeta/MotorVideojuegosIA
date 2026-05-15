import json
import unittest

from engine.editor.ui_core.controls.dropdown import ComboBoxModel, DropdownModel, DropdownOption


class DropdownTests(unittest.TestCase):
    def test_select_by_index_and_id(self) -> None:
        model = DropdownModel(options=[DropdownOption("a", "A"), DropdownOption("b", "B")])

        self.assertTrue(model.select_index(1))
        self.assertEqual(model.selected_id, "b")
        self.assertEqual(model.display_label, "B")
        self.assertTrue(model.select_id("a"))
        self.assertEqual(model.selected_index, 0)

    def test_disabled_option_not_selected(self) -> None:
        model = DropdownModel(options=[DropdownOption("a", "A", enabled=False)])

        self.assertFalse(model.select_index(0))
        self.assertIsNone(model.selected_id)

    def test_open_and_select_at(self) -> None:
        model = DropdownModel(options=[DropdownOption("a", "A"), DropdownOption("b", "B")])

        model.open(10, 10)
        self.assertTrue(model.popup.visible)
        self.assertEqual(model.select_at(20, 35), "b")
        self.assertEqual(model.selected_id, "b")
        self.assertFalse(model.popup.visible)

    def test_window_scroll_offset_limits_visible_options(self) -> None:
        model = DropdownModel(
            options=[DropdownOption(str(idx), f"Item {idx}") for idx in range(5)],
            max_visible_items=2,
        )

        model.open(0, 0)
        self.assertEqual(model.preferred_height(), model.item_height * 2)
        self.assertEqual([option.id for option in model.visible_options], ["0", "1"])
        self.assertEqual(model.scroll_by(2), 2)
        self.assertEqual([option.id for option in model.visible_options], ["2", "3"])
        self.assertEqual(model.option_at(5, 5).id, "2")
        self.assertEqual(model.select_at(5, 25), "3")

    def test_combobox_filters_by_query(self) -> None:
        model = ComboBoxModel(options=[DropdownOption("apple", "Apple"), DropdownOption("pear", "Pear")])

        model.set_query("app")
        self.assertEqual([item.id for item in model.filtered_options], ["apple"])
        self.assertEqual(model.display_label, "app")

    def test_serialization(self) -> None:
        model = DropdownModel(options=[DropdownOption("a", "A", value=1)])

        payload = json.loads(json.dumps(model.to_dict()))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["options"][0]["schema_version"], 1)
        self.assertIsInstance(payload, dict)
        restored = DropdownModel.from_dict(payload)
        self.assertEqual(restored.schema_version, 1)
        self.assertEqual(restored.options[0].value, 1)


if __name__ == "__main__":
    unittest.main()
