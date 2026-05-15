import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.editor.editor_layout import EditorLayout
from engine.editor.ui_core.docking import DockArea, DockLayout, DockSplit
from engine.project.project_service import ProjectService


class EditorLayoutDockingTests(unittest.TestCase):
    def _layout(self) -> EditorLayout:
        with patch.object(EditorLayout, "_resize_render_textures", return_value=None):
            return EditorLayout(1024, 768)

    def test_editor_layout_exports_and_applies_dock_layout(self) -> None:
        layout = self._layout()

        self.assertTrue(layout.move_dock_tab("CONSOLE", "center", 1))
        self.assertTrue(layout.consume_dock_layout_dirty())
        exported = layout.export_dock_layout()

        restored = self._layout()
        restored.apply_dock_layout(exported)

        self.assertEqual(restored.dock_layout.find_area("center").tabs[1], "CONSOLE")
        self.assertEqual(restored.active_tab, "SCENE")

    def test_editor_layout_reorder_and_active_tab_mark_dirty(self) -> None:
        layout = self._layout()

        self.assertTrue(layout.reorder_dock_tab("center", "GAME", 0))
        self.assertTrue(layout.set_dock_active_tab("center", "GAME"))

        self.assertEqual(layout.dock_layout.find_area("center").tabs[0], "GAME")
        self.assertEqual(layout.active_tab, "GAME")
        self.assertTrue(layout.consume_editor_preferences_dirty())

    def test_corrupt_applied_layout_falls_back_to_safe_default(self) -> None:
        layout = self._layout()

        layout.apply_dock_layout({"root": {"type": "unknown"}})

        self.assertEqual(layout.dock_layout.active_tab("center"), "SCENE")
        self.assertFalse(layout.consume_dock_layout_dirty())

    def test_project_service_persists_layout_in_editor_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            global_state = Path(tmp) / "global"
            service = ProjectService(root, global_state_dir=global_state)
            layout = self._layout()
            layout.move_dock_tab("CONSOLE", "center", 1)

            state = service.load_editor_state()
            state["layout"] = layout.export_dock_layout()
            service.save_editor_state(state)

            restored = service.load_editor_state()["layout"]
            applied = self._layout()
            applied.apply_dock_layout(restored)

            self.assertEqual(applied.dock_layout.find_area("center").tabs[1], "CONSOLE")

    def test_dock_layout_ratios_change_actual_editor_rects(self) -> None:
        layout = self._layout()
        original_width = layout.hierarchy_rect.width
        dock = DockLayout(
            DockSplit(
                "root",
                "vertical",
                0.74,
                DockSplit(
                    "main",
                    "horizontal",
                    0.30,
                    DockArea("hierarchy", ["HIERARCHY"], "HIERARCHY"),
                    DockSplit(
                        "main_right",
                        "horizontal",
                        0.70,
                        DockArea("center", ["SCENE", "GAME"], "SCENE"),
                        DockArea("inspector", ["INSPECTOR"], "INSPECTOR"),
                    ),
                ),
                DockArea("bottom", ["PROJECT"], "PROJECT"),
            )
        )

        layout.apply_dock_layout(dock.to_dict())

        self.assertNotEqual(layout.hierarchy_rect.width, original_width)
        self.assertGreater(layout.center_rect.x, layout.hierarchy_rect.x + layout.hierarchy_rect.width)
        self.assertGreater(layout.bottom_rect.y, layout.center_rect.y)

    def test_compute_tab_rects_follows_dock_tab_order(self) -> None:
        layout = self._layout()

        before = layout.compute_dock_tab_rects("center")
        self.assertLess(before["SCENE"].x, before["GAME"].x)

        self.assertTrue(layout.reorder_dock_tab("center", "GAME", 0))
        after = layout.compute_dock_tab_rects("center")

        self.assertLess(after["GAME"].x, after["SCENE"].x)
        self.assertTrue(layout.consume_dock_layout_dirty())

    def test_basic_tab_drag_completion_moves_tab_and_marks_dirty(self) -> None:
        layout = self._layout()

        self.assertTrue(layout.begin_dock_tab_drag("CONSOLE"))
        self.assertTrue(layout.complete_dock_tab_drag("center", 1))

        self.assertEqual(layout.dock_layout.find_area("center").tabs[1], "CONSOLE")
        self.assertTrue(layout.consume_dock_layout_dirty())

    def test_editor_layout_floating_window_wrappers_persist_and_mark_dirty(self) -> None:
        layout = self._layout()

        self.assertTrue(layout.float_dock_tab("CONSOLE", "bottom", (20, 30, 360, 240)))
        self.assertTrue(layout.consume_dock_layout_dirty())
        exported = layout.export_dock_layout()

        restored = self._layout()
        restored.apply_dock_layout(exported)

        self.assertIsNotNone(restored.dock_layout.find_floating_window("CONSOLE"))
        self.assertNotIn("CONSOLE", restored.dock_layout.find_area("bottom").tabs)
        self.assertTrue(restored.move_floating_window("CONSOLE", (40, 50, 420, 260)))
        self.assertTrue(restored.close_floating_window("CONSOLE"))
        self.assertFalse(restored.dock_layout.find_floating_window("CONSOLE").is_open)
        self.assertTrue(restored.dock_floating_tab("CONSOLE", "center", 1))
        self.assertEqual(restored.dock_layout.find_area("center").tabs[1], "CONSOLE")
        self.assertTrue(restored.consume_dock_layout_dirty())

    def test_editor_layout_area_pin_auto_hide_wrappers_persist(self) -> None:
        layout = self._layout()

        self.assertTrue(layout.set_dock_area_pinned("hierarchy", False))
        self.assertTrue(layout.set_dock_area_auto_hide("hierarchy", True))
        exported = layout.export_dock_layout()

        restored = self._layout()
        restored.apply_dock_layout(exported)

        self.assertFalse(restored.dock_layout.find_area("hierarchy").pinned)
        self.assertTrue(restored.dock_layout.find_area("hierarchy").auto_hide)
        self.assertGreater(restored.hierarchy_rect.width, 0)


if __name__ == "__main__":
    unittest.main()
