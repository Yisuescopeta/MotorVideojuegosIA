"""iOS platform exporter. Requires macOS + Xcode."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from engine.export.build_context import BuildContext
from engine.export.content_pack import build_content_pack
from engine.export.platform_exporter import PlatformExporter
from engine.utils.device_profiles import resolve_window_config

IS_MACOS = sys.platform == "darwin"


class IOSExporter(PlatformExporter):
    platform = "ios"

    def validate_environment(self) -> dict[str, Any]:
        xcodebuild = shutil.which("xcodebuild")
        xcrun = shutil.which("xcrun")
        xcode_version = ""
        if xcodebuild and IS_MACOS:
            try:
                result = subprocess.run(
                    [xcodebuild, "-version"],
                    capture_output=True, text=True, timeout=15,
                )
                xcode_version = result.stdout.strip().split("\n")[0] if result.stdout else ""
            except Exception:
                pass
        return {
            "platform": "ios",
            "is_macos": IS_MACOS,
            "xcode_available": xcodebuild is not None,
            "xcode_version": xcode_version,
            "xcrun_available": xcrun is not None,
            "python": sys.executable,
        }

    def export(self, ctx: BuildContext) -> bool:
        env = self.validate_environment()

        if not IS_MACOS:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: iOS export requires macOS with Xcode installed. "
                "Current OS: " + sys.platform + ". "
                "Build on a Mac or use a CI service with macOS runners (e.g., GitHub Actions macos-latest)."
            )
            return False

        if not env["xcode_available"]:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: Xcode not found. "
                "Install Xcode from the Mac App Store and run: "
                "sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer"
            )
            return False

        ctx.add_warning(
            f"Xcode version: {env.get('xcode_version', 'unknown')}"
        )

        staging = ctx.staging_dir
        staging.mkdir(parents=True, exist_ok=True)
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

        project_dir = self._generate_ios_project(ctx, staging)

        assets_src = staging / "content"
        assets_dst = project_dir / "assets"
        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)

        manifest_src = staging / "game.manifest.json"
        if manifest_src.exists():
            shutil.copy2(manifest_src, project_dir / "game.manifest.json")

        runtime_config_src = staging / "runtime_config.json"
        if runtime_config_src.exists():
            shutil.copy2(runtime_config_src, project_dir / "runtime_config.json")

        ctx.add_artifact(
            str(project_dir.relative_to(ctx.project_root)),
            "ios_project",
        )
        ctx.add_warning(
            "iOS project generated but not compiled. "
            "Open the project in Xcode on macOS to build and sign for iOS devices. "
            "Requires Apple Developer account for signing."
        )

        return not ctx.has_errors

    def _write_runtime_config(self, ctx: BuildContext, staging: Path) -> None:
        config = {
            "schema_version": 1,
            "entry_scene": ctx.preset.entry_scene,
            "project_name": ctx.preset.display_name or ctx.preset.name,
            "version": ctx.preset.version_name,
            "window": resolve_window_config(ctx.preset.window),
            "debug_tools": ctx.preset.include_debug_tools,
        }
        (staging / "runtime_config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _generate_ios_project(
        self, ctx: BuildContext, staging: Path,
    ) -> Path:
        template_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "platforms" / "ios" / "template"
        )
        project_dir = staging / "ios_project"

        if template_dir.exists():
            shutil.copytree(template_dir, project_dir, dirs_exist_ok=True)
        else:
            project_dir.mkdir(parents=True, exist_ok=True)
            ctx.add_warning(
                "iOS template not found at platforms/ios/template/. "
                "Generating minimal project structure."
            )

        replacements = {
            "{{APPLICATION_ID}}": ctx.preset.application_id or "com.motor.game",
            "{{DISPLAY_NAME}}": ctx.preset.display_name or ctx.preset.name,
            "{{VERSION_NAME}}": ctx.preset.version_name,
            "{{VERSION_CODE}}": str(ctx.preset.version_code),
        }

        for file_path in project_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in (".plist", ".xml"):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    for placeholder, value in replacements.items():
                        content = content.replace(placeholder, value)
                    file_path.write_text(content, encoding="utf-8")
                except Exception:
                    pass

        info_plist = project_dir / "Info.plist"
        if info_plist.exists():
            ctx.add_warning(f"Info.plist generated at {info_plist}")

        return project_dir
