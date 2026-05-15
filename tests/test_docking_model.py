import unittest

from engine.editor.ui_core.docking import DockArea, DockLayout, DockSplit, FloatingDockWindow, normalize_ratio


class DockingModelTests(unittest.TestCase):
    def test_default_layout_roundtrips_and_collects_areas(self) -> None:
        layout = DockLayout.default()
        restored = DockLayout.from_dict(layout.to_dict())

        self.assertEqual([area.id for area in restored.collect_areas()], ["hierarchy", "center", "inspector", "bottom"])
        self.assertEqual(restored.active_tab("center"), "SCENE")
        self.assertEqual(restored.active_tab("bottom"), "PROJECT")

    def test_corrupt_payload_returns_default_layout(self) -> None:
        layout = DockLayout.from_dict({"root": {"type": "split", "id": "bad"}})

        self.assertEqual(layout.active_tab("center"), "SCENE")
        self.assertIsNotNone(layout.find_area("inspector"))

    def test_move_tab_between_areas_updates_active_tabs(self) -> None:
        layout = DockLayout.default()

        self.assertTrue(layout.move_tab("CONSOLE", "center", 1))

        self.assertEqual(layout.find_area("center").tabs, ["SCENE", "CONSOLE", "GAME", "FLOW", "ANIMATOR"])
        self.assertEqual(layout.active_tab("center"), "CONSOLE")
        self.assertNotIn("CONSOLE", layout.find_area("bottom").tabs)

    def test_reorder_tab_clamps_index(self) -> None:
        layout = DockLayout.default()

        self.assertTrue(layout.reorder_tab("center", "ANIMATOR", -10))
        self.assertEqual(layout.find_area("center").tabs[0], "ANIMATOR")

        self.assertTrue(layout.reorder_tab("center", "ANIMATOR", 999))
        self.assertEqual(layout.find_area("center").tabs[-1], "ANIMATOR")

    def test_ratio_normalization(self) -> None:
        self.assertEqual(normalize_ratio(-1), 0.1)
        self.assertEqual(normalize_ratio(2), 0.9)
        self.assertEqual(normalize_ratio("bad"), 0.5)

        split = DockSplit("s", "diagonal", 2, DockArea("a"), DockArea("b"))
        self.assertEqual(split.direction, "horizontal")
        self.assertEqual(split.ratio, 0.9)

    def test_floating_window_roundtrips_and_docks_back(self) -> None:
        layout = DockLayout.default()

        self.assertTrue(layout.float_tab("CONSOLE", "bottom", (10, 20, 320, 240)))

        self.assertNotIn("CONSOLE", layout.find_area("bottom").tabs)
        window = layout.find_floating_window("CONSOLE")
        self.assertIsNotNone(window)
        self.assertEqual(window.to_dict()["width"], 320.0)

        restored = DockLayout.from_dict(layout.to_dict())
        self.assertEqual(restored.find_floating_window("CONSOLE").to_dict()["x"], 10.0)

        self.assertTrue(restored.move_floating_window("CONSOLE", (30, 40, 500, 300)))
        self.assertEqual(restored.find_floating_window("CONSOLE").to_dict()["height"], 300.0)
        self.assertTrue(restored.close_floating_window("CONSOLE"))
        self.assertFalse(restored.find_floating_window("CONSOLE").is_open)
        self.assertTrue(restored.dock_floating_tab("CONSOLE", "center", 1))
        self.assertEqual(restored.find_area("center").tabs[1], "CONSOLE")
        self.assertIsNone(restored.find_floating_window("CONSOLE"))

    def test_area_pin_and_auto_hide_roundtrip(self) -> None:
        area = DockArea("left", ["A"], "A", pinned=False, auto_hide=True)
        layout = DockLayout(DockSplit("root", "horizontal", 0.5, area, DockArea("right", ["B"])))

        restored = DockLayout.from_dict(layout.to_dict())

        self.assertFalse(restored.find_area("left").pinned)
        self.assertTrue(restored.find_area("left").auto_hide)
        self.assertTrue(restored.set_area_pinned("left", True))
        self.assertTrue(restored.set_area_auto_hide("left", False))
        self.assertTrue(restored.find_area("left").pinned)
        self.assertFalse(restored.find_area("left").auto_hide)

    def test_floating_window_clamps_size(self) -> None:
        window = FloatingDockWindow("A", 0, 0, -10, 0)

        self.assertEqual(window.width, 1.0)
        self.assertEqual(window.height, 1.0)


if __name__ == "__main__":
    unittest.main()
