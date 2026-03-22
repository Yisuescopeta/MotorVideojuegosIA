from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from engine.ai.capabilities import detect_capability_gaps
from engine.ai.execution import ExecutionEngine
from engine.ai.session_store import AISessionStore
from engine.ai.snapshots import AISnapshotService
from engine.ai.tools import AuthoringToolRegistry
from engine.ai.types import (
    AIApplyResult,
    AIApprovalRequest,
    AIContextWindow,
    AIMessage,
    AIPlanResponse,
    AIRequest,
    AISession,
    AIToolCall,
    CapabilityGap,
    ExecutionProposal,
    MutationPolicy,
    PlanQuestion,
    PlanningSession,
    ProviderPolicy,
)


class AISessionService:
    def __init__(
        self,
        engine_api,
        providers,
        memory_store,
        context_assembler,
        planner,
        execution,
        validator,
        tool_registry: Optional[AuthoringToolRegistry] = None,
        session_store: Optional[AISessionStore] = None,
        snapshot_service: Optional[AISnapshotService] = None,
    ) -> None:
        self._engine_api = engine_api
        self._providers = providers
        self._memory = memory_store
        self._context = context_assembler
        self._planner = planner
        self._execution = execution
        self._validator = validator
        self._tools = tool_registry or AuthoringToolRegistry()
        self._sessions = session_store or AISessionStore(engine_api.project_service)
        self._snapshots = snapshot_service or AISnapshotService(engine_api.project_service)

    def start_session(self, title: str = "", mode: str = "plan", activate: bool = True) -> AISession:
        now = self._now()
        session = AISession(
            id=f"session_{uuid4().hex[:12]}",
            title=(title.strip() or "AI Assistant"),
            status="idle",
            mode="plan" if mode == "plan" else "build",
            created_at=now,
            updated_at=now,
        )
        self._persist(session, activate=activate)
        return session

    def get_session(self, session_id: Optional[str] = None) -> Optional[AISession]:
        if session_id:
            return self._sessions.load(session_id)
        active = self._sessions.load_active()
        return active

    def submit_message(
        self,
        session_id: Optional[str],
        prompt: str,
        mode: str = "plan",
        answers: Optional[Dict[str, Any]] = None,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
        activate: bool = True,
    ) -> AISession:
        session = self.get_session(session_id)
        if session is None:
            session = self.start_session(title=self._derive_title(prompt), mode=self._normalize_session_mode(mode), activate=activate)
        session.title = session.title or self._derive_title(prompt)
        session.prompt = prompt.strip()
        session.mode = self._normalize_session_mode(mode)
        session.answers.update(dict(answers or {}))
        session.updated_at = self._now()
        session.pending_questions = []
        session.approval = None
        session.plan_response = AIPlanResponse()
        session.gaps = []
        self._append_message(session, "user", session.prompt)
        self._process_turn(session, raw_mode=mode, allow_python=allow_python, allow_engine_changes=allow_engine_changes)
        self._persist(session, activate=activate)
        return session

    def answer_question(
        self,
        session_id: str,
        answer: str,
        question_id: Optional[str] = None,
        mode: Optional[str] = None,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> AISession:
        session = self._require_session(session_id)
        if not session.pending_questions:
            self._append_message(session, "assistant", "There is no pending question to answer.")
            self._persist(session)
            return session

        current = session.pending_questions[0]
        if question_id:
            for question in session.pending_questions:
                if question.id == question_id:
                    current = question
                    break
        session.answers[current.id] = answer
        session.pending_questions = [question for question in session.pending_questions if question.id != current.id]
        session.updated_at = self._now()
        self._append_message(session, "user", answer)
        if session.pending_questions:
            self._append_message(session, "assistant", session.pending_questions[0].text, kind="question")
            session.status = "needs_input"
            self._persist(session)
            return session

        self._process_turn(
            session,
            raw_mode=mode or ("build" if session.mode == "build" else "plan"),
            append_user_message=False,
            allow_python=allow_python,
            allow_engine_changes=allow_engine_changes,
        )
        self._persist(session)
        return session

    def approve_proposal(
        self,
        session_id: str,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> AISession:
        session = self._require_session(session_id)
        self._apply_session_proposal(
            session,
            allow_python=allow_python,
            allow_engine_changes=allow_engine_changes,
        )
        self._persist(session)
        return session

    def _apply_session_proposal(
        self,
        session: AISession,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> AISession:
        if session.approval is None or session.approval.status not in {"pending", "proposal_ready"}:
            self._append_message(session, "assistant", "There is no pending proposal to apply.")
            return session

        snapshot_id = self._snapshots.capture(self._engine_api, session.approval.diff.files)
        results: List[Dict[str, Any]] = []
        errors: List[str] = []
        applied_tool_calls: List[str] = []
        for tool_call in session.approval.tool_calls:
            result = self._tools.execute(
                self._engine_api,
                tool_call,
                allow_python=allow_python,
                allow_engine_changes=allow_engine_changes,
            )
            results.append(
                {
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.tool_name,
                    "result": dict(result),
                }
            )
            if bool(result.get("success", False)):
                applied_tool_calls.append(tool_call.id)
            else:
                errors.append(f"{tool_call.summary or tool_call.tool_name}: {result.get('message', 'failed')}")
                break

        validation = self._validator.validate_tool_calls(self._engine_api, session.approval.tool_calls)
        if not validation.success:
            errors.extend([error for error in validation.errors if error not in errors])

        success = len(errors) == 0
        session.approval.status = "applied" if success else "blocked"
        session.last_apply = AIApplyResult(
            success=success,
            applied_tool_calls=applied_tool_calls,
            results=results,
            errors=errors,
            validation=validation,
            snapshot_id=snapshot_id,
            undo_summary="Restore scene and scripts from the snapshot taken before apply.",
        )
        session.tool_results = (session.tool_results + results)[-24:]
        session.context_window = self._context.assemble_window(session.prompt, tool_results=session.tool_results)
        session.updated_at = self._now()

        if success:
            session.status = "applied"
            self._append_message(session, "assistant", "Changes applied and validated.")
        else:
            restore_result = self._snapshots.restore(self._engine_api, snapshot_id)
            session.status = "blocked"
            summary = self._summarize_apply_failure(errors)
            if bool(restore_result.get("success", False)):
                self._append_message(session, "assistant", f"Apply bloqueado: {summary} Se ha restaurado el estado anterior.")
            else:
                self._append_message(session, "assistant", f"Apply bloqueado: {summary}")

        return session

    def reject_proposal(self, session_id: str) -> AISession:
        session = self._require_session(session_id)
        if session.approval is None:
            self._append_message(session, "assistant", "There is no proposal to reject.")
            self._persist(session)
            return session
        session.approval.status = "rejected"
        session.status = "rejected"
        session.updated_at = self._now()
        self._append_message(session, "assistant", "Proposal rejected. You can refine the prompt or start a new session.")
        self._persist(session)
        return session

    def undo_last_apply(self, session_id: str) -> AISession:
        session = self._require_session(session_id)
        if session.last_apply is None or not session.last_apply.snapshot_id:
            self._append_message(session, "assistant", "There is no applied proposal to undo.")
            self._persist(session)
            return session
        restore_result = self._snapshots.restore(self._engine_api, session.last_apply.snapshot_id)
        session.updated_at = self._now()
        session.context_window = self._context.assemble_window(session.prompt, tool_results=session.tool_results)
        if bool(restore_result.get("success", False)):
            session.status = "rolled_back"
            self._append_message(session, "assistant", "Last apply reverted from snapshot.")
        else:
            session.status = "blocked"
            self._append_message(session, "assistant", str(restore_result.get("message", "Undo failed")))
        self._persist(session)
        return session

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._tools.list_tools()

    def get_diagnostics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        provider_diagnostics = self._providers.list_providers()
        active_session = self.get_session(session_id)
        return {
            "active_session_id": active_session.id if active_session is not None else self._sessions.get_active_session_id(),
            "active_session_status": active_session.status if active_session is not None else "",
            "tool_count": len(self._tools.list_tools()),
            "providers": provider_diagnostics,
            "selected_provider": active_session.provider if active_session is not None else "",
        }

    def _process_turn(
        self,
        session: AISession,
        raw_mode: str,
        append_user_message: bool = False,
        allow_python: bool = False,
        allow_engine_changes: bool = False,
    ) -> None:
        memory = self._memory.load()
        provider_policy = ProviderPolicy.from_dict(memory.get("provider_policy", {}))
        mutation_policy = MutationPolicy.from_dict(memory.get("mutation_policy", {}))
        provider = self._providers.resolve(provider_policy)

        session.provider = provider.id
        session.model_name = (provider_policy.model_name or "").strip()
        session.updated_at = self._now()
        session.context_window = self._context.assemble_window(session.prompt, tool_results=session.tool_results)

        if self._requests_engine_scope_change(session.prompt):
            gap = CapabilityGap(
                id="engine_write_scope",
                title="engine write scope",
                reason="This assistant can extend game content and scripts, but not engine/ source code in this MVP.",
                suggested_track="implementation_brief",
                blocking=True,
                evidence=["write scope limited to game content and scripts"],
            )
            session.gaps = [gap]
            session.status = "blocked"
            session.pending_questions = []
            session.approval = None
            session.plan_response = AIPlanResponse(
                summary="La solicitud cae fuera del write scope del asistente.",
                reasoning="Puedo ayudarte a planificar una extension del motor, pero no modificar engine/ directamente desde este flujo.",
                project_findings=["Write scope actual: escenas, prefabs, scripts y metadatos de assets."],
                next_steps=["Definir la capacidad faltante", "Escribir un brief tecnico para el motor"],
                blocking_questions=[],
                can_build_now=False,
            )
            session.metadata["legacy_plan"] = {
                "session_type": "gap_analysis",
                "summary": "The request requires an engine extension outside the MVP write scope.",
                "assumptions": ["Write scope limited to scenes, prefabs, scripts and asset metadata."],
                "questions": [],
                "milestones": [
                    "Describe the missing engine capability",
                    "Specify the new serializable contract",
                    "Implement the engine extension in a separate engine task",
                ],
                "gaps": [gap.to_dict()],
                "selected_skills": [],
                "execution_intent": None,
                "metadata": {"track": "implementation_brief"},
            }
            self._append_message(
                session,
                "assistant",
                "This request falls outside the MVP write scope. I can prepare an implementation brief, but I will not modify engine/ directly.",
            )
            return

        legacy_context = self._context.assemble(session.prompt)
        plan = self._planner.build_plan(session.prompt, session.answers, legacy_context)
        session.metadata["legacy_plan"] = plan.to_dict()
        session.gaps = list(plan.gaps)

        provider_decision = self._plan_with_provider(provider, provider_policy, session)
        if provider_decision is not None:
            provider_questions = provider_decision.get("blocking_questions") or provider_decision.get("questions", [])
            if provider_questions and raw_mode not in {"direct", "execute"}:
                plan.questions = provider_questions
            if provider_decision.get("summary"):
                plan.summary = str(provider_decision["summary"])
            session.metadata["provider_plan"] = dict(provider_decision)

        session.plan_response = self._build_plan_response(plan, session, provider_decision)
        session.last_intent_resolution = {
            "prompt": session.prompt,
            "mode": raw_mode,
            "execution_intent": plan.execution_intent,
            "can_build_now": session.plan_response.can_build_now,
            "answers": dict(session.answers),
        }

        if plan.gaps:
            session.status = "blocked"
            session.pending_questions = []
            session.approval = None
            session.plan_response.can_build_now = False
            self._append_message(session, "assistant", self._render_plan_message(session.plan_response), kind="plan")
            return

        skip_questions = raw_mode in {"direct", "execute"}
        if plan.questions and not skip_questions:
            session.status = "needs_input"
            session.pending_questions = list(plan.questions)
            session.approval = None
            session.plan_response.blocking_questions = list(plan.questions)
            self._append_message(session, "assistant", self._render_plan_message(session.plan_response), kind="plan")
            return

        if raw_mode == "plan":
            session.status = "planned"
            session.pending_questions = []
            session.approval = None
            self._append_message(session, "assistant", self._render_plan_message(session.plan_response), kind="plan")
            return

        legacy_proposal = self._execution.build_proposal(plan, mutation_policy)
        session.metadata["legacy_proposal"] = legacy_proposal.to_dict()
        tool_calls = self._build_tool_calls_from_plan(legacy_proposal)
        if provider_decision is not None and provider_decision.get("tool_calls"):
            provider_tool_calls = self._normalize_provider_tool_calls(provider_decision.get("tool_calls", []))
            if provider_tool_calls:
                tool_calls = provider_tool_calls

        if not tool_calls and raw_mode in {"build", "execute", "direct"} and not plan.questions:
            generated_decision = self._attempt_provider_build_decision(provider, provider_policy, session)
            if generated_decision is not None:
                session.metadata["provider_build"] = dict(generated_decision)
                if generated_decision.get("summary"):
                    session.plan_response.summary = str(generated_decision.get("summary", "") or session.plan_response.summary)
                if generated_decision.get("reasoning"):
                    session.plan_response.reasoning = str(generated_decision.get("reasoning", "") or session.plan_response.reasoning)
                blocking_questions = list(generated_decision.get("blocking_questions", []))
                if blocking_questions:
                    session.status = "needs_input"
                    session.pending_questions = blocking_questions
                    session.approval = None
                    session.plan_response.blocking_questions = blocking_questions
                    session.plan_response.can_build_now = False
                    self._append_message(session, "assistant", self._render_plan_message(session.plan_response), kind="plan")
                    return
                generated_tool_calls = self._normalize_provider_tool_calls(generated_decision.get("tool_calls", []))
                if generated_tool_calls:
                    tool_calls = generated_tool_calls

        if not tool_calls:
            session.status = "blocked"
            session.approval = None
            session.plan_response.can_build_now = False
            self._append_message(session, "assistant", self._render_plan_message(session.plan_response), kind="plan")
            return

        diff = self._tools.build_diff_summary(tool_calls)
        approval = AIApprovalRequest(
            id=f"approval_{uuid4().hex[:10]}",
            summary=legacy_proposal.summary,
            diff=diff,
            tool_calls=tool_calls,
            status="pending",
            mode="build",
            requires_confirmation=legacy_proposal.requires_confirmation,
            allowed_scopes=["scene", "prefab", "script", "asset_meta"],
            metadata={"legacy_summary": legacy_proposal.summary},
        )
        session.approval = approval
        session.pending_questions = []
        session.status = "proposal_ready"
        if raw_mode in {"build", "execute"}:
            self._apply_session_proposal(
                session,
                allow_python=allow_python,
                allow_engine_changes=allow_engine_changes,
            )
            return
        self._append_message(session, "assistant", self._render_plan_message(session.plan_response), kind="plan")

    def _plan_with_provider(
        self,
        provider,
        policy: ProviderPolicy,
        session: AISession,
    ) -> Optional[Dict[str, Any]]:
        planner = getattr(provider, "plan_turn", None)
        if not callable(planner):
            return None
        try:
            raw_result = planner(
                prompt=session.prompt,
                answers=dict(session.answers),
                policy=policy,
                context=session.context_window.to_dict(),
                available_tools=self._tools.list_tools(),
                session_mode=session.mode,
            )
        except Exception:
            return None
        if not isinstance(raw_result, dict):
            return None

        question_payload = raw_result.get("blocking_questions", raw_result.get("questions", []))
        questions = [
            PlanQuestion.from_dict(item)
            for item in question_payload
            if isinstance(item, dict)
        ]
        return {
            "summary": str(raw_result.get("summary", "") or ""),
            "questions": questions,
            "reasoning": str(raw_result.get("reasoning", "") or ""),
            "project_findings": [str(item) for item in raw_result.get("project_findings", [])],
            "next_steps": [str(item) for item in raw_result.get("next_steps", [])],
            "blocking_questions": questions,
            "can_build_now": bool(raw_result.get("can_build_now", False)),
            "tool_calls": raw_result.get("tool_calls", []),
        }

    def _build_plan_response(
        self,
        plan: PlanningSession,
        session: AISession,
        provider_decision: Optional[Dict[str, Any]],
    ) -> AIPlanResponse:
        summary = str(provider_decision.get("summary", "") if provider_decision else "") or plan.summary
        reasoning = str(provider_decision.get("reasoning", "") if provider_decision else "")
        if not reasoning:
            reasoning = self._default_reasoning(plan, session)
        project_findings = [str(item) for item in (provider_decision.get("project_findings", []) if provider_decision else []) if str(item).strip()]
        if not project_findings:
            project_findings = self._default_project_findings(session)
        next_steps = [str(item) for item in (provider_decision.get("next_steps", []) if provider_decision else []) if str(item).strip()]
        if not next_steps:
            next_steps = list(plan.milestones[:3])
        blocking_questions = list(plan.questions)
        can_build_now = bool(provider_decision.get("can_build_now", False)) if provider_decision else False
        if not can_build_now:
            can_build_now = bool((plan.execution_intent or plan.metadata.get("generic_build_candidate")) and not plan.questions and not plan.gaps)
        return AIPlanResponse(
            summary=summary,
            reasoning=reasoning,
            project_findings=project_findings,
            next_steps=next_steps,
            blocking_questions=blocking_questions,
            can_build_now=can_build_now,
        )

    def _attempt_provider_build_decision(
        self,
        provider,
        policy: ProviderPolicy,
        session: AISession,
    ) -> Optional[Dict[str, Any]]:
        complete = getattr(provider, "complete", None)
        if not callable(complete):
            return None

        payload = {
            "task": "Translate the gameplay request into concrete tool calls for a game authoring assistant.",
            "session_mode": "build",
            "prompt": session.prompt,
            "answers": dict(session.answers),
            "context": {
                "scene_path": session.context_window.scene_path,
                "selected_entity": session.context_window.selected_entity,
                "entity_count": session.context_window.entity_count,
                "entities": self._engine_api.list_entities(),
                "recent_scripts": list(session.context_window.recent_scripts[:5]),
                "recent_assets": list(session.context_window.recent_assets[:5]),
                "tool_results": list(session.context_window.tool_results[-6:]),
            },
            "rules": [
                "Attempt a build whenever the request can be approximated with scene edits or a gameplay script.",
                "Do not modify engine/.",
                "Only use the provided tool names.",
                "For novel gameplay behaviours, prefer write_script plus add_script_behaviour attached to an existing entity.",
                "Use write_script targets only under scripts/.",
                "If you need to attach a script, module_path can be the relative script path without the .py suffix.",
                "If a required target entity is missing, ask one minimal blocking question instead of refusing generically.",
                "Return non-empty tool_calls whenever a reasonable attempt is possible.",
            ],
            "available_tools": self._tools.list_tools(),
            "response_schema": {
                "summary": "string",
                "reasoning": "string",
                "can_build_now": "boolean",
                "blocking_questions": [{"id": "string", "text": "string", "rationale": "string", "choices": ["string"]}],
                "tool_calls": [{"tool_name": "string", "summary": "string", "arguments": {}}],
            },
        }
        try:
            completion = complete(
                prompt=json.dumps(payload, ensure_ascii=False),
                system_prompt="Return only valid JSON matching the requested schema.",
                policy=policy,
            )
        except Exception:
            return None

        parsed = self._extract_json_object(completion)
        if not isinstance(parsed, dict):
            return None

        question_payload = parsed.get("blocking_questions", [])
        questions = [PlanQuestion.from_dict(item) for item in question_payload if isinstance(item, dict)]
        return {
            "summary": str(parsed.get("summary", "") or ""),
            "reasoning": str(parsed.get("reasoning", "") or ""),
            "can_build_now": bool(parsed.get("can_build_now", False)),
            "blocking_questions": questions,
            "tool_calls": parsed.get("tool_calls", []),
        }

    def _extract_json_object(self, payload: Any) -> Optional[Dict[str, Any]]:
        text = str(payload or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return parsed if isinstance(parsed, dict) else None

    def _default_reasoning(self, plan: PlanningSession, session: AISession) -> str:
        if plan.gaps:
            return "He revisado la peticion frente a las capacidades serializables del motor y ahora mismo falta soporte directo para resolverla dentro del editor."
        if plan.questions:
            return "He podido acotar bastante la intencion, pero todavia falta un dato imprescindible para construir o dar un plan fiable."
        if plan.execution_intent:
            return "He detectado una intencion concreta y ya puedo traducirla a cambios sobre entidades, componentes o scripts del proyecto."
        return "He revisado el prompt y el contexto del proyecto para devolverte un enfoque accionable sin convertir el flujo en un cuestionario generico."

    def _default_project_findings(self, session: AISession) -> List[str]:
        findings: List[str] = []
        if session.context_window.selected_entity:
            findings.append(f"Entidad seleccionada: {session.context_window.selected_entity}")
        findings.append(f"Entidades visibles en escena: {session.context_window.entity_count}")
        if session.context_window.recent_scripts:
            findings.append(f"Scripts recientes: {', '.join(session.context_window.recent_scripts[:2])}")
        findings.append(f"Proveedor activo: {session.provider or 'sin provider'}")
        return findings

    def _render_plan_message(self, plan_response: AIPlanResponse) -> str:
        lines: List[str] = []
        if plan_response.summary:
            lines.append(plan_response.summary)
        if plan_response.reasoning:
            lines.append(f"Analisis: {plan_response.reasoning}")
        if plan_response.project_findings:
            lines.append("Contexto: " + " | ".join(plan_response.project_findings[:3]))
        if plan_response.next_steps:
            lines.append("Siguientes pasos: " + " -> ".join(plan_response.next_steps[:3]))
        if plan_response.blocking_questions:
            lines.append("Falta una decision para seguir:")
            lines.append(plan_response.blocking_questions[0].text)
        elif plan_response.can_build_now:
            lines.append("Puedes pasar a Build para ejecutarlo sobre el proyecto.")
        return "\n".join(line for line in lines if line).strip()

    def _build_tool_calls_from_plan(self, proposal: ExecutionProposal) -> List[AIToolCall]:
        tool_calls: List[AIToolCall] = []
        for action in proposal.actions:
            tool_calls.append(
                self._tools.from_execution_action(
                    action,
                    script_content_resolver=self._execution.build_script_content,
                )
            )
        return tool_calls

    def _normalize_provider_tool_calls(self, payload: List[Dict[str, Any]]) -> List[AIToolCall]:
        tool_calls: List[AIToolCall] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", "") or item.get("name", "") or "").strip()
            if not tool_name or not self._tools.has_tool(tool_name):
                continue
            definition = self._tools.definition(tool_name)
            if definition is None:
                continue
            arguments = self._normalize_provider_arguments(tool_name, dict(item.get("arguments", {}) or {}))
            tool_calls.append(
                AIToolCall(
                    id=str(item.get("id", "") or f"provider_{uuid4().hex[:8]}"),
                    tool_name=tool_name,
                    arguments=arguments,
                    summary=str(item.get("summary", "") or ""),
                    status="planned",
                    read_only=definition.read_only,
                    write_scope=definition.write_scope,
                    risk=str(item.get("risk", "standard") or "standard"),
                    requires_confirmation=definition.requires_confirmation,
                )
            )
        return tool_calls

    def _normalize_provider_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(arguments)
        if tool_name == "write_script":
            normalized["target"] = self._normalize_script_target(normalized.get("target", ""))
        elif tool_name == "add_script_behaviour":
            module_path = str(normalized.get("module_path", "") or "").strip()
            if module_path:
                module_target = self._normalize_script_target(module_path)
                if module_target.endswith(".py"):
                    module_target = module_target[:-3]
                normalized["module_path"] = module_target.replace("\\", "/")
        return normalized

    def _normalize_script_target(self, target: Any) -> str:
        raw = str(target or "").strip().replace("\\", "/")
        if not raw:
            return ""

        project_service = getattr(self._engine_api, "project_service", None)
        if project_service is not None and getattr(project_service, "has_project", False):
            relative = project_service.to_relative_path(raw).replace("\\", "/")
            if relative.startswith("scripts/"):
                return relative
            if "/scripts/" in relative:
                return "scripts/" + relative.split("/scripts/", 1)[1]
            if relative.startswith("./scripts/"):
                return relative[2:]

        trimmed = raw.lstrip("./")
        if trimmed.startswith("scripts/"):
            return trimmed
        if "/scripts/" in trimmed:
            return "scripts/" + trimmed.split("/scripts/", 1)[1]
        filename = trimmed.rsplit("/", 1)[-1]
        return f"scripts/{filename}"

    def _render_gap_message(self, plan: PlanningSession) -> str:
        titles = ", ".join(gap.title for gap in plan.gaps)
        reasons = "; ".join(gap.reason for gap in plan.gaps)
        return f"{plan.summary} Gaps: {titles}. {reasons}"

    def _append_message(
        self,
        session: AISession,
        role: str,
        content: str,
        kind: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        session.messages.append(
            AIMessage(
                id=f"msg_{uuid4().hex[:10]}",
                role=role,
                content=content,
                kind=kind,
                created_at=self._now(),
                metadata=dict(metadata or {}),
            )
        )
        session.updated_at = self._now()

    def _persist(self, session: AISession, activate: bool = True) -> None:
        self._sessions.save(session)
        if activate:
            self._sessions.set_active_session_id(session.id)

    def _require_session(self, session_id: str) -> AISession:
        session = self._sessions.load(session_id)
        if session is None:
            raise ValueError(f"AI session '{session_id}' not found")
        return session

    def _normalize_session_mode(self, raw_mode: str) -> str:
        return "plan" if raw_mode == "plan" else "build"

    def _derive_title(self, prompt: str) -> str:
        compact = " ".join(str(prompt or "").split()).strip()
        return compact[:48] if compact else "AI Assistant"

    def _summarize_apply_failure(self, errors: List[str]) -> str:
        for error in errors:
            if error.startswith("Missing entity after execution: "):
                entity_name = error.split(": ", 1)[1].strip()
                return f"la entidad objetivo {entity_name} no existe en la escena actual."
        if errors:
            return errors[0]
        return "la propuesta no pudo aplicarse."

    def _requests_engine_scope_change(self, prompt: str) -> bool:
        lower = prompt.lower()
        mentions_engine = any(token in lower for token in ("engine/", "engine\\", "codigo del motor", "código del motor", "internals del motor"))
        mentions_change = any(token in lower for token in ("editar", "modificar", "cambiar", "refactor", "implementa", "rewrite"))
        return mentions_engine and mentions_change

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
