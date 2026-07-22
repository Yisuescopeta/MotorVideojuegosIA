from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class EditorCompositionFitnessTests(unittest.TestCase):
    def test_game_does_not_reach_scene_manager_private_state(self) -> None:
        source = (ROOT / "engine/core/game.py").read_text(encoding="utf-8-sig")
        forbidden = (
            "manager._projection",
            "manager._workspace",
            "manager._change_history",
            "manager._serializable_mutations",
        )
        self.assertEqual([token for token in forbidden if token in source], [])

    def test_only_editor_application_constructs_preview_registry(self) -> None:
        violations: list[str] = []
        for path in (ROOT / "engine/core", ROOT / "engine/editor").__iter__():
            if not path.exists():
                continue
            for source_path in path.rglob("*.py"):
                tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    called = node.func
                    if isinstance(called, ast.Name) and called.id == "PreviewLeaseRegistry":
                        violations.append(str(source_path.relative_to(ROOT)))
        self.assertEqual(violations, [])

    def test_consumers_do_not_inject_composition_root(self) -> None:
        violations: list[str] = []
        for source_path in (ROOT / "engine").rglob("*.py"):
            if source_path.name in {"composition_root.py", "__init__.py"}:
                continue
            source = source_path.read_text(encoding="utf-8-sig")
            if "EngineCompositionRoot" in source:
                violations.append(str(source_path.relative_to(ROOT)))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
