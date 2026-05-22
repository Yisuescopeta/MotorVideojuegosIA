"""Android platform exporter using Gradle + Android SDK."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from engine.export.build_context import BuildContext
from engine.export.content_pack import build_content_pack
from engine.export.platform_exporter import PlatformExporter

_PLACEHOLDERS = {
    "{{APPLICATION_ID}}": "application_id",
    "{{DISPLAY_NAME}}": "display_name",
    "{{VERSION_NAME}}": "version_name",
    "{{VERSION_CODE}}": "version_code",
    "{{MIN_SDK}}": "min_sdk",
    "{{TARGET_SDK}}": "target_sdk",
    "{{ORIENTATION}}": "orientation",
    "{{ENTRY_SCENE}}": "entry_scene",
}


class AndroidExporter(PlatformExporter):
    platform = "android"

    def validate_environment(self) -> dict[str, Any]:
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
        java_path = shutil.which("java") or shutil.which("java.exe") or ""
        gradle_path = shutil.which("gradle") or shutil.which("gradle.bat") or ""
        return {
            "platform": "android",
            "android_sdk_available": bool(android_home),
            "android_home": android_home,
            "java_available": bool(java_path),
            "java_path": java_path,
            "gradle_available": bool(gradle_path),
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

        self._write_runtime_config(ctx, staging)

        project_dir = self._generate_android_project(ctx, staging)

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
                "Gradle not found in PATH. Android project generated but not built. "
                "Install Gradle or use the generated project directly in Android Studio."
            )
            return False

        if ctx.preset.mode == "release":
            keystore = ctx.preset.extra.get("keystore_path", "")
            if keystore:
                ok = self._build_release(ctx, project_dir, env)
            else:
                ctx.add_warning(
                    "No keystore configured for release build. "
                    "Set keystore_path in preset extra. Building unsigned release."
                )
                ok = self._run_gradle_build(ctx, project_dir, "assembleRelease")
        else:
            ok = self._run_gradle_build(ctx, project_dir, "assembleDebug")

        if not ok:
            return False

        apk = self._find_apk(project_dir)
        if apk:
            dest_name = ctx._artifact_filename if ctx._artifact_filename else apk.name
            dest = output / dest_name
            shutil.copy2(apk, dest)
            ctx.add_artifact(
                str(dest.relative_to(ctx.project_root)),
                "apk",
                dest.stat().st_size,
            )

        if ctx.preset.mode == "release":
            aab = self._find_aab(project_dir)
            if aab:
                dest_name = ctx._artifact_filename if ctx._artifact_filename else aab.name
                dest = output / dest_name
                shutil.copy2(aab, dest)
                ctx.add_artifact(
                    str(dest.relative_to(ctx.project_root)),
                    "aab",
                    dest.stat().st_size,
                )

        return not ctx.has_errors

    def _write_runtime_config(self, ctx: BuildContext, staging: Path) -> None:
        config = {
            "schema_version": 1,
            "entry_scene": ctx.preset.entry_scene,
            "project_name": ctx.preset.display_name or ctx.preset.name,
            "version": ctx.preset.version_name,
            "window": ctx.preset.window or {
                "width": 1280, "height": 720,
                "resizable": True, "fullscreen": False,
            },
            "debug_tools": ctx.preset.include_debug_tools,
        }
        (staging / "runtime_config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

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
                    for placeholder, value in replacements.items():
                        content = content.replace(placeholder, value)
                    file_path.write_text(content, encoding="utf-8")
                except Exception:
                    pass

        return project_dir

    def _build_replacements(self, ctx: BuildContext) -> dict[str, str]:
        return {
            "{{APPLICATION_ID}}": ctx.preset.application_id or "com.motor.game",
            "{{DISPLAY_NAME}}": ctx.preset.display_name or ctx.preset.name,
            "{{VERSION_NAME}}": ctx.preset.version_name,
            "{{VERSION_CODE}}": str(ctx.preset.version_code),
            "{{MIN_SDK}}": str(ctx.preset.min_sdk),
            "{{TARGET_SDK}}": str(ctx.preset.target_sdk),
            "{{ORIENTATION}}": ctx.preset.orientation or "landscape",
            "{{ENTRY_SCENE}}": ctx.preset.entry_scene,
        }

    def _run_gradle_build(
        self, ctx: BuildContext, project_dir: Path, task: str,
        extra_env: dict[str, str] | None = None,
    ) -> bool:
        gradle = shutil.which("gradle") or shutil.which("gradle.bat")
        if not gradle:
            ctx.add_error("Gradle not found in PATH.")
            return False

        env = os.environ.copy()
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
        if android_home:
            env["ANDROID_HOME"] = android_home
        if extra_env:
            env.update(extra_env)

        try:
            result = subprocess.run(
                [gradle, task],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(project_dir),
                env=env,
            )
            if result.returncode != 0:
                ctx.add_error(
                    f"Gradle {task} failed (code {result.returncode}): "
                    f"{result.stderr[:500]}"
                )
                return False
        except subprocess.TimeoutExpired:
            ctx.add_error(f"Gradle {task} timed out after 600s")
            return False
        except Exception as exc:
            ctx.add_error(f"Gradle {task} failed: {exc}")
            return False

        return True

    def _build_release(
        self, ctx: BuildContext, project_dir: Path, env: dict[str, Any],
    ) -> bool:
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
            return False

        keystore_path = Path(keystore)
        if not keystore_path.is_absolute():
            keystore_path = ctx.project_root / keystore_path

        if not keystore_path.exists():
            ctx.add_error(
                "ANDROID_KEYSTORE_NOT_FOUND: Keystore not found at configured path. "
                "Create a keystore or update keystore_path."
            )
            return False

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
            content = content.replace(
                "signingConfig signingConfigs.debug",
                "signingConfig signingConfigs.release",
            )
            gradle_path.write_text(content, encoding="utf-8")

        # Copy keystore to project root so relative path resolves
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

    def _find_apk(self, project_dir: Path) -> Path | None:
        apk_dir = project_dir / "app" / "build" / "outputs" / "apk"
        if not apk_dir.exists():
            return None
        apks = list(apk_dir.rglob("*.apk"))
        return apks[0] if apks else None

    def _find_aab(self, project_dir: Path) -> Path | None:
        bundle_dir = project_dir / "app" / "build" / "outputs" / "bundle"
        if not bundle_dir.exists():
            return None
        aabs = list(bundle_dir.rglob("*.aab"))
        return aabs[0] if aabs else None

    def _add_project_artifacts(
        self, ctx: BuildContext, project_dir: Path,
    ) -> None:
        ctx.add_artifact(
            str(project_dir.relative_to(ctx.project_root)),
            "android_project",
        )
