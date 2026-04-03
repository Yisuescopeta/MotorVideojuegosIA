from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.api import EngineAPI
from engine.assets.asset_service import AssetService
from engine.project.project_service import ProjectService
from engine.workflows.ai_assist import (
    AuthoringExecutionRequest,
    AuthoringExecutionService,
    AuthoringExecutionStatus,
    AuthoringValidationService,
    HeadlessVerificationAssertion,
    HeadlessVerificationAssertionKind,
    HeadlessVerificationScenario,
    HeadlessVerificationService,
    ProjectContextPackGenerator,
    VerificationStatus,
)
from engine.workflows.ai_assist.types import (
    AuthoringEntityPropertyKind,
    AuthoringExecutionOperation,
    AuthoringExecutionOperationKind,
)


EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_VALIDATION_FAILED = 2
EXIT_VERIFICATION_FAILED = 3
EXIT_EXECUTION_FAILED = 4


def load_json_file(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def write_json_output(payload: Any, out_path: str = "") -> str:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
    if out_path:
        output = Path(out_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return rendered


def parse_execution_request(data: dict[str, Any]) -> AuthoringExecutionRequest:
    operations = [parse_execution_operation(item) for item in _as_list(data.get("operations"))]
    return AuthoringExecutionRequest(
        request_id=str(data.get("request_id", "") or "").strip(),
        label=str(data.get("label", "") or "").strip(),
        operations=operations,
        target_scene_ref=str(data.get("target_scene_ref", "") or "").strip(),
        metadata=_as_dict(data.get("metadata")),
    )


def parse_execution_operation(data: dict[str, Any]) -> AuthoringExecutionOperation:
    kind = data.get("kind", "")
    property_kind = data.get("property_kind", None)
    return AuthoringExecutionOperation(
        operation_id=str(data.get("operation_id", "") or "").strip(),
        kind=AuthoringExecutionOperationKind(str(kind)),
        entity_name=str(data.get("entity_name", "") or "").strip(),
        parent_name=str(data.get("parent_name", "") or "").strip(),
        component_name=str(data.get("component_name", "") or "").strip(),
        component_data=_as_dict(data.get("component_data")),
        field_name=str(data.get("field_name", "") or "").strip(),
        field_value=data.get("field_value"),
        property_kind=(
            AuthoringEntityPropertyKind(str(property_kind))
            if property_kind not in ("", None)
            else None
        ),
        property_value=data.get("property_value"),
        scene_name=str(data.get("scene_name", "") or "").strip(),
        scene_ref=str(data.get("scene_ref", "") or "").strip(),
        save_path=str(data.get("save_path", "") or "").strip(),
        prefab_path=str(data.get("prefab_path", "") or "").strip(),
        prefab_name=str(data.get("prefab_name", "") or "").strip(),
        prefab_parent_name=str(data.get("prefab_parent_name", "") or "").strip(),
        prefab_overrides=_as_dict(data.get("prefab_overrides")),
        scene_flow_key=str(data.get("scene_flow_key", "") or "").strip(),
        scene_flow_target=str(data.get("scene_flow_target", "") or "").strip(),
    )


def parse_verification_scenario(data: dict[str, Any], *, default_project_root: str = "") -> HeadlessVerificationScenario:
    assertions = [parse_verification_assertion(item) for item in _as_list(data.get("assertions"))]
    project_root = str(data.get("project_root", "") or "").strip() or default_project_root
    return HeadlessVerificationScenario(
        scenario_id=str(data.get("scenario_id", "") or "").strip(),
        project_root=project_root,
        scene_path=str(data.get("scene_path", "") or "").strip(),
        assertions=assertions,
        seed=_as_optional_int(data.get("seed")),
        play=bool(data.get("play", False)),
        step_frames=int(data.get("step_frames", 0) or 0),
        recent_event_limit=int(data.get("recent_event_limit", 50) or 50),
    )


def parse_verification_assertion(data: dict[str, Any]) -> HeadlessVerificationAssertion:
    kind = data.get("kind", "")
    return HeadlessVerificationAssertion(
        assertion_id=str(data.get("assertion_id", "") or "").strip(),
        kind=HeadlessVerificationAssertionKind(str(kind)),
        entity_name=str(data.get("entity_name", "") or "").strip(),
        component_name=str(data.get("component_name", "") or "").strip(),
        field_path=str(data.get("field_path", "") or "").strip(),
        expected_value=data.get("expected_value"),
        expected_scene_path=str(data.get("expected_scene_path", "") or "").strip(),
        scene_flow_key=str(data.get("scene_flow_key", "") or "").strip(),
        event_name=str(data.get("event_name", "") or "").strip(),
        event_data_subset=_as_dict(data.get("event_data_subset")),
        expected_state=str(data.get("expected_state", "") or "").strip(),
        min_frame=_as_optional_int(data.get("min_frame")),
        min_entity_count=_as_optional_int(data.get("min_entity_count")),
        max_entity_count=_as_optional_int(data.get("max_entity_count")),
    )


def run_context_pack(project_root: str) -> dict[str, Any]:
    project_service = ProjectService(project_root)
    asset_service = AssetService(project_service)
    artifacts = ProjectContextPackGenerator(project_service, asset_service).generate()
    return artifacts.to_dict()


def run_validation(
    *,
    project_root: str,
    target: str,
    path: str = "",
) -> tuple[int, dict[str, Any]]:
    api: EngineAPI | None = None
    try:
        if target == "active-scene":
            api = EngineAPI(project_root=project_root)
            if path:
                api.load_level(path)
            report = AuthoringValidationService(api).validate_active_scene()
        elif target == "scene-file":
            report = AuthoringValidationService(project_service=ProjectService(project_root)).validate_scene_file(path)
        elif target == "prefab-file":
            report = AuthoringValidationService(project_service=ProjectService(project_root)).validate_prefab_file(path)
        elif target == "scene-transitions":
            if path:
                report = AuthoringValidationService(project_service=ProjectService(project_root)).validate_scene_transition_references(path)
            else:
                api = EngineAPI(project_root=project_root)
                report = AuthoringValidationService(api).validate_scene_transition_references()
        elif target == "project":
            report = AuthoringValidationService(project_service=ProjectService(project_root)).validate_project_lightweight()
        else:
            raise ValueError(f"Unsupported validation target: {target}")
        exit_code = EXIT_OK if report.valid else EXIT_VALIDATION_FAILED
        return exit_code, report.to_dict()
    finally:
        if api is not None:
            api.shutdown()


def run_verification(scenario: HeadlessVerificationScenario) -> tuple[int, dict[str, Any]]:
    report = HeadlessVerificationService().run(scenario)
    exit_code = verification_exit_code(report.to_dict())
    return exit_code, report.to_dict()


def run_workflow(spec: dict[str, Any], *, project_root: str) -> tuple[int, dict[str, Any]]:
    result: dict[str, Any] = {
        "status": "success",
        "exit_code": EXIT_OK,
        "context": None,
        "execution": None,
        "validation": None,
        "verification": None,
    }

    if bool(_as_dict(spec.get("context")).get("enabled", False)):
        result["context"] = run_context_pack(project_root)

    api: EngineAPI | None = None
    try:
        execution_payload = _as_dict(spec.get("authoring_request"))
        validation_payload = _as_dict(spec.get("validation"))
        verification_payload = _as_dict(spec.get("verification"))

        if execution_payload:
            api = EngineAPI(project_root=project_root)
            request = parse_execution_request(execution_payload)
            if request.target_scene_ref:
                api.load_level(request.target_scene_ref)
            execution_result = AuthoringExecutionService(api).execute(request)
            result["execution"] = execution_result.to_dict()
            if execution_result.status != AuthoringExecutionStatus.SUCCESS:
                return EXIT_EXECUTION_FAILED, _failed_workflow_payload(result, EXIT_EXECUTION_FAILED)

            should_validate = bool(validation_payload) or execution_result.validation_required_next
            if should_validate:
                report = _run_workflow_validation(
                    api=api,
                    project_root=project_root,
                    payload=validation_payload,
                )
                result["validation"] = report.to_dict()
                if not report.valid:
                    return EXIT_VALIDATION_FAILED, _failed_workflow_payload(result, EXIT_VALIDATION_FAILED)
        elif validation_payload:
            report = _run_standalone_workflow_validation(project_root=project_root, payload=validation_payload)
            result["validation"] = report.to_dict()
            if not report.valid:
                return EXIT_VALIDATION_FAILED, _failed_workflow_payload(result, EXIT_VALIDATION_FAILED)

        if verification_payload:
            scenario = parse_verification_scenario(verification_payload, default_project_root=project_root)
            verification_report = HeadlessVerificationService().run(scenario)
            result["verification"] = verification_report.to_dict()
            verification_code = verification_exit_code(result["verification"])
            if verification_code != EXIT_OK:
                return verification_code, _failed_workflow_payload(result, verification_code)

        return EXIT_OK, result
    finally:
        if api is not None:
            api.shutdown()


def render_context_summary(payload: dict[str, Any]) -> list[str]:
    pack = payload.get("pack", {})
    return [
        f"[OK] context pack generated: {payload.get('json_path', '')}",
        f"[OK] markdown summary: {payload.get('markdown_path', '')}",
        (
            "[OK] counts: "
            f"scenes={len(_as_list(_as_dict(pack.get('scenes')).get('project_scenes')))} "
            f"assets={len(_as_list(_as_dict(pack.get('assets')).get('catalog')))} "
            f"script_behaviours={len(_as_list(_as_dict(pack.get('script_behaviours')).get('usages')))}"
        ),
    ]


def render_validation_summary(payload: dict[str, Any]) -> list[str]:
    diagnostics = _as_list(payload.get("diagnostics"))
    lines = [
        (
            f"[OK] validation passed: {payload.get('target_reference', '')}"
            if payload.get("valid")
            else f"[ERROR] validation failed: {payload.get('target_reference', '')}"
        ),
        f"[OK] diagnostics: {len(diagnostics)}",
    ]
    for diagnostic in diagnostics:
        code = str(_as_dict(diagnostic).get("code", "") or "")
        message = str(_as_dict(diagnostic).get("message", "") or "")
        lines.append(f"[ERROR] {code}: {message}")
    return lines


def render_verification_summary(payload: dict[str, Any]) -> list[str]:
    assertion_results = _as_list(payload.get("assertion_results"))
    setup_results = _as_list(payload.get("setup_results"))
    lines = [
        (
            f"[OK] verification passed: {payload.get('scene_path', '')}"
            if payload.get("status") == VerificationStatus.PASS
            else f"[ERROR] verification failed: {payload.get('scene_path', '')}"
        ),
        f"[OK] setup steps: {len(setup_results)}",
        f"[OK] assertions: {len(assertion_results)}",
    ]
    for item in assertion_results:
        if not bool(_as_dict(item).get("success")):
            lines.append(f"[ERROR] {item.get('assertion_id', '')}: {item.get('message', '')}")
    if payload.get("failure_summary"):
        lines.append(f"[ERROR] summary: {payload.get('failure_summary')}")
    return lines


def render_workflow_summary(payload: dict[str, Any]) -> list[str]:
    lines = [
        (
            "[OK] workflow completed"
            if int(payload.get("exit_code", EXIT_OK)) == EXIT_OK
            else f"[ERROR] workflow failed with exit code {payload.get('exit_code')}"
        )
    ]
    if payload.get("context"):
        lines.extend(render_context_summary(_as_dict(payload.get("context"))))
    if payload.get("execution"):
        execution = _as_dict(payload.get("execution"))
        lines.append(f"[OK] execution status: {execution.get('status', '')}")
        lines.append(f"[OK] operations applied: {len(_as_list(execution.get('operations_applied')))}")
        for diagnostic in _as_list(execution.get("diagnostics")):
            lines.append(f"[ERROR] {diagnostic.get('code', '')}: {diagnostic.get('message', '')}")
    if payload.get("validation"):
        lines.extend(render_validation_summary(_as_dict(payload.get("validation"))))
    if payload.get("verification"):
        lines.extend(render_verification_summary(_as_dict(payload.get("verification"))))
    return lines


def _run_workflow_validation(
    *,
    api: EngineAPI,
    project_root: str,
    payload: dict[str, Any],
):
    target = str(payload.get("target", "") or "active-scene").strip() or "active-scene"
    path = str(payload.get("path", "") or "").strip()
    service = AuthoringValidationService(api)
    if target == "active-scene":
        if path:
            api.load_level(path)
        return service.validate_active_scene()
    if target == "scene-file":
        return AuthoringValidationService(project_service=ProjectService(project_root)).validate_scene_file(path)
    if target == "prefab-file":
        return AuthoringValidationService(project_service=ProjectService(project_root)).validate_prefab_file(path)
    if target == "scene-transitions":
        return (
            AuthoringValidationService(project_service=ProjectService(project_root)).validate_scene_transition_references(path)
            if path
            else service.validate_scene_transition_references()
        )
    if target == "project":
        return AuthoringValidationService(project_service=ProjectService(project_root)).validate_project_lightweight()
    raise ValueError(f"Unsupported workflow validation target: {target}")


def _run_standalone_workflow_validation(*, project_root: str, payload: dict[str, Any]):
    target = str(payload.get("target", "") or "project").strip() or "project"
    path = str(payload.get("path", "") or "").strip()
    service = AuthoringValidationService(project_service=ProjectService(project_root))
    if target == "scene-file":
        return service.validate_scene_file(path)
    if target == "prefab-file":
        return service.validate_prefab_file(path)
    if target == "scene-transitions":
        return service.validate_scene_transition_references(path if path else None)
    if target == "project":
        return service.validate_project_lightweight()
    if target == "active-scene":
        api = EngineAPI(project_root=project_root)
        try:
            if path:
                api.load_level(path)
            return AuthoringValidationService(api).validate_active_scene()
        finally:
            api.shutdown()
    raise ValueError(f"Unsupported workflow validation target: {target}")


def _failed_workflow_payload(payload: dict[str, Any], exit_code: int) -> dict[str, Any]:
    failed = dict(payload)
    failed["status"] = "failed"
    failed["exit_code"] = exit_code
    return failed


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_optional_int(value: Any) -> int | None:
    if value in ("", None):
        return None
    return int(value)


def verification_exit_code(payload: dict[str, Any]) -> int:
    if any(not bool(_as_dict(item).get("success")) for item in _as_list(payload.get("setup_results"))):
        return EXIT_RUNTIME_ERROR
    if payload.get("status") == VerificationStatus.PASS:
        return EXIT_OK
    return EXIT_VERIFICATION_FAILED
