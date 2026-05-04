"""
tests/test_canvas_item_2d.py - Tests para CanvasItem2D componente + API.
"""

from __future__ import annotations

import unittest

from engine.components.canvas_item_2d import CanvasItem2D
from engine.levels.component_registry import create_default_registry


class TestCanvasItem2D(unittest.TestCase):

    def test_create_canvas_item(self):
        canvas = CanvasItem2D()
        self.assertEqual(canvas.z_index, 0)
        self.assertEqual(canvas.draw_commands, [])
        self.assertTrue(canvas.enabled)

    def test_add_rect_command(self):
        canvas = CanvasItem2D()
        canvas.add_rect(10, 20, 100, 50, (255, 0, 0, 255), filled=True)
        self.assertEqual(len(canvas.draw_commands), 1)
        cmd = canvas.draw_commands[0]
        self.assertEqual(cmd["shape"], "rect")
        self.assertEqual(cmd["x"], 10)
        self.assertEqual(cmd["y"], 20)
        self.assertEqual(cmd["w"], 100)
        self.assertEqual(cmd["h"], 50)
        self.assertEqual(cmd["color"], [255, 0, 0, 255])
        self.assertTrue(cmd["filled"])

    def test_add_circle_command(self):
        canvas = CanvasItem2D()
        canvas.add_circle(50, 60, 30, (0, 255, 0, 255), filled=False)
        self.assertEqual(len(canvas.draw_commands), 1)
        cmd = canvas.draw_commands[0]
        self.assertEqual(cmd["shape"], "circle")
        self.assertEqual(cmd["cx"], 50)
        self.assertEqual(cmd["cy"], 60)
        self.assertEqual(cmd["radius"], 30)
        self.assertEqual(cmd["color"], [0, 255, 0, 255])
        self.assertFalse(cmd["filled"])

    def test_add_line_command(self):
        canvas = CanvasItem2D()
        canvas.add_line(0, 0, 100, 100, (0, 0, 255, 255), thickness=3.0)
        self.assertEqual(len(canvas.draw_commands), 1)
        cmd = canvas.draw_commands[0]
        self.assertEqual(cmd["shape"], "line")
        self.assertEqual(cmd["x1"], 0)
        self.assertEqual(cmd["y1"], 0)
        self.assertEqual(cmd["x2"], 100)
        self.assertEqual(cmd["y2"], 100)
        self.assertEqual(cmd["color"], [0, 0, 255, 255])
        self.assertEqual(cmd["thickness"], 3.0)

    def test_serialization_roundtrip(self):
        canvas = CanvasItem2D(z_index=5)
        canvas.add_rect(0, 0, 64, 64, (255, 255, 255, 255))
        canvas.add_circle(32, 32, 16, (255, 0, 0, 128), filled=False)

        data = canvas.to_dict()
        self.assertEqual(data["z_index"], 5)
        self.assertEqual(len(data["draw_commands"]), 2)

        restored = CanvasItem2D.from_dict(data)
        self.assertEqual(restored.z_index, 5)
        self.assertEqual(len(restored.draw_commands), 2)
        self.assertEqual(restored.draw_commands[0]["shape"], "rect")
        self.assertEqual(restored.draw_commands[1]["shape"], "circle")

    def test_registry_creation(self):
        registry = create_default_registry()
        component_class = registry.get("CanvasItem2D")
        self.assertIsNotNone(component_class)
        instance = registry.create("CanvasItem2D", {"z_index": 10, "draw_commands": []})
        self.assertIsInstance(instance, CanvasItem2D)
        self.assertEqual(instance.z_index, 10)

    def test_clear_commands(self):
        canvas = CanvasItem2D()
        canvas.add_rect(0, 0, 32, 32)
        canvas.add_circle(16, 16, 8)
        self.assertEqual(len(canvas.draw_commands), 2)
        canvas.clear_commands()
        self.assertEqual(len(canvas.draw_commands), 0)

    def test_api_draw_rect(self):
        import json
        import tempfile
        from pathlib import Path

        from engine.api import EngineAPI
        from engine.project.project_service import ProjectService

        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        ProjectService(root)
        level_path = root / "levels" / "canvas_test.json"
        level_path.write_text(
            json.dumps({"name": "CanvasTest", "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
            encoding="utf-8",
        )

        try:
            api = EngineAPI(project_root=root.as_posix())
            api.load_level("levels/canvas_test.json")

            entity_name = "test_canvas_entity"
            api.create_entity(entity_name)
            result = api.draw_rect(entity_name, 10, 20, 100, 50, [255, 0, 0, 255])
            self.assertTrue(result.get("success"))

            entity_data = api.get_entity(entity_name)
            components = entity_data.get("components", {})
            self.assertIn("CanvasItem2D", components)
            canvas_data = components["CanvasItem2D"]
            self.assertEqual(len(canvas_data.get("draw_commands", [])), 1)
        finally:
            try:
                api.shutdown()
            except Exception:
                pass
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
