"""Tests for Android project generation."""
from __future__ import annotations

import json
import sys
import tempfile
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
        self.assertIn("{{ANDROID_PERMISSIONS}}", content)
        self.assertIn("@drawable/ic_launcher", content)

    def test_build_gradle_has_placeholders(self):
        gradle_path = self.template_dir / "app" / "build.gradle"
        if not gradle_path.exists():
            self.skipTest("app/build.gradle not found")
        content = gradle_path.read_text(encoding="utf-8")
        self.assertIn("{{APPLICATION_ID}}", content)
        self.assertIn("{{MIN_SDK}}", content)
        self.assertIn("{{TARGET_SDK}}", content)
        self.assertIn("{{COMPILE_SDK}}", content)
        self.assertIn("{{VERSION_NAME}}", content)
        self.assertIn("{{VERSION_CODE}}", content)
        self.assertIn("{{ANDROID_ABI_FILTERS}}", content)
        self.assertIn("{{DEBUG_APPLICATION_ID_SUFFIX}}", content)

    def test_generated_gradle_keeps_compile_sdk_and_target_sdk_separate(self):
        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preset = ExportPreset(
                name="Android Debug",
                platform="android",
                architecture="arm64-v8a",
                mode="debug",
                output_path="dist/export/android/Test-debug.apk",
                entry_scene="levels/test.json",
                display_name="Test",
                application_id="com.example.test",
                min_sdk=24,
                target_sdk=35,
                compile_sdk=35,
                extra={"android_python_runtime": True},
            )
            ctx = BuildContext(preset, root)
            ctx.staging_dir.mkdir(parents=True, exist_ok=True)

            project_dir = AndroidExporter()._generate_android_project(ctx, ctx.staging_dir)
            gradle = (project_dir / "app" / "build.gradle").read_text(encoding="utf-8")

        self.assertIn("compileSdk 35", gradle)
        self.assertIn("targetSdk 35", gradle)
        self.assertNotIn("compileSdk {{TARGET_SDK}}", gradle)

    def test_android_release_project_is_not_debuggable_or_debug_suffixed(self):
        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preset = ExportPreset(
                name="Android Release Local",
                platform="android",
                architecture="arm64-v8a",
                mode="release",
                output_path="dist/export/android/Test-release-local.apk",
                entry_scene="levels/test.json",
                display_name="Test",
                application_id="com.example.test",
                min_sdk=24,
                extra={"android_python_runtime": True, "local_release_signing": True},
            )
            ctx = BuildContext(preset, root)
            ctx.staging_dir.mkdir(parents=True, exist_ok=True)

            project_dir = AndroidExporter()._generate_android_project(ctx, ctx.staging_dir)
            gradle = (project_dir / "app" / "build.gradle").read_text(encoding="utf-8")
            manifest = (project_dir / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")

        self.assertNotIn("applicationIdSuffix '.debug'", gradle)
        self.assertNotIn("signingConfig signingConfigs.debug", gradle)
        self.assertIn("abiFilters 'arm64-v8a'", gradle)
        self.assertNotIn("android.permission.INTERNET", manifest)
        self.assertNotIn("android.permission.ACCESS_NETWORK_STATE", manifest)

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
        self.assertIn("SharedRuntimeBridge", content)
        self.assertIn("ScriptBehaviourBridge", content)

    def test_android_template_uses_logical_viewport_letterbox(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn('config.optJSONObject("window")', content)
        self.assertIn("private fun viewportFrame(): RectF", content)
        self.assertIn("private fun screenToViewport", content)
        self.assertIn("canvas.translate(frame.left, frame.top)", content)
        self.assertIn("canvas.scale(frame.width() / viewportW, frame.height() / viewportH)", content)
        self.assertIn("if (mapped != null) activePointers", content)

    def test_android_template_delegates_python_runtime_to_shared_runtime(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("preparePythonRuntimeFiles()", content)
        self.assertIn("sharedRuntimeBridge?.runFrame", content)
        self.assertIn("return", content[content.index("if (androidPythonRuntime)") : content.index("updateMobileControls()")])
        self.assertIn("create_shared_runtime", content)
        self.assertIn("run_shared_frame", content)

    def test_android_template_uses_selective_cached_runtime_asset_copy(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn('config.optString("android_runtime_cache_key", "uncached")', content)
        self.assertIn('".motor_runtime_cache_key"', content)
        self.assertIn("ANDROID_RUNTIME_ASSET_PATHS", content)
        self.assertIn('"runtime_config.json", "game.manifest.json", "levels", "assets", "scripts"', content)
        self.assertIn('assetPath == "chaquopy" || assetPath.startsWith("chaquopy/")', content)
        self.assertNotIn('copyAssetTree("", runtimeDir)', content)

    def test_android_template_sends_pointer_id_payload_to_python_runtime(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private val pressedPointers = mutableMapOf<Int, Pair<Float, Float>>()", content)
        self.assertIn("private val releasedPointers = mutableMapOf<Int, Pair<Float, Float>>()", content)
        self.assertIn("val pointers = JSONArray()", content)
        self.assertIn('.put("id", pointerId)', content)
        self.assertIn('payload.put("pointers", pointers)', content)
        self.assertIn("pressedPointers.containsKey(pointerId)", content)
        self.assertIn("clearTouchEdges()", content)
        self.assertIn("pressedPointers.clear()", content)
        self.assertIn("releasedPointers.clear()", content)

    def test_android_template_keeps_mobile_control_alpha_out_of_world_paint(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private val controlsPaint = Paint(Paint.ANTI_ALIAS_FLAG)", content)
        self.assertIn("paint.alpha = 255", content)
        self.assertIn("controlsPaint.color = Color.argb", content)
        self.assertIn("canvas.drawCircle(sx, sy, radius, controlsPaint)", content)

    def test_android_template_supports_dpad_mobile_controls(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn('controls.optString("movement_mode", "joystick")', content)
        self.assertIn('if (movementMode(controls) == "dpad")', content)
        self.assertIn('inputState["horizontal"] = if (dx >= 0.0f) 1.0f else -1.0f', content)
        self.assertIn("private fun drawDpad", content)

    def test_android_template_renders_pixel_art_without_bitmap_filtering(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private val spritePaint = Paint().apply", content)
        self.assertIn("isAntiAlias = false", content)
        self.assertIn("isFilterBitmap = false", content)
        self.assertIn("isDither = false", content)
        self.assertIn("BitmapFactory.Options().apply", content)
        self.assertIn("inScaled = false", content)
        self.assertIn("BitmapFactory.decodeStream(it, null, options)", content)

    def test_android_template_applies_animator_flip_when_drawing_frames(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private fun drawBitmapFrame", content)
        self.assertIn('flipX = animator.optBoolean("flip_x", false)', content)
        self.assertIn('flipY = animator.optBoolean("flip_y", false)', content)
        self.assertIn("if (flipX) -1.0f else 1.0f", content)
        self.assertIn("if (flipY) -1.0f else 1.0f", content)
        self.assertIn("canvas.drawBitmap(bitmap, src, dst, spritePaint)", content)

    def test_android_template_resolves_animator_slices_and_sprite_source_slice(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private val spriteMetadata = mutableMapOf<String, JSONObject?>()", content)
        self.assertIn("private fun getSliceRect", content)
        self.assertIn("private fun loadSpriteMetadata", content)
        self.assertIn('context.assets.open("$assetPath.meta.json")', content)
        self.assertIn('anim?.optJSONArray("slice_names")', content)
        self.assertIn('sprite.optString("source_slice", "")', content)

    def test_android_template_draws_sprite_and_animator_when_both_exist(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("drawAnimatedSprite(canvas, animator, entity, camera)", content)
        self.assertIn("drawSprite(canvas, sprite, entity, camera)", content)
        self.assertNotIn("} else if (bitmap != null) {", content)

    def test_android_template_does_not_render_camera_placeholder(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn('if (entity.components.has("Camera2D")) return', content)
        self.assertIn("canvas.drawRect(dst, paint)", content)

    def test_android_template_sorts_world_entities_like_renderer(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("val sceneIndex: Int", content)
        self.assertIn("for (entity in sortedWorldEntities())", content)
        self.assertIn("private fun sortedWorldEntities(): List<Entity>", content)
        self.assertIn('!it.components.has("Camera2D")', content)
        self.assertIn("compareBy<Entity> { renderPassIndex(it) }", content)
        self.assertIn(".thenBy { sortingLayerIndex(it) }", content)
        self.assertIn(".thenBy { renderOrderInLayer(it) }", content)
        self.assertIn(".thenBy { entityDepth(it) }", content)
        self.assertIn(".thenBy { it.sceneIndex }", content)
        self.assertIn('optJSONObject("render_2d")', content)
        self.assertIn('optJSONArray("sorting_layers")', content)
        self.assertIn('optJSONObject("RenderOrder2D")', content)

    def test_android_template_fallback_animator_tracks_speed_loop_and_on_complete(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn('animator.optDouble("speed", 1.0)', content)
        self.assertIn('animator.put("is_finished", true)', content)
        self.assertIn('val onComplete = anim.optString("on_complete", "")', content)
        self.assertIn('animator.put("current_state", onComplete)', content)

    def test_android_template_hides_disabled_mobile_action_buttons(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn('if (controls.optBoolean("action_1_enabled", true))', content)
        self.assertIn('if (controls.optBoolean("action_2_enabled", true))', content)
        self.assertIn('controls.optDouble("action_1_radius", 54.0).toFloat()', content)
        self.assertIn('controls.optDouble("action_2_radius", 46.0).toFloat()', content)

    def test_android_template_renders_visible_runtime_error(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private var runtimeError: String? = null", content)
        self.assertIn("drawRuntimeError(canvas, error)", content)
        self.assertIn("Motor Android runtime error", content)
        self.assertIn("setRuntimeError(", content)
        self.assertIn('snapshot?.optString("traceback", "")', content)

    def test_android_template_uses_visual_rect_for_render_and_collider_rect_for_physics(self):
        kt_path = self.template_dir / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt"
        content = kt_path.read_text(encoding="utf-8")
        self.assertIn("private fun visualRect(entity: Entity): RectF?", content)
        self.assertIn("val rect = visualRect(entity) ?: worldRect(entity) ?: return", content)
        self.assertIn('val c = entity.components.optJSONObject("Collider")', content)
        self.assertIn("private fun visualRectForSprite", content)
        self.assertIn('sprite.optDouble("height", baseHeight)', content)

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

    def test_runtime_config_resolves_mobile_landscape_window(self):
        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        preset = ExportPreset(
            name="Android Mobile Debug",
            platform="android",
            mode="debug",
            output_path="dist/export/android/Test.apk",
            entry_scene="levels/test.json",
            display_name="Test",
            application_id="com.example.test",
            min_sdk=24,
            window={"device_profile": "mobile_landscape"},
        )
        ctx = BuildContext(preset, self.project_root)
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)

        AndroidExporter()._write_runtime_config(ctx, ctx.staging_dir)

        config = json.loads((ctx.staging_dir / "runtime_config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["window"]["device_profile"], "mobile_landscape")
        self.assertEqual(config["window"]["width"], 844)
        self.assertEqual(config["window"]["height"], 390)
        self.assertIn("android_runtime_cache_key", config)

    def test_runtime_config_android_cache_key_is_stable_and_content_and_runtime_derived(self):
        from engine.export.android_exporter import AndroidExporter
        from engine.export.build_context import BuildContext
        from engine.export.models import ExportPreset

        runtime_seed = self.project_root / "runtime_seed.txt"
        runtime_seed.write_text("runtime-a", encoding="utf-8")

        class TestAndroidExporter(AndroidExporter):
            def _android_runtime_cache_seed_files(self):
                return [runtime_seed]

        preset = ExportPreset(
            name="Android Mobile Debug",
            platform="android",
            mode="debug",
            output_path="dist/export/android/Test.apk",
            entry_scene="levels/test.json",
            display_name="Test",
            application_id="com.example.test",
            min_sdk=24,
            extra={"android_python_runtime": True},
        )
        ctx = BuildContext(preset, self.project_root)
        ctx.staging_dir.mkdir(parents=True, exist_ok=True)
        manifest = ctx.staging_dir / "game.manifest.json"
        manifest.write_text('{"assets":["a.png"]}', encoding="utf-8")

        exporter = TestAndroidExporter()
        exporter._write_runtime_config(ctx, ctx.staging_dir)
        first = json.loads((ctx.staging_dir / "runtime_config.json").read_text(encoding="utf-8"))[
            "android_runtime_cache_key"
        ]
        exporter._write_runtime_config(ctx, ctx.staging_dir)
        second = json.loads((ctx.staging_dir / "runtime_config.json").read_text(encoding="utf-8"))[
            "android_runtime_cache_key"
        ]
        manifest.write_text('{"assets":["b.png"]}', encoding="utf-8")
        exporter._write_runtime_config(ctx, ctx.staging_dir)
        third = json.loads((ctx.staging_dir / "runtime_config.json").read_text(encoding="utf-8"))[
            "android_runtime_cache_key"
        ]
        manifest.write_text('{"assets":["a.png"]}', encoding="utf-8")
        runtime_seed.write_text("runtime-b", encoding="utf-8")
        exporter._write_runtime_config(ctx, ctx.staging_dir)
        fourth = json.loads((ctx.staging_dir / "runtime_config.json").read_text(encoding="utf-8"))[
            "android_runtime_cache_key"
        ]

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertNotEqual(first, fourth)

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

    def test_android_python_runtime_copies_shared_engine_runtime(self):
        from engine.export.android_exporter import AndroidExporter

        project_dir = self.project_root / "staging" / "android_project"
        ctx = self._ctx(android_python_runtime=True, min_sdk=24)

        AndroidExporter()._copy_android_python_runtime(ctx, project_dir, [])

        python_root = project_dir / "app" / "src" / "main" / "python"
        self.assertTrue((python_root / "engine" / "runtime" / "shared_game_runtime.py").exists())
        self.assertTrue((python_root / "pyray" / "__init__.py").exists())
        self.assertTrue((python_root / "sitecustomize.py").exists())
        self.assertFalse(ctx.errors)

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
        ctx = self._ctx(android_python_runtime=True, min_sdk=24)
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], [])

        self.assertTrue(ok, ctx.errors)

    def test_validation_blocks_playable_scene_without_shared_runtime(self):
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

        self.assertFalse(ok)
        self.assertTrue(any("ANDROID_RUNTIME_REQUIRES_SHARED_RUNTIME" in err for err in ctx.errors))

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

    def test_validation_blocks_advanced_animator_without_shared_runtime(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene(
            "test.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {},
                        "Animator": {
                            "sprite_sheet": {"path": "assets/player.png", "guid": ""},
                            "speed": 1.5,
                            "flip_y": True,
                            "parameters": {"facing": {"type": "string", "default": "down"}},
                            "state_machine": {"entry_state": "idle", "states": {}},
                            "animations": {
                                "idle": {
                                    "slice_names": ["idle_0"],
                                    "fps": 8.0,
                                    "loop": False,
                                    "on_complete": "run",
                                },
                                "run": {"frames": [1], "fps": 8.0, "loop": True},
                            },
                        },
                    },
                },
            ],
        )
        ctx = self._ctx()
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], [])

        self.assertFalse(ok)
        self.assertTrue(any("ANDROID_RUNTIME_UNSUPPORTED_ANIMATOR_ADVANCED" in err for err in ctx.errors))

    def test_validation_accepts_advanced_animator_with_shared_runtime(self):
        from engine.export.android_exporter import AndroidExporter

        scene = self._write_scene(
            "test.json",
            [
                {
                    "name": "Player",
                    "components": {
                        "Transform": {},
                        "Animator": {
                            "sprite_sheet": {"path": "assets/player.png", "guid": ""},
                            "speed": 1.5,
                            "parameters": {"facing": {"type": "string", "default": "down"}},
                            "state_machine": {"entry_state": "idle", "states": {}},
                            "animations": {"idle": {"slice_names": ["idle_0"], "fps": 8.0, "loop": True}},
                        },
                    },
                },
            ],
        )
        ctx = self._ctx(android_python_runtime=True, min_sdk=24)
        ok = AndroidExporter()._validate_android_runtime_v1(ctx, [scene], [])

        self.assertTrue(ok, ctx.errors)


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
