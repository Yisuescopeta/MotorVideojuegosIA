# Contratos de resultados

## Nivel de garantía

En esta primera versión, los contratos son garantías operativas basadas en instrucciones.

No constituyen validación técnica estricta hasta que exista un validador determinista de schemas.

La ausencia temporal de ese validador no permite ignorar los contratos ni inferir éxito desde una salida inválida.

## Envelope común

Toda salida de subagente debe ser JSON válido con este mínimo:

```json
{
  "agent_role": "role_name",
  "task_id": "queen-YYYYMMDD-NNN",
  "phase_id": "phase-id",
  "status": "completed|partial|blocked|failed|skipped|not_applicable",
  "summary": "resultado conciso",
  "evidence": [],
  "risks": []
}
```

El `status` describe únicamente el resultado del subagente. Reina debe convertirlo explícitamente en `phase_status` y después en `task_status`; no debe tratar estos tres conceptos como equivalentes.

## Contratos por rol

### `context_recon`

```json
{
  "subsystems": [],
  "critical_files": [],
  "existing_tests_authority": [],
  "canonical_documentation": [],
  "allowed_files": [],
  "forbidden_files": [],
  "local_changes_to_preserve": [],
  "unknowns": []
}
```

### `test_strategist`

```json
{
  "verdict": "sufficient|insufficient|not_applicable",
  "protected_current_behavior": [],
  "expected_new_behavior": [],
  "existing_tests_authority": [],
  "new_or_modified_tests_required": [],
  "tests_that_must_not_be_relaxed": [],
  "minimum_focused_commands": [],
  "recommended_regressions": [],
  "acceptance_criteria": [],
  "if_tests_cannot_run": []
}
```

- `sufficient` permite continuar.
- `insufficient` impide delegar implementación y obliga a completar el análisis o bloquear.
- `not_applicable` solo es válido para cambios documentales o mecánicos sin comportamiento observable y debe incluir una razón explícita en `summary` del envelope.
- Reina no puede inferir la suficiencia del TEST CONTRACT si falta `verdict`.
- `test_strategist_fast` y `test_strategist_deep` usan exactamente este contrato de familia.

### `planner`

```json
{
  "phases": [],
  "dependencies": [],
  "write_sets": {},
  "allowed_files": [],
  "forbidden_files": [],
  "validations": [],
  "documentation_required": [],
  "rollback": [],
  "terminal_criteria": []
}
```

Las variantes `planner_fast` y `planner_deep` usan este contrato.

### `builder`

```json
{
  "files_changed": [],
  "changes": [],
  "commands_run": [],
  "tests_run": [],
  "tests_not_run": [],
  "remaining_findings": [],
  "write_scope_violations": []
}
```

Si `write_scope_violations` no está vacío, el resultado no puede considerarse `completed`. Las variantes `builder_fast` y `builder_deep` usan este contrato.

### `documenter`

```json
{
  "documentation_decision": "updated|not_applicable|blocked",
  "files_changed": [],
  "contracts_documented": [],
  "commands_run": [],
  "reason": ""
}
```

### `validator`

```json
{
  "verdict": "pass|fail|partial|blocked",
  "commands_run": [],
  "passed": [],
  "failed": [],
  "not_run": [],
  "failure_classification": [],
  "test_contract_satisfied": false
}
```

`test_contract_satisfied` solo puede ser `true` cuando existe evidencia directa de los criterios y comandos aplicables.

### `code_reviewer`

```json
{
  "verdict": "approved|changes_required|blocked",
  "findings": [],
  "must_fix": [],
  "should_fix": [],
  "test_assessment": [],
  "scope_assessment": []
}
```

Solo permite avanzar con `verdict = approved` y `must_fix = []`. Las variantes `code_reviewer_fast` y `code_reviewer_deep` usan este contrato.

### `ai_friendliness`

```json
{
  "verdict": "approved|changes_required|not_applicable|blocked",
  "surfaces_checked": [],
  "compatibility_findings": [],
  "must_fix": [],
  "reason": ""
}
```

### `committer`

```json
{
  "authorized": false,
  "staged_files": [],
  "excluded_files": [],
  "scope_verified": false,
  "created": false,
  "sha": null,
  "message": null,
  "push_performed": false
}
```

Mantener `push_performed = false` salvo petición explícita.

## Validez y recuperación

- Invalidar salida vacía, JSON truncado, prosa sin resultado estructurado, éxito sin evidencia y archivos o comandos inventados.
- No aceptar ausencia de diff como prueba de éxito.
- Pedir una sola reformulación al mismo agente cuando el contenido exista pero el formato sea inválido.
- Bloquear con `missing_subagent_result` si el agente existe pero la reformulación no devuelve un resultado válido.
- Reservar `missing_required_agent` para un rol imprescindible que no existe.
- Permitir avance tras review únicamente con `verdict: approved` y `must_fix: []`.
