import json
import subprocess
import sys
import unittest
from pathlib import Path

from engine.ui.presets import get_ui_preset_definition, list_ui_preset_definitions

ROOT = Path(__file__).resolve().parents[1]


class UIPresetDefinitionsTests(unittest.TestCase):
    def test_list_ui_presets_returns_expected_ids(self) -> None:
        presets = list_ui_preset_definitions()

        self.assertEqual(
            [preset["id"] for preset in presets],
            ["hud-platformer", "main-menu", "pause-menu", "game-over", "dialog-box"],
        )

    def test_get_ui_preset_definition_returns_copy(self) -> None:
        definition = get_ui_preset_definition("main-menu")
        self.assertIsNotNone(definition)

        assert definition is not None
        definition["name"] = "Mutated"
        second = get_ui_preset_definition("main-menu")

        self.assertEqual(second["name"], "Main Menu")

    def test_unknown_preset_returns_none(self) -> None:
        self.assertIsNone(get_ui_preset_definition("missing-preset"))

    def test_pure_module_does_not_import_pyray_or_editor_ui(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json, sys; "
                    f"sys.path.insert(0, r'{ROOT.as_posix()}'); "
                    "import engine.ui.presets as presets; "
                    "print(json.dumps({"
                    "'has_pyray': 'pyray' in sys.modules, "
                    "'has_editor_ui': 'engine.editor.ui' in sys.modules, "
                    "'count': len(presets.list_ui_preset_definitions())"
                    "}))"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertFalse(payload["has_pyray"])
        self.assertFalse(payload["has_editor_ui"])
        self.assertEqual(payload["count"], 5)


if __name__ == "__main__":
    unittest.main()
