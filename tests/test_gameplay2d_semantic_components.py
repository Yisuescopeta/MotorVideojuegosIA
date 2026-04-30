from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.ai.compliance import run_ai_compliance
from engine.api import EngineAPI
from engine.components.gameplay2d import (
    Checkpoint2D,
    Collectible2D,
    EnemyPatrol2D,
    Goal2D,
    Hazard2D,
    KillZone2D,
    LevelBounds2D,
    MovingPlatform2D,
    RespawnPoint2D,
)
from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene
from engine.serialization.schema import migrate_scene_data, validate_scene_data

ROOT = Path(__file__).resolve().parents[1]


def _transform() -> dict[str, float | bool]:
    return {
        "enabled": True,
        "x": 0.0,
        "y": 0.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _component_payloads() -> dict[str, dict[str, object]]:
    return {
        "Collectible2D": Collectible2D().to_dict(),
        "Hazard2D": Hazard2D().to_dict(),
        "Goal2D": Goal2D().to_dict(),
        "RespawnPoint2D": RespawnPoint2D().to_dict(),
        "MovingPlatform2D": MovingPlatform2D().to_dict(),
        "EnemyPatrol2D": EnemyPatrol2D().to_dict(),
        "Checkpoint2D": Checkpoint2D().to_dict(),
        "KillZone2D": KillZone2D().to_dict(),
        "LevelBounds2D": LevelBounds2D().to_dict(),
    }


def _scene_payload() -> dict[str, object]:
    return {
        "name": "GameplaySemanticScene",
        "entities": [
            {
                "name": "GameplayMarkers",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {"Transform": _transform(), **_component_payloads()},
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


def _collider_payload(is_trigger: bool = True) -> dict[str, object]:
    return {
        "enabled": True,
        "width": 16.0,
        "height": 16.0,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "is_trigger": is_trigger,
    }


def _entity_payload(
    name: str,
    components: dict[str, dict[str, object]],
    *,
    x: float = 0.0,
    y: float = 0.0,
    tag: str = "Untagged",
) -> dict[str, object]:
    return {
        "name": name,
        "active": True,
        "tag": tag,
        "layer": "Default",
        "components": {
            "Transform": {**_transform(), "x": x, "y": y},
            **components,
        },
    }


def _runtime_scene_payload(
    extra_entities: list[dict[str, object]],
    *,
    player_x: float = 0.0,
    player_y: float = 0.0,
) -> dict[str, object]:
    player = _entity_payload(
        "Player",
        {
            "Collider": _collider_payload(is_trigger=False),
            "PlayerController2D": {
                "enabled": True,
                "move_speed": 180.0,
                "jump_velocity": -320.0,
                "air_control": 0.75,
            },
        },
        x=player_x,
        y=player_y,
        tag="Player",
    )
    return migrate_scene_data(
        {
            "name": "Gameplay Runtime Scene",
            "entities": [player, *extra_entities],
            "rules": [],
            "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
        }
    )


def _write_project_with_scene(root: Path, scene: dict[str, object]) -> Path:
    project = root / "SemanticRuntimeProject"
    levels = project / "levels"
    for path in [levels, project / "assets", project / "scripts", project / "settings"]:
        path.mkdir(parents=True, exist_ok=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "name": "SemanticRuntimeProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }
        ),
        encoding="utf-8",
    )
    scene_path = levels / "semantic_runtime.json"
    scene_path.write_text(json.dumps(scene, indent=2), encoding="utf-8")
    return scene_path


def _recent_event(api: EngineAPI, name: str) -> dict[str, object]:
    for event in api.get_recent_events(50):
        if event["name"] == name:
            return event
    return {}


def _runtime_api(scene_path: Path, workspace: Path) -> EngineAPI:
    return EngineAPI(
        project_root=scene_path.parents[1].as_posix(),
        global_state_dir=(workspace / "global").as_posix(),
    )


def _bounds_payload(
    *,
    left: float = 0.0,
    right: float = 100.0,
    top: float = -50.0,
    bottom: float = 100.0,
) -> dict[str, object]:
    return LevelBounds2D(left=left, right=right, top=top, bottom=bottom).to_dict()


class Gameplay2DSemanticComponentTests(unittest.TestCase):
    def test_default_creation(self) -> None:
        collectible = Collectible2D()
        hazard = Hazard2D()
        goal = Goal2D()
        respawn = RespawnPoint2D()
        moving_platform = MovingPlatform2D()
        enemy = EnemyPatrol2D()
        checkpoint = Checkpoint2D()
        killzone = KillZone2D()
        bounds = LevelBounds2D()

        self.assertTrue(collectible.enabled)
        self.assertEqual(collectible.points, 1)
        self.assertTrue(collectible.destroy_on_collect)
        self.assertEqual(collectible.event_name, "collectible_collected")
        self.assertEqual(hazard.damage, 1)
        self.assertTrue(hazard.respawn_on_touch)
        self.assertEqual(hazard.event_name, "hazard_touched")
        self.assertTrue(goal.complete_on_touch)
        self.assertEqual(goal.next_scene, "")
        self.assertEqual(goal.event_name, "goal_reached")
        self.assertEqual(respawn.spawn_id, "default")
        self.assertTrue(respawn.active)
        self.assertEqual(moving_platform.path, [])
        self.assertEqual(moving_platform.speed, 80.0)
        self.assertTrue(moving_platform.loop)
        self.assertTrue(moving_platform.start_active)
        self.assertEqual(enemy.patrol_points, [])
        self.assertEqual(enemy.damage, 1)
        self.assertEqual(enemy.event_name, "enemy_touched")
        self.assertEqual(checkpoint.checkpoint_id, "default")
        self.assertTrue(checkpoint.set_respawn_on_touch)
        self.assertEqual(checkpoint.event_name, "checkpoint_reached")
        self.assertEqual(killzone.damage, 1)
        self.assertEqual(killzone.event_name, "killzone_touched")
        self.assertEqual(bounds.to_dict()["right"], 1280.0)

    def test_roundtrip_serialization(self) -> None:
        cases = [
            Collectible2D(points=5, destroy_on_collect=False, event_name=" coin "),
            Hazard2D(damage=3, respawn_on_touch=False, event_name=" spike "),
            Goal2D(complete_on_touch=False, next_scene=" levels/next.json ", event_name=" win "),
            RespawnPoint2D(spawn_id=" checkpoint_a ", active=False),
            MovingPlatform2D(path=[{"x": 0.0, "y": 0.0}, {"x": 128.0, "y": 0.0}], speed=120.0, loop=False),
            EnemyPatrol2D(patrol_points=[{"x": 16.0, "y": 32.0}], speed=90.0, damage=2, event_name=" hit "),
            Checkpoint2D(checkpoint_id=" cp_a ", active=False, set_respawn_on_touch=False, event_name=" cp "),
            KillZone2D(damage=4, respawn_on_touch=False, event_name=" kill "),
            LevelBounds2D(left=-32.0, right=2048.0, top=-16.0, bottom=720.0),
        ]

        for component in cases:
            with self.subTest(component=type(component).__name__):
                data = component.to_dict()
                restored = type(component).from_dict(data)
                self.assertEqual(restored.to_dict(), data)

    def test_safe_defaults_from_invalid_values(self) -> None:
        collectible = Collectible2D.from_dict({"points": -10, "event_name": " "})
        hazard = Hazard2D.from_dict({"damage": "bad", "event_name": ""})
        respawn = RespawnPoint2D.from_dict({"active": "bad", "spawn_id": " "})
        moving_platform = MovingPlatform2D.from_dict({"speed": -10, "loop": "bad", "path": [["1", "2"], {"x": "bad"}]})
        enemy = EnemyPatrol2D.from_dict({"damage": "bad", "event_name": "", "patrol_points": "bad"})
        checkpoint = Checkpoint2D.from_dict({"checkpoint_id": " ", "active": "bad", "event_name": ""})
        killzone = KillZone2D.from_dict({"damage": -2, "respawn_on_touch": "bad", "event_name": ""})

        self.assertEqual(collectible.points, 0)
        self.assertEqual(collectible.event_name, "collectible_collected")
        self.assertEqual(hazard.damage, 1)
        self.assertEqual(hazard.event_name, "hazard_touched")
        self.assertTrue(respawn.active)
        self.assertEqual(respawn.spawn_id, "default")
        self.assertEqual(moving_platform.speed, 0.0)
        self.assertTrue(moving_platform.loop)
        self.assertEqual(moving_platform.path, [{"x": 1.0, "y": 2.0}, {"x": 0.0, "y": 0.0}])
        self.assertEqual(enemy.damage, 1)
        self.assertEqual(enemy.event_name, "enemy_touched")
        self.assertEqual(enemy.patrol_points, [])
        self.assertEqual(checkpoint.checkpoint_id, "default")
        self.assertTrue(checkpoint.active)
        self.assertEqual(checkpoint.event_name, "checkpoint_reached")
        self.assertEqual(killzone.damage, 0)
        self.assertTrue(killzone.respawn_on_touch)
        self.assertEqual(killzone.event_name, "killzone_touched")

    def test_default_registry_lists_and_creates_components(self) -> None:
        registry = create_default_registry()
        expected = {
            "Collectible2D",
            "Hazard2D",
            "Goal2D",
            "RespawnPoint2D",
            "MovingPlatform2D",
            "EnemyPatrol2D",
            "Checkpoint2D",
            "KillZone2D",
            "LevelBounds2D",
        }

        self.assertTrue(expected.issubset(set(registry.list_registered())))
        self.assertIsInstance(registry.create("Collectible2D", {"points": 2}), Collectible2D)
        self.assertIsInstance(registry.create("Hazard2D", {"damage": 4}), Hazard2D)
        self.assertIsInstance(registry.create("Goal2D", {"next_scene": "next"}), Goal2D)
        self.assertIsInstance(registry.create("RespawnPoint2D", {"spawn_id": "start"}), RespawnPoint2D)
        self.assertIsInstance(registry.create("MovingPlatform2D", {"speed": 2}), MovingPlatform2D)
        self.assertIsInstance(registry.create("EnemyPatrol2D", {"damage": 2}), EnemyPatrol2D)
        self.assertIsInstance(registry.create("Checkpoint2D", {"checkpoint_id": "a"}), Checkpoint2D)
        self.assertIsInstance(registry.create("KillZone2D", {"damage": 2}), KillZone2D)
        self.assertIsInstance(registry.create("LevelBounds2D", {"right": 10}), LevelBounds2D)

    def test_semantic_component_metadata_exposes_editor_defaults(self) -> None:
        registry = create_default_registry()
        expected_defaults = {
            "Collectible2D": Collectible2D().to_dict(),
            "Hazard2D": Hazard2D().to_dict(),
            "Goal2D": Goal2D().to_dict(),
            "RespawnPoint2D": RespawnPoint2D().to_dict(),
        }

        for component_name, default_payload in expected_defaults.items():
            with self.subTest(component=component_name):
                descriptor = registry.get_descriptor(component_name)
                self.assertIsNotNone(descriptor)
                assert descriptor is not None
                self.assertEqual(descriptor.default_payload, default_payload)
                self.assertIn("platformer", descriptor.editor_tags)
                self.assertTrue(descriptor.description)

    def test_scene_creates_world_with_semantic_components(self) -> None:
        scene = Scene.from_dict(_scene_payload())
        world = scene.create_world(create_default_registry())
        entity = world.get_entity_by_name("GameplayMarkers")

        self.assertIsNotNone(entity)
        if entity is None:
            self.fail("GameplayMarkers entity was not created")
        self.assertIsNotNone(entity.get_component(Transform))
        self.assertIsNotNone(entity.get_component(Collectible2D))
        self.assertIsNotNone(entity.get_component(Hazard2D))
        self.assertIsNotNone(entity.get_component(Goal2D))
        self.assertIsNotNone(entity.get_component(RespawnPoint2D))
        self.assertIsNotNone(entity.get_component(MovingPlatform2D))
        self.assertIsNotNone(entity.get_component(EnemyPatrol2D))
        self.assertIsNotNone(entity.get_component(Checkpoint2D))
        self.assertIsNotNone(entity.get_component(KillZone2D))
        self.assertIsNotNone(entity.get_component(LevelBounds2D))

    def test_scene_schema_accepts_semantic_components(self) -> None:
        migrated = migrate_scene_data(_scene_payload())
        self.assertEqual(validate_scene_data(migrated), [])

    def test_ai_compliance_accepts_semantic_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "SemanticGameplayProject"
            levels = project / "levels"
            for path in [levels, project / "assets", project / "scripts", project / "settings"]:
                path.mkdir(parents=True, exist_ok=True)
            (project / "project.json").write_text(
                json.dumps(
                    {
                        "name": "SemanticGameplayProject",
                        "version": 2,
                        "engine_version": "2026.03",
                        "paths": {
                            "assets": "assets",
                            "levels": "levels",
                            "prefabs": "prefabs",
                            "scripts": "scripts",
                            "settings": "settings",
                            "meta": ".motor/meta",
                            "build": ".motor/build",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (levels / "main_scene.json").write_text(
                json.dumps(migrate_scene_data(_scene_payload()), indent=2),
                encoding="utf-8",
            )

            report = run_ai_compliance(project, strict=True)

        self.assertTrue(report["success"], report)
        self.assertTrue(report["strict_pass"], report)
        self.assertEqual(report["checks"]["unknown_components"], [])
        self.assertFalse(
            any(item["code"] == "unknown_component" for item in report["warnings"]),
            report["warnings"],
        )


class Gameplay2DSemanticRuntimeTests(unittest.TestCase):
    def test_player_collectible_overlap_emits_collect_event(self) -> None:
        coin = _entity_payload(
            "Coin",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Collectible2D": Collectible2D(points=7, destroy_on_collect=False).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([coin]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "collectible_collected")
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["collectible"], "Coin")
                self.assertEqual(event["data"]["points"], 7)
            finally:
                api.shutdown()

    def test_collectible_destroy_on_collect_removes_runtime_entity_only(self) -> None:
        coin = _entity_payload(
            "Coin",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Collectible2D": Collectible2D(points=1, destroy_on_collect=True).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([coin]))
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                entity_names = {entity["name"] for entity in api.list_entities()}
                self.assertNotIn("Coin", entity_names)
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_hazard_respawns_player_at_first_active_respawn(self) -> None:
        hazard = _entity_payload(
            "Spike",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Hazard2D": Hazard2D(damage=3, respawn_on_touch=True).to_dict(),
            },
        )
        respawn = _entity_payload(
            "Respawn_default",
            {"RespawnPoint2D": RespawnPoint2D(spawn_id="default", active=True).to_dict()},
            x=120.0,
            y=80.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([hazard, respawn]))
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "hazard_touched")
                player = api.get_entity("Player")
                transform = player["components"]["Transform"]
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["hazard"], "Spike")
                self.assertEqual(event["data"]["damage"], 3)
                self.assertEqual(transform["x"], 120.0)
                self.assertEqual(transform["y"], 80.0)
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_hazard_without_respawn_emits_missing_respawn_event(self) -> None:
        hazard = _entity_payload(
            "Spike",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Hazard2D": Hazard2D(damage=3, respawn_on_touch=True).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([hazard]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "hazard_respawn_missing")
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["hazard"], "Spike")
                self.assertEqual(event["data"]["reason"], "no_active_respawn_point")
            finally:
                api.shutdown()

    def test_checkpoint_overlap_emits_checkpoint_reached(self) -> None:
        checkpoint = _entity_payload(
            "Checkpoint_A",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Checkpoint2D": Checkpoint2D(checkpoint_id="cp_a", set_respawn_on_touch=False).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([checkpoint]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "checkpoint_reached")
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["checkpoint"], "Checkpoint_A")
                self.assertEqual(event["data"]["checkpoint_id"], "cp_a")
            finally:
                api.shutdown()

    def test_hazard_event_does_not_reemit_for_repeated_contact_in_same_play_session(self) -> None:
        hazard = _entity_payload(
            "Spike",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Hazard2D": Hazard2D(damage=3, respawn_on_touch=False).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([hazard]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                api.step(1)
                hazard_events = [event for event in api.get_recent_events(50) if event["name"] == "hazard_touched"]
                self.assertEqual(len(hazard_events), 1)
            finally:
                api.shutdown()

    def test_checkpoint_sets_runtime_respawn_for_killzone_without_persisting_scene(self) -> None:
        checkpoint_collider = _collider_payload(is_trigger=True)
        checkpoint_collider["offset_x"] = -200.0
        checkpoint_collider["offset_y"] = -60.0
        checkpoint = _entity_payload(
            "Checkpoint_A",
            {
                "Collider": checkpoint_collider,
                "Checkpoint2D": Checkpoint2D(checkpoint_id="cp_a", set_respawn_on_touch=True).to_dict(),
            },
            x=200.0,
            y=60.0,
        )
        killzone = _entity_payload(
            "Pit_A",
            {
                "Collider": _collider_payload(is_trigger=True),
                "KillZone2D": KillZone2D(damage=2, respawn_on_touch=True).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([checkpoint, killzone]))
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                checkpoint_event = _recent_event(api, "checkpoint_reached")
                killzone_event = _recent_event(api, "killzone_touched")
                missing_event = _recent_event(api, "killzone_respawn_missing")
                player = api.get_entity("Player")
                transform = player["components"]["Transform"]
                self.assertEqual(checkpoint_event["data"]["checkpoint_id"], "cp_a")
                self.assertEqual(killzone_event["data"]["killzone"], "Pit_A")
                self.assertEqual(transform["x"], 200.0)
                self.assertEqual(transform["y"], 60.0)
                self.assertEqual(missing_event, {})
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_checkpoint_prefers_matching_respawn_point_for_killzone(self) -> None:
        checkpoint_collider = _collider_payload(is_trigger=True)
        checkpoint_collider["offset_x"] = -200.0
        checkpoint_collider["offset_y"] = -60.0
        checkpoint = _entity_payload(
            "Checkpoint_A",
            {
                "Collider": checkpoint_collider,
                "Checkpoint2D": Checkpoint2D(checkpoint_id="cp_a", set_respawn_on_touch=True).to_dict(),
            },
            x=200.0,
            y=60.0,
        )
        matching_respawn = _entity_payload(
            "Respawn_cp_a",
            {"RespawnPoint2D": RespawnPoint2D(spawn_id="cp_a", active=True).to_dict()},
            x=120.0,
            y=80.0,
        )
        killzone = _entity_payload(
            "Pit_A",
            {
                "Collider": _collider_payload(is_trigger=True),
                "KillZone2D": KillZone2D(damage=2, respawn_on_touch=True).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(
                Path(tmpdir),
                _runtime_scene_payload([checkpoint, matching_respawn, killzone]),
            )
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                player = api.get_entity("Player")
                transform = player["components"]["Transform"]
                self.assertEqual(transform["x"], 120.0)
                self.assertEqual(transform["y"], 80.0)
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_killzone_without_respawn_emits_missing_respawn_event(self) -> None:
        killzone = _entity_payload(
            "Pit_A",
            {
                "Collider": _collider_payload(is_trigger=True),
                "KillZone2D": KillZone2D(damage=5, respawn_on_touch=True).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([killzone]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "killzone_respawn_missing")
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["killzone"], "Pit_A")
                self.assertEqual(event["data"]["damage"], 5)
                self.assertEqual(event["data"]["reason"], "no_active_respawn_point")
            finally:
                api.shutdown()

    def test_level_bounds_left_exit_emits_event_and_clamps_without_persisting_scene(self) -> None:
        bounds = _entity_payload("LevelBounds", {"LevelBounds2D": _bounds_payload()})
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(
                Path(tmpdir),
                _runtime_scene_payload([bounds], player_x=-5.0, player_y=0.0),
            )
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "level_bounds_exited")
                player = api.get_entity("Player")
                transform = player["components"]["Transform"]
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["bounds_entity"], "LevelBounds")
                self.assertEqual(event["data"]["side"], "left")
                self.assertEqual(event["data"]["player_x"], -5.0)
                self.assertEqual(transform["x"], 0.0)
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_level_bounds_right_exit_emits_event_and_clamps_without_persisting_scene(self) -> None:
        bounds = _entity_payload("LevelBounds", {"LevelBounds2D": _bounds_payload()})
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(
                Path(tmpdir),
                _runtime_scene_payload([bounds], player_x=105.0, player_y=0.0),
            )
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "level_bounds_exited")
                player = api.get_entity("Player")
                transform = player["components"]["Transform"]
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["bounds_entity"], "LevelBounds")
                self.assertEqual(event["data"]["side"], "right")
                self.assertEqual(event["data"]["player_x"], 105.0)
                self.assertEqual(transform["x"], 100.0)
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_level_bounds_bottom_exit_respawns_at_active_respawn_without_persisting_scene(self) -> None:
        bounds = _entity_payload("LevelBounds", {"LevelBounds2D": _bounds_payload()})
        respawn = _entity_payload(
            "Respawn_default",
            {"RespawnPoint2D": RespawnPoint2D(spawn_id="default", active=True).to_dict()},
            x=25.0,
            y=30.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(
                Path(tmpdir),
                _runtime_scene_payload([bounds, respawn], player_x=10.0, player_y=120.0),
            )
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "level_bounds_exited")
                missing_event = _recent_event(api, "level_bounds_respawn_missing")
                player = api.get_entity("Player")
                transform = player["components"]["Transform"]
                self.assertEqual(event["data"]["side"], "bottom")
                self.assertEqual(event["data"]["player_y"], 120.0)
                self.assertEqual(transform["x"], 25.0)
                self.assertEqual(transform["y"], 30.0)
                self.assertEqual(missing_event, {})
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_level_bounds_bottom_exit_without_respawn_emits_missing_respawn(self) -> None:
        bounds = _entity_payload("LevelBounds", {"LevelBounds2D": _bounds_payload()})
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(
                Path(tmpdir),
                _runtime_scene_payload([bounds], player_x=10.0, player_y=120.0),
            )
            before = scene_path.read_text(encoding="utf-8")
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                exit_event = _recent_event(api, "level_bounds_exited")
                missing_event = _recent_event(api, "level_bounds_respawn_missing")
                self.assertEqual(exit_event["data"]["side"], "bottom")
                self.assertEqual(missing_event["data"]["player"], "Player")
                self.assertEqual(missing_event["data"]["bounds_entity"], "LevelBounds")
                self.assertEqual(missing_event["data"]["reason"], "no_active_respawn_point")
                self.assertEqual(scene_path.read_text(encoding="utf-8"), before)
            finally:
                api.shutdown()

    def test_goal_overlap_emits_goal_reached(self) -> None:
        goal = _entity_payload(
            "Goal",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Goal2D": Goal2D(next_scene="levels/next.json").to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([goal]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                event = _recent_event(api, "goal_reached")
                self.assertEqual(event["data"]["player"], "Player")
                self.assertEqual(event["data"]["goal"], "Goal")
                self.assertEqual(event["data"]["next_scene"], "levels/next.json")
            finally:
                api.shutdown()

    def test_goal_event_does_not_reemit_for_repeated_contact_in_same_play_session(self) -> None:
        goal = _entity_payload(
            "Goal",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Goal2D": Goal2D(next_scene="levels/next.json").to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([goal]))
            api = _runtime_api(scene_path, Path(tmpdir))
            try:
                api.load_level(scene_path.as_posix())
                api.play()
                api.step(1)
                api.step(1)
                goal_events = [event for event in api.get_recent_events(50) if event["name"] == "goal_reached"]
                self.assertEqual(len(goal_events), 1)
            finally:
                api.shutdown()

    def test_motor_runtime_events_step_frames_sees_semantic_events_without_persisting_scene(self) -> None:
        coin = _entity_payload(
            "Coin",
            {
                "Collider": _collider_payload(is_trigger=True),
                "Collectible2D": Collectible2D(points=2, destroy_on_collect=True).to_dict(),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_path = _write_project_with_scene(Path(tmpdir), _runtime_scene_payload([coin]))
            before = scene_path.read_text(encoding="utf-8")
            env = os.environ.copy()
            python_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "motor",
                    "runtime",
                    "events",
                    "--project",
                    scene_path.parents[1].as_posix(),
                    "--step-frames",
                    "1",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout[result.stdout.index("{"):])
            event_names = [event["name"] for event in payload["data"]["events"]]
            self.assertIn("collectible_collected", event_names)
            self.assertEqual(payload["data"]["step_frames"], 1)
            self.assertEqual(scene_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
