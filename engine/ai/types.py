from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderPolicy:
    mode: str = "hybrid"
    preferred_provider: str = "rule_based_local"
    model_name: str = ""
    endpoint: str = "http://127.0.0.1:11434"
    allow_remote_context: bool = False
    remote_redaction_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MutationPolicy:
    allow_scene_changes: bool = True
    allow_prefab_changes: bool = True
    allow_script_changes: bool = False
    allow_engine_changes: bool = False
    require_confirmation: bool = True
    require_python_confirmation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIRequest:
    prompt: str
    mode: str = "auto"
    answers: Dict[str, Any] = field(default_factory=dict)
    confirmed: bool = False
    allow_python: bool = False
    allow_engine_changes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanQuestion:
    id: str
    text: str
    rationale: str
    choices: List[str] = field(default_factory=list)
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
        return asdict(self)


@dataclass
class CapabilityGap:
    id: str
    title: str
    reason: str
    suggested_track: str
    blocking: bool = True
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
        data = asdict(self)
        data["planning_questions"] = [question.to_dict() for question in self.planning_questions]
        return data


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
            "metadata": dict(self.metadata),
        }


@dataclass
class ExecutionAction:
    id: str
    action_type: str
    summary: str
    args: Dict[str, Any]
    risk: str = "standard"
    requires_confirmation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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


@dataclass
class ValidationCheck:
    name: str
    success: bool
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
            "context_summary": dict(self.context_summary),
        }
