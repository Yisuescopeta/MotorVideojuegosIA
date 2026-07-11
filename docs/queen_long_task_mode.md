# Queen Long Task Plan Mode

Authority: operational-plan

Documentacion del modo de planes largos del sistema Queen.
**No es documentacion canonica del producto.**
Es una guia operativa para el uso del modo Long Task Plan.

## Que es

Long Task Plan Mode es el modo de Queen para tareas grandes, multi-fase,
arquitectonicas o que requieren multiples sesiones. En lugar del ciclo unico
normal, Queen opera sobre un plan persistente externalizado como artefacto
estable de sesion.

El ciclo por fase es:

```text
LOAD PLAN -> PLAN SYNC -> TEST CONTRACT -> IMPLEMENTAR FASE -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> UPDATE PLAN -> NEXT PHASE | COMMIT | BLOCK
```

El TEST CONTRACT se define antes de implementar. El resultado de AI AUDIT se
registra en UPDATE PLAN antes de avanzar, bloquear o cerrar.

Regla fuerte:

```text
phase completed != task completed
```

En este modo, `phase_status=completed` obliga a continuar. No devuelve control
al usuario salvo `blocked`, `failed`, `partial`, `completed` final o
`planning_only` explicito.

## Model Router por fase

En Long Task Plan Mode, Queen recalcula `model_route` al inicio de cada fase,
despues de `PLAN SYNC` y antes de `TEST CONTRACT`. Queen selecciona variantes de
subagente, no edita configuracion dinamica de modelos.

Si una fase falla en `validator` o `code-reviewer` por razones no triviales, la
siguiente iteracion sube `planner` y `code-reviewer` a variantes `deep`. Si el
TEST CONTRACT fue insuficiente por falta de analisis, Queen puede reintentar una
vez con `test-strategist-deep` antes de bloquear.

## Cuando usarlo

Queen activa Long Task Plan Mode automaticamente si:

- El usuario proporciona ruta a un plan.
- La tarea dice "usa plan", "tarea larga", "por fases" o similar.
- La tarea tiene mas de 2-3 fases.
- Toca arquitectura, schema, CLI, EngineAPI, docs canonicas o flujos IA.
- Requiere multiples sesiones.
- Toca adaptacion Godot o cambios amplios del motor.
- Queen detecta riesgo alto de scope creep.

## Cuando NO usarlo

Para tareas pequeñas o medianas (un solo archivo, un fix puntual, un test,
una actualizacion de docs), Queen usa Normal Task Mode. No fuerces plan mode
para tareas triviales — el overhead del plan no se justifica.

## Donde viven los planes

1. **Plan operativo local**: `.motor/queen_state/plans/<task_id>.plan.md`
   (estado local, no versionado en git).

2. **Plan versionado**: `docs/plans/active/<task_id>-<slug>.md`
   (versionado en git, para tareas epicas o compartidas).

3. **Plan archivado**: `docs/plans/archive/<task_id>-<slug>.md`
   (al terminar la tarea, mover aqui).

## Diferencia entre plan operativo y docs canonicas

| Plan operativo | Docs canonicas |
|----------------|----------------|
| Vive en `docs/plans/` | Vive en `docs/` (raiz) |
| `Authority: operational-plan` | Parte del contrato del motor |
| Describe QUE hacer | Describe COMO funciona el motor |
| Se archiva al terminar | Se actualiza con cada cambio de contrato |
| Por debajo de codigo/tests/docs canonicas | Autoridad solo debajo de codigo/tests |

## Template de plan

```md
# Queen Execution Plan: <nombre>

Status: active|completed|blocked|failed
Authority: operational-plan
Task ID: queen-YYYYMMDD-NNN
Created at: <ISO timestamp>
Updated at: <ISO timestamp>
Mode: long-task-plan

## Objective
<Descripcion clara del objetivo>

## Non-goals
- <Lo que NO se va a hacer>

## Constraints
- <Restricciones: no tocar engine/, no cambiar API, etc.>

## Current phase
- Name: <nombre de la fase actual>
- Status: pending|in_progress|done|blocked
- Allowed files: <archivos que esta fase puede tocar>
- Forbidden files: <archivos que NO debe tocar>
- Test contract: <test-contract-id o not_applicable con razon>
- Acceptance checks: <que debe cumplirse para dar la fase por buena>
- Docs affected: <docs canonicas que requieren actualizacion>
- Risks: <riesgos detectados>

## Phases

### Phase 1 — <nombre>
Status: pending|in_progress|done|blocked
Goal: <objetivo de la fase>
Allowed files: <lista>
Forbidden files: <lista>
Acceptance checks: <lista>
Docs affected: <lista>
Risks: <lista>

### Phase 2 — <nombre>
...

## Decisions
- <Date>: <Decision>. Reason: <razon>. Impact: <impacto>.

## Progress log
- <Date>: Phase <X>. Summary: <resumen>. Checks: <resultado>. Risks: <riesgos>.

## Final checks
- Focused tests: <pass|fail>
- Regression tests: <pass|fail>
- Lint: <pass|fail>
- Typecheck: <pass|fail>
- Motor doctor: <pass|fail>
- Review: <approved|changes_requested>
- AI audit: <score|not_applicable>
```

## TEST CONTRACT por fase

Despues de PLAN SYNC y antes de IMPLEMENTAR FASE, Queen invoca
`test-strategist` salvo docs-only trivial. El contrato define tests autoridad,
tests nuevos o modificados, tests que no se pueden relajar, comandos minimos
enfocados, regresiones recomendadas y criterios de aceptacion.

Si `test-strategist` ejecuta `py -m unittest ...`, ese resultado es solo
inspeccion auxiliar. La validacion final corresponde a `validator` despues de
DOCUMENTAR.

La matriz operativa de tests por subsistema vive en
`docs/queen_engine_workflow.md`.

## Como Queen sincroniza el plan

### Antes de cada fase (PLAN SYNC)

Queen lee del plan activo solo las secciones relevantes:

1. **Objective** y **Non-goals**: para no desviarse.
2. **Current phase**: nombre, archivos permitidos, checks, riesgos.
3. **Constraints**: restricciones activas.
4. **Decisions** recientes: decisiones tomadas en fases previas.

### Despues de cada fase (UPDATE PLAN)

Queen actualiza el plan con:

1. **Current phase** → marca `done` y avanza `Current phase` a la siguiente.
2. **Progress log**: entrada con resumen, checks y riesgos.
3. **AI AUDIT**: resultado, score o `not_applicable` con razon.
4. **Decisions**: si se tomaron decisiones arquitectonicas o de alcance.
5. **Risks**: nuevos riesgos detectados.
6. **Updated at**: timestamp.

Despues de registrar esos datos, UPDATE PLAN decide exactamente uno:

- `continue_next_phase`: continuar inmediatamente a la siguiente fase sin
  devolver control al usuario.
- `block`: detenerse por bloqueo real.
- `complete`: toda la tarea ya cumple Definition of Done.
- `partial`: se alcanzo `max_cycles`, contexto insuficiente o limite explicito
  de alcance.

Un reporte intermedio de fase no es respuesta final. Es entrada operativa para
la siguiente fase.

## Que pasa si el plan contradice codigo/tests/docs

El plan operativo esta por debajo de codigo, tests y docs canonicas en el
orden de autoridad. Si hay conflicto:

1. Codigo y tests tienen maxima autoridad.
2. Docs canonicas tienen la siguiente prioridad.
3. El plan debe corregirse para alinearse con las fuentes superiores.

Queen nunca debe tratar un plan como fuente de verdad superior a estas.

## Archivo de planes

Al terminar la tarea (completed, partial, blocked o failed):

1. El plan versionado se mueve de `docs/plans/active/` a `docs/plans/archive/`.
2. Se actualiza el header: `Status: completed|blocked|failed`.
3. Se añade `Archived at: <ISO timestamp>`.

## Codex y OpenCode

Ambas integraciones comparten planes en `docs/plans/active/`. En Codex, sesion
raiz carga `.agents/skills/queen/SKILL.md`, recalcula route por fase y valida
cada resultado JSON antes de UPDATE PLAN. `continue_next_phase` obliga a
continuar sin devolver control al usuario. Contrato compacto:
`.agents/skills/queen/references/long_task_mode.md`.

## Ver tambien

- `AGENTS.md` — contrato operativo de agentes.
- `.opencode/agents/queen.md` — prompt del agente Queen.
- `docs/queen_engine_workflow.md` — matriz operativa de validacion por subsistema.
- `docs/plans/README.md` — ciclo de vida de planes operativos.
