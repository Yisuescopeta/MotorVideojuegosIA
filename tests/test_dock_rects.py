import unittest

from engine.editor.ui_core.docking import DockArea, DockLayout, DockSplit
from engine.editor.ui_core.dock_rects import compute_dock_rects


class DockRectsTests(unittest.TestCase):
    def test_default_layout_computes_expected_area_order(self) -> None:
        rects = compute_dock_rects(DockLayout.default(), (0, 52, 1000, 700), splitter_size=4)

        self.assertEqual(set(rects.areas), {"hierarchy", "center", "inspector", "bottom"})
        self.assertGreater(rects.areas["center"][2], rects.areas["hierarchy"][2])
        self.assertGreater(rects.areas["bottom"][1], rects.areas["center"][1])
        self.assertEqual(set(rects.splitters), {"root", "main", "main_right"})

    def test_split_ratios_change_area_rects(self) -> None:
        layout = DockLayout(
            DockSplit(
                "root",
                "horizontal",
                0.25,
                DockArea("left", ["A"]),
                DockArea("right", ["B"]),
            )
        )

        rects = compute_dock_rects(layout, (0, 0, 400, 100), splitter_size=4)

        self.assertEqual(rects.areas["left"], (0.0, 0.0, 99.0, 100.0))
        self.assertEqual(rects.splitters["root"], (99.0, 0.0, 4.0, 100.0))
        self.assertEqual(rects.areas["right"], (103.0, 0.0, 297.0, 100.0))

    def test_vertical_split_uses_top_bottom(self) -> None:
        layout = DockLayout(
            DockSplit("root", "vertical", 0.5, DockArea("top", ["A"]), DockArea("bottom", ["B"]))
        )

        rects = compute_dock_rects(layout, (10, 20, 200, 104), splitter_size=4)

        self.assertEqual(rects.areas["top"], (10.0, 20.0, 200.0, 50.0))
        self.assertEqual(rects.splitters["root"], (10.0, 70.0, 200.0, 4.0))
        self.assertEqual(rects.areas["bottom"], (10.0, 74.0, 200.0, 50.0))


if __name__ == "__main__":
    unittest.main()
