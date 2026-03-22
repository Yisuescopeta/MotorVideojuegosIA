from __future__ import annotations

from typing import Any, Dict, Optional

from engine.ai.context import ContextAssembler
from engine.ai.execution import ExecutionEngine
from engine.ai.planning import PlanningEngine
from engine.ai.project_memory import ProjectMemoryStore
from engine.ai.providers import ProviderRegistry
from engine.ai.session_service import AISessionService
from engine.ai.session_store import AISessionStore
from engine.ai.skills import SkillRegistry
from engine.ai.snapshots import AISnapshotService
from engine.ai.tools import AuthoringToolRegistry
from engine.ai.types import (
    AIRequest,
    AIResponse,
    AISession,
    AIToolCall,
    ExecutionAction,
    ExecutionProposal,
    MutationPolicy,
    PlanningSession,
    ProviderPolicy,
)
from engine.ai.validation import ValidationEngine


class AIOrchestrator:
    def __init__(self, engine_api) -> None:
        self._engine_api = engine_api
        self._providers = ProviderRegistry()
        self._skills = SkillRegistry()
        self._memory = ProjectMemoryStore(engine_api.project_service)
        self._context = ContextAssembler(engine_api, self._skills, self._memory)
        self._planner = PlanningEngine()
        self._execution = ExecutionEngine()
        self._validator = ValidationEngine()
        self._tools = AuthoringToolRegistry()
        self._sessions = AISessionStore(engine_api.project_service)
        self._snapshots = AISnapshotService(engine_api.project_service)
        self._service = AISessionService(
            engine_api=engine_api,
            providers=self._providers,
            memory_store=self._memory,
            context_assembler=self._context,
            planner=self._planner,
            execution=self._execution,
            validator=self._validator,
            tool_registry=self._tools,
            session_store=self._sessions,
            snapshot_service=self._snapshots,
        )

    def handle(self, request: AIRequest) -> AIResponse:
        session = self._service.start_session(title=request.prompt[:48], mode="plan" if request.mode == "plan" else "build", activate=False)
        session = self._service.submit_message(
            session.id,
            request.prompt,
            mode=request.mode,
            answers=request.answers,
            allow_python=request.allow_python,
            allow_engine_changes=request.allow_engine_changes,
            activate=False,
        )
        if request.confirmed and session.approval is not None and request.mode not in {"build", "execute"}:
            session = self._service.approve_proposal(
                session.id,
                allow_python=request.allow_python,
                allow_engine_changes=request.allow_engine_changes,
            )
        return self._to_legacy_response(session, raw_mode=request.mode)

    def start_session(self, title: str = "", mode: str = "plan", activate: bool = True) -> Dict[str, Any]:
        return self._service.start_session(title=title, mode=mode, activate=activate).to_dict()

    def submit_message(
        self,
        session_id: Optional[str],
        prompt: str,
        mode: str = "plan",
        answers: Optional[Dict[str, Any]] = None,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
        activate: bool = True,
    ) -> Dict[str, Any]:
        return self._service.submit_message(
            session_id,
            prompt,
            mode=mode,
            answers=answers,
            allow_python=allow_python,
            allow_engine_changes=allow_engine_changes,
            activate=activate,
        ).to_dict()

    def answer_question(
        self,
        session_id: str,
        answer: str,
        question_id: Optional[str] = None,
        mode: Optional[str] = None,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> Dict[str, Any]:
        return self._service.answer_question(
            session_id,
            answer,
            question_id=question_id,
            mode=mode,
            allow_python=allow_python,
            allow_engine_changes=allow_engine_changes,
        ).to_dict()

    def approve_proposal(
        self,
        session_id: str,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> Dict[str, Any]:
        return self._service.approve_proposal(
            session_id,
            allow_python=allow_python,
            allow_engine_changes=allow_engine_changes,
        ).to_dict()

    def reject_proposal(self, session_id: str) -> Dict[str, Any]:
        return self._service.reject_proposal(session_id).to_dict()

    def get_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        session = self._service.get_session(session_id)
        return session.to_dict() if session is not None else {}

    def undo_last_apply(self, session_id: str) -> Dict[str, Any]:
        return self._service.undo_last_apply(session_id).to_dict()

    def list_tools(self) -> list[dict]:
        return self._service.list_tools()

    def list_skills(self) -> list[dict]:
        return [skill.to_dict() for skill in self._skills.list_skills()]

    def get_memory(self) -> Dict[str, Any]:
        return self._memory.load()

    def update_memory(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        return self._memory.update(patch)

    def list_providers(self) -> list[dict]:
        return self._providers.list_providers()

    def get_provider_diagnostics(self) -> Dict[str, Any]:
        memory = self._memory.load()
        provider_policy = ProviderPolicy.from_dict(memory.get("provider_policy", {}))
        selected = self._providers.resolve(provider_policy)
        diagnostics: Dict[str, Any] = {
            "selected_provider": selected.id,
            "policy": provider_policy.to_dict(),
            "providers": self._providers.list_providers(),
        }
        if hasattr(selected, "list_models"):
            try:
                diagnostics["models"] = getattr(selected, "list_models")(provider_policy)
            except Exception as exc:
                diagnostics["models_error"] = str(exc)
        return diagnostics

    def get_diagnostics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        diagnostics = self._service.get_diagnostics(session_id=session_id)
        diagnostics["provider"] = self.get_provider_diagnostics()
        return diagnostics

    def assemble_context(self, prompt: str) -> Dict[str, Any]:
        return self._context.assemble(prompt)

    def _to_legacy_response(self, session: AISession, raw_mode: str) -> AIResponse:
        legacy_plan_payload = session.metadata.get("legacy_plan")
        legacy_proposal_payload = session.metadata.get("legacy_proposal")
        legacy_plan = PlanningSession.from_dict(legacy_plan_payload) if isinstance(legacy_plan_payload, dict) else None
        if isinstance(legacy_proposal_payload, dict):
            legacy_proposal = ExecutionProposal.from_dict(legacy_proposal_payload)
        elif session.approval is not None:
            legacy_proposal = self._approval_to_legacy_proposal(session.approval)
        else:
            legacy_proposal = None

        context_summary = dict(session.context_window.summary)
        context_summary["plan_response"] = session.plan_response.to_dict()
        if session.last_apply is not None:
            context_summary["results"] = list(session.last_apply.results)
            context_summary["errors"] = list(session.last_apply.errors)
            context_summary["validation_errors"] = list(session.last_apply.validation.errors) if session.last_apply.validation is not None else []

        last_assistant_message = next((message.content for message in reversed(session.messages) if message.role == "assistant"), "")
        return AIResponse(
            status=session.status,
            mode="execution" if raw_mode == "execute" else raw_mode,
            message=last_assistant_message or "No response",
            plan=legacy_plan,
            proposal=legacy_proposal,
            validation=session.last_apply.validation if session.last_apply is not None else None,
            gaps=list(session.gaps),
            provider=session.provider,
            context_summary=context_summary,
        )

    def _approval_to_legacy_proposal(self, approval) -> ExecutionProposal:
        actions = [self._tool_call_to_execution_action(tool_call) for tool_call in approval.tool_calls]
        return ExecutionProposal(
            summary=approval.summary,
            actions=actions,
            validation_plan=["Run PLAY -> STOP validation"],
            blocked_by_gaps=False,
            requires_confirmation=approval.requires_confirmation,
            risk_notes=list(approval.diff.risk_notes),
        )

    def _tool_call_to_execution_action(self, tool_call: AIToolCall) -> ExecutionAction:
        if tool_call.tool_name == "write_script":
            return ExecutionAction(
                id=tool_call.id,
                action_type="python_write",
                summary=tool_call.summary or tool_call.tool_name,
                args={"target": str(tool_call.arguments.get("target", "") or "")},
                risk=tool_call.risk,
                requires_confirmation=tool_call.requires_confirmation,
            )
        return ExecutionAction(
            id=tool_call.id,
            action_type="api_call",
            summary=tool_call.summary or tool_call.tool_name,
            args={
                "method": tool_call.tool_name,
                "kwargs": dict(tool_call.arguments),
            },
            risk=tool_call.risk,
            requires_confirmation=tool_call.requires_confirmation,
        )
