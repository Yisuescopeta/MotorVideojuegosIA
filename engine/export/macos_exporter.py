"""macOS platform exporter using PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from engine.export.build_context import BuildContext
from engine.export.content_pack import build_content_pack
from engine.export.platform_exporter import PlatformExporter

IS_MACOS = sys.platform == "darwin"


class MacOSExporter(PlatformExporter):
    platform = "macos"

    def validate_environment(self) -> dict[str, Any]:
        pyinstaller = shutil.which("pyinstaller")
        xcodebuild = shutil.which("xcodebuild")
        xcode_version = ""
        if xcodebuild and IS_MACOS:
            try:
                result = subprocess.run(
                    ["xcodebuild", "-version"],
                    capture_output=True, text=True, timeout=15,
                )
                xcode_version = result.stdout.strip().split("\n")[0]
            except Exception:
                pass
        return {
            "platform": "macos",
            "is_macos": IS_MACOS,
            "pyinstaller_available": pyinstaller is not None,
            "pyinstaller_path": pyinstaller or "",
            "xcode_available": xcodebuild is not None,
            "xcode_version": xcode_version,
            "python": sys.executable,
        }

    def export(self, ctx: BuildContext) -> bool:
        env = self.validate_environment()

        if not IS_MACOS:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: macOS export requires a macOS host "
                "with Xcode installed. Current OS: " + sys.platform + "."
            )
            return False

        if not env["pyinstaller_available"]:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: PyInstaller not found. "
                "Install with: pip install pyinstaller"
            )
            return False

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

        spec_path = self._write_export_spec(ctx, staging)

        pyinstaller: str = shutil.which("pyinstaller")  # type: ignore[assignment]
        try:
            result = subprocess.run(
                [
                    pyinstaller,
                    "--distpath", str(output),
                    "--workpath", str(staging / "pyi_work"),
                    "--specpath", str(staging),
                    "--noconfirm",
                    "--windowed",
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(ctx.project_root),
            )
            if result.returncode != 0:
                ctx.add_error(
                    f"PyInstaller failed (code {result.returncode}): "
                    f"{result.stderr[:500]}"
                )
                return False
        except subprocess.TimeoutExpired:
            ctx.add_error("PyInstaller timed out after 300s")
            return False
        except Exception as exc:
            ctx.add_error(f"PyInstaller execution failed: {exc}")
            return False

        bundle_mode = getattr(ctx.preset, "bundle_mode", "packed")
        if bundle_mode != "packed":
            content_dst = output / ctx.preset.display_name / "content"
            content_src = staging / "content"
            if content_src.exists():
                if content_dst.exists():
                    shutil.rmtree(content_dst)
                shutil.copytree(content_src, content_dst)

        manifest_src = staging / "game.manifest.json"
        if manifest_src.exists():
            dst_dir = output / ctx.preset.display_name
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(manifest_src, dst_dir / "game.manifest.json")
            ctx.add_artifact(
                str((dst_dir / "game.manifest.json").relative_to(ctx.project_root)),
                "content_manifest",
            )

        runtime_config_src = staging / "runtime_config.json"
        if runtime_config_src.exists():
            dst_dir = output / ctx.preset.display_name
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime_config_src, dst_dir / "runtime_config.json")
            ctx.add_artifact(
                str((dst_dir / "runtime_config.json").relative_to(ctx.project_root)),
                "runtime_config",
            )

        pak_src = staging / "game.pak"
        if pak_src.exists():
            dst_dir = output / ctx.preset.display_name
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pak_src, dst_dir / "game.pak")
            ctx.add_artifact(
                str((dst_dir / "game.pak").relative_to(ctx.project_root)),
                "content_pack",
            )

        exe_name = _safe_exe_name(ctx.preset.display_name or ctx.preset.name)
        exe_candidates = _find_macos_executable(output, exe_name)

        if not exe_candidates:
            ctx.add_warning(
                "No macOS executable found in output directory after PyInstaller build."
            )
            return not ctx.has_errors

        exe_path = exe_candidates[0]
        size = exe_path.stat().st_size
        ctx.add_artifact(
            str(exe_path.relative_to(ctx.project_root)),
            "executable",
            size,
        )

        # Post-build: install runtime files to executable directory
        # For .app bundles, place files in Contents/Resources/
        if exe_path.suffix == ".app":
            runtime_dir = exe_path / "Contents" / "Resources"
        else:
            runtime_dir = exe_path.parent
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self._install_runtime_files(staging, runtime_dir, ctx)

        if not self._run_smoke_test(ctx, exe_path):
            return False

        return not ctx.has_errors

    def _write_runtime_config(self, ctx: BuildContext, staging: Path) -> None:
        import json
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

    def _write_export_spec(self, ctx: BuildContext, staging: Path) -> Path:
        runtime_dir = Path(__file__).resolve().parent.parent / "runtime"
        runtime_entry = runtime_dir / "exported_game.py"

        exe_name = _safe_exe_name(ctx.preset.display_name or ctx.preset.name)
        project_src = str(ctx.project_root.as_posix())
        runtime_src = str(runtime_entry.as_posix())
        runtime_config_src = str((staging / "runtime_config.json").as_posix())
        manifest_src = str((staging / "game.manifest.json").as_posix())
        content_src = str((staging / "content").as_posix())
        pak_src = str((staging / "game.pak").as_posix())

        bundle_mode = getattr(ctx.preset, "bundle_mode", "packed")
        if bundle_mode == "directory":
            datas_lines = (
                f"        (r'{runtime_config_src}', '.'),\n"
                f"        (r'{manifest_src}', '.'),\n"
                f"        (r'{content_src}', 'content'),\n"
            )
        else:
            datas_lines = (
                f"        (r'{runtime_config_src}', '.'),\n"
                f"        (r'{manifest_src}', '.'),\n"
                f"        (r'{pak_src}', '.'),\n"
            )

        spec = (
            "# -*- mode: python ; coding: utf-8 -*-\n"
            f"# Auto-generated export spec for {ctx.preset.name}\n"
            "a = Analysis(\n"
            f"    [r'{runtime_src}'],\n"
            f"    pathex=[r'{project_src}'],\n"
            "    binaries=[],\n"
            "    datas=[\n"
            f"{datas_lines}"
            "    ],\n"
            "    hiddenimports=[\n"
            "        'engine', 'engine.api', 'engine.runtime',\n"
            "        'engine.scenes', 'engine.ecs', 'engine.components',\n"
            "        'engine.systems', 'engine.events', 'engine.physics',\n"
            "        'engine.levels', 'engine.project', 'engine.config',\n"
            "    ],\n"
            "    hookspath=[],\n"
            "    hooksconfig={},\n"
            "    runtime_hooks=[],\n"
            "    excludes=[\n"
            "        'engine.editor', 'engine.inspector', 'tools',\n"
            "        'tests', 'docs', 'motor', 'main',\n"
            "    ],\n"
            "    noarchive=False,\n"
            "    optimize=0,\n"
            ")\n"
            "pyz = PYZ(a.pure)\n"
            "exe = EXE(\n"
            "    pyz,\n"
            "    a.scripts,\n"
            "    a.binaries,\n"
            "    a.datas,\n"
            f"    name='{exe_name}',\n"
            "    debug=False,\n"
            "    bootloader_ignore_signals=False,\n"
            "    strip=False,\n"
            "    upx=True,\n"
            "    upx_exclude=[],\n"
            "    runtime_tmpdir=None,\n"
            "    console=False,\n"
            "    disable_windowed_traceback=False,\n"
            "    argv_emulation=False,\n"
            "    target_arch=None,\n"
            "    codesign_identity=None,\n"
            "    entitlements_file=None,\n"
            ")\n"
        )
        spec_path = staging / f"{exe_name}.spec"
        spec_path.write_text(spec, encoding="utf-8")
        return spec_path

    def _run_smoke_test(self, ctx: BuildContext, exe_path: Path) -> bool:
        try:
            cmd = [str(exe_path), "--smoke-test"]
            if exe_path.suffix == ".app":
                cmd = ["open", str(exe_path), "--args", "--smoke-test"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(exe_path.parent if exe_path.suffix != ".app" else exe_path.parent.parent),
            )
        except subprocess.TimeoutExpired:
            ctx.add_error("Smoke test timed out after 60s")
            return False
        except Exception as exc:
            ctx.add_error(f"Smoke test failed to start: {exc}")
            return False
        if result.returncode != 0:
            ctx.add_error(
                f"Smoke test failed (code {result.returncode}): "
                f"{(result.stderr or result.stdout)[:500]}"
            )
            return False
        ctx.add_warning("Smoke test passed.")
        return True

    def _install_runtime_files(
        self, staging: Path, exe_dir: Path, ctx: BuildContext,
    ) -> None:
        for src_name in ("runtime_config.json", "game.manifest.json", "game.pak"):
            src = staging / src_name
            if src.exists():
                shutil.copy2(src, exe_dir / src_name)
                ctx.add_warning(f"Installed {src_name} to executable directory.")


def _safe_exe_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    return safe or "Game"


def _find_macos_executable(output: Path, exe_name: str) -> list[Path]:
    app_candidates = list(output.rglob(f"{exe_name}.app"))
    if app_candidates:
        return app_candidates
    bin_candidates = list(output.rglob(exe_name))
    return [p for p in bin_candidates if p.is_file() and not p.suffix]
