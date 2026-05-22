"""Tests for export spec generation (packed vs directory)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.export.build_context import BuildContext
from engine.export.models import ExportPreset


class TestLinuxSpecGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        (self.staging / "game.pak").write_text("fake_pak", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _make_preset(self, bundle_mode="packed"):
        return ExportPreset(
            name="Linux Test",
            platform="linux",
            output_path="dist/export/linux/Test",
            entry_scene="levels/test.json",
            display_name="LinuxApp",
            bundle_mode=bundle_mode,
        )

    def test_spec_packed_includes_game_pak(self):
        from engine.export.linux_exporter import LinuxExporter
        preset = self._make_preset("packed")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = LinuxExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("game.pak", content)
        self.assertNotIn("'content')", content)
        # Must NOT include full engine directory as a datas tuple
        self.assertNotIn("'engine')", content)

    def test_spec_directory_includes_content(self):
        from engine.export.linux_exporter import LinuxExporter
        preset = self._make_preset("directory")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = LinuxExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("'content')", content)
        self.assertNotIn("game.pak", content)
        self.assertNotIn("'engine')", content)


class TestMacOSSpecGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        (self.staging / "game.pak").write_text("fake_pak", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _make_preset(self, bundle_mode="packed"):
        return ExportPreset(
            name="MacOS Test",
            platform="macos",
            output_path="dist/export/macos/Test",
            entry_scene="levels/test.json",
            display_name="MacApp",
            bundle_mode=bundle_mode,
        )

    def test_spec_packed_includes_game_pak(self):
        from engine.export.macos_exporter import MacOSExporter
        preset = self._make_preset("packed")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = MacOSExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("game.pak", content)
        self.assertNotIn("'content')", content)
        self.assertNotIn("'engine')", content)

    def test_spec_directory_includes_content(self):
        from engine.export.macos_exporter import MacOSExporter
        preset = self._make_preset("directory")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = MacOSExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("'content')", content)
        self.assertNotIn("game.pak", content)
        self.assertNotIn("'engine')", content)


class TestWindowsSpecGeneration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        (self.staging / "game.pak").write_text("fake_pak", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _make_preset(self, bundle_mode="packed"):
        return ExportPreset(
            name="Win Test",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
            display_name="WinApp",
            bundle_mode=bundle_mode,
        )

    def test_spec_packed_includes_game_pak_not_content(self):
        from engine.export.windows_exporter import WindowsExporter
        preset = self._make_preset("packed")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = WindowsExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("game.pak", content)
        self.assertNotIn("'content')", content)
        self.assertNotIn("'engine')", content)

    def test_spec_directory_includes_content_not_pak(self):
        from engine.export.windows_exporter import WindowsExporter
        preset = self._make_preset("directory")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = WindowsExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("'content')", content)
        self.assertNotIn("game.pak", content)
        self.assertNotIn("'engine')", content)

    def test_spec_default_bundle_mode_is_packed(self):
        from engine.export.windows_exporter import WindowsExporter
        preset = ExportPreset(
            name="Win Default",
            platform="windows",
            output_path="dist/export/windows/Default",
            entry_scene="levels/test.json",
            display_name="WinDefault",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging
        exporter = WindowsExporter()
        spec_path = exporter._write_export_spec(ctx, self.staging)
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("game.pak", content)


class TestPyInstallerArgsWindows(unittest.TestCase):
    """Verify PyInstaller args for Windows exporter do NOT include --specpath."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        (self.staging / "game.pak").write_text("fake_pak", encoding="utf-8")
        (self.tmp / "levels").mkdir(parents=True, exist_ok=True)
        (self.tmp / "levels" / "test.json").write_text(json.dumps({"entities": []}), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_pyinstaller_args_no_specpath(self):
        from unittest.mock import MagicMock, patch

        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset
        from engine.export.windows_exporter import WindowsExporter

        preset = ExportPreset(
            name="Win Args Test",
            platform="windows",
            output_path="dist/export/windows/ArgsTest",
            entry_scene="levels/test.json",
            display_name="WinArgs",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        exporter = WindowsExporter()

        with patch("subprocess.run") as mock_run, \
             patch.object(exporter, "_run_smoke_test", return_value=True), \
             patch("shutil.which", return_value="/fake/pyinstaller"), \
             patch("engine.export.windows_exporter.build_content_pack", return_value=(MagicMock(), MagicMock())):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            exporter.export(ctx)

            if mock_run.called:
                args = mock_run.call_args[0][0]
                self.assertNotIn("--specpath", args)


class TestPyInstallerArgsLinux(unittest.TestCase):
    """Verify PyInstaller args for Linux exporter do NOT include --specpath."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        (self.staging / "game.pak").write_text("fake_pak", encoding="utf-8")
        (self.tmp / "levels").mkdir(parents=True, exist_ok=True)
        (self.tmp / "levels" / "test.json").write_text(json.dumps({"entities": []}), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_pyinstaller_args_no_specpath(self):
        from unittest.mock import MagicMock, patch

        from engine.export.build_context import BuildContext
        from engine.export.linux_exporter import LinuxExporter
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="Linux Args Test",
            platform="linux",
            output_path="dist/export/linux/ArgsTest",
            entry_scene="levels/test.json",
            display_name="LinuxArgs",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        exporter = LinuxExporter()

        with patch("subprocess.run") as mock_run, \
             patch.object(exporter, "_run_smoke_test", return_value=True), \
             patch("shutil.which", return_value="/fake/pyinstaller"), \
             patch("engine.export.linux_exporter.build_content_pack", return_value=(MagicMock(), MagicMock())):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            exporter.export(ctx)

            if mock_run.called:
                args = mock_run.call_args[0][0]
                self.assertNotIn("--specpath", args)


class TestPyInstallerArgsMacOS(unittest.TestCase):
    """Verify PyInstaller args for macOS exporter do NOT include --specpath or --windowed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        (self.staging / "game.pak").write_text("fake_pak", encoding="utf-8")
        (self.tmp / "levels").mkdir(parents=True, exist_ok=True)
        (self.tmp / "levels" / "test.json").write_text(json.dumps({"entities": []}), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_pyinstaller_args_no_specpath(self):
        from unittest.mock import MagicMock, patch

        from engine.export.build_context import BuildContext
        from engine.export.macos_exporter import MacOSExporter
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="Mac Args Test",
            platform="macos",
            output_path="dist/export/macos/ArgsTest",
            entry_scene="levels/test.json",
            display_name="MacArgs",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        exporter = MacOSExporter()

        with patch("engine.export.macos_exporter.IS_MACOS", True), \
             patch("subprocess.run") as mock_run, \
             patch.object(exporter, "_run_smoke_test", return_value=True), \
             patch("shutil.which", return_value="/fake/pyinstaller"), \
             patch("engine.export.macos_exporter.build_content_pack", return_value=(MagicMock(), MagicMock())):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            exporter.export(ctx)

            if mock_run.called:
                args = mock_run.call_args[0][0]
                self.assertNotIn("--specpath", args)

    def test_pyinstaller_args_no_windowed(self):
        from unittest.mock import MagicMock, patch

        from engine.export.build_context import BuildContext
        from engine.export.macos_exporter import MacOSExporter
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="Mac Args Test 2",
            platform="macos",
            output_path="dist/export/macos/ArgsTest2",
            entry_scene="levels/test.json",
            display_name="MacArgs2",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        exporter = MacOSExporter()

        with patch("engine.export.macos_exporter.IS_MACOS", True), \
             patch("subprocess.run") as mock_run, \
             patch.object(exporter, "_run_smoke_test", return_value=True), \
             patch("shutil.which", return_value="/fake/pyinstaller"), \
             patch("engine.export.macos_exporter.build_content_pack", return_value=(MagicMock(), MagicMock())):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            exporter.export(ctx)

            if mock_run.called:
                args = mock_run.call_args[0][0]
                self.assertNotIn("--windowed", args)


if __name__ == "__main__":
    unittest.main()
