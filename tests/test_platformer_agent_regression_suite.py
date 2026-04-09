import unittest
from unittest.mock import patch

from engine.components.animator import Animator
from engine.components.transform import Transform
from tests_support.platformer_regression_harness import RegressionProjectHarness


class PlatformerAgentRegressionSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = RegressionProjectHarness()
        self.api = self.harness.api

    def tearDown(self) -> None:
        self.harness.close()

    def test_variable_slice_animation_keeps_visual_anchor_stable(self) -> None:
        self.harness.load_level_fixture("platformer_runtime_scene.json")
        self.harness.attach_fake_slice_service(
            {
                "idle_small": {"x": 0, "y": 0, "width": 20, "height": 30, "pivot_x": 0.5, "pivot_y": 1.0},
                "idle_big": {"x": 20, "y": 0, "width": 36, "height": 48, "pivot_x": 0.5, "pivot_y": 1.0},
            }
        )
        self.harness.attach_fake_texture_loader()

        entity = self.api.game.world.get_entity_by_name("HeroAnimator")
        transform = entity.get_component(Transform)
        animator = entity.get_component(Animator)
        render_system = self.api.game.render_system

        draw_calls: list[dict[str, float]] = []

        def _capture_draw(_texture, _source, dest, _origin, _rotation, _tint) -> None:
            draw_calls.append(
                {
                    "x": float(dest.x),
                    "y": float(dest.y),
                    "width": float(dest.width),
                    "height": float(dest.height),
                }
            )

        with patch("engine.systems.render_system.rl.draw_texture_pro", side_effect=_capture_draw):
            render_system._draw_animated_sprite(transform, animator)
            animator.current_frame = 1
            render_system._draw_animated_sprite(transform, animator)

        self.assertEqual(len(draw_calls), 2)
        for payload in draw_calls:
            self.assertAlmostEqual(payload["x"] + (payload["width"] * 0.5), 100.0, places=4)
            self.assertAlmostEqual(payload["y"] + payload["height"], 200.0, places=4)

    def test_grounding_fixture_lands_and_stays_grounded(self) -> None:
        self.harness.load_level_fixture("platformer_runtime_scene.json")
        self.api.play()
        self.api.step(20)
        first_snapshot = self.api.get_runtime_debug_snapshot()
        self.api.step(10)
        second_snapshot = self.api.get_runtime_debug_snapshot()

        rigidbodies_first = {entry["entity"]: entry for entry in first_snapshot["physics"]["rigidbodies"]}
        rigidbodies_second = {entry["entity"]: entry for entry in second_snapshot["physics"]["rigidbodies"]}
        contacts = second_snapshot["physics"]["contacts"]
        player = self.api.get_entity("Player")

        self.assertTrue(rigidbodies_first["Player"]["grounded"])
        self.assertTrue(rigidbodies_second["Player"]["contact_state"]["grounded"])
        self.assertAlmostEqual(player["components"]["Transform"]["y"], 25.0, places=2)
        self.assertIn("floor", {entry["contact_type"] for entry in contacts})

    def test_tilemap_fixture_renders_atlas_tiles_and_generates_collision(self) -> None:
        self.harness.load_level_fixture("tilemap_runtime_scene.json")
        self.harness.attach_fake_slice_service(
            {
                "terrain_wall_a": {"x": 0, "y": 0, "width": 16, "height": 16},
                "terrain_wall_b": {"x": 16, "y": 0, "width": 16, "height": 16},
            }
        )
        graph = self.harness.build_raw_render_graph()
        world_commands = graph["passes"][0]["commands"]
        tile_command = next(command for command in world_commands if command.get("entity_name") == "Map")
        tile_chunk = tile_command["chunk_data"]

        self.assertEqual(tile_chunk["atlas_id"], "assets/terrain_atlas.png")
        self.assertEqual(tile_chunk["textured_tile_count"], 2)
        self.assertEqual(tile_chunk["fallback_tile_count"], 0)

        self.api.play()
        self.api.step(20)
        hero = self.api.get_entity("Hero")
        self.assertLess(hero["components"]["Transform"]["x"], 32.0)
        self.assertIn("on_collision", self.harness.recent_event_names())

    def test_ui_menu_fixture_is_navigable_via_engine_api_without_scripts(self) -> None:
        self.harness.load_level_fixture("ui_menu_scene.json")
        self.assertTrue(self.api.create_canvas(name="MenuCanvas", initial_focus_entity_id="PlayButton")["success"])
        self.assertTrue(
            self.api.create_ui_button(
                "PlayButton",
                "Play",
                "MenuCanvas",
                {"width": 220.0, "height": 72.0, "anchored_y": -80.0},
                {"type": "emit_event", "name": "ui.play_clicked"},
                nav_down="QuitButton",
            )["success"]
        )
        self.assertTrue(
            self.api.create_ui_button(
                "QuitButton",
                "Quit",
                "MenuCanvas",
                {"width": 220.0, "height": 72.0, "anchored_y": 20.0},
                {"type": "emit_event", "name": "ui.quit_clicked"},
                nav_up="PlayButton",
            )["success"]
        )

        focus = self.api.get_ui_focus()
        self.assertEqual(focus["focused_entity"], "PlayButton")
        move = self.api.ui_move_focus("down")
        self.assertTrue(move["success"])
        self.assertEqual(move["data"]["focused_entity"], "QuitButton")

        self.api.play()
        self.api.game.event_bus.clear_history()
        self.assertTrue(self.api.ui_submit()["success"])
        self.assertIn("ui.quit_clicked", self.harness.recent_event_names())

        self.api.game.event_bus.clear_history()
        self.assertTrue(self.api.ui_cancel()["success"])
        self.assertIn("ui.cancel", self.harness.recent_event_names())

    def test_critical_agent_workflows_remain_available_via_engine_api(self) -> None:
        required_methods = [
            "get_runtime_debug_snapshot",
            "preview_auto_slices",
            "apply_manual_slices",
            "build_animation_from_slices",
            "create_animator_state_from_slices",
            "create_tilemap",
            "bulk_set_tilemap_tiles",
            "configure_tilemap_tileset",
            "get_ui_focus",
            "focus_entity",
            "ui_move_focus",
            "ui_submit",
            "ui_cancel",
            "snap_entities_to_grid",
            "duplicate_entities",
            "stamp_prefab",
        ]
        for method_name in required_methods:
            self.assertTrue(hasattr(self.api, method_name), msg=f"EngineAPI missing {method_name}")


if __name__ == "__main__":
    unittest.main()
