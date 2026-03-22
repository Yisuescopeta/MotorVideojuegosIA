import os
import sys
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

import pyray as rl

from engine.api import EngineAPI
from engine.editor.animator_panel import expand_slice_sequence
from engine.editor.project_panel import ProjectPanel


MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc```\xf8\x0f\x00\x01\x04\x01\x00"
    b"\x18\xdd\x8d\xb1"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class AnimatorPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = EngineAPI()
        self.api.load_level("levels/demo_level.json")
        self.panel = self.api.game.animator_panel
        self.modal = self.api.game.sprite_editor_modal
        self._temp_files: list[Path] = []
        self._temp_dirs: list[Path] = []

    def tearDown(self) -> None:
        self.api.shutdown()
        for path in reversed(self._temp_files):
            if path.exists():
                path.unlink()
        for path in reversed(self._temp_dirs):
            if path.exists():
                path.rmdir()

    def _write_temp_png(self, relative_path: str) -> str:
        file_path = Path(relative_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(MINIMAL_PNG_BYTES)
        self._temp_files.append(file_path)
        return file_path.as_posix()

    def _write_sheet_with_slices(self, relative_path: str, slice_names: list[str]) -> str:
        asset_path = self._write_temp_png(relative_path)
        metadata_path = Path(f"{asset_path}.meta.json")
        self._temp_files.append(metadata_path)
        result = self.api.save_asset_metadata(
            asset_path,
            {
                "asset_type": "sprite_sheet",
                "import_mode": "grid",
                "grid": {"cell_width": 1, "cell_height": 1, "margin": 0, "spacing": 0},
                "slices": [
                    {
                        "name": name,
                        "x": index,
                        "y": 0,
                        "width": 1,
                        "height": 1,
                        "pivot_x": 0.5,
                        "pivot_y": 0.5,
                    }
                    for index, name in enumerate(slice_names)
                ],
            },
        )
        self.assertTrue(result["success"])
        return asset_path

    def _write_auto_slice_png(self, relative_path: str) -> str:
        asset_path = Path(relative_path)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        self._temp_dirs.append(asset_path.parent)
        image = rl.gen_image_color(6, 3, rl.BLANK)
        rl.image_draw_rectangle(image, 0, 0, 2, 3, rl.RED)
        rl.image_draw_rectangle(image, 4, 0, 2, 3, rl.BLUE)
        self.assertTrue(rl.export_image(image, asset_path.as_posix()))
        rl.unload_image(image)
        self._temp_files.append(asset_path)
        return asset_path.as_posix()

    def _write_opaque_background_sheet(self, relative_path: str) -> str:
        asset_path = Path(relative_path)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        self._temp_dirs.append(asset_path.parent)
        image = rl.gen_image_color(10, 4, rl.Color(254, 254, 254, 255))
        rl.image_draw_rectangle(image, 1, 1, 2, 2, rl.RED)
        rl.image_draw_rectangle(image, 6, 1, 2, 2, rl.BLUE)
        self.assertTrue(rl.export_image(image, asset_path.as_posix()))
        rl.unload_image(image)
        self._temp_files.append(asset_path)
        return asset_path.as_posix()

    def _create_animator_probe(self, name: str, sprite_sheet: str, animations: dict, default_state: str = "idle") -> None:
        created = self.api.create_entity(
            name,
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Animator": {
                    "enabled": True,
                    "sprite_sheet": sprite_sheet,
                    "frame_width": 32,
                    "frame_height": 32,
                    "animations": animations,
                    "default_state": default_state,
                    "current_state": default_state,
                    "current_frame": 0,
                    "is_finished": False,
                },
            },
        )
        self.assertTrue(created["success"])

    def test_expand_slice_sequence_clamps_without_wraparound(self) -> None:
        slices = ["idle_0", "idle_1", "idle_2", "idle_3"]
        self.assertEqual(expand_slice_sequence(slices, "idle_1", 2), ["idle_1", "idle_2"])
        self.assertEqual(expand_slice_sequence(slices, "idle_2", 5), ["idle_2", "idle_3"])
        self.assertEqual(expand_slice_sequence(slices, "missing", 2), [])
        self.assertEqual(expand_slice_sequence(slices, "idle_0", 0), [])

    def test_animator_lists_png_assets_even_without_slices(self) -> None:
        unsliced = self._write_temp_png("assets/test_animator_unsliced.png")
        sliced = self._write_sheet_with_slices("assets/test_animator_sliced.png", ["a_0"])
        self._create_animator_probe(
            "AnimatorAssetProbe",
            unsliced,
            {"idle": {"frames": [0], "slice_names": [], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        assets = {item["path"]: item for item in self.panel.list_sprite_sheet_assets()}
        self.assertIn(unsliced, assets)
        self.assertIn(sliced, assets)
        self.assertFalse(assets[unsliced]["has_slices"])
        self.assertTrue(assets[sliced]["has_slices"])

    def test_game_opens_sprite_editor_modal_from_animator_request(self) -> None:
        unsliced = self._write_temp_png("assets/test_animator_modal.png")
        self._create_animator_probe(
            "AnimatorModalProbe",
            unsliced,
            {"idle": {"frames": [0], "slice_names": [], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        self.panel.request_open_sprite_editor_for = unsliced
        self.api.game._process_ui_requests()

        self.assertTrue(self.modal.is_open)
        self.assertEqual(self.modal.asset_path, unsliced)

    def test_game_opens_sprite_editor_modal_from_inspector_request(self) -> None:
        unsliced = self._write_temp_png("assets/test_inspector_modal.png")
        self.api.game._inspector_system.request_open_sprite_editor_for = unsliced
        self.api.game._process_ui_requests()
        self.assertTrue(self.modal.is_open)
        self.assertEqual(self.modal.asset_path, unsliced)

    def test_project_panel_can_create_folders_with_unique_names(self) -> None:
        panel = ProjectPanel(self.api.project_service.get_project_path("assets").as_posix())
        panel.set_project_service(self.api.project_service)

        first = Path(panel.create_folder())
        second = Path(panel.create_folder())
        self._temp_dirs.extend([second, first])

        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        self.assertEqual(first.name, "New Folder")
        self.assertEqual(second.name, "New Folder 1")

    def test_sprite_editor_modal_generates_sidecar_and_refreshes_slices(self) -> None:
        unsliced = self._write_temp_png("assets/test_animator_generate.png")
        metadata_path = Path(f"{unsliced}.meta.json")
        self._temp_files.append(metadata_path)
        self._create_animator_probe(
            "AnimatorGenerateProbe",
            unsliced,
            {"idle": {"frames": [0], "slice_names": [], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        opened = self.modal.open(unsliced)
        self.assertTrue(opened)
        self.modal.cell_width = 1
        self.modal.cell_height = 1
        metadata = self.modal.save_grid_slices()

        self.assertIsNotNone(metadata)
        self.assertTrue(metadata_path.exists())

        world = self.api.game.world
        world.selected_entity_name = "AnimatorGenerateProbe"
        context = self.panel.get_selection_context(world)
        self.assertTrue(context["has_slices"])
        self.assertEqual(context["available_slices"], ["test_animator_generate_0"])

        self.assertTrue(self.api.undo()["success"])
        context = self.panel.get_selection_context(world)
        self.assertFalse(context["has_slices"])

    def test_sprite_editor_modal_can_import_image_and_auto_slice_like_unity(self) -> None:
        source_path = self._write_auto_slice_png("external/test_unity_like_source.png")
        imported_path = self.modal.import_image(source_path)
        imported_file = Path(self.api.project_service.resolve_path(imported_path))
        self._temp_files.append(imported_file)
        self._temp_files.append(Path(f"{imported_path}.meta.json"))

        self.assertIsNotNone(imported_path)
        self.assertTrue(imported_file.exists())
        self.assertTrue(imported_path.startswith("assets/"))

        self.modal.import_mode = "automatic"
        metadata = self.modal.save_automatic_slices()

        self.assertIsNotNone(metadata)
        self.assertEqual(len(metadata["slices"]), 2)
        self.assertEqual(metadata["import_mode"], "automatic")

    def test_auto_slice_detects_sprites_on_opaque_background(self) -> None:
        source_path = self._write_opaque_background_sheet("external/test_opaque_background.png")
        imported_path = self.modal.import_image(source_path)
        imported_file = Path(self.api.project_service.resolve_path(imported_path))
        self._temp_files.append(imported_file)
        self._temp_files.append(Path(f"{imported_path}.meta.json"))

        self.modal.import_mode = "automatic"
        metadata = self.modal.save_automatic_slices()

        self.assertIsNotNone(metadata)
        self.assertEqual(len(metadata["slices"]), 2)
        self.assertEqual(
            [(item["x"], item["y"], item["width"], item["height"]) for item in metadata["slices"]],
            [(1, 1, 2, 2), (6, 1, 2, 2)],
        )

    def test_manual_slices_are_saved_as_independent_sprite_rectangles(self) -> None:
        asset_path = self._write_temp_png("assets/test_manual_rects.png")
        metadata_path = Path(f"{asset_path}.meta.json")
        self._temp_files.append(metadata_path)

        self.assertTrue(self.modal.open(asset_path))
        self.modal.import_mode = "manual"
        self.modal.manual_slices = [
            {"x": 0, "y": 0, "width": 1, "height": 1},
            {"x": 0, "y": 0, "width": 2, "height": 1},
        ]
        metadata = self.modal.save_manual_slices()

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["import_mode"], "manual")
        self.assertEqual(len(metadata["slices"]), 2)
        self.assertEqual(metadata["slices"][1]["width"], 2)

    def test_animator_api_set_frames_updates_serializable_state(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_api.png", ["idle_0", "idle_1", "run_0"])
        self._create_animator_probe(
            "AnimatorApiProbe",
            sprite_sheet,
            {
                "idle": {"frames": [0, 1], "slice_names": ["idle_0", "idle_1"], "fps": 8.0, "loop": True, "on_complete": None},
                "run": {"frames": [2], "slice_names": ["run_0"], "fps": 12.0, "loop": False, "on_complete": "idle"},
            },
        )

        result = self.api.set_animator_state_frames(
            "AnimatorApiProbe",
            "idle",
            ["idle_1", "run_0"],
            fps=14.0,
            loop=False,
            on_complete="run",
            set_default=True,
        )
        self.assertTrue(result["success"])

        animator = self.api.get_entity("AnimatorApiProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["idle_1", "run_0"])
        self.assertEqual(animator["animations"]["idle"]["frames"], [0, 1])
        self.assertEqual(animator["default_state"], "idle")
        self.assertEqual(animator["animations"]["idle"]["on_complete"], "run")

    def test_animator_panel_frame_rows_support_add_move_remove_and_undo_redo(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_rows.png", ["slice_0", "slice_1", "slice_2"])
        self._create_animator_probe(
            "AnimatorRowsProbe",
            sprite_sheet,
            {"idle": {"frames": [0, 1], "slice_names": ["slice_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRowsProbe"
        self.panel.selected_state_name = "idle"

        self.assertTrue(self.panel.add_frame(world, "idle"))
        self.assertTrue(self.panel.set_frame_slice(world, "idle", 1, "slice_2"))
        self.assertTrue(self.panel.move_frame(world, "idle", 1, -1))

        animator = self.api.get_entity("AnimatorRowsProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["slice_2", "slice_0"])

        self.assertTrue(self.panel.remove_frame(world, "idle", 1))
        animator = self.api.get_entity("AnimatorRowsProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["slice_2"])

        self.assertTrue(self.api.undo()["success"])
        animator = self.api.get_entity("AnimatorRowsProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["slice_2", "slice_0"])

        self.assertTrue(self.api.redo()["success"])
        animator = self.api.get_entity("AnimatorRowsProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["slice_2"])

    def test_animator_panel_selection_context_handles_selection_states(self) -> None:
        world = self.api.game.world
        self.assertEqual(self.panel.get_selection_context(world)["status"], "no_selection")

        created = self.api.create_entity("NoAnimatorProbe")
        self.assertTrue(created["success"])
        world = self.api.game.world
        world.selected_entity_name = "NoAnimatorProbe"
        self.assertEqual(self.panel.get_selection_context(world)["status"], "no_animator")

        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_context.png", ["slice_0", "slice_1"])
        self._create_animator_probe(
            "AnimatorContextProbe",
            sprite_sheet,
            {"idle": {"frames": [0, 1], "slice_names": ["slice_0", "slice_1"], "fps": 8.0, "loop": True, "on_complete": None}},
        )
        world = self.api.game.world
        world.selected_entity_name = "AnimatorContextProbe"
        context = self.panel.get_selection_context(world)
        self.assertEqual(context["status"], "ready")
        self.assertTrue(context["has_slices"])
        self.assertEqual(context["selected_state_name"], "idle")
        self.assertEqual(context["available_slices"], ["slice_0", "slice_1"])

    def test_animator_panel_preserves_legacy_frames_until_state_is_edited(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_legacy.png", ["legacy_0", "legacy_1", "legacy_2"])
        self._create_animator_probe(
            "AnimatorLegacyProbe",
            sprite_sheet,
            {"idle": {"frames": [4, 5, 6], "fps": 6.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorLegacyProbe"
        self.panel.selected_state_name = "idle"

        context = self.panel.get_selection_context(world)
        self.assertEqual(context["selected_state_data"].get("slice_names", []), [])
        self.assertEqual(context["selected_state_data"]["frames"], [4, 5, 6])

        self.assertTrue(self.panel.add_frame(world, "idle"))
        self.assertTrue(self.panel.set_frame_slice(world, "idle", 0, "legacy_1"))

        animator = self.api.get_entity("AnimatorLegacyProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["frames"], [4, 5, 6])
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["legacy_1"])

    def test_animator_panel_can_change_animation_speed_from_frame_duration(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_speed.png", ["speed_0", "speed_1"])
        self._create_animator_probe(
            "AnimatorSpeedProbe",
            sprite_sheet,
            {"idle": {"frames": [0, 1], "slice_names": ["speed_0", "speed_1"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorSpeedProbe"
        self.panel.selected_state_name = "idle"

        self.assertEqual(self.panel._fps_to_frame_ms(8.0), 125)
        self.assertTrue(self.panel.set_state_field(world, "idle", fps=self.panel._frame_ms_to_fps(200)))

        animator = self.api.get_entity("AnimatorSpeedProbe")["components"]["Animator"]
        self.assertAlmostEqual(animator["animations"]["idle"]["fps"], 5.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
