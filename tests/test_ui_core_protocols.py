import ast
import importlib
import sys
import unittest
from pathlib import Path


PROTOCOLS_PATH = (
    Path(__file__).resolve().parents[1]
    / "engine"
    / "editor"
    / "ui_core"
    / "protocols.py"
)


class UICoreProtocolsTests(unittest.TestCase):
    def test_import_protocols_does_not_import_pyray(self) -> None:
        sys.modules.pop("pyray", None)

        importlib.import_module("engine.editor.ui_core.protocols")

        self.assertNotIn("pyray", sys.modules)

    def test_protocols_static_imports_stay_pure(self) -> None:
        tree = ast.parse(PROTOCOLS_PATH.read_text(encoding="utf-8"), filename=str(PROTOCOLS_PATH))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        for imported in imports:
            self.assertNotEqual(imported, "pyray")
            self.assertFalse(imported.startswith("pyray."))
            self.assertNotEqual(imported, "engine.editor.ui")
            self.assertFalse(imported.startswith("engine.editor.ui."))

    def test_protocols_exported_from_ui_core(self) -> None:
        import engine.editor.ui_core as ui_core
        from engine.editor.ui_core.protocols import EntityLike, PropertyValue, WorldLike

        self.assertIs(ui_core.EntityLike, EntityLike)
        self.assertIs(ui_core.WorldLike, WorldLike)
        self.assertIs(ui_core.PropertyValue, PropertyValue)
        self.assertIn("EntityLike", ui_core.__all__)
        self.assertIn("WorldLike", ui_core.__all__)
        self.assertIn("PropertyValue", ui_core.__all__)

    def test_runtime_structural_matches(self) -> None:
        from engine.editor.ui_core.protocols import EntityLike, WorldLike

        class EntityStub:
            id = 1
            name = "Player"

        class WorldStub:
            def iter_all_entities(self):
                return [EntityStub()]

        self.assertIsInstance(EntityStub(), EntityLike)
        self.assertIsInstance(WorldStub(), WorldLike)
        self.assertNotIsInstance(object(), EntityLike)
        self.assertNotIsInstance(object(), WorldLike)


if __name__ == "__main__":
    unittest.main()
