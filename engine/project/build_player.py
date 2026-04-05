from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from engine.project.build_prebuild import BuildPrebuildService, PrebuildDiagnostic, PrebuildReport
from engine.project.build_settings import BuildManifest, BuildSettings, BuildTargetPlatform
from engine.runtime import RuntimeManifest, runtime_manifest_from_build_manifest

if TYPE_CHECKING:
    from engine.assets.asset_service import AssetService
    from engine.project.project_service import ProjectService


@dataclass(frozen=True)
class BuildPlayerOptions:
    output_root: str = ""
    generated_at_utc: str = ""
    clean_output: bool = True


@dataclass(frozen=True)
class BuildReportDiagnostic:
    severity: str
    code: str
    message: str
    path: str = ""
    stage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "stage": self.stage,
        }


@dataclass(frozen=True)
class BuildReportOutputEntry:
    path: str
    kind: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
        }


@dataclass
class BuildReport:
    status: str
    target_platform: str
    output_path: str
    duration_seconds: float
    startup_scene: str
    included_scenes: tuple[str, ...] = ()
    included_asset_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[BuildReportDiagnostic] = field(default_factory=list)
    errors: list[BuildReportDiagnostic] = field(default_factory=list)
    output_summary: list[BuildReportOutputEntry] = field(default_factory=list)
    top_assets_by_size: list[dict[str, Any]] = field(default_factory=list)
    references: dict[str, str] = field(default_factory=dict)
    generated_at_utc: str = ""
    development_build: bool = False
    development_extras: tuple[str, ...] = ()
    report_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        ordered_counts = {
            key: int(self.included_asset_counts.get(key, 0))
            for key in ("scenes", "prefabs", "scripts", "assets", "metadata")
        }
        ordered_references = {
            key: str(self.references.get(key, ""))
            for key in (
                "runtime_manifest",
                "build_manifest",
                "prebuild_report",
                "asset_build_report",
                "content_bundle",
                "bundle_report",
            )
            if str(self.references.get(key, "")).strip()
        }
        payload = {
            "status": self.status,
            "target_platform": self.target_platform,
            "output_path": self.output_path,
            "duration_seconds": round(float(self.duration_seconds), 6),
            "startup_scene": self.startup_scene,
            "included_scenes": list(self.included_scenes),
            "included_asset_counts": ordered_counts,
            "warnings": [item.to_dict() for item in self.warnings],
            "errors": [item.to_dict() for item in self.errors],
            "output_summary": [item.to_dict() for item in self.output_summary],
            "top_assets_by_size": [dict(item) for item in self.top_assets_by_size],
            "references": ordered_references,
            "generated_at_utc": self.generated_at_utc,
            "development_build": self.development_build,
            "development_extras": list(self.development_extras),
        }
        if self.report_path:
            payload["report_path"] = self.report_path
        return payload


@dataclass(frozen=True)
class _PackagingRequest:
    project_root: str
    repo_root: str
    output_root: str
    executable_name: str
    development_build: bool
    include_logs: bool


@dataclass(frozen=True)
class _PackagingResult:
    executable_path: str


class _BuildPlayerFailure(RuntimeError):
    def __init__(self, *diagnostics: BuildReportDiagnostic) -> None:
        self.diagnostics = tuple(diagnostics)
        message = "; ".join(f"{item.code}: {item.message}" for item in diagnostics) or "Build Player failed"
        super().__init__(message)


def _diagnostic_sort_key(item: BuildReportDiagnostic) -> tuple[str, str, str, str]:
    return (
        item.stage.lower(),
        item.path.lower(),
        item.code.lower(),
        item.message.lower(),
    )


class _PyInstallerPackager:
    PLAYER_ENTRYPOINT = "player_main.py"
    SPEC_FILE_NAME = "player_runtime.spec"
    WORK_DIR_NAME = "pyinstaller_player"
    HIDDEN_IMPORTS = (
        "engine",
        "engine.config",
        "engine.core.game",
        "engine.core.engine_state",
        "engine.core.time_manager",
        "engine.core.hot_reload",
        "engine.ecs.entity",
        "engine.ecs.component",
        "engine.ecs.world",
        "engine.components.transform",
        "engine.components.sprite",
        "engine.components.collider",
        "engine.components.charactercontroller2d",
        "engine.components.joint2d",
        "engine.components.rigidbody",
        "engine.components.animator",
        "engine.components.camera2d",
        "engine.components.audiosource",
        "engine.components.inputmap",
        "engine.components.playercontroller2d",
        "engine.components.scriptbehaviour",
        "engine.components.tilemap",
        "engine.components.canvas",
        "engine.systems.render_system",
        "engine.systems.physics_system",
        "engine.systems.collision_system",
        "engine.systems.animation_system",
        "engine.systems.audio_system",
        "engine.systems.input_system",
        "engine.systems.player_controller_system",
        "engine.systems.character_controller_system",
        "engine.systems.script_behaviour_system",
        "engine.systems.selection_system",
        "engine.systems.ui_system",
        "engine.systems.ui_render_system",
        "engine.levels.component_registry",
        "engine.events.event_bus",
        "engine.events.rule_system",
        "engine.scenes.scene",
        "engine.scenes.scene_manager",
        "engine.resources.texture_manager",
        "engine.physics.box2d_backend",
        "engine.runtime",
        "engine.runtime.bootstrap",
        "cli.runtime_runner",
        "cli.headless_game",
        "player_main",
    )

    def package(self, request: _PackagingRequest) -> _PackagingResult:
        import importlib.util

        if importlib.util.find_spec("PyInstaller") is None:
            raise RuntimeError(
                "PyInstaller is not installed in this Python environment. "
                "Run: pip install pyinstaller"
            )

        repo_root = Path(request.repo_root).resolve()
        output_root = Path(request.output_root).resolve()
        output_root.parent.mkdir(parents=True, exist_ok=True)
        work_root = Path(request.project_root).resolve() / ".motor" / "build" / self.WORK_DIR_NAME
        work_root.mkdir(parents=True, exist_ok=True)
        spec_path = work_root / self.SPEC_FILE_NAME
        spec_path.write_text(self._build_spec(request), encoding="utf-8")

        log_path = work_root / "pyinstaller.log"
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            spec_path.as_posix(),
            "--noconfirm",
            "--distpath",
            output_root.parent.as_posix(),
            "--workpath",
            work_root.as_posix(),
        ]
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        combined_log = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        try:
            log_path.write_text(combined_log, encoding="utf-8", errors="replace")
        except Exception:
            pass
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        executable_path = output_root / f"{request.executable_name}.exe"
        if not executable_path.exists():
            raise RuntimeError(f"Packaged executable was not generated: {executable_path.as_posix()}")
        return _PackagingResult(executable_path=executable_path.as_posix())

    def _build_spec(self, request: _PackagingRequest) -> str:
        # The joiner indentation (20 spaces) must match the column of {hidden_imports} in
        # the f-string template so textwrap.dedent removes exactly the right prefix length.
        hidden_imports = ",\n                    ".join(repr(item) for item in self.HIDDEN_IMPORTS)
        console_enabled = "True" if request.development_build and request.include_logs else "False"
        return textwrap.dedent(
            f"""\
            # -*- mode: python ; coding: utf-8 -*-
            import os
            from PyInstaller.utils.hooks import collect_dynamic_libs

            block_cipher = None

            PROJECT_ROOT = {Path(request.repo_root).resolve().as_posix()!r}
            raylib_binaries = collect_dynamic_libs("raylib")

            a = Analysis(
                [os.path.join(PROJECT_ROOT, {self.PLAYER_ENTRYPOINT!r})],
                pathex=[PROJECT_ROOT],
                binaries=raylib_binaries,
                datas=[],
                hiddenimports=[
                    {hidden_imports}
                ],
                hookspath=[],
                hooksconfig={{}},
                runtime_hooks=[],
                excludes=["bandit", "mypy", "ruff", "pip_audit", "pytest"],
                win_no_prefer_redirects=False,
                win_private_assemblies=False,
                cipher=block_cipher,
                noarchive=False,
            )

            pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

            exe = EXE(
                pyz,
                a.scripts,
                [],
                exclude_binaries=True,
                name={request.executable_name!r},
                debug=False,
                bootloader_ignore_signals=False,
                strip=False,
                upx=True,
                console={console_enabled},
                disable_windowed_traceback=False,
            )

            coll = COLLECT(
                exe,
                a.binaries,
                a.zipfiles,
                a.datas,
                strip=False,
                upx=True,
                upx_exclude=[],
                name={Path(request.output_root).name!r},
            )
            """
        )


class BuildPlayerService:
    REPORT_FILE_NAME = "build_report.json"
    LAST_REPORT_FILE_NAME = "player_build_report.json"
    RUNTIME_DIR = "runtime"
    METADATA_DIR = "runtime/metadata"
    CONTENT_DIR = "runtime/content"
    DEV_DIR = "runtime/dev"
    IMPORTED_ARTIFACTS_DIR = "runtime/metadata/imported_assets"
    PREBUILD_REPORT_FILE_NAME = "prebuild_content_report.json"
    ASSET_BUILD_REPORT_FILE_NAME = "asset_build_report.json"
    CONTENT_BUNDLE_FILE_NAME = "content_bundle.json"
    BUNDLE_REPORT_FILE_NAME = "bundle_report.json"
    DEVELOPMENT_OPTIONS_FILE_NAME = "development_options.json"

    def __init__(
        self,
        project_service: "ProjectService",
        asset_service: "AssetService | None" = None,
        prebuild_service: BuildPrebuildService | None = None,
        *,
        packager: Any | None = None,
        timer: Callable[[], float] | None = None,
        repo_root: str | os.PathLike[str] | None = None,
    ) -> None:
        from engine.assets.asset_service import AssetService

        self._project_service = project_service
        self._asset_service = asset_service or AssetService(project_service)
        self._prebuild_service = prebuild_service or BuildPrebuildService(project_service, self._asset_service)
        self._packager = packager or _PyInstallerPackager()
        self._timer = timer or time.perf_counter
        self._repo_root = Path(repo_root).expanduser().resolve() if repo_root is not None else Path(__file__).resolve().parents[2]

    def build_player(self, options: BuildPlayerOptions | None = None) -> BuildReport:
        options = options or BuildPlayerOptions()
        start = float(self._timer())
        generated_at_utc = str(options.generated_at_utc or "").strip()
        build_root = self._project_service.get_project_path("build")
        output_root_path: Path | None = None
        warnings: list[BuildReportDiagnostic] = []
        target_platform = ""
        startup_scene = ""
        development_build = False

        try:
            try:
                settings = self._project_service.load_build_settings(strict=True)
            except Exception as exc:
                raise _BuildPlayerFailure(
                    self._diagnostic(
                        "error",
                        "build_settings.invalid",
                        f"Build settings could not be loaded: {exc}",
                        path=self._project_service.to_relative_path(self._project_service.get_build_settings_path()),
                        stage="build_settings",
                    )
                ) from exc
            generated_at_utc = generated_at_utc or self._project_service.generate_build_manifest(settings).generated_at_utc
            build_manifest = self._project_service.generate_build_manifest(settings, generated_at_utc=generated_at_utc)
            output_root_path = self._resolve_output_root(options.output_root, build_manifest)
            target_platform = settings.target_platform.value
            startup_scene = settings.startup_scene
            development_build = settings.development_build

            if settings.target_platform is not BuildTargetPlatform.WINDOWS_DESKTOP:
                raise _BuildPlayerFailure(
                    self._diagnostic(
                        "error",
                        "build_player.unsupported_target",
                        "Build Player currently supports only windows_desktop.",
                        stage="build_settings",
                    )
                )

            prebuild_report = self._prebuild_service.generate_report(generated_at_utc=generated_at_utc)
            self._prebuild_service.save_report(prebuild_report)
            warnings.extend(self._convert_prebuild_diagnostics(prebuild_report.warnings))
            if not prebuild_report.valid:
                raise _BuildPlayerFailure(*self._convert_prebuild_diagnostics(prebuild_report.blocking_errors))

            if options.clean_output and output_root_path.exists():
                shutil.rmtree(output_root_path)

            asset_build_report = self._asset_service.build_asset_artifacts()
            bundle_report = self._asset_service.create_bundle()
            packaging_result = self._packager.package(
                _PackagingRequest(
                    project_root=self._project_service.project_root.as_posix(),
                    repo_root=self._repo_root.as_posix(),
                    output_root=output_root_path.as_posix(),
                    executable_name=settings.output_name,
                    development_build=settings.development_build,
                    include_logs=settings.include_logs,
                )
            )

            content_root = output_root_path / self.CONTENT_DIR
            metadata_root = output_root_path / self.METADATA_DIR
            content_root.mkdir(parents=True, exist_ok=True)
            metadata_root.mkdir(parents=True, exist_ok=True)

            self._copy_selected_content(prebuild_report, content_root)
            _, _, packaged_bundle_report = self._write_packaged_asset_metadata(
                prebuild_report=prebuild_report,
                asset_build_report=asset_build_report,
                bundle_report=bundle_report,
                metadata_root=metadata_root,
                generated_at_utc=generated_at_utc,
            )

            runtime_manifest = runtime_manifest_from_build_manifest(
                build_manifest,
                generated_at_utc=generated_at_utc,
                startup_scene=settings.startup_scene,
                selected_content_summary={
                    "scenes": len(prebuild_report.selected_content.scenes),
                    "prefabs": len(prebuild_report.selected_content.prefabs),
                    "scripts": len(prebuild_report.selected_content.scripts),
                    "assets": len(prebuild_report.selected_content.assets),
                    "metadata": len(prebuild_report.selected_content.metadata),
                },
            )
            return self._finalize_success(
                settings=settings,
                build_manifest=build_manifest,
                prebuild_report=prebuild_report,
                runtime_manifest=runtime_manifest,
                packaged_bundle_report=packaged_bundle_report,
                executable_path=Path(packaging_result.executable_path),
                output_root=output_root_path,
                build_root=build_root,
                warnings=warnings,
                generated_at_utc=generated_at_utc,
                started_at=start,
            )
        except _BuildPlayerFailure as exc:
            errors = sorted(list(exc.diagnostics), key=_diagnostic_sort_key)
        except subprocess.CalledProcessError as exc:
            stderr_text = (getattr(exc, "stderr", None) or "").strip()
            snippet = stderr_text[-400:] if len(stderr_text) > 400 else stderr_text
            msg = f"PyInstaller packaging failed (exit code {exc.returncode})."
            if snippet:
                msg += f" Details: {snippet}"
            errors = [
                self._diagnostic(
                    "error",
                    "build_player.packaging_failed",
                    msg,
                    stage="packaging",
                )
            ]
        except Exception as exc:
            errors = [
                self._diagnostic(
                    "error",
                    "build_player.unexpected_error",
                    f"Build player failed unexpectedly: {exc}",
                    stage="build_player",
                )
            ]

        report = BuildReport(
            status="failed",
            target_platform=target_platform,
            output_path="" if output_root_path is None else output_root_path.as_posix(),
            duration_seconds=self._timer() - start,
            startup_scene=startup_scene,
            warnings=sorted(warnings, key=_diagnostic_sort_key),
            errors=errors,
            generated_at_utc=generated_at_utc,
            development_build=development_build,
        )
        self._write_last_report(report, build_root)
        return report

    def _resolve_output_root(self, override: str, build_manifest: BuildManifest) -> Path:
        output_root = str(override or "").strip()
        if not output_root:
            return self._project_service.resolve_path(build_manifest.output.output_root)
        candidate = Path(output_root).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return self._project_service.resolve_path(candidate.as_posix())

    def _convert_prebuild_diagnostics(self, diagnostics: list[PrebuildDiagnostic]) -> list[BuildReportDiagnostic]:
        return sorted(
            [
                BuildReportDiagnostic(
                    severity=item.severity,
                    code=item.code,
                    message=item.message,
                    path=item.path or item.reference or item.source_file,
                    stage=item.stage,
                )
                for item in diagnostics
            ],
            key=_diagnostic_sort_key,
        )

    def _diagnostic(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        path: str = "",
        stage: str = "",
    ) -> BuildReportDiagnostic:
        return BuildReportDiagnostic(
            severity=severity,
            code=code,
            message=message,
            path=path,
            stage=stage,
        )

    def _copy_selected_content(self, prebuild_report: PrebuildReport, content_root: Path) -> None:
        selected_content = prebuild_report.selected_content
        copied_paths: set[str] = set()
        metadata_paths = {"project.json", "settings/build_settings.json"}
        all_paths = (
            tuple(selected_content.scenes)
            + tuple(selected_content.prefabs)
            + tuple(selected_content.scripts)
            + tuple(selected_content.assets)
            + tuple(path for path in selected_content.metadata if path in metadata_paths)
        )
        for relative_path in all_paths:
            normalized_path = str(relative_path or "").strip().replace("\\", "/")
            if not normalized_path or normalized_path in copied_paths:
                continue
            copied_paths.add(normalized_path)
            source_path = self._project_service.resolve_path(normalized_path)
            if not source_path.exists() or not source_path.is_file():
                raise _BuildPlayerFailure(
                    self._diagnostic(
                        "error",
                        "build_player.selected_content_missing",
                        f"Selected build content '{normalized_path}' was not found.",
                        path=normalized_path,
                        stage="content_copy",
                    )
                )
            destination = content_root / Path(normalized_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)

    def _write_packaged_asset_metadata(
        self,
        *,
        prebuild_report: PrebuildReport,
        asset_build_report: dict[str, Any],
        bundle_report: dict[str, Any],
        metadata_root: Path,
        generated_at_utc: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        build_root = self._project_service.get_project_path("build")
        content_bundle_path = build_root / self.CONTENT_BUNDLE_FILE_NAME
        try:
            with content_bundle_path.open("r", encoding="utf-8") as handle:
                content_bundle = json.load(handle)
        except Exception as exc:
            raise _BuildPlayerFailure(
                self._diagnostic(
                    "error",
                    "build_player.content_bundle_missing",
                    f"Content bundle could not be loaded: {exc}",
                    path=self._project_service.to_relative_path(content_bundle_path),
                    stage="asset_bundle",
                )
            ) from exc

        selected_paths = set(prebuild_report.selected_content.scenes)
        selected_paths.update(prebuild_report.selected_content.prefabs)
        selected_paths.update(prebuild_report.selected_content.scripts)
        selected_paths.update(prebuild_report.selected_content.assets)

        imported_artifacts_root = metadata_root / "imported_assets"
        imported_artifacts_root.mkdir(parents=True, exist_ok=True)
        artifact_entries_by_path = {
            str(item.get("path", "")).strip(): dict(item)
            for item in asset_build_report.get("artifacts", [])
            if str(item.get("path", "")).strip()
        }
        bundle_assets_by_path = {
            str(item.get("path", "")).strip(): dict(item)
            for item in content_bundle.get("assets", [])
            if str(item.get("path", "")).strip()
        }
        packaged_artifacts: list[dict[str, Any]] = []
        packaged_bundle_assets: list[dict[str, Any]] = []
        total_artifact_bytes = 0
        total_input_bytes = 0

        for relative_path in sorted(selected_paths):
            artifact_entry = artifact_entries_by_path.get(relative_path)
            bundle_asset = bundle_assets_by_path.get(relative_path)
            if artifact_entry is None or bundle_asset is None:
                raise _BuildPlayerFailure(
                    self._diagnostic(
                        "error",
                        "build_player.asset_metadata_missing",
                        f"Build metadata for '{relative_path}' was not generated.",
                        path=relative_path,
                        stage="asset_bundle",
                    )
                )
            guid = str(artifact_entry.get("guid", "")).strip()
            if not guid:
                raise _BuildPlayerFailure(
                    self._diagnostic(
                        "error",
                        "build_player.asset_guid_missing",
                        f"Build metadata for '{relative_path}' does not contain a GUID.",
                        path=relative_path,
                        stage="asset_bundle",
                    )
                )
            source_artifact = self._project_service.resolve_path(str(artifact_entry.get("artifact_path", "")).strip())
            if not source_artifact.exists() or not source_artifact.is_file():
                raise _BuildPlayerFailure(
                    self._diagnostic(
                        "error",
                        "build_player.artifact_missing",
                        f"Artifact for '{relative_path}' was not found.",
                        path=self._project_service.to_relative_path(source_artifact),
                        stage="asset_bundle",
                    )
                )
            destination_artifact = imported_artifacts_root / f"{guid}.json"
            shutil.copy2(source_artifact, destination_artifact)
            total_artifact_bytes += destination_artifact.stat().st_size if destination_artifact.exists() else 0

            resolved_source = self._project_service.resolve_path(relative_path)
            total_input_bytes += resolved_source.stat().st_size if resolved_source.exists() else 0

            exported_artifact_path = self._export_relative_path(destination_artifact, metadata_root.parent.parent)
            packaged_artifacts.append(
                {
                    "guid": guid,
                    "path": relative_path,
                    "asset_kind": str(artifact_entry.get("asset_kind", "")).strip(),
                    "artifact_path": exported_artifact_path,
                    "source_hash": str(artifact_entry.get("source_hash", "")).strip(),
                    "import_settings_hash": str(artifact_entry.get("import_settings_hash", "")).strip(),
                    "cache_hit": False,
                    "artifact_size_bytes": destination_artifact.stat().st_size if destination_artifact.exists() else 0,
                }
            )
            packaged_bundle_assets.append(
                {
                    "guid": guid,
                    "path": relative_path,
                    "asset_kind": str(bundle_asset.get("asset_kind", "")).strip(),
                    "artifact_path": exported_artifact_path,
                    "dependencies": sorted(
                        {
                            str(item).strip()
                            for item in bundle_asset.get("dependencies", [])
                            if str(item).strip()
                        }
                    ),
                }
            )

        packaged_asset_report = {
            "version": 1,
            "generated_at_utc": generated_at_utc,
            "artifact_count": len(packaged_artifacts),
            "total_artifact_bytes": total_artifact_bytes,
            "artifacts_root": self.IMPORTED_ARTIFACTS_DIR,
            "artifacts": sorted(packaged_artifacts, key=lambda item: item["path"]),
        }
        packaged_bundle = {
            "version": 1,
            "generated_at_utc": generated_at_utc,
            "asset_count": len(packaged_bundle_assets),
            "build_report": f"{self.METADATA_DIR}/{self.ASSET_BUILD_REPORT_FILE_NAME}",
            "assets": sorted(packaged_bundle_assets, key=lambda item: item["path"]),
        }
        top_assets = [
            dict(item)
            for item in bundle_report.get("top_assets_by_size", [])
            if str(item.get("path", "")).strip() in selected_paths
        ]
        top_assets.sort(key=lambda item: (-int(item.get("size_bytes", 0)), str(item.get("path", "")).lower()))
        packaged_bundle_report = {
            "version": 1,
            "generated_at_utc": generated_at_utc,
            "bundle_path": f"{self.METADATA_DIR}/{self.CONTENT_BUNDLE_FILE_NAME}",
            "asset_count": len(packaged_bundle_assets),
            "total_input_bytes": total_input_bytes,
            "top_assets_by_size": top_assets,
            "artifacts": list(packaged_asset_report["artifacts"]),
        }

        self._write_json(metadata_root / self.ASSET_BUILD_REPORT_FILE_NAME, packaged_asset_report)
        self._write_json(metadata_root / self.CONTENT_BUNDLE_FILE_NAME, packaged_bundle)
        self._write_json(metadata_root / self.BUNDLE_REPORT_FILE_NAME, packaged_bundle_report)
        return packaged_asset_report, packaged_bundle, packaged_bundle_report

    def _finalize_success(
        self,
        *,
        settings: BuildSettings,
        build_manifest: BuildManifest,
        prebuild_report: PrebuildReport,
        runtime_manifest: RuntimeManifest,
        packaged_bundle_report: dict[str, Any],
        executable_path: Path,
        output_root: Path,
        build_root: Path,
        warnings: list[BuildReportDiagnostic],
        generated_at_utc: str,
        started_at: float,
    ) -> BuildReport:
        runtime_root = output_root / self.RUNTIME_DIR
        metadata_root = output_root / self.METADATA_DIR
        runtime_root.mkdir(parents=True, exist_ok=True)
        metadata_root.mkdir(parents=True, exist_ok=True)

        project_manifest_path = self._project_service.resolve_path(build_manifest.output.output_root) / BuildManifest.FILE_NAME
        project_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(project_manifest_path, build_manifest.to_dict())

        runtime_manifest_path = runtime_root / RuntimeManifest.FILE_NAME
        build_manifest_export_path = metadata_root / BuildManifest.FILE_NAME
        prebuild_report_path = metadata_root / self.PREBUILD_REPORT_FILE_NAME

        self._write_json(runtime_manifest_path, runtime_manifest.to_dict())
        self._write_json(build_manifest_export_path, build_manifest.to_dict())
        self._write_json(prebuild_report_path, prebuild_report.to_dict())

        development_extras = self._write_development_extras(settings, output_root, generated_at_utc)
        references = {
            "runtime_manifest": self._export_relative_path(runtime_manifest_path, output_root),
            "build_manifest": self._export_relative_path(build_manifest_export_path, output_root),
            "prebuild_report": self._export_relative_path(prebuild_report_path, output_root),
            "asset_build_report": f"{self.METADATA_DIR}/{self.ASSET_BUILD_REPORT_FILE_NAME}",
            "content_bundle": f"{self.METADATA_DIR}/{self.CONTENT_BUNDLE_FILE_NAME}",
            "bundle_report": f"{self.METADATA_DIR}/{self.BUNDLE_REPORT_FILE_NAME}",
        }
        selected_content = prebuild_report.selected_content
        included_asset_counts = {
            "scenes": len(selected_content.scenes),
            "prefabs": len(selected_content.prefabs),
            "scripts": len(selected_content.scripts),
            "assets": len(selected_content.assets),
            "metadata": len(selected_content.metadata),
        }

        report = BuildReport(
            status="succeeded",
            target_platform=settings.target_platform.value,
            output_path=output_root.as_posix(),
            duration_seconds=self._timer() - started_at,
            startup_scene=settings.startup_scene,
            included_scenes=tuple(selected_content.scenes),
            included_asset_counts=included_asset_counts,
            warnings=sorted(warnings, key=_diagnostic_sort_key),
            errors=[],
            output_summary=self._build_output_summary(output_root, executable_path, development_extras),
            top_assets_by_size=[dict(item) for item in packaged_bundle_report.get("top_assets_by_size", [])],
            references=references,
            generated_at_utc=generated_at_utc,
            development_build=settings.development_build,
            development_extras=tuple(development_extras),
        )

        report_path = metadata_root / self.REPORT_FILE_NAME
        report.report_path = self._project_service.to_relative_path(report_path)
        self._write_json(report_path, report.to_dict())
        project_player_report_path = self._project_service.resolve_path(build_manifest.artifacts.player_build_report)
        self._write_json(project_player_report_path, report.to_dict())
        self._write_last_report(report, build_root)
        return report

    def _write_development_extras(
        self,
        settings: BuildSettings,
        output_root: Path,
        generated_at_utc: str,
    ) -> list[str]:
        if not settings.development_build:
            return []
        development_root = output_root / self.DEV_DIR
        development_root.mkdir(parents=True, exist_ok=True)
        development_options_path = development_root / self.DEVELOPMENT_OPTIONS_FILE_NAME
        self._write_json(
            development_options_path,
            {
                "generated_at_utc": generated_at_utc,
                "development_build": True,
                "include_logs": settings.include_logs,
                "include_profiler": settings.include_profiler,
            },
        )
        extras = [self._export_relative_path(development_options_path, output_root)]
        if settings.include_logs:
            logs_root = development_root / "logs"
            logs_root.mkdir(parents=True, exist_ok=True)
            readme_path = logs_root / "README.txt"
            readme_path.write_text(
                "Development build logs will be written to this folder when runtime logging is enabled.\n",
                encoding="utf-8",
            )
            extras.append(self._export_relative_path(readme_path, output_root))
        return sorted(extras)

    def _build_output_summary(
        self,
        output_root: Path,
        executable_path: Path,
        development_extras: list[str],
    ) -> list[BuildReportOutputEntry]:
        candidates = [
            executable_path,
            output_root / self.RUNTIME_DIR,
            output_root / self.CONTENT_DIR,
            output_root / self.METADATA_DIR,
            output_root / self.RUNTIME_DIR / RuntimeManifest.FILE_NAME,
            output_root / self.METADATA_DIR / BuildManifest.FILE_NAME,
            output_root / self.METADATA_DIR / self.PREBUILD_REPORT_FILE_NAME,
            output_root / self.METADATA_DIR / self.ASSET_BUILD_REPORT_FILE_NAME,
            output_root / self.METADATA_DIR / self.CONTENT_BUNDLE_FILE_NAME,
            output_root / self.METADATA_DIR / self.BUNDLE_REPORT_FILE_NAME,
            output_root / self.METADATA_DIR / self.REPORT_FILE_NAME,
        ]
        for extra in development_extras:
            candidates.append(output_root / Path(extra))
        seen: set[str] = set()
        entries: list[BuildReportOutputEntry] = []
        for path in candidates:
            if not path.exists():
                continue
            relative_path = self._export_relative_path(path, output_root)
            if relative_path in seen:
                continue
            seen.add(relative_path)
            entries.append(
                BuildReportOutputEntry(
                    path=relative_path,
                    kind="directory" if path.is_dir() else "file",
                    size_bytes=0 if path.is_dir() else path.stat().st_size,
                )
            )
        entries.sort(key=lambda item: (item.path.lower(), item.kind, item.size_bytes))
        return entries

    def _write_last_report(self, report: BuildReport, build_root: Path) -> None:
        self._write_json(build_root / self.LAST_REPORT_FILE_NAME, report.to_dict())

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)

    def _export_relative_path(self, path: Path, output_root: Path) -> str:
        return path.resolve().relative_to(output_root.resolve()).as_posix()


def build_player(
    project_service: "ProjectService",
    *,
    output_root: str = "",
    generated_at_utc: str = "",
) -> BuildReport:
    return BuildPlayerService(project_service).build_player(
        BuildPlayerOptions(
            output_root=output_root,
            generated_at_utc=generated_at_utc,
        )
    )
