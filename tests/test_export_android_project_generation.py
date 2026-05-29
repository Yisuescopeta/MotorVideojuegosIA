"""Tests for Android project generation."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAndroidProjectGeneration(unittest.TestCase):
    """Test that Android project template can be processed and validated."""

    def setUp(self):
        self.template_dir = Path(__file__).parent.parent / "platforms" / "android" / "template"

    def test_template_structure_exists(self):
        required = [
            "settings.gradle",
            "build.gradle",
            "gradle.properties",
            "gradlew",
            "gradlew.bat",
            "app/build.gradle",
            "app/src/main/AndroidManifest.xml",
            "app/src/main/java/com/motorvideojuegos/MainActivity.kt",
            "app/src/main/python/motor_android_runtime.py",
            "app/src/main/res/drawable/ic_launcher.xml",
            "app/src/main/res/layout/activity_main.xml",
            "app/proguard-rules.pro",
            "gradle/wrapper/gradle-wrapper.properties",
            "gradle/wrapper/gradle-wrapper.jar",
        ]
        for rel_path in required:
            full = self.template_dir / rel_path
            self.assertTrue(full.exists(), f"Missing template file: {rel_path}")

    def test_android_manifest_has_placeholders(self):
        manifest_path = self.template_dir / "app" / "src" / "main" / "AndroidManifest.xml"
        if not manifest_path.exists():
            self.skipTest("AndroidManifest.xml not found")
        content = manifest_path.read_text(encoding="utf-8")
        self.assertIn("{{DISPLAY_NAME}}", content)
        self.assertIn("{{ORIENTATION}}", content)
        self.assertIn("@drawable/ic_launcher", content)

    def test_build_gradle_has_placeholders(self):
        gradle_path = self.template_dir / "app" / "build.gradle"
        if not gradle_path.exists():
            self.skipTest("app/build.gradle not found")
        content = gradle_path.read_text(encoding="utf-8")
        self.assertIn("{{APPLICATION_ID}}", content)
        self.assertIn("{{MIN_SDK}}", content)
        self.assertIn("{{TARGET_SDK}}", content)
        self.assertIn("{{VERSION_NAME}}", content)
        self.assertIn("{{VERSION_CODE}}", content)

    def test_settings_gradle_has_placeholders(self):
        settings_path = self.template_dir / "settings.gradle"
        if not settings_path.exists():
            self.skipTest("settings.gradle not found")
        content = settings_path.read_text(encoding="utf-8")
        self.assertIn("{{DISPLAY_NAME}}", content)

    def test_main_activity_kotlin_has_placeholders(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        if not kt_path.exists():
            self.skipTest("MainActivity.kt not found")
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("{{APPLICATION_ID}}", content)
        self.assertIn("MotorGameView", content)
        self.assertIn("SurfaceView", content)
        self.assertIn("MobileControls2D", content)
        self.assertIn("load_scene_flow", content)
        self.assertIn("controlCaptures", content)
        self.assertIn("ScriptBehaviourBridge", content)

    def test_android_template_has_chaquopy_placeholders(self):
        root_gradle = (self.template_dir / "build.gradle").read_text(encoding="utf-8")
        app_gradle = (self.template_dir / "app" / "build.gradle").read_text(encoding="utf-8")
        self.assertIn("{{CHAQUOPY_ROOT_PLUGIN}}", root_gradle)
        self.assertIn("{{CHAQUOPY_APP_PLUGIN}}", app_gradle)

    def test_android_template_uses_native_activity_theme(self):
        manifest_path = self.template_dir / "app" / "src" / "main" / "AndroidManifest.xml"
        themes_path = self.template_dir / "app" / "src" / "main" / "res" / "values" / "themes.xml"
        manifest = manifest_path.read_text(encoding="utf-8")
        themes = themes_path.read_text(encoding="utf-8")
        self.assertIn("@style/Theme.MotorGame", manifest)
        self.assertIn("@android:style/Theme.NoTitleBar.Fullscreen", themes)
        self.assertNotIn("Theme.AppCompat", manifest + themes)

    def test_gradle_wrapper_properties(self):
        wrapper_path = self.template_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
        if not wrapper_path.exists():
            self.skipTest("gradle-wrapper.properties not found")
        content = wrapper_path.read_text(encoding="utf-8")
        self.assertIn("distributionUrl", content)

    def test_android_exporter_prefers_generated_gradle_wrapper(self):
        import tempfile

        from engine.export.android_exporter import AndroidExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            wrapper_name = "gradlew.bat" if sys.platform.startswith("win") else "gradlew"
            (project_dir / wrapper_name).write_text("", encoding="utf-8")
            wrapper_dir = project_dir / "gradle" / "wrapper"
            wrapper_dir.mkdir(parents=True)
            (wrapper_dir / "gradle-wrapper.properties").write_text("distributionUrl=x", encoding="utf-8")
            (wrapper_dir / "gradle-wrapper.jar").write_bytes(b"jar")

            command = AndroidExporter()._resolve_gradle_command(project_dir)

        self.assertEqual(command, [str(project_dir / wrapper_name)])

    def test_ios_template_structure_exists(self):
        ios_dir = Path(__file__).parent.parent / "platforms" / "ios" / "template"
        required = [
            "Info.plist",
            "LaunchScreen.storyboard",
            "xcode_project.pbxproj",
        ]
        for rel_path in required:
            full = ios_dir / rel_path
            self.assertTrue(full.exists(), f"Missing iOS template file: {rel_path}")

    def test_ios_info_plist_has_placeholders(self):
        plist_path = Path(__file__).parent.parent / "platforms" / "ios" / "template" / "Info.plist"
        if not plist_path.exists():
            self.skipTest("Info.plist not found")
        content = plist_path.read_text(encoding="utf-8")
        self.assertIn("{{DISPLAY_NAME}}", content)
        self.assertIn("{{APPLICATION_ID}}", content)

    def test_placeholder_replacement(self):
        template = "Hello {{NAME}}, your app {{APPLICATION_ID}} is ready."
        replacements = {"{{NAME}}": "World", "{{APPLICATION_ID}}": "com.example.app"}
        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        self.assertEqual(result, "Hello World, your app com.example.app is ready.")
        self.assertNotIn("{{", result)


class TestAndroidExporterImport(unittest.TestCase):
    """Test that Android exporter can be imported."""

    def test_import_android_exporter(self):
        try:
            from engine.export.android_exporter import AndroidExporter  # noqa: F401
        except ImportError as e:
            self.skipTest(f"Android exporter not yet implemented: {e}")

    def test_android_exporter_platform(self):
        try:
            from engine.export.android_exporter import AndroidExporter
            self.assertEqual(AndroidExporter.platform, "android")
        except ImportError:
            self.skipTest("Android exporter not yet implemented")


class TestAndroidRuntimeV1Validation(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp.name)
        (self.project_root / "levels").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _ctx(self, *, android_python_runtime=False, min_sdk=23):
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="Android Debug",
            platform="android",
            mode="debug",
            output_path="dist/export/android/Test.apk",
            entry_scene="levels/test.json",
            display_name="Test",
            application_id="com.example.test",
            min_sdk=min_sdk,
            extra={"android_python_runtime": android_python_runtime} if android_python_runtime else {},
        )
        return BuildContext(preset, self.project_root)

    def _write_scene(self, name, entities):
        path = self.project_root / "levels" / name
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "name": name,
                    "entities": entities,
                    "rules": [],
                    "feature_metadata": {},
                }
            ),
            encoding="utf-8",
        )
        return f"levels/{name}"

    def test_validation_blocks_python_scripts(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene("test.json", [])
        ctx = self._ctx()
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], ["scripts/player.py"])

        self.assertFalse(ok)
        self.assertTrue(any("ANDROID_RUNTIME_UNSUPPORTED_SCRIPT" in err for err in ctx.errors))

    def test_validation_accepts_python_scripts_when_android_python_runtime_enabled(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene(
            "test.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {},
                        "InputMap": {},
                        "PlayerController2D": {},
                        "ScriptBehaviour": {"module_path": "scripts/player.py"},
                    },
                },
                {
                    "name": "Coin",
                    "components": {
                        "Transform": {},
                        "Collider": {"is_trigger": True},
                        "Collectible2D": {"points": 1},
                    },
                },
                {
                    "name": "MobileControlsOverlay",
                    "components": {"MobileControls2D": {"target_entity": "Player"}},
                },
            ],
        )
        ctx = self._ctx(android_python_runtime=True, min_sdk=24)
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], ["scripts/player.py"])

        self.assertTrue(ok, ctx.errors)

    def test_validation_blocks_android_python_runtime_below_min_sdk_24(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene("test.json", [])
        ctx = self._ctx(android_python_runtime=True, min_sdk=23)
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], ["scripts/player.py"])

        self.assertFalse(ok)
        self.assertTrue(any("ANDROID_PYTHON_RUNTIME_MIN_SDK" in err for err in ctx.errors))

    def test_android_python_runtime_copies_reachable_scripts(self):
        from engine.export.android_exporter import AndroidExporter

        script = self.project_root / "scripts" / "player.py"
        script.parent.mkdir()
        script.write_text("VALUE = 1\n", encoding="utf-8")
        project_dir = self.project_root / "staging" / "android_project"
        ctx = self._ctx(android_python_runtime=True, min_sdk=24)

        AndroidExporter()._copy_android_python_scripts(ctx, project_dir, ["scripts/player.py"])

        copied = project_dir / "app" / "src" / "main" / "python" / "player.py"
        self.assertEqual(copied.read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_validation_blocks_missing_mobile_controls_for_player(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene(
            "test.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {},
                        "InputMap": {},
                        "PlayerController2D": {},
                    },
                }
            ],
        )
        ctx = self._ctx()
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], [])

        self.assertFalse(ok)
        self.assertTrue(any("ANDROID_RUNTIME_MOBILE_CONTROLS_MISSING" in err for err in ctx.errors))

    def test_validation_accepts_supported_playable_scene_with_mobile_controls(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene(
            "test.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {},
                        "Collider": {},
                        "RigidBody": {},
                        "InputMap": {},
                        "PlayerController2D": {},
                        "Animator": {},
                    },
                },
                {
                    "name": "MobileControlsOverlay",
                    "components": {
                        "MobileControls2D": {"target_entity": "Player"},
                    },
                },
            ],
        )
        ctx = self._ctx()
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], [])

        self.assertTrue(ok, ctx.errors)

    def test_validation_blocks_unsupported_component(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene(
            "test.json",
            [{"name": "Audio", "components": {"AudioSource": {}}}],
        )
        ctx = self._ctx()
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], [])

        self.assertFalse(ok)
        self.assertTrue(any("ANDROID_RUNTIME_UNSUPPORTED_COMPONENT" in err for err in ctx.errors))


class TestIOSExporterImport(unittest.TestCase):
    """Test that iOS exporter can be imported."""

    def test_import_ios_exporter(self):
        try:
            from engine.export.ios_exporter import IOSExporter  # noqa: F401
        except ImportError as e:
            self.skipTest(f"iOS exporter not yet implemented: {e}")

    def test_ios_exporter_platform(self):
        try:
            from engine.export.ios_exporter import IOSExporter
            self.assertEqual(IOSExporter.platform, "ios")
        except ImportError:
            self.skipTest("iOS exporter not yet implemented")


class TestLinuxExporterImport(unittest.TestCase):
    """Test that Linux exporter can be imported."""

    def test_import_linux_exporter(self):
        try:
            from engine.export.linux_exporter import LinuxExporter  # noqa: F401
        except ImportError as e:
            self.skipTest(f"Linux exporter not yet implemented: {e}")

    def test_linux_exporter_platform(self):
        try:
            from engine.export.linux_exporter import LinuxExporter
            self.assertEqual(LinuxExporter.platform, "linux")
        except ImportError:
            self.skipTest("Linux exporter not yet implemented")


class TestMacOSExporterImport(unittest.TestCase):
    """Test that macOS exporter can be imported."""

    def test_import_macos_exporter(self):
        try:
            from engine.export.macos_exporter import MacOSExporter  # noqa: F401
        except ImportError as e:
            self.skipTest(f"macOS exporter not yet implemented: {e}")

    def test_macos_exporter_platform(self):
        try:
            from engine.export.macos_exporter import MacOSExporter
            self.assertEqual(MacOSExporter.platform, "macos")
        except ImportError:
            self.skipTest("macOS exporter not yet implemented")


if __name__ == "__main__":
    unittest.main()
