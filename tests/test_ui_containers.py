"""
tests/test_ui_containers.py - Tests for GridContainer, FlowContainer,
AspectRatioContainer and CenterContainer layouts.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.recttransform import RectTransform


def _rect_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": True,
        "anchor_min_x": 0.5,
        "anchor_min_y": 0.5,
        "anchor_max_x": 0.5,
        "anchor_max_y": 0.5,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "anchored_x": 0.0,
        "anchored_y": 0.0,
        "width": 100.0,
        "height": 40.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "layout_mode": "free",
        "layout_order": 0,
        "layout_ignore": False,
        "size_mode_x": "fixed",
        "size_mode_y": "fixed",
        "layout_align": "start",
        "padding_left": 0.0,
        "padding_top": 0.0,
        "padding_right": 0.0,
        "padding_bottom": 0.0,
        "spacing": 0.0,
    }
    payload.update(overrides)
    return payload


class TestRectTransformNewLayoutModes(unittest.TestCase):
    """Verify the new layout properties serialize/deserialize correctly."""

    def test_grid_mode_defaults(self) -> None:
        rt = RectTransform(layout_mode="grid")
        self.assertEqual(rt.layout_mode, "grid")
        self.assertEqual(rt.grid_columns, 2)
        self.assertEqual(rt.grid_rows, 1)

    def test_grid_mode_custom(self) -> None:
        rt = RectTransform(layout_mode="grid", grid_columns=3, grid_rows=4)
        self.assertEqual(rt.grid_columns, 3)
        self.assertEqual(rt.grid_rows, 4)

    def test_flow_mode_defaults(self) -> None:
        rt = RectTransform(layout_mode="flow")
        self.assertEqual(rt.layout_mode, "flow")
        self.assertEqual(rt.flow_direction, "horizontal")

    def test_flow_vertical(self) -> None:
        rt = RectTransform(layout_mode="flow", flow_direction="vertical")
        self.assertEqual(rt.flow_direction, "vertical")

    def test_aspect_ratio_defaults(self) -> None:
        rt = RectTransform(layout_mode="aspect_ratio")
        self.assertEqual(rt.layout_mode, "aspect_ratio")
        self.assertEqual(rt.aspect_ratio, 1.0)
        self.assertEqual(rt.aspect_stretch_mode, "fit")

    def test_aspect_ratio_custom(self) -> None:
        rt = RectTransform(
            layout_mode="aspect_ratio",
            aspect_ratio=1.7777,
            aspect_stretch_mode="fill",
        )
        self.assertEqual(rt.aspect_ratio, 1.7777)
        self.assertEqual(rt.aspect_stretch_mode, "fill")

    def test_center_mode(self) -> None:
        rt = RectTransform(layout_mode="center")
        self.assertEqual(rt.layout_mode, "center")

    def test_roundtrip_grid(self) -> None:
        rt = RectTransform(layout_mode="grid", grid_columns=3, grid_rows=2, spacing=5.0, padding_left=10.0)
        data = rt.to_dict()
        restored = RectTransform.from_dict(data)
        self.assertEqual(restored.layout_mode, "grid")
        self.assertEqual(restored.grid_columns, 3)
        self.assertEqual(restored.grid_rows, 2)
        self.assertEqual(restored.spacing, 5.0)
        self.assertEqual(restored.padding_left, 10.0)

    def test_roundtrip_flow(self) -> None:
        rt = RectTransform(layout_mode="flow", flow_direction="vertical", spacing=8.0)
        data = rt.to_dict()
        restored = RectTransform.from_dict(data)
        self.assertEqual(restored.layout_mode, "flow")
        self.assertEqual(restored.flow_direction, "vertical")
        self.assertEqual(restored.spacing, 8.0)

    def test_roundtrip_aspect_ratio(self) -> None:
        rt = RectTransform(
            layout_mode="aspect_ratio",
            aspect_ratio=1.6,
            aspect_stretch_mode="width_control_height",
        )
        data = rt.to_dict()
        restored = RectTransform.from_dict(data)
        self.assertEqual(restored.layout_mode, "aspect_ratio")
        self.assertEqual(restored.aspect_ratio, 1.6)
        self.assertEqual(restored.aspect_stretch_mode, "width_control_height")

    def test_roundtrip_center(self) -> None:
        rt = RectTransform(layout_mode="center")
        data = rt.to_dict()
        restored = RectTransform.from_dict(data)
        self.assertEqual(restored.layout_mode, "center")


class ContainerLayoutTests(unittest.TestCase):
    """Integration tests that verify UISystem lays out children correctly."""

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

    def _make_child_payload(self, name: str, width: float = 50.0, height: float = 50.0, **extra) -> dict:
        p = _rect_payload(width=width, height=height, layout_mode="free")
        p.update(extra)
        return {
            "name": name,
            "enabled": True,
            "transform": {"position": [0.0, 0.0], "scale": [1.0, 1.0], "rotation": 0.0},
            "components": {"RectTransform": p},
            "parent_name": None,
        }

    def _create_canvas_and_container(self, container_layout: str, container_opts: dict | None = None) -> str:
        scene_path = self._write_scene(
            "layout_test.json",
            {"name": "Layout Test", "entities": [], "rules": [], "feature_metadata": {}},
        )
        self.api.load_level(scene_path.as_posix())
        self.api.create_canvas(name="Canvas", reference_width=800, reference_height=600)

        rt_opts: dict[str, object] = {"layout_mode": container_layout, "width": 800.0, "height": 600.0}
        if container_opts:
            rt_opts.update(container_opts)
        result = self.api.create_ui_element("Container", "Canvas", rect_transform=rt_opts)
        self.assertTrue(result.get("success"), f"Failed to create container: {result}")
        return "Container"

    def _add_child(self, name: str, parent: str, **opts) -> None:
        width = float(opts.pop("width", 50.0))
        height = float(opts.pop("height", 50.0))
        self.api.create_ui_element(name, parent, rect_transform={
            "width": width,
            "height": height,
            **opts,
        })

    def _get_ui_system(self):
        return self.api.game._ui_system

    def _get_world(self):
        return self.api.game.world

    def _refresh_layout(self) -> None:
        ui = self._get_ui_system()
        world = self._get_world()
        ui.update(world, (800.0, 600.0), allow_interaction=False)

    def test_grid_container_arranges_children(self) -> None:
        parent = self._create_canvas_and_container("grid", {"grid_columns": 2, "grid_rows": 2, "spacing": 0, "padding_left": 0, "padding_top": 0, "padding_right": 0, "padding_bottom": 0})
        self._add_child("Cell0", parent, width=50, height=50)
        self._add_child("Cell1", parent, width=50, height=50)
        self._add_child("Cell2", parent, width=50, height=50)
        self._add_child("Cell3", parent, width=50, height=50)

        self._refresh_layout()
        ui = self._get_ui_system()
        layout0 = ui.get_entity_screen_rect("Cell0")
        layout1 = ui.get_entity_screen_rect("Cell1")
        layout2 = ui.get_entity_screen_rect("Cell2")
        layout3 = ui.get_entity_screen_rect("Cell3")

        self.assertIsNotNone(layout0)
        self.assertIsNotNone(layout1)
        self.assertIsNotNone(layout2)
        self.assertIsNotNone(layout3)

        # Two columns: Cell0 left, Cell1 right
        self.assertLess(layout0["x"], layout1["x"])
        # Cell0 and Cell1 same row
        self.assertAlmostEqual(layout0["y"], layout1["y"], places=1)
        # Cell2 below Cell0
        self.assertGreater(layout2["y"], layout0["y"])

    def test_grid_overflow_hidden(self) -> None:
        """Children beyond grid rows should not appear in layout."""
        parent = self._create_canvas_and_container("grid", {"grid_columns": 1, "grid_rows": 1, "spacing": 0, "padding_left": 0, "padding_top": 0, "padding_right": 0, "padding_bottom": 0})
        self._add_child("Visible", parent)
        self._add_child("Hidden", parent)

        self._refresh_layout()
        ui = self._get_ui_system()
        self.assertIsNotNone(ui.get_entity_screen_rect("Visible"))
        self.assertIsNone(ui.get_entity_screen_rect("Hidden"))

    def test_flow_container_wraps_to_next_row(self) -> None:
        parent = self._create_canvas_and_container("flow", {"spacing": 0, "padding_left": 0, "padding_top": 0, "padding_right": 0, "padding_bottom": 0})
        # Children that exceed 800px width, forcing wrap
        self._add_child("ChildA", parent, width=500, height=50)
        self._add_child("ChildB", parent, width=500, height=50)

        self._refresh_layout()
        ui = self._get_ui_system()
        la = ui.get_entity_screen_rect("ChildA")
        lb = ui.get_entity_screen_rect("ChildB")

        self.assertIsNotNone(la)
        self.assertIsNotNone(lb)
        # Second child wraps below first
        self.assertGreater(lb["y"], la["y"])

    def test_flow_vertical_direction(self) -> None:
        parent = self._create_canvas_and_container("flow", {"flow_direction": "vertical", "spacing": 0, "padding_left": 0, "padding_top": 0, "padding_right": 0, "padding_bottom": 0})
        self._add_child("Top", parent, width=100, height=400)
        self._add_child("Bottom", parent, width=100, height=400)

        self._refresh_layout()
        ui = self._get_ui_system()
        la = ui.get_entity_screen_rect("Top")
        lb = ui.get_entity_screen_rect("Bottom")

        self.assertIsNotNone(la)
        self.assertIsNotNone(lb)
        # Second child wraps to next column (right)
        self.assertGreater(lb["x"], la["x"])

    def test_aspect_ratio_keeps_proportions(self) -> None:
        parent = self._create_canvas_and_container("aspect_ratio", {"aspect_ratio": 2.0, "aspect_stretch_mode": "fit"})
        self._add_child("Image", parent, width=800, height=600)

        self._refresh_layout()
        ui = self._get_ui_system()
        rect = ui.get_entity_screen_rect("Image")
        self.assertIsNotNone(rect)
        # ratio = 2.0, fit within 800x600:
        # target_w = min(800, 600 * 2.0 = 1200) = 800
        # target_h = 800 / 2.0 = 400
        self.assertAlmostEqual(rect["width"] / max(rect["height"], 1.0), 2.0, places=1)

    def test_aspect_ratio_fill_mode(self) -> None:
        parent = self._create_canvas_and_container("aspect_ratio", {"aspect_ratio": 2.0, "aspect_stretch_mode": "fill"})
        self._add_child("Fill", parent)

        self._refresh_layout()
        ui = self._get_ui_system()
        rect = ui.get_entity_screen_rect("Fill")
        self.assertIsNotNone(rect)
        # fill mode: cover entire area
        # target_w = 800, target_h = 800/2=400, but 400 < 600 → target_h=600, target_w=1200
        self.assertGreaterEqual(rect["width"], 800.0)
        self.assertGreaterEqual(rect["height"], 600.0)

    def test_center_container_centers_child(self) -> None:
        parent = self._create_canvas_and_container("center")
        self._add_child("Centered", parent, width=100, height=50)

        self._refresh_layout()
        ui = self._get_ui_system()
        rect = ui.get_entity_screen_rect("Centered")
        self.assertIsNotNone(rect)
        # Container is 800x600, child is 100x50
        # Centered: x = (800-100)/2 = 350
        self.assertAlmostEqual(rect["x"], 350.0, places=1)
        self.assertAlmostEqual(rect["y"], 275.0, places=1)


if __name__ == "__main__":
    unittest.main()
