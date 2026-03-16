from __future__ import annotations

from pathlib import Path
from typing import List

from engine.ai.types import ExecutionProposal, ValidationCheck, ValidationReport


class ValidationEngine:
    def validate(self, engine_api, proposal: ExecutionProposal) -> ValidationReport:
        checks: List[ValidationCheck] = []
        errors: List[str] = []

        project_service = getattr(engine_api, "project_service", None)

        for action in proposal.actions:
            if action.action_type == "api_call":
                kwargs = action.args.get("kwargs", {})
                entity_name = kwargs.get("name") or kwargs.get("entity_name")
                if not entity_name:
                    continue
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
                continue

            if action.action_type == "python_write":
                target = str(action.args.get("target", "")).strip()
                if not target or project_service is None or not getattr(project_service, "has_project", False):
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

        runtime_check = self._validate_play_cycle(engine_api)
        checks.append(runtime_check)
        if not runtime_check.success:
            errors.append(runtime_check.details)

        return ValidationReport(success=len(errors) == 0, checks=checks, warnings=[], errors=errors)

    def _validate_play_cycle(self, engine_api) -> ValidationCheck:
        try:
            engine_api.play()
            engine_api.step(5)
            engine_api.stop()
            return ValidationCheck(
                name="play_cycle",
                success=True,
                details="La escena entro en PLAY, avanzo 5 frames y volvio a EDIT correctamente.",
            )
        except Exception as exc:
            return ValidationCheck(
                name="play_cycle",
                success=False,
                details=f"Fallo el ciclo PLAY/STOP: {exc}",
            )
