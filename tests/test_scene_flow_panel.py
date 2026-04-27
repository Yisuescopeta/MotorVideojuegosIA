import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pyray as rl
from engine.core.game import Game
from engine.editor.scene_flow_panel import SceneFlowPanel
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_transition_support import collect_project_scene_links, collect_project_scene_transitions


def _transform(x: float, y: float) -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


class SceneFlowPanelSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "FlowProject"
        self.project_service = ProjectService(
            self.project_root,
            global_state_dir=(self.root / "global_state"),
        )
        self.scene_manager = SceneManager(create_default_registry())

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, filename: str, payload: dict | str) -> Path:
        path = self.project_root / "levels" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        return path

    def _entry_scene(self, name: str, entry_points: list[tuple[str, str]]) -> dict:
        entities = []
        for index, (entry_id, label) in enumerate(entry_points):
            entities.append(
                {
                    "name": f"{label}Point",
                    "active": True,
                    "tag": "Untagged",
                    "layer": "Default",
                    "components": {
                        "Transform": _transform(100.0 + (index * 16.0), 80.0),
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
            "name": name,
            "entities": entities,
            "rules": [],
            "feature_metadata": {},
        }

    def test_collect_project_scene_transitions_builds_real_scene_adjacency(self) -> None:
        self._write_scene("level1.json", self._entry_scene("Level1", [("arrival", "Arrival")]))
        self._write_scene("game_over.json", self._entry_scene("GameOver", []))
        self._write_scene(
            "main_menu.json",
            {
                "schema_version": 2,
                "name": "MainMenu",
                "entities": [
                    {
                        "name": "PlayButton",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "UIButton": {"enabled": True, "interactable": True, "label": "Play", "on_click": {"type": "run_scene_transition"}},
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/level1.json",
                                "target_entry_id": "arrival",
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene(
            "level1_source.json",
            {
                "schema_version": 2,
                "name": "Level1Source",
                "entities": [
                    {
                        "name": "Portal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Collider": {
                                "enabled": True,
                                "width": 32.0,
                                "height": 32.0,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "is_trigger": True,
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/game_over.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnContact": {
                                "enabled": True,
                                "mode": "trigger_enter",
                                "require_player": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene(
            "game_over_source.json",
            {
                "schema_version": 2,
                "name": "GameOverSource",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Default",
                        "components": {
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/main_menu.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnPlayerDeath": {"enabled": True},
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )

        snapshot = collect_project_scene_transitions(self.project_service, self.scene_manager)

        summaries = {item["source_scene_name"]: item for item in snapshot["summaries"]}
        self.assertEqual(summaries["MainMenu"]["destination_labels"], ["Level1"])
        self.assertEqual(summaries["Level1Source"]["destination_labels"], ["GameOver"])
        self.assertEqual(summaries["GameOverSource"]["destination_labels"], ["MainMenu"])

        rows = {(item["source_scene_name"], item["source_entity_name"]): item for item in snapshot["rows"]}
        self.assertEqual(rows[("MainMenu", "PlayButton")]["trigger_label"], "UI Button")
        self.assertEqual(rows[("MainMenu", "PlayButton")]["target_entry_id"], "arrival")
        self.assertEqual(rows[("MainMenu", "PlayButton")]["status"], "ok")
        self.assertEqual(rows[("Level1Source", "Portal")]["trigger_label"], "Trigger Enter")
        self.assertEqual(rows[("GameOverSource", "Player")]["trigger_label"], "Player Death")

    def test_collect_project_scene_transitions_reports_missing_targets_and_incomplete_entities(self) -> None:
        self._write_scene("valid_target.json", self._entry_scene("ValidTarget", [("arrival", "Arrival")]))
        self._write_scene(
            "broken_links.json",
            {
                "schema_version": 2,
                "name": "BrokenLinks",
                "entities": [
                    {
                        "name": "MissingSceneButton",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "UIButton": {"enabled": True, "interactable": True, "label": "Missing", "on_click": {"type": "run_scene_transition"}},
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/ghost_scene.json",
                                "target_entry_id": "",
                            },
                        },
                    },
                    {
                        "name": "MissingSpawnPortal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/valid_target.json",
                                "target_entry_id": "ghost_spawn",
                            },
                            "SceneTransitionOnContact": {
                                "enabled": True,
                                "mode": "collision",
                                "require_player": True,
                            },
                        },
                    },
                    {
                        "name": "ActionOnly",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/valid_target.json",
                                "target_entry_id": "",
                            }
                        },
                    },
                    {
                        "name": "TriggerOnly",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "SceneTransitionOnInteract": {"enabled": True, "require_player": True}
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("broken_json.json", "{ invalid json")

        snapshot = collect_project_scene_transitions(self.project_service, self.scene_manager)

        rows = {(item["source_entity_name"], item["trigger_label"]): item for item in snapshot["rows"]}
        self.assertEqual(rows[("MissingSceneButton", "UI Button")]["status"], "error")
        self.assertTrue(any("does not exist" in message for message in rows[("MissingSceneButton", "UI Button")]["messages"]))
        self.assertEqual(rows[("MissingSpawnPortal", "Collision")]["status"], "error")
        self.assertTrue(any("ghost_spawn" in message for message in rows[("MissingSpawnPortal", "Collision")]["messages"]))
        self.assertEqual(rows[("ActionOnly", "Missing Trigger")]["status"], "warning")
        self.assertTrue(any("no trigger" in message.lower() for message in rows[("ActionOnly", "Missing Trigger")]["messages"]))
        self.assertEqual(rows[("TriggerOnly", "Interact Near")]["status"], "error")
        self.assertTrue(any("no SceneTransitionAction" in message for message in rows[("TriggerOnly", "Interact Near")]["messages"]))

        issue_scenes = {item["source_scene_name"]: item for item in snapshot["issues"]}
        self.assertIn("broken json", issue_scenes["broken json"]["source_scene_name"].lower())
        self.assertEqual(issue_scenes["broken json"]["status"], "error")

    def test_collect_project_scene_transitions_prefers_open_scene_snapshot_over_disk(self) -> None:
        source_path = self._write_scene(
            "unsaved_source.json",
            {
                "schema_version": 2,
                "name": "UnsavedSource",
                "entities": [
                    {
                        "name": "Portal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/target_b.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnContact": {
                                "enabled": True,
                                "mode": "trigger_enter",
                                "require_player": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("target_b.json", self._entry_scene("TargetB", []))
        self._write_scene("target_c.json", self._entry_scene("TargetC", []))

        self.assertIsNotNone(self.scene_manager.load_scene_from_file(source_path.as_posix(), activate=True))
        self.assertTrue(
            self.scene_manager.replace_component_data(
                "Portal",
                "SceneTransitionAction",
                {
                    "enabled": True,
                    "target_scene_path": "levels/target_c.json",
                    "target_entry_id": "",
                },
            )
        )

        snapshot = collect_project_scene_transitions(self.project_service, self.scene_manager)

        row = next(item for item in snapshot["rows"] if item["source_scene_name"] == "UnsavedSource")
        self.assertEqual(row["target_scene_name"], "TargetC")
        self.assertEqual(row["target_scene_path"], "levels/target_c.json")

    def test_game_flow_navigation_opens_scene_and_selects_entity(self) -> None:
        game = Game()
        game._scene_manager = Mock()
        game._scene_manager.set_selected_entity.return_value = True

        with patch.object(game, "activate_scene_workspace_tab", return_value=True) as activate_scene, patch.object(
            game,
            "load_scene_by_path",
            return_value=False,
        ) as load_scene:
            game._open_flow_source({"scene_ref": "levels/main_menu.json", "entity_name": "PlayButton"})
            game._open_flow_target({"scene_ref": "levels/level1.json"})

        activate_scene.assert_any_call("levels/main_menu.json")
        activate_scene.assert_any_call("levels/level1.json")
        game._scene_manager.set_selected_entity.assert_called_once_with("PlayButton")
        load_scene.assert_not_called()

    def test_flow_panel_render_keeps_internal_rects_inside_panel_rect(self) -> None:
        panel = SceneFlowPanel()
        target_rect = (12, 34, 720, 180)

        with patch("engine.editor.scene_flow_panel.gui_toggle_bool", side_effect=lambda rect, _label, value: value), patch(
            "pyray.gui_button",
            return_value=False,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch("pyray.draw_text"), patch(
            "pyray.begin_scissor_mode"
        ), patch("pyray.end_scissor_mode"), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_position"), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(*target_rect)

        px, py, pw, ph = target_rect
        def _inside(rect) -> bool:
            return (
                rect.x >= px
                and rect.y >= py
                and rect.x + rect.width <= px + pw
                and rect.y + rect.height <= py + ph
            )

        self.assertTrue(_inside(panel._panel_rect))
        self.assertTrue(_inside(panel._toolbar_rect))
        self.assertTrue(_inside(panel._list_rect))
        self.assertTrue(_inside(panel._list_header_rect))
        self.assertTrue(_inside(panel._list_body_rect))
        self.assertTrue(_inside(panel._editor_rect))
        self.assertTrue(_inside(panel._editor_header_rect))
        self.assertTrue(_inside(panel._editor_body_rect))
        self.assertTrue(all(_inside(rect) for rect in panel._cursor_interactive_rects))

    def test_flow_panel_uses_compact_layout_without_overflow_in_small_bottom_panel(self) -> None:
        panel = SceneFlowPanel()

        with patch("engine.editor.scene_flow_panel.gui_toggle_bool", side_effect=lambda rect, _label, value: value), patch(
            "pyray.gui_button",
            return_value=False,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch("pyray.draw_text"), patch(
            "pyray.begin_scissor_mode"
        ), patch("pyray.end_scissor_mode"), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_position"), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(0, 0, 320, 120)

        self.assertLessEqual(panel._toolbar_rect.x + panel._toolbar_rect.width, panel._panel_rect.x + panel._panel_rect.width)
        self.assertLessEqual(panel._list_rect.y + panel._list_rect.height, panel._panel_rect.y + panel._panel_rect.height)
        self.assertLessEqual(panel._editor_rect.y + panel._editor_rect.height, panel._panel_rect.y + panel._panel_rect.height)
        self.assertTrue(all(rect.width >= 0 and rect.height >= 0 for rect in panel._detail_columns.values()))

    def test_flow_panel_renders_visible_empty_state_sections(self) -> None:
        panel = SceneFlowPanel()
        drawn_texts: list[str] = []

        with patch("engine.editor.scene_flow_panel.gui_toggle_bool", side_effect=lambda rect, _label, value: value), patch(
            "pyray.gui_button",
            return_value=False,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch(
            "pyray.draw_text",
            side_effect=lambda text, *_args, **_kwargs: drawn_texts.append(str(text)),
        ), patch("pyray.begin_scissor_mode"), patch("pyray.end_scissor_mode"), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_position"), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(0, 0, 640, 180)

        self.assertIn("Scene Flow", drawn_texts)
        self.assertIn("Scene Links", drawn_texts)
        self.assertIn("Connection Editor", drawn_texts)
        self.assertIn("No SceneLink entities found in this view.", drawn_texts)

    def test_flow_panel_shows_error_fallback_when_internal_render_fails(self) -> None:
        panel = SceneFlowPanel()
        drawn_texts: list[str] = []

        with patch("engine.editor.scene_flow_panel.gui_toggle_bool", side_effect=lambda rect, _label, value: value), patch(
            "pyray.gui_button",
            return_value=False,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch(
            "pyray.draw_text",
            side_effect=lambda text, *_args, **_kwargs: drawn_texts.append(str(text)) if text != "Scene Links" else (_ for _ in ()).throw(RuntimeError("draw failure")),
        ), patch("pyray.begin_scissor_mode") as begin_scissor, patch(
            "pyray.end_scissor_mode"
        ) as end_scissor, patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_position"), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(0, 0, 640, 180)

        self.assertEqual(begin_scissor.call_count, 0)
        self.assertEqual(end_scissor.call_count, 0)
        self.assertIn("Flow could not render this frame.", drawn_texts)

    def test_collect_project_scene_links_shows_open_scene_link_rows_for_current_scene(self) -> None:
        self.scene_manager.create_new_scene("Main Scene")
        self.assertTrue(
            self.scene_manager.create_entity(
                "DoorA",
                components={
                    "Transform": _transform(0.0, 0.0),
                    "SceneLink": {
                        "enabled": True,
                        "target_path": "levels/next_a.json",
                        "flow_key": "",
                        "preview_label": "",
                        "link_mode": "trigger_enter",
                        "target_entry_id": "",
                    },
                },
            )
        )
        self.assertTrue(
            self.scene_manager.create_entity(
                "DoorB",
                components={
                    "Transform": _transform(16.0, 0.0),
                    "SceneLink": {
                        "enabled": True,
                        "target_path": "levels/next_b.json",
                        "flow_key": "",
                        "preview_label": "",
                        "link_mode": "collision",
                        "target_entry_id": "",
                    },
                },
            )
        )

        panel = SceneFlowPanel()
        panel.set_scene_manager(self.scene_manager)
        snapshot = panel.refresh(force=True)
        authoring_snapshot = collect_project_scene_links(self.project_service, self.scene_manager)

        self.assertEqual(len(snapshot["rows"]), 2)
        self.assertEqual(len(authoring_snapshot["rows"]), 2)
        self.assertEqual({row["source_entity_name"] for row in panel._filtered_items(snapshot)}, {"DoorA", "DoorB"})

    def test_collect_project_scene_transitions_prefers_scene_link_rows(self) -> None:
        self._write_scene(
            "linked_scene.json",
            {
                "schema_version": 2,
                "name": "LinkedScene",
                "entities": [
                    {
                        "name": "Portal",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": _transform(0.0, 0.0),
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
                                "target_path": "levels/next.json",
                                "flow_key": "",
                                "preview_label": "Next",
                                "link_mode": "trigger_enter",
                                "target_entry_id": "",
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/next.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnContact": {
                                "enabled": True,
                                "mode": "trigger_enter",
                                "require_player": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
        )
        self._write_scene("next.json", self._entry_scene("Next", []))

        snapshot = collect_project_scene_transitions(self.project_service, self.scene_manager)
        row = next(item for item in snapshot["rows"] if item["source_entity_name"] == "Portal")
        self.assertTrue(row["has_scene_link"])
        self.assertFalse(row["is_runtime_only"])
        self.assertEqual(row["trigger_label"], "Touch / Trigger")

    def test_flow_panel_can_create_scene_link_from_selected_entity(self) -> None:
        self.scene_manager.create_new_scene("Authoring")
        self.assertTrue(
            self.scene_manager.create_entity(
                "Portal",
                components={
                    "Transform": _transform(0.0, 0.0),
                    "Collider": {
                        "enabled": True,
                        "width": 32.0,
                        "height": 32.0,
                        "offset_x": 0.0,
                        "offset_y": 0.0,
                        "is_trigger": True,
                    },
                },
            )
        )
        self.assertTrue(self.scene_manager.set_selected_entity("Portal"))
        panel = SceneFlowPanel()
        panel.set_scene_manager(self.scene_manager)
        panel.set_project_service(self.project_service)

        self.assertTrue(panel._create_or_adopt_scene_link("Portal", None))
        self.assertTrue(panel._set_scene_link_target_scene("Portal", "levels/next.json"))
        self.assertTrue(panel._set_scene_link_mode("Portal", "trigger_enter"))
        scene_link = self.scene_manager.get_component_data("Portal", "SceneLink")
        action = self.scene_manager.get_component_data("Portal", "SceneTransitionAction")
        contact = self.scene_manager.get_component_data("Portal", "SceneTransitionOnContact")
        self.assertEqual(scene_link["target_path"], "levels/next.json")
        self.assertEqual(scene_link["link_mode"], "trigger_enter")
        self.assertEqual(action["target_scene_path"], "levels/next.json")
        self.assertEqual(contact["mode"], "trigger_enter")

    def test_draw_edge_renders_one_way_arrow(self) -> None:
        panel = SceneFlowPanel()
        source_rect = rl.Rectangle(100.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        target_rect = rl.Rectangle(360.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        panel._node_rects = {
            "entity::source": source_rect,
            "target::dest": target_rect,
        }

        with patch("pyray.draw_line_ex") as draw_line_ex, patch("pyray.draw_triangle") as draw_triangle:
            panel._draw_edge(
                {
                    "source_node_key": "entity::source",
                    "target_node_key": "target::dest",
                    "connection_type": "one_way",
                }
            )

        draw_line_ex.assert_called_once()
        draw_triangle.assert_called_once()

    def test_draw_edge_renders_two_way_arrows(self) -> None:
        panel = SceneFlowPanel()
        source_rect = rl.Rectangle(100.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        target_rect = rl.Rectangle(360.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        panel._node_rects = {
            "entity::source": source_rect,
            "entity::target": target_rect,
        }

        with patch("pyray.draw_line_ex") as draw_line_ex, patch("pyray.draw_triangle") as draw_triangle:
            panel._draw_edge(
                {
                    "source_node_key": "entity::source",
                    "target_node_key": "entity::target",
                    "connection_type": "two_way",
                }
            )

        self.assertEqual(draw_line_ex.call_count, 2)
        self.assertEqual(draw_triangle.call_count, 2)

    def test_flow_panel_render_draws_edges_after_preparing_node_rects(self) -> None:
        panel = SceneFlowPanel()
        panel.current_scene_only = False
        panel._snapshot = {
            "sidebar_items": [
                {
                    "sidebar_key": "sidebar::levels/a.json::DoorA",
                    "node_key": "entity::levels/a.json::DoorA",
                    "source_scene_ref": "levels/a.json",
                    "source_scene_path": "levels/a.json",
                    "source_scene_key": "levels/a",
                    "source_scene_name": "SceneA",
                    "source_entity_name": "DoorA",
                    "trigger_label": "Interact Near",
                    "status": "ok",
                    "connected": True,
                },
                {
                    "sidebar_key": "sidebar::levels/b.json::DoorB",
                    "node_key": "entity::levels/b.json::DoorB",
                    "source_scene_ref": "levels/b.json",
                    "source_scene_path": "levels/b.json",
                    "source_scene_key": "levels/b",
                    "source_scene_name": "SceneB",
                    "source_entity_name": "DoorB",
                    "trigger_label": "Interact Near",
                    "status": "ok",
                    "connected": True,
                },
            ],
            "runtime_only_items": [],
            "canvas_nodes": [
                {
                    "node_key": "entity::levels/a.json::DoorA",
                    "kind": "entity",
                    "scene_ref": "levels/a.json",
                    "scene_name": "SceneA",
                    "entity_name": "DoorA",
                    "label": "DoorA",
                    "status": "ok",
                    "x": 0.0,
                    "y": 0.0,
                    "has_stored_position": False,
                    "messages": [],
                },
                {
                    "node_key": "entity::levels/b.json::DoorB",
                    "kind": "entity",
                    "scene_ref": "levels/b.json",
                    "scene_name": "SceneB",
                    "entity_name": "DoorB",
                    "label": "DoorB",
                    "status": "ok",
                    "x": 0.0,
                    "y": 0.0,
                    "has_stored_position": False,
                    "messages": [],
                },
            ],
            "canvas_edges": [
                {
                    "edge_key": "two-way::entity::levels/a.json::DoorA::entity::levels/b.json::DoorB",
                    "source_node_key": "entity::levels/a.json::DoorA",
                    "target_node_key": "entity::levels/b.json::DoorB",
                    "connection_type": "two_way",
                    "source_scene_ref": "levels/a.json",
                    "target_scene_ref": "levels/b.json",
                    "status": "ok",
                    "messages": [],
                }
            ],
            "issues": [],
            "rows": [],
        }
        with patch.object(panel, "refresh", return_value=panel._snapshot), patch(
            "engine.editor.scene_flow_panel.gui_toggle_bool",
            side_effect=lambda rect, _label, value: value,
        ), patch(
            "pyray.gui_button",
            return_value=False,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch("pyray.draw_text"), patch(
            "pyray.draw_circle"
        ), patch("pyray.draw_line_ex") as draw_line_ex, patch(
            "pyray.draw_triangle"
        ) as draw_triangle, patch(
            "pyray.begin_scissor_mode"
        ), patch("pyray.end_scissor_mode"), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_position"), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(0, 0, 960, 320)

        self.assertEqual(draw_line_ex.call_count, 2)
        self.assertEqual(draw_triangle.call_count, 2)
        self.assertIn("entity::levels/a.json::DoorA", panel._node_rects)
        self.assertIn("entity::levels/b.json::DoorB", panel._node_rects)

    def test_left_click_on_entity_node_selects_without_opening_scene(self) -> None:
        panel = SceneFlowPanel()
        node = {
            "node_key": "entity::levels/a.json::DoorA",
            "kind": "entity",
            "scene_ref": "levels/a.json",
            "entity_name": "DoorA",
        }
        panel._node_rects = {
            node["node_key"]: rl.Rectangle(100.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        }
        snapshot = {
            "sidebar_items": [{"node_key": node["node_key"], "sidebar_key": "sidebar::doora"}],
            "canvas_nodes": [node],
        }
        mouse = rl.Vector2(120.0, 96.0)

        with patch("pyray.get_mouse_position", return_value=mouse), patch(
            "pyray.check_collision_point_rec",
            side_effect=lambda point, rect: rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height,
        ), patch("pyray.is_mouse_button_pressed", side_effect=lambda button: button == rl.MOUSE_BUTTON_LEFT), patch(
            "pyray.is_mouse_button_down",
            return_value=False,
        ), patch("pyray.is_mouse_button_released", return_value=False):
            panel._handle_canvas_interactions([node], snapshot)

        self.assertEqual(panel._selected_node_key, node["node_key"])
        self.assertEqual(panel._selected_sidebar_key, "sidebar::doora")
        self.assertEqual(panel._drag_node_key, node["node_key"])
        self.assertIsNone(panel.request_open_source)
        self.assertIsNone(panel.request_open_target)

    def test_left_click_on_target_node_selects_without_opening_scene(self) -> None:
        panel = SceneFlowPanel()
        node = {
            "node_key": "target::levels/b.json::DoorB",
            "kind": "target",
            "scene_ref": "levels/b.json",
            "entity_name": "",
        }
        panel._node_rects = {
            node["node_key"]: rl.Rectangle(360.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        }
        snapshot = {"sidebar_items": [], "canvas_nodes": [node]}
        mouse = rl.Vector2(380.0, 96.0)

        with patch("pyray.get_mouse_position", return_value=mouse), patch(
            "pyray.check_collision_point_rec",
            side_effect=lambda point, rect: rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height,
        ), patch("pyray.is_mouse_button_pressed", side_effect=lambda button: button == rl.MOUSE_BUTTON_LEFT), patch(
            "pyray.is_mouse_button_down",
            return_value=False,
        ), patch("pyray.is_mouse_button_released", return_value=False):
            panel._handle_canvas_interactions([node], snapshot)

        self.assertEqual(panel._selected_node_key, node["node_key"])
        self.assertIsNone(panel.request_open_source)
        self.assertIsNone(panel.request_open_target)

    def test_right_click_on_node_opens_context_menu(self) -> None:
        panel = SceneFlowPanel()
        node = {
            "node_key": "entity::levels/a.json::DoorA",
            "kind": "entity",
            "scene_ref": "levels/a.json",
            "entity_name": "DoorA",
        }
        panel._node_rects = {
            node["node_key"]: rl.Rectangle(100.0, 80.0, float(panel.NODE_WIDTH), float(panel.NODE_HEIGHT))
        }
        snapshot = {
            "sidebar_items": [{"node_key": node["node_key"], "sidebar_key": "sidebar::doora"}],
            "canvas_nodes": [node],
        }
        mouse = rl.Vector2(120.0, 96.0)

        with patch("pyray.get_mouse_position", return_value=mouse), patch(
            "pyray.check_collision_point_rec",
            side_effect=lambda point, rect: rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height,
        ), patch(
            "pyray.is_mouse_button_pressed",
            side_effect=lambda button: button == rl.MOUSE_BUTTON_RIGHT,
        ), patch("pyray.is_mouse_button_down", return_value=False), patch("pyray.is_mouse_button_released", return_value=False):
            panel._handle_canvas_interactions([node], snapshot)

        self.assertTrue(panel._context_menu_active)
        self.assertEqual(panel._context_menu_node_key, node["node_key"])
        self.assertEqual(panel._selected_node_key, node["node_key"])
        self.assertEqual(panel._selected_sidebar_key, "sidebar::doora")

    def test_context_menu_view_in_scene_requests_entity_open(self) -> None:
        panel = SceneFlowPanel()
        panel._panel_rect = rl.Rectangle(0.0, 0.0, 640.0, 360.0)
        panel._context_menu_active = True
        panel._context_menu_pos = rl.Vector2(120.0, 96.0)
        panel._context_menu_node_key = "entity::levels/a.json::DoorA"
        snapshot = {
            "canvas_nodes": [
                {
                    "node_key": "entity::levels/a.json::DoorA",
                    "kind": "entity",
                    "scene_ref": "levels/a.json",
                    "entity_name": "DoorA",
                }
            ]
        }
        menu_rect = panel._context_menu_rect()
        mouse = rl.Vector2(menu_rect.x + 10.0, menu_rect.y + 10.0)

        with patch("pyray.get_mouse_position", return_value=mouse), patch(
            "pyray.check_collision_point_rec",
            side_effect=lambda point, rect: rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height,
        ), patch("pyray.is_mouse_button_pressed", return_value=False), patch(
            "pyray.is_mouse_button_released",
            side_effect=lambda button: button == rl.MOUSE_BUTTON_LEFT,
        ), patch("pyray.draw_rectangle_rec"), patch("pyray.draw_rectangle_lines_ex"), patch("pyray.draw_text"):
            panel._draw_canvas_context_menu(snapshot)

        self.assertEqual(panel.request_open_source, {"scene_ref": "levels/a.json", "entity_name": "DoorA"})
        self.assertFalse(panel._context_menu_active)

    def test_context_menu_click_outside_closes_without_navigation(self) -> None:
        panel = SceneFlowPanel()
        panel._panel_rect = rl.Rectangle(0.0, 0.0, 640.0, 360.0)
        panel._context_menu_active = True
        panel._context_menu_pos = rl.Vector2(120.0, 96.0)
        panel._context_menu_node_key = "target::levels/b.json::DoorB"
        snapshot = {
            "canvas_nodes": [
                {
                    "node_key": "target::levels/b.json::DoorB",
                    "kind": "target",
                    "scene_ref": "levels/b.json",
                    "entity_name": "",
                }
            ]
        }
        mouse = rl.Vector2(12.0, 12.0)

        with patch("pyray.get_mouse_position", return_value=mouse), patch(
            "pyray.check_collision_point_rec",
            side_effect=lambda point, rect: rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height,
        ), patch(
            "pyray.is_mouse_button_pressed",
            side_effect=lambda button: button == rl.MOUSE_BUTTON_LEFT,
        ), patch("pyray.is_mouse_button_released", return_value=False), patch(
            "pyray.draw_rectangle_rec"
        ), patch("pyray.draw_rectangle_lines_ex"), patch("pyray.draw_text"):
            panel._draw_canvas_context_menu(snapshot)

        self.assertFalse(panel._context_menu_active)
        self.assertIsNone(panel.request_open_source)
        self.assertIsNone(panel.request_open_target)


if __name__ == "__main__":
    unittest.main()
