# Queen Execution Plan: migracion nativa a Codex

Status: active
Authority: operational-plan
Task ID: queen-20260710-001
Created at: 2026-07-10T12:00:00+02:00
Updated at: 2026-07-10T14:30:00+02:00
Mode: long-task-plan

## Objective

Migrar Reina de OpenCode a Codex nativo con la sesion raiz como orquestadora,
manteniendo OpenCode operativo, contratos estructurados y continuidad automatica.

## Non-goals

- No modificar `engine/`, contratos publicos ni serializacion.
- No eliminar `.opencode/` ni `opencode.json`.
- No cambiar modelos de OpenCode.
- No hacer `push`.

## Constraints

- Rama `fix/ciclosReina`, base `99fa3896f661298208bcacde2821c2fab1a9dae6`.
- Route `critical`: usar variantes deep para estrategia, plan, builder y review.
- `max_cycles = 5`; `phase completed != task completed`.
- `agents.max_depth = 1`; maximo tres implementadores con write sets disjuntos.
- TEST CONTRACT `test-contract-queen-codex-migration`: `sufficient`.
- No relajar tests existentes.

## Current phase

- Name: validacion-review-auditoria-commit
- Status: pending
- Allowed files: `AGENTS.md`, `.agents/skills/queen/**`, `.codex/**`, `tests/test_codex_queen_contract.py`, `tests/test_queen_agent_contract.py`, `docs/agents.md`, `docs/queen_engine_workflow.md`, `docs/queen_long_task_mode.md`, `docs/refactor/**`, este plan.
- Forbidden files: `engine/**`, `cli/**`, `main.py`, `docs/archive/**`, `.opencode/**`, `opencode.json`.
- Test contract: `test-contract-queen-codex-migration` (`sufficient`).
- Acceptance checks: TOML/JSON validos; 20 subagentes; validador funcional; OpenCode intacto; tests enfocados verdes.
- Docs affected: `AGENTS.md`, `docs/agents.md`, `docs/queen_engine_workflow.md`, `docs/queen_long_task_mode.md`, `docs/refactor/`.
- Risks: permisos finos por archivo son operativos; modelos dependen de cuenta; config de proyecto exige repo trusted.

## Phases

### Phase 1 — Configuracion y contratos Codex
Status: done
Goal: crear skill, config, 20 agentes, schemas y validador.
Allowed files: `.agents/skills/queen/**`, `.codex/**`.
Forbidden files: `engine/**`, `.opencode/**`, `opencode.json`.
Acceptance checks: skill valida; TOML parseable; profundidad 1; paralelismo 3.
Docs affected: none.
Risks: diferencias entre sandbox tecnico y restricciones operativas.

### Phase 2 — Tests de gobernanza
Status: done
Goal: probar agentes, router, transiciones, schemas, seguridad y coexistencia.
Allowed files: `tests/test_codex_queen_contract.py`, `tests/test_queen_agent_contract.py`.
Forbidden files: tests no relacionados.
Acceptance checks: tests Codex y OpenCode pasan sin relajar aserciones.
Docs affected: none.
Risks: pruebas estaticas no sustituyen smoke runtime.

### Phase 3 — Documentacion y baseline
Status: done
Goal: documentar activacion, arquitectura, limites y evidencia real.
Allowed files: `AGENTS.md`, `docs/agents.md`, `docs/queen_engine_workflow.md`, `docs/queen_long_task_mode.md`, `docs/refactor/**`, este plan.
Forbidden files: `START_HERE_AI.md`, `docs/archive/**`.
Acceptance checks: referencias validas; garantias tecnicas y operativas separadas.
Docs affected: las rutas permitidas.
Risks: duplicacion entre fuentes canonicas.

### Phase 4 — Validacion, review, auditoria y commit
Status: pending
Goal: validar Codex/OpenCode, revisar diff, auditar IA y crear commit final.
Allowed files: este plan y reporte de fase.
Forbidden files: cambios funcionales nuevos.
Acceptance checks: validator pass; review approved; AI audit approved; commit sin push.
Docs affected: plan y reporte de fase.
Risks: smoke de subagentes puede depender de autenticacion o modelo disponible.

## Test contract

- Protege OpenCode, ciclos, Model Router, TEST CONTRACT, DoD y commit final.
- Exige TOML parseable, nombres unicos, sandboxes, schemas y transiciones.
- Rechaza resultado vacio, no JSON, campos ausentes, tipos o enums invalidos.
- Clasifica fallos como funcional, entorno, dependencia, importacion o plataforma.
- Autoridad: `tests/test_queen_agent_contract.py` y tests de gobernanza existentes.

## Decisions

- 2026-07-10: sesion raiz Codex = Reina; no existe agente hijo `queen`.
- 2026-07-10: agentes standalone en `.codex/agents/`; no registro duplicado.
- 2026-07-10: `max_depth=1`, `max_threads=3`.
- 2026-07-10: conservar OpenCode sin cambios durante transicion.
- 2026-07-10: no modificar `START_HERE_AI.md`; Reina es tooling, no capacidad del motor.

## Progress log

- 2026-07-10: RECON y baseline completados. Suite: 3582 pass, 12 fallos funcionales baseline, 8 skipped.
- 2026-07-10: TEST CONTRACT `sufficient`; plan criticado y aprobado con alcance reducido.
- 2026-07-10: Phases 1-3 completadas. Skill valida; 20 agentes Codex,
  contratos JSON y validador creados. Checks: 76 focused pass, 75 governance
  pass, `git diff --check` pass. Siguiente decision: `continue_next_phase`.

## Validation gates

- Validator: pending.
- Review: pending.
- AI audit: pending.
- UPDATE PLAN decision: `continue_next_phase`.
- Next phase: Phase 4, validacion runtime, review, AI audit y commit.

## Rollback

Revertir solo archivos de esta migracion mediante parche inverso. Conservar
OpenCode. No usar reset, clean ni restore masivo. No crear commit si falla DoD.
