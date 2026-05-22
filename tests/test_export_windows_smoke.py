"""Smoke tests for Windows exporter and exported runtime purity."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from engine.export.build_context import BuildContext
from engine.export.exporter_registry import ExporterRegistry
from engine.export.models import ExportPreset
from engine.export.windows_exporter import WindowsExporter

ExporterRegistry.register(WindowsExporter())


class TestExportedRuntimePurity(unittest.TestCase):
    """Importing engine.runtime.* must not pull in editor or inspector.

    Uses diff-based sys.modules snapshot: we snapshot modules before import,
    import the target module, then assert no editor/inspector modules appear
    in the *newly added* modules.  This avoids order-dependent failures when
    a previous test already loaded engine.editor.
    """

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _snapshot() -> frozenset[str]:
        return frozenset(sys.modules.keys())

    @staticmethod
    def _added_editor_or_inspector(before: frozenset[str]) -> list[str]:
        added = set(sys.modules.keys()) - before
        return sorted(
            m
            for m in added
            if m == "engine.editor"
            or m == "engine.inspector"
            or m.startswith("engine.editor.")
            or m.startswith("engine.inspector.")
        )

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------
    def test_import_exported_game_no_inspector(self):
        before = self._snapshot()
        from engine.runtime.exported_game import main
        self.assertIsNotNone(main)
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_import_exported_game_module_level_no_bad_imports(self):
        before = self._snapshot()
        import engine.runtime.exported_game  # noqa: F401
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_bootstrap_module_no_inspector(self):
        before = self._snapshot()
        from engine.runtime.bootstrap import bootstrap_config
        self.assertIsNotNone(bootstrap_config)
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_runtime_config_no_inspector(self):
        before = self._snapshot()
        from engine.runtime.runtime_config import RuntimeConfig
        self.assertIsNotNone(RuntimeConfig)
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_content_loader_no_inspector(self):
        before = self._snapshot()
        from engine.runtime.content_loader import ContentLoader
        self.assertIsNotNone(ContentLoader)
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_import_ui_system_no_editor(self):
        before = self._snapshot()
        import engine.systems.ui_system  # noqa: F401
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_import_script_behaviour_system_no_editor(self):
        before = self._snapshot()
        import engine.systems.script_behaviour_system  # noqa: F401
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_import_render_system_no_editor(self):
        before = self._snapshot()
        import engine.systems.render_system  # noqa: F401
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_import_animation_system_no_editor(self):
        before = self._snapshot()
        import engine.systems.animation_system  # noqa: F401
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")

    def test_import_audio_system_no_editor(self):
        before = self._snapshot()
        import engine.systems.audio_system  # noqa: F401
        bad = self._added_editor_or_inspector(before)
        self.assertFalse(bad, f"Added editor/inspector modules: {bad}")


class TestWindowsExporter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "levels").mkdir(parents=True, exist_ok=True)
        (self.tmp / "levels" / "test.json").write_text(
            json.dumps({"entities": []}), encoding="utf-8",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_registered_in_registry(self):
        exporter = ExporterRegistry.get("windows")
        self.assertIsNotNone(exporter)
        self.assertIsInstance(exporter, WindowsExporter)

    def test_validate_environment(self):
        exporter = WindowsExporter()
        result = exporter.validate_environment()
        self.assertEqual(result["platform"], "windows")
        self.assertIn("pyinstaller_available", result)
        self.assertIn("python", result)

    def test_export_without_pyinstaller_fails_cleanly(self):
        preset = ExportPreset(
            name="Win Test",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        )
        ctx = BuildContext(preset, str(self.tmp))

        exporter = WindowsExporter()
        env = exporter.validate_environment()
        if env["pyinstaller_available"]:
            self.skipTest("PyInstaller available — skipping TOOLCHAIN_UNAVAILABLE test")

        success = exporter.export(ctx)
        self.assertFalse(success)
        self.assertTrue(ctx.has_errors)
        self.assertTrue(
            any("TOOLCHAIN_UNAVAILABLE" in e
                or "PyInstaller" in e
                for e in ctx.errors)
        )

    def test_spec_generation(self):
        preset = ExportPreset(
            name="Win Test",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)

        exporter = WindowsExporter()
        spec_path = exporter._write_export_spec(ctx, ctx.staging_dir)

        self.assertTrue(spec_path.exists())
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("Analysis", content)
        self.assertIn("exported_game.py", content)
        self.assertIn("EXE", content)

    def test_runtime_config_generation(self):
        preset = ExportPreset(
            name="Win Test",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
            display_name="My App",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)

        exporter = WindowsExporter()
        exporter._write_runtime_config(ctx, ctx.staging_dir)

        config_path = ctx.staging_dir / "runtime_config.json"
        self.assertTrue(config_path.exists())
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["entry_scene"], "levels/test.json")


if __name__ == "__main__":
    unittest.main()
