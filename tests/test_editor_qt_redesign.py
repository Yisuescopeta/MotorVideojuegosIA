import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


@unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
class EditorQtRedesignTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        self.app = QApplication.instance() or QApplication([])

    def test_frostline_theme_loader_loads_dark_and_light(self) -> None:
        from editor_qt.theme import editor_asset_path, load_editor_icon, load_theme, theme_path

        self.assertTrue(theme_path("frost_dark").exists())
        self.assertTrue(theme_path("frost_light").exists())
        self.assertTrue(editor_asset_path("brand", "logo_frostline.png").exists())
        self.assertFalse(load_editor_icon("brand", "logo_frostline.png").isNull())
        self.assertTrue(load_editor_icon("missing", "nope.png").isNull())

        loaded_dark = load_theme(self.app, "frost_dark")
        self.assertEqual(loaded_dark, "frost_dark")
        self.assertIn("#TopBar", self.app.styleSheet())

        loaded_light = load_theme(self.app, "frost_light")
        self.assertEqual(loaded_light, "frost_light")
        self.assertIn("#SideRail", self.app.styleSheet())

    def test_main_window_theme_switch_persists_preference_without_scene_edit(self) -> None:
        from editor_qt.bridge.engine_facade import EditorEngineFacade
        from editor_qt.main_window import MainWindow
        from tests.test_editor_qt_foundation import FakeEngineAPI

        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api), initial_theme="frost_dark")
        self.app.processEvents()
        try:
            self.assertEqual(window.findChild(type(window.center_tabs), "CenterTabs").objectName(), "CenterTabs")
            self.assertIsNotNone(window.findChild(type(window.top_bar), "TopBar"))
            self.assertIsNotNone(window.findChild(type(window.account_button), "AccountButton"))
            self.assertIsNotNone(window.findChild(type(window.top_bar), "TopBarProjectGroup"))
            self.assertFalse(window.account_button.icon().isNull())
            window.theme_action.trigger()
            self.app.processEvents()

            self.assertEqual(api.edits, [])
            self.assertEqual(api.editor_state["preferences"]["theme"], "frost_light")
        finally:
            api.dirty = False
            window.close()

    def test_hierarchy_search_and_active_toggle_emit_signal(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QSignalSpy

        from editor_qt.panels.hierarchy_panel import HierarchyPanel

        panel = HierarchyPanel()
        panel.set_entities(
            [
                {"name": "Player", "active": True, "parent": None},
                {"name": "Enemy", "active": False, "parent": None},
            ]
        )
        spy = QSignalSpy(panel.entity_active_set_requested)
        self.assertEqual(panel.title_label.text(), "HIERARCHY")
        self.assertEqual(panel.create_button.text(), "+")

        panel.set_search_text("play")
        self.assertFalse(panel.tree.topLevelItem(0).isHidden())
        self.assertTrue(panel.tree.topLevelItem(1).isHidden())

        item = panel.tree.topLevelItem(0)
        item.setCheckState(1, Qt.CheckState.Unchecked)
        self.app.processEvents()

        self.assertEqual(spy.count(), 1)
        self.assertEqual(spy.at(0)[0], "Player")
        self.assertFalse(spy.at(0)[1])

    def test_inspector_component_picker_filters_registry_descriptors(self) -> None:
        from editor_qt.panels.inspector_panel import InspectorPanel

        panel = InspectorPanel()
        panel.set_component_descriptors(
            [
                {"name": "Transform", "badge": "CORE", "description": "", "editor_tags": []},
                {"name": "Light2D", "badge": "CORE", "description": "Light", "editor_tags": ["lighting"]},
                {"name": "Sprite", "badge": "CORE", "description": "Texture", "editor_tags": ["render"]},
            ]
        )
        panel.set_entity({"name": "Lamp", "components": {"Transform": {"x": 0}}})
        self.assertEqual(panel.entity_name_label.text(), "Lamp")
        self.assertTrue(panel.entity_tab.isChecked())

        self.assertEqual(panel.component_names_for_query("light"), ["Light2D"])
        self.assertNotIn("Transform", panel.component_names_for_query(""))

    def test_project_panel_grid_list_and_add_scene_signal(self) -> None:
        from PySide6.QtTest import QSignalSpy

        from editor_qt.panels.project_panel import ProjectPanel

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "assets" / "hero.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"not-a-real-image")
            panel = ProjectPanel()
            view_spy = QSignalSpy(panel.view_mode_changed)
            scene_spy = QSignalSpy(panel.scene_create_requested)
            panel.set_project_data(
                project={"name": "Game", "root": tmpdir},
                active_scene={"path": "levels/main.json"},
                scenes=[{"name": "Main", "path": "levels/main.json"}],
                assets=[{"name": "Hero", "path": "assets/hero.png", "type": "texture"}],
                scripts=[],
                prefabs=[],
            )
            self.assertEqual(panel._panel_title.text(), "PROJECT")
            self.assertIn("1 Assets", panel._panel_summary.text())
            self.assertFalse(panel.assets_grid.item(0).icon().isNull())

            panel.set_view_mode("list")
            self.assertEqual(panel.view_mode(), "list")
            self.assertEqual(view_spy.count(), 1)

            add_scene_item = panel.assets_grid.item(0)
            panel._on_asset_grid_double_clicked(add_scene_item)
            self.assertEqual(scene_spy.count(), 1)

    def test_console_filters_and_command_signal(self) -> None:
        from PySide6.QtTest import QSignalSpy

        from editor_qt.panels.console_panel import ConsolePanel

        panel = ConsolePanel()
        spy = QSignalSpy(panel.command_submitted)
        panel.log("hello", "log")
        panel.log("careful", "warning")
        self.assertIn("1 Warnings", panel.summary_label.text())
        panel.set_filter("Warning")
        self.assertIn("careful", panel.output.toPlainText())
        self.assertNotIn("hello", panel.output.toPlainText())

        panel.command_input.setText("doctor")
        panel.command_input.returnPressed.emit()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(spy.at(0)[0], "doctor")

    def test_viewport_reset_frame_and_zoom_controls(self) -> None:
        from PySide6.QtGui import QPaintEvent

        from editor_qt.panels.viewport_panel import QtSceneViewportPanel

        viewport = QtSceneViewportPanel("Scene")
        viewport.resize(640, 480)
        viewport.set_snapshot(
            scene_info={"name": "Main", "dirty": False},
            entities=[{"name": "Player", "components": {"Transform": {"x": 100, "y": 50}}}],
        )
        viewport.set_selected_entity("Player")
        viewport.set_zoom_percent(175)
        self.assertEqual(viewport.zoom_percent(), 175)

        viewport.frame_selected()
        self.assertNotEqual(viewport._pan_x, 0.0)

        viewport.reset_camera()
        self.assertEqual(viewport.zoom_percent(), 100)
        self.assertEqual(viewport._pan_x, 0.0)
        viewport.paintEvent(QPaintEvent(viewport.rect()))
        self.assertEqual(viewport._chrome_mode, "Select")


if __name__ == "__main__":
    unittest.main()
