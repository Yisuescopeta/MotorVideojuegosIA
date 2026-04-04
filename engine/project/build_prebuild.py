from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.project.build_settings import (
    BuildManifest,
    build_manifest_from_settings,
    build_manifest_path_relative,
    utc_now_iso,
)
from engine.project.project_service import ProjectService

if TYPE_CHECKING:
    from engine.assets.asset_service import AssetService
    from engine.workflows.ai_assist.diagnostics import AuthoringValidationService
    from engine.workflows.ai_assist.types import ValidationDiagnosticsReport


@dataclass(frozen=True)
class PrebuildDiagnostic:
    severity: str
    blocking: bool
    code: str
    message: str
    stage: str
    reference: str = ""
    source_file: str = ""
    path: str = ""
    category: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "blocking": self.blocking,
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "reference": self.reference,
            "source_file": self.source_file,
            "path": self.path,
            "category": self.category,
        }


@dataclass(frozen=True)
class PrebuildSelectedContent:
    scenes: tuple[str, ...] = ()
    prefabs: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    metadata: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenes": list(self.scenes),
            "prefabs": list(self.prefabs),
            "scripts": list(self.scripts),
            "assets": list(self.assets),
            "metadata": list(self.metadata),
        }


@dataclass(frozen=True)
class PrebuildDependencyGraphSummary:
    root_scenes: tuple[str, ...] = ()
    selected_counts: dict[str, int] = field(default_factory=dict)
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    unresolved_dependencies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        ordered_adjacency = {
            key: list(value)
            for key, value in sorted(self.adjacency.items(), key=lambda item: item[0])
        }
        ordered_counts = {
            key: int(self.selected_counts.get(key, 0))
            for key in ("scenes", "prefabs", "scripts", "assets", "metadata", "total_nodes")
        }
        return {
            "root_scenes": list(self.root_scenes),
            "selected_counts": ordered_counts,
            "adjacency": ordered_adjacency,
            "unresolved_dependencies": list(self.unresolved_dependencies),
        }


@dataclass
class PrebuildReport:
    valid: bool
    startup_scene: str
    scene_order: tuple[str, ...]
    blocking_errors: list[PrebuildDiagnostic] = field(default_factory=list)
    warnings: list[PrebuildDiagnostic] = field(default_factory=list)
    selected_content: PrebuildSelectedContent = field(default_factory=PrebuildSelectedContent)
    omitted_content: PrebuildSelectedContent = field(default_factory=PrebuildSelectedContent)
    dependency_graph: PrebuildDependencyGraphSummary = field(default_factory=PrebuildDependencyGraphSummary)
    build_manifest: BuildManifest | None = None
    generated_at_utc: str = ""
    report_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "valid": self.valid,
            "startup_scene": self.startup_scene,
            "scene_order": list(self.scene_order),
            "blocking_errors": [item.to_dict() for item in self.blocking_errors],
            "warnings": [item.to_dict() for item in self.warnings],
            "selected_content": self.selected_content.to_dict(),
            "omitted_content": self.omitted_content.to_dict(),
            "dependency_graph": self.dependency_graph.to_dict(),
            "build_manifest": self.build_manifest.to_dict() if self.build_manifest is not None else None,
            "generated_at_utc": self.generated_at_utc,
        }
        if self.report_path:
            payload["report_path"] = self.report_path
        return payload


class BuildPrebuildService:
    REPORT_FILE_NAME = "prebuild_content_report.json"

    def __init__(
        self,
        project_service: ProjectService,
        asset_service: "AssetService",
        validation_service: "AuthoringValidationService | None" = None,
    ) -> None:
        if validation_service is None:
            from engine.workflows.ai_assist.diagnostics import AuthoringValidationService

            validation_service = AuthoringValidationService(project_service=project_service)
        self._project_service = project_service
        self._asset_service = asset_service
        self._validation_service = validation_service

    def generate_report(self, generated_at_utc: str | None = None) -> PrebuildReport:
        generated = generated_at_utc or utc_now_iso()
        diagnostics = _DiagnosticCollector()

        try:
            settings = self._project_service.load_build_settings(strict=True)
        except Exception as exc:
            diagnostics.add(
                PrebuildDiagnostic(
                    severity="error",
                    blocking=True,
                    code="build_settings.invalid",
                    message=f"Build settings could not be loaded: {exc}",
                    stage="build_settings",
                    reference=self._project_service.to_relative_path(self._project_service.get_build_settings_path()),
                )
            )
            return PrebuildReport(
                valid=False,
                startup_scene="",
                scene_order=(),
                blocking_errors=diagnostics.blocking_errors(),
                warnings=diagnostics.warnings(),
                generated_at_utc=generated,
            )

        build_root_relative = self._project_service.to_relative_path(self._project_service.get_project_path("build"))
        build_manifest = build_manifest_from_settings(settings, build_root_relative, generated_at_utc=generated)
        build_manifest_path = build_manifest_path_relative(settings, build_root_relative)

        catalog = self._asset_service.refresh_catalog()
        catalog_entries = list(catalog.get("assets", []))
        catalog_by_path = {
            str(entry.get("path", "")).strip(): dict(entry)
            for entry in catalog_entries
            if str(entry.get("path", "")).strip()
        }

        scene_order = tuple(settings.scenes_in_build)
        selected_paths: set[str] = set(scene_order)
        adjacency: dict[str, list[str]] = {scene: [] for scene in scene_order}
        unresolved_dependencies: set[str] = set()
        scene_set = set(scene_order)

        if settings.startup_scene not in scene_set:
            diagnostics.add(
                PrebuildDiagnostic(
                    severity="error",
                    blocking=True,
                    code="build_settings.startup_scene_not_included",
                    message=f"Startup scene '{settings.startup_scene}' is not present in scenes_in_build.",
                    stage="build_settings",
                    reference=settings.startup_scene,
                    source_file=settings.startup_scene,
                )
            )

        for scene_path in scene_order:
            exists = self._project_service.resolve_path(scene_path).exists()
            if not exists and scene_path == settings.startup_scene:
                diagnostics.add(
                    PrebuildDiagnostic(
                        severity="error",
                        blocking=True,
                        code="build_settings.startup_scene_missing",
                        message=f"Startup scene '{scene_path}' was not found.",
                        stage="build_settings",
                        reference=scene_path,
                        source_file=scene_path,
                    )
                )
            elif not exists:
                diagnostics.add(
                    PrebuildDiagnostic(
                        severity="error",
                        blocking=True,
                        code="build_settings.scene_missing",
                        message=f"Build scene '{scene_path}' was not found.",
                        stage="build_settings",
                        reference=scene_path,
                        source_file=scene_path,
                    )
                )
            if exists:
                self._translate_validation_report(
                    self._validation_service.validate_scene_file(scene_path),
                    stage="scene_validation",
                    diagnostics=diagnostics,
                )

        queue: deque[str] = deque(scene_order)
        expanded: set[str] = set()
        while queue:
            path = queue.popleft()
            if path in expanded:
                continue
            expanded.add(path)
            entry = catalog_by_path.get(path)
            if entry is None:
                adjacency.setdefault(path, [])
                continue

            dependencies = sorted({str(item).strip() for item in entry.get("dependencies", []) if str(item).strip()})
            adjacency[path] = dependencies
            for dependency in dependencies:
                dependency_entry = catalog_by_path.get(dependency)
                if dependency_entry is None:
                    unresolved_dependencies.add(dependency)
                    diagnostics.add(
                        PrebuildDiagnostic(
                            severity="error",
                            blocking=True,
                            code="dependency.missing",
                            message=f"Dependency '{dependency}' referenced from '{path}' was not found in the project.",
                            stage="dependency_closure",
                            reference=dependency,
                            source_file=path,
                            path=dependency,
                        )
                    )
                    continue

                dependency_kind = str(dependency_entry.get("asset_kind", "")).strip()
                if dependency_kind == "scene_data" and dependency not in scene_set:
                    unresolved_dependencies.add(dependency)
                    diagnostics.add(
                        PrebuildDiagnostic(
                            severity="error",
                            blocking=True,
                            code="scene_dependency.outside_build",
                            message=(
                                f"Scene '{path}' references scene '{dependency}', "
                                "but it is not listed in scenes_in_build."
                            ),
                            stage="dependency_closure",
                            reference=dependency,
                            source_file=path,
                            path=dependency,
                            category="scene_data",
                        )
                    )
                    continue

                if dependency not in selected_paths:
                    selected_paths.add(dependency)
                    queue.append(dependency)
                adjacency.setdefault(dependency, [])

        selected_prefabs = sorted(
            path
            for path in selected_paths
            if str(catalog_by_path.get(path, {}).get("asset_kind", "")) == "prefab"
        )
        for prefab_path in selected_prefabs:
            self._translate_validation_report(
                self._validation_service.validate_prefab_file(prefab_path),
                stage="prefab_validation",
                diagnostics=diagnostics,
            )

        selected_content = self._build_selected_content(
            scene_order=scene_order,
            selected_paths=selected_paths,
            catalog_by_path=catalog_by_path,
            build_manifest_path=build_manifest_path,
        )
        omitted_content = self._build_omitted_content(scene_order=scene_order, selected_paths=selected_paths, catalog_by_path=catalog_by_path)
        dependency_graph = self._build_dependency_graph(
            scene_order=scene_order,
            selected_content=selected_content,
            adjacency=adjacency,
            unresolved_dependencies=unresolved_dependencies,
        )

        blocking_errors = diagnostics.blocking_errors()
        warnings = diagnostics.warnings()
        return PrebuildReport(
            valid=not blocking_errors,
            startup_scene=settings.startup_scene,
            scene_order=scene_order,
            blocking_errors=blocking_errors,
            warnings=warnings,
            selected_content=selected_content,
            omitted_content=omitted_content,
            dependency_graph=dependency_graph,
            build_manifest=build_manifest,
            generated_at_utc=generated,
        )

    def save_report(self, report: PrebuildReport) -> Path:
        path = self._project_service.get_project_path("build") / self.REPORT_FILE_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        report.report_path = self._project_service.to_relative_path(path)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(report.to_dict(), handle, indent=4)
        return path

    def _translate_validation_report(
        self,
        report: "ValidationDiagnosticsReport",
        *,
        stage: str,
        diagnostics: "_DiagnosticCollector",
    ) -> None:
        for item in report.diagnostics:
            severity = str(getattr(getattr(item, "severity", ""), "value", getattr(item, "severity", "error"))).lower()
            blocking = severity != "warning"
            category = str(getattr(getattr(item, "category", ""), "value", getattr(item, "category", "")))
            diagnostics.add(
                PrebuildDiagnostic(
                    severity=severity if severity in {"warning", "error"} else "error",
                    blocking=blocking,
                    code=str(getattr(item, "code", "")).strip(),
                    message=str(getattr(item, "message", "")).strip(),
                    stage=stage,
                    reference=str(getattr(item, "reference", "")).strip(),
                    source_file=str(getattr(item, "source_file", "")).strip(),
                    path=str(getattr(item, "path", "")).strip(),
                    category=category,
                )
            )

    def _build_selected_content(
        self,
        *,
        scene_order: tuple[str, ...],
        selected_paths: set[str],
        catalog_by_path: dict[str, dict[str, Any]],
        build_manifest_path: str,
    ) -> PrebuildSelectedContent:
        prefabs: list[str] = []
        scripts: list[str] = []
        assets: list[str] = []
        for path in sorted(selected_paths):
            kind = str(catalog_by_path.get(path, {}).get("asset_kind", "")).strip()
            if kind == "scene_data":
                continue
            if kind == "prefab":
                prefabs.append(path)
                continue
            if kind == "script":
                scripts.append(path)
                continue
            assets.append(path)
        metadata = (
            "project.json",
            "settings/build_settings.json",
            build_manifest_path,
        )
        return PrebuildSelectedContent(
            scenes=scene_order,
            prefabs=tuple(prefabs),
            scripts=tuple(scripts),
            assets=tuple(assets),
            metadata=metadata,
        )

    def _build_omitted_content(
        self,
        *,
        scene_order: tuple[str, ...],
        selected_paths: set[str],
        catalog_by_path: dict[str, dict[str, Any]],
    ) -> PrebuildSelectedContent:
        omitted_scenes = tuple(
            path
            for path, entry in sorted(catalog_by_path.items(), key=lambda item: item[0])
            if str(entry.get("asset_kind", "")).strip() == "scene_data" and path not in set(scene_order)
        )
        prefabs: list[str] = []
        scripts: list[str] = []
        assets: list[str] = []
        for path, entry in sorted(catalog_by_path.items(), key=lambda item: item[0]):
            if path in selected_paths:
                continue
            kind = str(entry.get("asset_kind", "")).strip()
            if kind == "scene_data":
                continue
            if kind == "prefab":
                prefabs.append(path)
                continue
            if kind == "script":
                scripts.append(path)
                continue
            assets.append(path)
        return PrebuildSelectedContent(
            scenes=omitted_scenes,
            prefabs=tuple(prefabs),
            scripts=tuple(scripts),
            assets=tuple(assets),
            metadata=(),
        )

    def _build_dependency_graph(
        self,
        *,
        scene_order: tuple[str, ...],
        selected_content: PrebuildSelectedContent,
        adjacency: dict[str, list[str]],
        unresolved_dependencies: set[str],
    ) -> PrebuildDependencyGraphSummary:
        selected_nodes = set(scene_order)
        selected_nodes.update(selected_content.prefabs)
        selected_nodes.update(selected_content.scripts)
        selected_nodes.update(selected_content.assets)
        ordered_adjacency = {
            key: sorted(
                dependency
                for dependency in adjacency.get(key, [])
                if dependency in selected_nodes
            )
            for key in sorted(selected_nodes)
        }
        counts = {
            "scenes": len(selected_content.scenes),
            "prefabs": len(selected_content.prefabs),
            "scripts": len(selected_content.scripts),
            "assets": len(selected_content.assets),
            "metadata": len(selected_content.metadata),
            "total_nodes": len(selected_nodes),
        }
        return PrebuildDependencyGraphSummary(
            root_scenes=scene_order,
            selected_counts=counts,
            adjacency=ordered_adjacency,
            unresolved_dependencies=tuple(sorted(unresolved_dependencies)),
        )


class _DiagnosticCollector:
    def __init__(self) -> None:
        self._items: list[PrebuildDiagnostic] = []
        self._seen: set[tuple[str, ...]] = set()

    def add(self, diagnostic: PrebuildDiagnostic) -> None:
        key = (
            diagnostic.severity,
            str(diagnostic.blocking),
            diagnostic.stage,
            diagnostic.code,
            diagnostic.reference,
            diagnostic.source_file,
            diagnostic.path,
            diagnostic.message,
            diagnostic.category,
        )
        if key in self._seen:
            return
        self._seen.add(key)
        self._items.append(diagnostic)

    def blocking_errors(self) -> list[PrebuildDiagnostic]:
        return self._sorted(blocking=True)

    def warnings(self) -> list[PrebuildDiagnostic]:
        return self._sorted(blocking=False)

    def _sorted(self, *, blocking: bool) -> list[PrebuildDiagnostic]:
        return sorted(
            [item for item in self._items if item.blocking == blocking],
            key=lambda item: (
                item.source_file.lower(),
                item.reference.lower(),
                item.stage.lower(),
                item.code.lower(),
                item.path.lower(),
                item.message.lower(),
            ),
        )
