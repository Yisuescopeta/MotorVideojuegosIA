"""
tests/test_scene_inheritance.py — Tests for scene inheritance (Godot "editable children").
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from engine.scenes.scene_inheritance import (
    create_child_scene_payload,
    resolve_inherited_scene,
)
from engine.serialization.schema import CURRENT_SCENE_SCHEMA_VERSION, validate_scene_data


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class TestSceneInheritance(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_scene_inheritance_")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _base_scene(self) -> dict:
        return {
            "name": "BaseScene",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [
                {
                    "name": "Player",
                    "active": True,
                    "tag": "Player",
                    "layer": "Default",
                    "parent": None,
                    "components": {
                        "Transform": {"enabled": True, "x": 100.0, "y": 200.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                        "Sprite": {"enabled": True, "texture": {"path": "player.png", "guid": ""}, "texture_path": "player.png"},
                    },
                    "component_metadata": {},
                    "id": "entity_player",
                },
                {
                    "name": "Enemy",
                    "active": True,
                    "tag": "Enemy",
                    "layer": "Default",
                    "parent": None,
                    "components": {
                        "Transform": {"enabled": True, "x": 300.0, "y": 400.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    },
                    "component_metadata": {},
                    "id": "entity_enemy",
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }

    def test_resolve_scene_without_inheritance(self) -> None:
        """A scene without inherits_from should return unchanged data."""
        data = self._base_scene()
        resolved = resolve_inherited_scene("", data)
        self.assertEqual(resolved["name"], "BaseScene")
        self.assertEqual(len(resolved["entities"]), 2)

    def test_resolve_inherited_scene_loads_base(self) -> None:
        """Child scene should inherit all entities from base."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")
        _write_json(base_path, self._base_scene())

        child_data = create_child_scene_payload("ChildScene", "base.json")
        _write_json(child_path, child_data)

        resolved = resolve_inherited_scene(child_path, child_data)
        self.assertEqual(resolved["name"], "ChildScene")
        self.assertEqual(len(resolved["entities"]), 2)
        self.assertNotIn("inherits_from", resolved)

    def test_override_entity_in_child(self) -> None:
        """Child can override component properties of a base entity."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")
        _write_json(base_path, self._base_scene())

        child_data = {
            "name": "ChildScene",
            "inherits_from": "base.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {"x": 999.0, "y": 888.0},
                    },
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        _write_json(child_path, child_data)

        resolved = resolve_inherited_scene(child_path, child_data)
        player = next(e for e in resolved["entities"] if e["name"] == "Player")
        self.assertEqual(player["components"]["Transform"]["x"], 999.0)
        self.assertEqual(player["components"]["Transform"]["y"], 888.0)
        # Rotation should still be from base
        self.assertEqual(player["components"]["Transform"]["rotation"], 0.0)
        # Sprite should still be from base
        self.assertIn("Sprite", player["components"])

    def test_add_new_entity_in_child(self) -> None:
        """Child can add new entities not present in the base."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")
        _write_json(base_path, self._base_scene())

        child_data = {
            "name": "ChildScene",
            "inherits_from": "base.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [
                {
                    "name": "Boss",
                    "active": True,
                    "tag": "Boss",
                    "layer": "Default",
                    "parent": None,
                    "components": {
                        "Transform": {"enabled": True, "x": 500.0, "y": 500.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    },
                    "component_metadata": {},
                    "id": "entity_boss",
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        _write_json(child_path, child_data)

        resolved = resolve_inherited_scene(child_path, child_data)
        self.assertEqual(len(resolved["entities"]), 3)
        boss = next(e for e in resolved["entities"] if e["name"] == "Boss")
        self.assertEqual(boss["components"]["Transform"]["x"], 500.0)

    def test_backward_compat_no_inheritance_field(self) -> None:
        """A scene without inherits_from field should load identically."""
        data = self._base_scene()
        resolved = resolve_inherited_scene("", data)
        self.assertEqual(resolved["name"], data["name"])
        self.assertEqual(len(resolved["entities"]), len(data["entities"]))
        # Schema validation should pass
        errors = validate_scene_data(resolved)
        self.assertEqual(errors, [])

    def test_circular_inheritance_detected(self) -> None:
        """Circular inherits_from chains should raise ValueError."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")

        base_data = self._base_scene()
        base_data["inherits_from"] = "child.json"
        _write_json(base_path, base_data)

        child_data = {
            "name": "ChildScene",
            "inherits_from": "base.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [],
            "rules": [],
            "feature_metadata": {},
        }
        _write_json(child_path, child_data)

        with self.assertRaises(ValueError) as ctx:
            resolve_inherited_scene(child_path, child_data)
        self.assertIn("Circular", str(ctx.exception))

    def test_nested_inheritance(self) -> None:
        """Grandchild inherits from child, which inherits from base."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")
        grandchild_path = os.path.join(self.temp_dir, "grandchild.json")

        _write_json(base_path, self._base_scene())

        child_data = {
            "name": "ChildScene",
            "inherits_from": "base.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [
                {
                    "name": "Player",
                    "components": {"Transform": {"x": 50.0}},
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        _write_json(child_path, child_data)

        grandchild_data = {
            "name": "GrandchildScene",
            "inherits_from": "child.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [
                {
                    "name": "Player",
                    "components": {"Transform": {"y": 99.0}},
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        _write_json(grandchild_path, grandchild_data)

        resolved = resolve_inherited_scene(grandchild_path, grandchild_data)
        self.assertEqual(resolved["name"], "GrandchildScene")
        player = next(e for e in resolved["entities"] if e["name"] == "Player")
        self.assertEqual(player["components"]["Transform"]["x"], 50.0)  # From child
        self.assertEqual(player["components"]["Transform"]["y"], 99.0)  # From grandchild

    def test_child_override_entity_properties(self) -> None:
        """Child can override entity-level properties (active, tag, layer, parent, groups)."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")
        _write_json(base_path, self._base_scene())

        child_data = {
            "name": "ChildScene",
            "inherits_from": "base.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [
                {
                    "name": "Enemy",
                    "active": False,
                    "tag": "Boss",
                    "layer": "UI",
                },
            ],
            "rules": [],
            "feature_metadata": {},
        }
        _write_json(child_path, child_data)

        resolved = resolve_inherited_scene(child_path, child_data)
        enemy = next(e for e in resolved["entities"] if e["name"] == "Enemy")
        self.assertEqual(enemy["active"], False)
        self.assertEqual(enemy["tag"], "Boss")
        self.assertEqual(enemy["layer"], "UI")

    def test_child_overrides_rules(self) -> None:
        """Child rules completely replace base rules."""
        base_data = self._base_scene()
        base_data["rules"] = [{"event": "on_start", "do": [{"action": "log_message", "message": "base"}]}]
        base_path = os.path.join(self.temp_dir, "base.json")
        _write_json(base_path, base_data)

        child_data = {
            "name": "ChildScene",
            "inherits_from": "base.json",
            "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
            "entities": [],
            "rules": [{"event": "on_start", "do": [{"action": "log_message", "message": "child"}]}],
            "feature_metadata": {},
        }
        child_path = os.path.join(self.temp_dir, "child.json")
        _write_json(child_path, child_data)

        resolved = resolve_inherited_scene(child_path, child_data)
        self.assertEqual(len(resolved["rules"]), 1)
        self.assertEqual(resolved["rules"][0]["do"][0]["message"], "child")

    def test_inheritance_preserves_schema_version(self) -> None:
        """Resolved scene should always have current schema version."""
        base_path = os.path.join(self.temp_dir, "base.json")
        child_path = os.path.join(self.temp_dir, "child.json")
        _write_json(base_path, self._base_scene())

        child_data = create_child_scene_payload("ChildScene", "base.json")
        _write_json(child_path, child_data)

        resolved = resolve_inherited_scene(child_path, child_data)
        self.assertEqual(resolved["schema_version"], CURRENT_SCENE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
