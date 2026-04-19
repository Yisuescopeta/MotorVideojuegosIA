import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyray as rl
from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI
from engine.components.recttransform import RectTransform
from engine.components.transform import Transform

MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xe2%\x9b"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class InspectorCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        demo_level = Path(__file__).resolve().parents[1] / "levels" / "demo_level.json"
        target_level = self.project_root / "levels" / "demo_level.json"
        target_level.parent.mkdir(parents=True, exist_ok=True)
        target_level.write_text(demo_level.read_text(encoding="utf-8"), encoding="utf-8")
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")
        self.inspector = self.api.game._inspector_system

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _create_probe(self, name: str, components: dict) -> None:
        result = self.api.create_entity(name, components=components)
        self.assertTrue(result["success"])

    def _write_scene(self, filename: str, payload: dict) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _write_png(self, relative_path: str) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MINIMAL_PNG_BYTES)
        return path

    def _target_scene_payload(self, scene_name: str, entry_points: list[tuple[str, str, float, float]]) -> dict:
        entities = [
            {
                "name": "Player",
                "active": True,
                "tag": "Player",
                "layer": "Default",
                "components": {
                    "Transform": {
                        "enabled": True,
                        "x": 16.0,
                        "y": 24.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    },
                    "PlayerController2D": {
                        "enabled": True,
                        "move_speed": 180.0,
                        "jump_velocity": -320.0,
                        "air_control": 0.75,
                    },
                },
            }
        ]
        for entry_id, label, x, y in entry_points:
            entities.append(
                {
                    "name": f"{entry_id.title()}Point",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": x,
                            "y": y,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        },
                        "SceneEntryPoint": {
                            "enabled": True,
                            "entry_id": entry_id,
                            "label": label,
                        },
                    },
                }
            )
        return {
            "schema_version": 2,
            "name": scene_name,
            "entities": entities,
            "rules": [],
            "feature_metadata": {},
        }

    def test_registry_covers_all_current_builtins(self) -> None:
        expected = {
            "Transform",
            "Sprite",
            "Collider",
            "RigidBody",
            "Animator",
            "Camera2D",
            "AudioSource",
            "InputMap",
            "PlayerController2D",
            "Tilemap",
            "ScriptBehaviour",
            "SceneEntryPoint",
        }
        self.assertTrue(expected.issubset(set(self.inspector.list_dedicated_editors())))

    def test_sprite_payload_edits_update_scene_and_support_undo_redo(self) -> None:
        self._create_probe(
            "InspectorSpriteProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Sprite": {
                    "enabled": True,
                    "texture_path": "assets/player.png",
                    "width": 32,
                    "height": 32,
                    "origin_x": 0.5,
                    "origin_y": 0.5,
                    "flip_x": False,
                    "flip_y": False,
                    "tint": [255, 255, 255, 255],
                },
            },
        )

        def update(payload: dict) -> None:
            payload["texture_path"] = "assets/player_alt.png"
            payload["tint"] = [128, 200, 255, 255]

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorSpriteProbe", "Sprite", update)
        self.assertTrue(success)

        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [128, 200, 255, 255])
        scene_sprite = self.api.scene_manager.current_scene.find_entity("InspectorSpriteProbe")["components"]["Sprite"]
        self.assertEqual(scene_sprite["tint"], [128, 200, 255, 255])

        self.assertTrue(self.api.undo()["success"])
        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [255, 255, 255, 255])

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [128, 200, 255, 255])

    def test_tilemap_payload_edits_update_scene_and_support_undo_redo(self) -> None:
        self._create_probe(
            "InspectorTilemapProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/base_tiles.png"},
                    "tileset_path": "assets/base_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": []}],
                },
            },
        )

        def update(payload: dict) -> None:
            payload["cell_width"] = 32
            payload["default_layer_name"] = "Gameplay"
            payload["layers"][0]["locked"] = True
            payload["layers"][0]["offset_x"] = 12.0

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorTilemapProbe", "Tilemap", update)
        self.assertTrue(success)

        tilemap = self.api.get_entity("InspectorTilemapProbe")["components"]["Tilemap"]
        self.assertEqual(tilemap["cell_width"], 32)
        self.assertEqual(tilemap["default_layer_name"], "Gameplay")
        self.assertEqual(tilemap["layers"][0]["locked"], True)
        self.assertEqual(tilemap["layers"][0]["offset_x"], 12.0)
        scene_tilemap = self.api.scene_manager.current_scene.find_entity("InspectorTilemapProbe")["components"]["Tilemap"]
        self.assertEqual(scene_tilemap["layers"][0]["locked"], True)

        self.assertTrue(self.api.undo()["success"])
        tilemap = self.api.get_entity("InspectorTilemapProbe")["components"]["Tilemap"]
        self.assertEqual(tilemap["cell_width"], 16)
        self.assertEqual(tilemap["default_layer_name"], "Ground")
        self.assertEqual(tilemap["layers"][0]["locked"], False)

        self.assertTrue(self.api.redo()["success"])
        tilemap = self.api.get_entity("InspectorTilemapProbe")["components"]["Tilemap"]
        self.assertEqual(tilemap["cell_width"], 32)
        self.assertEqual(tilemap["layers"][0]["offset_x"], 12.0)

    def test_tilemap_palette_prefers_layer_slices_and_falls_back_to_grid(self) -> None:
        self._write_png("assets/component_tiles.png")
        self._write_png("assets/layer_tiles.png")
        self._write_png("assets/grid_only.png")
        self.api.asset_service.generate_sprite_grid_slices("assets/layer_tiles.png", cell_width=1, cell_height=1, naming_prefix="layer")

        self._create_probe(
            "TilePaletteProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/component_tiles.png"},
                    "tileset_path": "assets/component_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tilemap_source": {"guid": "", "path": "assets/layer_tiles.png"}, "tiles": []}],
                },
            },
        )

        slice_options = self.inspector.list_tilemap_palette_options(self.api.game.world, "TilePaletteProbe", "Ground")
        self.assertEqual(slice_options, [("layer_0", "layer_0")])
        slice_entries = self.inspector.list_tilemap_palette_entries(self.api.game.world, "TilePaletteProbe", "Ground")
        self.assertEqual(slice_entries[0]["resolution"], "slice")
        self.assertEqual(slice_entries[0]["source_rect"], {"x": 0, "y": 0, "width": 1, "height": 1})
        self.assertTrue(slice_entries[0]["texture_path"].endswith("assets/layer_tiles.png"))
        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TilePaletteProbe", layer_name="Ground"))
        slice_state = self.inspector.get_tilemap_tool_state()
        self.assertEqual(slice_state["source"]["path"], "assets/layer_tiles.png")
        self.assertEqual(slice_state["tile_id"], "layer_0")

        self._create_probe(
            "TileGridProbe",
            {
                "Transform": {"enabled": True, "x": 10.0, "y": 20.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/grid_only.png"},
                    "tileset_path": "assets/grid_only.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Decor",
                    "layers": [{"name": "Decor", "offset_x": 32.0, "offset_y": 16.0, "tiles": []}],
                },
            },
        )
        grid_options = self.inspector.list_tilemap_palette_options(self.api.game.world, "TileGridProbe", "Decor")
        self.assertEqual(grid_options, [("0", "0")])
        grid_entries = self.inspector.list_tilemap_palette_entries(self.api.game.world, "TileGridProbe", "Decor")
        self.assertEqual(grid_entries[0]["resolution"], "grid")
        self.assertEqual(grid_entries[0]["source_rect"], {"x": 0, "y": 0, "width": 1, "height": 1})
        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileGridProbe", layer_name="Decor"))
        self.assertEqual(
            self.inspector.tilemap_world_to_cell(self.api.game.world, "TileGridProbe", 42.0, 36.0),
            (0, 0),
        )
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(42.0, 36.0), True)
        preview = self.inspector.get_tilemap_preview_snapshot(self.api.game.world)
        self.assertIsNotNone(preview)
        self.assertEqual(preview["resolution"], "grid")
        self.assertEqual(preview["cell"], (0, 0))
        self.assertTrue(preview["editable"])
        self.assertEqual(preview["cell_rect"], {"x": 42.0, "y": 36.0, "width": 16.0, "height": 16.0})

    def test_tilemap_brush_paints_drag_stroke_on_active_layer_with_single_undo(self) -> None:
        self._write_png("assets/brush_tiles.png")
        self._create_probe(
            "TileBrushProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/brush_tiles.png"},
                    "tileset_path": "assets/brush_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [
                        {"name": "Ground", "tiles": []},
                        {"name": "Decor", "tiles": []},
                    ],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileBrushProbe", layer_name="Decor"))
        self.assertTrue(self.inspector.set_tilemap_selected_tile(self.api.game.world, "TileBrushProbe", "0"))
        self.assertTrue(self.inspector.set_tilemap_tool_mode("paint"))

        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), False)
        tilemap = self.api.get_tilemap("TileBrushProbe")
        decor_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Decor")
        self.assertEqual(decor_layer["tiles"], [])

        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(24.0, 8.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(24.0, 8.0), True)

        tilemap = self.api.get_tilemap("TileBrushProbe")
        ground_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        decor_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Decor")
        self.assertEqual(ground_layer["tiles"], [])
        self.assertEqual(sorted((tile["x"], tile["y"]) for tile in decor_layer["tiles"]), [(0, 0), (1, 0)])

        self.assertTrue(self.api.undo()["success"])
        tilemap = self.api.get_tilemap("TileBrushProbe")
        decor_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Decor")
        self.assertEqual(decor_layer["tiles"], [])

        self.assertTrue(self.api.redo()["success"])
        tilemap = self.api.get_tilemap("TileBrushProbe")
        decor_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Decor")
        self.assertEqual(sorted((tile["x"], tile["y"]) for tile in decor_layer["tiles"]), [(0, 0), (1, 0)])

    def test_tilemap_brush_erase_supports_undo(self) -> None:
        self._write_png("assets/erase_tiles.png")
        self._create_probe(
            "TileEraseProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/erase_tiles.png"},
                    "tileset_path": "assets/erase_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "0", "source": {"guid": "", "path": "assets/erase_tiles.png"}, "flags": [], "tags": [], "custom": {}, "animated": False, "animation_id": "", "terrain_type": ""}]}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileEraseProbe", layer_name="Ground"))
        self.assertTrue(self.inspector.set_tilemap_tool_mode("erase"))

        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)

        tilemap = self.api.get_tilemap("TileEraseProbe")
        ground_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertEqual(ground_layer["tiles"], [])

        self.assertTrue(self.api.undo()["success"])
        tilemap = self.api.get_tilemap("TileEraseProbe")
        ground_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertEqual([(tile["x"], tile["y"]) for tile in ground_layer["tiles"]], [(0, 0)])

    def test_tilemap_preview_marks_hidden_layers_invalid_and_blocks_paint(self) -> None:
        self._write_png("assets/hidden_tiles.png")
        self._create_probe(
            "TileHiddenProbe",
            {
                "Transform": {"enabled": True, "x": 4.0, "y": 6.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/hidden_tiles.png"},
                    "tileset_path": "assets/hidden_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "visible": False, "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileHiddenProbe", layer_name="Ground"))
        self.assertTrue(self.inspector.set_tilemap_selected_tile(self.api.game.world, "TileHiddenProbe", "0"))
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(4.0, 6.0), True)
        preview = self.inspector.get_tilemap_preview_snapshot(self.api.game.world)
        self.assertIsNotNone(preview)
        self.assertEqual(preview["status"], "hidden")
        self.assertFalse(preview["editable"])

        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(4.0, 6.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(4.0, 6.0), True)

        tilemap = self.api.get_tilemap("TileHiddenProbe")
        ground_layer = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertEqual(ground_layer["tiles"], [])

    def test_tilemap_world_to_cell_applies_transform_rotation_scale_and_layer_offset(self) -> None:
        self._write_png("assets/transform_tiles.png")
        self._create_probe(
            "TileTransformProbe",
            {
                "Transform": {"enabled": True, "x": 10.0, "y": 20.0, "rotation": 90.0, "scale_x": 2.0, "scale_y": 3.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/transform_tiles.png"},
                    "tileset_path": "assets/transform_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "offset_x": 4.0, "offset_y": 5.0, "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileTransformProbe", layer_name="Ground"))
        self.assertEqual(self.inspector.tilemap_world_to_cell(self.api.game.world, "TileTransformProbe", -125.0, 76.0), (1, 2))
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(-125.0, 76.0), True)

        preview = self.inspector.get_tilemap_preview_snapshot(self.api.game.world)
        self.assertEqual(preview["cell"], (1, 2))
        self.assertEqual(preview["rotation"], 90.0)
        self.assertEqual(preview["scale"], {"x": 2.0, "y": 3.0})
        self.assertAlmostEqual(preview["cell_rect"]["x"], -101.0)
        self.assertAlmostEqual(preview["cell_rect"]["y"], 60.0)
        self.assertEqual((preview["cell_rect"]["width"], preview["cell_rect"]["height"]), (32.0, 48.0))
        self.assertAlmostEqual(preview["cell_corners"][0][0], -101.0)
        self.assertAlmostEqual(preview["cell_corners"][0][1], 60.0)

    def test_tilemap_zero_scale_is_not_editable(self) -> None:
        self._write_png("assets/zero_scale_tiles.png")
        self._create_probe(
            "TileZeroScaleProbe",
            {
                "Transform": {"enabled": True, "x": 10.0, "y": 20.0, "rotation": 0.0, "scale_x": 0.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/zero_scale_tiles.png"},
                    "tileset_path": "assets/zero_scale_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileZeroScaleProbe", layer_name="Ground"))
        self.assertIsNone(self.inspector.tilemap_world_to_cell(self.api.game.world, "TileZeroScaleProbe", 10.0, 20.0))
        preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileZeroScaleProbe", (0, 0))
        self.assertEqual(preview["status"], "invalid_transform")
        self.assertFalse(preview["editable"])

    def test_tilemap_negative_scale_mirrors_cell_preview_and_nonfinite_is_invalid(self) -> None:
        self._write_png("assets/mirror_tiles.png")
        self._create_probe(
            "TileMirrorProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": -1.0, "scale_y": -2.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/mirror_tiles.png"},
                    "tileset_path": "assets/mirror_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileMirrorProbe", layer_name="Ground"))
        self.assertEqual(self.inspector.tilemap_world_to_cell(self.api.game.world, "TileMirrorProbe", -24.0, -80.0), (1, 2))
        preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileMirrorProbe", (1, 2))
        self.assertEqual(preview["status"], "ok")
        self.assertTrue(preview["editable"])
        self.assertEqual(preview["scale"], {"x": -1.0, "y": -2.0})
        self.assertEqual((preview["cell_rect"]["x"], preview["cell_rect"]["y"]), (-32.0, -96.0))
        self.assertEqual((preview["cell_rect"]["width"], preview["cell_rect"]["height"]), (16.0, 32.0))
        self.assertEqual(preview["cell_corners"][0], (-16.0, -64.0))
        self.assertEqual((preview["source_rect"]["x"], preview["source_rect"]["y"]), (1.0, 1.0))
        self.assertEqual((preview["source_rect"]["width"], preview["source_rect"]["height"]), (-1.0, -1.0))

        transform = self.api.game.world.get_entity_by_name("TileMirrorProbe").get_component(Transform)
        transform.scale_x = math.inf
        invalid_preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileMirrorProbe", (1, 2))
        self.assertEqual(invalid_preview["status"], "invalid_transform")
        self.assertFalse(invalid_preview["editable"])

    def test_tilemap_keyboard_navigation_and_shortcuts_are_editor_only(self) -> None:
        self._write_png("assets/nav_tiles.png")
        self._create_probe(
            "TileNavProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/nav_tiles.png"},
                    "tileset_path": "assets/nav_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 4,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileNavProbe", layer_name="Ground"))

        def right_pressed(key: int) -> bool:
            return key == rl.KEY_RIGHT

        with patch("pyray.is_key_down", return_value=False), patch("pyray.is_key_pressed", side_effect=right_pressed):
            self.inspector.update(0.0, self.api.game.world, True)
        self.assertEqual(self.inspector.get_tilemap_tool_state()["palette_selected_index"], 1)

        enter_seen = False

        def enter_pressed(key: int) -> bool:
            nonlocal enter_seen
            if key == rl.KEY_ENTER and not enter_seen:
                enter_seen = True
                return True
            return False

        with patch("pyray.is_key_down", return_value=False), patch("pyray.is_key_pressed", side_effect=enter_pressed):
            self.inspector.update(0.0, self.api.game.world, True)
        self.assertEqual(self.inspector.get_tilemap_tool_state()["tile_id"], "1")

        def flood_shortcut(key: int) -> bool:
            return key == rl.KEY_G

        with patch("pyray.is_key_down", return_value=False), patch("pyray.is_key_pressed", side_effect=flood_shortcut):
            self.inspector.update(0.0, self.api.game.world, True)
        self.assertEqual(self.inspector.get_tilemap_tool_state()["mode"], "flood_fill")

        self.inspector.editing_text_field = "dummy"
        with patch("pyray.is_key_down", return_value=False), patch("pyray.is_key_pressed", side_effect=lambda key: key == rl.KEY_D):
            self.inspector.update(0.0, self.api.game.world, True)
        self.assertEqual(self.inspector.get_tilemap_tool_state()["mode"], "flood_fill")
        self.inspector.editing_text_field = None

        with patch("pyray.is_key_down", side_effect=lambda key: key == rl.KEY_LEFT_SHIFT), patch("pyray.is_key_pressed", return_value=False):
            self.inspector.update(0.0, self.api.game.world, True)
            self.assertEqual(self.inspector.get_tilemap_tool_state()["effective_mode"], "erase")

    def test_tilemap_activation_resets_palette_selection_when_switching_entities(self) -> None:
        self._write_png("assets/switch_tiles.png")
        tilemap_components = {
            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            "Tilemap": {
                "enabled": True,
                "cell_width": 16,
                "cell_height": 16,
                "orientation": "orthogonal",
                "tileset": {"guid": "", "path": "assets/switch_tiles.png"},
                "tileset_path": "assets/switch_tiles.png",
                "tileset_tile_width": 1,
                "tileset_tile_height": 1,
                "tileset_columns": 4,
                "tileset_spacing": 0,
                "tileset_margin": 0,
                "default_layer_name": "Ground",
                "layers": [{"name": "Ground", "tiles": []}],
            },
        }
        self._create_probe("TileSwitchA", tilemap_components)
        self._create_probe("TileSwitchB", tilemap_components)

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileSwitchA", layer_name="Ground"))
        self.assertTrue(self.inspector.set_tilemap_selected_tile(self.api.game.world, "TileSwitchA", "2"))
        self.assertEqual(self.inspector.get_tilemap_tool_state()["palette_selected_index"], 2)

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileSwitchB", layer_name="Ground"))
        state = self.inspector.get_tilemap_tool_state()
        self.assertEqual(state["tile_id"], "0")
        self.assertEqual(state["palette_selected_index"], 0)

    def test_tilemap_pick_box_fill_flood_fill_and_stamp_are_transactional(self) -> None:
        self._write_png("assets/tool_tiles.png")
        self.api.asset_service.generate_sprite_grid_slices("assets/tool_tiles.png", cell_width=1, cell_height=1, naming_prefix="tool")
        self._create_probe(
            "TileToolsProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/tool_tiles.png"},
                    "tileset_path": "assets/tool_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [
                        {
                            "name": "Ground",
                            "tiles": [
                                {"x": 0, "y": 0, "tile_id": "0", "source": {"guid": "", "path": "assets/tool_tiles.png"}, "flags": [], "tags": [], "custom": {}, "animated": False, "animation_id": "", "terrain_type": ""},
                                {"x": 1, "y": 0, "tile_id": "1", "source": {"guid": "", "path": "assets/tool_tiles.png"}, "flags": [], "tags": [], "custom": {}, "animated": False, "animation_id": "", "terrain_type": ""},
                            ],
                        }
                    ],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileToolsProbe", layer_name="Ground"))
        self.assertTrue(self.inspector.set_tilemap_tool_mode("pick"))
        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)
        self.assertEqual(self.inspector.get_tilemap_tool_state()["tile_id"], "0")
        self.assertEqual(self.inspector.get_tilemap_tool_state()["mode"], "paint")

        self.assertTrue(self.inspector.set_tilemap_tool_mode("box_fill"))
        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(0.0, 16.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(16.0, 32.0), True)
        tilemap = self.api.get_tilemap("TileToolsProbe")
        ground = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertTrue({(0, 1), (1, 1), (0, 2), (1, 2)}.issubset({(tile["x"], tile["y"]) for tile in ground["tiles"]}))
        self.assertTrue(self.api.undo()["success"])
        self.assertTrue(self.api.redo()["success"])

        self.assertTrue(self.inspector.set_tilemap_selected_tile(self.api.game.world, "TileToolsProbe", "tool_0"))
        self.assertTrue(self.inspector.set_tilemap_tool_mode("flood_fill"))
        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)
        tilemap = self.api.get_tilemap("TileToolsProbe")
        ground = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertEqual(next(tile for tile in ground["tiles"] if tile["x"] == 0 and tile["y"] == 0)["tile_id"], "tool_0")

        self.assertTrue(self.inspector.set_tilemap_tool_mode("pick"))
        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(8.0, 8.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(24.0, 8.0), True)
        self.assertEqual(self.inspector.get_tilemap_tool_state()["mode"], "stamp")
        self.assertGreaterEqual(len(self.inspector.get_tilemap_tool_state()["stamp_tiles"]), 2)

        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(48.0, 0.0), True)
        with patch("pyray.is_mouse_button_pressed", return_value=False), patch("pyray.is_mouse_button_down", return_value=False), patch(
            "pyray.is_mouse_button_released",
            return_value=True,
        ):
            self.inspector.handle_tilemap_scene_input(self.api.game.world, rl.Vector2(48.0, 0.0), True)
        tilemap = self.api.get_tilemap("TileToolsProbe")
        ground = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertTrue({(3, 0), (4, 0)}.issubset({(tile["x"], tile["y"]) for tile in ground["tiles"]}))

    def test_tilemap_stamp_preview_resolves_each_tile_and_blocks_invalid_stamp(self) -> None:
        self._write_png("assets/stamp_preview_tiles.png")
        tile_payload = {
            "source": {"guid": "", "path": "assets/stamp_preview_tiles.png"},
            "flags": [],
            "tags": [],
            "custom": {},
            "animated": False,
            "animation_id": "",
            "terrain_type": "",
        }
        self._create_probe(
            "TileStampPreviewProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/stamp_preview_tiles.png"},
                    "tileset_path": "assets/stamp_preview_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 2,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [
                        {
                            "name": "Ground",
                            "tiles": [
                                {"x": 0, "y": 0, "tile_id": "0", **tile_payload},
                                {"x": 1, "y": 0, "tile_id": "1", **tile_payload},
                                {"x": 0, "y": 1, "tile_id": "2", **tile_payload},
                                {"x": 1, "y": 1, "tile_id": "3", **tile_payload},
                            ],
                        }
                    ],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileStampPreviewProbe", layer_name="Ground"))
        self.assertTrue(self.inspector._set_tilemap_stamp_from_scene(self.api.game.world, "TileStampPreviewProbe", (0, 0), (1, 1)))
        preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileStampPreviewProbe", (3, 3))
        self.assertTrue(preview["editable"])
        self.assertEqual(len(preview["preview_tiles"]), 4)
        self.assertEqual([tile["cell"] for tile in preview["preview_tiles"]], [(3, 3), (4, 3), (3, 4), (4, 4)])
        self.assertTrue(all(tile["status"] == "ok" for tile in preview["preview_tiles"]))

        self.inspector._tilemap_authoring.stamp_tiles[1]["tile_id"] = "missing"
        invalid_preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileStampPreviewProbe", (3, 3))
        self.assertFalse(invalid_preview["editable"])
        self.assertEqual(invalid_preview["preview_tiles"][1]["status"], "unresolved_tile")
        self.assertFalse(self.inspector._apply_tilemap_brush(self.api.game.world, "TileStampPreviewProbe", (3, 3)))
        tilemap = self.api.get_tilemap("TileStampPreviewProbe")
        ground = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertNotIn((3, 3), {(tile["x"], tile["y"]) for tile in ground["tiles"]})

    def test_tilemap_stamp_preview_uses_per_tile_source_without_global_tileset(self) -> None:
        self._write_png("assets/stamp_source_override_tiles.png")
        self._create_probe(
            "TileStampSourceProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": ""},
                    "tileset_path": "",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 2,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileStampSourceProbe", layer_name="Ground"))
        self.assertTrue(self.inspector.set_tilemap_tool_mode("stamp"))
        self.inspector._tilemap_authoring.stamp_tiles = [
            {"offset_x": 0, "offset_y": 0, "tile_id": "0", "source": {"guid": "", "path": "assets/stamp_source_override_tiles.png"}},
            {"offset_x": 1, "offset_y": 0, "tile_id": "1", "source": {"guid": "", "path": "assets/stamp_source_override_tiles.png"}},
        ]
        preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileStampSourceProbe", (0, 0))
        self.assertEqual(preview["status"], "ok")
        self.assertTrue(preview["editable"])
        self.assertEqual([tile["status"] for tile in preview["preview_tiles"]], ["ok", "ok"])
        self.assertEqual([tile["source"]["path"] for tile in preview["preview_tiles"]], ["assets/stamp_source_override_tiles.png", "assets/stamp_source_override_tiles.png"])

        self.inspector._tilemap_authoring.stamp_tiles[1]["source"] = {"guid": "", "path": ""}
        invalid_preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileStampSourceProbe", (0, 0))
        self.assertFalse(invalid_preview["editable"])
        self.assertEqual(invalid_preview["preview_tiles"][1]["status"], "missing_source")
        self.assertFalse(self.inspector._apply_tilemap_brush(self.api.game.world, "TileStampSourceProbe", (0, 0)))
        tilemap = self.api.get_tilemap("TileStampSourceProbe")
        ground = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertEqual(ground["tiles"], [])

    def test_tilemap_flood_fill_uses_explicit_bounds_and_reports_truncation(self) -> None:
        self._write_png("assets/flood_bounds_tiles.png")
        self._create_probe(
            "TileFloodBoundsProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Tilemap": {
                    "enabled": True,
                    "cell_width": 16,
                    "cell_height": 16,
                    "orientation": "orthogonal",
                    "tileset": {"guid": "", "path": "assets/flood_bounds_tiles.png"},
                    "tileset_path": "assets/flood_bounds_tiles.png",
                    "tileset_tile_width": 1,
                    "tileset_tile_height": 1,
                    "tileset_columns": 1,
                    "tileset_spacing": 0,
                    "tileset_margin": 0,
                    "default_layer_name": "Ground",
                    "layers": [{"name": "Ground", "tiles": []}],
                },
            },
        )

        self.assertTrue(self.inspector.activate_tilemap_tool(self.api.game.world, "TileFloodBoundsProbe", layer_name="Ground"))
        self.assertTrue(self.inspector.set_tilemap_selected_tile(self.api.game.world, "TileFloodBoundsProbe", "0"))
        self.assertTrue(self.inspector.set_tilemap_tool_mode("flood_fill"))
        auto_preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileFloodBoundsProbe", (0, 0))
        self.assertEqual(auto_preview["flood_bounds"], (-8, -8, 7, 7))
        self.assertEqual(auto_preview["flood_preview_count"], 256)
        self.assertFalse(auto_preview["flood_truncated"])

        self.assertTrue(self.inspector.set_tilemap_flood_bounds(mode="manual", min_x=0, min_y=0, max_x=2, max_y=2, max_cells=4))
        manual_preview = self.inspector._build_tilemap_preview_snapshot(self.api.game.world, "TileFloodBoundsProbe", (1, 1))
        self.assertEqual(manual_preview["flood_bounds"], (0, 0, 2, 2))
        self.assertEqual(manual_preview["flood_preview_count"], 4)
        self.assertTrue(manual_preview["flood_truncated"])
        self.assertEqual(self.inspector.get_tilemap_tool_state()["flood_preview_count"], 4)
        self.assertTrue(self.inspector._apply_tilemap_flood_fill(self.api.game.world, "TileFloodBoundsProbe", (1, 1)))
        tilemap = self.api.get_tilemap("TileFloodBoundsProbe")
        ground = next(layer for layer in tilemap["layers"] if layer["name"] == "Ground")
        self.assertEqual(len(ground["tiles"]), 4)
        self.assertTrue({(0, 1), (1, 1)}.issubset({(tile["x"], tile["y"]) for tile in ground["tiles"]}))

    def test_animator_payload_edits_use_serializable_source_and_history(self) -> None:
        self._create_probe(
            "InspectorAnimatorProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Animator": {
                    "enabled": True,
                    "sprite_sheet": "assets/player_sheet.png",
                    "frame_width": 32,
                    "frame_height": 32,
                    "animations": {
                        "idle": {
                            "frames": [0, 1],
                            "slice_names": ["idle_0", "idle_1"],
                            "fps": 8.0,
                            "loop": True,
                            "on_complete": None,
                        }
                    },
                    "default_state": "idle",
                    "current_state": "idle",
                    "current_frame": 0,
                    "is_finished": False,
                },
            },
        )

        def update(payload: dict) -> None:
            payload["default_state"] = "run"
            payload["animations"]["run"] = {
                "frames": [2, 3, 4],
                "slice_names": ["run_0", "run_1", "run_2"],
                "fps": 12.0,
                "loop": True,
                "on_complete": None,
            }

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorAnimatorProbe", "Animator", update)
        self.assertTrue(success)

        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "run")
        self.assertEqual(animator["animations"]["run"]["slice_names"], ["run_0", "run_1", "run_2"])
        scene_animator = self.api.scene_manager.current_scene.find_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertIn("run", scene_animator["animations"])

        self.assertTrue(self.api.undo()["success"])
        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "idle")
        self.assertNotIn("run", animator["animations"])

        self.assertTrue(self.api.redo()["success"])
        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "run")
        self.assertIn("run", animator["animations"])

    def test_script_behaviour_payload_edits_use_common_route_and_history(self) -> None:
        self._create_probe(
            "InspectorScriptProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "ScriptBehaviour": {
                    "enabled": True,
                    "module_path": "platformer_character",
                    "run_in_edit_mode": False,
                    "public_data": {"health": 3, "coins": 0},
                },
            },
        )

        def update(payload: dict) -> None:
            payload["module_path"] = "enemy_brain"
            payload["public_data"] = {"health": 5, "coins": 2, "alive": True}

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorScriptProbe", "ScriptBehaviour", update)
        self.assertTrue(success)

        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "enemy_brain")
        self.assertEqual(script_data["public_data"], {"health": 5, "coins": 2, "alive": True})
        scene_script = self.api.scene_manager.current_scene.find_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(scene_script["public_data"]["coins"], 2)

        self.assertTrue(self.api.undo()["success"])
        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "platformer_character")
        self.assertEqual(script_data["public_data"], {"health": 3, "coins": 0})

        self.assertTrue(self.api.redo()["success"])
        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "enemy_brain")
        self.assertEqual(script_data["public_data"]["alive"], True)

    def test_transform_editor_uses_serializable_local_values_for_child_entity(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorParent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 200.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "InspectorParent",
                "InspectorChild",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 15.0, "scale_x": 1.5, "scale_y": 0.75}},
            )["success"]
        )

        child = self.api.game.world.get_entity_by_name("InspectorChild")
        transform = child.get_component(Transform)
        rendered_values: dict[str, float | bool] = {}

        def capture(label, value, *args, **kwargs):
            rendered_values[label] = value
            return args[4] + 1

        with patch.object(self.inspector, "_draw_component_field", side_effect=capture):
            self.inspector._draw_transform_editor(transform, child.id, 0, 0, 240, True, self.api.game.world)

        self.assertEqual(rendered_values["X"], 12.0)
        self.assertEqual(rendered_values["Y"], 8.0)
        self.assertEqual(rendered_values["Rotation"], 15.0)
        self.assertEqual(rendered_values["Scale X"], 1.5)
        self.assertEqual(rendered_values["Scale Y"], 0.75)

    def test_inspector_transform_edit_persists_local_transform_after_save_and_reload(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorParent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 50.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "InspectorParent",
                "InspectorChild",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(self.api.scene_manager.set_selected_entity("InspectorChild"))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorChild", "Transform", "x", 30.0))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorChild", "Transform", "y", 40.0))

        child_data = self.api.scene_manager.current_scene.find_entity("InspectorChild")
        self.assertEqual(child_data["components"]["Transform"]["x"], 30.0)
        self.assertEqual(child_data["components"]["Transform"]["y"], 40.0)
        self.assertEqual(self.api.game.world.selected_entity_name, "InspectorChild")

        save_path = self.project_root / "levels" / "inspector_transform_scene.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        child = self.api.game.world.get_entity_by_name("InspectorChild")
        transform = child.get_component(Transform)
        self.assertEqual(transform.local_x, 30.0)
        self.assertEqual(transform.local_y, 40.0)
        self.assertEqual(transform.x, 130.0)
        self.assertEqual(transform.y, 90.0)

    def test_component_fold_state_survives_transform_commit_rebuild(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorFoldProbe",
                {"Transform": {"enabled": True, "x": 12.0, "y": 24.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )

        before_entity = self.api.game.world.get_entity_by_name("InspectorFoldProbe")
        expansion_key = self.inspector._component_expansion_key("InspectorFoldProbe", "Transform")
        self.inspector.expanded_components.add(expansion_key)

        self.assertTrue(
            self.inspector._apply_component_property(self.api.game.world, "InspectorFoldProbe", "Transform", "x", 99.0)
        )

        after_entity = self.api.game.world.get_entity_by_name("InspectorFoldProbe")
        self.assertNotEqual(before_entity.id, after_entity.id)
        self.assertIn(expansion_key, self.inspector.expanded_components)
        self.assertEqual(after_entity.get_component(Transform).x, 99.0)

    def test_component_fold_state_survives_rect_transform_commit_rebuild(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorRectProbe",
                {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RectTransform": {
                        "enabled": True,
                        "anchored_x": 0.0,
                        "anchored_y": 0.0,
                        "width": 160.0,
                        "height": 90.0,
                        "rotation": 0.0,
                        "scale_x": 1.0,
                        "scale_y": 1.0,
                    },
                },
            )["success"]
        )

        before_entity = self.api.game.world.get_entity_by_name("InspectorRectProbe")
        expansion_key = self.inspector._component_expansion_key("InspectorRectProbe", "RectTransform")
        self.inspector.expanded_components.add(expansion_key)

        self.assertTrue(
            self.inspector._apply_component_property(
                self.api.game.world,
                "InspectorRectProbe",
                "RectTransform",
                "width",
                220.0,
            )
        )

        after_entity = self.api.game.world.get_entity_by_name("InspectorRectProbe")
        self.assertNotEqual(before_entity.id, after_entity.id)
        self.assertIn(expansion_key, self.inspector.expanded_components)
        self.assertEqual(after_entity.get_component(RectTransform).width, 220.0)

    def test_inspector_rect_transform_edit_persists_after_save_and_reload(self) -> None:
        self._create_probe(
            "InspectorButton",
            {
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
                }
            },
        )

        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorButton", "RectTransform", "anchored_x", 32.0))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorButton", "RectTransform", "height", 96.0))

        button_data = self.api.scene_manager.current_scene.find_entity("InspectorButton")
        self.assertEqual(button_data["components"]["RectTransform"]["anchored_x"], 32.0)
        self.assertEqual(button_data["components"]["RectTransform"]["height"], 96.0)

        save_path = self.project_root / "levels" / "inspector_rect_scene.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        button = self.api.game.world.get_entity_by_name("InspectorButton")
        rect_transform = button.get_component(RectTransform)
        self.assertEqual(rect_transform.anchored_x, 32.0)
        self.assertEqual(rect_transform.height, 96.0)

    def test_inspector_scene_transition_ui_button_persists_and_supports_undo_redo(self) -> None:
        self._write_scene(
            "transition_target.json",
            self._target_scene_payload("Transition Target", [("arrival", "Arrival", 192.0, 144.0)]),
        )
        self._create_probe(
            "PortalButton",
            {
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
                    "width": 220.0,
                    "height": 64.0,
                    "rotation": 0.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                },
                "UIButton": {
                    "enabled": True,
                    "interactable": True,
                    "label": "Go",
                    "normal_color": [72, 72, 72, 255],
                    "hover_color": [92, 92, 92, 255],
                    "pressed_color": [56, 56, 56, 255],
                    "disabled_color": [48, 48, 48, 200],
                    "transition_scale_pressed": 0.96,
                    "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                },
            },
        )

        self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "PortalButton", "ui_button"))
        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "PortalButton",
                "levels/transition_target.json",
            )
        )
        self.assertTrue(self.inspector._set_scene_transition_target_spawn(self.api.game.world, "PortalButton", "arrival"))

        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["UIButton"]["on_click"]["type"], "run_scene_transition")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_scene_path"], "levels/transition_target.json")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")

        self.assertTrue(self.api.undo()["success"])
        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "")

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")

        save_path = self.project_root / "levels" / "inspector_transition_saved.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        entity = self.api.get_entity("PortalButton")
        self.assertEqual(entity["components"]["UIButton"]["on_click"]["type"], "run_scene_transition")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_scene_path"], "levels/transition_target.json")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")

    def test_inspector_scene_transition_trigger_presets_materialize_expected_components(self) -> None:
        self._create_probe(
            "TransitionProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Collider": {
                    "enabled": True,
                    "width": 32.0,
                    "height": 32.0,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "is_trigger": True,
                },
                "UIButton": {
                    "enabled": True,
                    "interactable": True,
                    "label": "Go",
                    "normal_color": [72, 72, 72, 255],
                    "hover_color": [92, 92, 92, 255],
                    "pressed_color": [56, 56, 56, 255],
                    "disabled_color": [48, 48, 48, 200],
                    "transition_scale_pressed": 0.96,
                    "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                },
            },
        )

        for preset, component_name, mode in (
            ("interact_near", "SceneTransitionOnInteract", None),
            ("trigger_enter", "SceneTransitionOnContact", "trigger_enter"),
            ("collision", "SceneTransitionOnContact", "collision"),
            ("player_death", "SceneTransitionOnPlayerDeath", None),
        ):
            with self.subTest(preset=preset):
                self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "TransitionProbe", preset))
                components = self.api.get_entity("TransitionProbe")["components"]
                self.assertIn("SceneTransitionAction", components)
                self.assertIn(component_name, components)
                if mode is not None:
                    self.assertEqual(components["SceneTransitionOnContact"]["mode"], mode)
                trigger_count = sum(
                    1
                    for trigger_name in (
                        "SceneTransitionOnContact",
                        "SceneTransitionOnInteract",
                        "SceneTransitionOnPlayerDeath",
                    )
                    if trigger_name in components
                )
                self.assertEqual(trigger_count, 1)

    def test_scene_transition_target_scene_change_refreshes_spawn_options_and_clears_invalid_spawn(self) -> None:
        self._write_scene(
            "transition_target_a.json",
            self._target_scene_payload("Transition A", [("arrival", "Arrival", 100.0, 100.0)]),
        )
        self._write_scene(
            "transition_target_b.json",
            self._target_scene_payload("Transition B", [("exit", "Exit", 240.0, 140.0)]),
        )
        self._create_probe(
            "Portal",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            },
        )

        self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "Portal", "collision"))
        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "Portal",
                "levels/transition_target_a.json",
            )
        )
        self.assertTrue(self.inspector._set_scene_transition_target_spawn(self.api.game.world, "Portal", "arrival"))

        spawn_options = self.inspector._get_scene_transition_spawn_options(self.api.game.world, "Portal")
        self.assertIn(("arrival", "Arrival (ArrivalPoint)"), spawn_options)

        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "Portal",
                "levels/transition_target_b.json",
            )
        )

        entity = self.api.get_entity("Portal")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "")
        spawn_options = self.inspector._get_scene_transition_spawn_options(self.api.game.world, "Portal")
        self.assertIn(("exit", "Exit (ExitPoint)"), spawn_options)
        self.assertFalse(any(key == "arrival" for key, _ in spawn_options))

    def test_scene_transition_validation_messages_cover_invalid_scene_spawn_and_player_death_warning(self) -> None:
        self._write_scene(
            "transition_target_valid.json",
            self._target_scene_payload("Transition Valid", [("arrival", "Arrival", 96.0, 64.0)]),
        )
        self._create_probe(
            "InteractPortal",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            },
        )

        self.assertTrue(self.inspector._set_scene_transition_preset(self.api.game.world, "InteractPortal", "player_death"))
        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "InteractPortal",
                "levels/missing_scene.json",
            )
        )
        messages = self.inspector._get_scene_transition_validation_messages(self.api.game.world, "InteractPortal")
        self.assertTrue(any("player-like entity" in message for _, message in messages))
        self.assertTrue(any("does not exist" in message for _, message in messages))

        self.assertTrue(
            self.inspector._set_scene_transition_target_scene(
                self.api.game.world,
                "InteractPortal",
                "levels/transition_target_valid.json",
            )
        )
        self.assertTrue(self.inspector._set_scene_transition_target_spawn(self.api.game.world, "InteractPortal", "ghost"))
        messages = self.inspector._get_scene_transition_validation_messages(self.api.game.world, "InteractPortal")
        self.assertTrue(any("player-like entity" in message for _, message in messages))
        self.assertTrue(any("ghost" in message for _, message in messages))

    def test_script_executor_exposes_undo_redo_commands(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [
            {"action": "INSPECT_EDIT", "args": {"entity": "Ground", "component": "Transform", "property": "x", "value": 700.0}},
            {"action": "UNDO", "args": {}},
            {"action": "REDO", "args": {}},
        ]

        self.assertTrue(executor.run_all())
        ground = self.api.get_entity("Ground")
        self.assertEqual(ground["components"]["Transform"]["x"], 700.0)

    def test_scene_link_mode_syncs_runtime_button_transition(self) -> None:
        self._create_probe(
            "FlowButton",
            {
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
                    "width": 220.0,
                    "height": 72.0,
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
                    "on_click": {"type": "emit_event", "name": "ui.button_clicked"},
                },
                "SceneLink": {
                    "enabled": True,
                    "target_path": "levels/demo_level.json",
                    "flow_key": "",
                    "preview_label": "Demo",
                    "link_mode": "",
                    "target_entry_id": "",
                },
            },
        )

        self.assertTrue(self.inspector._set_scene_link_mode(self.api.game.world, "FlowButton", "ui_button"))
        entity = self.api.get_entity("FlowButton")
        self.assertEqual(entity["components"]["SceneLink"]["link_mode"], "ui_button")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_scene_path"], "levels/demo_level.json")
        self.assertEqual(entity["components"]["UIButton"]["on_click"]["type"], "run_scene_transition")

    def test_scene_link_target_spawn_updates_runtime_transition(self) -> None:
        self._write_scene(
            "flow_target.json",
            self._target_scene_payload("FlowTarget", [("arrival", "Arrival", 48.0, 64.0)]),
        )
        self._create_probe(
            "PortalFlow",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Collider": {
                    "enabled": True,
                    "width": 32.0,
                    "height": 32.0,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "is_trigger": True,
                },
                "SceneLink": {
                    "enabled": True,
                    "target_path": "levels/flow_target.json",
                    "flow_key": "",
                    "preview_label": "Target",
                    "link_mode": "trigger_enter",
                    "target_entry_id": "",
                },
            },
        )

        self.assertTrue(self.inspector._sync_scene_link_runtime(self.api.game.world, "PortalFlow"))
        self.assertTrue(self.inspector._set_scene_link_target_spawn(self.api.game.world, "PortalFlow", "arrival"))
        entity = self.api.get_entity("PortalFlow")
        self.assertEqual(entity["components"]["SceneLink"]["target_entry_id"], "arrival")
        self.assertEqual(entity["components"]["SceneTransitionAction"]["target_entry_id"], "arrival")
        self.assertEqual(entity["components"]["SceneTransitionOnContact"]["mode"], "trigger_enter")


if __name__ == "__main__":
    unittest.main()
