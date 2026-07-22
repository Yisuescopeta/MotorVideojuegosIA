import ast
import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry
from engine.scenes.scene_manager import SceneManager


class IdFirstFitnessTests(unittest.TestCase):
    _NAME_FIRST = {
        "add_component",
        "add_component_to_entity",
        "apply_edit_to_world",
        "apply_transform_state",
        "remove_component",
        "remove_component_from_entity",
        "remove_entity",
        "replace_component",
        "replace_component_data",
        "reparent_entity",
        "set_entity_parent",
        "update_component",
        "update_entity_property",
    }

    def test_id_first_methods_do_not_delegate_to_name_first_methods(self) -> None:
        root = Path(__file__).parents[1] / "engine"
        violations: list[str] = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not function.name.endswith("_by_id"):
                    continue
                for call in ast.walk(function):
                    if not isinstance(call, ast.Call):
                        continue
                    called = call.func.attr if isinstance(call.func, ast.Attribute) else ""
                    if called in self._NAME_FIRST:
                        violations.append(f"{path}:{function.lineno}->{called}:{call.lineno}")
        self.assertEqual(violations, [])

    def test_entity_ref_survives_rename_for_id_first_mutations(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(
            {
                "name": "ID first",
                "entities": [
                    {
                        "id": "hero-id",
                        "name": "Hero",
                        "components": {
                            "Transform": {
                                "x": 1.0,
                                "y": 2.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
            }
        )
        target = manager.entity_ref_by_name("Hero")
        self.assertIsNotNone(target)
        assert target is not None

        self.assertTrue(manager.update_entity_property_by_id(target.entity_id, "name", "Renamed"))
        self.assertTrue(
            manager.apply_transform_state_by_id(
                target.entity_id,
                {"x": 72.0, "y": 9.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            )
        )
        renamed = manager.find_entity_data_by_id(target.entity_id)
        self.assertIsNotNone(renamed)
        assert renamed is not None
        self.assertEqual(renamed["name"], "Renamed")
        self.assertEqual(renamed["components"]["Transform"]["x"], 72.0)


if __name__ == "__main__":
    unittest.main()
