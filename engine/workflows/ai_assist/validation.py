from __future__ import annotations

from typing import Any

from engine.api import EngineAPI
from engine.serialization import migrate_prefab_data, migrate_scene_data, validate_prefab_data, validate_scene_data
from engine.workflows.ai_assist.types import (
    AuthoringPlan,
    AuthoringRequest,
    ValidationIssue,
    ValidationIssueSeverity,
    ValidationReport,
    ValidationStatus,
)


def _issue(
    code: str,
    message: str,
    *,
    severity: ValidationIssueSeverity = ValidationIssueSeverity.ERROR,
    blocking: bool = False,
    target: str = "",
) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, severity=severity, blocking=blocking, target=target)


def _project_relative_target(api: EngineAPI, target: str) -> bool:
    if not target or api.project_service is None:
        return True
    try:
        resolved = api.project_service.resolve_path(target)
        resolved.relative_to(api.project_service.project_root)
        return True
    except Exception:
        return False


def _status_for_issues(issues: list[ValidationIssue]) -> ValidationStatus:
    if any(issue.blocking for issue in issues):
        return ValidationStatus.FAIL
    if issues:
        return ValidationStatus.WARN
    return ValidationStatus.PASS


def validate_scene_payload(scene_payload: Any) -> ValidationReport:
    issues: list[ValidationIssue] = []
    checked_artifacts = ["scene_payload"]
    try:
        migrated = migrate_scene_data(dict(scene_payload))
    except Exception as exc:
        issues.append(_issue("scene_payload.invalid", f"Scene payload migration failed: {exc}", blocking=True))
        return ValidationReport(status=ValidationStatus.FAIL, checked_artifacts=checked_artifacts, issues=issues)

    for error in validate_scene_data(migrated):
        issues.append(_issue("scene_payload.schema", error, blocking=True, target="scene_payload"))
    return ValidationReport(status=_status_for_issues(issues), checked_artifacts=checked_artifacts, issues=issues)


def validate_prefab_payload(prefab_payload: Any) -> ValidationReport:
    issues: list[ValidationIssue] = []
    checked_artifacts = ["prefab_payload"]
    try:
        migrated = migrate_prefab_data(dict(prefab_payload))
    except Exception as exc:
        issues.append(_issue("prefab_payload.invalid", f"Prefab payload migration failed: {exc}", blocking=True))
        return ValidationReport(status=ValidationStatus.FAIL, checked_artifacts=checked_artifacts, issues=issues)

    for error in validate_prefab_data(migrated):
        issues.append(_issue("prefab_payload.schema", error, blocking=True, target="prefab_payload"))
    return ValidationReport(status=_status_for_issues(issues), checked_artifacts=checked_artifacts, issues=issues)


def validate_authoring_request(
    api: EngineAPI,
    request: AuthoringRequest,
    *,
    plan: AuthoringPlan | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    checked_artifacts = ["authoring_request"]
    if plan is not None:
        checked_artifacts.append("authoring_plan")

    if not request.goal.strip():
        issues.append(_issue("request.goal_required", "Authoring request goal must be non-empty.", blocking=True))

    if request.target_scene_path and not api.get_active_scene().get("path") and request.operation_kind.value == "scene_edit":
        issues.append(
            _issue(
                "request.scene_missing",
                "Scene workflow requires an active scene before authoring.",
                blocking=True,
                target=request.target_scene_path,
            )
        )

    path_targets = {
        "target_scene_path": request.target_scene_path,
        "target_prefab_path": request.target_prefab_path,
        "target_script_path": request.target_script_path,
        "target_asset_path": request.target_asset_path,
    }
    for field_name, target in path_targets.items():
        if target and not _project_relative_target(api, target):
            issues.append(
                _issue(
                    "request.path_outside_project",
                    f"{field_name} must stay inside the active project.",
                    blocking=True,
                    target=target,
                )
            )

    if plan is not None and not plan.steps:
        issues.append(
            _issue(
                "plan.no_steps",
                "Authoring plan must contain at least one explicit step.",
                blocking=True,
                target=plan.plan_id,
            )
        )

    return ValidationReport(status=_status_for_issues(issues), checked_artifacts=checked_artifacts, issues=issues)


def validate_workflow(
    api: EngineAPI,
    request: AuthoringRequest,
    *,
    plan: AuthoringPlan | None = None,
    scene_payload: Any | None = None,
    prefab_payload: Any | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    checked_artifacts: list[str] = []

    request_report = validate_authoring_request(api, request, plan=plan)
    issues.extend(request_report.issues)
    checked_artifacts.extend(request_report.checked_artifacts)

    if scene_payload is not None:
        scene_report = validate_scene_payload(scene_payload)
        issues.extend(scene_report.issues)
        checked_artifacts.extend(scene_report.checked_artifacts)

    if prefab_payload is not None:
        prefab_report = validate_prefab_payload(prefab_payload)
        issues.extend(prefab_report.issues)
        checked_artifacts.extend(prefab_report.checked_artifacts)

    deduped_artifacts = list(dict.fromkeys(checked_artifacts))
    return ValidationReport(status=_status_for_issues(issues), checked_artifacts=deduped_artifacts, issues=issues)
