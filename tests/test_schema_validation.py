import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.assets.prefab import PrefabManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_transition_support import validate_scene_transition_references
from engine.serialization.schema import (
    CURRENT_PREFAB_SCHEMA_VERSION,
    CURRENT_SCENE_SCHEMA_VERSION,
    build_canonical_scene_payload,
    migrate_prefab_data,
    migrate_scene_data,
    validate_prefab_data,
    validate_scene_data,
)

ROOT = Path(__file__).resolve().parents[1]


def _transform_component() -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": 0.0,
        "y": 0.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _scene_payload(
    *,
    entities: list[dict[str, object]] | None = None,
    rules: list[dict[str, object]] | None = None,
    feature_metadata: dict[str, object] | None = None,
    name: str = "Scene",
) -> dict[str, object]:
    return {
        "name": name,
        "entities": entities or [],
        "rules": rules or [],
        "feature_metadata": feature_metadata or {},
    }


def _entity_payload(
    name: str,
    *,
    components: dict[str, object] | None = None,
    tag: str = "Untagged",
    layer: str = "Default",
) -> dict[str, object]:
    return {
        "name": name,
        "active": True,
        "tag": tag,
        "layer": layer,
        "components": components or {"Transform": _transform_component()},
    }


class SchemaValidationTests(unittest.TestCase):
    def test_legacy_scene_payload_migrates_to_current_schema(self) -> None:
        legacy = {"name": "Legacy", "entities": [], "rules": []}
        migrated = migrate_scene_data(legacy)
        self.assertEqual(migrated["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)
        self.assertEqual(validate_scene_data(migrated), [])

    def test_scene_v1_collider_is_canonicalized_to_v2(self) -> None:
        migrated = migrate_scene_data(
            {
                "schema_version": 1,
                "name": "LegacyCollider",
                "entities": [
                    {
                        "name": "Wall",
                        "components": {
                            "Collider": {"enabled": True, "width": 20.0, "height": 8.0, "offset_x": 0.0, "offset_y": 0.0}
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        collider = migrated["entities"][0]["components"]["Collider"]
        self.assertEqual(migrated["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)
        self.assertEqual(collider["shape_type"], "box")
        self.assertEqual(collider["radius"], 10.0)
        self.assertEqual(collider["points"], [])
        self.assertEqual(collider["friction"], 0.2)
        self.assertEqual(collider["restitution"], 0.0)
        self.assertEqual(collider["density"], 1.0)

    def test_scene_v1_rigidbody_is_canonicalized_to_v2(self) -> None:
        migrated = migrate_scene_data(
            {
                "schema_version": 1,
                "name": "LegacyRigidBody",
                "entities": [
                    {
                        "name": "Body",
                        "components": {
                            "RigidBody": {
                                "enabled": True,
                                "velocity_x": 3.0,
                                "velocity_y": 4.0,
                                "gravity_scale": 1.0,
                                "constraints": ["FreezePositionX"],
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        rigidbody = migrated["entities"][0]["components"]["RigidBody"]
        self.assertEqual(migrated["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)
        self.assertEqual(rigidbody["body_type"], "dynamic")
        self.assertTrue(rigidbody["simulated"])
        self.assertTrue(rigidbody["freeze_x"])
        self.assertFalse(rigidbody["freeze_y"])
        self.assertEqual(rigidbody["constraints"], ["FreezePositionX"])
        self.assertFalse(rigidbody["use_full_kinematic_contacts"])
        self.assertEqual(rigidbody["collision_detection_mode"], "discrete")

    def test_scene_v1_animator_string_asset_ref_is_canonicalized_to_v2(self) -> None:
        migrated = migrate_scene_data(
            {
                "schema_version": 1,
                "name": "LegacyAnimator",
                "entities": [
                    {
                        "name": "Player",
                        "components": {
                            "Animator": {
                                "enabled": True,
                                "sprite_sheet": "assets/sprites/player_sheet.png",
                                "frame_width": 32,
                                "frame_height": 32,
                                "default_state": "idle",
                                "current_state": "idle",
                                "animations": {"idle": {"frames": [0], "fps": 8.0, "loop": True}},
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        animator = migrated["entities"][0]["components"]["Animator"]
        self.assertEqual(animator["sprite_sheet"], {"guid": "", "path": "assets/sprites/player_sheet.png"})
        self.assertEqual(animator["sprite_sheet_path"], "assets/sprites/player_sheet.png")

    def test_animator_controller_is_canonicalized_with_defaults(self) -> None:
        migrated = migrate_scene_data(
            {
                "name": "AnimatorControllerScene",
                "entities": [
                    {
                        "name": "Player",
                        "components": {
                            "Animator": {
                                "enabled": True,
                                "sprite_sheet": "assets/sprites/player_sheet.png",
                                "frame_width": 32,
                                "frame_height": 32,
                                "default_state": "idle",
                                "current_state": "idle",
                                "animations": {"idle": {"frames": [0], "fps": 8.0, "loop": True}},
                            },
                            "AnimatorController": {},
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        controller = migrated["entities"][0]["components"]["AnimatorController"]
        self.assertEqual(controller["enabled"], True)
        self.assertEqual(controller["entry_state"], "")
        self.assertEqual(controller["parameters"], {})
        self.assertEqual(controller["states"], {})
        self.assertEqual(controller["transitions"], [])

    def test_scene_validation_rejects_animator_controller_without_animator(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                entities=[
                    _entity_payload(
                        "Actor",
                        components={
                            "AnimatorController": {
                                "enabled": True,
                                "entry_state": "",
                                "parameters": {},
                                "states": {},
                                "transitions": [],
                            }
                        },
                    )
                ]
            )
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.entities[0].components.AnimatorController: requires Animator on the same entity", errors)

    def test_scene_validation_rejects_animator_controller_states_pointing_to_missing_clip(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                entities=[
                    _entity_payload(
                        "Actor",
                        components={
                            "Animator": {
                                "enabled": True,
                                "sprite_sheet": "assets/actor.png",
                                "sprite_sheet_path": "assets/actor.png",
                                "frame_width": 16,
                                "frame_height": 16,
                                "default_state": "idle",
                                "current_state": "idle",
                                "animations": {"idle": {"frames": [0], "fps": 8.0, "loop": True}},
                            },
                            "AnimatorController": {
                                "enabled": True,
                                "entry_state": "logic_idle",
                                "parameters": {"speed": {"type": "float", "default": 0.0}},
                                "states": {"logic_idle": {"animation_state": "run", "enter_events": [], "exit_events": []}},
                                "transitions": [],
                            },
                        },
                    )
                ]
            )
        )
        errors = validate_scene_data(payload)
        self.assertTrue(
            any("AnimatorController.states.logic_idle.animation_state: unknown animator state 'run'" in error for error in errors),
            errors,
        )

    def test_scene_manager_save_includes_schema_version(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene({"name": "SaveMe", "entities": [], "rules": [], "feature_metadata": {}})
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            payload = json.loads(scene_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)

    def test_prefab_manager_loads_legacy_prefab_and_assigns_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            prefab_path = Path(temp_dir) / "enemy.prefab"
            prefab_path.write_text(
                json.dumps({"name": "Enemy", "components": {"Transform": _transform_component()}}),
                encoding="utf-8",
            )
            payload = PrefabManager.load_prefab_data(prefab_path.as_posix())
        self.assertIsNotNone(payload)
        self.assertEqual(payload["schema_version"], CURRENT_PREFAB_SCHEMA_VERSION)

    def test_prefab_legacy_override_map_is_canonicalized_to_operations(self) -> None:
        migrated = migrate_prefab_data(
            {
                "schema_version": 1,
                "root_name": "Enemy",
                "entities": [
                    {
                        "name": "Enemy",
                        "components": {"Transform": _transform_component()},
                        "prefab_instance": {
                            "prefab_path": "prefabs/enemy.prefab",
                            "root_name": "Enemy",
                            "overrides": {"": {"active": False, "components": {"Transform": {"x": 5.0}}}},
                        },
                    }
                ],
            }
        )
        overrides = migrated["entities"][0]["prefab_instance"]["overrides"]
        self.assertIn("operations", overrides)
        self.assertTrue(any(operation["op"] == "set_entity_property" for operation in overrides["operations"]))
        self.assertTrue(any(operation["op"] == "replace_component" for operation in overrides["operations"]))

    def test_tilemap_payload_migrates_and_validates(self) -> None:
        legacy = {
            "name": "TilemapScene",
            "entities": [
                {
                    "name": "Grid",
                    "components": {
                        "Tilemap": {
                            "layers": [
                                {
                                    "name": "Ground",
                                    "tiles": [{"x": 0, "y": 0, "tile_id": "grass"}],
                                }
                            ]
                        }
                    },
                }
            ],
            "rules": [],
        }
        migrated = migrate_scene_data(legacy)
        self.assertEqual(validate_scene_data(migrated), [])

    def test_scene_validation_accepts_valid_hierarchy(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "Hierarchy",
                "entities": [
                    {"name": "Root", "components": {"Transform": _transform_component()}},
                    {"name": "Child", "parent": "Root", "components": {"Transform": _transform_component()}},
                    {"name": "GrandChild", "parent": "Child", "components": {"Transform": _transform_component()}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        self.assertEqual(validate_scene_data(payload), [])

    def test_scene_validation_rejects_missing_parent(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenHierarchy",
                "entities": [
                    {"name": "Child", "parent": "Ghost", "components": {"Transform": _transform_component()}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.entities[0].parent: unknown parent 'Ghost'", errors)

    def test_scene_validation_rejects_hierarchy_cycle(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenHierarchy",
                "entities": [
                    {"name": "A", "parent": "B", "components": {"Transform": _transform_component()}},
                    {"name": "B", "parent": "A", "components": {"Transform": _transform_component()}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertTrue(any("cycle detected involving" in error for error in errors))

    def test_scene_validation_rejects_self_parent(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenHierarchy",
                "entities": [
                    {"name": "Solo", "parent": "Solo", "components": {"Transform": _transform_component()}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.entities[0].parent: entity cannot be its own parent", errors)

    def test_scene_validation_rejects_duplicate_entity_names(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenHierarchy",
                "entities": [
                    {"name": "Dup", "components": {}},
                    {"name": "Dup", "components": {}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.entities[1].name: duplicate entity name 'Dup'", errors)

    def test_prefab_validation_accepts_valid_relative_hierarchy(self) -> None:
        payload = migrate_prefab_data(
            {
                "root_name": "Enemy",
                "entities": [
                    {"name": "Enemy", "components": {"Transform": _transform_component()}},
                    {"name": "Weapon", "parent": "", "components": {"Transform": _transform_component()}},
                    {"name": "Barrel", "parent": "Weapon", "components": {"Transform": _transform_component()}},
                ],
            }
        )
        self.assertEqual(validate_prefab_data(payload), [])

    def test_prefab_validation_rejects_missing_relative_parent(self) -> None:
        payload = migrate_prefab_data(
            {
                "root_name": "Enemy",
                "entities": [
                    {"name": "Enemy", "components": {"Transform": _transform_component()}},
                    {"name": "Weapon", "parent": "Ghost", "components": {"Transform": _transform_component()}},
                ],
            }
        )
        errors = validate_prefab_data(payload)
        self.assertIn("$.entities[1].parent: unknown parent 'Ghost'", errors)

    def test_prefab_validation_rejects_multiple_roots(self) -> None:
        payload = migrate_prefab_data(
            {
                "root_name": "Enemy",
                "entities": [
                    {"name": "Enemy", "components": {}},
                    {"name": "Weapon", "components": {}},
                ],
            }
        )
        errors = validate_prefab_data(payload)
        self.assertIn("$.entities: expected exactly one root entity, got 2", errors)

    def test_scene_manager_load_rejects_semantically_invalid_scene(self) -> None:
        manager = SceneManager(create_default_registry())
        with self.assertRaisesRegex(ValueError, "unknown parent 'Ghost'"):
            manager.load_scene(
                {
                    "name": "BrokenHierarchy",
                    "entities": [
                        {"name": "Child", "parent": "Ghost", "components": {"Transform": _transform_component()}},
                    ],
                    "rules": [],
                    "feature_metadata": {},
                }
            )

    def test_migrate_scene_rejects_unsupported_future_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported scene schema version: 99"):
            migrate_scene_data({"schema_version": 99, "name": "Future", "entities": [], "rules": [], "feature_metadata": {}})

    def test_migrate_prefab_rejects_unsupported_future_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported prefab schema version: 99"):
            migrate_prefab_data({"schema_version": 99, "root_name": "Future", "entities": []})

    def test_migrate_scene_rejects_ambiguous_asset_reference_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cannot migrate .*Animator: inconsistent sprite_sheet and sprite_sheet_path"):
            migrate_scene_data(
                {
                    "schema_version": 1,
                    "name": "Broken",
                    "entities": [
                        {
                            "name": "Player",
                            "components": {
                                "Animator": {
                                    "sprite_sheet": {"guid": "", "path": "assets/sprites/a.png"},
                                    "sprite_sheet_path": "assets/sprites/b.png",
                                }
                            },
                        }
                    ],
                    "rules": [],
                    "feature_metadata": {},
                }
            )

    def test_scene_validation_rejects_invalid_core_component_shapes(self) -> None:
        cases = [
            ("Transform", "oops", "expected object"),
            ("RectTransform", {"width": -1.0}, "$.entities[0].components.RectTransform.width: expected >= 0.0"),
            (
                "Collider",
                {"shape_type": "triangle"},
                "$.entities[0].components.Collider.shape_type: expected one of",
            ),
            (
                "RigidBody",
                {"body_type": "ghost"},
                "$.entities[0].components.RigidBody.body_type: expected one of",
            ),
            (
                "Animator",
                {"animations": {"idle": {"fps": 0}}},
                "$.entities[0].components.Animator.animations.idle.fps: expected > 0.0",
            ),
            (
                "Tilemap",
                {"layers": [{"name": "Ground", "tiles": [{"x": 0, "y": 0, "tile_id": "", "source": 7}]}]},
                "$.entities[0].components.Tilemap.layers[0].tiles[0].tile_id: expected non-empty string",
            ),
            (
                "Camera2D",
                {"zoom": 0},
                "$.entities[0].components.Camera2D.zoom: expected > 0.0",
            ),
            (
                "InputMap",
                {"action_1": 7},
                "$.entities[0].components.InputMap.action_1: expected string",
            ),
            (
                "Canvas",
                {"reference_width": 0},
                "$.entities[0].components.Canvas.reference_width: expected >= 1",
            ),
            (
                "UIText",
                {"alignment": "justify"},
                "$.entities[0].components.UIText.alignment: expected one of",
            ),
            (
                "UIButton",
                {"on_click": {"type": "load_scene"}},
                "$.entities[0].components.UIButton.on_click.path: expected non-empty string",
            ),
        ]

        for component_name, component_data, expected in cases:
            with self.subTest(component=component_name):
                payload = migrate_scene_data(
                    _scene_payload(
                        entities=[
                            {
                                "name": "Actor",
                                "components": {component_name: component_data},
                            }
                        ]
                    )
                )
                errors = validate_scene_data(payload)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_scene_validation_rejects_invalid_feature_metadata_for_core_keys(self) -> None:
        cases = [
            ({"scene_flow": {}}, "$.feature_metadata.scene_flow: expected non-empty object"),
            (
                {"render_2d": {"sorting_layers": ["Default", "Default"]}},
                "$.feature_metadata.render_2d.sorting_layers[1]: duplicate layer 'Default'",
            ),
            (
                {"render_2d": {"minimap": {"enabled": True, "width": 32, "height": 64, "margin": 0}}},
                "$.feature_metadata.render_2d.minimap.width: expected >= 64",
            ),
            (
                {"physics_2d": {"backend": "chipmunk"}},
                "$.feature_metadata.physics_2d.backend: expected one of",
            ),
            (
                {"physics_2d": {"layer_matrix": {"Hero|Walls": "yes"}}},
                "$.feature_metadata.physics_2d.layer_matrix.Hero|Walls: expected boolean",
            ),
        ]

        for feature_metadata, expected in cases:
            with self.subTest(feature_metadata=feature_metadata):
                payload = migrate_scene_data(_scene_payload(feature_metadata=feature_metadata))
                errors = validate_scene_data(payload)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_prefab_validation_rejects_invalid_core_component_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cannot migrate .*AudioSource: inconsistent asset and asset_path"):
            migrate_prefab_data(
                {
                    "root_name": "Enemy",
                    "entities": [
                        {
                            "name": "Enemy",
                            "components": {
                                "AudioSource": {
                                    "asset": {"path": "assets/sfx/hit.wav"},
                                    "asset_path": "assets/sfx/miss.wav",
                                }
                            },
                        }
                    ],
                }
            )

    def test_scene_world_canonical_roundtrip_preserves_core_payload(self) -> None:
        source = migrate_scene_data(
            {
                "name": "Canonical",
                "entities": [
                    {
                        "name": "Root",
                        "components": {
                            "Transform": _transform_component(),
                            "Camera2D": {"enabled": True, "zoom": 1.25, "framing_mode": "platformer"},
                            "InputMap": {"enabled": True, "action_1": "SPACE"},
                            "AudioSource": {
                                "enabled": True,
                                "asset": {"path": "assets/audio/click.wav", "guid": "audio-guid"},
                                "asset_path": "assets/audio/click.wav",
                                "volume": 0.7,
                            },
                            "ScriptBehaviour": {
                                "enabled": True,
                                "script": {"path": "scripts/player.py", "guid": "script-guid"},
                                "module_path": "player",
                                "run_in_edit_mode": False,
                                "public_data": {"speed": 4},
                            },
                            "Canvas": {
                                "enabled": True,
                                "render_mode": "screen_space_overlay",
                                "reference_width": 800,
                                "reference_height": 600,
                                "match_mode": "stretch",
                                "sort_order": 1,
                            },
                        },
                    },
                    {
                        "name": "Child",
                        "parent": "Root",
                        "components": {
                            "Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "RectTransform": {"enabled": True, "width": 280.0, "height": 84.0, "anchor_min_x": 0.5, "anchor_min_y": 0.5, "anchor_max_x": 0.5, "anchor_max_y": 0.5, "pivot_x": 0.5, "pivot_y": 0.5, "anchored_x": 0.0, "anchored_y": 0.0},
                            "Sprite": {
                                "enabled": True,
                                "texture": {"path": "assets/sprites/player.png", "guid": "sprite-guid"},
                                "texture_path": "assets/sprites/player.png",
                                "width": 32,
                                "height": 32,
                                "tint": [255, 255, 255, 255],
                            },
                            "Collider": {"enabled": True, "width": 16.0, "height": 16.0, "shape_type": "box"},
                            "RigidBody": {"enabled": True, "body_type": "dynamic", "constraints": ["FreezePositionX"]},
                            "Animator": {
                                "enabled": True,
                                "sprite_sheet": {"path": "assets/sprites/player_sheet.png", "guid": "sheet-guid"},
                                "sprite_sheet_path": "assets/sprites/player_sheet.png",
                                "frame_width": 32,
                                "frame_height": 32,
                                "default_state": "idle",
                                "current_state": "idle",
                                "animations": {"idle": {"frames": [0, 1], "fps": 8.0, "loop": True}},
                            },
                            "Tilemap": {
                                "enabled": True,
                                "cell_width": 16,
                                "cell_height": 16,
                                "orientation": "orthogonal",
                                "tileset": {"path": "assets/tiles/terrain.png", "guid": "tileset-guid"},
                                "tileset_path": "assets/tiles/terrain.png",
                                "layers": [
                                    {
                                        "name": "Ground",
                                        "visible": True,
                                        "opacity": 1.0,
                                        "metadata": {"theme": "forest"},
                                        "tiles": [
                                            {
                                                "x": 1,
                                                "y": 2,
                                                "tile_id": "grass",
                                                "source": {"path": "assets/tiles/terrain.png", "guid": "tileset-guid"},
                                                "flags": ["solid"],
                                                "tags": ["ground"],
                                                "custom": {"biome": "forest"},
                                            }
                                        ],
                                    }
                                ],
                            },
                            "UIText": {"enabled": True, "text": "Play", "font_size": 24, "color": [255, 255, 255, 255], "alignment": "center", "wrap": False},
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
                "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "ok"}]}],
                "feature_metadata": {
                    "scene_flow": {"next_scene": "levels/next_scene.json"},
                    "render_2d": {"sorting_layers": ["Default", "Foreground"]},
                    "physics_2d": {"backend": "box2d", "layer_matrix": {"Hero|Walls": False}},
                    "input_profile": {"scheme": "keyboard"},
                },
            }
        )

        scene = Scene.from_dict(source)
        world = scene.create_world(create_default_registry())
        canonical = build_canonical_scene_payload(
            scene.name,
            world.serialize(),
            scene.rules_data,
            scene.feature_metadata,
        )

        self.assertEqual(validate_scene_data(canonical), [])
        self.assertEqual(canonical["rules"], source["rules"])
        self.assertEqual(canonical["feature_metadata"], source["feature_metadata"])
        reloaded_scene = Scene.from_dict(canonical)
        rebuilt = build_canonical_scene_payload(
            reloaded_scene.name,
            reloaded_scene.create_world(create_default_registry()).serialize(),
            reloaded_scene.rules_data,
            reloaded_scene.feature_metadata,
        )
        self.assertEqual(rebuilt, canonical)
        child = next(entity for entity in canonical["entities"] if entity["name"] == "Child")
        self.assertEqual(child["parent"], "Root")
        self.assertEqual(child["components"]["UIButton"]["on_click"]["name"], "ui.play_clicked")

    def test_scene_validation_rejects_rule_without_event(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenRules",
                "entities": [],
                "rules": [{"do": [{"action": "log_message", "message": "hi"}]}],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.rules[0].event: expected non-empty string", errors)

    def test_scene_validation_rejects_unknown_rule_action(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenRules",
                "entities": [],
                "rules": [{"event": "tick", "do": [{"action": "teleport"}]}],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.rules[0].do[0].action: unsupported action 'teleport'", errors)

    def test_scene_validation_rejects_invalid_set_position_action(self) -> None:
        payload = migrate_scene_data(
            {
                "name": "BrokenRules",
                "entities": [],
                "rules": [{"event": "tick", "do": [{"action": "set_position", "entity": "Player"}]}],
                "feature_metadata": {},
            }
        )
        errors = validate_scene_data(payload)
        self.assertIn("$.rules[0].do[0]: expected x or y", errors)

    def test_scene_transition_action_roundtrip_save_load(self) -> None:
        manager = SceneManager(create_default_registry())
        source_payload = _scene_payload(
            name="TransitionSource",
            entities=[
                _entity_payload(
                    "Portal",
                    components={
                        "Transform": _transform_component(),
                        "SceneTransitionAction": {
                            "enabled": True,
                            "target_scene_path": "levels/target_scene.json",
                            "target_entry_id": "arrival",
                        },
                    },
                )
            ],
        )
        manager.load_scene(source_payload)
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "transition_source.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            saved = json.loads(scene_path.read_text(encoding="utf-8"))
            action = saved["entities"][0]["components"]["SceneTransitionAction"]
            self.assertEqual(action["target_scene_path"], "levels/target_scene.json")
            self.assertEqual(action["target_entry_id"], "arrival")

            reloaded_manager = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded_manager.load_scene_from_file(scene_path.as_posix()))
            reloaded_entity = reloaded_manager.current_scene.find_entity("Portal")
            self.assertIsNotNone(reloaded_entity)
            reloaded_action = reloaded_entity["components"]["SceneTransitionAction"]
            self.assertEqual(reloaded_action["target_scene_path"], "levels/target_scene.json")
            self.assertEqual(reloaded_action["target_entry_id"], "arrival")

    def test_scene_entry_point_roundtrip_save_load(self) -> None:
        manager = SceneManager(create_default_registry())
        source_payload = _scene_payload(
            name="EntryScene",
            entities=[
                _entity_payload(
                    "SpawnNorth",
                    components={
                        "Transform": _transform_component(),
                        "SceneEntryPoint": {
                            "enabled": True,
                            "entry_id": "north_gate",
                            "label": "North Gate",
                        },
                    },
                )
            ],
        )
        manager.load_scene(source_payload)
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_path = Path(temp_dir) / "entry_scene.json"
            self.assertTrue(manager.save_scene_to_file(scene_path.as_posix()))
            saved = json.loads(scene_path.read_text(encoding="utf-8"))
            entry = saved["entities"][0]["components"]["SceneEntryPoint"]
            self.assertEqual(entry["entry_id"], "north_gate")
            self.assertEqual(entry["label"], "North Gate")

            reloaded_manager = SceneManager(create_default_registry())
            self.assertIsNotNone(reloaded_manager.load_scene_from_file(scene_path.as_posix()))
            reloaded_entity = reloaded_manager.current_scene.find_entity("SpawnNorth")
            self.assertIsNotNone(reloaded_entity)
            reloaded_entry = reloaded_entity["components"]["SceneEntryPoint"]
            self.assertEqual(reloaded_entry["entry_id"], "north_gate")
            self.assertEqual(reloaded_entry["label"], "North Gate")

    def test_scene_transition_validation_rejects_empty_target_scene(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="BrokenTransition",
                entities=[
                    _entity_payload(
                        "Portal",
                        components={
                            "Transform": _transform_component(),
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "",
                                "target_entry_id": "",
                            },
                        },
                    )
                ],
            )
        )
        errors = validate_scene_data(payload)
        self.assertIn(
            "$.entities[0].components.SceneTransitionAction.target_scene_path: expected non-empty string",
            errors,
        )

    def test_scene_transition_reference_validation_rejects_missing_target_scene(self) -> None:
        source_payload = _scene_payload(
            name="Source",
            entities=[
                _entity_payload(
                    "Portal",
                    components={
                        "Transform": _transform_component(),
                        "SceneTransitionAction": {
                            "enabled": True,
                            "target_scene_path": "levels/missing_scene.json",
                            "target_entry_id": "",
                        },
                    },
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "levels" / "source_scene.json"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(json.dumps(migrate_scene_data(source_payload), indent=2), encoding="utf-8")
            errors = validate_scene_transition_references(source_payload, scene_path=source_path.as_posix())
        self.assertIn(
            "$.entities[0].components.SceneTransitionAction.target_scene_path: target scene 'levels/missing_scene.json' does not exist",
            errors,
        )

    def test_scene_transition_reference_validation_rejects_missing_target_spawn(self) -> None:
        target_payload = _scene_payload(
            name="Target",
            entities=[
                _entity_payload(
                    "SpawnArrival",
                    components={
                        "Transform": _transform_component(),
                        "SceneEntryPoint": {"enabled": True, "entry_id": "arrival", "label": "Arrival"},
                    },
                )
            ],
        )
        source_payload = _scene_payload(
            name="Source",
            entities=[
                _entity_payload(
                    "Portal",
                    components={
                        "Transform": _transform_component(),
                        "SceneTransitionAction": {
                            "enabled": True,
                            "target_scene_path": "levels/target_scene.json",
                            "target_entry_id": "missing_spawn",
                        },
                    },
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            levels_dir = Path(temp_dir) / "levels"
            levels_dir.mkdir(parents=True, exist_ok=True)
            source_path = levels_dir / "source_scene.json"
            target_path = levels_dir / "target_scene.json"
            source_path.write_text(json.dumps(migrate_scene_data(source_payload), indent=2), encoding="utf-8")
            target_path.write_text(json.dumps(migrate_scene_data(target_payload), indent=2), encoding="utf-8")
            errors = validate_scene_transition_references(source_payload, scene_path=source_path.as_posix())
        self.assertIn(
            "$.entities[0].components.SceneTransitionAction.target_entry_id: target entry point 'missing_spawn' was not found in destination scene",
            errors,
        )

    def test_scene_transition_reference_validation_allows_empty_target_spawn(self) -> None:
        target_payload = _scene_payload(
            name="Target",
            entities=[
                _entity_payload(
                    "SpawnArrival",
                    components={
                        "Transform": _transform_component(),
                        "SceneEntryPoint": {"enabled": True, "entry_id": "arrival", "label": "Arrival"},
                    },
                )
            ],
        )
        source_payload = _scene_payload(
            name="Source",
            entities=[
                _entity_payload(
                    "Portal",
                    components={
                        "Transform": _transform_component(),
                        "SceneTransitionAction": {
                            "enabled": True,
                            "target_scene_path": "levels/target_scene.json",
                            "target_entry_id": "",
                        },
                    },
                )
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            levels_dir = Path(temp_dir) / "levels"
            levels_dir.mkdir(parents=True, exist_ok=True)
            source_path = levels_dir / "source_scene.json"
            target_path = levels_dir / "target_scene.json"
            source_path.write_text(json.dumps(migrate_scene_data(source_payload), indent=2), encoding="utf-8")
            target_path.write_text(json.dumps(migrate_scene_data(target_payload), indent=2), encoding="utf-8")
            errors = validate_scene_transition_references(source_payload, scene_path=source_path.as_posix())
        self.assertEqual(errors, [])

    def test_scene_with_multiple_valid_entry_points_and_transition_reference(self) -> None:
        target_payload = _scene_payload(
            name="Target",
            entities=[
                _entity_payload(
                    "SpawnNorth",
                    components={
                        "Transform": _transform_component(),
                        "SceneEntryPoint": {"enabled": True, "entry_id": "north_gate", "label": "North Gate"},
                    },
                ),
                _entity_payload(
                    "SpawnSouth",
                    components={
                        "Transform": _transform_component(),
                        "SceneEntryPoint": {"enabled": True, "entry_id": "south_gate", "label": "South Gate"},
                    },
                ),
            ],
        )
        source_payload = _scene_payload(
            name="Source",
            entities=[
                _entity_payload(
                    "Portal",
                    components={
                        "Transform": _transform_component(),
                        "SceneTransitionAction": {
                            "enabled": True,
                            "target_scene_path": "levels/target_scene.json",
                            "target_entry_id": "south_gate",
                        },
                    },
                )
            ],
        )
        self.assertEqual(validate_scene_data(migrate_scene_data(target_payload)), [])
        with tempfile.TemporaryDirectory() as temp_dir:
            levels_dir = Path(temp_dir) / "levels"
            levels_dir.mkdir(parents=True, exist_ok=True)
            source_path = levels_dir / "source_scene.json"
            target_path = levels_dir / "target_scene.json"
            source_path.write_text(json.dumps(migrate_scene_data(source_payload), indent=2), encoding="utf-8")
            target_path.write_text(json.dumps(migrate_scene_data(target_payload), indent=2), encoding="utf-8")
            errors = validate_scene_transition_references(source_payload, scene_path=source_path.as_posix())
        self.assertEqual(errors, [])

    def test_scene_entry_points_must_be_unique_within_scene(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="DuplicateEntryIds",
                entities=[
                    _entity_payload(
                        "SpawnA",
                        components={
                            "Transform": _transform_component(),
                            "SceneEntryPoint": {"enabled": True, "entry_id": "arrival", "label": "A"},
                        },
                    ),
                    _entity_payload(
                        "SpawnB",
                        components={
                            "Transform": _transform_component(),
                            "SceneEntryPoint": {"enabled": True, "entry_id": "arrival", "label": "B"},
                        },
                    ),
                ],
            )
        )
        errors = validate_scene_data(payload)
        self.assertTrue(any("duplicate entry id 'arrival'" in error for error in errors), errors)

    def test_scene_transition_triggers_require_action_component(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="MissingAction",
                entities=[
                    _entity_payload(
                        "Portal",
                        components={
                            "Transform": _transform_component(),
                            "SceneTransitionOnContact": {
                                "enabled": True,
                                "mode": "trigger_enter",
                                "require_player": True,
                            },
                        },
                    )
                ],
            )
        )
        errors = validate_scene_data(payload)
        self.assertIn(
            "$.entities[0].components.SceneTransitionAction: required when using scene transition triggers",
            errors,
        )

    def test_scene_transition_on_interact_requires_trigger_collider(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="InteractWithoutTrigger",
                entities=[
                    _entity_payload(
                        "Portal",
                        components={
                            "Transform": _transform_component(),
                            "Collider": {
                                "enabled": True,
                                "width": 32.0,
                                "height": 32.0,
                                "offset_x": 0.0,
                                "offset_y": 0.0,
                                "is_trigger": False,
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/next_scene.json",
                                "target_entry_id": "",
                            },
                            "SceneTransitionOnInteract": {
                                "enabled": True,
                                "require_player": True,
                            },
                        },
                    )
                ],
            )
        )
        errors = validate_scene_data(payload)
        self.assertIn(
            "$.entities[0].components.SceneTransitionOnInteract: requires Collider.is_trigger = true",
            errors,
        )

    def test_button_scene_transition_action_type_is_valid_when_action_component_exists(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="UIButtonTransition",
                entities=[
                    _entity_payload(
                        "PlayButton",
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
                                "on_click": {"type": "run_scene_transition"},
                            },
                            "SceneTransitionAction": {
                                "enabled": True,
                                "target_scene_path": "levels/next_scene.json",
                                "target_entry_id": "",
                            },
                        },
                    )
                ],
            )
        )
        self.assertEqual(validate_scene_data(payload), [])

    def test_scene_link_is_canonicalized_with_authoring_fields(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="SceneLinkFacade",
                entities=[
                    _entity_payload(
                        "Portal",
                        components={
                            "Transform": _transform_component(),
                            "SceneLink": {
                                "enabled": True,
                                "target_path": " levels/next_scene.json ",
                                "flow_key": " next ",
                                "preview_label": " Next ",
                                "link_mode": " collision ",
                                "target_entry_id": " arrival ",
                            },
                        },
                    )
                ],
            )
        )
        scene_link = payload["entities"][0]["components"]["SceneLink"]
        self.assertEqual(scene_link["target_path"], "levels/next_scene.json")
        self.assertEqual(scene_link["flow_key"], "next")
        self.assertEqual(scene_link["preview_label"], "Next")
        self.assertEqual(scene_link["link_mode"], "collision")
        self.assertEqual(scene_link["target_entry_id"], "arrival")

    def test_scene_link_validation_rejects_unknown_link_mode(self) -> None:
        payload = migrate_scene_data(
            _scene_payload(
                name="InvalidSceneLink",
                entities=[
                    _entity_payload(
                        "Portal",
                        components={
                            "Transform": _transform_component(),
                            "SceneLink": {
                                "enabled": True,
                                "target_path": "levels/next_scene.json",
                                "link_mode": "magic",
                            },
                        },
                    )
                ],
            )
        )
        errors = validate_scene_data(payload)
        self.assertTrue(any("SceneLink.link_mode: expected one of" in error for error in errors), errors)

    def test_schema_cli_validate_all_marks_invalid_rules(self) -> None:
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            levels = root / "levels"
            levels.mkdir(parents=True, exist_ok=True)
            valid_scene = levels / "valid.json"
            invalid_scene = levels / "invalid.json"
            valid_scene.write_text(
                json.dumps(
                    {
                        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
                        "name": "ValidScene",
                        "entities": [],
                        "rules": [{"event": "tick", "do": [{"action": "log_message", "message": "ok"}]}],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            invalid_scene.write_text(
                json.dumps(
                    {
                        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
                        "name": "InvalidScene",
                        "entities": [],
                        "rules": [{"event": "tick", "do": [{"action": "emit_event"}]}],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-m", "tools.schema_cli", "validate_all", root.as_posix()],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("$.rules[0].do[0].event: expected non-empty string", result.stdout)

    def test_schema_cli_validate_all_ignores_meta_json(self) -> None:
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            levels = root / "levels"
            levels.mkdir(parents=True, exist_ok=True)
            (levels / "scene.json").write_text(
                json.dumps(
                    {
                        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
                        "name": "ValidScene",
                        "entities": [],
                        "rules": [],
                        "feature_metadata": {},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            (levels / "scene.json.meta.json").write_text(json.dumps({"guid": "abc"}, indent=2), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "tools.schema_cli", "validate_all", root.as_posix()],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("[OK] scene valido:", result.stdout)
        self.assertIn("[SKIP] no es payload de escena/prefab:", result.stdout)

    def test_real_repo_levels_load_migrate_save_and_reload(self) -> None:
        manager = SceneManager(create_default_registry())
        with tempfile.TemporaryDirectory() as temp_dir:
            for scene_path in sorted((ROOT / "levels").glob("*.json")):
                if scene_path.name.endswith(".meta.json"):
                    continue
                with self.subTest(scene=scene_path.name):
                    raw = json.loads(scene_path.read_text(encoding="utf-8"))
                    world = manager.load_scene(raw, source_path=scene_path.as_posix())
                    self.assertIsNotNone(world)
                    migrated = migrate_scene_data(raw)
                    self.assertEqual(validate_scene_data(migrated), [])
                    output = Path(temp_dir) / scene_path.name
                    self.assertTrue(manager.save_scene_to_file(output.as_posix(), key=scene_path.as_posix()))
                    saved = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(saved["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)
                    reloaded_manager = SceneManager(create_default_registry())
                    reloaded = reloaded_manager.load_scene_from_file(output.as_posix())
                    self.assertIsNotNone(reloaded)


if __name__ == "__main__":
    unittest.main()
