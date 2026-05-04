"""Tests for autoload system - declarative singleton entity loading."""
from __future__ import annotations

import json
import os
import tempfile
from unittest import TestCase

from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.autoload_system import AutoloadSystem


class TestAutoloadSystem(TestCase):
    """Test suite for AutoloadSystem."""

    def setUp(self) -> None:
        self.temp_dir: str = tempfile.mkdtemp(prefix="motor_autoload_test_")
        self.settings_dir: str = os.path.join(self.temp_dir, "settings")
        os.makedirs(self.settings_dir, exist_ok=True)
        self.prefabs_dir: str = os.path.join(self.temp_dir, "prefabs")
        os.makedirs(self.prefabs_dir, exist_ok=True)
        self.registry = create_default_registry()

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_settings(self, autoloads: dict) -> str:
        path = os.path.join(self.settings_dir, "project_settings.json")
        settings = {
            "startup_scene": "levels/level_1.json",
            "template": "empty",
            "autoloads": autoloads,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f)
        return path

    def _write_prefab(self, prefab_name: str, entities: list[dict]) -> str:
        path = os.path.join(self.prefabs_dir, f"{prefab_name}.json")
        data = {"entities": entities}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def _make_system(self) -> AutoloadSystem:
        return AutoloadSystem(project_root=self.temp_dir, registry=self.registry)

    def test_autoload_system_load(self) -> None:
        """Cargar autoloads desde project_settings.json."""
        self._write_prefab(
            "global_state",
            [
                {
                    "name": "GlobalState",
                    "active": True,
                    "tag": "Autoload",
                    "layer": "Default",
                    "parent": None,
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 0.0,
                            "y": 0.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                    "component_metadata": {},
                }
            ],
        )
        self._write_settings(
            {
                "GlobalState": {
                    "scene_path": "prefabs/global_state.json",
                    "singleton": True,
                }
            }
        )

        system = self._make_system()
        world = World()
        result = system.load_autoloads(world, scene_manager=None)

        self.assertIn("GlobalState", result)
        self.assertIsNotNone(result["GlobalState"])
        self.assertIsInstance(result["GlobalState"], int)
        self.assertEqual(len(system.list_autoloads()), 1)

    def test_autoload_get_by_name(self) -> None:
        """get_autoload retorna entity_id."""
        self._write_prefab(
            "global_state",
            [
                {
                    "name": "MyGlobal",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 0.0,
                            "y": 0.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                }
            ],
        )
        self._write_settings(
            {
                "MyGlobal": {
                    "scene_path": "prefabs/global_state.json",
                    "singleton": True,
                }
            }
        )

        system = self._make_system()
        world = World()
        system.load_autoloads(world, scene_manager=None)

        entity_id = system.get_autoload("MyGlobal")
        self.assertIsNotNone(entity_id)
        self.assertIsInstance(entity_id, int)
        self.assertGreater(entity_id, -1)

        self.assertIsNone(system.get_autoload("NonExistent"))

    def test_autoload_list(self) -> None:
        """list_autoloads retorna nombres."""
        self._write_prefab(
            "global_state",
            [
                {
                    "name": "GlobalState",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 0.0,
                            "y": 0.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                }
            ],
        )
        self._write_settings(
            {
                "GlobalState": {
                    "scene_path": "prefabs/global_state.json",
                    "singleton": True,
                }
            }
        )

        system = self._make_system()
        world = World()
        system.load_autoloads(world, scene_manager=None)

        names = system.list_autoloads()
        self.assertEqual(names, ["GlobalState"])

    def test_autoload_no_settings(self) -> None:
        """Sin archivo project_settings, no crashea."""
        system = self._make_system()
        world = World()
        result = system.load_autoloads(world, scene_manager=None)

        self.assertEqual(result, {})
        self.assertEqual(system.list_autoloads(), [])

    def test_autoload_non_singleton_skipped(self) -> None:
        """Autoloads sin singleton=true se ignoran."""
        self._write_prefab(
            "global_state",
            [
                {
                    "name": "GlobalState",
                    "components": {
                        "Transform": {
                            "enabled": True,
                            "x": 0.0,
                            "y": 0.0,
                            "rotation": 0.0,
                            "scale_x": 1.0,
                            "scale_y": 1.0,
                        }
                    },
                }
            ],
        )
        self._write_settings(
            {
                "NotSingleton": {
                    "scene_path": "prefabs/global_state.json",
                    "singleton": False,
                }
            }
        )

        system = self._make_system()
        world = World()
        result = system.load_autoloads(world, scene_manager=None)

        self.assertNotIn("NotSingleton", result)
        self.assertEqual(system.list_autoloads(), [])

    def test_autoload_missing_scene(self) -> None:
        """Scene_path no existe, se ignora sin crashear."""
        self._write_settings(
            {
                "MissingScene": {
                    "scene_path": "prefabs/non_existent.json",
                    "singleton": True,
                }
            }
        )

        system = self._make_system()
        world = World()
        result = system.load_autoloads(world, scene_manager=None)

        self.assertNotIn("MissingScene", result)
        self.assertEqual(system.list_autoloads(), [])
