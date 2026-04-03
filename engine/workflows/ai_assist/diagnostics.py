from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_transition_support import (
    collect_project_scene_transitions,
    validate_scene_transition_references,
)
from engine.serialization.schema import (
    build_canonical_scene_payload,
    migrate_prefab_data,
    migrate_scene_data,
    validate_prefab_data,
    validate_scene_data,
)
from engine.workflows.ai_assist.types import (
    ValidationDiagnostic,
    ValidationDiagnosticCategory,
    ValidationDiagnosticsReport,
    ValidationDiagnosticSeverity,
    ValidationTargetKind,
)


class _ProjectBoundaryError(ValueError):
    pass


class AuthoringValidationService:
    """Structured validation adapter for AI-assisted authoring workflows."""

    def __init__(
        self,
        api: EngineAPI | None = None,
        *,
        project_service: ProjectService | None = None,
        scene_manager: SceneManager | None = None,
    ) -> None:
        self.api = api
        self.project_service = project_service or (api.project_service if api is not None else None)
        self.scene_manager = scene_manager or (api.scene_manager if api is not None else None)

    def validate_active_scene(self) -> ValidationDiagnosticsReport:
        active_summary = self._get_active_scene_summary()
        reference = self._normalize_reference(
            str(active_summary.get("path", "") or active_summary.get("key", "") or "active_scene")
        )
        checked_files = [reference] if reference and reference != "active_scene" else []
        entry = self._resolve_active_entry()
        if entry is None or getattr(entry, "scene", None) is None or getattr(entry, "edit_world", None) is None:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.WORKSPACE_REFERENCE,
                code="workspace.no_active_scene",
                message="No active scene is available for validation.",
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                reference=reference or "active_scene",
                source_file=reference if reference != "active_scene" else "",
            )
            return self._build_report(
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                target_reference=reference or "active_scene",
                diagnostics=[diagnostic],
                raw_messages=[diagnostic.message],
                checked_files=checked_files,
            )

        try:
            world_snapshot = copy.deepcopy(entry.edit_world.serialize())
            payload = build_canonical_scene_payload(
                scene_name=entry.scene.name,
                world_snapshot=world_snapshot,
                rules_data=entry.scene.rules_data,
                feature_metadata=entry.scene.feature_metadata,
            )
        except Exception as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="scene.migration_failed",
                message=f"Active scene validation failed during canonicalization: {exc}",
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                reference=reference or "active_scene",
                source_file=reference if reference != "active_scene" else "",
            )
            return self._build_report(
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                target_reference=reference or "active_scene",
                diagnostics=[diagnostic],
                raw_messages=[diagnostic.message],
                checked_files=checked_files,
            )

        diagnostics, raw_messages = self._collect_scene_diagnostics(
            payload,
            scene_path=str(getattr(entry.scene, "source_path", "") or ""),
            target_kind=ValidationTargetKind.ACTIVE_SCENE,
            reference=reference or "active_scene",
        )
        return self._build_report(
            target_kind=ValidationTargetKind.ACTIVE_SCENE,
            target_reference=reference or "active_scene",
            diagnostics=diagnostics,
            raw_messages=raw_messages,
            checked_files=checked_files,
        )

    def validate_scene_file(self, scene_path: str) -> ValidationDiagnosticsReport:
        reference = self._normalize_reference(scene_path)
        checked_files = [reference] if reference else []
        payload, diagnostics, raw_messages = self._load_scene_payload(scene_path, ValidationTargetKind.SCENE_FILE)
        if payload is None:
            return self._build_report(
                target_kind=ValidationTargetKind.SCENE_FILE,
                target_reference=reference,
                diagnostics=diagnostics,
                raw_messages=raw_messages,
                checked_files=checked_files,
            )

        scene_diagnostics, scene_messages = self._collect_scene_diagnostics(
            payload,
            scene_path=scene_path,
            target_kind=ValidationTargetKind.SCENE_FILE,
            reference=reference,
        )
        return self._build_report(
            target_kind=ValidationTargetKind.SCENE_FILE,
            target_reference=reference,
            diagnostics=scene_diagnostics,
            raw_messages=scene_messages,
            checked_files=checked_files,
        )

    def validate_prefab_file(self, prefab_path: str) -> ValidationDiagnosticsReport:
        reference = self._normalize_reference(prefab_path)
        checked_files = [reference] if reference else []
        payload, diagnostics, raw_messages = self._load_prefab_payload(prefab_path, ValidationTargetKind.PREFAB_FILE)
        if payload is None:
            return self._build_report(
                target_kind=ValidationTargetKind.PREFAB_FILE,
                target_reference=reference,
                diagnostics=diagnostics,
                raw_messages=raw_messages,
                checked_files=checked_files,
            )

        prefab_messages = validate_prefab_data(payload)
        prefab_diagnostics = [
            self._diagnostic_from_message(
                message,
                default_category=ValidationDiagnosticCategory.PREFAB_SCHEMA,
                target_kind=ValidationTargetKind.PREFAB_FILE,
                reference=reference,
                source_file=reference,
            )
            for message in prefab_messages
        ]
        return self._build_report(
            target_kind=ValidationTargetKind.PREFAB_FILE,
            target_reference=reference,
            diagnostics=prefab_diagnostics,
            raw_messages=prefab_messages,
            checked_files=checked_files,
        )

    def validate_scene_transition_references(self, scene_path: str | None = None) -> ValidationDiagnosticsReport:
        if scene_path:
            reference = self._normalize_reference(scene_path)
            checked_files = [reference] if reference else []
            payload, diagnostics, raw_messages = self._load_scene_payload(scene_path, ValidationTargetKind.SCENE_FILE)
            if payload is None:
                return self._build_report(
                    target_kind=ValidationTargetKind.SCENE_FILE,
                    target_reference=reference,
                    diagnostics=diagnostics,
                    raw_messages=raw_messages,
                    checked_files=checked_files,
                )
            messages = validate_scene_transition_references(payload, scene_path=self._resolve_existing_path(scene_path).as_posix())
            transition_diagnostics = [
                self._diagnostic_from_message(
                    message,
                    default_category=ValidationDiagnosticCategory.SCENE_TRANSITION,
                    target_kind=ValidationTargetKind.SCENE_FILE,
                    reference=reference,
                    source_file=reference,
                )
                for message in messages
            ]
            return self._build_report(
                target_kind=ValidationTargetKind.SCENE_FILE,
                target_reference=reference,
                diagnostics=transition_diagnostics,
                raw_messages=messages,
                checked_files=checked_files,
            )

        active_summary = self._get_active_scene_summary()
        reference = self._normalize_reference(
            str(active_summary.get("path", "") or active_summary.get("key", "") or "active_scene")
        )
        checked_files = [reference] if reference and reference != "active_scene" else []
        entry = self._resolve_active_entry()
        if entry is None or getattr(entry, "scene", None) is None or getattr(entry, "edit_world", None) is None:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.WORKSPACE_REFERENCE,
                code="workspace.no_active_scene",
                message="No active scene is available for transition validation.",
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                reference=reference or "active_scene",
                source_file=reference if reference != "active_scene" else "",
            )
            return self._build_report(
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                target_reference=reference or "active_scene",
                diagnostics=[diagnostic],
                raw_messages=[diagnostic.message],
                checked_files=checked_files,
            )

        try:
            payload = build_canonical_scene_payload(
                scene_name=entry.scene.name,
                world_snapshot=copy.deepcopy(entry.edit_world.serialize()),
                rules_data=entry.scene.rules_data,
                feature_metadata=entry.scene.feature_metadata,
            )
        except Exception as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="scene.migration_failed",
                message=f"Active scene transition validation failed during canonicalization: {exc}",
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                reference=reference or "active_scene",
                source_file=reference if reference != "active_scene" else "",
            )
            return self._build_report(
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                target_reference=reference or "active_scene",
                diagnostics=[diagnostic],
                raw_messages=[diagnostic.message],
                checked_files=checked_files,
            )

        messages = validate_scene_transition_references(payload, scene_path=str(getattr(entry.scene, "source_path", "") or "") or None)
        diagnostics = [
            self._diagnostic_from_message(
                message,
                default_category=ValidationDiagnosticCategory.SCENE_TRANSITION,
                target_kind=ValidationTargetKind.ACTIVE_SCENE,
                reference=reference or "active_scene",
                source_file=reference if reference != "active_scene" else "",
            )
            for message in messages
        ]
        return self._build_report(
            target_kind=ValidationTargetKind.ACTIVE_SCENE,
            target_reference=reference or "active_scene",
            diagnostics=diagnostics,
            raw_messages=messages,
            checked_files=checked_files,
        )

    def validate_project_lightweight(self) -> ValidationDiagnosticsReport:
        reference = self._normalize_reference(
            self.project_service.project_root.as_posix() if self.project_service is not None else "project"
        ) or "project"
        diagnostics: list[ValidationDiagnostic] = []
        raw_messages: list[str] = []
        checked_files: list[str] = []

        if self.project_service is None or not self.project_service.has_project:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.WORKSPACE_REFERENCE,
                code="project.unavailable",
                message="Project validation requires an active project.",
                target_kind=ValidationTargetKind.PROJECT,
                reference=reference,
            )
            return self._build_report(
                target_kind=ValidationTargetKind.PROJECT,
                target_reference=reference,
                diagnostics=[diagnostic],
                raw_messages=[diagnostic.message],
                checked_files=[],
            )

        for scene_record in self.project_service.list_project_scenes():
            path = str(scene_record.get("path", "") or "")
            if not path:
                continue
            report = self.validate_scene_file(path)
            diagnostics.extend(report.diagnostics)
            raw_messages.extend(report.raw_messages)
            checked_files.extend(report.checked_files)

        for prefab_path in self._list_project_prefabs():
            report = self.validate_prefab_file(prefab_path)
            diagnostics.extend(report.diagnostics)
            raw_messages.extend(report.raw_messages)
            checked_files.extend(report.checked_files)

        transition_snapshot = collect_project_scene_transitions(
            self.project_service,
            self.scene_manager or SceneManager(create_default_registry()),
        )
        diagnostics.extend(self._diagnostics_from_transition_snapshot(transition_snapshot))
        raw_messages.extend(self._raw_messages_from_transition_snapshot(transition_snapshot))

        return self._build_report(
            target_kind=ValidationTargetKind.PROJECT,
            target_reference=reference,
            diagnostics=diagnostics,
            raw_messages=raw_messages,
            checked_files=checked_files,
        )

    def _collect_scene_diagnostics(
        self,
        payload: dict[str, Any],
        *,
        scene_path: str,
        target_kind: ValidationTargetKind,
        reference: str,
    ) -> tuple[list[ValidationDiagnostic], list[str]]:
        schema_messages = validate_scene_data(payload)
        diagnostics = [
            self._diagnostic_from_message(
                message,
                default_category=ValidationDiagnosticCategory.SCENE_SCHEMA,
                target_kind=target_kind,
                reference=reference,
                source_file=reference if target_kind != ValidationTargetKind.ACTIVE_SCENE or reference != "active_scene" else "",
            )
            for message in schema_messages
        ]
        raw_messages = list(schema_messages)
        if schema_messages:
            return diagnostics, raw_messages

        transition_messages = validate_scene_transition_references(
            payload,
            scene_path=self._resolve_existing_path(scene_path).as_posix() if scene_path else None,
        )
        diagnostics.extend(
            self._diagnostic_from_message(
                message,
                default_category=ValidationDiagnosticCategory.SCENE_TRANSITION,
                target_kind=target_kind,
                reference=reference,
                source_file=reference if target_kind != ValidationTargetKind.ACTIVE_SCENE or reference != "active_scene" else "",
            )
            for message in transition_messages
        )
        raw_messages.extend(transition_messages)
        return diagnostics, raw_messages

    def _load_scene_payload(
        self,
        scene_path: str,
        target_kind: ValidationTargetKind,
    ) -> tuple[dict[str, Any] | None, list[ValidationDiagnostic], list[str]]:
        reference = self._normalize_reference(scene_path)
        try:
            resolved = self._resolve_existing_path(scene_path)
        except FileNotFoundError:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="scene.file_not_found",
                message=f"Scene file '{scene_path}' was not found.",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]
        except _ProjectBoundaryError:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.WORKSPACE_REFERENCE,
                code="scene.path_outside_project",
                message=f"Scene path '{scene_path}' is outside the active project.",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]

        try:
            with resolved.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="scene.invalid_json",
                message=f"Scene file '{reference}' contains invalid JSON: {exc}",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]
        except OSError as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="scene.unreadable",
                message=f"Scene file '{reference}' could not be read: {exc}",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]

        try:
            payload = migrate_scene_data(raw)
        except Exception as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="scene.migration_failed",
                message=f"Scene file '{reference}' failed migration: {exc}",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]
        return payload, [], []

    def _load_prefab_payload(
        self,
        prefab_path: str,
        target_kind: ValidationTargetKind,
    ) -> tuple[dict[str, Any] | None, list[ValidationDiagnostic], list[str]]:
        reference = self._normalize_reference(prefab_path)
        try:
            resolved = self._resolve_existing_path(prefab_path)
        except FileNotFoundError:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="prefab.file_not_found",
                message=f"Prefab file '{prefab_path}' was not found.",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]
        except _ProjectBoundaryError:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.WORKSPACE_REFERENCE,
                code="prefab.path_outside_project",
                message=f"Prefab path '{prefab_path}' is outside the active project.",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]

        try:
            with resolved.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="prefab.invalid_json",
                message=f"Prefab file '{reference}' contains invalid JSON: {exc}",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]
        except OSError as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="prefab.unreadable",
                message=f"Prefab file '{reference}' could not be read: {exc}",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]

        try:
            payload = migrate_prefab_data(raw)
        except Exception as exc:
            diagnostic = self._simple_diagnostic(
                category=ValidationDiagnosticCategory.IO,
                code="prefab.migration_failed",
                message=f"Prefab file '{reference}' failed migration: {exc}",
                target_kind=target_kind,
                reference=reference,
                source_file=reference,
            )
            return None, [diagnostic], [diagnostic.message]
        return payload, [], []

    def _diagnostic_from_message(
        self,
        message: str,
        *,
        default_category: ValidationDiagnosticCategory,
        target_kind: ValidationTargetKind,
        reference: str,
        source_file: str,
    ) -> ValidationDiagnostic:
        path = self._extract_path(message)
        category = self._classify_message(message, default_category=default_category)
        return ValidationDiagnostic(
            severity=ValidationDiagnosticSeverity.ERROR,
            category=category,
            code=self._code_for_message(message, category=category, default_category=default_category),
            message=message,
            reference=reference,
            source_file=source_file,
            path=path,
            target_kind=target_kind,
        )

    def _simple_diagnostic(
        self,
        *,
        category: ValidationDiagnosticCategory,
        code: str,
        message: str,
        target_kind: ValidationTargetKind,
        reference: str,
        source_file: str = "",
        path: str = "",
    ) -> ValidationDiagnostic:
        return ValidationDiagnostic(
            severity=ValidationDiagnosticSeverity.ERROR,
            category=category,
            code=code,
            message=message,
            reference=reference,
            source_file=source_file,
            path=path,
            target_kind=target_kind,
        )

    def _build_report(
        self,
        *,
        target_kind: ValidationTargetKind,
        target_reference: str,
        diagnostics: list[ValidationDiagnostic],
        raw_messages: list[str],
        checked_files: list[str],
    ) -> ValidationDiagnosticsReport:
        deduped_files = sorted({item for item in checked_files if item})
        ordered_diagnostics = sorted(
            diagnostics,
            key=lambda item: (
                str(item.source_file or "").lower(),
                str(item.reference or "").lower(),
                str(item.category.value if hasattr(item.category, "value") else item.category).lower(),
                str(item.code or "").lower(),
                str(item.path or "").lower(),
                str(item.message or "").lower(),
            ),
        )
        ordered_raw_messages = sorted(str(message) for message in raw_messages)
        valid = not any(item.severity == ValidationDiagnosticSeverity.ERROR for item in ordered_diagnostics)
        return ValidationDiagnosticsReport(
            target_kind=target_kind,
            target_reference=target_reference,
            valid=valid,
            diagnostics=ordered_diagnostics,
            raw_messages=ordered_raw_messages,
            checked_files=deduped_files,
        )

    def _get_active_scene_summary(self) -> dict[str, Any]:
        if self.api is not None:
            return self.api.get_active_scene()
        if self.scene_manager is None:
            return {}
        return self.scene_manager.get_active_scene_summary()

    def _resolve_active_entry(self) -> Any | None:
        if self.scene_manager is None:
            return None
        active_key = str(getattr(self.scene_manager, "active_scene_key", "") or "")
        if not active_key:
            return None
        return self.scene_manager.resolve_entry(active_key)

    def _resolve_existing_path(self, path: str) -> Path:
        candidate = self.project_service.resolve_path(path) if self.project_service is not None else Path(path).expanduser().resolve()
        if self.project_service is not None:
            try:
                candidate.relative_to(self.project_service.project_root)
            except ValueError as exc:
                raise _ProjectBoundaryError(str(candidate)) from exc
        if not candidate.exists():
            raise FileNotFoundError(candidate.as_posix())
        return candidate

    def _normalize_reference(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        if self.project_service is None:
            return normalized.replace("\\", "/")
        try:
            return self.project_service.to_relative_path(normalized)
        except Exception:
            return normalized.replace("\\", "/")

    def _extract_path(self, message: str) -> str:
        if message.startswith("$.") and ": " in message:
            return message.split(": ", 1)[0]
        return ""

    def _classify_message(
        self,
        message: str,
        *,
        default_category: ValidationDiagnosticCategory,
    ) -> ValidationDiagnosticCategory:
        if default_category == ValidationDiagnosticCategory.PREFAB_SCHEMA:
            return ValidationDiagnosticCategory.PREFAB_SCHEMA
        lowered = message.lower()
        if message.startswith("$.feature_metadata.scene_flow"):
            return ValidationDiagnosticCategory.SCENE_FLOW
        if message.startswith("$.feature_metadata."):
            return ValidationDiagnosticCategory.FEATURE_METADATA
        if "target scene '" in lowered or "target entry point" in lowered:
            return ValidationDiagnosticCategory.SCENE_TRANSITION
        if "scenetransitionaction" in message or "scenetransitiononcontact" in message or "scenetransitiononinteract" in message or "sceneentrypoint" in message:
            return ValidationDiagnosticCategory.SCENE_TRANSITION
        if "unknown parent" in lowered or "cycle detected" in lowered or "cannot be its own parent" in lowered or "duplicate entity name" in lowered:
            return ValidationDiagnosticCategory.SCENE_HIERARCHY
        return default_category

    def _code_for_message(
        self,
        message: str,
        *,
        category: ValidationDiagnosticCategory,
        default_category: ValidationDiagnosticCategory,
    ) -> str:
        lowered = message.lower()
        if category == ValidationDiagnosticCategory.SCENE_HIERARCHY:
            if "unknown parent" in lowered:
                return "scene_hierarchy.unknown_parent"
            if "cycle detected" in lowered:
                return "scene_hierarchy.cycle_detected"
            if "cannot be its own parent" in lowered:
                return "scene_hierarchy.self_parent"
            if "duplicate entity name" in lowered:
                return "scene_hierarchy.duplicate_entity_name"
            return "scene_hierarchy.invalid"
        if category == ValidationDiagnosticCategory.SCENE_TRANSITION:
            if "does not exist" in lowered:
                return "scene_transition.target_scene_missing"
            if "not found in destination scene" in lowered:
                return "scene_transition.target_entry_missing"
            if "required when using scene transition triggers" in lowered:
                return "scene_transition.missing_action"
            if "requires collider.is_trigger = true" in lowered:
                return "scene_transition.invalid_trigger"
            if "invalid source scene payload" in lowered:
                return "scene_transition.source_invalid"
            return "scene_transition.invalid"
        if category == ValidationDiagnosticCategory.SCENE_FLOW:
            return "scene_flow.invalid"
        if category == ValidationDiagnosticCategory.FEATURE_METADATA:
            return "feature_metadata.invalid"
        if category == ValidationDiagnosticCategory.PREFAB_SCHEMA:
            if "unknown parent" in lowered:
                return "prefab_schema.unknown_parent"
            if "exactly one root entity" in lowered:
                return "prefab_schema.invalid_root_count"
            return "prefab_schema.invalid"
        if default_category == ValidationDiagnosticCategory.SCENE_SCHEMA:
            return "scene_schema.invalid"
        return f"{default_category.value}.invalid"

    def _list_project_prefabs(self) -> list[str]:
        if self.project_service is None or not self.project_service.has_project:
            return []
        return self.project_service.list_project_prefabs()

    def _diagnostics_from_transition_snapshot(self, snapshot: dict[str, Any]) -> list[ValidationDiagnostic]:
        diagnostics: list[ValidationDiagnostic] = []
        for issue in snapshot.get("issues", []):
            source_file = self._normalize_reference(str(issue.get("source_scene_path", "") or issue.get("source_scene_ref", "") or ""))
            reference = source_file or "project"
            for message in issue.get("messages", []):
                diagnostics.append(
                    ValidationDiagnostic(
                        severity=ValidationDiagnosticSeverity.ERROR,
                        category=ValidationDiagnosticCategory.PROJECT_CONSISTENCY,
                        code="project_consistency.invalid_scene",
                        message=str(message),
                        reference=reference,
                        source_file=source_file,
                        target_kind=ValidationTargetKind.PROJECT,
                    )
                )
        for row in snapshot.get("rows", []):
            status = str(row.get("status", "") or "").lower()
            if status not in {"error", "warning"}:
                continue
            source_file = self._normalize_reference(str(row.get("source_scene_path", "") or row.get("source_scene_ref", "") or ""))
            reference = source_file or "project"
            severity = (
                ValidationDiagnosticSeverity.WARNING if status == "warning" else ValidationDiagnosticSeverity.ERROR
            )
            for message in row.get("messages", []):
                diagnostics.append(
                    ValidationDiagnostic(
                        severity=severity,
                        category=ValidationDiagnosticCategory.SCENE_TRANSITION,
                        code="scene_transition.project_reference_invalid",
                        message=str(message),
                        reference=reference,
                        source_file=source_file,
                        target_kind=ValidationTargetKind.PROJECT,
                    )
                )
        return sorted(
            diagnostics,
            key=lambda item: (
                str(item.source_file or "").lower(),
                str(item.reference or "").lower(),
                str(item.code or "").lower(),
                str(item.message or "").lower(),
            ),
        )

    def _raw_messages_from_transition_snapshot(self, snapshot: dict[str, Any]) -> list[str]:
        messages: list[str] = []
        for issue in snapshot.get("issues", []):
            messages.extend(str(message) for message in issue.get("messages", []))
        for row in snapshot.get("rows", []):
            status = str(row.get("status", "") or "").lower()
            if status not in {"error", "warning"}:
                continue
            messages.extend(str(message) for message in row.get("messages", []))
        return sorted(messages)
