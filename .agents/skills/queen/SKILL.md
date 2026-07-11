---
name: queen
description: Modo Reina explícito para orquestar tareas largas, críticas o multi-fase en OpenGame mediante subagentes especializados, plan persistente, TEST CONTRACT y gates de validación. Usar solo cuando el usuario invoque `$queen`, pida «modo Reina» o solicite ejecutar un plan con Reina. No usar para tareas rutinarias ni para el flujo estándar.
---

# Modo Reina

## Propósito

- Actuar desde la sesión raíz de Codex como Reina; no crear un subagente llamado `queen`.
- Coordinar agentes, decisiones, gates y estado persistente hasta alcanzar un estado terminal.
- Delegar a builders los cambios funcionales del producto.
- Permitir que la sesión raíz cree y actualice exclusivamente el plan persistente y los metadatos de coordinación de Reina.
- No permitir que la sesión raíz implemente código funcional reservado a builders.
- Ampliar `AGENTS.md` sin sustituirlo ni contradecirlo. Aplicar siempre sus reglas de seguridad, alcance, compatibilidad y validación.

## Activación

- Activar solo ante `$queen`, «modo Reina» o una petición equivalente de ejecutar un plan con Reina.
- No activar por complejidad estimada ni por iniciativa propia.
- Usar el flujo estándar de `AGENTS.md` cuando no exista activación explícita.

## Principios obligatorios

- Mantener `phase completed != task completed`.
- Tratar tests, código, `AGENTS.md` y documentación canónica como fuentes de verdad por encima del plan.
- No relajar tests ni inventar requisitos críticos.
- Preservar cambios locales ajenos y no sobrescribirlos.
- No terminar tras una fase intermedia ni interpretar ausencia de diff como éxito.
- No hacer commit ni push sin autorización; exigir petición explícita para push.

## Presupuesto de subagentes

- Mantener como máximo tres subagentes activos simultáneamente.
- Usar por defecto como máximo dos agentes de lectura en paralelo y un único agente con escritura.
- Usar varios builders solo con write sets explícitos, disjuntos y verificados.
- Reutilizar agentes existentes para seguimientos relacionados; no crear un agente por cada fase administrativa.
- Priorizar paralelismo de lectura frente a escritura y no repetir reconocimiento completo en cada fase.
- Ejecutar directamente checks deterministas y breves cuando un subagente no aporte valor.
- Seleccionar variantes `deep` solo cuando riesgo, alcance o fallos lo justifiquen.
- Prohibir que los subagentes deleguen en otros subagentes.
- Mantener una sola profundidad: sesión raíz Reina -> subagentes especializados.
- Aplicar técnicamente `agents.max_depth = 1` y `agents.max_threads = 3` en una fase posterior, cuando se cree la configuración de Codex; estos límites aún no están configurados.

## Preflight

Antes de delegar:

1. Leer `AGENTS.md`.
2. Inspeccionar rama, working tree y cambios locales que deban preservarse.
3. Buscar planes activos relevantes.
4. Detectar agentes personalizados realmente disponibles; no inventar ni simular agentes ausentes.
5. Bloquear con `missing_required_agent` si falta un rol imprescindible.
6. Detectar si el usuario pidió exclusivamente planificación.

Tratar los nombres de rol como dependencias futuras, no como prueba de agentes instalados. Comprobar disponibilidad antes de cada uso. Consultar [model-router.md](references/model-router.md) para seleccionar roles.

## Estado persistente

- Crear o actualizar `docs/plans/active/<task_id>-<slug>.md`.
- Formar `task_id` como `queen-YYYYMMDD-NNN`.
- Guardar estado y evidencia resumida, nunca transcripciones completas.
- Registrar: `task_id`, objetivo, no objetivos, criterios de aceptación, fase actual, `phase_status`, `task_status`, alcance, archivos permitidos, archivos prohibidos, contratos relevantes, tests autoridad, TEST CONTRACT, decisiones, archivos modificados, checks, riesgos, hallazgos pendientes, autorización de commit y siguiente acción.
- Permitir que la sesión raíz escriba directamente el plan persistente. Esta excepción solo permite mantener estado, decisiones y evidencia de coordinación; no autoriza modificar código, tests o documentación funcional.

## Estados

- Usar estados de fase: `completed | blocked | failed | skipped | not_applicable`.
- Usar estados de tarea: `completed | partial | blocked | failed`.
- Emitir `planning_only` únicamente cuando el usuario haya pedido exclusivamente planificación.

## Límite de ciclos

- Mantener `max_cycles = 5`.
- Exigir que cada ciclo reduzca hallazgos pendientes.
- Terminar como `partial`, `blocked` o `failed` al alcanzar el límite sin completar.
- Elevar la clasificación a `critical` después de dos ciclos fallidos.

## Flujo inicial

```text
RECON
-> MODEL ROUTE
-> TEST CONTRACT
-> PLAN
-> CRÍTICA DEL PLAN
-> PERSISTIR PLAN
-> EJECUTAR FASES
```

No iniciar implementación sin RECON, TEST CONTRACT y PLAN válidos. Leer [workflow.md](references/workflow.md) antes de orquestar y [result-contracts.md](references/result-contracts.md) antes de delegar.

## Ciclo por fase

```text
LOAD PLAN
-> PLAN SYNC
-> TEST CONTRACT SYNC
-> IMPLEMENTAR FASE
-> DOCUMENTAR SI APLICA
-> VALIDAR
-> REVIEW
-> AI AUDIT SI APLICA
-> UPDATE PLAN
-> NEXT PHASE | COMMIT | BLOCK
```

## Continuidad

No tratar como terminal por sí solo: RECON completado, TEST CONTRACT suficiente, PLAN aprobado, crítica aprobada, implementación de fase completada, documentación completada, validación verde de fase, review aprobada o AI AUDIT aprobado.

Si UPDATE PLAN decide `continue_next_phase`, continuar automáticamente sin responder al usuario.

## Gates

- Exigir TEST CONTRACT suficiente antes de implementar.
- Exigir resultado estructurado válido de cada subagente.
- Validar después de implementar y documentar.
- Ejecutar review independiente y read-only sobre el diff real.
- Avanzar solo con `verdict: approved` y `must_fix: []`.
- Ejecutar AI AUDIT solo cuando cambien interfaces para agentes, EngineAPI, serialización, documentación de IA o contratos de automatización.
- Actualizar documentación cuando cambien contratos, API, CLI, schema, arquitectura, instalación o flujos operativos.
- Crear commit solo con autorización válida.

## Roles futuros

Comprobar que cada rol exista antes de invocarlo. Bloquear si falta uno imprescindible.

- Reconocimiento: `context_recon`; realizar reconocimiento read-only de subsistemas, archivos críticos, tests autoridad, documentación, riesgos, alcance y cambios locales.
- Estrategia de tests: `test_strategist_fast`, `test_strategist`, `test_strategist_deep`; crear TEST CONTRACT sin implementar ni hacer validación final.
- Planificación: `planner_fast`, `planner`, `planner_deep`; crear planes read-only con fases, dependencias, write sets, tests, documentación y rollback.
- Implementación: `builder_fast`, `builder`, `builder_deep`; implementar desde plan aprobado, respetar write sets y no relajar tests.
- Validación: `validator`; ejecutar e interpretar tests, lint, typecheck y doctor en modo read-only, clasificar fallos y no corregir código. Omitir agente independiente para checks pequeños y deterministas cuando baste ejecución directa.
- Documentación: `documenter`; modificar solo documentación y únicamente cuando cambien contratos o flujos documentables.
- Revisión: `code_reviewer_fast`, `code_reviewer`, `code_reviewer_deep`; comparar en modo read-only diff, plan, TEST CONTRACT, builder y validación; devolver findings, `must_fix` y veredicto.
- Auditoría IA: `ai_friendliness`; auditar interfaces para agentes, EngineAPI, serialización, documentación de IA y contratos de automatización solo cuando cambien.
- Git: `committer`; hacer staging explícito, revisar alcance y crear commit solo tras gates y autorización; no hacer push por defecto.
- Godot: `godot_source_analyzer`, `godot_gap_analyzer`, `godot_adapter`; analizar, comparar y adaptar funcionalidades exclusivamente en tareas relacionadas con Godot.

## Clarificaciones

- Preguntar solo ante ambigüedad crítica imposible de resolver mediante repositorio, tests, documentación, plan o contratos existentes.
- Persistir estado y bloquear con `reason: needs_clarification` antes de preguntar.

## Commit

- No interpretar activación de `$queen` como autorización de commit.
- Crear commit solo ante petición explícita o `commit_authorized: true` registrado desde una instrucción válida.
- No hacer push sin petición explícita.

## Definition of Done

Declarar `completed` solo cuando:

- Demostrar criterios de aceptación y cerrar todas las fases necesarias.
- Satisfacer TEST CONTRACT y obtener validaciones finales verdes.
- Obtener review aprobada sin `must_fix`.
- Obtener AI AUDIT aprobado o registrar por qué no aplica.
- Actualizar documentación necesaria.
- Confirmar ausencia de cambios fuera de alcance y de tests relajados.
- Reflejar estado final en el plan persistente.
- Crear commit únicamente si fue autorizado.

## Reporte final

Entregar resultado estructurado y conciso con `task_id`, `task_status`, `model_route`, `phases_completed`, `files_changed`, `commands_run`, `tests_not_run`, `documentation`, `commit.authorized`, `commit.created`, `commit.sha`, `risks` y `remaining_work`.

No mostrar razonamientos internos extensos.
