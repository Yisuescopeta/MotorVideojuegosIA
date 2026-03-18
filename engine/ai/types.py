from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _serialize(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


@dataclass
class ProviderPolicy:
    mode: str = "hybrid"
    preferred_provider: str = "rule_based_local"
    model_name: str = ""
    endpoint: str = "http://127.0.0.1:11434"
    api_key: str = ""
    allow_remote_context: bool = False
    remote_redaction_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "preferred_provider": self.preferred_provider,
            "model_name": self.model_name,
            "endpoint": self.endpoint,
            "api_key": self.api_key,
            "allow_remote_context": self.allow_remote_context,
            "remote_redaction_enabled": self.remote_redaction_enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderPolicy":
        if not isinstance(data, dict):
            return cls()
        return cls(
            mode=str(data.get("mode", "hybrid") or "hybrid"),
            preferred_provider=str(data.get("preferred_provider", "rule_based_local") or "rule_based_local"),
            model_name=str(data.get("model_name", "") or ""),
            endpoint=str(data.get("endpoint", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"),
            api_key=str(data.get("api_key", "") or ""),
            allow_remote_context=bool(data.get("allow_remote_context", False)),
            remote_redaction_enabled=bool(data.get("remote_redaction_enabled", True)),
        )


@dataclass
class MutationPolicy:
    allow_scene_changes: bool = True
    allow_prefab_changes: bool = True
    allow_script_changes: bool = False
    allow_engine_changes: bool = False
    require_confirmation: bool = True
    require_python_confirmation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_scene_changes": self.allow_scene_changes,
            "allow_prefab_changes": self.allow_prefab_changes,
            "allow_script_changes": self.allow_script_changes,
            "allow_engine_changes": self.allow_engine_changes,
            "require_confirmation": self.require_confirmation,
            "require_python_confirmation": self.require_python_confirmation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MutationPolicy":
        if not isinstance(data, dict):
            return cls()
        return cls(
            allow_scene_changes=bool(data.get("allow_scene_changes", True)),
            allow_prefab_changes=bool(data.get("allow_prefab_changes", True)),
            allow_script_changes=bool(data.get("allow_script_changes", False)),
            allow_engine_changes=bool(data.get("allow_engine_changes", False)),
            require_confirmation=bool(data.get("require_confirmation", True)),
            require_python_confirmation=bool(data.get("require_python_confirmation", True)),
        )


@dataclass
class AIRequest:
    prompt: str
    mode: str = "auto"
    answers: Dict[str, Any] = field(default_factory=dict)
    confirmed: bool = False
    allow_python: bool = False
    allow_engine_changes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "mode": self.mode,
            "answers": dict(self.answers),
            "confirmed": self.confirmed,
            "allow_python": self.allow_python,
            "allow_engine_changes": self.allow_engine_changes,
        }


@dataclass
class PlanQuestion:
    id: str
    text: str
    rationale: str
    choices: List[str] = field(default_factory=list)
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "rationale": self.rationale,
            "choices": list(self.choices),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanQuestion":
        return cls(
            id=str(data.get("id", "") or ""),
            text=str(data.get("text", "") or ""),
            rationale=str(data.get("rationale", "") or ""),
            choices=[str(item) for item in data.get("choices", [])],
            required=bool(data.get("required", True)),
        )


@dataclass
class CapabilityDescriptor:
    id: str
    name: str
    category: str
    available: bool
    description: str
    evidence: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "available": self.available,
            "description": self.description,
            "evidence": list(self.evidence),
            "tags": list(self.tags),
        }


@dataclass
class CapabilityGap:
    id: str
    title: str
    reason: str
    suggested_track: str
    blocking: bool = True
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "reason": self.reason,
            "suggested_track": self.suggested_track,
            "blocking": self.blocking,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityGap":
        return cls(
            id=str(data.get("id", "") or ""),
            title=str(data.get("title", "") or ""),
            reason=str(data.get("reason", "") or ""),
            suggested_track=str(data.get("suggested_track", "") or ""),
            blocking=bool(data.get("blocking", True)),
            evidence=[str(item) for item in data.get("evidence", [])],
        )


@dataclass
class SkillManifest:
    id: str
    version: int
    domain: str
    summary: str
    trigger_keywords: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    planning_questions: List[PlanQuestion] = field(default_factory=list)
    allowed_operations: List[str] = field(default_factory=list)
    validations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "domain": self.domain,
            "summary": self.summary,
            "trigger_keywords": list(self.trigger_keywords),
            "capabilities": list(self.capabilities),
            "planning_questions": [question.to_dict() for question in self.planning_questions],
            "allowed_operations": list(self.allowed_operations),
            "validations": list(self.validations),
        }


@dataclass
class PlanningSession:
    session_type: str
    summary: str
    assumptions: List[str] = field(default_factory=list)
    questions: List[PlanQuestion] = field(default_factory=list)
    milestones: List[str] = field(default_factory=list)
    gaps: List[CapabilityGap] = field(default_factory=list)
    selected_skills: List[str] = field(default_factory=list)
    execution_intent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_type": self.session_type,
            "summary": self.summary,
            "assumptions": list(self.assumptions),
            "questions": [question.to_dict() for question in self.questions],
            "milestones": list(self.milestones),
            "gaps": [gap.to_dict() for gap in self.gaps],
            "selected_skills": list(self.selected_skills),
            "execution_intent": self.execution_intent,
            "metadata": _serialize(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanningSession":
        return cls(
            session_type=str(data.get("session_type", "") or ""),
            summary=str(data.get("summary", "") or ""),
            assumptions=[str(item) for item in data.get("assumptions", [])],
            questions=[PlanQuestion.from_dict(item) for item in data.get("questions", []) if isinstance(item, dict)],
            milestones=[str(item) for item in data.get("milestones", [])],
            gaps=[CapabilityGap.from_dict(item) for item in data.get("gaps", []) if isinstance(item, dict)],
            selected_skills=[str(item) for item in data.get("selected_skills", [])],
            execution_intent=str(data.get("execution_intent")) if data.get("execution_intent") is not None else None,
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class ExecutionAction:
    id: str
    action_type: str
    summary: str
    args: Dict[str, Any]
    risk: str = "standard"
    requires_confirmation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action_type": self.action_type,
            "summary": self.summary,
            "args": _serialize(self.args),
            "risk": self.risk,
            "requires_confirmation": self.requires_confirmation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionAction":
        return cls(
            id=str(data.get("id", "") or ""),
            action_type=str(data.get("action_type", "") or ""),
            summary=str(data.get("summary", "") or ""),
            args=dict(data.get("args", {}) or {}),
            risk=str(data.get("risk", "standard") or "standard"),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
        )


@dataclass
class ExecutionProposal:
    summary: str
    actions: List[ExecutionAction] = field(default_factory=list)
    validation_plan: List[str] = field(default_factory=list)
    blocked_by_gaps: bool = False
    requires_confirmation: bool = True
    risk_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "actions": [action.to_dict() for action in self.actions],
            "validation_plan": list(self.validation_plan),
            "blocked_by_gaps": self.blocked_by_gaps,
            "requires_confirmation": self.requires_confirmation,
            "risk_notes": list(self.risk_notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionProposal":
        return cls(
            summary=str(data.get("summary", "") or ""),
            actions=[ExecutionAction.from_dict(item) for item in data.get("actions", []) if isinstance(item, dict)],
            validation_plan=[str(item) for item in data.get("validation_plan", [])],
            blocked_by_gaps=bool(data.get("blocked_by_gaps", False)),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            risk_notes=[str(item) for item in data.get("risk_notes", [])],
        )


@dataclass
class ValidationCheck:
    name: str
    success: bool
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationCheck":
        return cls(
            name=str(data.get("name", "") or ""),
            success=bool(data.get("success", False)),
            details=str(data.get("details", "") or ""),
        )


@dataclass
class ValidationReport:
    success: bool
    checks: List[ValidationCheck] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "checks": [check.to_dict() for check in self.checks],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationReport":
        return cls(
            success=bool(data.get("success", False)),
            checks=[ValidationCheck.from_dict(item) for item in data.get("checks", []) if isinstance(item, dict)],
            warnings=[str(item) for item in data.get("warnings", [])],
            errors=[str(item) for item in data.get("errors", [])],
        )


@dataclass
class AIMessage:
    id: str
    role: str
    content: str
    kind: str = "text"
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "kind": self.kind,
            "created_at": self.created_at,
            "metadata": _serialize(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIMessage":
        return cls(
            id=str(data.get("id", "") or ""),
            role=str(data.get("role", "assistant") or "assistant"),
            content=str(data.get("content", "") or ""),
            kind=str(data.get("kind", "text") or "text"),
            created_at=str(data.get("created_at", "") or ""),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class AIToolCall:
    id: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    status: str = "planned"
    read_only: bool = False
    write_scope: str = "scene"
    risk: str = "standard"
    requires_confirmation: bool = True
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "arguments": _serialize(self.arguments),
            "summary": self.summary,
            "status": self.status,
            "read_only": self.read_only,
            "write_scope": self.write_scope,
            "risk": self.risk,
            "requires_confirmation": self.requires_confirmation,
            "result": _serialize(self.result),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIToolCall":
        return cls(
            id=str(data.get("id", "") or ""),
            tool_name=str(data.get("tool_name", "") or ""),
            arguments=dict(data.get("arguments", {}) or {}),
            summary=str(data.get("summary", "") or ""),
            status=str(data.get("status", "planned") or "planned"),
            read_only=bool(data.get("read_only", False)),
            write_scope=str(data.get("write_scope", "scene") or "scene"),
            risk=str(data.get("risk", "standard") or "standard"),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            result=dict(data.get("result", {}) or {}),
        )


@dataclass
class AIDiffSummary:
    summary: str = ""
    entities: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "entities": list(self.entities),
            "files": list(self.files),
            "assets": list(self.assets),
            "tools": list(self.tools),
            "risk_notes": list(self.risk_notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIDiffSummary":
        return cls(
            summary=str(data.get("summary", "") or ""),
            entities=[str(item) for item in data.get("entities", [])],
            files=[str(item) for item in data.get("files", [])],
            assets=[str(item) for item in data.get("assets", [])],
            tools=[str(item) for item in data.get("tools", [])],
            risk_notes=[str(item) for item in data.get("risk_notes", [])],
        )


@dataclass
class AIApprovalRequest:
    id: str
    summary: str
    diff: AIDiffSummary = field(default_factory=AIDiffSummary)
    tool_calls: List[AIToolCall] = field(default_factory=list)
    status: str = "pending"
    mode: str = "build"
    requires_confirmation: bool = True
    allowed_scopes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "diff": self.diff.to_dict(),
            "tool_calls": [tool_call.to_dict() for tool_call in self.tool_calls],
            "status": self.status,
            "mode": self.mode,
            "requires_confirmation": self.requires_confirmation,
            "allowed_scopes": list(self.allowed_scopes),
            "metadata": _serialize(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIApprovalRequest":
        return cls(
            id=str(data.get("id", "") or ""),
            summary=str(data.get("summary", "") or ""),
            diff=AIDiffSummary.from_dict(data.get("diff", {}) or {}),
            tool_calls=[AIToolCall.from_dict(item) for item in data.get("tool_calls", []) if isinstance(item, dict)],
            status=str(data.get("status", "pending") or "pending"),
            mode=str(data.get("mode", "build") or "build"),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            allowed_scopes=[str(item) for item in data.get("allowed_scopes", [])],
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class AIApplyResult:
    success: bool
    applied_tool_calls: List[str] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validation: Optional[ValidationReport] = None
    snapshot_id: str = ""
    undo_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "applied_tool_calls": list(self.applied_tool_calls),
            "results": _serialize(self.results),
            "errors": list(self.errors),
            "validation": self.validation.to_dict() if self.validation is not None else None,
            "snapshot_id": self.snapshot_id,
            "undo_summary": self.undo_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIApplyResult":
        validation_data = data.get("validation")
        return cls(
            success=bool(data.get("success", False)),
            applied_tool_calls=[str(item) for item in data.get("applied_tool_calls", [])],
            results=[dict(item) for item in data.get("results", []) if isinstance(item, dict)],
            errors=[str(item) for item in data.get("errors", [])],
            validation=ValidationReport.from_dict(validation_data) if isinstance(validation_data, dict) else None,
            snapshot_id=str(data.get("snapshot_id", "") or ""),
            undo_summary=str(data.get("undo_summary", "") or ""),
        )


@dataclass
class AIContextWindow:
    prompt: str = ""
    scene_path: str = ""
    selected_entity: str = ""
    entity_count: int = 0
    recent_assets: List[str] = field(default_factory=list)
    recent_scripts: List[str] = field(default_factory=list)
    capabilities: List[Dict[str, Any]] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "scene_path": self.scene_path,
            "selected_entity": self.selected_entity,
            "entity_count": self.entity_count,
            "recent_assets": list(self.recent_assets),
            "recent_scripts": list(self.recent_scripts),
            "capabilities": _serialize(self.capabilities),
            "memory": _serialize(self.memory),
            "tool_results": _serialize(self.tool_results),
            "summary": _serialize(self.summary),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIContextWindow":
        return cls(
            prompt=str(data.get("prompt", "") or ""),
            scene_path=str(data.get("scene_path", "") or ""),
            selected_entity=str(data.get("selected_entity", "") or ""),
            entity_count=int(data.get("entity_count", 0) or 0),
            recent_assets=[str(item) for item in data.get("recent_assets", [])],
            recent_scripts=[str(item) for item in data.get("recent_scripts", [])],
            capabilities=[dict(item) for item in data.get("capabilities", []) if isinstance(item, dict)],
            memory=dict(data.get("memory", {}) or {}),
            tool_results=[dict(item) for item in data.get("tool_results", []) if isinstance(item, dict)],
            summary=dict(data.get("summary", {}) or {}),
        )


@dataclass
class AIPlanResponse:
    summary: str = ""
    reasoning: str = ""
    project_findings: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    blocking_questions: List[PlanQuestion] = field(default_factory=list)
    can_build_now: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "reasoning": self.reasoning,
            "project_findings": list(self.project_findings),
            "next_steps": list(self.next_steps),
            "blocking_questions": [question.to_dict() for question in self.blocking_questions],
            "can_build_now": self.can_build_now,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIPlanResponse":
        return cls(
            summary=str(data.get("summary", "") or ""),
            reasoning=str(data.get("reasoning", "") or ""),
            project_findings=[str(item) for item in data.get("project_findings", [])],
            next_steps=[str(item) for item in data.get("next_steps", [])],
            blocking_questions=[PlanQuestion.from_dict(item) for item in data.get("blocking_questions", []) if isinstance(item, dict)],
            can_build_now=bool(data.get("can_build_now", False)),
        )


@dataclass
class AISession:
    id: str
    title: str
    status: str = "idle"
    mode: str = "plan"
    provider: str = ""
    model_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    prompt: str = ""
    messages: List[AIMessage] = field(default_factory=list)
    pending_questions: List[PlanQuestion] = field(default_factory=list)
    answers: Dict[str, Any] = field(default_factory=dict)
    approval: Optional[AIApprovalRequest] = None
    last_apply: Optional[AIApplyResult] = None
    context_window: AIContextWindow = field(default_factory=AIContextWindow)
    plan_response: AIPlanResponse = field(default_factory=AIPlanResponse)
    last_intent_resolution: Dict[str, Any] = field(default_factory=dict)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    gaps: List[CapabilityGap] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "mode": self.mode,
            "provider": self.provider,
            "model_name": self.model_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "prompt": self.prompt,
            "messages": [message.to_dict() for message in self.messages],
            "pending_questions": [question.to_dict() for question in self.pending_questions],
            "answers": _serialize(self.answers),
            "approval": self.approval.to_dict() if self.approval is not None else None,
            "last_apply": self.last_apply.to_dict() if self.last_apply is not None else None,
            "context_window": self.context_window.to_dict(),
            "plan_response": self.plan_response.to_dict(),
            "last_intent_resolution": _serialize(self.last_intent_resolution),
            "tool_results": _serialize(self.tool_results),
            "gaps": [gap.to_dict() for gap in self.gaps],
            "metadata": _serialize(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AISession":
        approval_data = data.get("approval")
        last_apply_data = data.get("last_apply")
        context_data = data.get("context_window", {}) or {}
        plan_response_data = data.get("plan_response", {}) or {}
        return cls(
            id=str(data.get("id", "") or ""),
            title=str(data.get("title", "") or ""),
            status=str(data.get("status", "idle") or "idle"),
            mode=str(data.get("mode", "plan") or "plan"),
            provider=str(data.get("provider", "") or ""),
            model_name=str(data.get("model_name", "") or ""),
            created_at=str(data.get("created_at", "") or ""),
            updated_at=str(data.get("updated_at", "") or ""),
            prompt=str(data.get("prompt", "") or ""),
            messages=[AIMessage.from_dict(item) for item in data.get("messages", []) if isinstance(item, dict)],
            pending_questions=[PlanQuestion.from_dict(item) for item in data.get("pending_questions", []) if isinstance(item, dict)],
            answers=dict(data.get("answers", {}) or {}),
            approval=AIApprovalRequest.from_dict(approval_data) if isinstance(approval_data, dict) else None,
            last_apply=AIApplyResult.from_dict(last_apply_data) if isinstance(last_apply_data, dict) else None,
            context_window=AIContextWindow.from_dict(context_data),
            plan_response=AIPlanResponse.from_dict(plan_response_data) if isinstance(plan_response_data, dict) else AIPlanResponse(),
            last_intent_resolution=dict(data.get("last_intent_resolution", {}) or {}),
            tool_results=[dict(item) for item in data.get("tool_results", []) if isinstance(item, dict)],
            gaps=[CapabilityGap.from_dict(item) for item in data.get("gaps", []) if isinstance(item, dict)],
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class AIResponse:
    status: str
    mode: str
    message: str
    plan: Optional[PlanningSession] = None
    proposal: Optional[ExecutionProposal] = None
    validation: Optional[ValidationReport] = None
    gaps: List[CapabilityGap] = field(default_factory=list)
    provider: str = ""
    context_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "message": self.message,
            "plan": self.plan.to_dict() if self.plan else None,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "gaps": [gap.to_dict() for gap in self.gaps],
            "provider": self.provider,
            "context_summary": _serialize(self.context_summary),
        }
