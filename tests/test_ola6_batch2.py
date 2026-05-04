"""Tests for OLA6 batch 2: UITabBar, UITabContainer, UISplitContainer."""
from __future__ import annotations

import unittest

from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.ui_splitcontainer import UISplitContainer
from engine.components.ui_tabbar import UITabBar, UITabContainer
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.ui_system import UISystem


class UITabBarTests(unittest.TestCase):
    """Tests for UITabBar component."""

    def test_default_values(self) -> None:
        tb = UITabBar()
        self.assertEqual(tb.tabs, [])
        self.assertEqual(tb.current_tab, 0)
        self.assertEqual(tb.tab_alignment, "left")
        self.assertFalse(tb.scrollable)
        self.assertEqual(tb.tab_close_display_policy, "show_active_only")

    def test_serialization_roundtrip(self) -> None:
        tb = UITabBar(
            tabs=[{"title": "Tab 1", "icon_path": "res://icon1.png"}, {"title": "Tab 2"}],
            current_tab=1,
            tab_alignment="center",
            scrollable=True,
            tab_close_display_policy="always",
        )
        data = tb.to_dict()
        restored = UITabBar.from_dict(data)
        self.assertEqual(len(restored.tabs), 2)
        self.assertEqual(restored.tabs[0]["title"], "Tab 1")
        self.assertEqual(restored.current_tab, 1)
        self.assertEqual(restored.tab_alignment, "center")
        self.assertTrue(restored.scrollable)
        self.assertEqual(restored.tab_close_display_policy, "always")

    def test_tabs_independent_copies(self) -> None:
        tb = UITabBar(tabs=[{"title": "A"}])
        tb.tabs[0]["title"] = "B"
        tb2 = UITabBar(tabs=[{"title": "A"}])
        self.assertEqual(tb2.tabs[0]["title"], "A")

    def test_layout_tabbar_children_positioned(self) -> None:
        world = World()
        system = UISystem()
        parent = world.create_entity("TabBar")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=300, height=40, layout_mode="free"))
        parent.add_component(UITabBar(tabs=[{"title": "A"}, {"title": "B"}, {"title": "C"}]))

        child_a = world.create_entity("TabA")
        child_a.parent_name = "TabBar"
        child_a.add_component(RectTransform(width=50, height=30))
        child_b = world.create_entity("TabB")
        child_b.parent_name = "TabBar"
        child_b.add_component(RectTransform(width=50, height=30))
        child_c = world.create_entity("TabC")
        child_c.parent_name = "TabBar"
        child_c.add_component(RectTransform(width=50, height=30))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout = system.get_layout_entry("TabBar")
        self.assertIsNotNone(layout)

        child_a_layout = system.get_layout_entry("TabA")
        child_b_layout = system.get_layout_entry("TabB")
        child_c_layout = system.get_layout_entry("TabC")
        self.assertIsNotNone(child_a_layout)
        self.assertIsNotNone(child_b_layout)
        self.assertIsNotNone(child_c_layout)
        # Children should be side by side
        self.assertLess(child_a_layout["x"], child_b_layout["x"])
        self.assertLess(child_b_layout["x"], child_c_layout["x"])

    def test_tabbar_click_switches_tab(self) -> None:
        world = World()
        system = UISystem()
        tb = UITabBar(tabs=[{"title": "A"}, {"title": "B"}, {"title": "C"}], current_tab=0)
        parent = world.create_entity("TabBar")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=300, height=40, layout_mode="free"))
        parent.add_component(tb)

        child_a = world.create_entity("TabA")
        child_a.parent_name = "TabBar"
        child_a.add_component(RectTransform(width=50, height=30))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout = system.get_layout_entry("TabBar")
        # 3 tabs in 800px viewport -> each tab ~266.67px wide
        # Click on tab 1 (second tab, middle third)
        system.inject_pointer_state(
            x=float(layout["x"]) + 400.0,
            y=float(layout["y"]) + 20.0,
            down=False,
            pressed=True,
            released=False,
        )
        system.update(world, (800.0, 600.0))
        self.assertEqual(tb.current_tab, 1)

        # Release
        system.inject_pointer_state(
            x=float(layout["x"]) + 400.0,
            y=float(layout["y"]) + 20.0,
            down=False,
            pressed=False,
            released=True,
        )
        system.update(world, (800.0, 600.0))
        self.assertEqual(tb.current_tab, 1)

    def test_tabbar_right_alignment(self) -> None:
        world = World()
        system = UISystem()
        parent = world.create_entity("TabBar")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=40, layout_mode="free"))
        parent.add_component(UITabBar(tabs=[{"title": "A"}, {"title": "B"}], tab_alignment="right"))

        child_a = world.create_entity("TabA")
        child_a.parent_name = "TabBar"
        child_a.add_component(RectTransform(width=50, height=30))
        child_b = world.create_entity("TabB")
        child_b.parent_name = "TabBar"
        child_b.add_component(RectTransform(width=50, height=30))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout_a = system.get_layout_entry("TabA")
        layout_b = system.get_layout_entry("TabB")
        self.assertIsNotNone(layout_a)
        self.assertIsNotNone(layout_b)
        # Tabs fill the width, so positions should be consecutive
        self.assertGreater(float(layout_b["x"]), float(layout_a["x"]))

    def test_tabbar_center_alignment(self) -> None:
        world = World()
        system = UISystem()
        parent = world.create_entity("TabBar")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=40, layout_mode="free"))
        parent.add_component(UITabBar(tabs=[{"title": "A"}, {"title": "B"}], tab_alignment="center"))

        child_a = world.create_entity("TabA")
        child_a.parent_name = "TabBar"
        child_a.add_component(RectTransform(width=50, height=30))
        child_b = world.create_entity("TabB")
        child_b.parent_name = "TabBar"
        child_b.add_component(RectTransform(width=50, height=30))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout_a = system.get_layout_entry("TabA")
        layout_b = system.get_layout_entry("TabB")
        self.assertIsNotNone(layout_a)
        self.assertIsNotNone(layout_b)
        # Tabs fill width, positions should be consecutive
        self.assertAlmostEqual(float(layout_a["x"]), 0.0, delta=1.0)
        self.assertGreater(float(layout_b["x"]), float(layout_a["x"]))


class UITabContainerTests(unittest.TestCase):
    """Tests for UITabContainer component."""

    def test_default_values(self) -> None:
        tc = UITabContainer()
        self.assertEqual(tc.current_tab, 0)
        self.assertEqual(tc.tab_titles, [])
        self.assertTrue(tc.use_hidden_tabs_for_min_size)
        self.assertFalse(tc.drag_to_rearrange_enabled)
        self.assertFalse(tc.all_tabs_in_front)

    def test_serialization_roundtrip(self) -> None:
        tc = UITabContainer(
            current_tab=2,
            tab_titles=[{"title": "Tab 1"}, {"title": "Tab 2"}, {"title": "Tab 3"}],
            use_hidden_tabs_for_min_size=False,
            drag_to_rearrange_enabled=True,
            all_tabs_in_front=True,
        )
        data = tc.to_dict()
        restored = UITabContainer.from_dict(data)
        self.assertEqual(restored.current_tab, 2)
        self.assertEqual(len(restored.tab_titles), 3)
        self.assertFalse(restored.use_hidden_tabs_for_min_size)
        self.assertTrue(restored.drag_to_rearrange_enabled)
        self.assertTrue(restored.all_tabs_in_front)

    def test_layout_shows_current_tab_content(self) -> None:
        world = World()
        system = UISystem()
        tc = UITabContainer(
            current_tab=0,
            tab_titles=[{"title": "Tab 1"}, {"title": "Tab 2"}],
        )
        parent = world.create_entity("TabContainer")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(tc)

        tab_header_a = world.create_entity("HeaderA")
        tab_header_a.parent_name = "TabContainer"
        tab_header_a.add_component(RectTransform(width=100, height=30))
        tab_header_b = world.create_entity("HeaderB")
        tab_header_b.parent_name = "TabContainer"
        tab_header_b.add_component(RectTransform(width=100, height=30))
        content_a = world.create_entity("ContentA")
        content_a.parent_name = "TabContainer"
        content_a.add_component(RectTransform(width=200, height=200))
        content_b = world.create_entity("ContentB")
        content_b.parent_name = "TabContainer"
        content_b.add_component(RectTransform(width=200, height=200))

        system._ensure_layout_cache(world, (800.0, 600.0))

        # Tab 0 content should be on-screen
        layout_a = system.get_layout_entry("ContentA")
        self.assertIsNotNone(layout_a)
        self.assertGreater(float(layout_a["width"]), 0)
        self.assertGreater(float(layout_a["x"]), -1000)

        # Tab 1 content should be hidden
        layout_b = system.get_layout_entry("ContentB")
        self.assertIsNotNone(layout_b)
        self.assertLess(float(layout_b["x"]), -100)

    def test_tabcontainer_click_switches_current_tab(self) -> None:
        world = World()
        system = UISystem()
        tc = UITabContainer(
            current_tab=0,
            tab_titles=[{"title": "Tab 1"}, {"title": "Tab 2"}, {"title": "Tab 3"}],
        )
        parent = world.create_entity("TabContainer")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(tc)

        tab_h1 = world.create_entity("H1")
        tab_h1.parent_name = "TabContainer"

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout = system.get_layout_entry("TabContainer")

        # Click on second tab header area
        tab_width = float(layout["width"]) / 3
        system.inject_pointer_state(
            x=float(layout["x"]) + tab_width + tab_width * 0.5,
            y=float(layout["y"]) + 10.0,
            down=False,
            pressed=True,
            released=False,
        )
        system.update(world, (800.0, 600.0))
        self.assertEqual(tc.current_tab, 1)

    def test_tabcontainer_click_below_bar_no_switch(self) -> None:
        world = World()
        system = UISystem()
        tc = UITabContainer(
            current_tab=0,
            tab_titles=[{"title": "Tab 1"}, {"title": "Tab 2"}],
        )
        parent = world.create_entity("TabContainer")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(tc)

        tab_h1 = world.create_entity("H1")
        tab_h1.parent_name = "TabContainer"
        tab_h1.add_component(RectTransform(width=50, height=30))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout = system.get_layout_entry("TabContainer")

        # Click below tab bar (in content area) should not switch
        system.inject_pointer_state(
            x=float(layout["x"]) + float(layout["width"]) * 0.75,
            y=float(layout["y"]) + 100.0,
            down=False,
            pressed=True,
            released=False,
        )
        system.update(world, (800.0, 600.0))
        self.assertEqual(tc.current_tab, 0)


class UISplitContainerTests(unittest.TestCase):
    """Tests for UISplitContainer component."""

    def test_default_values(self) -> None:
        sc = UISplitContainer()
        self.assertEqual(sc.split_offset, 0.5)
        self.assertFalse(sc.vertical)
        self.assertEqual(sc.dragger_visibility, "visible")
        self.assertFalse(sc.collapsed)
        self.assertEqual(sc.drag_step, 1.0)

    def test_serialization_roundtrip(self) -> None:
        sc = UISplitContainer(
            split_offset=0.7,
            vertical=True,
            dragger_visibility="hidden",
            collapsed=True,
            drag_step=5.0,
        )
        data = sc.to_dict()
        restored = UISplitContainer.from_dict(data)
        self.assertEqual(restored.split_offset, 0.7)
        self.assertTrue(restored.vertical)
        self.assertEqual(restored.dragger_visibility, "hidden")
        self.assertTrue(restored.collapsed)
        self.assertEqual(restored.drag_step, 5.0)

    def test_split_offset_clamped(self) -> None:
        sc = UISplitContainer(split_offset=2.0)
        self.assertEqual(sc.split_offset, 1.0)
        sc2 = UISplitContainer(split_offset=-0.5)
        self.assertEqual(sc2.split_offset, 0.0)

    def test_layout_horizontal_split(self) -> None:
        world = World()
        system = UISystem()
        sc = UISplitContainer(split_offset=0.6, vertical=False)
        parent = world.create_entity("Split")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(sc)

        left = world.create_entity("Left")
        left.parent_name = "Split"
        left.add_component(RectTransform(width=100, height=100))
        right = world.create_entity("Right")
        right.parent_name = "Split"
        right.add_component(RectTransform(width=100, height=100))

        system._ensure_layout_cache(world, (800.0, 600.0))

        left_l = system.get_layout_entry("Left")
        right_l = system.get_layout_entry("Right")
        self.assertIsNotNone(left_l)
        self.assertIsNotNone(right_l)

        parent_l = system.get_layout_entry("Split")
        total_w = float(parent_l["width"])
        dragger = 8.0
        expected_left = (total_w - dragger) * 0.6
        self.assertAlmostEqual(float(left_l["width"]), expected_left, delta=1.0)
        self.assertGreater(float(right_l["x"]), float(left_l["x"]) + float(left_l["width"]))

    def test_layout_vertical_split(self) -> None:
        world = World()
        system = UISystem()
        sc = UISplitContainer(split_offset=0.4, vertical=True)
        parent = world.create_entity("Split")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(sc)

        top = world.create_entity("Top")
        top.parent_name = "Split"
        top.add_component(RectTransform(width=100, height=50))
        bottom = world.create_entity("Bottom")
        bottom.parent_name = "Split"
        bottom.add_component(RectTransform(width=100, height=50))

        system._ensure_layout_cache(world, (800.0, 600.0))

        top_l = system.get_layout_entry("Top")
        bottom_l = system.get_layout_entry("Bottom")
        self.assertIsNotNone(top_l)
        self.assertIsNotNone(bottom_l)

        parent_l = system.get_layout_entry("Split")
        total_h = float(parent_l["height"])
        dragger = 8.0
        expected_top = (total_h - dragger) * 0.4
        self.assertAlmostEqual(float(top_l["height"]), expected_top, delta=1.0)
        self.assertGreater(float(bottom_l["y"]), float(top_l["y"]) + float(top_l["height"]))

    def test_split_drag_updates_offset(self) -> None:
        world = World()
        system = UISystem()
        sc = UISplitContainer(split_offset=0.5, vertical=False)
        parent = world.create_entity("Split")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(sc)

        left = world.create_entity("Left")
        left.parent_name = "Split"
        left.add_component(RectTransform(width=100, height=100))
        right = world.create_entity("Right")
        right.parent_name = "Split"
        right.add_component(RectTransform(width=100, height=100))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout = system.get_layout_entry("Split")

        # Dragger is at ~200px (0.5 * (400 - 8) + 0)
        dragger_x = float(layout["x"]) + (float(layout["width"]) - 8.0) * 0.5 + 4.0
        dragger_y = float(layout["y"]) + float(layout["height"]) * 0.5

        # Press on dragger
        system.inject_pointer_state(
            x=dragger_x, y=dragger_y,
            down=False, pressed=True, released=False,
        )
        system.update(world, (800.0, 600.0))

        # Drag to the right
        system.inject_pointer_state(
            x=dragger_x + 50.0, y=dragger_y,
            down=True, pressed=False, released=False,
            frames=2,
        )
        system.update(world, (800.0, 600.0))
        system.update(world, (800.0, 600.0))
        self.assertGreater(sc.split_offset, 0.55)

        # Release
        system.inject_pointer_state(
            x=dragger_x + 50.0, y=dragger_y,
            down=False, pressed=False, released=True,
        )
        system.update(world, (800.0, 600.0))

    def test_collapsed_split_only_shows_first_child(self) -> None:
        world = World()
        system = UISystem()
        sc = UISplitContainer(split_offset=0.5, collapsed=True)
        parent = world.create_entity("Split")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(sc)

        left = world.create_entity("Left")
        left.parent_name = "Split"
        left.add_component(RectTransform(width=100, height=100))
        right = world.create_entity("Right")
        right.parent_name = "Split"
        right.add_component(RectTransform(width=100, height=100))

        system._ensure_layout_cache(world, (800.0, 600.0))
        left_l = system.get_layout_entry("Left")
        parent_l = system.get_layout_entry("Split")
        self.assertAlmostEqual(float(left_l["width"]), float(parent_l["width"]), delta=1.0)
        # Right child should not have layout (only 2 children, second is skipped on collapse)
        right_l = system.get_layout_entry("Right")
        self.assertIsNone(right_l)

    def test_drag_step_snapping(self) -> None:
        world = World()
        system = UISystem()
        sc = UISplitContainer(split_offset=0.5, vertical=False, drag_step=10.0)
        parent = world.create_entity("Split")
        parent.add_component(Canvas())
        parent.add_component(RectTransform(width=400, height=300, layout_mode="free"))
        parent.add_component(sc)

        left = world.create_entity("Left")
        left.parent_name = "Split"
        left.add_component(RectTransform(width=100, height=100))

        system._ensure_layout_cache(world, (800.0, 600.0))
        layout = system.get_layout_entry("Split")
        total = float(layout["width"]) - 8.0
        dragger_x = float(layout["x"]) + total * 0.5 + 4.0
        dragger_y = float(layout["y"]) + float(layout["height"]) * 0.5

        system.inject_pointer_state(x=dragger_x, y=dragger_y, down=False, pressed=True, released=False)
        system.update(world, (800.0, 600.0))
        system.inject_pointer_state(x=dragger_x + 7.0, y=dragger_y, down=True, pressed=False, released=False, frames=2)
        system.update(world, (800.0, 600.0))
        system.update(world, (800.0, 600.0))

        # With drag_step=10 and drag length ~7, offset should snap to nearest 10px step
        expected_step = round((total * 0.5 + 7.0) / 10.0) * 10.0 / total
        self.assertAlmostEqual(sc.split_offset, max(0.0, min(1.0, expected_step)), delta=0.05)


class ComponentRegistryTests(unittest.TestCase):
    """Tests that all new components are registered."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_uitabbar_registered(self) -> None:
        cls = self.registry.get("UITabBar")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, UITabBar)

    def test_uitabcontainer_registered(self) -> None:
        cls = self.registry.get("UITabContainer")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, UITabContainer)

    def test_uisplitcontainer_registered(self) -> None:
        cls = self.registry.get("UISplitContainer")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, UISplitContainer)

    def test_registered_names_consistent(self) -> None:
        names = self.registry.list_registered()
        self.assertIn("UITabBar", names)
        self.assertIn("UITabContainer", names)
        self.assertIn("UISplitContainer", names)

    def test_can_create_from_dict(self) -> None:
        tabbar = self.registry.create("UITabBar", {
            "tabs": [{"title": "Tab 1"}],
            "current_tab": 0,
            "tab_alignment": "center",
        })
        self.assertIsInstance(tabbar, UITabBar)
        self.assertEqual(tabbar.tab_alignment, "center")

        split = self.registry.create("UISplitContainer", {
            "split_offset": 0.7,
            "vertical": True,
        })
        self.assertIsInstance(split, UISplitContainer)
        self.assertEqual(split.split_offset, 0.7)
        self.assertTrue(split.vertical)

        container = self.registry.create("UITabContainer", {
            "tab_titles": [{"title": "A"}, {"title": "B"}],
            "current_tab": 1,
        })
        self.assertIsInstance(container, UITabContainer)
        self.assertEqual(container.current_tab, 1)
