import json
import unittest

from engine.editor.ui_core.controls.context_menu import (
    ContextMenuItem,
    ContextMenuManager,
    ContextMenuModel,
    context_menu_from_tuples,
)


class ContextMenuTests(unittest.TestCase):
    def test_open_highlight_and_activate(self) -> None:
        menu = ContextMenuModel(
            items=[
                ContextMenuItem("open", "Open"),
                ContextMenuItem("sep", "", separator=True),
                ContextMenuItem("delete", "Delete", enabled=False),
                ContextMenuItem("rename", "Rename"),
            ]
        )

        menu.open_at(10, 10)
        self.assertTrue(menu.popup.visible)
        self.assertEqual(menu.highlighted_index, 0)
        self.assertEqual(menu.move_highlight(1), 3)
        self.assertEqual(menu.activate_highlighted(), "rename")
        self.assertFalse(menu.popup.visible)

    def test_item_at_and_disabled_not_selected(self) -> None:
        menu = ContextMenuModel([ContextMenuItem("a", "A"), ContextMenuItem("b", "B", enabled=False)])
        menu.open_at(0, 0)

        self.assertEqual(menu.item_at(5, 5).id, "a")
        self.assertIsNone(menu.activate_at(5, 25))
        self.assertIsNone(menu.selected_id)

    def test_factory_and_serialization(self) -> None:
        menu = context_menu_from_tuples([("copy", "Copy")])

        self.assertEqual(menu.items[0].label, "Copy")
        payload = json.loads(json.dumps(menu.to_dict()))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["items"][0]["schema_version"], 1)
        self.assertIsInstance(payload, dict)
        restored = ContextMenuModel.from_dict(payload)
        self.assertEqual(restored.schema_version, 1)
        self.assertEqual(restored.items[0].id, "copy")

    def test_submenu_opens_and_child_action_closes_root(self) -> None:
        menu = ContextMenuModel(
            [ContextMenuItem("file", "File", children=[ContextMenuItem("new", "New"), ContextMenuItem("open", "Open")])]
        )
        menu.open_at(10, 10)

        self.assertIsNone(menu.activate_at(15, 15))
        self.assertIsNotNone(menu.child_menu)
        self.assertEqual(menu.activate_at(175, 37), "open")
        self.assertEqual(menu.selected_id, "open")
        self.assertFalse(menu.popup.visible)

    def test_context_menu_manager_lifecycle(self) -> None:
        manager = ContextMenuManager()
        menu = ContextMenuModel([ContextMenuItem("copy", "Copy")])

        manager.open(menu, 0, 0)
        self.assertTrue(menu.popup.visible)
        self.assertEqual(manager.activate_at(5, 5), "copy")
        self.assertIsNone(manager.root)


if __name__ == "__main__":
    unittest.main()
