import unittest
from unittest.mock import patch
import json
import tempfile
from pathlib import Path

from engine.components.recttransform import RectTransform
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager
from engine.serialization.schema import CURRENT_SCENE_SCHEMA_VERSION


class SceneManagerSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene_manager = SceneManager(create_default_registry())
        self.scene_manager.load_scene(
            {
                "name": "Sync Probe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 10.0,
                                "y": 20.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_sync_from_edit_world_skips_when_nothing_changed(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(edit_world)

        with patch.object(edit_world, "serialize", wraps=edit_world.serialize) as serialize_mock:
            changed = self.scene_manager.sync_from_edit_world()

        self.assertFalse(changed)
        self.assertEqual(serialize_mock.call_count, 0)

    def test_sync_from_edit_world_skips_transient_preview_without_force(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        transform.x = 144.0
        self.scene_manager.mark_edit_world_dirty(reason="transient_preview")

        with patch.object(edit_world, "serialize", wraps=edit_world.serialize) as serialize_mock:
            changed = self.scene_manager.sync_from_edit_world()

        self.assertFalse(changed)
        self.assertEqual(serialize_mock.call_count, 0)
        self.assertFalse(self.scene_manager.is_dirty)

    def test_pending_world_changes_are_flushed_before_generic_scene_edit(self) -> None:
        self.assertTrue(
            self.scene_manager.add_component_to_entity(
                "Player",
                "Sprite",
                component_data={
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
            )
        )
        edit_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(edit_world)
        player = edit_world.get_entity_by_name("Player")
        self.assertIsNotNone(player)

        sprite = player.get_component(Sprite)
        self.assertIsNotNone(sprite)
        sprite.width = 96
        self.scene_manager.mark_edit_world_dirty()

        updated = self.scene_manager.apply_edit_to_world("Player", "Sprite", "height", 48)
        self.assertTrue(updated)

        refreshed_world = self.scene_manager.get_edit_world()
        refreshed_player = refreshed_world.get_entity_by_name("Player")
        refreshed_sprite = refreshed_player.get_component(Sprite)
        self.assertEqual(refreshed_sprite.width, 96)
        self.assertEqual(refreshed_sprite.height, 48)

    def test_apply_edit_to_world_routes_transform_to_canonical_authoring_path(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(edit_world)
        player = edit_world.get_entity_by_name("Player")
        self.assertIsNotNone(player)

        transform = player.get_component(Transform)
        self.assertIsNotNone(transform)
        transform.x = 144.0
        self.scene_manager.mark_edit_world_dirty()

        with patch.object(
            self.scene_manager,
            "apply_transform_state",
            wraps=self.scene_manager.apply_transform_state,
        ) as transform_mock, patch.object(
            self.scene_manager,
            "_sync_entry_from_edit_world",
            wraps=self.scene_manager._sync_entry_from_edit_world,
        ) as sync_mock:
            updated = self.scene_manager.apply_edit_to_world("Player", "Transform", "y", 88.0)

        self.assertTrue(updated)
        transform_mock.assert_called_once_with(
            "Player",
            {"y": 88.0},
            self.scene_manager.active_scene_key,
            record_history=True,
            label="Player.Transform.y",
        )
        self.assertEqual(sync_mock.call_count, 0)
        refreshed_world = self.scene_manager.get_edit_world()
        refreshed_player = refreshed_world.get_entity_by_name("Player")
        refreshed_transform = refreshed_player.get_component(Transform)
        self.assertEqual(refreshed_transform.x, 10.0)
        self.assertEqual(refreshed_transform.y, 88.0)
        self.assertFalse(self.scene_manager.resolve_entry(self.scene_manager.active_scene_key).edit_world_sync_pending)

    def test_apply_edit_to_world_routes_rect_transform_to_canonical_authoring_path(self) -> None:
        self.assertTrue(
            self.scene_manager.create_entity(
                "Button",
                components={
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
        )
        edit_world = self.scene_manager.get_edit_world()
        button = edit_world.get_entity_by_name("Button")
        rect_transform = button.get_component(RectTransform)
        self.assertIsNotNone(rect_transform)
        rect_transform.anchored_x = 72.0
        self.scene_manager.mark_edit_world_dirty()

        with patch.object(
            self.scene_manager,
            "apply_rect_transform_state",
            wraps=self.scene_manager.apply_rect_transform_state,
        ) as rect_mock, patch.object(
            self.scene_manager,
            "_sync_entry_from_edit_world",
            wraps=self.scene_manager._sync_entry_from_edit_world,
        ) as sync_mock:
            updated = self.scene_manager.apply_edit_to_world("Button", "RectTransform", "height", 96.0)

        self.assertTrue(updated)
        rect_mock.assert_called_once_with(
            "Button",
            {"height": 96.0},
            self.scene_manager.active_scene_key,
            record_history=True,
            label="Button.RectTransform.height",
        )
        self.assertEqual(sync_mock.call_count, 0)
        refreshed_world = self.scene_manager.get_edit_world()
        refreshed_button = refreshed_world.get_entity_by_name("Button")
        refreshed_rect = refreshed_button.get_component(RectTransform)
        self.assertEqual(refreshed_rect.anchored_x, 0.0)
        self.assertEqual(refreshed_rect.height, 96.0)
        self.assertFalse(self.scene_manager.resolve_entry(self.scene_manager.active_scene_key).edit_world_sync_pending)

    def test_apply_transform_state_commits_directly_to_scene_even_with_pending_world_sync(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        self.assertIsNotNone(edit_world)
        player = edit_world.get_entity_by_name("Player")
        self.assertIsNotNone(player)

        transform = player.get_component(Transform)
        self.assertIsNotNone(transform)
        transform.x = 144.0
        self.scene_manager.mark_edit_world_dirty()

        with patch.object(
            self.scene_manager,
            "_sync_entry_from_edit_world",
            wraps=self.scene_manager._sync_entry_from_edit_world,
        ) as sync_mock:
            updated = self.scene_manager.apply_transform_state("Player", {"x": 45.0, "y": 64.0})

        self.assertTrue(updated)
        self.assertEqual(sync_mock.call_count, 0)
        refreshed_world = self.scene_manager.get_edit_world()
        refreshed_player = refreshed_world.get_entity_by_name("Player")
        refreshed_transform = refreshed_player.get_component(Transform)
        self.assertEqual(refreshed_transform.x, 45.0)
        self.assertEqual(refreshed_transform.y, 64.0)
        self.assertFalse(self.scene_manager.resolve_entry(self.scene_manager.active_scene_key).edit_world_sync_pending)

    def test_transient_preview_is_not_flushed_before_generic_scene_edit(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "PreviewProbe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 10.0, "y": 20.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
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
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        edit_world = manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        sprite = player.get_component(Sprite)
        sprite.width = 96
        manager.mark_edit_world_dirty(reason="transient_preview")

        with patch.object(
            manager,
            "_sync_entry_from_edit_world",
            wraps=manager._sync_entry_from_edit_world,
        ) as sync_mock:
            updated = manager.apply_edit_to_world("Player", "Sprite", "height", 48)

        self.assertTrue(updated)
        self.assertEqual(sync_mock.call_count, 0)
        refreshed_sprite = manager.get_edit_world().get_entity_by_name("Player").get_component(Sprite)
        self.assertEqual(refreshed_sprite.width, 32)
        self.assertEqual(refreshed_sprite.height, 48)

    def test_save_scene_to_file_ignores_transient_preview_and_cancels_it(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        transform.x = 144.0
        self.scene_manager.mark_edit_world_dirty(reason="transient_preview")

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "transient_preview_scene.json"
            self.assertTrue(self.scene_manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

        self.assertEqual(persisted["entities"][0]["components"]["Transform"]["x"], 10.0)
        refreshed_transform = self.scene_manager.get_edit_world().get_entity_by_name("Player").get_component(Transform)
        self.assertEqual(refreshed_transform.x, 10.0)
        self.assertFalse(self.scene_manager.resolve_entry(self.scene_manager.active_scene_key).edit_world_sync_pending)
        self.assertFalse(self.scene_manager.is_dirty)

    def test_save_scene_to_file_flushes_legacy_pending_world_changes(self) -> None:
        edit_world = self.scene_manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        transform.x = 77.0
        self.scene_manager.mark_edit_world_dirty(reason="legacy_authoring")

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "legacy_pending_scene.json"
            self.assertTrue(self.scene_manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

        self.assertEqual(persisted["entities"][0]["components"]["Transform"]["x"], 77.0)
        self.assertEqual(self.scene_manager.current_scene.find_entity("Player")["components"]["Transform"]["x"], 77.0)

    def test_sync_from_edit_world_preserves_rules_and_feature_metadata(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "Roundtrip",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Hero",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 10.0, "y": 20.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
                        },
                    }
                ],
                "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "keep"}]}],
                "feature_metadata": {
                    "scene_flow": {"next_scene": "levels/next.json"},
                    "render_2d": {"sorting_layers": ["Default", "Foreground"]},
                },
            }
        )

        edit_world = manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        transform.x = 77.0
        manager.mark_edit_world_dirty()

        changed = manager.sync_from_edit_world(force=True)

        self.assertTrue(changed)
        payload = manager.current_scene.to_dict()
        self.assertEqual(payload["rules"], [{"event": "tick", "do": [{"action": "log_message", "message": "keep"}]}])
        self.assertEqual(payload["feature_metadata"]["scene_flow"], {"next_scene": "levels/next.json"})
        self.assertEqual(payload["feature_metadata"]["render_2d"]["sorting_layers"], ["Default", "Foreground"])
        self.assertEqual(payload["entities"][0]["components"]["Transform"]["x"], 77.0)

    def test_save_and_reload_roundtrip_preserves_core_scene_payload(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "SaveRoundtrip",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Canvas": {"enabled": True, "render_mode": "screen_space_overlay", "reference_width": 800, "reference_height": 600, "match_mode": "stretch", "sort_order": 0},
                        },
                    },
                    {
                        "name": "PlayButton",
                        "parent": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Transform": {"enabled": True, "x": 24.0, "y": 12.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "UIButton": {
                                "enabled": True,
                                "interactable": True,
                                "label": "Play",
                                "normal_color": [72, 72, 72, 255],
                                "hover_color": [92, 92, 92, 255],
                                "pressed_color": [56, 56, 56, 255],
                                "disabled_color": [48, 48, 48, 200],
                                "transition_scale_pressed": 0.96,
                                "on_click": {"type": "load_scene_flow", "target": "next_scene"},
                            },
                        },
                    },
                ],
                "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "saved"}]}],
                "feature_metadata": {
                    "scene_flow": {"next_scene": "levels/next.json"},
                    "render_2d": {"sorting_layers": ["Default", "UI"]},
                },
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "roundtrip_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

            reloaded = SceneManager(create_default_registry())
            reloaded.load_scene_from_file(scene_path.as_posix())
            payload = reloaded.current_scene.to_dict()
            world = reloaded.get_edit_world()
            button = world.get_entity_by_name("PlayButton")

        self.assertEqual(persisted["rules"], [{"event": "tick", "do": [{"action": "log_message", "message": "saved"}]}])
        self.assertEqual(persisted["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)
        self.assertEqual(persisted["feature_metadata"]["scene_flow"], {"next_scene": "levels/next.json"})
        self.assertEqual(payload["feature_metadata"]["render_2d"]["sorting_layers"], ["Default", "UI"])
        self.assertEqual(payload["entities"][1]["parent"], "CanvasRoot")
        self.assertEqual(payload["entities"][1]["components"]["UIButton"]["on_click"]["target"], "next_scene")
        self.assertIsNotNone(button)
        self.assertEqual(button.parent_name, "CanvasRoot")

    def test_set_feature_metadata_updates_scene_and_edit_world(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "FeatureMetadata",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            }
        )

        updated = manager.set_feature_metadata("input_profile", {"source": "api"})

        self.assertTrue(updated)
        self.assertTrue(manager.is_dirty)
        self.assertEqual(manager.current_scene.feature_metadata["input_profile"], {"source": "api"})
        self.assertEqual(manager.get_edit_world().feature_metadata["input_profile"], {"source": "api"})

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "feature_metadata_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

            reloaded = SceneManager(create_default_registry())
            reloaded.load_scene_from_file(scene_path.as_posix())

        self.assertEqual(persisted["feature_metadata"]["input_profile"], {"source": "api"})
        self.assertEqual(reloaded.current_scene.feature_metadata["input_profile"], {"source": "api"})

    def test_signal_feature_metadata_roundtrips_through_save_and_reload(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "SignalMetadata",
                "entities": [
                    {
                        "name": "Emitter",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        signals = {
            "connections": [
                {
                    "id": "emit_to_event",
                    "source": {"id": "Emitter", "signal": "pressed"},
                    "target": {"kind": "event_bus"},
                    "callable": {"event": "ui.emitter_pressed"},
                    "flags": ["deferred"],
                    "binds": [{"button": "left"}],
                    "description": "Emitir click al bus",
                }
            ]
        }

        updated = manager.set_feature_metadata("signals", signals)

        self.assertTrue(updated)
        self.assertEqual(manager.current_scene.list_signal_connections(), signals["connections"])
        self.assertEqual(manager.get_edit_world().feature_metadata["signals"], signals)

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "signal_metadata_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

            reloaded = SceneManager(create_default_registry())
            reloaded.load_scene_from_file(scene_path.as_posix())

        self.assertEqual(persisted["feature_metadata"]["signals"], signals)
        self.assertEqual(reloaded.current_scene.list_signal_connections(), signals["connections"])

    def test_entity_groups_roundtrip_through_save_reload_and_edit_world(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "EntityGroups",
                "entities": [
                    {
                        "name": "EnemySpawner",
                        "active": True,
                        "tag": "Spawner",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        updated = manager.set_entity_groups("EnemySpawner", ["Enemies", " Gameplay ", "Enemies", ""])

        self.assertTrue(updated)
        self.assertEqual(manager.current_scene.get_entity_groups("EnemySpawner"), ["Enemies", "Gameplay"])
        self.assertEqual(manager.current_scene.find_entity("EnemySpawner")["groups"], ["Enemies", "Gameplay"])
        self.assertEqual(list(manager.get_edit_world().get_entity_by_name("EnemySpawner").groups), ["Enemies", "Gameplay"])

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "entity_groups_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

            reloaded = SceneManager(create_default_registry())
            reloaded.load_scene_from_file(scene_path.as_posix())

        self.assertEqual(persisted["entities"][0]["groups"], ["Enemies", "Gameplay"])
        self.assertEqual(reloaded.current_scene.get_entity_groups("EnemySpawner"), ["Enemies", "Gameplay"])
        self.assertEqual(list(reloaded.get_edit_world().get_entity_by_name("EnemySpawner").groups), ["Enemies", "Gameplay"])

    def test_invalid_camera_zoom_edit_is_rejected_and_save_remains_reloadable(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "CameraValidation",
                "entities": [
                    {
                        "name": "Camera",
                        "active": True,
                        "tag": "MainCamera",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Camera2D": {
                                "enabled": True,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "zoom": 1.0,
                                "rotation": 0.0,
                                "is_primary": True,
                                "follow_entity": "",
                                "framing_mode": "platformer",
                                "dead_zone_width": 0.0,
                                "dead_zone_height": 0.0,
                                "clamp_left": None,
                                "clamp_right": None,
                                "clamp_top": None,
                                "clamp_bottom": None,
                                "recenter_on_play": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        before = manager.current_scene.to_dict()

        updated = manager.apply_edit_to_world("Camera", "Camera2D", "zoom", 0.0)

        self.assertFalse(updated)
        self.assertEqual(manager.current_scene.to_dict(), before)

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "camera_validation_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))

        self.assertEqual(reloaded.current_scene.find_entity("Camera")["components"]["Camera2D"]["zoom"], 1.0)

    def test_invalid_physics_backend_metadata_is_rejected_and_save_remains_reloadable(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "PhysicsValidation",
                "entities": [],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )

        before = manager.current_scene.to_dict()

        updated = manager.set_feature_metadata("physics_2d", {"backend": "ghost"})

        self.assertFalse(updated)
        self.assertEqual(manager.current_scene.to_dict(), before)

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "physics_validation_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))

        self.assertEqual(reloaded.current_scene.feature_metadata["physics_2d"]["backend"], "legacy_aabb")

    def test_invalid_ui_text_alignment_is_rejected_and_save_remains_reloadable(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "UITextValidation",
                "entities": [
                    {
                        "name": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 0,
                            },
                        },
                    },
                    {
                        "name": "Label",
                        "parent": "CanvasRoot",
                        "active": True,
                        "tag": "UI",
                        "layer": "UI",
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
                                "height": 60.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "UIText": {
                                "enabled": True,
                                "text": "Play",
                                "font_size": 24,
                                "color": [255, 255, 255, 255],
                                "alignment": "center",
                            },
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        before = manager.current_scene.to_dict()

        updated = manager.replace_component_data(
            "Label",
            "UIText",
            {
                "enabled": True,
                "text": "Play",
                "font_size": 24,
                "color": [255, 255, 255, 255],
                "alignment": "justify",
            },
        )

        self.assertFalse(updated)
        self.assertEqual(manager.current_scene.to_dict(), before)

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "ui_text_validation_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))

        self.assertEqual(reloaded.current_scene.find_entity("Label")["components"]["UIText"]["alignment"], "center")

    def test_invalid_legacy_authoring_snapshot_is_rejected_cleanly_before_serializable_edit(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "LegacyFlushRejection",
                "entities": [
                    {
                        "name": "Camera",
                        "active": True,
                        "tag": "MainCamera",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Camera2D": {
                                "enabled": True,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "zoom": 1.0,
                                "rotation": 0.0,
                                "is_primary": True,
                                "follow_entity": "",
                                "framing_mode": "platformer",
                                "dead_zone_width": 0.0,
                                "dead_zone_height": 0.0,
                                "clamp_left": None,
                                "clamp_right": None,
                                "clamp_top": None,
                                "clamp_bottom": None,
                                "recenter_on_play": True,
                            },
                        },
                    },
                    {
                        "name": "Actor",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 4.0, "y": 6.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
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
                    },
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        before = manager.current_scene.to_dict()
        entry = manager.resolve_entry(manager.active_scene_key)
        edit_world = manager.get_edit_world()
        camera = edit_world.get_entity_by_name("Camera")
        camera_component = next(component for component in camera.get_all_components() if type(component).__name__ == "Camera2D")
        camera_component.zoom = 0.0
        manager.mark_edit_world_dirty(reason="legacy_authoring")

        self.assertTrue(manager.is_dirty)
        self.assertTrue(entry.edit_world_sync_pending)

        updated = manager.apply_edit_to_world("Actor", "Sprite", "height", 48)

        self.assertFalse(updated)
        self.assertEqual(manager.current_scene.to_dict(), before)
        self.assertFalse(entry.edit_world_sync_pending)
        self.assertFalse(manager.is_dirty)
        restored_camera = manager.get_edit_world().get_entity_by_name("Camera")
        restored_component = next(component for component in restored_camera.get_all_components() if type(component).__name__ == "Camera2D")
        self.assertEqual(restored_component.zoom, 1.0)

        retried = manager.apply_edit_to_world("Actor", "Sprite", "height", 48)

        self.assertTrue(retried)
        self.assertTrue(manager.is_dirty)
        self.assertEqual(manager.current_scene.find_entity("Actor")["components"]["Sprite"]["height"], 48)

    def test_save_rejects_invalid_legacy_authoring_snapshot_and_restores_sane_state(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "LegacyFlushSave",
                "entities": [
                    {
                        "name": "Camera",
                        "active": True,
                        "tag": "MainCamera",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Camera2D": {
                                "enabled": True,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "zoom": 1.0,
                                "rotation": 0.0,
                                "is_primary": True,
                                "follow_entity": "",
                                "framing_mode": "platformer",
                                "dead_zone_width": 0.0,
                                "dead_zone_height": 0.0,
                                "clamp_left": None,
                                "clamp_right": None,
                                "clamp_top": None,
                                "clamp_bottom": None,
                                "recenter_on_play": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        entry = manager.resolve_entry(manager.active_scene_key)

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "legacy_flush_save_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            persisted_before = scene_path.read_text(encoding="utf-8")

            edit_world = manager.get_edit_world()
            camera = edit_world.get_entity_by_name("Camera")
            camera_component = next(component for component in camera.get_all_components() if type(component).__name__ == "Camera2D")
            camera_component.zoom = 0.0
            manager.mark_edit_world_dirty(reason="legacy_authoring")

            self.assertFalse(manager.save_scene_to_file(scene_path.as_posix()))
            self.assertEqual(scene_path.read_text(encoding="utf-8"), persisted_before)
            self.assertFalse(entry.edit_world_sync_pending)
            self.assertFalse(manager.is_dirty)

            restored_camera = manager.get_edit_world().get_entity_by_name("Camera")
            restored_component = next(component for component in restored_camera.get_all_components() if type(component).__name__ == "Camera2D")
            self.assertEqual(restored_component.zoom, 1.0)

            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))

    def test_save_scene_to_file_rejects_invalid_scene_and_preserves_existing_file(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "SaveGate",
                "entities": [
                    {
                        "name": "Camera",
                        "active": True,
                        "tag": "MainCamera",
                        "layer": "Default",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Camera2D": {
                                "enabled": True,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "zoom": 1.0,
                                "rotation": 0.0,
                                "is_primary": True,
                                "follow_entity": "",
                                "framing_mode": "platformer",
                                "dead_zone_width": 0.0,
                                "dead_zone_height": 0.0,
                                "clamp_left": None,
                                "clamp_right": None,
                                "clamp_top": None,
                                "clamp_bottom": None,
                                "recenter_on_play": True,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "save_gate_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            persisted_before = scene_path.read_text(encoding="utf-8")

            manager.current_scene.find_entity("Camera")["components"]["Camera2D"]["zoom"] = 0.0

            self.assertFalse(manager.save_scene_to_file(scene_path.as_posix()))
            self.assertEqual(scene_path.read_text(encoding="utf-8"), persisted_before)

            reloaded = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))

        self.assertEqual(reloaded.current_scene.find_entity("Camera")["components"]["Camera2D"]["zoom"], 1.0)

    def test_transform_edit_save_and_reload_preserves_selection(self) -> None:
        self.assertTrue(self.scene_manager.set_selected_entity("Player"))
        self.assertTrue(self.scene_manager.apply_edit_to_world("Player", "Transform", "x", 33.0))

        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "selected_transform_scene.json"
            self.assertTrue(self.scene_manager.save_scene_to_file(scene_path.as_posix()))
            persisted = json.loads(scene_path.read_text(encoding="utf-8"))

        self.assertEqual(self.scene_manager.get_edit_world().selected_entity_name, "Player")
        reloaded_world = self.scene_manager.reload_scene()
        self.assertIsNotNone(reloaded_world)
        self.assertEqual(reloaded_world.selected_entity_name, "Player")
        self.assertEqual(persisted["entities"][0]["components"]["Transform"]["x"], 33.0)
        self.assertEqual(self.scene_manager.current_scene.find_entity("Player")["components"]["Transform"]["x"], 33.0)


if __name__ == "__main__":
    unittest.main()
