"""
tests/test_ui_panels.py - Tests for UIPanel and UIScrollContainer components.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.uipanel import UIPanel
from engine.components.uiscrollcontainer import UIScrollContainer
from engine.levels.component_registry import create_default_registry


class TestUIPanel(unittest.TestCase):
    def test_create_panel(self) -> None:
        panel = UIPanel()
        self.assertTrue(panel.enabled)
        self.assertEqual(panel.color, (40, 40, 40, 255))
        self.assertEqual(panel.border_color, (60, 60, 60, 255))
        self.assertEqual(panel.border_width, 0)
        self.assertEqual(panel.corner_radius, 0)
        self.assertEqual(panel.texture_path, "")

    def test_panel_serialization(self) -> None:
        panel = UIPanel(
            enabled=True,
            color=(20, 30, 40, 200),
            border_color=(100, 100, 100, 255),
            border_width=2,
            corner_radius=8,
            texture_path="res://ui/panel_bg.png",
        )
        data = panel.to_dict()
        restored = UIPanel.from_dict(data)
        self.assertEqual(restored.enabled, panel.enabled)
        self.assertEqual(restored.color, panel.color)
        self.assertEqual(restored.border_color, panel.border_color)
        self.assertEqual(restored.border_width, panel.border_width)
        self.assertEqual(restored.corner_radius, panel.corner_radius)
        self.assertEqual(restored.texture_path, panel.texture_path)

    def test_panel_serialization_json(self) -> None:
        panel = UIPanel(
            color=(10, 20, 30, 255),
            border_color=(200, 100, 50, 255),
            border_width=4,
            corner_radius=12,
        )
        payload = panel.to_dict()
        raw = json.dumps(payload)
        loaded = json.loads(raw)
        restored = UIPanel.from_dict(loaded)
        self.assertEqual(restored.color, panel.color)
        self.assertEqual(restored.border_width, panel.border_width)

    def test_panel_custom_colors(self) -> None:
        panel = UIPanel(
            color=(255, 0, 0, 128),
            border_color=(0, 255, 0, 200),
        )
        self.assertEqual(panel.color, (255, 0, 0, 128))
        self.assertEqual(panel.border_color, (0, 255, 0, 200))

    def test_panel_from_dict_defaults(self) -> None:
        panel = UIPanel.from_dict({})
        self.assertTrue(panel.enabled)
        self.assertEqual(panel.color, (40, 40, 40, 255))
        self.assertEqual(panel.border_color, (60, 60, 60, 255))
        self.assertEqual(panel.border_width, 0)
        self.assertEqual(panel.corner_radius, 0)
        self.assertEqual(panel.texture_path, "")


class TestUIScrollContainer(unittest.TestCase):
    def test_create_scroll_container(self) -> None:
        sc = UIScrollContainer()
        self.assertTrue(sc.enabled)
        self.assertFalse(sc.scroll_horizontal)
        self.assertTrue(sc.scroll_vertical)
        self.assertEqual(sc.content_width, 200.0)
        self.assertEqual(sc.content_height, 200.0)
        self.assertEqual(sc.scroll_x, 0.0)
        self.assertEqual(sc.scroll_y, 0.0)

    def test_scroll_serialization(self) -> None:
        sc = UIScrollContainer(
            enabled=True,
            scroll_horizontal=True,
            scroll_vertical=False,
            content_width=400.0,
            content_height=300.0,
        )
        data = sc.to_dict()
        restored = UIScrollContainer.from_dict(data)
        self.assertEqual(restored.enabled, sc.enabled)
        self.assertEqual(restored.scroll_horizontal, sc.scroll_horizontal)
        self.assertEqual(restored.scroll_vertical, sc.scroll_vertical)
        self.assertEqual(restored.content_width, sc.content_width)
        self.assertEqual(restored.content_height, sc.content_height)

    def test_scroll_container_scroll(self) -> None:
        sc = UIScrollContainer(scroll_horizontal=True, scroll_vertical=True)
        sc.scroll(50.0, 100.0)
        self.assertEqual(sc.scroll_x, 50.0)
        self.assertEqual(sc.scroll_y, 100.0)
        # scroll again
        sc.scroll(30.0, 50.0)
        self.assertEqual(sc.scroll_x, 80.0)
        self.assertEqual(sc.scroll_y, 150.0)

    def test_scroll_container_scroll_no_horizontal(self) -> None:
        sc = UIScrollContainer(scroll_horizontal=False, scroll_vertical=True)
        sc.scroll(50.0, 100.0)
        self.assertEqual(sc.scroll_x, 0.0)
        self.assertEqual(sc.scroll_y, 100.0)

    def test_scroll_container_scroll_no_vertical(self) -> None:
        sc = UIScrollContainer(scroll_horizontal=True, scroll_vertical=False)
        sc.scroll(50.0, 100.0)
        self.assertEqual(sc.scroll_x, 50.0)
        self.assertEqual(sc.scroll_y, 0.0)

    def test_scroll_container_scroll_clamped_negative(self) -> None:
        sc = UIScrollContainer(scroll_horizontal=True, scroll_vertical=True)
        sc.scroll(-200.0, -200.0)
        self.assertEqual(sc.scroll_x, 0.0)
        self.assertEqual(sc.scroll_y, 0.0)

    def test_scroll_container_from_dict_defaults(self) -> None:
        sc = UIScrollContainer.from_dict({})
        self.assertTrue(sc.enabled)
        self.assertFalse(sc.scroll_horizontal)
        self.assertTrue(sc.scroll_vertical)
        self.assertEqual(sc.content_width, 200.0)
        self.assertEqual(sc.content_height, 200.0)

    def test_scroll_container_runtime_not_serialized(self) -> None:
        sc = UIScrollContainer(scroll_horizontal=True, scroll_vertical=True)
        sc.scroll(50.0, 30.0)
        self.assertEqual(sc.scroll_x, 50.0)
        self.assertEqual(sc.scroll_y, 30.0)
        data = sc.to_dict()
        self.assertNotIn("_scroll_x", data)
        self.assertNotIn("_scroll_y", data)


class TestComponentRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_registry_panel(self) -> None:
        cls = self.registry.get("UIPanel")
        self.assertIsNotNone(cls)
        self.assertIs(cls, UIPanel)
        panel = self.registry.create("UIPanel", {"color": [100, 100, 100, 255]})
        self.assertIsInstance(panel, UIPanel)
        self.assertEqual(panel.color, (100, 100, 100, 255))

    def test_registry_panel_defaults(self) -> None:
        panel = self.registry.create("UIPanel", {})
        self.assertIsInstance(panel, UIPanel)
        self.assertEqual(panel.color, (40, 40, 40, 255))

    def test_registry_scroll(self) -> None:
        cls = self.registry.get("UIScrollContainer")
        self.assertIsNotNone(cls)
        self.assertIs(cls, UIScrollContainer)
        sc = self.registry.create("UIScrollContainer", {"content_width": 800.0})
        self.assertIsInstance(sc, UIScrollContainer)
        self.assertEqual(sc.content_width, 800.0)

    def test_registry_scroll_defaults(self) -> None:
        sc = self.registry.create("UIScrollContainer", {})
        self.assertIsInstance(sc, UIScrollContainer)
        self.assertTrue(sc.scroll_vertical)
        self.assertFalse(sc.scroll_horizontal)

    def test_registry_metadata_panel(self) -> None:
        descriptor = self.registry.get_descriptor("UIPanel")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.name, "UIPanel")
        self.assertEqual(descriptor.origin, "native")
        self.assertIn("ui", descriptor.editor_tags)
        self.assertIn("container", descriptor.editor_tags)

    def test_registry_metadata_scroll(self) -> None:
        descriptor = self.registry.get_descriptor("UIScrollContainer")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.name, "UIScrollContainer")
        self.assertIn("scroll", descriptor.editor_tags)


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

    def test_api_create_panel(self) -> None:
        scene_path = self._write_scene(
            "panel_test.json",
            {"name": "Panel Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level(scene_path.as_posix())
        result = self.api.create_canvas(name="MainCanvas")
        self.assertTrue(result["success"])
        result = self.api.create_panel("MyPanel", "MainCanvas")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyPanel")
        self.assertIsNotNone(entity)

    def test_api_create_scroll_container(self) -> None:
        scene_path = self._write_scene(
            "scroll_test.json",
            {"name": "Scroll Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level(scene_path.as_posix())
        result = self.api.create_canvas(name="MainCanvas")
        self.assertTrue(result["success"])
        result = self.api.create_scroll_container("MyScroll", "MainCanvas")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("MyScroll")
        self.assertIsNotNone(entity)

    def test_api_list_ui_nodes_includes_panel_and_scroll(self) -> None:
        scene_path = self._write_scene(
            "ui_nodes_test.json",
            {"name": "UI Nodes Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level(scene_path.as_posix())
        self.api.create_canvas(name="MainCanvas")
        self.api.create_panel("MyPanel", "MainCanvas")
        self.api.create_scroll_container("MyScroll", "MainCanvas")
        nodes = self.api.list_ui_nodes()
        names = [n["name"] for n in nodes]
        self.assertIn("MyPanel", names)
        self.assertIn("MyScroll", names)


if __name__ == "__main__":
    unittest.main()
