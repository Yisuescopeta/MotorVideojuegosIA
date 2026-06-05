"""Android platform exporter using Gradle + Android SDK."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
from hashlib import sha256
from html import escape as _html_escape
from pathlib import Path
from typing import Any

from engine.export.build_context import BuildContext
from engine.export.content_pack import build_content_pack
from engine.export.platform_exporter import PlatformExporter
from engine.utils.device_profiles import resolve_window_config

_PLACEHOLDERS = {
    "{{APPLICATION_ID}}": "application_id",
    "{{DISPLAY_NAME}}": "display_name",
    "{{VERSION_NAME}}": "version_name",
    "{{VERSION_CODE}}": "version_code",
    "{{MIN_SDK}}": "min_sdk",
    "{{TARGET_SDK}}": "target_sdk",
    "{{COMPILE_SDK}}": "compile_sdk",
    "{{ORIENTATION}}": "orientation",
    "{{ENTRY_SCENE}}": "entry_scene",
}


def _xml_escape(value: str) -> str:
    return _html_escape(value, quote=True)


def _gradle_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


class AndroidExporter(PlatformExporter):
    platform = "android"

    def validate_environment(self, project_dir: Path | None = None) -> dict[str, Any]:
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
        java_path = shutil.which("java") or shutil.which("java.exe") or ""
        gradle_command = self._resolve_gradle_command(project_dir)
        gradle_path = " ".join(gradle_command)
        return {
            "platform": "android",
            "android_sdk_available": bool(android_home),
            "android_home": android_home,
            "java_available": bool(java_path),
            "java_path": java_path,
            "gradle_available": bool(gradle_command),
            "gradle_path": gradle_path,
            "python": sys.executable,
        }

    def export(self, ctx: BuildContext) -> bool:
        env = self.validate_environment()
        staging = ctx.staging_dir
        staging.mkdir(parents=True, exist_ok=True)

        # Resolve output semantics: if output_path ends with .apk/.aab,
        # use parent as output_dir and copy artifact to exact output_path
        output_path_str = ctx.preset.output_path
        if output_path_str.endswith((".apk", ".aab")):
            ctx.output_dir = ctx.project_root / Path(output_path_str).parent
            ctx._artifact_filename = Path(output_path_str).name
        else:
            ctx.output_dir = ctx.project_root / output_path_str
            ctx._artifact_filename = None

        output = ctx.output_dir
        output.mkdir(parents=True, exist_ok=True)

        try:
            manifest, graph = build_content_pack(
                ctx.preset, ctx.project_root, staging,
            )
        except Exception as exc:
            ctx.add_error(f"Content pack failed: {exc}")
            return False

        ctx.add_warning(
            f"Content pack built: {len(manifest.assets)} assets, "
            f"{len(manifest.scenes)} scenes, {len(manifest.scripts)} scripts"
        )

        if not self._validate_android_runtime_v1(ctx, graph.reachable_scenes, graph.reachable_scripts):
            return False

        self._write_runtime_config(ctx, staging)

        project_dir = self._generate_android_project(ctx, staging)
        env = self.validate_environment(project_dir)

        assets_src = staging / "content"
        assets_dst = project_dir / "app" / "src" / "main" / "assets"
        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)

        manifest_src = staging / "game.manifest.json"
        if manifest_src.exists():
            shutil.copy2(manifest_src, assets_dst / "game.manifest.json")

        runtime_config_src = staging / "runtime_config.json"
        if runtime_config_src.exists():
            shutil.copy2(runtime_config_src, assets_dst / "runtime_config.json")

        if self._android_python_runtime_enabled(ctx):
            self._copy_android_python_runtime(ctx, project_dir, graph.reachable_scripts)

        self._add_project_artifacts(ctx, project_dir)

        if not env["android_sdk_available"]:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: ANDROID_HOME not set. "
                "Set ANDROID_HOME or ANDROID_SDK_ROOT environment variable. "
                "Download Android SDK from https://developer.android.com/studio"
            )
            return False

        if not env["java_available"]:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: Java/JDK not found. "
                "Install JDK 11 or later. Run: java -version"
            )
            return False

        if not env["gradle_available"]:
            ctx.add_error(
                "Gradle not found in PATH and no Gradle wrapper found in generated project. "
                "Android project generated but not built. Install Gradle, add gradlew/gradlew.bat, "
                "or use the generated project directly in Android Studio."
            )
            return False

        if ctx.preset.mode == "release":
            keystore = ctx.preset.extra.get("keystore_path", "")
            if keystore or bool(ctx.preset.extra.get("local_release_signing", False)):
                ok = self._build_release(ctx, project_dir, env)
            else:
                ctx.add_error(
                    "ANDROID_RELEASE_SIGNING_REQUIRED: Release build requires "
                    "extra.keystore_path or extra.local_release_signing=true."
                )
                return False
        else:
            ok = self._run_gradle_build(ctx, project_dir, "assembleDebug")

        if not ok:
            return False

        apk = self._find_apk(project_dir, ctx.preset.mode)
        if apk:
            self._copy_android_artifact(ctx, apk, output, "apk")

        if ctx.preset.mode == "release":
            aab = self._find_aab(project_dir, ctx.preset.mode)
            if aab:
                self._copy_android_artifact(ctx, aab, output, "aab")

        return not ctx.has_errors

    def _write_runtime_config(self, ctx: BuildContext, staging: Path) -> None:
        config = {
            "schema_version": 1,
            "entry_scene": ctx.preset.entry_scene,
            "project_name": ctx.preset.display_name or ctx.preset.name,
            "version": ctx.preset.version_name,
            "window": resolve_window_config(ctx.preset.window),
            "debug_tools": ctx.preset.include_debug_tools,
            "android_python_runtime": self._android_python_runtime_enabled(ctx),
            "android_runtime_cache_key": self._android_runtime_cache_key(staging),
        }
        (staging / "runtime_config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _android_runtime_cache_key(self, staging: Path) -> str:
        digest = sha256()
        manifest = staging / "game.manifest.json"
        if manifest.exists():
            digest.update(b"manifest\0")
            digest.update(manifest.read_bytes())
        for path in self._android_runtime_cache_seed_files():
            if path.exists():
                try:
                    seed_name = str(path.relative_to(Path(__file__).resolve().parent.parent.parent))
                except ValueError:
                    seed_name = path.name
                digest.update(seed_name.encode("utf-8"))
                digest.update(b"\0")
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _android_runtime_cache_seed_files(self) -> list[Path]:
        root = Path(__file__).resolve().parent.parent.parent
        template_root = root / "platforms" / "android" / "template"
        return [
            template_root / "app" / "src" / "main" / "java" / "com" / "motorvideojuegos" / "MainActivity.kt",
            template_root / "app" / "src" / "main" / "python" / "motor_android_runtime.py",
        ]

    def _generate_android_project(
        self, ctx: BuildContext, staging: Path,
    ) -> Path:
        template_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "platforms" / "android" / "template"
        )
        project_dir = staging / "android_project"

        if template_dir.exists():
            shutil.copytree(template_dir, project_dir, dirs_exist_ok=True)
        else:
            project_dir.mkdir(parents=True, exist_ok=True)
            ctx.add_warning(
                "Android template not found at platforms/android/template/. "
                "Generating minimal project structure."
            )

        replacements = self._build_replacements(ctx)
        for file_path in project_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in (
                ".gradle", ".xml", ".kt", ".properties", ".pro",
            ):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    rmap = replacements["gradle"] if file_path.suffix == ".gradle" else replacements["xml"]
                    for placeholder, value in rmap.items():
                        content = content.replace(placeholder, value)
                    file_path.write_text(content, encoding="utf-8")
                except Exception:
                    pass

        return project_dir

    def _build_replacements(self, ctx: BuildContext) -> dict[str, dict[str, str]]:
        app_id = ctx.preset.application_id or "com.motor.game"
        display = ctx.preset.display_name or ctx.preset.name
        version = ctx.preset.version_name
        version_code = str(ctx.preset.version_code)
        min_sdk = str(ctx.preset.min_sdk)
        target_sdk = str(ctx.preset.target_sdk)
        compile_sdk = str(ctx.preset.compile_sdk)
        orientation = ctx.preset.orientation or "landscape"
        entry = ctx.preset.entry_scene
        android_permissions = self._android_permissions(ctx)
        abi_filters = self._android_abi_filters(ctx)
        debug_application_id_suffix = "applicationIdSuffix '.debug'" if ctx.preset.mode == "debug" else ""

        return {
            "xml": {
                "{{APPLICATION_ID}}": _xml_escape(app_id),
                "{{DISPLAY_NAME}}": _xml_escape(display),
                "{{VERSION_NAME}}": _xml_escape(version),
                "{{VERSION_CODE}}": version_code,
                "{{MIN_SDK}}": min_sdk,
                "{{TARGET_SDK}}": target_sdk,
                "{{COMPILE_SDK}}": compile_sdk,
                "{{ORIENTATION}}": _xml_escape(orientation),
                "{{ENTRY_SCENE}}": _xml_escape(entry),
                "{{CHAQUOPY_ROOT_PLUGIN}}": "",
                "{{CHAQUOPY_APP_PLUGIN}}": "",
                "{{ANDROID_PERMISSIONS}}": android_permissions,
                "{{ANDROID_ABI_FILTERS}}": abi_filters,
                "{{DEBUG_APPLICATION_ID_SUFFIX}}": debug_application_id_suffix,
            },
            "gradle": {
                "{{APPLICATION_ID}}": _gradle_escape(app_id),
                "{{DISPLAY_NAME}}": _gradle_escape(display),
                "{{VERSION_NAME}}": _gradle_escape(version),
                "{{VERSION_CODE}}": version_code,
                "{{MIN_SDK}}": min_sdk,
                "{{TARGET_SDK}}": target_sdk,
                "{{COMPILE_SDK}}": compile_sdk,
                "{{ORIENTATION}}": _gradle_escape(orientation),
                "{{ENTRY_SCENE}}": _gradle_escape(entry),
                "{{CHAQUOPY_ROOT_PLUGIN}}": (
                    "id 'com.chaquo.python' version '17.0.0' apply false"
                    if self._android_python_runtime_enabled(ctx)
                    else ""
                ),
                "{{CHAQUOPY_APP_PLUGIN}}": (
                    "id 'com.chaquo.python'"
                    if self._android_python_runtime_enabled(ctx)
                    else ""
                ),
                "{{ANDROID_PERMISSIONS}}": android_permissions,
                "{{ANDROID_ABI_FILTERS}}": abi_filters,
                "{{DEBUG_APPLICATION_ID_SUFFIX}}": debug_application_id_suffix,
            },
        }

    def _android_python_runtime_enabled(self, ctx: BuildContext) -> bool:
        return bool(ctx.preset.extra.get("android_python_runtime", False))

    def _android_permissions(self, ctx: BuildContext) -> str:
        if not bool(ctx.preset.extra.get("android_network_permissions", False)):
            return ""
        return (
            '<uses-permission android:name="android.permission.INTERNET" />\n'
            '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />'
        )

    def _android_abi_filters(self, ctx: BuildContext) -> str:
        architecture = str(ctx.preset.architecture or "").strip()
        if architecture and architecture != "universal":
            return f"'{_gradle_escape(architecture)}'"
        return "'arm64-v8a', 'armeabi-v7a', 'x86_64'"

    def _validate_android_runtime_v1(
        self,
        ctx: BuildContext,
        reachable_scenes: list[str],
        reachable_scripts: list[str],
    ) -> bool:
        """Fail early when the native Android v1 runtime cannot run a scene."""
        python_runtime = self._android_python_runtime_enabled(ctx)
        if reachable_scripts and not python_runtime:
            for script in reachable_scripts:
                ctx.add_error(
                    "ANDROID_RUNTIME_UNSUPPORTED_SCRIPT: ScriptBehaviour/Python scripts "
                    f"are not supported by the native Android runtime v1: {script}. "
                    "Enable android_python_runtime in the Android preset or remove "
                    "ScriptBehaviour from Android scenes."
                )
        if python_runtime and ctx.preset.min_sdk < 24:
            ctx.add_error(
                "ANDROID_PYTHON_RUNTIME_MIN_SDK: android_python_runtime requires "
                "min_sdk >= 24 for Chaquopy 17.0.0."
            )

        supported_components = {
            "Transform",
            "RectTransform",
            "Canvas",
            "UIText",
            "UIButton",
            "UIImage",
            "Camera2D",
            "Collider",
            "RigidBody",
            "InputMap",
            "PlayerController2D",
            "Animator",
            "Sprite",
            "MobileControls2D",
        }
        if python_runtime:
            supported_components.update({
                "ScriptBehaviour",
                "Collectible2D",
                "Hazard2D",
                "Goal2D",
                "RespawnPoint2D",
                "MovingPlatform2D",
                "EnemyPatrol2D",
                "Checkpoint2D",
                "KillZone2D",
                "LevelBounds2D",
            })
        unsupported_v1 = {
            "AudioSource",
            "AudioListener2D",
            "Tilemap",
            "ParticleEmitter2D",
            "Light2D",
            "NavigationAgent2D",
            "NavigationObstacle2D",
            "Tween",
            "Timer",
            "ResourcePreloader",
            "Line2D",
            "Polygon2D",
            "Area2D",
            "RayCast2D",
            "CharacterController2D",
            "SceneTransitionAction",
            "SceneTransitionOnContact",
            "SceneTransitionOnInteract",
            "SceneTransitionOnPlayerDeath",
            "SceneEntryPoint",
            "SceneLink",
            "RenderOrder2D",
            "RenderStyle2D",
            "VisibleOnScreenNotifier2D",
            "VisibleOnScreenEnabler2D",
            "PathFollower2D",
            "ParallaxLayer",
            "Joint2D",
            "CollisionShape2D",
            "CollisionShapeSet2D",
            "CollisionPolygon2D",
            "CollisionFilter2D",
            "StaticBody2D",
            "AnimatableBody2D",
            "Marker2D",
        }
        if not python_runtime:
            unsupported_v1.update({
                "ScriptBehaviour",
                "Collectible2D",
                "Hazard2D",
                "Goal2D",
                "RespawnPoint2D",
                "MovingPlatform2D",
                "EnemyPatrol2D",
                "Checkpoint2D",
                "KillZone2D",
                "LevelBounds2D",
            })

        for scene_path in reachable_scenes:
            scene_file = ctx.project_root / scene_path
            try:
                data = json.loads(scene_file.read_text(encoding="utf-8"))
            except Exception as exc:
                ctx.add_error(f"ANDROID_RUNTIME_SCENE_PARSE_FAILED: {scene_path}: {exc}")
                continue

            mobile_targets: set[str] = set()
            playable_targets: set[str] = set()
            for entity in data.get("entities", []):
                if not isinstance(entity, dict):
                    continue
                name = str(entity.get("name", ""))
                components = entity.get("components", {})
                if not isinstance(components, dict):
                    continue
                if "MobileControls2D" in components:
                    control = components.get("MobileControls2D", {})
                    if isinstance(control, dict):
                        mobile_targets.add(str(control.get("target_entity", "Player") or "Player"))
                if "InputMap" in components and "PlayerController2D" in components:
                    playable_targets.add(name)
                animator = components.get("Animator")
                if not python_runtime and isinstance(animator, dict) and self._animator_requires_shared_runtime(animator):
                    ctx.add_error(
                        "ANDROID_RUNTIME_UNSUPPORTED_ANIMATOR_ADVANCED: "
                        f"{scene_path}:{name} uses Animator state_machine, parameters, "
                        "slice_names, flip_y, speed, or on_complete, which require "
                        "android_python_runtime=true for Android parity."
                    )
                for component_name in components:
                    if component_name in unsupported_v1 or component_name not in supported_components:
                        ctx.add_error(
                            "ANDROID_RUNTIME_UNSUPPORTED_COMPONENT: "
                            f"{scene_path}:{name} uses {component_name}, which is not "
                            "supported by the native Android runtime v1."
                        )

            missing_controls = sorted(playable_targets - mobile_targets)
            for target in missing_controls:
                ctx.add_error(
                    "ANDROID_RUNTIME_MOBILE_CONTROLS_MISSING: "
                    f"{scene_path} has playable entity '{target}' without a "
                    "MobileControls2D overlay targeting it. Run: "
                    f"py -m motor mobile controls add --scene {scene_path} "
                    f"--target {target} --profile platformer --project . --json"
                )
            if playable_targets and not python_runtime:
                ctx.add_error(
                    "ANDROID_RUNTIME_REQUIRES_SHARED_RUNTIME: "
                    f"{scene_path} has playable entities "
                    f"{', '.join(sorted(playable_targets))}; Android gameplay parity "
                    "requires android_python_runtime=true and min_sdk >= 24."
                )

        return not ctx.has_errors

    def _animator_requires_shared_runtime(self, animator: dict[str, Any]) -> bool:
        if isinstance(animator.get("state_machine"), dict):
            return True
        if isinstance(animator.get("parameters"), dict) and animator.get("parameters"):
            return True
        if bool(animator.get("flip_y", False)):
            return True
        try:
            if float(animator.get("speed", 1.0)) != 1.0:
                return True
        except (TypeError, ValueError):
            return True
        animations = animator.get("animations", {})
        if not isinstance(animations, dict):
            return False
        for animation in animations.values():
            if not isinstance(animation, dict):
                continue
            if animation.get("on_complete") is not None:
                return True
            slice_names = animation.get("slice_names", [])
            if isinstance(slice_names, list) and slice_names:
                return True
        return False

    def _run_gradle_build(
        self, ctx: BuildContext, project_dir: Path, task: str,
        extra_env: dict[str, str] | None = None,
    ) -> bool:
        gradle = self._resolve_gradle_command(project_dir)
        if not gradle:
            ctx.add_error("Gradle not found in PATH and no Gradle wrapper found in generated project.")
            return False

        env = os.environ.copy()
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
        if android_home:
            env["ANDROID_HOME"] = android_home
        if extra_env:
            env.update(extra_env)

        try:
            result = subprocess.run(
                [*gradle, task],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(project_dir),
                env=env,
            )
            if result.returncode != 0:
                output = "\n".join(
                    part for part in (result.stdout, result.stderr) if part
                )
                tail = output[-8000:]
                ctx.add_error(
                    f"Gradle {task} failed (code {result.returncode}) "
                    f"in {project_dir}:\n{tail}"
                )
                return False
        except subprocess.TimeoutExpired:
            ctx.add_error(f"Gradle {task} timed out after 600s")
            return False
        except Exception as exc:
            ctx.add_error(f"Gradle {task} failed: {exc}")
            return False

        return True

    def _resolve_gradle_command(self, project_dir: Path | None = None) -> list[str]:
        if project_dir is not None:
            wrapper = project_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
            wrapper_dir = wrapper.parent / "gradle" / "wrapper"
            if (
                wrapper.exists()
                and (wrapper_dir / "gradle-wrapper.properties").exists()
                and (wrapper_dir / "gradle-wrapper.jar").exists()
            ):
                return [str(wrapper)]
        gradle = shutil.which("gradle") or shutil.which("gradle.bat")
        return [gradle] if gradle else []

    def _copy_android_python_scripts(
        self,
        ctx: BuildContext,
        project_dir: Path,
        reachable_scripts: list[str],
    ) -> None:
        python_root = project_dir / "app" / "src" / "main" / "python"
        python_root.mkdir(parents=True, exist_ok=True)
        for script in reachable_scripts:
            normalized = str(script).replace("\\", "/").lstrip("/")
            if not normalized.startswith("scripts/") or not normalized.endswith(".py"):
                continue
            src = ctx.project_root / normalized
            if not src.exists():
                ctx.add_warning(f"Android Python script missing: {normalized}")
                continue
            rel = normalized[len("scripts/"):]
            dest = python_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    def _copy_android_python_runtime(
        self,
        ctx: BuildContext,
        project_dir: Path,
        reachable_scripts: list[str],
    ) -> None:
        python_root = project_dir / "app" / "src" / "main" / "python"
        python_root.mkdir(parents=True, exist_ok=True)
        repo_root = Path(__file__).resolve().parents[2]
        ignore = shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
        )
        for package_name in ("engine", "pyray"):
            src = repo_root / package_name
            dest = python_root / package_name
            if not src.exists():
                ctx.add_error(f"ANDROID_PYTHON_RUNTIME_MISSING: {package_name}")
                continue
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=ignore)
        sitecustomize = repo_root / "sitecustomize.py"
        if sitecustomize.exists():
            shutil.copy2(sitecustomize, python_root / "sitecustomize.py")
        else:
            ctx.add_error("ANDROID_PYTHON_RUNTIME_MISSING: sitecustomize.py")
        self._copy_android_python_scripts(ctx, project_dir, reachable_scripts)

    def _build_release(
        self, ctx: BuildContext, project_dir: Path, env: dict[str, Any],
    ) -> bool:
        signing = self._resolve_release_signing(ctx, project_dir, env)
        if signing is None:
            return False

        keystore_path = signing["keystore_path"]
        store_pass = signing["store_pass"]
        key_alias = signing["key_alias"]
        key_pass = signing["key_pass"]

        gradle_path = project_dir / "app" / "build.gradle"
        if gradle_path.exists():
            content = gradle_path.read_text(encoding="utf-8")
            signing_block = (
                "\n    signingConfigs {\n"
                "        release {\n"
                "            storeFile rootProject.file('keystore.jks')\n"
                "            storePassword System.getenv(\"RELEASE_STORE_PASSWORD\") ?: \"\"\n"
                f"            keyAlias System.getenv(\"RELEASE_KEY_ALIAS\") ?: \"{key_alias}\"\n"
                "            keyPassword System.getenv(\"RELEASE_KEY_PASSWORD\") ?: \"\"\n"
                "        }\n"
                "    }\n"
            )
            if "signingConfigs {" not in content:
                content = content.replace(
                    "buildTypes {",
                    signing_block + "    buildTypes {",
                )
            if "signingConfig signingConfigs.release" not in content:
                content = content.replace(
                    "release {\n            minifyEnabled true",
                    "release {\n            minifyEnabled true\n            signingConfig signingConfigs.release",
                )
            content = content.replace(
                "signingConfig signingConfigs.debug",
                "signingConfig signingConfigs.release",
            )
            gradle_path.write_text(content, encoding="utf-8")

        keystore_dest = project_dir / "keystore.jks"
        shutil.copy2(keystore_path, keystore_dest)

        sign_env: dict[str, str] = {}
        if store_pass:
            sign_env["RELEASE_STORE_PASSWORD"] = store_pass
        if key_pass:
            sign_env["RELEASE_KEY_PASSWORD"] = key_pass

        ok = self._run_gradle_build(ctx, project_dir, "assembleRelease", extra_env=sign_env)
        if ok:
            self._run_gradle_build(ctx, project_dir, "bundleRelease", extra_env=sign_env)
        return ok

    def _resolve_release_signing(
        self, ctx: BuildContext, project_dir: Path, env: dict[str, Any],
    ) -> dict[str, str] | None:
        if bool(ctx.preset.extra.get("local_release_signing", False)) and not ctx.preset.extra.get("keystore_path", ""):
            return self._ensure_local_release_signing(ctx, env)

        keystore = ctx.preset.extra.get("keystore_path", "")
        store_pass = ctx.preset.extra.get("keystore_password", "")
        key_alias = ctx.preset.extra.get("key_alias", "")
        key_pass = ctx.preset.extra.get("key_password", store_pass)

        if not keystore:
            ctx.add_error(
                "ANDROID_KEYSTORE_MISSING: Release build requires "
                "keystore_path in preset extra. Configure keystore_path, "
                "keystore_password, key_alias in the preset extra fields."
            )
            return None

        keystore_path = Path(keystore)
        if not keystore_path.is_absolute():
            keystore_path = ctx.project_root / keystore_path

        if not keystore_path.exists():
            ctx.add_error(
                "ANDROID_KEYSTORE_NOT_FOUND: Keystore not found at configured path. "
                "Create a keystore or update keystore_path."
            )
            return None
        return {
            "keystore_path": str(keystore_path),
            "store_pass": str(store_pass),
            "key_alias": str(key_alias),
            "key_pass": str(key_pass),
        }

    def _ensure_local_release_signing(self, ctx: BuildContext, env: dict[str, Any]) -> dict[str, str] | None:
        signing_dir = ctx.project_root / ".motor" / "android"
        signing_dir.mkdir(parents=True, exist_ok=True)
        keystore_path = signing_dir / "local-release.keystore"
        metadata_path = signing_dir / "local-release-signing.json"

        if metadata_path.exists() and keystore_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            keytool = shutil.which("keytool") or shutil.which("keytool.exe")
            if not keytool:
                java_path = str(env.get("java_path", "") or "")
                candidate = Path(java_path).resolve().parent / "keytool.exe" if java_path else Path()
                keytool = str(candidate) if candidate.exists() else ""
            if not keytool:
                ctx.add_error(
                    "ANDROID_KEYTOOL_MISSING: local_release_signing requires keytool from the JDK."
                )
                return None
            metadata = {
                "store_pass": secrets.token_urlsafe(24),
                "key_alias": "motor_local_release",
            }
            metadata["key_pass"] = metadata["store_pass"]
            command = [
                keytool,
                "-genkeypair",
                "-v",
                "-keystore",
                str(keystore_path),
                "-storepass",
                metadata["store_pass"],
                "-keypass",
                metadata["key_pass"],
                "-alias",
                metadata["key_alias"],
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "10000",
                "-dname",
                "CN=Motor Local Release, O=MotorVideojuegosIA, C=ES",
            ]
            result = subprocess.run(command, cwd=str(ctx.project_root), capture_output=True, text=True)
            if result.returncode != 0:
                ctx.add_error(
                    "ANDROID_LOCAL_KEYSTORE_FAILED: keytool could not create the local release keystore. "
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
                return None
            metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding="utf-8")

        return {
            "keystore_path": str(keystore_path),
            "store_pass": str(metadata.get("store_pass", "")),
            "key_alias": str(metadata.get("key_alias", "motor_local_release")),
            "key_pass": str(metadata.get("store_pass", "")),
        }

    def _find_apk(self, project_dir: Path, mode: str) -> Path | None:
        apk_dir = project_dir / "app" / "build" / "outputs" / "apk"
        expected = apk_dir / mode / f"app-{mode}.apk"
        return self._find_android_artifact(apk_dir, expected, "*.apk", mode)

    def _find_aab(self, project_dir: Path, mode: str) -> Path | None:
        bundle_dir = project_dir / "app" / "build" / "outputs" / "bundle"
        expected = bundle_dir / mode / f"app-{mode}.aab"
        return self._find_android_artifact(bundle_dir, expected, "*.aab", mode)

    def _find_android_artifact(
        self,
        output_dir: Path,
        expected: Path,
        pattern: str,
        mode: str,
    ) -> Path | None:
        if expected.is_file():
            return expected
        if not output_dir.exists():
            return None
        candidates = [
            path
            for path in output_dir.rglob(pattern)
            if path.is_file() and mode.lower() in path.name.lower()
        ]
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda path: (-path.stat().st_mtime_ns, path.as_posix()),
        )[0]

    def _copy_android_artifact(
        self,
        ctx: BuildContext,
        source: Path,
        output_dir: Path,
        kind: str,
    ) -> Path:
        dest_name = self._artifact_dest_name(ctx, source)
        dest = output_dir / dest_name
        if dest.exists() and dest.is_dir():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        ctx.add_artifact(
            str(dest.relative_to(ctx.project_root)),
            kind,
            dest.stat().st_size,
        )
        return dest

    def _artifact_dest_name(self, ctx: BuildContext, source: Path) -> str:
        if ctx._artifact_filename and Path(ctx._artifact_filename).suffix == source.suffix:
            return ctx._artifact_filename
        return source.name

    def _add_project_artifacts(
        self, ctx: BuildContext, project_dir: Path,
    ) -> None:
        ctx.add_artifact(
            str(project_dir.relative_to(ctx.project_root)),
            "android_project",
        )
