from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.ai.compliance import run_ai_compliance
from engine.components.gameplay2d import (
    Collectible2D,
    Goal2D,
    Hazard2D,
    RespawnPoint2D,
)
from engine.components.transform import Transform
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene
from engine.serialization.schema import migrate_scene_data, validate_scene_data


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


class Gameplay2DSemanticComponentTests(unittest.TestCase):
    def test_default_creation(self) -> None:
        collectible = Collectible2D()
        hazard = Hazard2D()
        goal = Goal2D()
        respawn = RespawnPoint2D()

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

    def test_roundtrip_serialization(self) -> None:
        cases = [
            Collectible2D(points=5, destroy_on_collect=False, event_name=" coin "),
            Hazard2D(damage=3, respawn_on_touch=False, event_name=" spike "),
            Goal2D(complete_on_touch=False, next_scene=" levels/next.json ", event_name=" win "),
            RespawnPoint2D(spawn_id=" checkpoint_a ", active=False),
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

        self.assertEqual(collectible.points, 0)
        self.assertEqual(collectible.event_name, "collectible_collected")
        self.assertEqual(hazard.damage, 1)
        self.assertEqual(hazard.event_name, "hazard_touched")
        self.assertTrue(respawn.active)
        self.assertEqual(respawn.spawn_id, "default")

    def test_default_registry_lists_and_creates_components(self) -> None:
        registry = create_default_registry()
        expected = {"Collectible2D", "Hazard2D", "Goal2D", "RespawnPoint2D"}

        self.assertTrue(expected.issubset(set(registry.list_registered())))
        self.assertIsInstance(registry.create("Collectible2D", {"points": 2}), Collectible2D)
        self.assertIsInstance(registry.create("Hazard2D", {"damage": 4}), Hazard2D)
        self.assertIsInstance(registry.create("Goal2D", {"next_scene": "next"}), Goal2D)
        self.assertIsInstance(registry.create("RespawnPoint2D", {"spawn_id": "start"}), RespawnPoint2D)

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


if __name__ == "__main__":
    unittest.main()
