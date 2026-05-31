from __future__ import annotations

import builtins
import importlib
import sys
import unittest
from unittest.mock import patch


class TestAndroidRuntimeImports(unittest.TestCase):
    def test_engine_utils_imports_without_tkinter(self):
        original_import = builtins.__import__

        def import_without_tkinter(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "tkinter" or name.startswith("tkinter."):
                raise ImportError("No module named 'tkinter'")
            return original_import(name, globals, locals, fromlist, level)

        for module_name in list(sys.modules):
            if module_name == "engine.utils" or module_name.startswith("engine.utils."):
                sys.modules.pop(module_name, None)

        with patch("builtins.__import__", side_effect=import_without_tkinter):
            importlib.import_module("engine.utils.viewport")
            clipboard = importlib.import_module("engine.utils.clipboard")

            self.assertEqual(clipboard.get_clipboard_text(), "")
            clipboard.set_clipboard_text("ignored")


if __name__ == "__main__":
    unittest.main()
