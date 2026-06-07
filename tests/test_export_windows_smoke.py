"""Smoke tests for Windows exporter and exported runtime purity."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from engine.export.build_context import BuildContext
from engine.export.exporter_registry import ExporterRegistry
from engine.export.models import ExportPreset
from engine.export.preset_schema import validate_preset
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

    def _write_spec_for_preset(self, preset: ExportPreset) -> str:
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)

        exporter = WindowsExporter()
        spec_path = exporter._write_export_spec(ctx, ctx.staging_dir)

        self.assertTrue(spec_path.exists())
        return spec_path.read_text(encoding="utf-8")

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

    def test_validate_environment_prefers_active_python_module(self):
        exporter = WindowsExporter()

        with patch("engine.export.toolchain.importlib.util.find_spec", return_value=object()), patch(
            "engine.export.toolchain.shutil.which",
            return_value=None,
        ):
            result = exporter.validate_environment()

        self.assertTrue(result["pyinstaller_available"])
        self.assertTrue(result["pyinstaller_module_available"])
        self.assertEqual(result["pyinstaller_resolution"], "python_module")
        self.assertEqual(result["pyinstaller_command"], [sys.executable, "-m", "PyInstaller"])

    def test_validate_environment_uses_path_when_module_missing(self):
        exporter = WindowsExporter()

        with patch("engine.export.toolchain.importlib.util.find_spec", return_value=None), patch(
            "engine.export.toolchain.shutil.which",
            side_effect=["C:/fake/pyinstaller.exe", None],
        ):
            result = exporter.validate_environment()

        self.assertTrue(result["pyinstaller_available"])
        self.assertFalse(result["pyinstaller_module_available"])
        self.assertEqual(result["pyinstaller_resolution"], "path_executable")
        self.assertEqual(result["pyinstaller_command"], ["C:/fake/pyinstaller.exe"])

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
        content = self._write_spec_for_preset(preset)
        self.assertIn("Analysis", content)
        self.assertIn("exported_game.py", content)
        self.assertIn("EXE", content)

    def test_spec_generation_release_uses_windowed_no_console(self):
        content = self._write_spec_for_preset(ExportPreset(
            name="Win Release",
            platform="windows",
            mode="release",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        ))

        self.assertIn("console=False", content)

    def test_spec_generation_debug_uses_console(self):
        content = self._write_spec_for_preset(ExportPreset(
            name="Win Debug",
            platform="windows",
            mode="debug",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        ))

        self.assertIn("console=True", content)

    def test_spec_generation_debug_tools_use_console(self):
        content = self._write_spec_for_preset(ExportPreset(
            name="Win Debug Tools",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
            include_debug_tools=True,
        ))

        self.assertIn("console=True", content)

    def test_spec_generation_extra_console_uses_console(self):
        content = self._write_spec_for_preset(ExportPreset(
            name="Win Console",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
            extra={"console": True},
        ))

        self.assertIn("console=True", content)

    def test_spec_generation_includes_raylib_runtime_hooks(self):
        content = self._write_spec_for_preset(ExportPreset(
            name="Win Raylib",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        ))

        self.assertIn("'pyray'", content)
        self.assertIn("'raylib'", content)
        self.assertIn("collect_submodules('raylib')", content)
        self.assertIn("collect_dynamic_libs('raylib')", content)
        self.assertIn("pyinstaller_hooks", content)
        self.assertLess(
            content.index("sysconfig.get_paths().get('purelib')"),
            content.index(f"r'{self.tmp.as_posix()}'"),
        )

    def test_preset_validation_accepts_console_extra_field(self):
        preset = ExportPreset.from_dict({
            "name": "Win Console",
            "platform": "windows",
            "output_path": "dist/export/windows/Test",
            "entry_scene": "levels/test.json",
            "console": True,
        })

        errors = validate_preset(preset)

        self.assertFalse([error for error in errors if error.code == "UNKNOWN_PRESET_FIELD"])

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

    def test_export_uses_python_module_pyinstaller_command(self):
        preset = ExportPreset(
            name="Win Module Test",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)
        exporter = WindowsExporter()

        with patch("subprocess.run") as mock_run, patch.object(
            exporter, "_run_smoke_test", return_value=True
        ), patch(
            "engine.export.windows_exporter.resolve_pyinstaller",
            return_value={
                "pyinstaller_available": True,
                "pyinstaller_path": "",
                "pyinstaller_module_available": True,
                "pyinstaller_resolution": "python_module",
                "pyinstaller_command": [sys.executable, "-m", "PyInstaller"],
                "python_executable": sys.executable,
            },
        ), patch(
            "engine.export.windows_exporter.build_content_pack",
            return_value=(MagicMock(assets=[], scenes=[], scripts=[]), MagicMock()),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            exporter.export(ctx)

        args = mock_run.call_args_list[0][0][0]
        self.assertEqual(args[:3], [sys.executable, "-m", "PyInstaller"])
        self.assertEqual(mock_run.call_args_list[0].kwargs["cwd"], str(ctx.staging_dir))


class TestExportedGameWindowed(unittest.TestCase):
    def test_windowed_pyray_returns_clear_error_when_window_not_ready(self):
        from engine.runtime.exported_game import _run_windowed_pyray

        fake_pyray = SimpleNamespace(
            BLACK=object(),
            MOUSE_BUTTON_LEFT=0,
            init_window=MagicMock(),
            is_window_ready=MagicMock(return_value=False),
            close_window=MagicMock(),
        )
        fake_runtime = MagicMock()
        fake_runtime.load_scene.return_value = True
        fake_loader = MagicMock()
        fake_loader.get_entry_scene.return_value = "levels/test.json"
        config = SimpleNamespace(
            base_path=str(Path(".")),
            entry_scene="levels/test.json",
            project_name="Test Game",
            version="0.1.0",
            window={"width": 320, "height": 180},
        )

        with patch.dict(sys.modules, {"pyray": fake_pyray}), patch(
            "engine.runtime.content_loader.ContentLoader",
            return_value=fake_loader,
        ), patch(
            "engine.runtime.exported_game._create_shared_runtime",
            return_value=fake_runtime,
        ), patch(
            "engine.levels.component_registry.create_default_registry",
            return_value=MagicMock(),
        ):
            result = _run_windowed_pyray(config)

        self.assertEqual(result, 2)
        fake_pyray.init_window.assert_called_once_with(320, 180, "Test Game v0.1.0")
        fake_pyray.is_window_ready.assert_called_once_with()
        fake_pyray.close_window.assert_called_once_with()

    def test_windowed_pyray_updates_and_renders_once_per_frame(self):
        from engine.runtime.exported_game import _run_windowed_pyray

        fake_pyray = SimpleNamespace(
            BLACK=object(),
            WHITE=object(),
            GRAY=object(),
            DARKGRAY=object(),
            SKYBLUE=object(),
            MOUSE_BUTTON_LEFT=0,
            init_window=MagicMock(),
            is_window_ready=MagicMock(return_value=True),
            close_window=MagicMock(),
            set_target_fps=MagicMock(),
            window_should_close=MagicMock(side_effect=[False, True]),
            get_mouse_position=MagicMock(return_value=SimpleNamespace(x=12.0, y=34.0)),
            is_mouse_button_down=MagicMock(return_value=True),
            is_mouse_button_pressed=MagicMock(return_value=False),
            is_mouse_button_released=MagicMock(return_value=True),
            begin_drawing=MagicMock(),
            clear_background=MagicMock(),
            measure_text=MagicMock(return_value=40),
            draw_text=MagicMock(),
            draw_rectangle=MagicMock(),
            draw_rectangle_lines=MagicMock(),
            end_drawing=MagicMock(),
        )
        fake_runtime = MagicMock()
        fake_runtime.load_scene.return_value = True
        fake_runtime.world = object()
        fake_loader = MagicMock()
        fake_loader.get_entry_scene.return_value = "levels/test.json"
        config = SimpleNamespace(
            base_path=str(Path(".")),
            entry_scene="levels/test.json",
            project_name="Test Game",
            version="0.1.0",
            window={"width": 320, "height": 180},
        )

        with patch.dict(sys.modules, {"pyray": fake_pyray}), patch(
            "engine.runtime.content_loader.ContentLoader",
            return_value=fake_loader,
        ), patch(
            "engine.runtime.exported_game._create_shared_runtime",
            return_value=fake_runtime,
        ), patch(
            "engine.levels.component_registry.create_default_registry",
            return_value=MagicMock(),
        ):
            result = _run_windowed_pyray(config)

        self.assertEqual(result, 0)
        fake_runtime.run_frame.assert_called_once_with(
            1.0 / 60.0,
            pointer_state={
                "x": 12.0,
                "y": 34.0,
                "down": True,
                "pressed": False,
                "released": True,
            },
        )
        fake_runtime.render.assert_called_once_with((320.0, 180.0))
        fake_runtime.update_ui.assert_not_called()
        fake_runtime.render_ui.assert_not_called()


if __name__ == "__main__":
    unittest.main()
