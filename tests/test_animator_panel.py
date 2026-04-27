import tempfile
import unittest
from pathlib import Path

import pyray as rl
from engine.api import EngineAPI
from engine.editor.animator_panel import (
    build_state_payload_from_slice_group,
    can_refresh_from_recommended_group,
    choose_default_slice_sequence,
    detect_slice_groups,
    detect_slice_sequences,
    expand_slice_sequence,
    get_default_state_name_for_group,
    get_recommended_group_action_hint,
    get_recommended_group_refresh_label,
    get_recommended_group_refresh_variant,
    get_recommended_group_sync_badge_variant,
    get_recommended_group_sync_status,
    get_recommended_slice_group,
    get_selected_state_slice_names,
    normalize_group_match_name,
)
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
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        self._previous_cwd = Path.cwd()
        self._copy_repo_file("levels/demo_level.json")
        self._change_cwd(self.project_root)
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")
        self.panel = self.api.game.animator_panel
        self.modal = self.api.game.sprite_editor_modal
        self._temp_files: list[Path] = []
        self._temp_dirs: list[Path] = []

    def tearDown(self) -> None:
        self.api.shutdown()
        self._change_cwd(self._previous_cwd)
        self._temp_dir.cleanup()

    def _change_cwd(self, path: Path) -> None:
        import os
        os.chdir(path)

    def _copy_repo_file(self, relative_path: str) -> Path:
        source = Path(__file__).resolve().parents[1] / relative_path
        target = self.project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def _write_temp_png(self, relative_path: str) -> str:
        file_path = self.project_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(MINIMAL_PNG_BYTES)
        self._temp_files.append(file_path)
        if file_path.is_relative_to(self.project_root):
            return file_path.relative_to(self.project_root).as_posix()
        return file_path.as_posix()

    def _write_sheet_with_slices(self, relative_path: str, slice_names: list[str]) -> str:
        asset_path = self._write_temp_png(relative_path)
        metadata_path = self.project_root / f"{asset_path}.meta.json"
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
        asset_path = self.workspace / relative_path
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
        asset_path = self.workspace / relative_path
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

    def test_detect_slice_sequences_groups_numbered_prefix_runs(self) -> None:
        sequences = detect_slice_sequences(["idle_0", "idle_1", "run_0", "idle_3", "run_1", "pose"])
        self.assertEqual(sequences, [["idle_0", "idle_1"], ["run_0", "run_1"]])

    def test_choose_default_slice_sequence_prefers_longest_numbered_run(self) -> None:
        choice = choose_default_slice_sequence(["idle_0", "idle_1", "run_0", "run_1", "run_2"])
        self.assertEqual(choice, ["run_0", "run_1", "run_2"])

        fallback = choose_default_slice_sequence(["pose_a", "pose_b"])
        self.assertEqual(fallback, ["pose_a"])

    def test_detect_slice_groups_collects_simple_prefix_groups_in_order(self) -> None:
        groups = detect_slice_groups(["idle_2", "run_1", "idle_0", "pose", "run_0", "idle_1", "jump_0"])
        self.assertEqual(
            groups,
            [
                {"group_name": "idle", "slice_names": ["idle_0", "idle_1", "idle_2"], "count": 3},
                {"group_name": "run", "slice_names": ["run_0", "run_1"], "count": 2},
            ],
        )

    def test_group_helpers_build_state_payload_and_default_name(self) -> None:
        self.assertEqual(get_default_state_name_for_group("idle"), "idle")
        self.assertEqual(get_default_state_name_for_group(""), "state")
        self.assertEqual(normalize_group_match_name(" Idle_1 "), "idle")
        self.assertEqual(normalize_group_match_name("run"), "run")

        payload = build_state_payload_from_slice_group(
            ["idle_0", "idle_1"],
            preserve_fields={"fps": 12.0, "loop": False, "on_complete": "run"},
        )
        self.assertEqual(payload["frames"], [0, 1])
        self.assertEqual(payload["slice_names"], ["idle_0", "idle_1"])
        self.assertEqual(payload["fps"], 12.0)
        self.assertEqual(payload["loop"], False)
        self.assertEqual(payload["on_complete"], "run")

    def test_get_recommended_slice_group_matches_selected_state_name_safely(self) -> None:
        groups = [
            {"group_name": "idle", "slice_names": ["idle_0", "idle_1"], "count": 2},
            {"group_name": "run", "slice_names": ["run_0", "run_1"], "count": 2},
        ]
        self.assertEqual(get_recommended_slice_group("idle", groups), groups[0])
        self.assertEqual(get_recommended_slice_group("idle_1", groups), groups[0])
        self.assertIsNone(get_recommended_slice_group("jump", groups))

    def test_can_refresh_from_recommended_group_requires_selected_state_and_valid_group(self) -> None:
        context = {"selected_state_name": "idle"}
        recommended = {"group_name": "idle", "slice_names": ["idle_0", "idle_1"], "count": 2}
        self.assertTrue(can_refresh_from_recommended_group(context, recommended))
        self.assertFalse(can_refresh_from_recommended_group({"selected_state_name": ""}, recommended))
        self.assertFalse(can_refresh_from_recommended_group(context, None))
        self.assertFalse(can_refresh_from_recommended_group(context, {"group_name": "idle", "slice_names": [], "count": 0}))

    def test_recommended_group_sync_helpers_compare_selected_state_slice_names(self) -> None:
        recommended = {"group_name": "idle", "slice_names": ["idle_0", "idle_1"], "count": 2}
        aligned_context = {
            "selected_state_name": "idle",
            "selected_state_data": {"slice_names": ["idle_0", "idle_1"]},
        }
        out_of_sync_context = {
            "selected_state_name": "idle",
            "selected_state_data": {"slice_names": ["idle_1", "idle_0"]},
        }

        self.assertEqual(get_selected_state_slice_names(aligned_context), ["idle_0", "idle_1"])
        self.assertEqual(get_recommended_group_sync_status(aligned_context, recommended), "aligned")
        self.assertEqual(get_recommended_group_sync_status(out_of_sync_context, recommended), "out_of_sync")
        self.assertIsNone(get_recommended_group_sync_status({"selected_state_name": ""}, recommended))
        self.assertIsNone(get_recommended_group_sync_status(aligned_context, None))
        self.assertIsNone(
            get_recommended_group_sync_status(
                aligned_context,
                {"group_name": "idle", "slice_names": [], "count": 0},
            )
        )

    def test_recommended_group_action_hint_uses_existing_sync_status(self) -> None:
        self.assertEqual(get_recommended_group_action_hint("aligned"), "Already aligned")
        self.assertEqual(get_recommended_group_action_hint("out_of_sync"), "Will update frames")
        self.assertEqual(get_recommended_group_action_hint(None), "")

    def test_recommended_group_refresh_label_uses_existing_sync_status(self) -> None:
        self.assertEqual(get_recommended_group_refresh_label("aligned"), "Refresh Anyway")
        self.assertEqual(get_recommended_group_refresh_label("out_of_sync"), "Refresh Frames")
        self.assertEqual(get_recommended_group_refresh_label(None), "Refresh From Recommended")

    def test_recommended_group_refresh_variant_uses_existing_sync_status(self) -> None:
        self.assertEqual(get_recommended_group_refresh_variant("aligned"), "neutral")
        self.assertEqual(get_recommended_group_refresh_variant("out_of_sync"), "emphasis")
        self.assertEqual(get_recommended_group_refresh_variant(None), "default")

    def test_recommended_group_sync_badge_variant_uses_existing_sync_status(self) -> None:
        self.assertEqual(get_recommended_group_sync_badge_variant("aligned"), "neutral")
        self.assertEqual(get_recommended_group_sync_badge_variant("out_of_sync"), "emphasis")
        self.assertEqual(get_recommended_group_sync_badge_variant(None), "default")

    def test_animator_lists_png_assets_even_without_slices(self) -> None:
        unsliced = self._write_temp_png("assets/test_animator_unsliced.png")
        sliced = self._write_sheet_with_slices("assets/test_animator_sliced.png", ["a_0"])
        metadata_only = self._write_temp_png("assets/test_animator_metadata.png")
        metadata_result = self.api.save_asset_metadata(
            metadata_only,
            {
                "asset_type": "texture",
                "import_mode": "raw",
                "grid": {},
                "automatic": {},
                "slices": [],
            },
        )
        self.assertTrue(metadata_result["success"])
        self._create_animator_probe(
            "AnimatorAssetProbe",
            unsliced,
            {"idle": {"frames": [0], "slice_names": [], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        assets = {item["path"]: item for item in self.panel.list_sprite_sheet_assets()}
        self.assertIn(unsliced, assets)
        self.assertIn(sliced, assets)
        self.assertIn(metadata_only, assets)
        self.assertFalse(assets[unsliced]["has_slices"])
        self.assertTrue(assets[sliced]["has_slices"])
        self.assertEqual(assets[unsliced]["pipeline_status"], "image")
        self.assertEqual(assets[metadata_only]["pipeline_status"], "metadata")
        self.assertEqual(assets[sliced]["pipeline_status"], "ready")
        self.assertEqual(assets[sliced]["slice_count"], 1)

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
        self.assertEqual(metadata["import_mode"], "grid")
        self.assertEqual(metadata["import_settings"]["grid"], metadata["grid"])
        self.assertEqual(metadata["import_settings"]["automatic"], {})

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
        self.assertEqual(context["sprite_sheet_pipeline_status"], "ready")
        self.assertEqual(context["sprite_sheet_pipeline_label"], "sprite ready")

    def test_animator_panel_context_marks_unsliced_sheet_as_needing_slicing(self) -> None:
        unsliced = self._write_temp_png("assets/test_animator_context_unsliced.png")
        metadata = self.api.save_asset_metadata(
            unsliced,
            {
                "asset_type": "sprite_sheet",
                "import_mode": "grid",
                "grid": {"cell_width": 16, "cell_height": 16},
                "automatic": {},
                "slices": [],
            },
        )
        self.assertTrue(metadata["success"])
        self._create_animator_probe(
            "AnimatorUnslicedContextProbe",
            unsliced,
            {"idle": {"frames": [0], "slice_names": [], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorUnslicedContextProbe"
        context = self.panel.get_selection_context(world)

        self.assertEqual(context["sprite_sheet_pipeline_status"], "needs slicing")
        self.assertEqual(context["sprite_sheet_pipeline_label"], "sprite sheet without slices")
        self.assertFalse(context["sprite_sheet_ready"])
        self.assertFalse(context["has_slices"])

    def test_animator_create_state_bootstraps_from_detected_slice_sequence(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_bootstrap.png",
            ["idle_0", "idle_1", "idle_2", "run_0"],
        )
        self._create_animator_probe(
            "AnimatorBootstrapProbe",
            sprite_sheet,
            {},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorBootstrapProbe"

        self.assertTrue(self.panel.create_state(world))
        animator = self.api.get_entity("AnimatorBootstrapProbe")["components"]["Animator"]
        created_state = animator["animations"]["state_1"]

        self.assertEqual(created_state["slice_names"], ["idle_0", "idle_1", "idle_2"])
        self.assertEqual(created_state["frames"], [0, 1, 2])

    def test_animator_panel_lists_detected_slice_groups_from_context(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_groups.png",
            ["idle_0", "idle_1", "run_0", "run_1", "pose"],
        )
        self._create_animator_probe(
            "AnimatorGroupsProbe",
            sprite_sheet,
            {"existing": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorGroupsProbe"
        groups = self.panel.list_detected_slice_groups(world)

        self.assertEqual(
            groups,
            [
                {"group_name": "idle", "slice_names": ["idle_0", "idle_1"], "count": 2},
                {"group_name": "run", "slice_names": ["run_0", "run_1"], "count": 2},
            ],
        )

    def test_animator_panel_recommends_group_for_selected_state(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_recommended_group.png",
            ["idle_0", "idle_1", "run_0", "run_1"],
        )
        self._create_animator_probe(
            "AnimatorRecommendedProbe",
            sprite_sheet,
            {
                "idle_1": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None},
                "run": {"frames": [0], "slice_names": ["run_0"], "fps": 8.0, "loop": True, "on_complete": None},
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRecommendedProbe"
        self.panel.selected_state_name = "idle_1"
        context = self.panel.get_selection_context(world)
        recommended = self.panel._get_recommended_group_from_context(context)

        self.assertIsNotNone(recommended)
        self.assertEqual(recommended["group_name"], "idle")

    def test_animator_panel_marks_recommended_group_as_aligned_when_sequences_match(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_aligned_group.png",
            ["idle_0", "idle_1", "run_0", "run_1"],
        )
        self._create_animator_probe(
            "AnimatorAlignedProbe",
            sprite_sheet,
            {"idle": {"frames": [0, 1], "slice_names": ["idle_0", "idle_1"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorAlignedProbe"
        self.panel.selected_state_name = "idle"
        context = self.panel.get_selection_context(world)
        recommended = self.panel._get_recommended_group_from_context(context)

        self.assertEqual(
            self.panel._get_recommended_group_sync_status_from_context(context, recommended),
            "aligned",
        )

    def test_animator_panel_marks_recommended_group_as_out_of_sync_when_sequences_differ(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_out_of_sync_group.png",
            ["idle_0", "idle_1", "idle_2", "run_0"],
        )
        self._create_animator_probe(
            "AnimatorOutOfSyncProbe",
            sprite_sheet,
            {"idle": {"frames": [0], "slice_names": ["run_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorOutOfSyncProbe"
        self.panel.selected_state_name = "idle"
        context = self.panel.get_selection_context(world)
        recommended = self.panel._get_recommended_group_from_context(context)

        self.assertEqual(
            self.panel._get_recommended_group_sync_status_from_context(context, recommended),
            "out_of_sync",
        )

    def test_animator_panel_has_no_recommended_group_when_no_clear_match_exists(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_no_recommended_group.png",
            ["idle_0", "idle_1", "run_0", "run_1"],
        )
        self._create_animator_probe(
            "AnimatorNoRecommendedProbe",
            sprite_sheet,
            {"jump": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorNoRecommendedProbe"
        self.panel.selected_state_name = "jump"
        context = self.panel.get_selection_context(world)

        self.assertIsNone(self.panel._get_recommended_group_from_context(context))
        self.assertIsNone(self.panel._get_recommended_group_sync_status_from_context(context, None))

    def test_animator_can_create_state_from_slice_group_with_safe_name_collision(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_create_group.png",
            ["idle_0", "idle_1", "run_0", "run_1"],
        )
        self._create_animator_probe(
            "AnimatorCreateGroupProbe",
            sprite_sheet,
            {"idle": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorCreateGroupProbe"

        self.assertTrue(self.panel.create_state_from_slice_group(world, "idle"))
        animator = self.api.get_entity("AnimatorCreateGroupProbe")["components"]["Animator"]
        self.assertIn("idle_1", animator["animations"])
        self.assertEqual(animator["animations"]["idle_1"]["slice_names"], ["idle_0", "idle_1"])
        self.assertEqual(animator["animations"]["idle_1"]["frames"], [0, 1])

    def test_animator_can_create_state_from_recommended_group_with_safe_name_collision(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_create_recommended_group.png",
            ["idle_0", "idle_1", "run_0", "run_1"],
        )
        self._create_animator_probe(
            "AnimatorCreateRecommendedProbe",
            sprite_sheet,
            {
                "idle": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None},
                "idle_1": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None},
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorCreateRecommendedProbe"
        self.panel.selected_state_name = "idle"

        self.assertTrue(self.panel.create_state_from_recommended_group(world))
        animator = self.api.get_entity("AnimatorCreateRecommendedProbe")["components"]["Animator"]
        self.assertIn("idle_2", animator["animations"])
        self.assertEqual(animator["animations"]["idle_2"]["slice_names"], ["idle_0", "idle_1"])

    def test_animator_can_refresh_selected_state_from_recommended_group_preserving_fields(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_refresh_recommended_group.png",
            ["idle_0", "idle_1", "idle_2", "run_0"],
        )
        self._create_animator_probe(
            "AnimatorRefreshRecommendedProbe",
            sprite_sheet,
            {
                "idle": {
                    "frames": [9],
                    "slice_names": ["run_0"],
                    "fps": 11.0,
                    "loop": False,
                    "on_complete": "idle",
                },
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRefreshRecommendedProbe"
        self.panel.selected_state_name = "idle"
        before_context = self.panel.get_selection_context(world)
        before_recommended = self.panel._get_recommended_group_from_context(before_context)

        self.assertEqual(
            self.panel._get_recommended_group_sync_status_from_context(before_context, before_recommended),
            "out_of_sync",
        )

        self.assertTrue(self.panel.refresh_state_from_recommended_group(world))
        animator = self.api.get_entity("AnimatorRefreshRecommendedProbe")["components"]["Animator"]
        state = animator["animations"]["idle"]
        self.assertEqual(state["slice_names"], ["idle_0", "idle_1", "idle_2"])
        self.assertEqual(state["frames"], [0, 1, 2])
        self.assertEqual(state["fps"], 11.0)
        self.assertEqual(state["loop"], False)
        self.assertEqual(state["on_complete"], "idle")
        after_context = self.panel.get_selection_context(world)
        after_recommended = self.panel._get_recommended_group_from_context(after_context)
        self.assertEqual(
            self.panel._get_recommended_group_sync_status_from_context(after_context, after_recommended),
            "aligned",
        )

    def test_animator_refresh_from_recommended_group_is_safe_and_idempotent(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_refresh_idempotent.png",
            ["idle_0", "idle_1"],
        )
        self._create_animator_probe(
            "AnimatorRefreshIdempotentProbe",
            sprite_sheet,
            {
                "idle": {
                    "frames": [0, 1],
                    "slice_names": ["idle_0", "idle_1"],
                    "fps": 8.0,
                    "loop": True,
                    "on_complete": None,
                },
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRefreshIdempotentProbe"
        self.panel.selected_state_name = "idle"

        self.assertTrue(self.panel.refresh_state_from_recommended_group(world))
        animator = self.api.get_entity("AnimatorRefreshIdempotentProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["idle"]["slice_names"], ["idle_0", "idle_1"])
        self.assertEqual(animator["animations"]["idle"]["frames"], [0, 1])

    def test_animator_refresh_from_recommended_group_fails_without_recommendation(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_refresh_no_recommendation.png",
            ["idle_0", "idle_1"],
        )
        self._create_animator_probe(
            "AnimatorRefreshNoRecommendationProbe",
            sprite_sheet,
            {
                "jump": {
                    "frames": [0],
                    "slice_names": ["idle_0"],
                    "fps": 8.0,
                    "loop": True,
                    "on_complete": None,
                },
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRefreshNoRecommendationProbe"
        self.panel.selected_state_name = "jump"
        self.assertFalse(self.panel.refresh_state_from_recommended_group(world))

    def test_animator_can_apply_slice_group_to_existing_state_preserving_fields(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_apply_group.png",
            ["idle_0", "idle_1", "run_0", "run_1", "run_2"],
        )
        self._create_animator_probe(
            "AnimatorApplyGroupProbe",
            sprite_sheet,
            {
                "run": {
                    "frames": [9],
                    "slice_names": ["idle_0"],
                    "fps": 14.0,
                    "loop": False,
                    "on_complete": "idle",
                },
                "idle": {"frames": [0], "slice_names": ["idle_0"], "fps": 8.0, "loop": True, "on_complete": None},
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorApplyGroupProbe"

        self.assertTrue(self.panel.apply_slice_group_to_state(world, "run", "run"))
        animator = self.api.get_entity("AnimatorApplyGroupProbe")["components"]["Animator"]
        state = animator["animations"]["run"]

        self.assertEqual(state["slice_names"], ["run_0", "run_1", "run_2"])
        self.assertEqual(state["frames"], [0, 1, 2])
        self.assertEqual(state["fps"], 14.0)
        self.assertEqual(state["loop"], False)
        self.assertEqual(state["on_complete"], "idle")

    def test_animator_group_operations_fail_safely_when_no_groups_are_detectable(self) -> None:
        sprite_sheet = self._write_sheet_with_slices(
            "assets/test_animator_no_groups.png",
            ["pose", "jump", "land"],
        )
        self._create_animator_probe(
            "AnimatorNoGroupsProbe",
            sprite_sheet,
            {"idle": {"frames": [0], "slice_names": ["pose"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorNoGroupsProbe"

        self.assertEqual(self.panel.list_detected_slice_groups(world), [])
        self.assertFalse(self.panel.create_state_from_slice_group(world, "idle"))
        self.assertFalse(self.panel.apply_slice_group_to_state(world, "idle", "idle"))

    def test_animator_panel_can_request_sprite_editor_for_unprepared_sheet(self) -> None:
        unsliced = self._write_temp_png("assets/test_animator_request_unsliced.png")
        self._create_animator_probe(
            "AnimatorRequestUnslicedProbe",
            unsliced,
            {"idle": {"frames": [0], "slice_names": [], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRequestUnslicedProbe"
        context = self.panel.get_selection_context(world)

        self.assertEqual(context["sprite_sheet_pipeline_status"], "image")
        self.panel.request_open_sprite_editor_for = context["sprite_sheet"]
        self.api.game._process_ui_requests()
        self.assertTrue(self.modal.is_open)
        self.assertEqual(self.modal.asset_path, unsliced)

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

    def test_animator_panel_duplicate_state(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_dup.png", ["a_0", "a_1", "b_0"])
        self._create_animator_probe(
            "AnimatorDupProbe",
            sprite_sheet,
            {
                "idle": {"frames": [0], "slice_names": ["a_0"], "fps": 8.0, "loop": True, "on_complete": None},
                "run": {"frames": [1, 2], "slice_names": ["a_1", "b_0"], "fps": 12.0, "loop": False, "on_complete": None},
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorDupProbe"

        self.assertTrue(self.panel.duplicate_state(world, "idle"))
        animator = self.api.get_entity("AnimatorDupProbe")["components"]["Animator"]
        self.assertIn("idle_copy", animator["animations"])
        self.assertEqual(animator["animations"]["idle_copy"]["slice_names"], ["a_0"])
        self.assertEqual(animator["animations"]["idle_copy"]["fps"], 8.0)
        self.assertEqual(animator["animations"]["idle_copy"]["loop"], True)

        self.assertTrue(self.panel.duplicate_state(world, "run", "dash"))
        animator = self.api.get_entity("AnimatorDupProbe")["components"]["Animator"]
        self.assertIn("dash", animator["animations"])
        self.assertEqual(animator["animations"]["dash"]["slice_names"], ["a_1", "b_0"])
        self.assertEqual(animator["animations"]["dash"]["fps"], 12.0)
        self.assertEqual(animator["animations"]["dash"]["loop"], False)

    def test_animator_panel_duplicate_state_avoids_name_collision(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_dup2.png", ["x_0"])
        self._create_animator_probe(
            "AnimatorDup2Probe",
            sprite_sheet,
            {"idle": {"frames": [0], "slice_names": ["x_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorDup2Probe"

        self.assertTrue(self.panel.duplicate_state(world, "idle"))
        self.assertTrue(self.panel.duplicate_state(world, "idle"))
        animator = self.api.get_entity("AnimatorDup2Probe")["components"]["Animator"]
        self.assertIn("idle_copy", animator["animations"])
        self.assertIn("idle_copy_1", animator["animations"])

    def test_animator_panel_rename_state(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_rename.png", ["a_0", "b_0"])
        self._create_animator_probe(
            "AnimatorRenameProbe",
            sprite_sheet,
            {
                "idle": {"frames": [0], "slice_names": ["a_0"], "fps": 8.0, "loop": True, "on_complete": None},
                "run": {"frames": [1], "slice_names": ["b_0"], "fps": 12.0, "loop": False, "on_complete": "idle"},
            },
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorRenameProbe"
        self.panel.selected_state_name = "idle"

        self.assertTrue(self.panel.rename_state(world, "idle", "idle_alt"))
        animator = self.api.get_entity("AnimatorRenameProbe")["components"]["Animator"]
        self.assertIn("idle_alt", animator["animations"])
        self.assertNotIn("idle", animator["animations"])
        self.assertEqual(animator["default_state"], "idle_alt")

        self.assertTrue(self.panel.rename_state(world, "run", "sprint"))
        animator = self.api.get_entity("AnimatorRenameProbe")["components"]["Animator"]
        self.assertEqual(animator["animations"]["sprint"]["on_complete"], "idle_alt")

    def test_animator_panel_set_animator_flip(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_flip.png", ["f_0"])
        self._create_animator_probe(
            "AnimatorFlipProbe",
            sprite_sheet,
            {"idle": {"frames": [0], "slice_names": ["f_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorFlipProbe"

        self.assertTrue(self.panel.set_animator_flip(world, flip_x=True))
        animator = self.api.get_entity("AnimatorFlipProbe")["components"]["Animator"]
        self.assertEqual(animator["flip_x"], True)

        self.assertTrue(self.panel.set_animator_flip(world, flip_y=True))
        animator = self.api.get_entity("AnimatorFlipProbe")["components"]["Animator"]
        self.assertEqual(animator["flip_y"], True)

        self.assertTrue(self.panel.set_animator_flip(world, flip_x=False))
        animator = self.api.get_entity("AnimatorFlipProbe")["components"]["Animator"]
        self.assertEqual(animator["flip_x"], False)
        self.assertEqual(animator["flip_y"], True)

    def test_animator_panel_set_animator_speed(self) -> None:
        sprite_sheet = self._write_sheet_with_slices("assets/test_animator_sp.png", ["s_0"])
        self._create_animator_probe(
            "AnimatorSpeedPanelProbe",
            sprite_sheet,
            {"idle": {"frames": [0], "slice_names": ["s_0"], "fps": 8.0, "loop": True, "on_complete": None}},
        )

        world = self.api.game.world
        world.selected_entity_name = "AnimatorSpeedPanelProbe"

        self.assertTrue(self.panel.set_animator_speed(world, 2.0))
        animator = self.api.get_entity("AnimatorSpeedPanelProbe")["components"]["Animator"]
        self.assertEqual(animator["speed"], 2.0)

        self.assertTrue(self.panel.set_animator_speed(world, 0.5))
        animator = self.api.get_entity("AnimatorSpeedPanelProbe")["components"]["Animator"]
        self.assertEqual(animator["speed"], 0.5)

        self.assertTrue(self.panel.set_animator_speed(world, 0.0))
        animator = self.api.get_entity("AnimatorSpeedPanelProbe")["components"]["Animator"]
        self.assertEqual(animator["speed"], 0.01)


class AnimatorPanelSourceRegressionTests(unittest.TestCase):
    def test_animator_panel_does_not_reference_modal_or_private_runtime_hooks(self) -> None:
        source = Path("engine/editor/animator_panel.py").read_text(encoding="utf-8")
        forbidden_tokens = (
            "sprite_editor_modal",
            "._input_system",
            "._event_bus",
        )

        for token in forbidden_tokens:
            self.assertNotIn(token, source, msg=f"engine/editor/animator_panel.py still references {token}")


if __name__ == "__main__":
    unittest.main()
