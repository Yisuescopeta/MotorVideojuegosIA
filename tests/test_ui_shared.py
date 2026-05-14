"""Purity and integration tests for engine.ui.shared module.

Verifies:
1. shared module imports cleanly without pyray, editor/, or engine internals.
2. Editor UI modules can re-import from shared without breakage.
3. Functions work correctly on pure data.
"""

import ast
import importlib
import sys
import unittest
from pathlib import Path


UI_ROOT = Path(__file__).resolve().parents[1] / "engine" / "ui"
SHARED_MODULE_FILES = [
    "__init__",
    "shared",
    "shared_constants",
]


class SharedUIPurityTests(unittest.TestCase):
    """Verify engine.ui.shared imports stay pure (no pyray, no editor, no engine internals)."""

    def test_import_shared_does_not_import_pyray(self) -> None:
        sys.modules.pop("pyray", None)
        sys.modules.pop("raylib", None)
        importlib.import_module("engine.ui.shared")
        self.assertNotIn("pyray", sys.modules)
        self.assertNotIn("raylib", sys.modules)

    def test_import_shared_constants_does_not_import_pyray(self) -> None:
        sys.modules.pop("pyray", None)
        sys.modules.pop("raylib", None)
        importlib.import_module("engine.ui.shared_constants")
        self.assertNotIn("pyray", sys.modules)
        self.assertNotIn("raylib", sys.modules)

    def test_import_ui_package_does_not_import_pyray(self) -> None:
        sys.modules.pop("pyray", None)
        sys.modules.pop("raylib", None)
        importlib.import_module("engine.ui")
        self.assertNotIn("pyray", sys.modules)
        self.assertNotIn("raylib", sys.modules)

    def test_shared_static_imports_stay_pure(self) -> None:
        banned_exact = {
            "pyray",
            "raylib",
            "engine.editor",
            "engine.editor.ui",
            "engine.editor.ui_core",
            "engine.core",
            "engine.systems",
            "engine.components",
            "engine.scenes",
            "engine.app",
        }
        banned_prefixes = (
            "pyray.",
            "raylib.",
            "engine.editor.",
            "engine.core.",
            "engine.systems.",
            "engine.components.",
            "engine.scenes.",
            "engine.app.",
        )

        for module_name in SHARED_MODULE_FILES:
            path = UI_ROOT / f"{module_name}.py"
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


class SharedUIGeometryTests(unittest.TestCase):
    """Verify geometry helpers work on pure data."""

    def setUp(self):
        from engine.ui.shared import (
            Rect,
            clamp_rect,
            inset_rect,
            rect_contains,
            rect_intersection,
            rect_union,
            split_bottom,
            split_left,
            split_right,
            split_top,
        )

        self.inset_rect = inset_rect
        self.split_top = split_top
        self.split_bottom = split_bottom
        self.split_left = split_left
        self.split_right = split_right
        self.rect_contains = rect_contains
        self.clamp_rect = clamp_rect
        self.rect_union = rect_union
        self.rect_intersection = rect_intersection

    def test_inset_rect_positive(self):
        result = self.inset_rect((0, 0, 100, 100), 10)
        self.assertEqual(result, (10.0, 10.0, 80.0, 80.0))

    def test_inset_rect_zero(self):
        result = self.inset_rect((0, 0, 100, 100), 0)
        self.assertEqual(result, (0.0, 0.0, 100.0, 100.0))

    def test_inset_rect_too_large(self):
        result = self.inset_rect((0, 0, 10, 10), 100)
        self.assertEqual(result, (100.0, 100.0, 0.0, 0.0))

    def test_split_top(self):
        top, bottom = self.split_top((0, 0, 100, 200), 50)
        self.assertEqual(top, (0, 0, 100, 50))
        self.assertEqual(bottom, (0, 50, 100, 150))

    def test_split_bottom(self):
        main, bottom = self.split_bottom((0, 0, 100, 200), 50)
        self.assertEqual(main, (0, 0, 100, 150))
        self.assertEqual(bottom, (0, 150, 100, 50))

    def test_split_left(self):
        left, right = self.split_left((0, 0, 200, 100), 80)
        self.assertEqual(left, (0, 0, 80, 100))
        self.assertEqual(right, (80, 0, 120, 100))

    def test_split_right(self):
        main, right = self.split_right((0, 0, 200, 100), 60)
        self.assertEqual(main, (0, 0, 140, 100))
        self.assertEqual(right, (140, 0, 60, 100))

    def test_rect_contains_inside(self):
        self.assertTrue(self.rect_contains((0, 0, 100, 100), 50, 50))

    def test_rect_contains_boundary(self):
        self.assertTrue(self.rect_contains((0, 0, 100, 100), 0, 0))
        self.assertTrue(self.rect_contains((0, 0, 100, 100), 100, 100))

    def test_rect_contains_outside(self):
        self.assertFalse(self.rect_contains((0, 0, 100, 100), -1, 50))
        self.assertFalse(self.rect_contains((0, 0, 100, 100), 101, 50))

    def test_clamp_rect_inside(self):
        result = self.clamp_rect((10, 10, 50, 50), (0, 0, 100, 100))
        self.assertEqual(result, (10, 10, 50, 50))

    def test_clamp_rect_oversized(self):
        result = self.clamp_rect((0, 0, 200, 200), (0, 0, 100, 100))
        self.assertEqual(result, (0, 0, 100, 100))

    def test_rect_union(self):
        result = self.rect_union((0, 0, 10, 10), (5, 5, 15, 15))
        self.assertEqual(result, (0, 0, 20, 20))

    def test_rect_intersection(self):
        result = self.rect_intersection((0, 0, 10, 10), (5, 5, 15, 15))
        self.assertEqual(result, (5, 5, 5, 5))

    def test_rect_intersection_disjoint(self):
        result = self.rect_intersection((0, 0, 10, 10), (20, 20, 10, 10))
        self.assertIsNone(result)


class SharedUIColorTests(unittest.TestCase):
    """Verify color helpers work on pure data."""

    def setUp(self):
        from engine.ui.shared import (
            int_to_rgba,
            is_dark_theme,
            lerp_color,
            rgba,
            rgba_to_hex,
            rgba_to_int,
            with_alpha,
        )

        self.rgba = rgba
        self.with_alpha = with_alpha
        self.lerp_color = lerp_color
        self.is_dark_theme = is_dark_theme
        self.rgba_to_int = rgba_to_int
        self.int_to_rgba = int_to_rgba
        self.rgba_to_hex = rgba_to_hex

    def test_rgba_clamps(self):
        self.assertEqual(self.rgba(300, -10, 128, 500), (255, 0, 128, 255))

    def test_with_alpha(self):
        self.assertEqual(self.with_alpha((100, 200, 50, 255), 128), (100, 200, 50, 128))

    def test_lerp_color_halfway(self):
        result = self.lerp_color((0, 0, 0, 255), (200, 200, 200, 255), 0.5)
        self.assertEqual(result, (100, 100, 100, 255))

    def test_is_dark_theme_dark(self):
        self.assertTrue(self.is_dark_theme((30, 30, 30, 255)))

    def test_is_dark_theme_light(self):
        self.assertFalse(self.is_dark_theme((240, 240, 240, 255)))

    def test_rgba_to_int_and_back(self):
        original = (100, 150, 200, 255)
        packed = self.rgba_to_int(original)
        unpacked = self.int_to_rgba(packed)
        self.assertEqual(unpacked, original)

    def test_rgba_to_hex_with_alpha(self):
        self.assertEqual(self.rgba_to_hex((255, 0, 128, 255)), "#FF0080FF")

    def test_rgba_to_hex_without_alpha(self):
        self.assertEqual(self.rgba_to_hex((255, 0, 128, 0), include_alpha=False), "#FF0080")


class SharedUIMathTests(unittest.TestCase):
    """Verify math/estimate helpers."""

    def setUp(self):
        from engine.ui.shared import (
            clamp,
            distance,
            lerp,
            line_height_estimate,
            text_width_estimate,
        )

        self.clamp = clamp
        self.lerp = lerp
        self.distance = distance
        self.text_width_estimate = text_width_estimate
        self.line_height_estimate = line_height_estimate

    def test_clamp(self):
        self.assertEqual(self.clamp(5, 0, 10), 5)
        self.assertEqual(self.clamp(-5, 0, 10), 0)
        self.assertEqual(self.clamp(15, 0, 10), 10)

    def test_lerp(self):
        self.assertEqual(self.lerp(0, 100, 0.5), 50.0)
        self.assertEqual(self.lerp(0, 100, 0.0), 0.0)
        self.assertEqual(self.lerp(0, 100, 1.0), 100.0)

    def test_distance(self):
        self.assertAlmostEqual(self.distance(0, 0, 3, 4), 5.0)

    def test_text_width_estimate(self):
        w = self.text_width_estimate("hello", 16)
        self.assertGreater(w, 30)
        self.assertLess(w, 60)

    def test_text_width_estimate_empty(self):
        self.assertEqual(self.text_width_estimate("", 16), 0.0)

    def test_line_height_estimate(self):
        self.assertAlmostEqual(self.line_height_estimate(16), 22.4)


class SharedUIConstantsTests(unittest.TestCase):
    """Verify shared_constants are importable and have expected types."""

    def test_rgba_type(self):
        from engine.ui.shared_constants import RGBA

        val: RGBA = (0, 0, 0, 0)
        self.assertEqual(val, (0, 0, 0, 0))

    def test_font_sizes_positive(self):
        from engine.ui import shared_constants as sc

        self.assertGreater(sc.FONT_SIZE_SM, 0)
        self.assertLess(sc.FONT_SIZE_SM, sc.FONT_SIZE_MD)
        self.assertLess(sc.FONT_SIZE_MD, sc.FONT_SIZE_LG)

    def test_colors_are_rgba_tuples(self):
        from engine.ui import shared_constants as sc

        self.assertEqual(len(sc.COLOR_TRANSPARENT), 4)
        self.assertEqual(sc.COLOR_TRANSPARENT[3], 0)
        self.assertEqual(sc.COLOR_BLACK[3], 255)

    def test_shortcuts_are_tuples(self):
        from engine.ui import shared_constants as sc

        self.assertIsInstance(sc.KEY_SHORTCUT_SAVE, tuple)
        self.assertIn("ctrl", sc.KEY_SHORTCUT_SAVE)
        self.assertIn("s", sc.KEY_SHORTCUT_SAVE)


class SharedUIEditorReimportTests(unittest.TestCase):
    """Verify editor UI modules can import from shared without regressions."""

    def test_ui_core_geometry_functions_match_shared(self):
        from engine.editor.ui_core import geometry as ui_core_geom
        from engine.ui import shared as ui_shared

        # Same API surface for shared functions
        for func_name in ["inset_rect", "split_top", "split_bottom", "split_left",
                          "split_right", "rect_contains", "clamp_rect"]:
            self.assertTrue(hasattr(ui_core_geom, func_name), f"ui_core missing {func_name}")
            self.assertTrue(hasattr(ui_shared, func_name), f"shared missing {func_name}")

        # Behavior parity
        self.assertEqual(ui_core_geom.inset_rect((0, 0, 100, 100), 10),
                         ui_shared.inset_rect((0, 0, 100, 100), 10))
        self.assertEqual(ui_core_geom.split_top((0, 0, 100, 200), 50),
                         ui_shared.split_top((0, 0, 100, 200), 50))
        self.assertEqual(ui_core_geom.rect_contains((0, 0, 100, 100), 50, 50),
                         ui_shared.rect_contains((0, 0, 100, 100), 50, 50))

    def test_ui_core_colors_functions_match_shared(self):
        from engine.editor.ui_core import colors as ui_core_colors
        from engine.ui import shared as ui_shared

        for func_name in ["rgba", "with_alpha", "lerp_color", "is_dark_theme",
                          "rgba_to_int", "int_to_rgba", "rgba_to_hex"]:
            self.assertTrue(hasattr(ui_core_colors, func_name), f"ui_core missing {func_name}")
            self.assertTrue(hasattr(ui_shared, func_name), f"shared missing {func_name}")

        # Behavior parity
        self.assertEqual(ui_core_colors.rgba(100, 150, 200),
                         ui_shared.rgba(100, 150, 200))
        self.assertEqual(ui_core_colors.with_alpha((100, 200, 50, 255), 128),
                         ui_shared.with_alpha((100, 200, 50, 255), 128))
        self.assertEqual(ui_core_colors.is_dark_theme((30, 30, 30, 255)),
                         ui_shared.is_dark_theme((30, 30, 30, 255)))

    def test_editor_ui_shims_still_work_after_shared_exists(self):
        """Verify editor ui/ shims still re-export correctly."""
        from engine.editor.ui import geometry as editor_geom
        from engine.editor.ui import colors as editor_colors

        self.assertTrue(callable(editor_geom.inset_rect))
        self.assertTrue(callable(editor_geom.split_top))
        self.assertTrue(callable(editor_colors.rgba))
        self.assertTrue(callable(editor_colors.lerp_color))

        # to_ray_color stays impure in editor.ui
        self.assertTrue(callable(editor_colors.to_ray_color))

    def test_shared_does_not_leak_editor_state(self):
        """shared module has no references to EditorTheme, ThemeRegistry, SceneManager, etc."""
        import engine.ui as ui

        editor_only = ["EditorTheme", "ThemeRegistry", "UNITY_DARK", "UNITY_LIGHT",
                       "SceneManager", "InspectorModel", "TreeModel",
                       "get_active_theme", "set_active_theme"]
        for name in editor_only:
            self.assertFalse(hasattr(ui, name), f"shared leaks {name}")

        # ui.shared and ui.shared_constants also clean
        import engine.ui.shared as s
        import engine.ui.shared_constants as sc

        for name in editor_only:
            self.assertFalse(hasattr(s, name), f"shared.py leaks {name}")
            self.assertFalse(hasattr(sc, name), f"shared_constants.py leaks {name}")


if __name__ == "__main__":
    unittest.main()
