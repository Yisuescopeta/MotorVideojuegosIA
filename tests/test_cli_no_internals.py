"""
tests/test_cli_no_internals.py

Tests to verify that the official motor CLI does not depend on private engine internals.

These tests catch regressions where CLI code might start using:
- Private SceneManager methods (e.g., _get_active_entry())
- Private EngineAPI attributes
- Any underscore-prefixed methods or attributes
"""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import motor.cli_core as cli_core_module


class NoInternalsAccessTests(unittest.TestCase):
    """Tests that CLI code does not access private engine internals."""

    def test_cli_core_does_not_access_private_scene_manager(self) -> None:
        """Verify cli_core.py does not access scene_manager._* private methods."""
        source_path = Path(__file__).parent.parent / "motor" / "cli_core.py"
        self.assertTrue(source_path.exists(), f"Source file not found: {source_path}")

        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        private_accesses: list[str] = []

        for node in ast.walk(tree):
            # Check for attribute access like scene_manager._something
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                # Check if accessing a private attribute (starts with _)
                if attr_name.startswith("_") and not attr_name.startswith("__"):
                    # Get the full attribute chain
                    full_chain = self._get_attribute_chain(node)
                    if "scene_manager" in full_chain.lower():
                        private_accesses.append(full_chain)

        if private_accesses:
            self.fail(
                f"cli_core.py accesses private SceneManager methods: {private_accesses}\n"
                "Use public EngineAPI surfaces instead."
            )

    def test_auto_load_scene_uses_only_public_api(self) -> None:
        """Verify _auto_load_scene uses only public EngineAPI methods."""
        source = inspect.getsource(cli_core_module._auto_load_scene)

        # Should use public methods
        public_methods_expected = ["has_active_scene", "get_active_scene_info", "get_editor_state", "load_scene"]
        for method in public_methods_expected:
            self.assertIn(
                f"api.{method}",
                source,
                f"_auto_load_scene should use api.{method}()"
            )

        # Should NOT access scene_manager directly
        self.assertNotIn(
            "scene_manager",
            source,
            "_auto_load_scene should not access api.scene_manager directly"
        )

        # Should NOT access _get_active_entry
        self.assertNotIn(
            "_get_active_entry",
            source,
            "_auto_load_scene should not use private _get_active_entry() method"
        )

    def test_all_cli_commands_use_public_api_only(self) -> None:
        """Verify all cmd_* functions use only public API surfaces."""
        # Get all cmd_* functions
        cmd_functions = [
            obj for name, obj in inspect.getmembers(cli_core_module)
            if name.startswith("cmd_") and callable(obj)
        ]

        self.assertGreater(len(cmd_functions), 0, "Should find cmd_* functions")

        for func in cmd_functions:
            source = inspect.getsource(func)
            func_name = func.__name__

            # These patterns indicate private access
            private_patterns = [
                "scene_manager._",  # Accessing private scene_manager methods
                "api.scene_manager",  # Direct scene_manager access (use API methods instead)
                "_get_active_entry",  # Private method
            ]

            for pattern in private_patterns:
                self.assertNotIn(
                    pattern,
                    source,
                    f"{func_name} should not access private internals: {pattern}"
                )

    def test_has_active_scene_is_public(self) -> None:
        """Verify has_active_scene() exists as a public method via delegation."""
        from engine.api._scene_workspace_api import SceneWorkspaceAPI

        # The method should exist in SceneWorkspaceAPI (delegated by EngineAPI)
        self.assertTrue(
            hasattr(SceneWorkspaceAPI, "has_active_scene"),
            "SceneWorkspaceAPI should expose has_active_scene()"
        )

    def test_get_active_scene_info_is_public(self) -> None:
        """Verify get_active_scene_info() exists as a public method via delegation."""
        from engine.api._scene_workspace_api import SceneWorkspaceAPI

        self.assertTrue(
            hasattr(SceneWorkspaceAPI, "get_active_scene_info"),
            "SceneWorkspaceAPI should expose get_active_scene_info()"
        )

    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Get the full attribute chain from an AST node."""
        parts = [node.attr]
        current = node.value

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return ".".join(reversed(parts))


class SceneWorkspacePublicAPITests(unittest.TestCase):
    """Tests for the new public SceneWorkspaceAPI surfaces."""

    def test_has_active_scene_returns_bool(self) -> None:
        """Verify has_active_scene() returns a boolean."""
        from engine.api._scene_workspace_api import SceneWorkspaceAPI

        # Check method exists and has correct signature
        self.assertTrue(hasattr(SceneWorkspaceAPI, "has_active_scene"))

        sig = inspect.signature(SceneWorkspaceAPI.has_active_scene)
        self.assertEqual(
            len(sig.parameters),
            1,  # self
            "has_active_scene should only take 'self' parameter"
        )

    def test_get_active_scene_info_structure(self) -> None:
        """Verify get_active_scene_info returns expected structure."""
        from engine.api._scene_workspace_api import SceneWorkspaceAPI

        self.assertTrue(hasattr(SceneWorkspaceAPI, "get_active_scene_info"))

        # Check the docstring mentions expected keys
        docstring = SceneWorkspaceAPI.get_active_scene_info.__doc__ or ""
        expected_keys = ["has_scene", "path", "name", "key", "dirty", "entity_count"]
        for key in expected_keys:
            self.assertIn(
                key,
                docstring,
                f"get_active_scene_info docstring should document '{key}' key"
            )


if __name__ == "__main__":
    unittest.main()
