# Queen Execution Plan: World y SceneManager core refactor

Status: completed
Authority: operational-plan
Task ID: queen-20260712-001
Created at: 2026-07-12T12:57:18+02:00
Updated at: 2026-07-12T22:06:09+02:00
Mode: long-task-plan

## Objective

Ejecutar el plan maestro de refactorizacion segura hasta A-CORE y B-CORE:
encapsular presencia de componentes, separar grupos, serializacion, clonacion y
persistencia, y centralizar solo el rollback serializable equivalente.

## Non-goals

- No ejecutar A5, A6, B4, B5, gate posterior ni backlog C.
- No cambiar Scene v2, EngineAPI publica, prefabs, editor, fisica o gameplay.
- No retirar compatibilidad legacy ni optimizar sin benchmark.
- No hacer commit ni push.

## Initial state

- Branch: `feat/refactorWorldySceneManager`.
- HEAD: `66ca559213412edbf91e2db35802938913be1f5c`.
- Trackeados iniciales: sin cambios.
- Cambio local ajeno a preservar: `.codex-remote-attachments/**`.
- Evidencia generada por esta tarea: `artifacts/benchmarks/queen-20260712-001/**`.
- Python local: `py -3.11`, Python 3.11.1. `python` falla por alias de Microsoft Store.
- Model route: `critical` (`*_deep`).
- TEST CONTRACT: `test-contract-queen-20260712-001`, `sufficient`.
- Commit authorized: `false`.
- Max cycles: 5.

## Acceptance criteria

- Tres consumidores de produccion dejan de leer indices privados.
- `world.group_registry`, serializacion, clonacion y errores publicos conservan contrato.
- EDIT -> PLAY -> STOP, Scene v2, prefabs y legacy permanecen compatibles.
- `SceneWorkspace` queda sin I/O; persistencia tecnica tiene autoridad separada.
- `SceneManager` conserva instalacion, rekey, dirty, pending, mtime y callbacks.
- B3 restaura exactamente campos caracterizados y excluye rutas incrementales.
- Suite, Ruff, mypy, benchmarks, review y AI audit sin regresiones nuevas.
- STOP obligatorio tras B-CORE.

## Scope

Allowed production files by phase:

- A1.5: `engine/ecs/world.py`, `engine/systems/collision_system.py`,
  `engine/systems/physics_system.py`, `engine/app/runtime_controller.py`.
- A2: `engine/ecs/group_registry.py`, `engine/ecs/world.py`.
- A3: `engine/ecs/world_serialization.py`, `engine/ecs/world.py`.
- A4: `engine/ecs/world_clone.py`, `engine/ecs/world.py`.
- B1 benchmark: `engine/debug/benchmark_runner.py` y test enfocado.
- B2: `engine/scenes/scene_persistence.py`, `engine/scenes/scene_manager.py`,
  `engine/scenes/workspace_lifecycle.py`.
- B3: `engine/scenes/scene_manager.py`.
- Tests enfocados y docs canonicas estrictamente relacionados.

Forbidden:

- `.codex-remote-attachments/**`, `AGENTS.md`, `.agents/**`, `.codex/**`, `.opencode/**`.
- `engine/api/**`, `engine/serialization/schema.py`, `engine/scenes/scene.py`,
  `engine/scenes/contracts.py`, `engine/ecs/component.py`, `engine/ecs/entity.py`,
  `engine/physics/**`, `engine/core/**`, `cli/**`, `main.py`.
- Todo alcance A5/A6/B4/B5/C.

## TEST CONTRACT summary

- Caracterizar comportamiento actual antes de moverlo; tests nuevos pasan contra
  produccion previa.
- Proteger colisiones de identidad, estructuras legacy, presencia canonical/legacy,
  payload/warnings/errores, clone sin aliasing y EDIT/PLAY.
- Proteger storage personalizado, atomicidad vigente, readback, recuento, mtime,
  dirty guard, callbacks, memoria ante fallo, ports y adapters.
- Proteger rollback exacto sin restaurar `dirty_before_pending_edit_world_sync`,
  `edit_world_version` ni campos adicionales.
- No relajar tests existentes. Patches internos pueden seguir autoridad nueva sin
  aliases muertos.

## Baseline evidence

- `py -3.11 -m unittest discover -s tests`: 3624 tests, OK, 8 skipped,
  470.747 s.
- `py -3.11 -m ruff check engine cli tools main.py`: pass.
- `py -3.11 -m ruff check tests`: pass.
- `py -3.11 -m mypy engine cli tools main.py`: pass, 410 source files.
- Quick benchmark: passed 4/4, 0 warnings, 0 failures.
- A4 before, 7 repeats: `world_clone` median 493.2962 ms.
- A1.5 before, 10 repeats: `ecs_queries` median 0.4785 ms;
  `world_clone` median 30.7454 ms.

## Plan critique

Verdict: approved.

Adjustments:

- Reutilizar baseline ya ejecutado; no repetir suite completa antes de A1.
- Tratar `artifacts/benchmarks/**` como evidencia generada, fuera de commit.
- A2.2 termina `keep` por defecto salvo reduccion demostrable de wiring.
- Crear medicion `scene_save` en framework existente antes de aprobar B2.
- No actualizar `docs/schema_serialization.md` si schema/payload no cambian.
- Un unico `builder_deep`; escritura serial por fase.

## Phases

### A0-A1 - Reconocimiento, baseline y contratos World

- Status: completed
- Cycle: 2/5.
- Decision: tests de caracterizacion; produccion intacta.
- Write set: tests ECS/World estrictamente necesarios.
- Exit: contratos A1.5-A4 no ambiguos y tests pasan contra baseline.

### A1.5 - Presencia de componentes

- Status: completed
- Cycle: 2/5.
- Decision: `merge_with_existing_service` en `World`.
- Exit: sin accesos privados en tres consumidores y benchmark equivalente.

### A2.1-A2.2 - GroupRegistry

- Status: completed
- Decision: A2.1 `extract`; A2.2 `keep` por defecto.
- Exit: traslado mecanico, sin ciclos, `world.group_registry` estable.

### A3 - Serializacion

- Status: completed
- Cycle: 2/5.
- Decision: `extract` funcion de modulo, o `keep/blocked` con evidencia.
- Exit: payload, orden, warnings, errores y aliasing equivalentes.

### A4 - Clonacion

- Status: completed
- Cycle: 2/5 (documental).
- Decision: `extract` funcion de modulo, o `keep/blocked` con evidencia.
- Exit: factory `World`, jerarquia, metadata, prefabs y aislamiento equivalentes.

### GATE A-CORE

- Status: completed
- Requires: validator pass, review approved, AI audit approved/not_applicable,
  benchmarks sin degradacion material y documentacion necesaria.

### B0-B1 - Reauditoria, contratos y benchmark scene_save

- Status: completed
- Cycle: 2/5.
- Decision: caracterizacion primero; produccion de escenas intacta.
- Exit: persistencia/rollback caracterizados y baseline `scene_save` disponible.

### B2 - Persistencia

- Status: in_progress
- Cycle: 2/5.
- Decision: `extract` `ScenePersistenceService`.
- Exit: workspace sin I/O; atomicidad, custom storage, mtime y callbacks estables.

### B3 - Snapshot/rollback

- Status: pending
- Decision: `extract_helpers` privados en `scene_manager.py`; `keep` valido.
- Exit: solo familias equivalentes comparten captura/restauracion exacta.

### GATE B-CORE y STOP

- Status: pending
- Requires: suite autoridad, Ruff, mypy, benchmarks, review, AI audit y docs.
- Terminal: actualizar `task_status` y detener. No iniciar A5/B4.

## Validation policy

- Cada fase: tests enfocados, Ruff/mypy del diff, `git diff --check`, validator y
  review deep aprobada sin `must_fix`.
- A-CORE/B-CORE: regresion cruzada, quick benchmark y comparaciones enfocadas.
- Degradacion de mediana >10% fuera de variabilidad: segunda ronda e investigacion.
- No usar p95 como evidencia con menos de 30 muestras.

## Rollback

Parche inverso limitado al write set causal, seguido de tests enfocados. Nunca
`reset`, `clean`, restore masivo ni doble implementacion. Bloquear dependencias si
no recupera baseline.

## Decisions

- 2026-07-12: ruta `critical`; roles deep disponibles.
- 2026-07-12: RECON valido tras una reformulacion de envelope.
- 2026-07-12: TEST CONTRACT `sufficient`.
- 2026-07-12: plan profundo criticado y aprobado con ajustes anteriores.
- 2026-07-12: commit y push no autorizados.

## Validation gates

- RECON: completed.
- TEST CONTRACT: sufficient.
- PLAN: completed.
- Plan critique: approved.
- A0-A1 builder cycle 1: completed, 9 tests, produccion intacta.
- A0-A1 validator cycle 1: pass, 56/56 focused.
- A0-A1 review cycle 1: changes_required.
- Must fix: no congelar identidad de mappings privados sin consumidor; cubrir
  aliasing de payload JSON anidado de componentes.
- A0-A1 builder cycle 2: completed.
- A0-A1 validator cycle 2: pass, 56/56 focused.
- A0-A1 review cycle 2: approved, `must_fix: []`.
- A1.5 builder cycle 1: completed; benchmark `ecs_queries` +1.30% median.
- A1.5 validator cycle 1: pass, 87/87 focused, Ruff/mypy/rg pass.
- A1.5 review cycle 1: changes_required.
- Must fix: bucles explicitos sin generadores en ruta caliente; documentar API
  estable de presencia en `docs/TECHNICAL.md`.
- A1.5 builder/documenter cycle 2: completed.
- A1.5 validator cycle 2: pass, 150 focused/governance.
- A1.5 review cycle 2: approved, `must_fix: []`.
- A2 builder: completed; A2.1 `extract`, A2.2 `keep World dependency`.
- A2 validator: pass, 39/39 focused, AST/import/cycle checks pass.
- A2 review: approved, `must_fix: []`.
- A3 builder cycle 1: completed; `world_serialize` median -1.91%.
- A3 validator cycle 1: pass, 93 focused, Ruff/mypy/import/scope pass.
- A3 review cycle 1: changes_required.
- Must fix: preservar atribucion de warning legacy a `engine/ecs/world.py` en
  ramas normal y prefab; documentar autoridad `world_serialization`.
- A3 builder/documenter cycle 2: completed.
- A3 validator cycle 2: pass, 94 focused.
- A3 review cycle 2: approved, `must_fix: []`.
- A4 builder: completed; `world_clone` median +0.52%.
- A4 validator: pass, 90 focused.
- A4 review cycle 1: changes_required.
- Must fix: documentar autoridad `world_clone.clone_world` y fachada/factory
  exacta `World.clone`.
- A4 documenter: completed.
- A4 validator cycle 2: pass.
- A4 review cycle 2: approved, `must_fix: []`.
- GATE A-CORE documenter: completed.
- GATE A-CORE validator: pass, 283 authority tests, quick 4/4.
- GATE A-CORE review: approved, `must_fix: []`.
- GATE A-CORE AI audit: approved, `must_fix: []`.
- B0-B1 builder cycle 1: completed; `scene_save` baseline 10 muestras,
  mediana 5052.451 ms.
- B0-B1 validator cycle 1: pass, 83 focused.
- B0-B1 review cycle 1: changes_required.
- Must fix: fallos observables de storage personalizado; orden/conservacion de
  mtime; benchmark `scene_save` sin contaminar workspace principal.
- B0-B1 builder cycle 2: completed; baseline `scene_save` aislado 10 muestras,
  mediana 4542.766 ms.
- B0-B1 validator cycle 2: pass, 85 focused + 7 must-fix.
- B0-B1 review cycle 2: approved, `must_fix: []`.
- B2 builder cycle 1: completed; `scene_save` median -3.44%.
- B2 validator cycle 1: fail; 310 tests verdes pero ImportError de
  `COMPACT_SCENE_SAVE_SEPARATORS` desde `scene_manager`.
- Must fix: restaurar reexport compatible y contrato de importacion.
- B2 builder cycle 2: completed; reexport de separadores restaurado por
  identidad desde la autoridad `scene_persistence`.
- B2 validator cycle 2: pass, 311 tests; Ruff, mypy, autoridad unica y
  benchmark previo verificados.
- B2 review cycle 2: changes_required.
- Must fix: documentar autoridad tecnica de persistencia y fronteras de
  `SceneManager`/`SceneWorkspace`.
- B2 documenter cycle 3: completed en `docs/TECHNICAL.md` y
  `docs/architecture.md`.
- B2 validator cycle 3: pass; canon contrastado con codigo y contratos.
- B2 review cycle 3: approved, `must_fix: []`.
- B3 builder cycle 1: completed; snapshot frozen de cinco campos y helpers
  privados aplicados a nueve familias serializables equivalentes.
- B3 validator cycle 1: pass, 195 tests; exclusiones, firmas y scope
  verificados.
- B3 review cycle 1: approved, `must_fix: []`; documentacion no requerida por
  tratarse de consolidacion privada sin cambio observable.
- GATE B-CORE validator pre-doc: pass; 3663 tests, 8 skipped, Ruff, mypy 414,
  quick 4/4 y deltas enfocados dentro de 10%.
- GATE B-CORE review pre-doc: changes_required.
- Must fix funcional: `load_scene_from_file` debe absorber solo fallos de
  lectura; errores posteriores de migracion, validacion o instalacion deben
  propagarse como en baseline.
- AI audit B-CORE pre-doc: changes_required.
- Must fix documental: describir `operations.scene_save`, umbral, aislamiento,
  campos estructurados y aumento de duracion del quick por workload ampliado.
- GATE B-CORE builder cycle 2: completed; limite historico de excepciones de
  carga restaurado con rojo-verde.
- GATE B-CORE validator cycle 2: pass, 175 tests; default/custom, cause,
  migracion, validacion, instalacion y stale verificados.
- GATE B-CORE review cycle 2: approved, `must_fix: []`.
- GATE B-CORE documenter cycle 3: completed; `operations.scene_save`, workload
  quick y ruta completa de autoridad documentados.
- GATE B-CORE final validator: pass; suite fresca 3669 tests, 8 skipped,
  Ruff, mypy 414, benchmark tests 24 y quick 4/4.
- GATE B-CORE final review: approved, `must_fix: []`.
- GATE B-CORE final AI audit: approved, `must_fix: []`.
- Focused benchmark deltas: `ecs_queries` +1.296%, `world_serialize` -1.909%,
  `world_clone` +0.517% y `scene_save` -3.439%.
- GATE B-CORE: completed.
- STOP: completed. A5, A6, B4, B5 y backlog C no iniciados.
- Commit authorized: false. Commit created: false. Push: false.
- Task status: completed.
- Remaining work: ninguno dentro del alcance autorizado; cualquier fase
  posterior requiere una instruccion independiente.
