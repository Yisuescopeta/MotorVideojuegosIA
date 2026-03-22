from __future__ import annotations

from pathlib import Path
from typing import List

from engine.ai.types import AIToolCall, ExecutionAction, ExecutionProposal, ValidationCheck, ValidationReport


class ValidationEngine:
    def validate(self, engine_api, proposal: ExecutionProposal) -> ValidationReport:
        tool_calls = [self._action_to_tool_call(action) for action in proposal.actions]
        return self.validate_tool_calls(engine_api, tool_calls)

    def validate_tool_calls(self, engine_api, tool_calls: List[AIToolCall]) -> ValidationReport:
        checks: List[ValidationCheck] = []
        errors: List[str] = []

        project_service = getattr(engine_api, "project_service", None)

        for tool_call in tool_calls:
            entity_name = str(tool_call.arguments.get("name", "") or tool_call.arguments.get("entity_name", "") or "")
            if entity_name and tool_call.tool_name not in {"inspect_entity", "list_assets", "list_prefabs", "list_scripts", "write_script", "save_asset_metadata", "validate_play_cycle"}:
                exists = any(entity["name"] == entity_name for entity in engine_api.list_entities())
                checks.append(
                    ValidationCheck(
                        name=f"entity_exists:{entity_name}",
                        success=exists,
                        details=f"La entidad {entity_name} {'existe' if exists else 'no existe'} tras la ejecucion.",
                    )
                )
                if not exists:
                    errors.append(f"Missing entity after execution: {entity_name}")

            target = str(tool_call.arguments.get("target", "") or "").strip()
            if target:
                if project_service is None or not getattr(project_service, "has_project", False):
                    checks.append(
                        ValidationCheck(
                            name="python_scaffold",
                            success=False,
                            details="No se pudo resolver el destino del scaffold Python.",
                        )
                    )
                    errors.append("Python scaffold target unresolved")
                    continue
                target_path = project_service.resolve_path(target)
                exists = Path(target_path).exists()
                checks.append(
                    ValidationCheck(
                        name=f"python_file:{target}",
                        success=exists,
                        details=f"El archivo {target} {'existe' if exists else 'no existe'} tras la ejecucion.",
                    )
                )
                if not exists:
                    errors.append(f"Missing python scaffold after execution: {target}")

            if tool_call.tool_name == "add_component":
                component_name = str(tool_call.arguments.get("component_name", "") or "")
                if entity_name and component_name:
                    entity = next((item for item in engine_api.list_entities() if item["name"] == entity_name), None)
                    has_component = bool(entity and component_name in entity.get("components", {}))
                    checks.append(
                        ValidationCheck(
                            name=f"component_exists:{entity_name}.{component_name}",
                            success=has_component,
                            details=f"El componente {component_name} {'existe' if has_component else 'no existe'} en {entity_name}.",
                        )
                    )
                    if not has_component:
                        errors.append(f"Missing component after execution: {entity_name}.{component_name}")

        runtime_check = self._validate_play_cycle(engine_api)
        checks.append(runtime_check)
        if not runtime_check.success:
            errors.append(runtime_check.details)

        return ValidationReport(success=len(errors) == 0, checks=checks, warnings=[], errors=errors)

    def _action_to_tool_call(self, action: ExecutionAction) -> AIToolCall:
        if action.action_type == "api_call":
            return AIToolCall(
                id=action.id,
                tool_name=str(action.args.get("method", "") or ""),
                arguments=dict(action.args.get("kwargs", {}) or {}),
                summary=action.summary,
            )
        if action.action_type == "python_write":
            return AIToolCall(
                id=action.id,
                tool_name="write_script",
                arguments={"target": str(action.args.get("target", "") or "")},
                summary=action.summary,
                write_scope="script",
            )
        return AIToolCall(
            id=action.id,
            tool_name=action.action_type,
            arguments=dict(action.args or {}),
            summary=action.summary,
        )

    def _validate_play_cycle(self, engine_api) -> ValidationCheck:
        try:
            engine_api.play()
            game = getattr(engine_api, "game", None)
            if game is not None and hasattr(game, "step_frame"):
                engine_api.step(5)
            engine_api.stop()
            return ValidationCheck(
                name="play_cycle",
                success=True,
                details="La escena entro en PLAY y volvio a EDIT correctamente.",
            )
        except Exception as exc:
            return ValidationCheck(
                name="play_cycle",
                success=False,
                details=f"Fallo el ciclo PLAY/STOP: {exc}",
            )
