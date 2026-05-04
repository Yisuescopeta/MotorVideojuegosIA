"""
tests/test_ola6_batch1.py - Tests for UIPopup, UIPopupMenu, UIWindow, RichTextLabel.
"""

import unittest
from unittest.mock import MagicMock, patch

from engine.components.rich_text_label import RichTextLabel
from engine.components.ui_popup import UIPopup, UIPopupMenu, UIWindow
from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.ui_popup_system import UIPopupSystem
from engine.systems.ui_system import UISystem
from engine.systems.ui_render_system import UIRenderSystem


# ============================================================
# UIPopup tests
# ============================================================

class UIPopupTests(unittest.TestCase):
    def test_defaults(self) -> None:
        popup = UIPopup()
        self.assertFalse(popup.visible)
        self.assertTrue(popup.popup_exclusive)
        self.assertFalse(popup.transparent_background)

    def test_serialization_round_trip(self) -> None:
        popup = UIPopup(visible=True, popup_exclusive=True, transparent_background=True)
        popup._overlay_color = (10, 20, 30, 200)
        data = popup.to_dict()
        restored = UIPopup.from_dict(data)
        self.assertTrue(restored.visible)
        self.assertTrue(restored.popup_exclusive)
        self.assertTrue(restored.transparent_background)
        self.assertEqual(restored._overlay_color, (10, 20, 30, 200))

    def test_visible_toggling(self) -> None:
        popup = UIPopup()
        self.assertFalse(popup.visible)
        popup.visible = True
        self.assertTrue(popup.visible)
        popup.visible = False
        self.assertFalse(popup.visible)


# ============================================================
# UIPopupMenu tests
# ============================================================

class UIPopupMenuTests(unittest.TestCase):
    def test_defaults(self) -> None:
        menu = UIPopupMenu()
        self.assertFalse(menu.visible)
        self.assertEqual(menu.items, [])
        self.assertEqual(menu.popup_position_x, 0.0)
        self.assertEqual(menu.popup_position_y, 0.0)

    def test_add_item(self) -> None:
        menu = UIPopupMenu()
        menu.add_item("New", item_id=1)
        self.assertEqual(len(menu.items), 1)
        self.assertEqual(menu.items[0]["text"], "New")
        self.assertEqual(menu.items[0]["id"], 1)
        self.assertFalse(menu.items[0]["separator"])

    def test_add_separator(self) -> None:
        menu = UIPopupMenu()
        menu.add_item("A")
        menu.add_separator()
        menu.add_item("B")
        self.assertEqual(len(menu.items), 3)
        self.assertTrue(menu.items[1]["separator"])

    def test_clear(self) -> None:
        menu = UIPopupMenu()
        menu.add_item("X")
        menu.add_item("Y")
        self.assertEqual(len(menu.items), 2)
        menu.clear()
        self.assertEqual(len(menu.items), 0)
        self.assertEqual(menu._hovered_index, -1)

    def test_serialization_round_trip(self) -> None:
        menu = UIPopupMenu(visible=True, popup_position_x=100, popup_position_y=200)
        menu.add_item("Open", item_id=5)
        menu.add_separator()
        menu.add_item("Close", item_id=6)
        data = menu.to_dict()
        restored = UIPopupMenu.from_dict(data)
        self.assertTrue(restored.visible)
        self.assertEqual(restored.popup_position_x, 100)
        self.assertEqual(restored.popup_position_y, 200)
        self.assertEqual(len(restored.items), 3)
        self.assertEqual(restored.items[0]["text"], "Open")

    def test_visible_toggle(self) -> None:
        menu = UIPopupMenu()
        self.assertFalse(menu.visible)
        menu.visible = True
        self.assertTrue(menu.visible)


# ============================================================
# UIWindow tests
# ============================================================

class UIWindowTests(unittest.TestCase):
    def test_defaults(self) -> None:
        window = UIWindow()
        self.assertTrue(window.visible)
        self.assertEqual(window.title, "Window")
        self.assertFalse(window.resizable)
        self.assertFalse(window.wrap_controls)
        self.assertFalse(window.transient)

    def test_custom_title(self) -> None:
        window = UIWindow(title="My Dialog")
        self.assertEqual(window.title, "My Dialog")

    def test_serialization_round_trip(self) -> None:
        window = UIWindow(
            visible=True,
            title="Settings",
            resizable=True,
            wrap_controls=True,
            transient=False,
        )
        data = window.to_dict()
        restored = UIWindow.from_dict(data)
        self.assertTrue(restored.visible)
        self.assertEqual(restored.title, "Settings")
        self.assertTrue(restored.resizable)
        self.assertTrue(restored.wrap_controls)
        self.assertFalse(restored.transient)

    def test_visible_toggle(self) -> None:
        window = UIWindow()
        self.assertTrue(window.visible)
        window.visible = False
        self.assertFalse(window.visible)


# ============================================================
# RichTextLabel tests
# ============================================================

class RichTextLabelTests(unittest.TestCase):
    def test_defaults(self) -> None:
        rtl = RichTextLabel()
        self.assertTrue(rtl.enabled)
        self.assertEqual(rtl.text, "")
        self.assertEqual(rtl.font_size, 14)
        self.assertEqual(rtl.default_color, (255, 255, 255, 255))
        self.assertEqual(rtl.visible_characters, -1)
        self.assertEqual(rtl.percent_visible, 1.0)
        self.assertTrue(rtl.autowrap)
        self.assertTrue(rtl.scroll_active)
        self.assertFalse(rtl.selection_enabled)
        self.assertEqual(rtl._scroll_offset, 0.0)

    def test_serialization_round_trip(self) -> None:
        rtl = RichTextLabel(
            enabled=True,
            text="Hello [b]World[/b]",
            font_size=20,
            default_color=(255, 0, 0, 255),
            visible_characters=50,
            percent_visible=0.5,
            autowrap=False,
            scroll_active=False,
            selection_enabled=True,
        )
        data = rtl.to_dict()
        restored = RichTextLabel.from_dict(data)
        self.assertTrue(restored.enabled)
        self.assertEqual(restored.text, "Hello [b]World[/b]")
        self.assertEqual(restored.font_size, 20)
        self.assertEqual(restored.default_color, (255, 0, 0, 255))
        self.assertEqual(restored.visible_characters, 50)
        self.assertEqual(restored.percent_visible, 0.5)
        self.assertFalse(restored.autowrap)
        self.assertFalse(restored.scroll_active)
        self.assertTrue(restored.selection_enabled)

    def test_scroll_up_down(self) -> None:
        rtl = RichTextLabel()
        rtl._max_scroll = 100.0
        rtl._scroll_offset = 50.0
        rtl.scroll_up(30.0)
        self.assertEqual(rtl._scroll_offset, 20.0)
        rtl.scroll_down(30.0)
        self.assertEqual(rtl._scroll_offset, 50.0)
        rtl.scroll_up(200.0)
        self.assertEqual(rtl._scroll_offset, 0.0)
        rtl.scroll_down(200.0)
        self.assertEqual(rtl._scroll_offset, 100.0)

    def test_scroll_clamped(self) -> None:
        rtl = RichTextLabel()
        rtl._max_scroll = 30.0
        rtl._scroll_offset = 30.0
        rtl.scroll_down(50.0)
        self.assertEqual(rtl._scroll_offset, 30.0)

    def test_percent_visible_clamped(self) -> None:
        rtl = RichTextLabel(percent_visible=2.0)
        self.assertEqual(rtl.percent_visible, 1.0)
        rtl2 = RichTextLabel(percent_visible=-0.5)
        self.assertEqual(rtl2.percent_visible, 0.0)

    def test_font_size_minimum(self) -> None:
        rtl = RichTextLabel(font_size=3)
        self.assertEqual(rtl.font_size, 8)


# ============================================================
# UIPopupSystem tests
# ============================================================

class UIPopupSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = UIPopupSystem()

    def _make_popup_entity(self, name: str = "test_popup", visible: bool = True, exclusive: bool = True) -> Entity:
        entity = Entity(name)
        entity.add_component(Canvas(enabled=True, reference_width=800, reference_height=600))
        entity.add_component(RectTransform())
        entity.add_component(UIPopup(visible=visible, popup_exclusive=exclusive))
        self.world.add_entity(entity)
        return entity

    def _make_menu_entity(self, name: str = "test_menu") -> Entity:
        entity = Entity(name)
        entity.add_component(Canvas(enabled=True, reference_width=800, reference_height=600))
        entity.add_component(RectTransform())
        menu = UIPopupMenu(visible=True)
        menu.add_item("Option A", item_id=1)
        menu.add_item("Option B", item_id=2)
        menu.add_separator()
        menu.add_item("Quit", item_id=99)
        entity.add_component(menu)
        self.world.add_entity(entity)
        return entity

    def _make_window_entity(self, name: str = "test_window") -> Entity:
        entity = Entity(name)
        entity.add_component(Canvas(enabled=True, reference_width=800, reference_height=600))
        entity.add_component(RectTransform())
        entity.add_component(UIWindow(visible=True, title="Test"))
        self.world.add_entity(entity)
        return entity

    def test_empty_world_no_popups(self) -> None:
        layouts: dict = {}
        self.system.update(self.world, layouts)
        self.assertEqual(len(self.system.get_visible_popups()), 0)
        self.assertEqual(len(self.system.get_visible_menus()), 0)
        self.assertEqual(len(self.system.get_visible_windows()), 0)
        self.assertFalse(self.system.get_popup_blocking())

    def test_popup_blocking_exclusive(self) -> None:
        self._make_popup_entity("popup1", visible=True, exclusive=True)
        layouts = {"popup1": {"x": 100, "y": 100, "width": 600, "height": 400}}
        self.system.update(self.world, layouts)
        self.assertTrue(self.system.get_popup_blocking())
        self.assertEqual(len(self.system.get_visible_popups()), 1)

    def test_popup_non_exclusive(self) -> None:
        self._make_popup_entity("popup1", visible=True, exclusive=False)
        layouts = {"popup1": {"x": 100, "y": 100, "width": 600, "height": 400}}
        self.system.update(self.world, layouts)
        self.assertFalse(self.system.get_popup_blocking())
        self.assertEqual(len(self.system.get_visible_popups()), 1)

    def test_popup_not_visible(self) -> None:
        self._make_popup_entity("popup1", visible=False, exclusive=True)
        layouts = {"popup1": {"x": 100, "y": 100, "width": 600, "height": 400}}
        self.system.update(self.world, layouts)
        self.assertEqual(len(self.system.get_visible_popups()), 0)
        self.assertFalse(self.system.get_popup_blocking())

    def test_visible_menus(self) -> None:
        self._make_menu_entity("menu1")
        layouts = {"menu1": {"x": 0, "y": 0, "width": 200, "height": 100}}
        self.system.update(self.world, layouts)
        self.assertEqual(len(self.system.get_visible_menus()), 1)

    def test_visible_windows(self) -> None:
        self._make_window_entity("win1")
        layouts = {"win1": {"x": 50, "y": 50, "width": 300, "height": 200}}
        self.system.update(self.world, layouts)
        self.assertEqual(len(self.system.get_visible_windows()), 1)

    def test_hidden_window_not_visible(self) -> None:
        entity = Entity("hidden_win")
        entity.add_component(Canvas(enabled=True, reference_width=800, reference_height=600))
        entity.add_component(RectTransform())
        entity.add_component(UIWindow(visible=False, title="Hidden"))
        self.world.add_entity(entity)
        layouts = {"hidden_win": {"x": 0, "y": 0, "width": 200, "height": 100}}
        self.system.update(self.world, layouts)
        self.assertEqual(len(self.system.get_visible_windows()), 0)

    def test_window_close_button(self) -> None:
        entity = self._make_window_entity("win1")
        window = entity.get_component(UIWindow)
        layouts = {"win1": {"x": 50.0, "y": 50.0, "width": 300.0, "height": 200.0}}

        self.system.update(self.world, layouts)
        self.assertTrue(window.visible)

        # Click close button (top-right corner, close button area)
        consumed = self.system.handle_click(
            self.world,
            x=340.0,  # close button x: 50+300-26 = 324, so 340 is within [324, 350]
            y=60.0,   # within title bar
            layouts=layouts,
            pressed=True,
            released=False,
            down=False,
        )
        self.assertFalse(window.visible)
        self.assertTrue(consumed)

    def test_window_drag(self) -> None:
        entity = self._make_window_entity("win1")
        layouts = {"win1": {"x": 50.0, "y": 50.0, "width": 300.0, "height": 200.0}}

        self.system.update(self.world, layouts)

        # Press on title bar to start drag
        self.system.handle_click(
            self.world,
            x=100.0, y=60.0,
            layouts=layouts,
            pressed=True, released=False, down=False,
        )

        # Drag to new position
        self.system.handle_click(
            self.world,
            x=200.0, y=100.0,
            layouts=layouts,
            pressed=False, released=False, down=True,
        )

        self.assertEqual(layouts["win1"]["x"], 150.0)  # 200 - 50 (offset)
        self.assertEqual(layouts["win1"]["y"], 90.0)   # 100 - 10 (offset)

    def test_get_selected_menu_id(self) -> None:
        entity = self._make_menu_entity("menu1")
        menu = entity.get_component(UIPopupMenu)
        menu._selected_id = 42
        self.assertEqual(self.system.get_selected_menu_id(entity), 42)
        self.assertEqual(menu._selected_id, -1)  # reset after read


# ============================================================
# Component Registry integration tests
# ============================================================

class ComponentRegistryIntegrationTests(unittest.TestCase):
    def test_popup_registered(self) -> None:
        from engine.levels.component_registry import create_default_registry
        registry = create_default_registry()
        cls = registry.get("UIPopup")
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "UIPopup")

    def test_popupmenu_registered(self) -> None:
        from engine.levels.component_registry import create_default_registry
        registry = create_default_registry()
        cls = registry.get("UIPopupMenu")
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "UIPopupMenu")

    def test_window_registered(self) -> None:
        from engine.levels.component_registry import create_default_registry
        registry = create_default_registry()
        cls = registry.get("UIWindow")
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "UIWindow")

    def test_richtextlabel_registered(self) -> None:
        from engine.levels.component_registry import create_default_registry
        registry = create_default_registry()
        cls = registry.get("RichTextLabel")
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "RichTextLabel")

    def test_popup_create_from_dict(self) -> None:
        from engine.levels.component_registry import create_default_registry
        registry = create_default_registry()
        comp = registry.create("UIPopup", {"visible": True, "popup_exclusive": False})
        self.assertIsInstance(comp, UIPopup)
        self.assertTrue(comp.visible)
        self.assertFalse(comp.popup_exclusive)

    def test_richtextlabel_create_from_dict(self) -> None:
        from engine.levels.component_registry import create_default_registry
        registry = create_default_registry()
        comp = registry.create("RichTextLabel", {
            "text": "[b]Test[/b]",
            "font_size": 16,
            "autowrap": False,
        })
        self.assertIsInstance(comp, RichTextLabel)
        self.assertEqual(comp.text, "[b]Test[/b]")
        self.assertEqual(comp.font_size, 16)
        self.assertFalse(comp.autowrap)


if __name__ == "__main__":
    unittest.main()
