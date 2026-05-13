import ast
import importlib
import json
import sys
import unittest
from pathlib import Path


UI_CORE_ROOT = Path(__file__).resolve().parents[1] / "engine" / "editor" / "ui_core"
UI_CORE_MODULES = [
    "__init__",
    "tokens",
    "geometry",
    "widget_state",
    "colors",
    "theme",
    "protocols",
    "property_widgets",
    "inspector",
    "tree_view",
]


class UICorePurityTests(unittest.TestCase):
    def test_import_ui_core_does_not_import_pyray(self) -> None:
        sys.modules.pop("pyray", None)
        importlib.import_module("engine.editor.ui_core")
        self.assertNotIn("pyray", sys.modules)

    def test_ui_core_static_imports_stay_pure(self) -> None:
        banned_exact = {
            "pyray",
            "engine.editor.ui",
            "engine.editor.ui.icons",
            "engine.editor.ui.input",
            "engine.editor.ui.draw",
            "engine.editor.ui.panels",
            "engine.editor.ui.widgets",
            "engine.editor.ui.scroll",
        }
        banned_prefixes = ("pyray.", "engine.editor.ui.")

        for module_name in UI_CORE_MODULES:
            path = UI_CORE_ROOT / f"{module_name}.py"
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)

            for imported in imports:
                self.assertNotIn(imported, banned_exact, f"{module_name} imports {imported}")
                self.assertFalse(
                    imported.startswith(banned_prefixes),
                    f"{module_name} imports {imported}",
                )

    def test_core_symbols_accessible(self) -> None:
        import engine.editor.ui_core as ui_core

        self.assertEqual(ui_core.EDITOR_BG, (56, 56, 56, 255))
        self.assertEqual(ui_core.UNITY_DARK.bg, ui_core.EDITOR_BG)
        self.assertEqual(ui_core.inset_rect((0, 0, 10, 10), 2), (2.0, 2.0, 6.0, 6.0))

        descriptor = ui_core.PropertyDescriptor("is_active", ui_core.PropertyKind.BOOL, value=True)
        self.assertEqual(descriptor.display_name, "Is Active")

        node = ui_core.TreeNode(1, "Player", 0, "Entity", [])
        self.assertTrue(ui_core.matches_search(node, "player"))

        model = ui_core.build_inspector_model_from_dict({"name": "Player", "components": {"Transform": {"x": 1.0}}})
        self.assertIsNotNone(model.find_group("Entity"))
        self.assertIsNotNone(model.find_property("Transform", "x"))

    def test_ui_core_contract_metadata_is_json_dict_like(self) -> None:
        import engine.editor.ui_core as ui_core

        metadata = ui_core.UI_CORE_CONTRACT
        self.assertIsInstance(metadata, dict)
        self.assertIn("UI_CORE_CONTRACT", ui_core.__all__)
        self.assertEqual(metadata["schema_version"], 1)
        self.assertFalse(metadata["engine_api_surface"])
        self.assertFalse(metadata["cli_surface"])
        self.assertIn("dataclasses", metadata["data_shapes"])
        self.assertIsInstance(json.loads(json.dumps(metadata)), dict)

    def test_old_shim_paths_match_core_symbols(self) -> None:
        from engine.editor.ui import geometry as old_geometry
        from engine.editor.ui import inspector as old_inspector
        from engine.editor.ui import property_widgets as old_property_widgets
        from engine.editor.ui import theme as old_theme
        from engine.editor.ui import tokens as old_tokens
        from engine.editor.ui import tree_view as old_tree_view
        from engine.editor.ui import widget_state as old_widget_state
        from engine.editor.ui_core import geometry, inspector, property_widgets, theme, tokens, tree_view, widget_state

        self.assertEqual(old_tokens.EDITOR_BG, tokens.EDITOR_BG)
        self.assertIs(old_geometry.inset_rect, geometry.inset_rect)
        self.assertIs(old_widget_state.WidgetState, widget_state.WidgetState)
        self.assertIs(old_theme.EditorTheme, theme.EditorTheme)
        self.assertIs(old_property_widgets.PropertyDescriptor, property_widgets.PropertyDescriptor)
        self.assertIs(old_inspector.InspectorModel, inspector.InspectorModel)
        self.assertIs(old_tree_view.TreeModel, tree_view.TreeModel)


if __name__ == "__main__":
    unittest.main()
