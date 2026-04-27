import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.api import EngineAPI
from engine.components.uibutton import UIButton
from engine.editor.cursor_manager import CursorVisualState
from engine.systems.ui_render_system import UIRenderSystem

REPO_ROOT = Path(__file__).resolve().parents[1]


def _rect_transform_payload(**overrides: object) -> dict[str, object]:
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


class CanvasUISystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "CanvasProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _copy_real_scene(self, filename: str) -> Path:
        source = REPO_ROOT / "levels" / filename
        target = self.project_root / "levels" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def test_canvas_components_roundtrip_and_api_lists_ui_nodes(self) -> None:
        scene_path = self._write_scene(
            "ui_roundtrip.json",
            {
                "name": "UI Roundtrip",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(self.api.create_ui_text("Title", "Hello UI", "CanvasRoot", {"width": 320.0, "height": 80.0})["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )
        self.api.game.save_current_scene()

        raw = json.loads(scene_path.read_text(encoding="utf-8"))
        entity_names = {entity["name"] for entity in raw["entities"]}
        self.assertIn("CanvasRoot", entity_names)
        self.assertIn("Title", entity_names)
        self.assertIn("PlayButton", entity_names)
        self.assertEqual(raw["entities"][0]["components"]["Canvas"]["render_mode"], "screen_space_overlay")
        self.assertEqual(raw["entities"][1]["components"]["UIText"]["text"], "Hello UI")
        self.assertEqual(raw["entities"][2]["components"]["UIButton"]["on_click"]["name"], "ui.play_clicked")

        ui_nodes = {entity["name"] for entity in self.api.list_ui_nodes()}
        self.assertEqual(ui_nodes, {"CanvasRoot", "Title", "PlayButton"})

    def test_ui_button_roundtrip_preserves_optional_sprite_fields(self) -> None:
        scene_path = self._write_scene(
            "ui_button_sprite_roundtrip.json",
            {
                "name": "UI Button Sprite Roundtrip",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
                normal_sprite={"path": "assets/ui/button_normal.png"},
                pressed_sprite={"path": "assets/ui/button_pressed.png"},
                normal_slice="idle",
                pressed_slice="pressed",
                preserve_aspect=False,
            )["success"]
        )
        self.api.game.save_current_scene()

        raw = json.loads(scene_path.read_text(encoding="utf-8"))
        button = next(entity for entity in raw["entities"] if entity["name"] == "PlayButton")
        payload = button["components"]["UIButton"]

        self.assertEqual(payload["normal_sprite"], {"guid": "", "path": "assets/ui/button_normal.png"})
        self.assertEqual(payload["pressed_sprite"], {"guid": "", "path": "assets/ui/button_pressed.png"})
        self.assertEqual(payload["normal_slice"], "idle")
        self.assertEqual(payload["pressed_slice"], "pressed")
        self.assertFalse(payload["preserve_aspect"])

    def test_create_ui_image_is_listed_as_ui_node_and_serialized(self) -> None:
        scene_path = self._write_scene(
            "ui_image.json",
            {
                "name": "UI Image",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_image(
                "TitleBanner",
                "CanvasRoot",
                {"path": "assets/ui/banner.png"},
                {"width": 448.0, "height": 160.0},
                slice_name="banner_main",
            )["success"]
        )
        self.api.game.save_current_scene()

        raw = json.loads(scene_path.read_text(encoding="utf-8"))
        banner = next(entity for entity in raw["entities"] if entity["name"] == "TitleBanner")
        payload = banner["components"]["UIImage"]

        self.assertEqual(payload["sprite"], {"guid": "", "path": "assets/ui/banner.png"})
        self.assertEqual(payload["slice_name"], "banner_main")
        self.assertTrue(payload["preserve_aspect"])

        ui_nodes = {entity["name"] for entity in self.api.list_ui_nodes()}
        self.assertEqual(ui_nodes, {"CanvasRoot", "TitleBanner"})

    def test_rect_transform_layout_scales_with_reference_resolution(self) -> None:
        scene_path = self._write_scene(
            "ui_layout.json",
            {
                "name": "UI Layout",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "PlayButton",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 280.0,
                                "height": 84.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIButton": {
                                "enabled": True,
                                "interactable": True,
                                "label": "Play",
                                "normal_color": [72, 72, 72, 255],
                                "hover_color": [92, 92, 92, 255],
                                "pressed_color": [56, 56, 56, 255],
                                "disabled_color": [48, 48, 48, 200],
                                "transition_scale_pressed": 0.96,
                                "on_click": {"type": "emit_event", "name": "ui.play_clicked"},
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._update_ui_overlay(self.api.game.world, (800.0, 600.0))
        base_layout = self.api.game._ui_system.get_entity_screen_rect("PlayButton")
        self.api.game._update_ui_overlay(self.api.game.world, (1600.0, 1200.0))
        scaled_layout = self.api.game._ui_system.get_entity_screen_rect("PlayButton")

        self.assertEqual(base_layout, {"x": 260.0, "y": 258.0, "width": 280.0, "height": 84.0})
        self.assertEqual(scaled_layout, {"x": 520.0, "y": 516.0, "width": 560.0, "height": 168.0})

    def test_vertical_stack_layout_applies_padding_spacing_and_layout_order(self) -> None:
        scene_path = self._write_scene(
            "ui_vertical_stack.json",
            {
                "name": "UI Vertical Stack",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": _rect_transform_payload(
                                anchor_min_x=0.0,
                                anchor_min_y=0.0,
                                anchor_max_x=1.0,
                                anchor_max_y=1.0,
                                pivot_x=0.0,
                                pivot_y=0.0,
                                width=0.0,
                                height=0.0,
                                layout_mode="vertical_stack",
                                layout_align="center",
                                padding_left=20.0,
                                padding_top=20.0,
                                padding_right=20.0,
                                padding_bottom=20.0,
                                spacing=10.0,
                            ),
                        },
                    },
                    {
                        "name": "Footer",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=200.0, height=40.0, layout_order=2),
                        },
                    },
                    {
                        "name": "Header",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=300.0, height=50.0, layout_order=0),
                        },
                    },
                    {
                        "name": "Content",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=400.0, height=80.0, layout_order=1),
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._update_ui_overlay(self.api.game.world, (800.0, 600.0))
        ui_system = self.api.game._ui_system

        self.assertEqual(ui_system.get_entity_screen_rect("Header"), {"x": 250.0, "y": 20.0, "width": 300.0, "height": 50.0})
        self.assertEqual(ui_system.get_entity_screen_rect("Content"), {"x": 200.0, "y": 80.0, "width": 400.0, "height": 80.0})
        self.assertEqual(ui_system.get_entity_screen_rect("Footer"), {"x": 300.0, "y": 170.0, "width": 200.0, "height": 40.0})

    def test_horizontal_stack_layout_distributes_stretch_space(self) -> None:
        scene_path = self._write_scene(
            "ui_horizontal_stack.json",
            {
                "name": "UI Horizontal Stack",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": _rect_transform_payload(
                                anchor_min_x=0.0,
                                anchor_min_y=0.0,
                                anchor_max_x=1.0,
                                anchor_max_y=1.0,
                                pivot_x=0.0,
                                pivot_y=0.0,
                                width=0.0,
                                height=0.0,
                                layout_mode="horizontal_stack",
                                layout_align="center",
                                padding_left=20.0,
                                padding_top=20.0,
                                padding_right=20.0,
                                padding_bottom=20.0,
                                spacing=10.0,
                            ),
                        },
                    },
                    {
                        "name": "Left",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=100.0, height=40.0),
                        },
                    },
                    {
                        "name": "CenterFill",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=50.0, height=80.0, size_mode_x="stretch"),
                        },
                    },
                    {
                        "name": "RightFillHeight",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=150.0, height=60.0, size_mode_y="stretch"),
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._update_ui_overlay(self.api.game.world, (800.0, 600.0))
        ui_system = self.api.game._ui_system

        self.assertEqual(ui_system.get_entity_screen_rect("Left"), {"x": 20.0, "y": 280.0, "width": 100.0, "height": 40.0})
        self.assertEqual(ui_system.get_entity_screen_rect("CenterFill"), {"x": 130.0, "y": 260.0, "width": 490.0, "height": 80.0})
        self.assertEqual(
            ui_system.get_entity_screen_rect("RightFillHeight"),
            {"x": 630.0, "y": 20.0, "width": 150.0, "height": 560.0},
        )

    def test_nested_stack_containers_resolve_descendant_layouts(self) -> None:
        scene_path = self._write_scene(
            "ui_nested_stacks.json",
            {
                "name": "UI Nested Stacks",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": _rect_transform_payload(
                                anchor_min_x=0.0,
                                anchor_min_y=0.0,
                                anchor_max_x=1.0,
                                anchor_max_y=1.0,
                                pivot_x=0.0,
                                pivot_y=0.0,
                                width=0.0,
                                height=0.0,
                                layout_mode="vertical_stack",
                                layout_align="stretch",
                                padding_left=20.0,
                                padding_top=20.0,
                                padding_right=20.0,
                                padding_bottom=20.0,
                                spacing=10.0,
                            ),
                        },
                    },
                    {
                        "name": "Panel",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(
                                width=500.0,
                                height=200.0,
                                size_mode_x="stretch",
                                layout_mode="horizontal_stack",
                                layout_align="stretch",
                                padding_left=10.0,
                                padding_top=10.0,
                                padding_right=10.0,
                                padding_bottom=10.0,
                                spacing=10.0,
                            ),
                        },
                    },
                    {
                        "name": "PanelLeft",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "Panel",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=100.0, height=40.0),
                        },
                    },
                    {
                        "name": "PanelRight",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "Panel",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=50.0, height=60.0, size_mode_x="stretch"),
                        },
                    },
                    {
                        "name": "Footer",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=300.0, height=50.0),
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._update_ui_overlay(self.api.game.world, (800.0, 600.0))
        ui_system = self.api.game._ui_system

        self.assertEqual(ui_system.get_entity_screen_rect("Panel"), {"x": 20.0, "y": 20.0, "width": 760.0, "height": 200.0})
        self.assertEqual(ui_system.get_entity_screen_rect("PanelLeft"), {"x": 30.0, "y": 30.0, "width": 100.0, "height": 180.0})
        self.assertEqual(ui_system.get_entity_screen_rect("PanelRight"), {"x": 140.0, "y": 30.0, "width": 630.0, "height": 180.0})
        self.assertEqual(ui_system.get_entity_screen_rect("Footer"), {"x": 20.0, "y": 230.0, "width": 760.0, "height": 50.0})

    def test_layout_ignore_keeps_legacy_position_inside_stack_container(self) -> None:
        scene_path = self._write_scene(
            "ui_layout_ignore.json",
            {
                "name": "UI Layout Ignore",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": _rect_transform_payload(
                                anchor_min_x=0.0,
                                anchor_min_y=0.0,
                                anchor_max_x=1.0,
                                anchor_max_y=1.0,
                                pivot_x=0.0,
                                pivot_y=0.0,
                                width=0.0,
                                height=0.0,
                                layout_mode="vertical_stack",
                                layout_align="start",
                                padding_left=20.0,
                                padding_top=20.0,
                                padding_right=20.0,
                                padding_bottom=20.0,
                                spacing=10.0,
                            ),
                        },
                    },
                    {
                        "name": "Header",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=300.0, height=50.0),
                        },
                    },
                    {
                        "name": "AbsoluteBadge",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(
                                anchor_min_x=1.0,
                                anchor_min_y=0.0,
                                anchor_max_x=1.0,
                                anchor_max_y=0.0,
                                pivot_x=1.0,
                                pivot_y=0.0,
                                anchored_x=-20.0,
                                anchored_y=20.0,
                                width=80.0,
                                height=40.0,
                                layout_ignore=True,
                            ),
                        },
                    },
                    {
                        "name": "Footer",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(width=300.0, height=50.0, layout_order=1),
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._update_ui_overlay(self.api.game.world, (800.0, 600.0))
        ui_system = self.api.game._ui_system

        self.assertEqual(ui_system.get_entity_screen_rect("Header"), {"x": 20.0, "y": 20.0, "width": 300.0, "height": 50.0})
        self.assertEqual(ui_system.get_entity_screen_rect("Footer"), {"x": 20.0, "y": 80.0, "width": 300.0, "height": 50.0})
        self.assertEqual(ui_system.get_entity_screen_rect("AbsoluteBadge"), {"x": 700.0, "y": 20.0, "width": 80.0, "height": 40.0})

    def test_rect_transform_roundtrip_preserves_layout_foundation_fields(self) -> None:
        scene_path = self._write_scene(
            "ui_layout_roundtrip.json",
            {
                "name": "UI Layout Roundtrip",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": _rect_transform_payload(
                                anchor_min_x=0.0,
                                anchor_min_y=0.0,
                                anchor_max_x=1.0,
                                anchor_max_y=1.0,
                                pivot_x=0.0,
                                pivot_y=0.0,
                                width=0.0,
                                height=0.0,
                            ),
                        },
                    },
                    {
                        "name": "Panel",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": _rect_transform_payload(
                                width=320.0,
                                height=180.0,
                                layout_mode="vertical_stack",
                                layout_order=3,
                                layout_ignore=True,
                                size_mode_x="stretch",
                                size_mode_y="fixed",
                                layout_align="end",
                                padding_left=4.0,
                                padding_top=6.0,
                                padding_right=8.0,
                                padding_bottom=10.0,
                                spacing=12.0,
                            ),
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game.save_current_scene()

        raw = json.loads(scene_path.read_text(encoding="utf-8"))
        panel = next(entity for entity in raw["entities"] if entity["name"] == "Panel")
        rect_payload = panel["components"]["RectTransform"]

        self.assertEqual(rect_payload["layout_mode"], "vertical_stack")
        self.assertEqual(rect_payload["layout_order"], 3)
        self.assertTrue(rect_payload["layout_ignore"])
        self.assertEqual(rect_payload["size_mode_x"], "stretch")
        self.assertEqual(rect_payload["size_mode_y"], "fixed")
        self.assertEqual(rect_payload["layout_align"], "end")
        self.assertEqual(rect_payload["padding_left"], 4.0)
        self.assertEqual(rect_payload["padding_top"], 6.0)
        self.assertEqual(rect_payload["padding_right"], 8.0)
        self.assertEqual(rect_payload["padding_bottom"], 10.0)
        self.assertEqual(rect_payload["spacing"], 12.0)

    def test_ui_hit_testing_prefers_rect_transform_nodes_over_canvas_root(self) -> None:
        scene_path = self._write_scene(
            "ui_hit_test.json",
            {
                "name": "UI Hit Test",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "Panel",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 200.0,
                                "height": 80.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        ui_system = self.api.game._ui_system
        world = self.api.game.world
        hit = ui_system.find_topmost_entity_at_point(world, 400.0, 300.0, (800.0, 600.0))
        self.assertIsNotNone(hit)
        self.assertEqual(hit.name, "Panel")

    def test_button_click_release_inside_fires_and_release_outside_does_not(self) -> None:
        scene_path = self._write_scene(
            "ui_interaction.json",
            {
                "name": "UI Interaction",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "PlayButton",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "CanvasRoot",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 280.0,
                                "height": 84.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIButton": {
                                "enabled": True,
                                "interactable": True,
                                "label": "Play",
                                "normal_color": [72, 72, 72, 255],
                                "hover_color": [92, 92, 92, 255],
                                "pressed_color": [56, 56, 56, 255],
                                "disabled_color": [48, 48, 48, 200],
                                "transition_scale_pressed": 0.96,
                                "on_click": {"type": "emit_event", "name": "ui.play_clicked"},
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertIn("ui.play_clicked", event_names)

        self.api.game._event_bus.clear_history()
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        self.api.game._ui_system.inject_pointer_state(40.0, 40.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=True)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertNotIn("ui.play_clicked", event_names)

    def test_ui_layout_cache_uses_ui_layout_version_for_cache_hits(self) -> None:
        scene_path = self._write_scene(
            "ui_layout_cache_hit.json",
            {
                "name": "UI Layout Cache Hit",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        world = self.api.game.world
        ui_system = self.api.game._ui_system
        with patch.object(world, "get_entities_with", wraps=world.get_entities_with) as get_entities_with:
            ui_system.update(world, (800.0, 600.0), allow_interaction=False)
            first_call_count = get_entities_with.call_count
            first_button_queries = sum(1 for args, _ in get_entities_with.call_args_list if args == (UIButton,))

            world.touch()
            ui_system.update(world, (800.0, 600.0), allow_interaction=False)

            self.assertEqual(get_entities_with.call_count, first_call_count)
            button_queries = sum(1 for args, _ in get_entities_with.call_args_list if args == (UIButton,))
            self.assertEqual(button_queries, first_button_queries)

    def test_rect_transform_change_invalidates_layout_cache(self) -> None:
        scene_path = self._write_scene(
            "ui_rect_transform_cache_invalidation.json",
            {
                "name": "UI RectTransform Cache Invalidation",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        world = self.api.game.world
        ui_system = self.api.game._ui_system
        ui_system.update(world, (800.0, 600.0), allow_interaction=False)
        base_layout = ui_system.get_entity_screen_rect("PlayButton")

        self.assertTrue(self.api.edit_component("PlayButton", "RectTransform", "width", 320.0)["success"])
        ui_system.update(world, (800.0, 600.0), allow_interaction=False)
        updated_layout = ui_system.get_entity_screen_rect("PlayButton")

        self.assertEqual(base_layout, {"x": 260.0, "y": 258.0, "width": 280.0, "height": 84.0})
        self.assertEqual(updated_layout, {"x": 240.0, "y": 258.0, "width": 320.0, "height": 84.0})

    def test_ui_button_update_still_fires_click(self) -> None:
        scene_path = self._write_scene(
            "ui_update_button_click.json",
            {
                "name": "UI Update Button Click",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        ui_system = self.api.game._ui_system
        world = self.api.game.world
        ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        ui_system.update(world, (800.0, 600.0), allow_interaction=True)
        ui_system.inject_pointer_state(400.0, 300.0, down=False, pressed=False, released=True)
        ui_system.update(world, (800.0, 600.0), allow_interaction=True)

        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertIn("ui.play_clicked", event_names)

    def test_ui_layout_cache_invalidates_on_viewport_change(self) -> None:
        scene_path = self._write_scene(
            "ui_viewport_cache_invalidation.json",
            {
                "name": "UI Viewport Cache Invalidation",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        ui_system = self.api.game._ui_system
        world = self.api.game.world
        ui_system.update(world, (800.0, 600.0), allow_interaction=False)
        base_layout = ui_system.get_entity_screen_rect("PlayButton")
        world.touch()
        ui_system.update(world, (1600.0, 1200.0), allow_interaction=False)
        scaled_layout = ui_system.get_entity_screen_rect("PlayButton")

        self.assertEqual(base_layout, {"x": 260.0, "y": 258.0, "width": 280.0, "height": 84.0})
        self.assertEqual(scaled_layout, {"x": 520.0, "y": 516.0, "width": 560.0, "height": 168.0})

    def test_button_does_not_fire_when_ui_overlay_is_updated_without_runtime_interaction(self) -> None:
        scene_path = self._write_scene(
            "ui_edit_blocked.json",
            {
                "name": "UI Edit Blocked",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=True, pressed=True, released=False)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=False)
        self.api.game._ui_system.inject_pointer_state(400.0, 300.0, down=False, pressed=False, released=True)
        self.api.game._ui_system.update(self.api.game.world, (800.0, 600.0), allow_interaction=False)

        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertNotIn("ui.play_clicked", event_names)

    def test_button_with_sprite_still_fires_declared_action(self) -> None:
        scene_path = self._write_scene(
            "ui_sprite_button_click.json",
            {
                "name": "UI Sprite Button Click",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
                normal_sprite={"path": "assets/ui/button_normal.png"},
            )["success"]
        )

        result = self.api.click_ui_button("PlayButton")

        self.assertTrue(result["success"])
        event_names = [event.name for event in self.api.game.event_bus.get_recent_events()]
        self.assertIn("ui.play_clicked", event_names)

    def test_scene_viewport_size_helper_uses_scene_texture_dimensions(self) -> None:
        self.api.game.editor_layout = SimpleNamespace(
            active_tab="SCENE",
            scene_texture=SimpleNamespace(texture=SimpleNamespace(width=320, height=180)),
            game_texture=SimpleNamespace(texture=SimpleNamespace(width=640, height=360)),
        )

        self.assertEqual(self.api.game._ui_viewport_size_for_tab("SCENE"), (320.0, 180.0))
        self.assertEqual(self.api.game._ui_viewport_size_for_tab("GAME"), (640.0, 360.0))

    def test_scene_without_canvas_remains_compatible(self) -> None:
        scene_path = self._write_scene(
            "plain_scene.json",
            {
                "name": "Plain Scene",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        self.api.step(1)

        self.assertEqual(self.api.list_ui_nodes(), [])
        self.assertEqual(self.api.get_ui_layout("Missing"), {})

    def test_non_interactable_button_blocks_click(self) -> None:
        scene_path = self._write_scene(
            "ui_disabled_button.json",
            {
                "name": "Disabled Button",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )
        self.assertTrue(self.api.edit_component("PlayButton", "UIButton", "interactable", False)["success"])

        result = self.api.click_ui_button("PlayButton")

        self.assertFalse(result["success"])
        self.assertEqual([event.name for event in self.api.game.event_bus.get_recent_events()], [])

    def test_cursor_intent_marks_enabled_button_as_interactive(self) -> None:
        scene_path = self._write_scene(
            "ui_cursor_enabled.json",
            {
                "name": "Cursor Enabled",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )

        intent = self.api.game._ui_system.get_cursor_intent(
            self.api.game.world,
            (800.0, 600.0),
            400.0,
            300.0,
            allow_interaction=True,
        )

        self.assertEqual(intent, CursorVisualState.INTERACTIVE)

    def test_cursor_intent_ignores_non_interactable_buttons(self) -> None:
        scene_path = self._write_scene(
            "ui_cursor_disabled.json",
            {
                "name": "Cursor Disabled",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())
        self.assertTrue(self.api.create_canvas(name="CanvasRoot")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "CanvasRoot",
                {"width": 280.0, "height": 84.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
            )["success"]
        )
        self.assertTrue(self.api.edit_component("PlayButton", "UIButton", "interactable", False)["success"])

        intent = self.api.game._ui_system.get_cursor_intent(self.api.game.world, (800.0, 600.0), 400.0, 300.0)

        self.assertEqual(intent, CursorVisualState.DEFAULT)

    def test_ui_render_system_resolve_button_visual_fallbacks(self) -> None:
        render_system = UIRenderSystem()
        button = UIButton(
            label="Play",
            normal_sprite={"path": "assets/ui/button_normal.png"},
            hover_sprite={"path": "assets/ui/button_hover.png"},
            normal_slice="idle",
            hover_slice="hover",
            image_tint=(250, 240, 230, 255),
        )

        hovered = render_system._resolve_button_visual(button, {"hovered": True, "pressed": False})
        self.assertEqual(hovered["asset_ref"], {"guid": "", "path": "assets/ui/button_hover.png"})
        self.assertEqual(hovered["slice_name"], "hover")

        pressed = render_system._resolve_button_visual(button, {"hovered": True, "pressed": True})
        self.assertEqual(pressed["asset_ref"], {"guid": "", "path": "assets/ui/button_hover.png"})
        self.assertEqual(pressed["slice_name"], "hover")

        disabled = render_system._resolve_button_visual(button, {"hovered": False, "pressed": False})
        self.assertEqual(disabled["asset_ref"], {"guid": "", "path": "assets/ui/button_normal.png"})

        button.interactable = False
        disabled = render_system._resolve_button_visual(button, {"hovered": False, "pressed": False})
        self.assertEqual(disabled["asset_ref"], {"guid": "", "path": "assets/ui/button_normal.png"})
        self.assertEqual(disabled["slice_name"], "idle")
        self.assertEqual(disabled["tint"], (175, 168, 161, 219))

    def test_real_main_menu_canvas_button_loads_platformer_scene(self) -> None:
        self._copy_real_scene("main_menu_scene.json")
        self._copy_real_scene("platformer_test_scene.json")

        self.api.load_level("levels/main_menu_scene.json")

        ui_nodes = {entity["name"] for entity in self.api.list_ui_nodes()}
        self.assertIn("MainCanvas", ui_nodes)
        self.assertIn("PlayButton", ui_nodes)

        result = self.api.click_ui_button("PlayButton")

        self.assertTrue(result["success"])
        self.assertEqual(self.api.scene_manager.scene_name, "Platformer Test Scene")
        self.assertTrue(self.api.game.current_scene_path.endswith("levels/platformer_test_scene.json"))

    def test_scene_view_ui_visibility_requires_play_or_selected_root_canvas(self) -> None:
        scene_path = self._write_scene(
            "ui_visibility.json",
            {
                "name": "UI Visibility",
                "entities": [
                    {
                        "name": "MainCanvas",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.0,
                                "anchor_min_y": 0.0,
                                "anchor_max_x": 1.0,
                                "anchor_max_y": 1.0,
                                "pivot_x": 0.0,
                                "pivot_y": 0.0,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 0.0,
                                "height": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                        },
                    },
                    {
                        "name": "TitleText",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "parent": "MainCanvas",
                        "components": {
                            "RectTransform": {
                                "enabled": True,
                                "anchor_min_x": 0.5,
                                "anchor_min_y": 0.5,
                                "anchor_max_x": 0.5,
                                "anchor_max_y": 0.5,
                                "pivot_x": 0.5,
                                "pivot_y": 0.5,
                                "anchored_x": 0.0,
                                "anchored_y": 0.0,
                                "width": 240.0,
                                "height": 64.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIText": {
                                "enabled": True,
                                "text": "Title",
                                "font_size": 24,
                                "color": [255, 255, 255, 255],
                                "alignment": "center",
                                "wrap": False,
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self.api.load_level(scene_path.as_posix())

        ui_system = self.api.game._ui_system
        world = self.api.game.world

        self.assertFalse(ui_system.should_render_scene_view_ui(world, allow_runtime=False))
        self.assertTrue(self.api.scene_manager.set_selected_entity("TitleText"))
        self.assertFalse(ui_system.should_render_scene_view_ui(world, allow_runtime=False))
        self.assertTrue(self.api.scene_manager.set_selected_entity("MainCanvas"))
        self.assertTrue(ui_system.should_render_scene_view_ui(world, allow_runtime=False))
        self.assertTrue(ui_system.should_render_scene_view_ui(world, allow_runtime=True))


if __name__ == "__main__":
    unittest.main()
