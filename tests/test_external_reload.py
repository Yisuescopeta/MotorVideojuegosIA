import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pyray as rl

sys.path.append(os.getcwd())

from engine.core.game import Game
from engine.components.transform import Transform
from engine.editor.editor_layout import EditorLayout
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager


class GameExternalReloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "ReloadProject"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.scene_path = self.project_root / "levels" / "reload_scene.json"
        self.asset_path = self.project_root / "assets" / "hero.png"
        self.asset_path.parent.mkdir(parents=True, exist_ok=True)
        self.asset_path.write_bytes(b"old-bytes")
        self._write_scene(x=10.0, y=20.0)

        self.game = Game()
        self.game.set_scene_manager(SceneManager(create_default_registry()))
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            self.game.editor_layout = EditorLayout(1280, 720)
        self.game.set_project_service(self.project_service)
        self.game.set_scene_manager(self.game._scene_manager)
        self.assertTrue(self.game.load_scene_by_path(self.scene_path.as_posix()))
        self.game.editor_layout.editor_camera.target = rl.Vector2(120.0, -45.0)
        self.game.editor_layout.editor_camera.zoom = 1.6
        self.game._prime_external_change_snapshot()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, *, x: float, y: float) -> None:
        self.scene_path.parent.mkdir(parents=True, exist_ok=True)
        self.scene_path.write_text(
            json.dumps(
                {
                    "name": "Reload Scene",
                    "entities": [
                        {
                            "name": "Player",
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
                                }
                            },
                        }
                    ],
                    "rules": [],
                    "feature_metadata": {},
                },
                indent=4,
            ),
            encoding="utf-8",
        )

    def _poll_once(self) -> None:
        self.game._external_last_poll_time = 0.0
        with patch("time.perf_counter", return_value=10.0):
            self.game._poll_external_project_changes()

    def test_clean_scene_reload_applies_disk_changes(self) -> None:
        self.game._scene_manager.set_selected_entity("Player")
        self._write_scene(x=96.0, y=64.0)

        self._poll_once()

        world = self.game.world
        player = world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        self.assertEqual(transform.x, 96.0)
        self.assertEqual(transform.y, 64.0)
        self.assertEqual(world.selected_entity_name, "Player")
        self.assertEqual(self.game.editor_layout.editor_camera.target.x, 120.0)
        self.assertEqual(self.game.editor_layout.editor_camera.target.y, -45.0)
        self.assertAlmostEqual(self.game.editor_layout.editor_camera.zoom, 1.6, places=4)
        self.assertEqual(self.game._external_change_applied_count, 1)
        self.assertEqual(len(self.game._external_conflict_paths), 0)

    def test_dirty_scene_blocks_external_reload_and_tracks_conflict(self) -> None:
        self.assertTrue(self.game._scene_manager.apply_edit_to_world("Player", "Transform", "x", 55.0))
        self._write_scene(x=101.0, y=20.0)

        self._poll_once()

        world = self.game.world
        player = world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        self.assertEqual(transform.x, 55.0)
        self.assertIn(self.scene_path.resolve().as_posix(), self.game._external_conflict_paths)
        self.assertEqual(self.game._external_change_applied_count, 0)

    def test_asset_change_invalidates_project_resources(self) -> None:
        render_system = Mock()
        render_system.reset_project_resources = Mock()
        render_system.set_project_service = Mock()
        self.game._render_system = render_system

        self.asset_path.write_bytes(b"new-bytes")

        self._poll_once()

        render_system.reset_project_resources.assert_called_once()
        render_system.set_project_service.assert_called_once_with(self.project_service)
        self.assertEqual(self.game._external_change_applied_count, 1)


if __name__ == "__main__":
    unittest.main()
