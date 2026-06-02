"""Focused tests for AuthoringAPI.create_entity tag/layer/active
and SceneWorkspaceAPI.get_active_scene(include_entities)."""

import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.project.project_service import ProjectService


class TestCreateEntityCompat(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.level_path = self.root / "levels" / "test_authoring.json"
        self.level_path.write_text(
            json.dumps(
                {"name": "TestScene", "entities": [], "rules": [], "feature_metadata": {}},
                indent=2,
            ),
            encoding="utf-8",
        )
        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level("levels/test_authoring.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_create_entity_backward_compat_no_kwargs(self) -> None:
        """Old calls without tag/layer/active still work."""
        result = self.api.create_entity("OldStyle")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("OldStyle")
        self.assertEqual(entity["name"], "OldStyle")

    def test_create_entity_backward_compat_with_components(self) -> None:
        """Old calls with only components still work."""
        result = self.api.create_entity(
            "WithComponents",
            {"Transform": {"x": 10.0, "y": 20.0}},
        )
        self.assertTrue(result["success"])
        entity = self.api.get_entity("WithComponents")
        self.assertEqual(entity["components"]["Transform"]["x"], 10.0)

    def test_create_entity_applies_tag(self) -> None:
        """create_entity with tag= applies it post-create."""
        result = self.api.create_entity("Tagged", tag="Player")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("Tagged")
        self.assertEqual(entity["tag"], "Player")

    def test_create_entity_applies_layer(self) -> None:
        """create_entity with layer= applies it post-create."""
        result = self.api.create_entity("Layered", layer="UI")
        self.assertTrue(result["success"])
        entity = self.api.get_entity("Layered")
        self.assertEqual(entity["layer"], "UI")

    def test_create_entity_applies_active(self) -> None:
        """create_entity with active=False applies it post-create."""
        result = self.api.create_entity("Inactive", active=False)
        self.assertTrue(result["success"])
        entity = self.api.get_entity("Inactive")
        self.assertFalse(entity["active"])

    def test_create_entity_applies_all_three(self) -> None:
        """create_entity with tag, layer, and active applies all."""
        result = self.api.create_entity(
            "FullFeatured",
            tag="Enemy",
            layer="Actors",
            active=False,
        )
        self.assertTrue(result["success"])
        entity = self.api.get_entity("FullFeatured")
        self.assertEqual(entity["tag"], "Enemy")
        self.assertEqual(entity["layer"], "Actors")
        self.assertFalse(entity["active"])

    def test_create_entity_duplicate_name_still_fails(self) -> None:
        """Duplicate entity name still returns failure."""
        self.api.create_entity("Unique")
        result = self.api.create_entity("Unique", tag="Player")
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Entity already exists")

    def test_create_entity_with_components_and_properties(self) -> None:
        """create_entity with components + tag/layer/active works together."""
        result = self.api.create_entity(
            "Mixed",
            {"Transform": {"x": 5.0}},
            tag="NPC",
            layer="Props",
            active=True,
        )
        self.assertTrue(result["success"])
        entity = self.api.get_entity("Mixed")
        self.assertEqual(entity["tag"], "NPC")
        self.assertEqual(entity["layer"], "Props")
        self.assertTrue(entity["active"])
        self.assertEqual(entity["components"]["Transform"]["x"], 5.0)

    def test_create_entity_no_scene_fails_safely(self) -> None:
        """create_entity with tag/layer/active fails safely when no scene."""
        api2 = EngineAPI(project_root=self.root.as_posix())
        try:
            result = api2.create_entity("Ghost", tag="Enemy")
            self.assertFalse(result["success"])
        finally:
            api2.shutdown()


class TestGetActiveSceneEntities(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.level_path = self.root / "levels" / "test_scene.json"
        self.level_path.write_text(
            json.dumps(
                {
                    "name": "TestScene",
                    "entities": [
                        {
                            "name": "Player",
                            "active": True,
                            "tag": "Player",
                            "layer": "Default",
                            "components": {
                                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            },
                        },
                        {
                            "name": "Ground",
                            "active": True,
                            "tag": "Untagged",
                            "layer": "Default",
                            "components": {
                                "Transform": {"enabled": True, "x": 0.0, "y": 400.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            },
                        },
                    ],
                    "rules": [],
                    "feature_metadata": {},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level("levels/test_scene.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_get_active_scene_default_summary(self) -> None:
        """Default call returns summary dict without entities list."""
        summary = self.api.get_active_scene()
        self.assertIsInstance(summary, dict)
        self.assertIn("path", summary)
        self.assertNotIn("entities", summary)
        self.assertNotIn("entity_count", summary)

    def test_get_active_scene_include_entities(self) -> None:
        """include_entities=True adds entities list and entity_count."""
        result = self.api.get_active_scene(include_entities=True)
        self.assertIsInstance(result, dict)
        self.assertIn("entities", result)
        self.assertIn("entity_count", result)
        self.assertEqual(result["entity_count"], 2)
        self.assertIsInstance(result["entities"], list)
        self.assertIn("Player", result["entities"])
        self.assertIn("Ground", result["entities"])

    def test_get_active_scene_include_entities_new_entity(self) -> None:
        """entities list reflects entities created after load."""
        self.api.create_entity("Enemy")
        result = self.api.get_active_scene(include_entities=True)
        self.assertEqual(result["entity_count"], 3)
        self.assertIn("Enemy", result["entities"])

    def test_get_active_scene_no_world_include_entities_safe(self) -> None:
        """include_entities=True is safe when no world is loaded."""
        api2 = EngineAPI(project_root=self.root.as_posix())
        try:
            result = api2.get_active_scene(include_entities=True)
            self.assertEqual(result, {})
        finally:
            api2.shutdown()


if __name__ == "__main__":
    unittest.main()
