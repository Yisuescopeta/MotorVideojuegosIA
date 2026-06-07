"""Windows platform exporter using PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from engine.export.build_context import BuildContext
from engine.export.content_pack import build_content_pack
from engine.export.platform_exporter import PlatformExporter
from engine.export.toolchain import resolve_pyinstaller
from engine.utils.device_profiles import resolve_window_config


class WindowsExporter(PlatformExporter):
    platform = "windows"

    def validate_environment(self) -> dict[str, Any]:
        pyinstaller = resolve_pyinstaller()
        return {
            "platform": "windows",
            "pyinstaller_available": pyinstaller["pyinstaller_available"],
            "pyinstaller_path": pyinstaller["pyinstaller_path"],
            "pyinstaller_module_available": pyinstaller["pyinstaller_module_available"],
            "pyinstaller_resolution": pyinstaller["pyinstaller_resolution"],
            "pyinstaller_command": list(pyinstaller["pyinstaller_command"]),
            "python": sys.executable,
        }

    def export(self, ctx: BuildContext) -> bool:
        env = self.validate_environment()
        if not env["pyinstaller_available"]:
            ctx.add_error(
                "TOOLCHAIN_UNAVAILABLE: PyInstaller not found. "
                f"Install with: {sys.executable} -m pip install pyinstaller"
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

        try:
            result = subprocess.run(
                [
                    *env["pyinstaller_command"],
                    "--distpath", str(output),
                    "--workpath", str(staging / "pyi_work"),
                    "--noconfirm",
                    str(spec_path),
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(staging),
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

        exe_name = f"{_safe_exe_name(ctx.preset.display_name or ctx.preset.name)}.exe"
        exe_candidates = list(output.rglob(exe_name))
        if not exe_candidates:
            exe_candidates = list(output.rglob("*.exe"))

        if not exe_candidates:
            ctx.add_warning(
                "No .exe found in output directory after PyInstaller build."
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
        exe_dir = exe_path.parent
        self._install_runtime_files(staging, exe_dir, ctx)

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
            "window": resolve_window_config(ctx.preset.window),
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
        hooks_src = str(self._write_pyinstaller_hooks(staging).as_posix())
        console_enabled = (
            ctx.preset.mode == "debug"
            or ctx.preset.include_debug_tools
            or bool(ctx.preset.extra.get("console", False))
        )

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
            "import site\n"
            "import sysconfig\n"
            "from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules\n"
            "\n"
            "runtime_pathex = []\n"
            "for _path in [\n"
            "    sysconfig.get_paths().get('purelib'),\n"
            "    sysconfig.get_paths().get('platlib'),\n"
            "    *site.getsitepackages(),\n"
            f"    r'{project_src}',\n"
            "]:\n"
            "    if _path and _path not in runtime_pathex:\n"
            "        runtime_pathex.append(_path)\n"
            "\n"
            "raylib_hiddenimports = collect_submodules('raylib')\n"
            "raylib_binaries = collect_dynamic_libs('raylib')\n"
            "\n"
            "a = Analysis(\n"
            f"    [r'{runtime_src}'],\n"
            "    pathex=runtime_pathex,\n"
            "    binaries=raylib_binaries,\n"
            "    datas=[\n"
            f"{datas_lines}"
            "    ],\n"
            "    hiddenimports=[\n"
            "        'engine', 'engine.api', 'engine.runtime',\n"
            "        'engine.scenes', 'engine.ecs', 'engine.components',\n"
            "        'engine.systems', 'engine.events', 'engine.physics',\n"
            "        'engine.levels', 'engine.project', 'engine.config',\n"
            "        'pyray', 'raylib',\n"
            "        *raylib_hiddenimports,\n"
            "    ],\n"
            f"    hookspath=[r'{hooks_src}'],\n"
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
            f"    console={console_enabled!r},\n"
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

    def _write_pyinstaller_hooks(self, staging: Path) -> Path:
        hooks_dir = staging / "pyinstaller_hooks"
        pre_find_dir = hooks_dir / "pre_find_module_path"
        pre_find_dir.mkdir(parents=True, exist_ok=True)
        (pre_find_dir / "hook-pyray.py").write_text(
            (
                "from pathlib import Path\n"
                "import site\n"
                "import sysconfig\n"
                "from PyInstaller.utils.hooks import logger\n"
                "\n"
                "\n"
                "def _candidate_paths():\n"
                "    seen = []\n"
                "    for path in [\n"
                "        sysconfig.get_paths().get('purelib'),\n"
                "        sysconfig.get_paths().get('platlib'),\n"
                "        *site.getsitepackages(),\n"
                "    ]:\n"
                "        if path and path not in seen:\n"
                "            seen.append(path)\n"
                "            yield path\n"
                "\n"
                "\n"
                "def pre_find_module_path(api):\n"
                "    for path in _candidate_paths():\n"
                "        root = Path(path)\n"
                "        if (root / 'pyray' / '__init__.py').exists() or (root / 'pyray.py').exists():\n"
                "            logger.debug('pyray: retargeting to site package dir %r', path)\n"
                "            api.search_dirs = [path]\n"
                "            return\n"
            ),
            encoding="utf-8",
        )
        return hooks_dir

    def _run_smoke_test(self, ctx: BuildContext, exe_path: Path) -> bool:
        try:
            result = subprocess.run(
                [str(exe_path), "--smoke-test"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(exe_path.parent),
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
        """Copy runtime_config.json, game.manifest.json, game.pak to executable dir."""
        for src_name in ("runtime_config.json", "game.manifest.json", "game.pak"):
            src = staging / src_name
            if src.exists():
                shutil.copy2(src, exe_dir / src_name)
                ctx.add_warning(f"Installed {src_name} to executable directory.")


def _safe_exe_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    return safe or "Game"
