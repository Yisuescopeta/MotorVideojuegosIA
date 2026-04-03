from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthoringOperationKind(StrEnum):
    SCENE_EDIT = "scene_edit"
    PREFAB_EDIT = "prefab_edit"
    SCRIPT_EDIT = "script_edit"
    ASSET_METADATA_EDIT = "asset_metadata_edit"
    ANALYSIS_ONLY = "analysis_only"


class PlanStepKind(StrEnum):
    CHECK = "check"
    ENGINE_API_CALL = "engine_api_call"
    VALIDATE = "validate"
    VERIFY = "verify"


class ValidationIssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationDiagnosticCategory(StrEnum):
    SCENE_SCHEMA = "scene_schema"
    PREFAB_SCHEMA = "prefab_schema"
    SCENE_HIERARCHY = "scene_hierarchy"
    SCENE_TRANSITION = "scene_transition"
    SCENE_FLOW = "scene_flow"
    FEATURE_METADATA = "feature_metadata"
    PROJECT_CONSISTENCY = "project_consistency"
    WORKSPACE_REFERENCE = "workspace_reference"
    IO = "io"


class ValidationTargetKind(StrEnum):
    ACTIVE_SCENE = "active_scene"
    SCENE_FILE = "scene_file"
    PREFAB_FILE = "prefab_file"
    PROJECT = "project"


class ValidationStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class VerificationMode(StrEnum):
    NONE = "none"
    HEADLESS_CAPTURE = "headless_capture"
    SCRIPT_COMMANDS = "script_commands"


class VerificationStatus(StrEnum):
    NOT_RUN = "not_run"
    PASS = "pass"
    FAIL = "fail"


class HeadlessVerificationAssertionKind(StrEnum):
    ENTITY_EXISTS = "entity_exists"
    ENTITY_NOT_EXISTS = "entity_not_exists"
    COMPONENT_EXISTS = "component_exists"
    COMPONENT_NOT_EXISTS = "component_not_exists"
    COMPONENT_FIELD_EQUALS = "component_field_equals"
    SELECTED_SCENE_IS = "selected_scene_is"
    SCENE_FLOW_TARGET_CAN_BE_LOADED = "scene_flow_target_can_be_loaded"
    RECENT_EVENT_EXISTS = "recent_event_exists"
    ENGINE_STATUS_SANITY = "engine_status_sanity"


class WorkflowStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    VERIFIED = "verified"
    FAILED = "failed"


class ContextPackSourceKind(StrEnum):
    SCENE = "scene"
    PREFAB = "prefab"


class AuthoringExecutionMode(StrEnum):
    TRANSACTIONAL_SCENE_EDIT = "transactional_scene_edit"
    WORKSPACE_ONLY = "workspace_only"


class AuthoringExecutionOperationKind(StrEnum):
    CREATE_ENTITY = "create_entity"
    CREATE_CHILD_ENTITY = "create_child_entity"
    SET_PARENT = "set_parent"
    ADD_COMPONENT = "add_component"
    REMOVE_COMPONENT = "remove_component"
    EDIT_COMPONENT_FIELD = "edit_component_field"
    SET_ENTITY_PROPERTY = "set_entity_property"
    CREATE_SCENE = "create_scene"
    OPEN_SCENE = "open_scene"
    ACTIVATE_SCENE = "activate_scene"
    SAVE_SCENE = "save_scene"
    INSTANTIATE_PREFAB = "instantiate_prefab"
    SET_SCENE_FLOW_CONNECTION = "set_scene_flow_connection"


class AuthoringEntityPropertyKind(StrEnum):
    ACTIVE = "active"
    TAG = "tag"
    LAYER = "layer"


class AuthoringExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class RollbackStatus(StrEnum):
    NOT_NEEDED = "not_needed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class AuthoringExecutionFailureStage(StrEnum):
    NONE = "none"
    REQUEST_VALIDATION = "request_validation"
    BEGIN_TRANSACTION = "begin_transaction"
    OPERATION = "operation"
    COMMIT_TRANSACTION = "commit_transaction"
    ROLLBACK_TRANSACTION = "rollback_transaction"


@dataclass(frozen=True)
class SceneContextEntry:
    key: str
    name: str
    path: str
    dirty: bool = False
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssetInventoryEntry:
    path: str
    asset_kind: str = ""
    guid: str = ""
    importer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectContextSnapshot:
    snapshot_id: str
    created_at: str
    project_root: str
    project_name: str
    current_scene_name: str = ""
    current_scene_path: str = ""
    open_scenes: list[SceneContextEntry] = field(default_factory=list)
    feature_metadata: dict[str, Any] = field(default_factory=dict)
    asset_summaries: list[AssetInventoryEntry] = field(default_factory=list)
    prefab_paths: list[str] = field(default_factory=list)
    script_paths: list[str] = field(default_factory=list)
    runtime_mode: str = ""
    selected_entity_name: str | None = None

    @property
    def asset_count(self) -> int:
        return len(self.asset_summaries)

    @property
    def prefab_count(self) -> int:
        return len(self.prefab_paths)

    @property
    def script_count(self) -> int:
        return len(self.script_paths)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["asset_count"] = self.asset_count
        payload["prefab_count"] = self.prefab_count
        payload["script_count"] = self.script_count
        return payload


@dataclass(frozen=True)
class AuthoringRequest:
    workflow_id: str
    goal: str
    operation_kind: AuthoringOperationKind
    verification_mode: VerificationMode = VerificationMode.NONE
    target_scene_path: str = ""
    target_prefab_path: str = ""
    target_script_path: str = ""
    target_asset_path: str = ""
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthoringPlanStep:
    step_id: str
    kind: PlanStepKind
    description: str
    engine_api_call: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthoringPlan:
    plan_id: str
    request_id: str
    steps: list[AuthoringPlanStep] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    requires_engine_mutation: bool = False
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationIssueSeverity
    blocking: bool = False
    target: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    status: ValidationStatus
    checked_artifacts: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def blocking_issue_count(self) -> int:
        return sum(1 for issue in self.issues if issue.blocking)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blocking_issue_count"] = self.blocking_issue_count
        return payload


@dataclass(frozen=True)
class ValidationDiagnostic:
    severity: ValidationDiagnosticSeverity
    category: ValidationDiagnosticCategory
    code: str
    message: str
    reference: str
    source_file: str = ""
    path: str = ""
    target_kind: ValidationTargetKind | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationDiagnosticsReport:
    target_kind: ValidationTargetKind
    target_reference: str
    valid: bool
    diagnostics: list[ValidationDiagnostic] = field(default_factory=list)
    raw_messages: list[str] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationEvidence:
    kind: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeadlessVerificationAssertion:
    assertion_id: str
    kind: HeadlessVerificationAssertionKind
    entity_name: str = ""
    component_name: str = ""
    field_path: str = ""
    expected_value: Any = None
    expected_scene_path: str = ""
    scene_flow_key: str = ""
    event_name: str = ""
    event_data_subset: dict[str, Any] = field(default_factory=dict)
    expected_state: str = ""
    min_frame: int | None = None
    min_entity_count: int | None = None
    max_entity_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            key: value
            for key, value in payload.items()
            if value not in ("", None, {})
        }


@dataclass(frozen=True)
class HeadlessVerificationScenario:
    scenario_id: str
    project_root: str
    scene_path: str
    assertions: list[HeadlessVerificationAssertion] = field(default_factory=list)
    seed: int | None = None
    play: bool = False
    step_frames: int = 0
    recent_event_limit: int = 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "project_root": self.project_root,
            "scene_path": self.scene_path,
            "assertions": [assertion.to_dict() for assertion in self.assertions],
            "seed": self.seed,
            "play": self.play,
            "step_frames": self.step_frames,
            "recent_event_limit": self.recent_event_limit,
        }


@dataclass(frozen=True)
class HeadlessVerificationSetupResult:
    step: str
    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeadlessVerificationAssertionResult:
    assertion_id: str
    kind: HeadlessVerificationAssertionKind
    success: bool
    message: str = ""
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeadlessVerificationReport:
    scenario_id: str
    status: VerificationStatus
    project_root: str
    scene_path: str
    setup_results: list[HeadlessVerificationSetupResult] = field(default_factory=list)
    assertion_results: list[HeadlessVerificationAssertionResult] = field(default_factory=list)
    final_engine_status: dict[str, Any] = field(default_factory=dict)
    final_active_scene: dict[str, Any] = field(default_factory=dict)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    failure_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "project_root": self.project_root,
            "scene_path": self.scene_path,
            "setup_results": [result.to_dict() for result in self.setup_results],
            "assertion_results": [result.to_dict() for result in self.assertion_results],
            "final_engine_status": dict(self.final_engine_status),
            "final_active_scene": dict(self.final_active_scene),
            "recent_events": list(self.recent_events),
            "failure_summary": self.failure_summary,
        }


@dataclass(frozen=True)
class VerificationReport:
    status: VerificationStatus
    executed_checks: list[str] = field(default_factory=list)
    evidences: list[VerificationEvidence] = field(default_factory=list)
    runtime_details: dict[str, Any] = field(default_factory=dict)
    failure_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowResultSummary:
    workflow_id: str
    status: WorkflowStatus
    context_snapshot_id: str = ""
    plan_id: str = ""
    changed_targets: list[str] = field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.PASS
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN
    next_step: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthoringExecutionOperation:
    operation_id: str
    kind: AuthoringExecutionOperationKind
    entity_name: str = ""
    parent_name: str = ""
    component_name: str = ""
    component_data: dict[str, Any] = field(default_factory=dict)
    field_name: str = ""
    field_value: Any = None
    property_kind: AuthoringEntityPropertyKind | None = None
    property_value: Any = None
    scene_name: str = ""
    scene_ref: str = ""
    save_path: str = ""
    prefab_path: str = ""
    prefab_name: str = ""
    prefab_parent_name: str = ""
    prefab_overrides: dict[str, Any] = field(default_factory=dict)
    scene_flow_key: str = ""
    scene_flow_target: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            key: value
            for key, value in payload.items()
            if value not in ("", None, {})
        }


@dataclass(frozen=True)
class AuthoringExecutionRequest:
    request_id: str
    label: str
    operations: list[AuthoringExecutionOperation] = field(default_factory=list)
    target_scene_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "label": self.label,
            "operations": [operation.to_dict() for operation in self.operations],
            "target_scene_ref": self.target_scene_ref,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AuthoringExecutionOperationResult:
    operation_id: str
    kind: AuthoringExecutionOperationKind
    success: bool
    message: str = ""
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthoringExecutionDiagnostic:
    code: str
    message: str
    operation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthoringExecutionResult:
    request_id: str
    status: AuthoringExecutionStatus
    execution_mode: AuthoringExecutionMode | None = None
    operations_requested: list[AuthoringExecutionOperation] = field(default_factory=list)
    operations_applied: list[str] = field(default_factory=list)
    operation_results: list[AuthoringExecutionOperationResult] = field(default_factory=list)
    rollback_status: RollbackStatus = RollbackStatus.NOT_APPLICABLE
    final_target_scene_ref: str = ""
    failure_stage: AuthoringExecutionFailureStage = AuthoringExecutionFailureStage.NONE
    failed_operation_id: str = ""
    validation_required_next: bool = False
    diagnostics: list[AuthoringExecutionDiagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "execution_mode": self.execution_mode,
            "operations_requested": [operation.to_dict() for operation in self.operations_requested],
            "operations_applied": list(self.operations_applied),
            "operation_results": [result.to_dict() for result in self.operation_results],
            "rollback_status": self.rollback_status,
            "final_target_scene_ref": self.final_target_scene_ref,
            "failure_stage": self.failure_stage,
            "failed_operation_id": self.failed_operation_id,
            "validation_required_next": self.validation_required_next,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


@dataclass(frozen=True)
class ContextPackSceneRecord:
    name: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackOpenSceneRecord:
    key: str
    name: str
    path: str
    dirty: bool = False
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackAssetRecord:
    path: str
    guid: str = ""
    asset_kind: str = ""
    importer: str = ""
    labels: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackAssetMetadataRecord:
    path: str
    guid: str = ""
    asset_kind: str = ""
    importer: str = ""
    asset_type: str = ""
    import_mode: str = ""
    labels: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    import_settings: dict[str, Any] = field(default_factory=dict)
    slices_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackPublicDataField:
    key: str
    value_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackScriptBehaviourUsage:
    source_kind: ContextPackSourceKind
    source_path: str
    entity_name: str
    script_path: str = ""
    module_path: str = ""
    run_in_edit_mode: bool = False
    public_data_shape: list[ContextPackPublicDataField] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackProjectSection:
    manifest: dict[str, Any]
    important_paths: dict[str, str]
    startup_scene: str
    editor_state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackSceneSection:
    project_scenes: list[ContextPackSceneRecord] = field(default_factory=list)
    active_scene: dict[str, Any] = field(default_factory=dict)
    open_scenes: list[ContextPackOpenSceneRecord] = field(default_factory=list)
    active_scene_flow_connections: dict[str, str] = field(default_factory=dict)
    transition_summaries: list[dict[str, Any]] = field(default_factory=list)
    transition_rows: list[dict[str, Any]] = field(default_factory=list)
    transition_issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackAssetSection:
    catalog: list[ContextPackAssetRecord] = field(default_factory=list)
    prefabs: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    relevant_metadata: list[ContextPackAssetMetadataRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackFeatureSection:
    sorting_layers: list[str] = field(default_factory=list)
    physics_backend_selection: dict[str, Any] = field(default_factory=dict)
    physics_metadata: list[dict[str, Any]] = field(default_factory=list)
    scene_flow_metadata: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextPackScriptBehaviourSection:
    usages: list[ContextPackScriptBehaviourUsage] = field(default_factory=list)

    @property
    def module_paths(self) -> list[str]:
        return sorted({usage.module_path for usage in self.usages if usage.module_path})

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["module_paths"] = self.module_paths
        return payload


@dataclass(frozen=True)
class ProjectContextPack:
    schema_version: int
    project: ContextPackProjectSection
    scenes: ContextPackSceneSection
    assets: ContextPackAssetSection
    features: ContextPackFeatureSection
    script_behaviours: ContextPackScriptBehaviourSection

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project": self.project.to_dict(),
            "scenes": self.scenes.to_dict(),
            "assets": self.assets.to_dict(),
            "features": self.features.to_dict(),
            "script_behaviours": self.script_behaviours.to_dict(),
        }


@dataclass(frozen=True)
class ProjectContextPackArtifacts:
    json_path: str
    markdown_path: str
    pack: ProjectContextPack

    def to_dict(self) -> dict[str, Any]:
        return {
            "json_path": self.json_path,
            "markdown_path": self.markdown_path,
            "pack": self.pack.to_dict(),
        }
