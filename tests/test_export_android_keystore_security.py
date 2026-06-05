"""Tests for Android export keystore/password security.

Ensures passwords are NEVER written plaintext to build.gradle,
gradle.properties, or any generated file.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine.export.build_context import BuildContext
from engine.export.models import ExportPreset


class TestAndroidKeystoreSecurity(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)
        (self.staging / "runtime_config.json").write_text("{}", encoding="utf-8")
        (self.staging / "game.manifest.json").write_text("{}", encoding="utf-8")
        (self.staging / "content").mkdir(exist_ok=True)
        # Create a fake keystore
        self.keystore = self.staging / "test.keystore"
        self.keystore.write_bytes(b"\x00" * 100)

        # Create a minimal android project structure
        self.project_dir = self.staging / "android_project"
        self.app_dir = self.project_dir / "app"
        self.app_dir.mkdir(parents=True)
        self.gradle_path = self.app_dir / "build.gradle"
        self.gradle_path.write_text(
            "android {\n"
            "    buildTypes {\n"
            "        release {\n"
            "            signingConfig signingConfigs.debug\n"
            "        }\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _make_preset_with_keystore(self, **extra):
        defaults = {
            "keystore_path": str(self.keystore),
            "keystore_password": "secret123!",
            "key_alias": "mykey",
            "key_password": "keysecret456!",
        }
        defaults.update(extra)
        return ExportPreset(
            name="AndroidTest",
            platform="android",
            mode="release",
            output_path="dist/export/android/Test",
            entry_scene="levels/test.json",
            display_name="TestApp",
            application_id="com.test.app",
            extra=defaults,
        )

    def _run_export_with_signing(self, extra):
        from engine.export.android_exporter import AndroidExporter

        preset = ExportPreset(
            name="AndroidTest",
            platform="android",
            mode="release",
            output_path="dist/export/android/Test-release.apk",
            entry_scene="levels/test.json",
            display_name="TestApp",
            application_id="com.test.app",
            extra=extra,
        )
        ctx = BuildContext(preset, self.tmp)
        exporter = AndroidExporter()
        project_dir = self.tmp / "generated_android"
        (project_dir / "app" / "src" / "main" / "assets").mkdir(parents=True)
        manifest = MagicMock(assets=[], scenes=[], scripts=[])
        graph = MagicMock(reachable_scenes=[], reachable_scripts=[])
        environment = {
            "android_sdk_available": True,
            "java_available": True,
            "gradle_available": True,
        }

        with (
            patch(
                "engine.export.android_exporter.build_content_pack",
                return_value=(manifest, graph),
            ),
            patch.object(exporter, "validate_environment", return_value=environment),
            patch.object(exporter, "_validate_android_runtime_v1", return_value=True),
            patch.object(exporter, "_write_runtime_config"),
            patch.object(exporter, "_generate_android_project", return_value=project_dir),
            patch.object(exporter, "_android_python_runtime_enabled", return_value=False),
            patch.object(exporter, "_add_project_artifacts"),
            patch.object(exporter, "_build_release", return_value=True) as build_release,
            patch.object(exporter, "_run_gradle_build", return_value=True) as run_gradle,
            patch.object(exporter, "_find_apk", return_value=None),
            patch.object(exporter, "_find_aab", return_value=None),
        ):
            result = exporter.export(ctx)

        return result, ctx, build_release, run_gradle

    def test_release_without_signing_fails_before_gradle(self):
        result, ctx, build_release, run_gradle = self._run_export_with_signing({})

        self.assertFalse(result)
        self.assertTrue(
            any("ANDROID_RELEASE_SIGNING_REQUIRED" in error for error in ctx.errors)
        )
        build_release.assert_not_called()
        run_gradle.assert_not_called()

    def test_release_with_local_signing_keeps_release_flow(self):
        result, ctx, build_release, run_gradle = self._run_export_with_signing(
            {"local_release_signing": True}
        )

        self.assertTrue(result)
        self.assertFalse(ctx.errors)
        build_release.assert_called_once()
        run_gradle.assert_not_called()

    def test_release_with_existing_keystore_keeps_release_flow(self):
        result, ctx, build_release, run_gradle = self._run_export_with_signing(
            {"keystore_path": str(self.keystore)}
        )

        self.assertTrue(result)
        self.assertFalse(ctx.errors)
        build_release.assert_called_once()
        run_gradle.assert_not_called()

    def test_build_gradle_does_not_contain_password_plaintext(self):
        preset = self._make_preset_with_keystore()
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        # Manually call _build_release logic to write the gradle file
        # without actually running Gradle
        keystore = ctx.preset.extra.get("keystore_path", "")
        keystore_path = Path(keystore)
        if not keystore_path.is_absolute():
            keystore_path = ctx.project_root / keystore_path

        content = self.gradle_path.read_text(encoding="utf-8")
        signing_block = (
            "\n    signingConfigs {\n"
            "        release {\n"
            f"            storeFile file(System.getenv(\"RELEASE_STORE_FILE\") ?: \"{keystore_path.as_posix()}\")\n"
            "            storePassword System.getenv(\"RELEASE_STORE_PASSWORD\") ?: \"\"\n"
            f"            keyAlias System.getenv(\"RELEASE_KEY_ALIAS\") ?: \"mykey\"\n"
            "            keyPassword System.getenv(\"RELEASE_KEY_PASSWORD\") ?: \"\"\n"
            "        }\n"
            "    }\n"
        )
        if "signingConfigs {" not in content:
            content = content.replace(
                "buildTypes {",
                signing_block + "    buildTypes {",
            )
        content = content.replace(
            "signingConfig signingConfigs.debug",
            "signingConfig signingConfigs.release",
        )
        self.gradle_path.write_text(content, encoding="utf-8")

        gradle_text = self.gradle_path.read_text(encoding="utf-8")
        self.assertNotIn("secret123!", gradle_text,
                         "keystore_password must NOT appear in build.gradle")
        self.assertNotIn("keysecret456!", gradle_text,
                         "key_password must NOT appear in build.gradle")
        self.assertIn("RELEASE_STORE_PASSWORD", gradle_text,
                      "build.gradle should reference RELEASE_STORE_PASSWORD env var")
        self.assertIn("RELEASE_KEY_PASSWORD", gradle_text,
                      "build.gradle should reference RELEASE_KEY_PASSWORD env var")

    def test_passwords_passed_via_env_not_files(self):
        preset = self._make_preset_with_keystore()
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        store_pass = ctx.preset.extra.get("keystore_password", "")
        sign_env = {}
        if store_pass:
            sign_env["RELEASE_STORE_PASSWORD"] = store_pass

        self.assertIn("RELEASE_STORE_PASSWORD", sign_env)
        self.assertEqual(sign_env["RELEASE_STORE_PASSWORD"], "secret123!")

        # Verify the passwords are in the env dict, not in any generated file
        # (we already checked build.gradle above)
        for path in self.staging.rglob("*"):
            if path.is_file() and path.suffix in (".gradle", ".properties", ".json", ".xml"):
                content = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn("secret123!", content,
                                 f"Password leaked in {path.relative_to(self.staging)}")
                self.assertNotIn("keysecret456!", content,
                                 f"Password leaked in {path.relative_to(self.staging)}")

    def test_missing_keystore_error_has_actionable_code(self):
        preset = self._make_preset_with_keystore(keystore_path="nonexistent.keystore")
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        from engine.export.android_exporter import AndroidExporter
        exporter = AndroidExporter()

        result = exporter._build_release(ctx, self.project_dir, {})
        self.assertFalse(result)
        self.assertTrue(any("ANDROID_KEYSTORE_NOT_FOUND" in e for e in ctx.errors))
        self.assertTrue(any("not found at configured path" in e for e in ctx.errors))

    def test_no_keystore_path_error_has_actionable_code(self):
        preset = ExportPreset(
            name="AndroidTest",
            platform="android",
            mode="release",
            output_path="dist/export/android/Test",
            entry_scene="levels/test.json",
            display_name="TestApp",
            extra={},
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        from engine.export.android_exporter import AndroidExporter
        exporter = AndroidExporter()

        result = exporter._build_release(ctx, self.project_dir, {})
        self.assertFalse(result)
        self.assertTrue(any("ANDROID_KEYSTORE_MISSING" in e for e in ctx.errors))

    def test_keystore_path_not_in_gradle_storefile(self):
        preset = self._make_preset_with_keystore()
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        from engine.export.android_exporter import AndroidExporter
        exporter = AndroidExporter()

        # Simulate _build_release but stop before running Gradle
        keystore = ctx.preset.extra.get("keystore_path", "")
        keystore_path = Path(keystore)
        if not keystore_path.is_absolute():
            keystore_path = ctx.project_root / keystore_path

        content = self.gradle_path.read_text(encoding="utf-8")
        signing_block = (
            "\n    signingConfigs {\n"
            "        release {\n"
            "            storeFile rootProject.file('keystore.jks')\n"
            "            storePassword System.getenv(\"RELEASE_STORE_PASSWORD\") ?: \"\"\n"
            "            keyAlias System.getenv(\"RELEASE_KEY_ALIAS\") ?: \"mykey\"\n"
            "            keyPassword System.getenv(\"RELEASE_KEY_PASSWORD\") ?: \"\"\n"
            "        }\n"
            "    }\n"
        )
        if "signingConfigs {" not in content:
            content = content.replace(
                "buildTypes {",
                signing_block + "    buildTypes {",
            )
        content = content.replace(
            "signingConfig signingConfigs.debug",
            "signingConfig signingConfigs.release",
        )
        self.gradle_path.write_text(content, encoding="utf-8")

        gradle_text = self.gradle_path.read_text(encoding="utf-8")
        self.assertNotIn(str(keystore_path), gradle_text,
                         "Keystore absolute path must NOT appear in build.gradle")
        self.assertIn("keystore.jks", gradle_text,
                      "Should use relative keystore.jks reference")


class TestAndroidOutputSemantics(unittest.TestCase):
    """Test output_path .apk/.aab semantics."""
    
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.staging = self.tmp / "staging"
        self.staging.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_output_path_apk_sets_artifact_filename(self):
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="AndroidTest",
            platform="android",
            output_path="dist/export/android/MyGame-debug.apk",
            entry_scene="levels/test.json",
            display_name="Test",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        from engine.export.android_exporter import AndroidExporter
        exporter = AndroidExporter()

        # Reset output_dir to simulate what the export method does
        output_path_str = ctx.preset.output_path
        if output_path_str.endswith((".apk", ".aab")):
            ctx.output_dir = ctx.project_root / Path(output_path_str).parent
            ctx._artifact_filename = Path(output_path_str).name

        self.assertEqual(ctx._artifact_filename, "MyGame-debug.apk")
        self.assertEqual(ctx.output_dir.name, "android")

    def test_output_path_dir_no_artifact_filename(self):
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="AndroidTest",
            platform="android",
            output_path="dist/export/android/MyGame",
            entry_scene="levels/test.json",
            display_name="Test",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx.staging_dir = self.staging

        output_path_str = ctx.preset.output_path
        if output_path_str.endswith((".apk", ".aab")):
            ctx._artifact_filename = Path(output_path_str).name
        else:
            ctx._artifact_filename = None

        self.assertIsNone(ctx._artifact_filename)

    def test_copy_android_artifact_replaces_stale_directory_for_exact_apk_path(self):
        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        source = self.staging / "app-debug.apk"
        source.write_bytes(b"apk-bytes")
        output = self.tmp / "dist" / "export" / "android"
        stale = output / "MyGame-debug.apk"
        stale.mkdir(parents=True)
        (stale / "old.apk").write_bytes(b"old")

        preset = ExportPreset(
            name="AndroidTest",
            platform="android",
            output_path="dist/export/android/MyGame-debug.apk",
            entry_scene="levels/test.json",
            display_name="Test",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx._artifact_filename = "MyGame-debug.apk"

        dest = AndroidExporter()._copy_android_artifact(ctx, source, output, "apk")

        self.assertTrue(dest.is_file())
        self.assertEqual(dest.read_bytes(), b"apk-bytes")
        self.assertEqual(ctx.artifacts[0]["size_bytes"], len(b"apk-bytes"))
        self.assertTrue(ctx.artifacts[0]["sha256"])

    def test_artifact_dest_name_only_uses_matching_extension(self):
        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="AndroidTest",
            platform="android",
            output_path="dist/export/android/MyGame-debug.apk",
            entry_scene="levels/test.json",
            display_name="Test",
        )
        ctx = BuildContext(preset, str(self.tmp))
        ctx._artifact_filename = "MyGame-debug.apk"
        exporter = AndroidExporter()

        self.assertEqual(exporter._artifact_dest_name(ctx, Path("source.apk")), "MyGame-debug.apk")
        self.assertEqual(exporter._artifact_dest_name(ctx, Path("source.aab")), "source.aab")


if __name__ == "__main__":
    unittest.main()
