from __future__ import annotations

from typing import Any, Dict

from engine.ai.context import ContextAssembler
from engine.ai.execution import ExecutionEngine
from engine.ai.planning import PlanningEngine
from engine.ai.project_memory import ProjectMemoryStore
from engine.ai.providers import ProviderRegistry
from engine.ai.skills import SkillRegistry
from engine.ai.types import AIRequest, AIResponse, MutationPolicy, ProviderPolicy
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

    def handle(self, request: AIRequest) -> AIResponse:
        memory = self._memory.load()
        provider_policy = ProviderPolicy(**memory.get("provider_policy", {}))
        mutation_policy = MutationPolicy(**memory.get("mutation_policy", {}))
        provider = self._providers.resolve(provider_policy)
        context = self._context.assemble(request.prompt)
        plan = self._planner.build_plan(request.prompt, request.answers, context)

        if (request.mode == "plan" and not request.confirmed) or (plan.questions and request.mode not in {"direct", "execute"}):
            self._remember_plan(plan)
            return AIResponse(
                status="needs_input" if plan.questions else "planned",
                mode="plan",
                message=self._render_message(
                    provider,
                    provider_policy,
                    "La IA ha preparado el modo plan y necesita mas contexto antes de mutar el proyecto." if plan.questions else "Plan listo para revision.",
                    plan=plan,
                    proposal=None,
                ),
                plan=plan,
                gaps=list(plan.gaps),
                provider=provider.id,
                context_summary=context["summary"],
            )

        proposal = self._execution.build_proposal(plan, mutation_policy)
        if not request.confirmed or request.mode == "proposal":
            self._remember_plan(plan)
            return AIResponse(
                status="proposal_ready",
                mode="proposal",
                message=self._render_message(
                    provider,
                    provider_policy,
                    "Propuesta de ejecucion lista. Requiere confirmacion antes de aplicar cambios.",
                    plan=plan,
                    proposal=proposal,
                ),
                plan=plan,
                proposal=proposal,
                gaps=list(plan.gaps),
                provider=provider.id,
                context_summary=context["summary"],
            )

        success, results, errors = self._execution.apply(
            self._engine_api,
            proposal,
            allow_python=request.allow_python,
            allow_engine_changes=request.allow_engine_changes,
        )
        validation = self._validator.validate(self._engine_api, proposal) if success else None
        validation_success = bool(validation is None or validation.success)

        if success:
            self._remember_plan(plan, applied=True)

        status = "applied" if success and validation_success else ("applied_with_warnings" if success else "blocked")
        if success and validation_success:
            fallback_message = "Cambios aplicados y validados."
        elif success:
            fallback_message = "Cambios aplicados, pero la validacion detecto problemas."
        else:
            fallback_message = "La ejecucion quedo bloqueada por politicas o fallos."

        return AIResponse(
            status=status,
            mode="execution",
            message=self._render_message(
                provider,
                provider_policy,
                fallback_message,
                plan=plan,
                proposal=proposal,
            ),
            plan=plan,
            proposal=proposal,
            validation=validation,
            gaps=list(plan.gaps),
            provider=provider.id,
            context_summary={
                **context["summary"],
                "results": results,
                "errors": errors,
                "validation_errors": list(validation.errors) if validation is not None else [],
            },
        )

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
        provider_policy = ProviderPolicy(**memory.get("provider_policy", {}))
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

    def assemble_context(self, prompt: str) -> Dict[str, Any]:
        return self._context.assemble(prompt)

    def _remember_plan(self, plan, applied: bool = False) -> None:
        update = {
            "last_plan_summary": plan.summary,
            "pending_questions": [question.id for question in plan.questions],
        }
        if applied:
            update["confirmed_decisions"] = list(plan.assumptions)
        self._memory.update(update)

    def _render_message(self, provider, policy: ProviderPolicy, fallback: str, plan, proposal) -> str:
        if provider.id == "ollama_local":
            prompt = self._build_provider_prompt(fallback, plan, proposal)
            try:
                completion = provider.complete(prompt=prompt, system_prompt="Resume el estado del asistente del motor de forma breve y util para el usuario.", policy=policy)
            except Exception:
                completion = ""
            if completion:
                return completion
        return fallback

    def _build_provider_prompt(self, fallback: str, plan, proposal) -> str:
        prompt = [fallback]
        if plan is not None:
            prompt.append(f"Plan: {plan.summary}")
            if plan.questions:
                prompt.append("Preguntas pendientes: " + ", ".join(question.text for question in plan.questions))
            if plan.gaps:
                prompt.append("Gaps detectados: " + ", ".join(gap.title for gap in plan.gaps))
        if proposal is not None:
            prompt.append("Acciones propuestas: " + ", ".join(action.summary for action in proposal.actions[:5]))
        return "\n".join(prompt)
