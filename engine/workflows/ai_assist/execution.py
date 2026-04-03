from __future__ import annotations

from typing import Any, Callable

from engine.api import EngineAPI
from engine.api.types import ActionResult
from engine.workflows.ai_assist.types import (
    AuthoringEntityPropertyKind,
    AuthoringExecutionDiagnostic,
    AuthoringExecutionFailureStage,
    AuthoringExecutionMode,
    AuthoringExecutionOperation,
    AuthoringExecutionOperationKind,
    AuthoringExecutionOperationResult,
    AuthoringExecutionRequest,
    AuthoringExecutionResult,
    AuthoringExecutionStatus,
    RollbackStatus,
)

# Mixed requests are intentionally rejected. Workspace operations change which
# scene is open, active, and saved, while transactional operations rely on a
# stable active-scene transaction boundary. Callers must split those phases
# into separate requests to keep rollback and persistence behavior predictable.
TRANSACTIONAL_OPERATION_KINDS = {
    AuthoringExecutionOperationKind.CREATE_ENTITY,
    AuthoringExecutionOperationKind.CREATE_CHILD_ENTITY,
    AuthoringExecutionOperationKind.SET_PARENT,
    AuthoringExecutionOperationKind.ADD_COMPONENT,
    AuthoringExecutionOperationKind.REMOVE_COMPONENT,
    AuthoringExecutionOperationKind.EDIT_COMPONENT_FIELD,
    AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY,
    AuthoringExecutionOperationKind.INSTANTIATE_PREFAB,
    AuthoringExecutionOperationKind.SET_SCENE_FLOW_CONNECTION,
}

WORKSPACE_OPERATION_KINDS = {
    AuthoringExecutionOperationKind.CREATE_SCENE,
    AuthoringExecutionOperationKind.OPEN_SCENE,
    AuthoringExecutionOperationKind.ACTIVATE_SCENE,
    AuthoringExecutionOperationKind.SAVE_SCENE,
}

VALIDATION_REQUIRED_KINDS = TRANSACTIONAL_OPERATION_KINDS | {
    AuthoringExecutionOperationKind.CREATE_SCENE,
}


class AuthoringExecutionService:
    def __init__(self, api: EngineAPI) -> None:
        self._api = api

    def execute(self, request: AuthoringExecutionRequest) -> AuthoringExecutionResult:
        diagnostics: list[AuthoringExecutionDiagnostic] = []
        operation_results: list[AuthoringExecutionOperationResult] = []
        operations_applied: list[str] = []
        normalized_request = self._normalize_request(request)

        mode = self._classify_request(normalized_request, diagnostics)
        if mode is None:
            return self._rejected_result(
                normalized_request,
                diagnostics=diagnostics,
                operation_results=operation_results,
                operations_applied=operations_applied,
                failure_stage=AuthoringExecutionFailureStage.REQUEST_VALIDATION,
            )

        if not self._validate_request(normalized_request, mode, diagnostics):
            return self._rejected_result(
                normalized_request,
                diagnostics=diagnostics,
                operation_results=operation_results,
                operations_applied=operations_applied,
                mode=mode,
                failure_stage=AuthoringExecutionFailureStage.REQUEST_VALIDATION,
            )

        transaction_started = False
        rollback_status = (
            RollbackStatus.NOT_APPLICABLE
            if mode == AuthoringExecutionMode.WORKSPACE_ONLY
            else RollbackStatus.NOT_NEEDED
        )

        if mode == AuthoringExecutionMode.TRANSACTIONAL_SCENE_EDIT:
            begin_result = self._api.begin_transaction(normalized_request.label or "authoring_execution")
            if not bool(begin_result.get("success")):
                diagnostics.append(
                    AuthoringExecutionDiagnostic(
                        code="transaction.begin_failed",
                        message=str(begin_result.get("message") or "Transaction start failed"),
                    )
                )
                return AuthoringExecutionResult(
                    request_id=normalized_request.request_id,
                    status=AuthoringExecutionStatus.FAILED,
                    execution_mode=mode,
                    operations_requested=list(normalized_request.operations),
                    operations_applied=operations_applied,
                    operation_results=operation_results,
                    rollback_status=RollbackStatus.NOT_NEEDED,
                    final_target_scene_ref=self._current_scene_ref(),
                    failure_stage=AuthoringExecutionFailureStage.BEGIN_TRANSACTION,
                    failed_operation_id="",
                    validation_required_next=False,
                    diagnostics=diagnostics,
                )
            transaction_started = True

        for operation in normalized_request.operations:
            result = self._execute_operation(operation)
            operation_results.append(result)
            if result.success:
                operations_applied.append(operation.operation_id)
                continue

            diagnostics.append(
                AuthoringExecutionDiagnostic(
                    code="operation.failed",
                    message=result.message or "Operation failed",
                    operation_id=operation.operation_id,
                )
            )
            if transaction_started:
                rollback_status = self._rollback_transaction(diagnostics)
                failure_stage = (
                    AuthoringExecutionFailureStage.OPERATION
                    if rollback_status == RollbackStatus.SUCCEEDED
                    else AuthoringExecutionFailureStage.ROLLBACK_TRANSACTION
                )
                status = (
                    AuthoringExecutionStatus.ROLLED_BACK
                    if rollback_status == RollbackStatus.SUCCEEDED
                    else AuthoringExecutionStatus.FAILED
                )
            else:
                rollback_status = RollbackStatus.NOT_APPLICABLE
                status = AuthoringExecutionStatus.FAILED
                failure_stage = AuthoringExecutionFailureStage.OPERATION
            return AuthoringExecutionResult(
                request_id=normalized_request.request_id,
                status=status,
                execution_mode=mode,
                operations_requested=list(normalized_request.operations),
                operations_applied=operations_applied,
                operation_results=operation_results,
                rollback_status=rollback_status,
                final_target_scene_ref=self._current_scene_ref(),
                failure_stage=failure_stage,
                failed_operation_id=operation.operation_id,
                validation_required_next=self._requires_validation(operations_applied, normalized_request),
                diagnostics=diagnostics,
            )

        if transaction_started:
            commit_result = self._api.commit_transaction()
            if not bool(commit_result.get("success")):
                diagnostics.append(
                    AuthoringExecutionDiagnostic(
                        code="transaction.commit_failed",
                        message=str(commit_result.get("message") or "Transaction commit failed"),
                    )
                )
                rollback_status = self._rollback_transaction(diagnostics)
                failure_stage = (
                    AuthoringExecutionFailureStage.COMMIT_TRANSACTION
                    if rollback_status == RollbackStatus.SUCCEEDED
                    else AuthoringExecutionFailureStage.ROLLBACK_TRANSACTION
                )
                status = (
                    AuthoringExecutionStatus.ROLLED_BACK
                    if rollback_status == RollbackStatus.SUCCEEDED
                    else AuthoringExecutionStatus.FAILED
                )
                return AuthoringExecutionResult(
                    request_id=normalized_request.request_id,
                    status=status,
                    execution_mode=mode,
                    operations_requested=list(normalized_request.operations),
                    operations_applied=operations_applied,
                    operation_results=operation_results,
                    rollback_status=rollback_status,
                    final_target_scene_ref=self._current_scene_ref(),
                    failure_stage=failure_stage,
                    failed_operation_id="",
                    validation_required_next=self._requires_validation(operations_applied, normalized_request),
                    diagnostics=diagnostics,
                )

        return AuthoringExecutionResult(
            request_id=normalized_request.request_id,
            status=AuthoringExecutionStatus.SUCCESS,
            execution_mode=mode,
            operations_requested=list(normalized_request.operations),
            operations_applied=operations_applied,
            operation_results=operation_results,
            rollback_status=rollback_status,
            final_target_scene_ref=self._current_scene_ref(),
            failure_stage=AuthoringExecutionFailureStage.NONE,
            failed_operation_id="",
            validation_required_next=self._requires_validation(operations_applied, normalized_request),
            diagnostics=diagnostics,
        )

    def _normalize_request(self, request: AuthoringExecutionRequest) -> AuthoringExecutionRequest:
        return AuthoringExecutionRequest(
            request_id=str(request.request_id or "").strip(),
            label=str(request.label or "").strip() or "authoring_execution",
            operations=[self._normalize_operation(operation) for operation in request.operations],
            target_scene_ref=str(request.target_scene_ref or "").strip(),
            metadata=dict(request.metadata),
        )

    def _normalize_operation(self, operation: AuthoringExecutionOperation) -> AuthoringExecutionOperation:
        kind: Any = operation.kind
        if not isinstance(kind, AuthoringExecutionOperationKind):
            try:
                kind = AuthoringExecutionOperationKind(str(kind))
            except ValueError:
                kind = str(kind)

        property_kind: Any = operation.property_kind
        if property_kind is not None and not isinstance(property_kind, AuthoringEntityPropertyKind):
            try:
                property_kind = AuthoringEntityPropertyKind(str(property_kind))
            except ValueError:
                property_kind = str(property_kind)

        return AuthoringExecutionOperation(
            operation_id=str(operation.operation_id or "").strip(),
            kind=kind,
            entity_name=str(operation.entity_name or "").strip(),
            parent_name=str(operation.parent_name or "").strip(),
            component_name=str(operation.component_name or "").strip(),
            component_data=self._copy_dict(operation.component_data),
            field_name=str(operation.field_name or "").strip(),
            field_value=operation.field_value,
            property_kind=property_kind,
            property_value=operation.property_value,
            scene_name=str(operation.scene_name or "").strip(),
            scene_ref=str(operation.scene_ref or "").strip(),
            save_path=str(operation.save_path or "").strip(),
            prefab_path=str(operation.prefab_path or "").strip(),
            prefab_name=str(operation.prefab_name or "").strip(),
            prefab_parent_name=str(operation.prefab_parent_name or "").strip(),
            prefab_overrides=self._copy_dict(operation.prefab_overrides),
            scene_flow_key=str(operation.scene_flow_key or "").strip(),
            scene_flow_target=str(operation.scene_flow_target or "").strip(),
        )

    def _classify_request(
        self,
        request: AuthoringExecutionRequest,
        diagnostics: list[AuthoringExecutionDiagnostic],
    ) -> AuthoringExecutionMode | None:
        if not request.operations:
            diagnostics.append(
                AuthoringExecutionDiagnostic(
                    code="request.empty_operations",
                    message="Authoring execution request must contain at least one operation.",
                )
            )
            return None

        kinds = {operation.kind for operation in request.operations}
        if kinds & TRANSACTIONAL_OPERATION_KINDS and kinds & WORKSPACE_OPERATION_KINDS:
            conflicting_modes = []
            if kinds & WORKSPACE_OPERATION_KINDS:
                conflicting_modes.append(AuthoringExecutionMode.WORKSPACE_ONLY.value)
            if kinds & TRANSACTIONAL_OPERATION_KINDS:
                conflicting_modes.append(AuthoringExecutionMode.TRANSACTIONAL_SCENE_EDIT.value)
            diagnostics.append(
                AuthoringExecutionDiagnostic(
                    code="request.mixed_execution_modes",
                    message=(
                        "Mixed workspace and transactional operations are not allowed in one execution request. "
                        f"Detected modes: {', '.join(conflicting_modes)}."
                    ),
                )
            )
            diagnostics.append(
                AuthoringExecutionDiagnostic(
                    code="request.mixed_execution_modes.operations",
                    message="Conflicting operations: "
                    + ", ".join(
                        f"{operation.operation_id}:{getattr(operation.kind, 'value', operation.kind)}"
                        for operation in request.operations
                    ),
                )
            )
            return None
        if kinds <= WORKSPACE_OPERATION_KINDS:
            return AuthoringExecutionMode.WORKSPACE_ONLY
        return AuthoringExecutionMode.TRANSACTIONAL_SCENE_EDIT

    def _validate_request(
        self,
        request: AuthoringExecutionRequest,
        mode: AuthoringExecutionMode,
        diagnostics: list[AuthoringExecutionDiagnostic],
    ) -> bool:
        valid = True
        for operation in request.operations:
            code, message = self._validate_operation(operation)
            if code:
                diagnostics.append(
                    AuthoringExecutionDiagnostic(
                        code=code,
                        message=message,
                        operation_id=operation.operation_id,
                    )
                )
                valid = False

        if mode == AuthoringExecutionMode.TRANSACTIONAL_SCENE_EDIT:
            active_scene = self._api.get_active_scene()
            if not active_scene:
                diagnostics.append(
                    AuthoringExecutionDiagnostic(
                        code="request.no_active_scene",
                        message="Transactional authoring execution requires an active scene.",
                    )
                )
                valid = False
            elif request.target_scene_ref and not self._matches_active_scene(request.target_scene_ref, active_scene):
                diagnostics.append(
                    AuthoringExecutionDiagnostic(
                        code="request.target_scene_mismatch",
                        message="Transactional authoring request target_scene_ref does not match the active scene.",
                    )
                )
                valid = False

        return valid

    def _validate_operation(self, operation: AuthoringExecutionOperation) -> tuple[str, str]:
        if not operation.operation_id.strip():
            return ("operation.missing_id", "Operation id is required.")
        if not isinstance(operation.kind, AuthoringExecutionOperationKind):
            return ("operation.invalid_kind", "Operation kind is not supported.")

        kind = operation.kind
        if kind in {
            AuthoringExecutionOperationKind.CREATE_ENTITY,
            AuthoringExecutionOperationKind.CREATE_SCENE,
        } and not operation.entity_name.strip() and not operation.scene_name.strip():
            if kind == AuthoringExecutionOperationKind.CREATE_ENTITY:
                return ("operation.missing_entity_name", "create_entity requires entity_name.")
            return ("operation.missing_scene_name", "create_scene requires scene_name.")

        if kind == AuthoringExecutionOperationKind.CREATE_ENTITY and not operation.entity_name.strip():
            return ("operation.missing_entity_name", "create_entity requires entity_name.")
        if kind == AuthoringExecutionOperationKind.CREATE_CHILD_ENTITY:
            if not operation.entity_name.strip():
                return ("operation.missing_entity_name", "create_child_entity requires entity_name.")
            if not operation.parent_name.strip():
                return ("operation.missing_parent_name", "create_child_entity requires parent_name.")
        if kind == AuthoringExecutionOperationKind.SET_PARENT and not operation.entity_name.strip():
            return ("operation.missing_entity_name", "set_parent requires entity_name.")
        if kind in {
            AuthoringExecutionOperationKind.ADD_COMPONENT,
            AuthoringExecutionOperationKind.REMOVE_COMPONENT,
        }:
            if not operation.entity_name.strip():
                return ("operation.missing_entity_name", f"{kind.value} requires entity_name.")
            if not operation.component_name.strip():
                return ("operation.missing_component_name", f"{kind.value} requires component_name.")
        if kind == AuthoringExecutionOperationKind.EDIT_COMPONENT_FIELD:
            if not operation.entity_name.strip():
                return ("operation.missing_entity_name", "edit_component_field requires entity_name.")
            if not operation.component_name.strip():
                return ("operation.missing_component_name", "edit_component_field requires component_name.")
            if not operation.field_name.strip():
                return ("operation.missing_field_name", "edit_component_field requires field_name.")
        if kind == AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY:
            if not operation.entity_name.strip():
                return ("operation.missing_entity_name", "set_entity_property requires entity_name.")
            if operation.property_kind not in set(AuthoringEntityPropertyKind):
                return ("operation.invalid_property_kind", "set_entity_property requires property_kind active, tag, or layer.")
            if operation.property_value is None:
                return ("operation.missing_property_value", "set_entity_property requires property_value.")
        if kind in {
            AuthoringExecutionOperationKind.OPEN_SCENE,
            AuthoringExecutionOperationKind.ACTIVATE_SCENE,
        } and not operation.scene_ref.strip():
            return ("operation.missing_scene_ref", f"{kind.value} requires scene_ref.")
        if kind == AuthoringExecutionOperationKind.INSTANTIATE_PREFAB and not operation.prefab_path.strip():
            return ("operation.missing_prefab_path", "instantiate_prefab requires prefab_path.")
        if kind == AuthoringExecutionOperationKind.SET_SCENE_FLOW_CONNECTION and not operation.scene_flow_key.strip():
            return ("operation.missing_scene_flow_key", "set_scene_flow_connection requires scene_flow_key.")
        return ("", "")

    def _matches_active_scene(self, target_scene_ref: str, active_scene: dict[str, Any]) -> bool:
        normalized_target = str(target_scene_ref or "").strip()
        candidates = {
            str(active_scene.get("key", "") or "").strip(),
            str(active_scene.get("path", "") or "").strip(),
        }
        active_path = str(active_scene.get("path", "") or "").strip()
        if self._api.project_service is not None:
            try:
                candidates.add(self._api.project_service.resolve_path(target_scene_ref).as_posix())
            except Exception:
                pass
            if active_path:
                try:
                    candidates.add(self._api.project_service.to_relative_path(active_path))
                except Exception:
                    pass
        return normalized_target in {candidate for candidate in candidates if candidate}

    def _execute_operation(self, operation: AuthoringExecutionOperation) -> AuthoringExecutionOperationResult:
        try:
            action_result = self._dispatch_operation(operation)
        except Exception as exc:
            return AuthoringExecutionOperationResult(
                operation_id=operation.operation_id,
                kind=operation.kind,
                success=False,
                message=str(exc),
                data=None,
            )

        return AuthoringExecutionOperationResult(
            operation_id=operation.operation_id,
            kind=operation.kind,
            success=bool(action_result.get("success")),
            message=str(action_result.get("message") or ""),
            data=action_result.get("data"),
        )

    def _dispatch_operation(self, operation: AuthoringExecutionOperation) -> ActionResult:
        dispatch: dict[AuthoringExecutionOperationKind, Callable[[AuthoringExecutionOperation], ActionResult]] = {
            AuthoringExecutionOperationKind.CREATE_ENTITY: self._op_create_entity,
            AuthoringExecutionOperationKind.CREATE_CHILD_ENTITY: self._op_create_child_entity,
            AuthoringExecutionOperationKind.SET_PARENT: self._op_set_parent,
            AuthoringExecutionOperationKind.ADD_COMPONENT: self._op_add_component,
            AuthoringExecutionOperationKind.REMOVE_COMPONENT: self._op_remove_component,
            AuthoringExecutionOperationKind.EDIT_COMPONENT_FIELD: self._op_edit_component_field,
            AuthoringExecutionOperationKind.SET_ENTITY_PROPERTY: self._op_set_entity_property,
            AuthoringExecutionOperationKind.CREATE_SCENE: self._op_create_scene,
            AuthoringExecutionOperationKind.OPEN_SCENE: self._op_open_scene,
            AuthoringExecutionOperationKind.ACTIVATE_SCENE: self._op_activate_scene,
            AuthoringExecutionOperationKind.SAVE_SCENE: self._op_save_scene,
            AuthoringExecutionOperationKind.INSTANTIATE_PREFAB: self._op_instantiate_prefab,
            AuthoringExecutionOperationKind.SET_SCENE_FLOW_CONNECTION: self._op_set_scene_flow_connection,
        }
        handler = dispatch[operation.kind]
        return handler(operation)

    def _op_create_entity(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.create_entity(operation.entity_name, components=self._copy_dict(operation.component_data))

    def _op_create_child_entity(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.create_child_entity(
            operation.parent_name,
            operation.entity_name,
            components=self._copy_dict(operation.component_data),
        )

    def _op_set_parent(self, operation: AuthoringExecutionOperation) -> ActionResult:
        parent_name = operation.parent_name.strip() or None
        return self._api.set_entity_parent(operation.entity_name, parent_name)

    def _op_add_component(self, operation: AuthoringExecutionOperation) -> ActionResult:
        payload = self._copy_dict(operation.component_data)
        return self._api.add_component(operation.entity_name, operation.component_name, data=payload or None)

    def _op_remove_component(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.remove_component(operation.entity_name, operation.component_name)

    def _op_edit_component_field(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.edit_component(
            operation.entity_name,
            operation.component_name,
            operation.field_name,
            operation.field_value,
        )

    def _op_set_entity_property(self, operation: AuthoringExecutionOperation) -> ActionResult:
        if operation.property_kind == AuthoringEntityPropertyKind.ACTIVE:
            return self._api.set_entity_active(operation.entity_name, bool(operation.property_value))
        if operation.property_kind == AuthoringEntityPropertyKind.TAG:
            return self._api.set_entity_tag(operation.entity_name, str(operation.property_value))
        return self._api.set_entity_layer(operation.entity_name, str(operation.property_value))

    def _op_create_scene(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.create_scene(operation.scene_name)

    def _op_open_scene(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.open_scene(operation.scene_ref)

    def _op_activate_scene(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.activate_scene(operation.scene_ref)

    def _op_save_scene(self, operation: AuthoringExecutionOperation) -> ActionResult:
        scene_ref = operation.scene_ref.strip() or None
        save_path = operation.save_path.strip() or None
        return self._api.save_scene(key_or_path=scene_ref, path=save_path)

    def _op_instantiate_prefab(self, operation: AuthoringExecutionOperation) -> ActionResult:
        prefab_name = operation.prefab_name.strip() or None
        prefab_parent = operation.prefab_parent_name.strip() or None
        overrides = self._copy_dict(operation.prefab_overrides)
        return self._api.instantiate_prefab(
            operation.prefab_path,
            name=prefab_name,
            parent=prefab_parent,
            overrides=overrides or None,
        )

    def _op_set_scene_flow_connection(self, operation: AuthoringExecutionOperation) -> ActionResult:
        return self._api.set_scene_connection(operation.scene_flow_key, operation.scene_flow_target)

    def _rollback_transaction(
        self,
        diagnostics: list[AuthoringExecutionDiagnostic],
    ) -> RollbackStatus:
        rollback_result = self._api.rollback_transaction()
        if bool(rollback_result.get("success")):
            return RollbackStatus.SUCCEEDED
        diagnostics.append(
            AuthoringExecutionDiagnostic(
                code="transaction.rollback_failed",
                message=str(rollback_result.get("message") or "Transaction rollback failed"),
            )
        )
        return RollbackStatus.FAILED

    def _requires_validation(
        self,
        operations_applied: list[str],
        request: AuthoringExecutionRequest,
    ) -> bool:
        applied_ids = set(operations_applied)
        return any(
            operation.operation_id in applied_ids and operation.kind in VALIDATION_REQUIRED_KINDS
            for operation in request.operations
        )

    def _rejected_result(
        self,
        request: AuthoringExecutionRequest,
        *,
        diagnostics: list[AuthoringExecutionDiagnostic],
        operation_results: list[AuthoringExecutionOperationResult],
        operations_applied: list[str],
        mode: AuthoringExecutionMode | None = None,
        failure_stage: AuthoringExecutionFailureStage = AuthoringExecutionFailureStage.REQUEST_VALIDATION,
    ) -> AuthoringExecutionResult:
        return AuthoringExecutionResult(
            request_id=request.request_id,
            status=AuthoringExecutionStatus.REJECTED,
            execution_mode=mode,
            operations_requested=list(request.operations),
            operations_applied=operations_applied,
            operation_results=operation_results,
            rollback_status=RollbackStatus.NOT_APPLICABLE,
            final_target_scene_ref=self._current_scene_ref(),
            failure_stage=failure_stage,
            failed_operation_id="",
            validation_required_next=False,
            diagnostics=diagnostics,
        )

    def _current_scene_ref(self) -> str:
        active_scene = self._api.get_active_scene()
        current = str(active_scene.get("path") or active_scene.get("key") or "")
        project_service = getattr(self._api, "project_service", None)
        if not current or project_service is None:
            return current
        try:
            return project_service.to_relative_path(current)
        except Exception:
            return current.replace("\\", "/")

    def _copy_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(payload) if isinstance(payload, dict) else {}
