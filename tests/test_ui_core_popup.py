import json
import unittest

from engine.editor.ui_core.controls.popup import PopupManager, PopupModel, alert_popup, confirm_popup, yes_no_popup


class PopupTests(unittest.TestCase):
    def test_open_close_contains_and_serialize(self) -> None:
        popup = PopupModel(name="menu")

        popup.open((10, 20, 100, 50))
        self.assertTrue(popup.visible)
        self.assertTrue(popup.contains_point(20, 30))
        self.assertFalse(popup.contains_point(0, 0))

        payload = popup.to_dict()
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["name"], "menu")
        self.assertIsInstance(json.loads(json.dumps(payload)), dict)
        restored = PopupModel.from_dict(json.loads(json.dumps(payload)))
        self.assertEqual(restored.schema_version, 1)
        self.assertEqual(restored.rect, (10.0, 20.0, 100.0, 50.0))
        self.assertTrue(restored.visible)

        popup.close()
        self.assertFalse(popup.visible)

    def test_outside_click_can_close(self) -> None:
        popup = PopupModel(close_on_outside=True)
        popup.open((0, 0, 10, 10))

        self.assertEqual(popup.handle_pointer_down(20, 20), "closed")
        self.assertFalse(popup.visible)

    def test_place_below_flips_when_needed(self) -> None:
        popup = PopupModel()

        rect = popup.place_below((10, 80, 50, 10), (60, 40), (100, 100))
        self.assertEqual(rect, (10.0, 40.0, 60, 40))

    def test_dialog_factories_are_concrete(self) -> None:
        self.assertEqual(alert_popup("A", "Body").buttons, ["ok"])
        self.assertEqual(confirm_popup("C", "Body").buttons, ["cancel", "ok"])
        self.assertEqual(yes_no_popup("Q", "Body").buttons, ["no", "yes"])

    def test_popup_manager_uses_lifo(self) -> None:
        manager = PopupManager()
        first = manager.push(PopupModel(name="first", rect=(0, 0, 10, 10)))
        second = manager.push(PopupModel(name="second", rect=(20, 20, 10, 10)))

        self.assertIs(manager.top, second)
        self.assertEqual(manager.handle_pointer_down(0, 0), "closed")
        self.assertFalse(second.visible)
        self.assertIs(manager.top, first)
        self.assertIs(manager.pop(), first)
        self.assertIsNone(manager.top)


if __name__ == "__main__":
    unittest.main()
