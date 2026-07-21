# Queen Execution Plan: SceneManager refactor

Status: completed
Authority: operational-plan
Task ID: queen-20260713-001
Created at: 2026-07-14T12:45:01+02:00
Updated at: 2026-07-21T18:56:14Z
Archived at: 2026-07-19T00:03:26Z
Completed at: 2026-07-21T18:54:14Z
Mode: long-task-plan

## Estado

- `task_id`: `queen-20260713-001`
- `model_route`: `critical`
- `max_cycles`: `5`
- `cycle`: `1/5` (continuación reautorizada explícitamente por usuario el 2026-07-16; los cinco ciclos agotados anteriores quedan registrados como evidencia)
- `current_phase`: `cierre CI completado`
- `phase_status`: `S0-S9 completed; CI completed`
- `task_status`: `completed`
- `next_action`: `none`
- `commit_authorized`: `true` (autorización explícita del usuario para commits de cierre)
- `commit_created`: `true` (commit funcional `f0bc3cc5561b789dcc0135718e495e889b7d7465` y commit test/workflow `8926d4b25b6377927141b129f734d2aaed1db211`; el SHA del commit documental final no se autorreferencia aquí)
- `push_authorized`: `true` (autorización explícita del usuario)
- `functional_commit_pushed`: `true` (el SHA existe en `origin/feat/SceneManagerRefactor`)
- `base_sha`: `fded3556ed9509d5f0e06221f1655ba0f4053687`
- `resume_head_sha`: `3850e1995c1a7756803bfa8486f27c7ccf570874`
- `resume_merge_base_sha`: `fded3556ed9509d5f0e06221f1655ba0f4053687`
- `functional_sha`: `f0bc3cc5561b789dcc0135718e495e889b7d7465`
- `ci_validation_target_sha`: `f0bc3cc5561b789dcc0135718e495e889b7d7465`
- `ci_checkout_verified_sha`: `f0bc3cc5561b789dcc0135718e495e889b7d7465` (functional checkout exacto; `engine/` idéntico al harness)
- `functional_closure_commit_sha`: `f0bc3cc5561b789dcc0135718e495e889b7d7465`
- `closure_documentation_sha`: `self-referential final documentation commit; reported externally after creation`
- `branch_head_sha_before_ci_closure`: `075b28ae491302679cd6a476db156d8eb0bca1df`
- `upstream_sha_before_ci_closure`: `075b28ae491302679cd6a476db156d8eb0bca1df`
- `branch_vs_origin_main_before_ci_closure`: `ahead 7, behind 0`
- `workflow_dispatch_fix_sha`: `70a152325c7f693df7a1b315e72b5ad2188c16db`
- `branch_head_sha_at_ci_dispatch`: `8926d4b25b6377927141b129f734d2aaed1db211`
- `upstream`: `origin/feat/SceneManagerRefactor`
- `merge_base_with_origin_main`: `fded3556ed9509d5f0e06221f1655ba0f4053687`
- `branch_vs_upstream_before_ci_closure`: `ahead 0, behind 0`
- `functional_commit_author`: `Yisuescopeta <jesuscervantesfernandez2006@gmail.com>`
- `functional_commit_date`: `2026-07-18T17:17:23+02:00`
- `working_tree_initial`: `clean`
- `working_tree_after_closure`: `clean`
- `ci_execution`: `completed`

## Cierre CI 2026-07-21

- El snapshot funcional permaneció inmutable en `f0bc3cc5561b789dcc0135718e495e889b7d7465`.
- No se instaló OpenCode ni se añadió al workflow, manifiestos o `PATH`.
- La corrección fue exclusivamente de hermeticidad en `tests/test_queen_dispatch.py`: los tests que mockean `run_opencode` controlan también `resolve_opencode_executable`, y el test directo inyecta `executable="opencode"`.
- El test corregido se incorporó como overlay controlado desde `harness/tests/test_queen_dispatch.py` a `functional/tests/test_queen_dispatch.py`.
- El workflow comparó tree SHA de `engine/` antes del overlay: harness `2d62a63d347d0091cc9877b07bba1b6d778c9a46`, functional `2d62a63d347d0091cc9877b07bba1b6d778c9a46`; permanecieron idénticos.
- Tras el overlay, el único archivo modificado fue `tests/test_queen_dispatch.py`; no hubo cambios en `functional/engine/`.
- El run verde `29858340033` sustituye al run fallido `29665496955` como gate terminal; el run fallido se conserva como evidencia histórica.

### Evidencia del workflow

- `test/workflow commit`: `8926d4b25b6377927141b129f734d2aaed1db211`.
- `harness SHA`: `8926d4b25b6377927141b129f734d2aaed1db211`.
- `functional validation SHA`: `f0bc3cc5561b789dcc0135718e495e889b7d7465`.
- `run ID`: `29858340033`.
- `URL`: `https://github.com/Yisuescopeta/OpenGame/actions/runs/29858340033`.
- `createdAt`: `2026-07-21T18:42:04Z`.
- `startedAt`: `2026-07-21T18:42:04Z`.
- `updatedAt`: `2026-07-21T18:54:14Z`.
- `status`: `completed`.
- `conclusion`: `success`.
- `job ID`: `88728273671`.
- Job `Validate exact functional snapshot`: `success`.
- Steps `Set up job`, `Validate validation_ref format`, `Checkout workflow harness`, `Checkout functional snapshot`, `Configure validation evidence directory`, `Verify snapshots and engine tree`, `Overlay controlled Queen test`, `Set up Python 3.11`, `Install project`, `Full test suite`, `Restore tracked test side effects`, `Ruff production`, `Ruff tests`, `Mypy`, `Scene architecture and import-cycle contracts`, `Benchmark round 1`, `Benchmark round 2`, `Diff check`, `Upload validation evidence`, all post-steps and `Complete job`: `success`.
- Artefact `scene-manager-refactor-validation-f0bc3cc5561b789dcc0135718e495e889b7d7465`: ID `8506555393`, digest `sha256:96df3d41b6f0003eda135a66c2f23713e26750b038a757c50a8870c2b8181116`, size `42382` bytes, `created_at` `2026-07-21T18:54:05Z`, `expires_at` `2026-08-20T18:54:04Z`, `expired=false`.
- Artefact download: successful to temporary evidence directory; inspection confirmed snapshot, overlay, post-suite status, full-suite, Ruff, Mypy, architecture and benchmark logs/JSON files. Diff-check produced no output because it was clean; its step concluded `success`.

## Autoridades

Las entradas cronológicas posteriores conservan snapshots de cada fase. Frases
como «sin commit ni push» solo describen aquel instante; la sección `Estado` y
el cierre reproducible al final son autoridad para el estado Git actual.

- Especificación maestra vigente aportada al reanudar: `D:/putas/plan_scene_manager_especificacion_maestra_corregida.md`
- Revisión más reciente detectada por fecha y contenido:
  `D:/putas/plan_scene_manager_especificacion_maestra_final_reina.md`
  (2026-07-13 19:16, SHA-256
  `26BAC3BAC9012FDDBD5BC0A7802ADAC01A80BDDC801F693865B59E75A4239FE2`);
  es un superset posterior de la copia aportada (`+276/-29`) que añade el
  protocolo progresivo de primitivas `Scene` y el mapeo explícito a cinco
  macro-ciclos. Se cargaron ambas; el prompt actual y el plan vivo prevalecen.
  No se creó otra copia.
- Baseline: `artifacts/refactor_scene_manager/baseline.json`
- Benchmark bruto: `artifacts/refactor_scene_manager/baseline_benchmarks.json`
- Baseline de rendimiento comparable autoridad desde S1: `artifacts/refactor_scene_manager/s1-benchmarks.json`
- Working tree, tests y código prevalecen sobre este plan y la especificación.
- Este archivo es la única fuente viva de estado operativo. No crear execution logs paralelos.

## Objetivo

Convertir `engine/scenes/scene_manager.py` en fachada de composición, routing, coordinación transversal y compatibilidad, trasladando cada política a una autoridad única sin cambiar API pública ni comportamiento observable.

## No objetivos

- Cambiar Scene v2, schema, formato de prefab o semántica EDIT/PLAY.
- Optimizar algoritmos durante la extracción.
- Sustituir historial por otro framework.
- Generalizar authoring incremental fuera de `Transform` y `RectTransform`.
- Corregir fallos funcionales ajenos.
- Modificar API pública sin wrapper compatible y test explícito.

## Criterios terminales

- Gates S1, S2, S3, S4, S5, S6, S7A, S7, S8 y S9 cerrados en orden.
- `SceneManager` no implementa projection, pending sync, authoring, snapshots, scene flow ni historial.
- Workspace es único instalador de representaciones y autoridad de selección/dirty.
- Ningún módulo externo a `scene.py` muta almacenamiento interno de `Scene` ni llama helpers privados.
- Ningún servicio importa o recibe `SceneManager`; no hay ciclos ni implementación doble.
- API, IDs, selección, EDIT/PLAY, dirty, pending, rollback, historial, prefabs, guardado y scene flow compatibles.
- Tests enfocados, suite completa, Ruff y Mypy verdes por gate.
- Benchmarks comparables de siete muestras sin regresión material confirmada.
- Review independiente aprobada; AI audit aprobado o `not_applicable` justificado.
- Documentación canónica actualizada cuando cambie una autoridad.

## Estado inicial validado

- Rama `feat/SceneManagerRefactor`, igual a `origin/main` en SHA base.
- Working tree limpio antes del baseline.
- `SceneManager`: 1.989 líneas, 86.725 bytes.
- Baseline enfocado: 84 tests, verde.
- Baseline completo: 3.670 tests, 8 skips, verde, 471.158 s.
- Ruff producción/tests: verde. Mypy: 414 archivos, verde.
- Benchmark suite: 4/4 verde.
- Métricas repetidas actuales: `scene_create_world`, `scene_add_entity_canonicalization`, `scene_save`, `world_clone`, solo tres muestras.
- Métricas one-shot: `transform_edit`, `edit_to_play`, `play_to_edit`; no bloquean hasta S1.

## Solapamientos

- `origin/feat/refactorWorldySceneManager`: ancestro de `origin/main`; integrado, `exclude_from_base`.
- `origin/codex/SceneManager`: ancestro de `origin/main`; obsoleto, `exclude_from_base`.
- PR #26: head ancestro de main, base antigua `Implementación`; recomendar cierre como obsoleto, `exclude_from_base`.
- PR #10: antiguo, `DIRTY`, sin archivos `engine/scenes`; `exclude_from_base`, reauditar solo si revive.
- No existe trabajo local ajeno que preservar al inicio. Los artifacts y este plan creados por esta ejecución sí deben preservarse.

## TEST CONTRACT

- `phase_id`: `initial-test-contract`
- `verdict`: `sufficient`
- No relajar contratos conductuales ni de compatibilidad pública.
- Proteger IDs/selección, EDIT/PLAY, persistencia, dirty/pending, incremental sin rebuild, undo/redo, rollback semántico, scene flow, prefabs y callbacks de guardado.
- Migrar tests acoplados a privados solo en la fase propietaria: nuevo test directo + test público verde antes de retirar el test antiguo.
- No congelar forma interna de snapshots.
- Nuevas suites previstas: `test_scene_flow.py`, `test_scene_projection.py`, `test_scene_edit_sync.py`, `test_scene_incremental_authoring.py`, `test_scene_serializable_authoring.py`, `test_scene_architecture.py`.
- La suite completa se ejecuta en S1 y en cada gate S2-S9. Gate S7A también exige suite completa.

## Inventario de autoridad S0

| Bloque actual | Estado escrito | Autoridad objetivo | Decisión |
| --- | --- | --- | --- |
| claves untitled, rutas, entries, lifecycle | entries/active key/runtime | `SceneWorkspace` | extract/consolidate S2 |
| `_entity_id_for_name`, `_entity_name_for_id`, `set_selected_entity` | selección Scene/World | `SceneWorkspace` | extract S2 |
| dirty disperso | `entry.dirty` | `SceneWorkspace` | extract por rutas desde S2 |
| sync `SceneLink`/metadata e invalid links | `Scene.feature_metadata`/links | `SceneFlowPolicy` + primitivas Scene | extract S2 |
| validation/canonicalization/rebuild/install | `entry.scene`, `edit_world`, versión | projection produce; workspace instala | decompose S3 |
| pending legacy/preview/flush | pending reason, dirty anterior | `SceneEditSyncCoordinator` | extract S4 |
| Transform/RectTransform directo y deltas | Scene/World/versions/history | `SceneIncrementalAuthoring` | extract S5 |
| prefab override helpers | prefab override ops | conditional `PrefabOverrideService` | decide S6 |
| snapshot/commit/rollback serializable | Scene/World/selection/dirty/pending | `SerializableMutationCoordinator` | extract/gate S7A |
| CRUD/metadata/feature metadata/by-ID | Scene/World/history | `SceneSerializableAuthoring` | extract S7B-D |
| history dispatch/context CRUD | history + callbacks | passive `SceneChangeCoordinator` | rewire S8A |
| structural God Context/direct Scene mutation | Scene/hierarchy/prefab/history | explicit ports + Scene primitives | rewire S8B |
| wrappers/helpers/imports residuales | multiple | facade only | cleanup S9 |

## Tests acoplados a implementación

- `test_scene_mutation_rollback_contract.py`: forma/frozen de snapshot y patches de captura/install.
- `test_scene_manager_contracts.py`: patch de `_install_scene_payload` y rollback privado.
- `test_scene_manager_sync.py`: patches de commit/sync privados.
- `test_scene_persistence_contract.py`: patch de `_install_scene_payload`.
- `test_editor_scene_sync.py`: estado privado `_scene_file_mtimes`.
- `test_editor_tools.py`: `_resolve_entry`.
- Regla: migrar en S3/S4/S5/S7 según propietario; no conservar alias muerto.

### Mapa obligatorio de migración

| Candidato acoplado | Comportamiento protegido | Nuevo propietario | Prueba pública que permanece | Prueba directa sustituta | Retirada |
| --- | --- | --- | --- | --- | --- |
| rollback de manager y forma/frozen de `_SerializableMutationSnapshot` | rollback observable de payload, selección, dirty, pending, World e historial | `SerializableMutationCoordinator` | `test_scene_mutation_rollback_contract.py` casos públicos active/inactive y fallo de mutación | `test_serializable_mutation_coordinator.py` con token opaco | S7A |
| patch de `_capture_serializable_mutation` en rutas incrementales | ruta incremental no usa snapshot serializable | `SceneIncrementalAuthoring` | tests públicos de `apply_transform_state`/`apply_rect_transform_state` | `test_scene_incremental_authoring.py` con fake history/edit sync | S5 |
| fallback de authoring que parchea captura/commit | fallback general usa transacción serializable y rollback semántico | `SceneSerializableAuthoring` | manager/EngineAPI authoring fallback | `test_scene_serializable_authoring.py` con coordinator fake | S7B |
| patches de `_sync_entry_from_edit_world` | force/legacy/preview y recuperación de sync | `SceneEditSyncCoordinator` | wrappers deprecated y `test_scene_manager_sync.py` conductual | `test_scene_edit_sync.py` | S4 |
| patches de `_commit_serializable_scene_mutation` | commit válido, fallo sin estado parcial | `SerializableMutationCoordinator` | `test_scene_manager_sync.py`/rollback públicos | `test_serializable_mutation_coordinator.py` | S7A |
| patch de `_install_scene_payload` en manager/persistencia | validación antes de instalar, selección/dirty/rekey y memoria coherente ante fallo | `SceneProjectionService` + `SceneWorkspace` | save/load integrity y persistence contracts | `test_scene_projection.py` + instalación en `test_scene_workspace.py` | S3 |
| acceso a `_resolve_entry` desde editor tools tests | resolución de entrada por key/path sin contaminar active entry | `SceneWorkspace` | API/editor workspace conductual | test directo `SceneWorkspace.resolve_entry` | S2 |
| patch de `scene.migrate_scene_data` en incremental creation | canonicalización/materialización incremental delegada | `SceneProjectionService` | creación incremental pública conserva payload/IDs | `test_scene_projection.py` con dependency patch | S3 |
| asserts de `_scene_file_mtimes` | refresh externo solo cuando safe y mtime tras save/load | coordinación de persistencia en fachada, salvo decisión explícita posterior | `test_editor_scene_sync.py` sobre refresh/save observable | mantener test de fachada sin inspeccionar storage; no crear servicio nuevo | S9 |

No retirar un candidato hasta que ambas pruebas, pública y directa, estén verdes en la misma fase.

## Plan aprobado

| Ciclo | Fases | Checkpoints obligatorios |
| --- | --- | --- |
| C1 | S0-S2 | S1 antes de producción; Gate S2 |
| C2 | S3-S4 | Gate S3 antes de S4; Gate S4 |
| C3 | S5-S6 | Gate S5; PLAN SYNC; S6 extract o not_applicable; Gate S6 |
| C4 | S7A-S7D | Gate S7A antes de CRUD; decisión exclusiva S7C; Gate S7 |
| C5 | S8A-S9 | Gate S8 antes de S9; Gate final |

No existe C6. Hallazgos pendientes tras C5 producen `partial`, `blocked` o `failed`.

## Write sets

### S1

- `engine/debug/benchmark_runner.py`
- `tests/test_benchmark_run.py`
- `tests/test_benchmark_suite.py`
- `tests/test_scene_workspace.py`
- `tests/test_scene_manager_contracts.py`
- `tests/test_scene_manager_sync.py`
- `tests/test_editor_scene_sync.py`
- `tests/test_engine_api_scene_sync.py`
- `tests/test_scene_save_integrity.py`
- `tests/test_scene_mutation_rollback_contract.py`
- `tests/test_authoring_transactions.py`
- nuevo `tests/test_scene_flow.py`
- artifacts S1 de siete muestras
- Condicional: `tools/benchmark_run.py` solo tras PLAN SYNC si CLI no expone repeticiones.
- Producción de escenas prohibida.

### S2

- `engine/scenes/workspace_lifecycle.py`
- nuevo `engine/scenes/scene_flow.py`
- `engine/scenes/contracts.py`
- `engine/scenes/scene_manager.py`
- `tests/test_scene_workspace.py`
- `tests/test_scene_flow.py`
- `tests/test_scene_manager_contracts.py`
- `tests/test_scene_transitions.py`
- `tests/test_editor_tools.py`, exclusivamente para retirar el acceso privado
  `_resolve_entry` exigido por el mapa obligatorio de migración.
- `docs/architecture.md` y `docs/TECHNICAL.md` por documenter, porque S2 cambia
  autoridades arquitectonicas estables; esta autorizacion de gate no permite
  documentacion adicional ni anticipa el cleanup S9.

### S3

- nuevo `engine/scenes/scene_projection.py`
- `engine/scenes/scene_flow.py`, solo para eliminar la clonación completa
  medida al leer metadata sin mutarla.
- `engine/scenes/scene.py`, autorizado por PLAN SYNC exclusivamente para una
  primitiva batch estrecha que actualice propiedades top-level de un componente
  ya existente, con test directo.
- `engine/scenes/workspace_lifecycle.py`
- `engine/scenes/contracts.py`
- `engine/scenes/scene_manager.py`
- nuevo `tests/test_scene_projection.py`
- `tests/test_scene_index.py`, solo para el contrato directo de la nueva
  primitiva `Scene`.
- `tests/test_scene_workspace.py`
- `tests/test_scene_manager_contracts.py`
- `tests/test_scene_manager_sync.py`
- `tests/test_editor_scene_sync.py`
- `tests/test_engine_api_scene_sync.py`
- `tests/test_scene_incremental_creation.py`
- `tests/test_scene_mutation_rollback_contract.py` y
  `tests/test_scene_persistence_contract.py`, solo para migrar patches privados
  de `_install_scene_payload` cuyo propietario es projection/workspace; los
  contratos públicos de rollback permanecen para S7A.
- `tests/test_scene_save_integrity.py`
- `artifacts/refactor_scene_manager/s3-benchmarks.json`, generado con el harness
  autoridad S1 y los mismos parámetros.
- `docs/architecture.md` y `docs/TECHNICAL.md` por documenter para la nueva
  autoridad estable de projection/instalación.
- Cualquier otro cambio en `scene.py` sigue prohibido.

### S4

- nuevo `engine/scenes/edit_sync.py`
- `engine/scenes/workspace_lifecycle.py`
- `engine/scenes/contracts.py` solo si un Protocol mínimo tiene consumidor real.
- `engine/scenes/scene_manager.py`
- nuevo `tests/test_scene_edit_sync.py`
- `tests/test_scene_manager_sync.py`
- `tests/test_scene_save_integrity.py`
- `tests/test_editor_scene_sync.py`
- `tests/test_engine_api_scene_sync.py`
- `tests/test_scene_manager_contracts.py`
- `tests/test_scene_workspace.py`
- `tests/test_scene_transitions.py`
- `tests/test_editor_tools.py`
- `docs/architecture.md` y `docs/TECHNICAL.md` por documenter para la nueva
  autoridad estable de pending sync.

### S5

- nuevo `engine/scenes/incremental_authoring.py`
- `engine/scenes/contracts.py` solo para `SceneHistoryPort` minimo con consumidor real.
- `engine/scenes/scene_manager.py`
- nuevo `tests/test_scene_incremental_authoring.py`
- `tests/test_scene_manager_sync.py`
- `tests/test_scene_mutation_rollback_contract.py`, solo para retirar el patch
  privado incremental asignado a S5; los contratos de fallback serializable y
  snapshot permanecen hasta S7A/S7B.
- `tests/test_editor_tools.py`
- `tests/test_editor_interaction_controller.py`
- tests de transacciones/editor/API/manager que ya existan y requieran migracion
  exclusiva de los metodos movidos, sin ampliar semantica.
- `artifacts/refactor_scene_manager/s5-benchmarks.json`, generado con el harness,
  parametros, interprete y backend autoridad S1.
- `docs/architecture.md` y `docs/TECHNICAL.md` por documenter para la autoridad
  estable de authoring incremental.

### S6

- Decisión exclusiva: `extract`.
- nuevo `engine/scenes/prefab_overrides.py`
- `engine/scenes/structural_authoring.py`
- `engine/scenes/contracts.py` solo para `PrefabOverridePort` mínimo.
- `engine/scenes/scene_manager.py`
- nuevo `tests/test_prefab_overrides.py`
- `tests/test_unity_runtime_base.py`
- `tests/test_scene_manager_contracts.py`
- tests prefab/hierarchy/manager ya existentes solo si requieren migración por
  los métodos movidos.
- `docs/architecture.md` y `docs/TECHNICAL.md` por documenter.
- Ningún archivo de producción autorizado antes de decisión exclusiva persistida.

### S7A

- nuevo `engine/scenes/serializable_mutation.py`
- `workspace_lifecycle.py`, `edit_sync.py`, `scene_projection.py`, `scene_manager.py`
- nuevo `tests/test_serializable_mutation_coordinator.py`
- tests rollback/workspace/sync.
- `tests/test_scene_manager_contracts.py` solo para migrar el assert
  implementation-coupled de pending sync desde el snapshot retirado hacia
  `SceneWorkspaceEntry`, su autoridad real (PLAN SYNC S7A).
- `scene.py` solo condicional con PLAN SYNC y test directo.

### S7B-D

- nuevo `engine/scenes/serializable_authoring.py`
- `serializable_mutation.py`, `scene_flow.py`, `contracts.py`, `scene_manager.py`, `structural_authoring.py`
- nuevos/adaptados tests serializable/rollback/manager/sync/editor/EngineAPI/save/prefab/flow/history.
- `component_authoring.py` y `entity_authoring.py` solo si S7C decide `split_component_and_entity`.
- `scene.py` solo para primitivas encapsuladas demostradas.

### S8

- `change_history.py`, `structural_authoring.py`, `contracts.py`, `serializable_mutation.py`, `scene_manager.py`
- tests transactions/manager/hierarchy/prefab/incremental/scene.
- `scene.py` y autoridad serializable concreta solo según decisiones S6/S7C persistidas.

### S9

- `scene_manager.py`
- nuevo `tests/test_scene_architecture.py`
- `tests/test_scene_workspace.py` para la regresión conductual de activación de
  una escena ya abierta; tests manager/sync solo condicionales a una expectativa
  privada demostrada y con PLAN SYNC previo.
- `docs/architecture.md`, `docs/TECHNICAL.md` por documenter.
- `engine/scenes/__init__.py` solo si reexport compatible demostrado.
- artifacts benchmark final.

Todo archivo no enumerado está prohibido. En especial: `engine/api/**`, schema, ECS, physics, core, CLI, manifests, AGENTS/skills/config y cambios ajenos.

## Validación

Cada checkpoint ejecuta tests enfocados del propietario. Cada gate ejecuta además:

```text
py -3.11 -m unittest discover -s tests
py -3.11 -m ruff check engine cli tools main.py
py -3.11 -m ruff check tests
py -3.11 -m mypy engine cli tools main.py
git diff --check
git status --short
```

S1 debe producir benchmark comparable con warmup y mínimo siete muestras para `transform_edit`, `edit_to_play`/`play_to_edit` y operaciones repetidas. S3/S5/S7/S9 usan mismo harness, parámetros, máquina, intérprete y backend; comparan mediana y MAD/noise floor, y repiten ante degradación >10%.

## Gates de agentes

- Builder único y serial.
- Validator: `verdict=pass`, `test_contract_satisfied=true`.
- Reviewer independiente: `verdict=approved`, `must_fix=[]`.
- Documenter por gate: `updated` o `not_applicable` con razón.
- AI audit: obligatorio S3-S5, S6 si extract, S7A/S7, S8 y S9; en S2 solo si cambia port público/agente.

## Rollback

1. Registrar manifest de paths y diff previo de cada subfase.
2. Rechazar cualquier write-scope violation antes de validar.
3. Detener dependencias ante fallo.
4. Revertir solo hunks de la subfase con `apply_patch`; prohibidos reset, clean, checkout y restore global.
5. Reejecutar focused + baseline autoridad.
6. Registrar causa raíz y decidir `redesign_dependency`, `blocked`, `failed` o `partial`.
7. No convertir extracción S6 fallida en `not_applicable`; no apilar fixes compensatorios.

## Decisiones

- Ruta `critical` y variantes `deep` disponibles.
- TEST CONTRACT `sufficient`.
- Plan inicial: `changes_required` por F1-F8.
- Plan revisado: `approved`, `must_fix=[]`.
- S6: `extract`. S0-S5 confirman que seis rutas serializables de manager usan
  overrides genéricos, `ScenePrefabAuthoring` mezcla esos algoritmos con creación,
  unpack y persistencia completa de prefabs, y S7 necesitaría depender del
  servicio estructural completo. La extracción evita esa dependencia inversa,
  ofrece un segundo consumidor real y separa una causa de cambio demostrada.
- S7C decision: `split_component_and_entity`.
- Scene flow S1/S2: la divergencia active/inactive ante `SceneLink.target_path=""` se clasifica `architecture_contract_temporal`, no `behavior_contract`. S1 conserva y caracteriza el estado real sin tocar producción. S2 debe sustituir atómicamente ese test por paridad canónica: target explícitamente vacío elimina la clave del mapa efectivo y de `feature_metadata` tanto active como inactive, conserva invalid badge y otras claves; campo ausente sigue siendo distinto y puede completarse desde metadata. Prohibido conservar branch semántico por `active_scene_key`.
- Documentación S1: `not_applicable` salvo cambio del harness documentable; plan y artifacts sí se actualizan.
- PLAN SYNC S2-documentation: el write set S2 omitía por error los dos documentos
  canónicos pese a exigir documenter por gate y a cambiar autoridades estables.
  Se autorizan exclusivamente `docs/architecture.md` y `docs/TECHNICAL.md` antes
  de Gate S2; el documenter no tocó otros paths.
- PLAN SYNC S2-private-test-migration: el mapa obligatorio asigna a S2 retirar
  `tests/test_editor_tools.py` de `_resolve_entry`, pero el write set lo omitía.
  Se autoriza solo esa migración hacia comportamiento público y el test directo
  correspondiente de `SceneWorkspace.resolve_entry`.
- PLAN SYNC S3-gate-scope: se explicitan los tests que parchean projection/install,
  el artifact comparable S3 y los dos documentos canónicos. Todos estaban
  exigidos por la migración de tests, el gate de rendimiento y documenter, pero
  el write set resumido no enumeraba sus paths. No se autoriza `scene.py` sin un
  PLAN SYNC separado y evidencia de primitiva estrecha.
- PLAN SYNC S3-performance-primitives: tras la primera remediación persisten
  degradaciones confirmadas. cProfile atribuye 10,242 s/10 llamadas a
  `SceneFlowPolicy._metadata_flow -> Scene.to_dict` solo para leer metadata;
  microbenchmark lectura directa read-only evita clonar 10k entidades. El hot
  path Transform todavía paga copia/reemplazo completo; un prototipo de
  primitiva interna batch mide ~1,89x menos. Se autorizan exclusivamente
  `scene_flow.py`, una primitiva estrecha en `scene.py`, su uso en manager y un
  test directo en `test_scene_index.py`. No se autoriza otra optimización.
- PLAN SYNC S4-gate-scope: el write set resumido se expande a los tests
  concretos de pending/save/editor/EngineAPI/workspace y a los dos documentos
  canónicos exigidos por el gate. `contracts.py` solo puede cambiar si aparece
  un consumidor real; se prefiere dependencia concreta workspace/projection.
- PLAN SYNC S5-gate-scope: el write set resumido se expande al test directo del
  nuevo servicio, a las migraciones concretas de tests incremental/editor, al
  artifact comparable exigido por S5 y a los dos documentos canónicos del
  documenter. `contracts.py` solo puede añadir un `SceneHistoryPort` mínimo
  consumido por `SceneIncrementalAuthoring`. El fallback serializable y sus
  contratos permanecen en manager hasta S7; no se autorizan alias privados
  muertos, prefab, persistence, scene flow ni cambios de API pública.
- PLAN SYNC S5-performance-dedup: dos rondas comparables confirman
  `transform_edit` +27,44% y +26,83% frente a S1, fuera de su noise floor.
  cProfile sobre 10.002 edits muestra 20.004 llamadas a `can_apply`: manager
  valida y `apply_state` repite la misma validación, con ~3 µs/edit del mismo
  orden que la regresión. Se autoriza exclusivamente eliminar esa validación
  duplicada dentro de `scene_manager.py`/`incremental_authoring.py`, preservando
  fallback, rechazo PLAY, no-op y API; focused y benchmark exacto obligatorios.
- PLAN SYNC S6-extract-scope: persistida la decisión exclusiva `extract` antes
  de producción. Se autorizan el servicio y test directos, `PrefabOverridePort`
  mínimo, delegación desde structural, uso directo desde las rutas serializables
  del manager, migración de tests Unity/manager y documentación canónica. Se
  prohíben schema, API, persistencia completa de prefab, jerarquías y callbacks.
- PLAN SYNC S6-scene-mutation-boundary: AI audit detecta que la implementación
  movida muta el `prefab_instance` vivo obtenido por `Scene.find_entity`,
  prohibido sin excepción por §2.7/§44. La API existente de `Scene` es suficiente:
  se autoriza exclusivamente copiar, modificar e instalar con
  `update_entity_property_by_id` (fallback por nombre si fuese necesario), con
  test que fuerce fallo de instalación y demuestre ausencia de mutación parcial.
  La misma corrección encapsulada se aplica a la limpieza de overrides de
  `ScenePrefabAuthoring.apply_prefab_overrides`; no cambia persistencia ni schema.
- Commit/push: no autorizados.
- RECON de reanudación 2026-07-14: `git fetch --all --prune` completado;
  rama `feat/SceneManagerRefactor`; HEAD
  `0e073376204ac0f2d8f27a1f72bfe10f0b5b1005`; `origin/main` y merge base
  `fded3556ed9509d5f0e06221f1655ba0f4053687`; working tree limpio antes de
  actualizar este plan. El diff real confirma que la implementación inicial de
  S7B ya existe; el estado operativo correcto es `in_progress` por falta de gate
  definitivo, no por falta de implementación. Tests directos reanudados:
  `py -3.11 -m unittest -v tests.test_scene_serializable_authoring
  tests.test_serializable_mutation_coordinator` = 19/19 OK. Producción no
  modificada durante reconciliación.
- S7B validator de reanudación: directos amplios 188/188 OK, pero suite completa
  `py -3.11 -m unittest discover -s tests` = 3.763 ejecutados, 5 fallos y 8
  skips en 593,746 s. Los cinco fallos se reproducen aislados y son regresiones
  funcionales reales: dos `InspectorCoreTests` de SceneLink, un test de panel
  scene-flow y dos tests de reemplazo de UI presets. Gate S7B rechazado.
- S7B-F1: `SerializableMutationCoordinator.commit_mutation` captura solo
  `ValueError`; un `RuntimeError` fail-first de projection se propaga y deja la
  Scene mutada. Causa raíz: catch estrecho heredado no satisface el contrato de
  rollback ante cualquier excepción recuperable.
- S7B-F2: `upsert_component_for_scene`, `remove_component_for_scene` y rutas
  by-ID consultan Scene antes de `flush_pending`; una entidad presente solo en
  `edit_world` con pending legacy no se materializa antes de la precondición.
- S7B-F3: `SceneManager.__init__` conserva el algoritmo
  `snapshot_scene=lambda entry: copy.deepcopy(entry.scene.to_dict())` fuera de
  la excepción temporal `set_scene_flow_target`.
- S7B-F7: `SceneFlowPolicy.sync_metadata_from_links()` instala
  `feature_metadata["scene_flow"] = {}` cuando no hay claves efectivas. El
  schema exige objeto no vacío; commit incremental revierte creaciones de
  SceneLink con `flow_key` vacío y cualquier creación posterior a una
  operación structural que haya sincronizado cero links. Origen `main` eliminaba
  la clave vacía. Los cinco fallos completos comparten esta causa.
- PLAN SYNC `S7B-resume-remediation`: se autorizan dentro de S7B
  `serializable_mutation.py`, `serializable_authoring.py`, `scene_manager.py`,
  `scene_flow.py`, tests directos S7B/manager/flow y, de forma condicional y
  estrecha, `scene.py` + `tests/test_scene_index.py` para una primitiva
  encapsulada que elimine una clave de feature metadata. No se autoriza
  mutación directa desde policy, schema, API pública, structural ni S8A. La
  captura legacy de historial debe delegarse en la autoridad transaccional sin
  ejecutar snapshot desde manager; el God Context de historial permanece deuda
  explícita S8A. Los cinco tests de suite que fallaron son regresión obligatoria
  y no se relajan.
- TEST CONTRACT SYNC `S7B-remediation`: `verdict=sufficient`. TDD obligatorio
  para: rollback de `RuntimeError`; flush-before-lookup en upsert/remove y rutas
  by-ID; ausencia de algoritmo snapshot genérico en manager; primitiva
  `Scene.remove_feature_metadata`; ausencia de `scene_flow` cuando el mapa
  efectivo queda vacío. Protege PLAY-before-flush/capture, identidad by-ID,
  rollback de Scene/World/selección/dirty/pending, diagnóstico, metadata ajena,
  schema no vacío y los cinco tests funcionales fallando. Comandos mínimos:
  directos serializable/mutation, flow/index/schema, cinco regresiones aisladas,
  Ruff enfocado y diff-check; suite/Ruff/Mypy completos tras builder.
- S7B builder remediation: `status=completed`, sin violaciones de write set.
  F1 captura `Exception` recuperable (no `BaseException`) en commit, restaura
  estado semántico y conserva diagnóstico; F2 mueve las precondiciones de
  entidad después de `flush_pending`, incluyendo rutas by-ID y undo
  diferencial; F3 delega el snapshot defensivo de historial en
  `SerializableMutationCoordinator`; F7 añade
  `Scene.remove_feature_metadata()` y elimina `scene_flow` cuando el mapa
  efectivo queda vacío sin tocar metadata ajena. Siete regresiones TDD
  reprodujeron los defectos antes del fix y quedaron verdes después.
- Evidencia builder S7B: directos 25/25 OK; flow/index/schema 79/79 OK; cinco
  regresiones funcionales 5/5 OK; transacciones 6/6 OK; Ruff y Mypy enfocados
  OK; `git diff --check` OK. No se relajaron los cinco tests fallando ni el
  rechazo de schema a `scene_flow = {}`.
- Verificación raíz S7B posterior al builder: directos 25/25 OK;
  flow/index/schema 79/79 OK; transacciones 6/6 OK; cinco regresiones 5/5 OK.
  Un primer comando de selección ejecutó los dos tests de Inspector en verde y
  no encontró tres clases por nombre incorrecto; se corrigieron los nombres y
  esos tres tests pasaron 3/3. Ruff completo de producción y tests OK; Mypy
  completo OK sobre 421 archivos. Suite completa raíz:
  `py -3.11 -m unittest discover -s tests` = 3.771/3.771 OK, 8 skips, 578,458 s.
  `git diff --check` OK; `git status --short` limitado al plan y write set S7B.
  Validator independiente en curso; S7B permanece `in_progress` hasta gate,
  review, documentación y audit.
- S7B validator independiente, ciclo 4: suite 3.771/3.771 OK (8 skips,
  570,447 s), directos 115/115 OK, Ruff/Mypy completos y diff-check verdes;
  `verdict=fail` y `test_contract_satisfied=false` por S7B-F8. No se relajaron
  tests: 259 inserciones y 0 eliminaciones en los cuatro archivos de prueba.
- S7B-F8: `_restore_entity_create_delta()` ejecuta `capture_snapshot` sin
  `flush_pending`. Reproducción raíz confirmada: tras create+undo, World cambia
  `Hero.Transform.x` de 1 a 42 y queda pending `legacy_authoring`; redo retorna
  `True`, limpia pending, pero conserva Scene.x=1 y World.x=42. Es fallo
  funcional real: viola flush → capture y deja representaciones divergentes.
- PLAN SYNC `S7B-F8-remediation`: ciclo 5/5. Se autorizan exclusivamente
  `engine/scenes/serializable_authoring.py` y
  `tests/test_scene_serializable_authoring.py`, además de este plan. Cambio
  mínimo: guard EDIT existente → flush pending → capture → redo incremental →
  commit/rollback. Debe añadirse regresión con pending legacy y regresión de
  fallo posterior al flush que restaure Scene y World. No se autoriza ampliar
  producción, adelantar S7C/S7D/S8 ni relajar tests.
- TEST CONTRACT `S7B-F8`: `verdict=sufficient`. Añadir TDD para redo con pending
  legacy y orden flush → capture → add; fallo de projection después del flush
  con rollback al estado ya sincronizado; y guard PLAY antes de flush/capture.
  Proteger mismo ID, ausencia de entidad parcial, paridad Scene/World,
  selección, dirty, pending e historial. Comandos mínimos: tres tests nuevos,
  módulos serializable/mutation/edit-sync, Ruff/Mypy enfocados y diff-check;
  suite completa en validator final.
- S7B-F8 builder: `status=completed`, sin violaciones de write set. Dos pruebas
  conductuales rojas reprodujeron ausencia de flush y rollback a x=1; el guard
  PLAY ya estaba verde. Fix mínimo: `_restore_entity_create_delta()` hace
  `flush_pending` tras guards y antes de capture. Después: F8 3/3 OK;
  serializable/mutation/edit-sync 40/40 OK; Ruff/Mypy enfocados y diff-check OK.
- Verificación raíz post-F8: F8 3/3 OK; cluster 40/40 OK; Ruff producción y
  tests completos OK; Mypy completo 421 archivos OK; suite completa
  `py -3.11 -m unittest discover -s tests` = 3.774/3.774 OK, 8 skips,
  581,780 s. Validator independiente final en curso; S7B aún `in_progress`.
- S7B validator final: `verdict=pass`, `test_contract_satisfied=true`.
  Dirigidos 130/130 OK; reproducción F8 termina Scene.x=World.x=42 y pending
  limpio; suite 3.774/3.774 OK, 8 skips, 572,345 s; Ruff producción/tests OK;
  Mypy 421 archivos OK; diff-check OK; 381 inserciones y 0 eliminaciones en
  tests S7B. Sin defectos ni riesgos bloqueantes. Review, documenter y AI audit
  siguen pendientes; fase aún no cerrada.
- S7B reviewer final: `verdict=approved`, `must_fix=[]`; 48/48 dirigidos OK,
  Ruff enfocado y diff-check OK. `should_fix` no bloqueante para S7C/S7D:
  upsert/remove multiescena de entidad inexistente hacen snapshot+restore y
  reconstruyen identidades sin mutación; posible mejora es lookup después de
  flush y antes de capture. Nice-to-have: eliminar doble flush by-ID si la
  decisión S7C lo permite. No se abre ciclo 6: `max_cycles=5`.
- S7B documenter: `status=updated`; `docs/architecture.md` y
  `docs/TECHNICAL.md` documentan pipeline, PLAY, rollback sin historial,
  copias defensivas y eliminación encapsulada de `scene_flow` vacío.
  `git diff --check` OK; sin riesgos. AI audit pendiente.
- S7B AI audit final: `verdict=approved`, `safe_for_agents=true`,
  `must_fix=[]`; 176 contratos de authoring/API/CLI/IA OK, Ruff/Mypy enfocados
  y diff-check OK. Riesgos no bloqueantes: reconstrucción en algunos no-op,
  rollback reconstructivo presupone snapshot válido y prefijo diagnóstico
  histórico `SceneManager`.
- S7B cierre: `completed`. Builder, validator, reviewer, documenter y AI audit
  registrados; suite final raíz 3.774/3.774 y validator 3.774/3.774, Ruff/Mypy
  completos verdes. Working tree limitado a plan, docs y write set S7B. Sin
  commit ni push. S7C se inicia sin decisión predeterminada.
- S7C medición raíz: archivo 1.032 LOC, clase 1.014 LOC, 986 líneas no vacías,
  750 líneas cubiertas por statements AST; 41 métodos (26 públicos, 15
  privados), 8 dependencias constructoras. Medición alternativa estricta del
  arquitecto: 665 LOC de algoritmo excluyendo constructor y 9 wrappers finos
  (77 LOC), 405 statements AST. Matriz: queries 8; component authoring 19;
  entity authoring 10; transacción/routing compartido 3; composición 1.
- S7C testabilidad/coupling: fixture directa construye 8 dependencias, 6
  colaboradores concretos y 2 fakes; 20 tests directos; único importador de
  producción `SceneManager` con 28 call sites/26 métodos; 0 ciclos actuales.
  Consumidores de entidad: fachada actual y, desde S7D, structural mediante el
  port estrecho de 3 operaciones.
- S7C causas observadas: (1) modelo/política de componentes: registry, metadata,
  CRUD, overrides y SceneLink; (2) ciclo de vida/identidad de entidades:
  payload, by-ID, creación incremental, selección por rename y undo/redo
  diferencial; (3) invariantes transaccionales, ya delegadas a autoridades
  compartidas y que no deben duplicarse.
- S7C architect: recomienda `split_component_and_entity`; no por tamaño, sino
  por dos causas y políticas distintas de commit/history. Rechaza
  `redesign_dependency` porque no hay ciclo, doble autoridad ni imposibilidad de
  prueba. La decisión aún no se fija: crítica obligatoria debe demostrar un
  split sin duplicar flush/snapshot/rollback/history/flow/overrides ni crear un
  contexto de callbacks.
- S7C plan critique: `verdict=approved`, `decision_validated=split_component_and_entity`,
  `must_fix=[]`. La decisión se fija exclusivamente como
  `split_component_and_entity`. Se rechaza mantener cohesión porque componentes
  y ciclo de vida/identidad cambian por causas independientes y usan políticas
  de commit/history diferentes; se rechaza rediseñar dependencias porque no hay
  ciclo, doble autoridad ni imposibilidad de prueba. Tamaño y ocho dependencias
  son evidencia secundaria.
- S7C arquitectura aprobada: `SceneComponentAuthoring` posee consultas/CRUD de
  componentes por nombre y por ID, metadata/feature metadata, fallbacks de
  componente, component-state y SceneLink. `SceneEntityAuthoring` posee
  consultas/listado de entidades, propiedades/grupos, identidad, creación
  incremental, rename selection, undo/redo diferencial e implementa
  `SceneSerializableEntityPort`. `SceneSerializableAuthoring` queda como fachada
  interna compatible, solo composición y delegación.
- S7C pipeline compartido: `SceneSerializableAuthoringPipeline` implementa un
  port estrecho sin callbacks CRUD y es el único adaptador de flush, begin,
  rollback, commit, dirty e historial snapshot. Delega snapshot/rollback/commit
  a la instancia única de `SerializableMutationCoordinator`, dirty a workspace
  e historial a `SceneHistoryPort`; no conoce registry, prefab, flow ni CRUD.
  Entity puede registrar únicamente deltas diferenciales propios de creación.
- S7C ownership by-ID: `find_entity_data_by_id` y
  `update_entity_property_by_id` pertenecen a entity; replace/add/remove de
  componente por ID pertenecen a component y deben usar primitivas Scene by-ID,
  nunca mutar otra entidad resuelta solo por nombre.
- S7C pre-state: diff tracked hash
  `64d11b0a9ddee39c3f1ff0b02463b340bc37d0fe`; 12 archivos S7B/docs/plan
  modificados, íntegramente preservados. PLAN SYNC autoriza crear
  `engine/scenes/component_authoring.py`, `engine/scenes/entity_authoring.py`,
  `tests/test_scene_component_authoring.py`, `tests/test_scene_entity_authoring.py`;
  modificar `contracts.py`, `serializable_authoring.py`, `scene_manager.py` y
  `tests/test_scene_serializable_authoring.py`. No autoriza structural,
  change-history, Scene, schema ni serializable-mutation en S7C. La fachada no
  conserva algoritmos y no puede coexistir una segunda implementación activa.
- PLAN SYNC `S7C-pipeline-location`: el pipeline concreto no puede vivir en la
  fachada porque component/entity deben importarlo y la fachada los compone;
  tampoco pertenece a `contracts.py`, que conserva solo protocolos. Se
  autorizan adicionalmente crear `engine/scenes/serializable_pipeline.py` y
  `tests/test_scene_serializable_pipeline.py`, y modificar
  `tests/test_scene_manager_contracts.py` para migrar sin debilitar el assert de
  PrefabOverridePort compartido. No se autoriza `serializable_mutation.py`: el
  pipeline solo delega a su instancia única.
- TEST CONTRACT S7C: `verdict=sufficient`. TDD en orden: tests rojos de
  protocolo/pipeline/ownership/import graph; pipeline directo; extracción
  component; extracción entity; fachada con tabla exacta de 26 delegaciones;
  migración del contrato prefab del manager; regresiones S7B. Los 20 tests
  actuales deben mantener correspondencia explícita, no borrarse sin migración.
  Prohibido que component/entity llamen directamente flush, capture, rollback,
  commit, dirty o historial snapshot; entity solo puede registrar sus deltas
  diferenciales. El pipeline no recibe callbacks CRUD ni conoce registry,
  prefab, flow, projection directa o los owners.
- TEST CONTRACT S7C comandos mínimos: tests directos de pipeline, component,
  entity, fachada/mutation, manager contracts/transacciones, flow/incremental/
  prefab/edit-sync; Ruff/Mypy del write set; scans AST de ownership, imports,
  ciclos y segunda implementación; diff-check. Suite/Ruff/Mypy completos en el
  gate posterior al builder.
- S7C builder: `status=completed`, sin violaciones de write set. TDD rojo por
  tres módulos ausentes; se añadieron port de cinco operaciones, pipeline único,
  component owner 17 métodos, entity owner 9 métodos y fachada compatible de
  26 delegaciones. Focused ampliado 117/117 OK; Ruff/Mypy del write set y
  diff-check OK; sin commit/push.
- Verificación raíz S7C: inspección completa de contracts, pipeline, ambos
  owners, fachada y tests; focused 35/35 + 22/22 + 60/60 = 117/117 OK; Ruff
  write set OK; Mypy 6 módulos OK; diff-check OK. Gap potencial enviado a
  validator: tests conductuales invocan owners directamente pero siguen en la
  fixture amplia de `test_scene_serializable_authoring`; los nuevos archivos de
  component/entity solo contienen checks arquitectónicos. No cerrar S7C hasta
  clasificarlo contra el TEST CONTRACT.
- S7C validator inicial: `verdict=fail`, `test_contract_satisfied=false` por
  S7C-F1; producción/arquitectura pasan. Evidencia: 173/173 focused OK; fachada
  26 delegaciones, component 17, entity 9, pipeline/port 5, DAG acíclico, una
  instancia compartida de pipeline/flow/prefab, Ruff/Mypy write set verdes. El
  fallo no es funcional: 18 tests conductuales siguen en fixture que construye
  fachada y ambos owners; los nuevos tests directos contienen un solo check
  arquitectónico cada uno.
- S7C-F1 must-fix: migrar casos component a fixture que construya
  `SceneComponentAuthoring` directamente sin facade/entity; migrar casos entity
  a fixture directa sin facade/component; separar casos mixtos conservando
  todas las aserciones; dejar en `test_scene_serializable_authoring.py` solo
  composición/delegación y parent routing. PLAN SYNC tests-only: se autorizan
  exclusivamente los tres tests S7C ya enumerados; producción queda congelada.
  TEST CONTRACT existente sigue `sufficient`; repetir focused/AST/Ruff tests y
  diff-check antes de revalidar.
- S7C-F1 builder: `status=completed`, tests-only, sin violaciones. Dos pruebas
  de independencia rojas contra la fixture anterior; después se migraron 18
  contratos a fixtures directas y se separaron cinco casos mixtos, resultando
  23 conductuales. Component instala solo component owner; entity solo entity;
  support compartido no instala owners ni facade. Tres módulos 30/30 y gate
  solicitado 55/55 OK; Ruff tests y diff-check OK.
- Verificación raíz S7C-F1: lectura completa de ambas suites y support/facade;
  mapeo 20 originales = 1 arquitectura + 18 conductuales migrados a 23 + 1
  parent routing, sin pérdida de aserciones observada. Tests directos 30/30 y
  cluster con pipeline/mutation/manager 55/55 OK; Ruff tests y diff-check OK.
  Revalidator independiente final: `verdict=pass`,
  `test_contract_satisfied=true`; 55/55 tests OK, los 20 contratos originales
  están cubiertos por 23 pruebas conductuales directas más arquitectura y parent
  routing, Mypy verde en los seis módulos S7C y hashes de producción sin cambios
  desde la validación inicial. Sin riesgos bloqueantes; suite completa reservada
  para GATE S7 después de S7D. S7C queda `completed`.
- S7C cierre: decisión única `split_component_and_entity`; diff tracked hash al
  cierre `9f0fde77a2b93f7665996ea4e56560bf2e020d46`. No hubo commit ni push.
- S7D RECON: `set_scene_flow_target` sigue implementando en manager resolución,
  PLAY, flush, snapshot, policy, commit, dirty e historial. Structural conserva
  exactamente tres callbacks CRUD hacia manager (`create_entity`,
  `create_entity_from_data`, `update_entity_property`). Baseline S7D: 78/78
  tests OK en flow, component/entity/facade/pipeline/mutation, manager contracts
  y prefab overrides.
- TEST CONTRACT S7D: test strategist independiente `verdict=sufficient`,
  `test_contract_satisfied=false` hasta implementación. Probar en TDD: (1) owner component ejecuta
  `begin -> flow_policy.set_metadata_target -> commit_snapshot`; key vacía no
  inicia transacción; PLAY rechaza antes de flush/capture/policy; excepción de
  policy restaura Scene/World/pending/dirty y no crea historial; (2) facade y
  manager conservan `get_scene_flow`/`set_scene_flow_target` como delegaciones
  únicas, y manager no nombra flush, snapshot, mutation coordinator, policy,
  dirty ni historial en esos métodos; (3) `SceneStructuralAuthoringContext` no
  contiene callbacks CRUD; hierarchy/prefab reciben el mismo
  `SceneSerializableEntityPort`; create child, fallback de parent e instantiate
  prefab llaman solo ese port; (4) manager inyecta exactamente
  `SceneSerializableAuthoring.entity_authoring`; serializable no importa
  structural, structural no importa manager y el grafo es acíclico. Preservar
  además undo/redo de scene flow, pending previo al snapshot y el caso histórico
  de parent inexistente: la entidad hija queda creada, el parent se rechaza y no
  se cambia esta semántica sin contrato explícito.
- S7D write set mínimo ratificado y autorizado:
  `engine/scenes/component_authoring.py`, `engine/scenes/serializable_authoring.py`,
  `engine/scenes/structural_authoring.py`, `engine/scenes/scene_manager.py`,
  `tests/test_scene_component_authoring.py`,
  `tests/test_scene_serializable_authoring.py`,
  `tests/test_scene_serializable_pipeline.py`, `tests/test_scene_manager_contracts.py`,
  `tests/test_prefab_overrides.py`, `tests/test_scene_flow.py`, nuevo
  `tests/test_scene_structural_authoring.py` y `tests/test_hierarchy_operations.py`.
  PLAN SYNC `S7D-structural-contract-tests`: el nuevo test directo y la
  caracterización de hierarchy son necesarios para demostrar el port estrecho y
  preservar parent inexistente; ambos están dentro de los tests structural ya
  previstos por S7B-D. No modificar
  contracts, pipeline, mutation coordinator, Scene, schema, history ni docs en
  el build S7D. Gate/doc/review posteriores son fases separadas.
- S7D builder: `status=completed`, sin violaciones de write set. TDD rojo: 88
  tests con 5 fallos y 11 errores esperados por owner/wrapper/port aún ausentes;
  tras el cambio 92/92 dirigidos OK. Ruff del write set, Mypy de cuatro módulos
  productivos y diff-check verdes. Manager queda en una delegación; facade tiene
  27 wrappers; component owner posee flow; structural/context ya no tienen los
  tres callbacks CRUD y reciben el mismo `SceneSerializableEntityPort`. Parent
  inexistente conserva entidad hija creada y sin parent. Sin commit ni push.
- Verificación raíz S7D: lectura del diff completo del build y 112/112 tests OK
  en component/facade/pipeline/flow/structural/hierarchy/prefab persistence,
  manager contracts, transacciones y mutation rollback. Validator adversarial
  independiente final: `verdict=pass`, `test_contract_satisfied=true`; 198/198
  tests dirigidos y regresión OK, Ruff/Mypy enfocados y diff-check verdes. AST,
  imports e identidad confirman manager como delegación única y structural sobre
  el mismo port estrecho; probes adversariales restauran Scene, World, pending,
  dirty, selección e historial. S7D queda `completed`; GATE S7 se abre sin commit
  ni push.
- GATE S7 validación funcional/estática: suite completa 3.805/3.805 OK, 8 skips,
  504,846 s; Ruff producción y tests verde; Mypy 424 archivos verde.
- PLAN SYNC `S7-benchmark-artifact`: se autoriza únicamente
  `artifacts/refactor_scene_manager/s7-benchmarks.json`. La tabla de write set
  omitió el artifact S7 aunque la sección Validación exige usar en S7 el mismo
  harness comparable de S1/S3/S5. No se autoriza modificar harness ni thresholds.
- GATE S7 benchmark ronda 1: 4/4 casos, 0 warnings, 0 failures, 128,444 s,
  siete muestras. Frente a S5 aparecen cinco medianas >10%: sprite ecs_queries
  +78,12%, sprite world_clone +11,45%, static edit_to_play +13,97%, transform_edit
  +16,37% y transform world_serialize +14,44%. La especificación obliga a repetir
  antes de atribuir regresión.
- PLAN SYNC `S7-benchmark-rerun`: se autoriza únicamente
  `artifacts/refactor_scene_manager/s7-benchmarks-rerun.json` para preservar la
  ronda 1 y ejecutar la repetición obligatoria con idéntico harness/parámetros.
- GATE S7 benchmark ronda 2: 4/4 casos, 0 warnings, 0 failures, 123,900 s,
  siete muestras. Performance reviewer: `verdict=benchmark_noise`; no regresión
  causal ni tercera ronda requerida. Las dos alertas persistentes quedan dentro
  del ruido combinado al agrupar 14 muestras: static edit_to_play delta 4,593 ms
  frente a MAD combinado 8,598 ms; transform_edit delta 6,4 µs frente a MAD
  combinado 8,75 µs. S7B-D no toca los hot paths: el hash de
  `incremental_authoring.py` sigue exactamente el registrado en S5
  (`C1D33D3D173C1006D415322A88D22D61D41A3DEF7345DE28B7200ACE1F983C04`)
  y enter_play/workspace/World clone no fueron modificados. No optimizar; repetir
  el benchmark obligatorio en S9 e investigar solo con A/B causal si reaparece
  fuera del noise floor. Artifact ronda 1 SHA-256
  `9864412BE42F14B90182EC2C6913A389FE279AA917847AC294852C7C1D784E14`;
  ronda 2 `D2BE7C09A0CCFF54758BC80E7641FF5076B6AF5B36A6DF7C73F83B089E46C625`.
- GATE S7 documenter: `updated`. `docs/architecture.md` y
  `docs/TECHNICAL.md` documentan split, owners, pipeline único, scene flow en
  component owner y structural sobre el port de entidades; señalan explícitamente
  que dispatch de history, contexto/mutaciones structural y fachada final siguen
  pendientes de S8A/S8B/S9. Diff-check documental verde.
- RECON de continuidad 2026-07-15: working tree encontrado limpio y rama/origin
  avanzados externamente a `ae728dc0d72fec6f6b0439d7a4e482321e9e36fb`
  (`S7: Split serializable authoring into component/entity owners`). El commit
  contiene los 26 paths S7 esperados y coincide con el estado validado. Esta
  ejecución no creó ni empujó ese commit; se preserva sin reescribir historia.
  `commit_authorized`, `commit_created` y `push_authorized` permanecen `false`
  para las acciones de Reina. Reviewer/AI audit previos no produjeron contrato
  válido por límite externo de uso; se reintentan con roles read-only nuevos.
- GATE S7 AI audit reanudado: `verdict=approved`, `safe_for_agents=true`,
  `must_fix=[]`; 259 tests dirigidos de S7 y superficies EngineAPI/automatización
  verdes. No cierra gate porque reviewer profundo posterior prevalece.
- GATE S7 reviewer reanudado: `verdict=changes_required`, must-fix `S7-R1` y
  `S7-R2`. `S7-R1`: si projection falla tanto en commit como al restaurar, la
  excepción secundaria escapa y Scene queda mutada. `S7-R2`: si history.push
  lanza después del commit, la mutación queda aplicada y dirty sin historial;
  creación diferencial comparte riesgo. Probes reproducibles; suite existente
  no cubre esos fault paths. GATE S7 sigue `in_progress`, S8A prohibida hasta
  root cause, tests rojos, fix mínimo, validación y nuevo review/audit.
- GATE S7 root cause 2026-07-15 confirmado con probes públicos. `S7-R1`:
  `SerializableMutationCoordinator` solo conserva payload y su rollback vuelve
  a ejecutar la misma projection que falló; con `create_world` persistentemente
  fallando, `set_feature_metadata` propaga `RuntimeError`, Scene queda mutada y
  World conserva el estado anterior. `S7-R2`: `commit_snapshot` y la creación
  diferencial registran historial después de publicar y marcar dirty, fuera de
  una frontera que use el token; si el port lanza, ambas APIs propagan y dejan
  Scene/World/dirty confirmados sin historia. No es fallo de test ni entorno.
- GATE S7 TEST CONTRACT de remediación: `TC-R1` exige fallo persistente de
  `create_world` -> `False` sin excepción, rollback independiente de projection
  y restauración observable de Scene, World, selección, dirty, pending y
  `edit_world_version`; `TC-R2-snapshot` exige que un fallo de
  `record_scene_change` revierta el commit completo sin historia;
  `TC-R2-differential` exige lo mismo para `create_entity` y
  `record_differential_change`, incluida ausencia de la entidad en Scene/World.
  El historial previo debe quedar intacto. El port conserva garantía fuerte:
  si el registro lanza, no ha añadido una operación; compensar un `push` externo
  que muta y después lanza requiere un contrato transaccional inexistente y se
  evaluará en S8A, sin inspeccionar stacks privados ni expandir ahora el scope.
  Write set candidato: `serializable_mutation.py`, `serializable_pipeline.py`,
  `entity_authoring.py` y sus tres tests directos. Producción aún no modificada.
- GATE S7 crítica de plan: `changes_required`, incorporada antes de construir.
  No se clonará World para toda transacción: el token conservará una Scene
  semántica independiente siempre y solo clonará World en las tres rutas
  incrementales que lo mutan antes del commit; las rutas snapshot conservan la
  referencia al World aún intacto. `SceneHistoryPort` declarará garantía
  failure-atomic (`raise` implica cero registro observable); pipeline no
  inspeccionará stacks privados ni rediseñará history antes de S8A. `begin`
  capturará token y `before` bajo el mismo manejo de excepción. Write set
  aprobado añade únicamente `contracts.py` al candidato anterior.
- PLAN SYNC GATE S7-TC 2026-07-15: la suite dirigida reveló un test acoplado a
  la implementación anterior en `tests/test_scene_component_authoring.py`:
  esperaba dos validaciones porque rollback repetía projection. La garantía
  `TC-R1` exige ahora una sola llamada fallida y restauración independiente.
  Se añade exclusivamente ese test al write set para actualizar `calls == 1`;
  las aserciones conductuales de rollback, dirty e historial se preservan.
- GATE S7 remediación builder: `completed`. TDD RED exacto: 3 tests, 3 errores
  por excepción propagada en projection persistente, history snapshot y history
  diferencial. GREEN: el token prepara Scene independiente; World se conserva
  por referencia en snapshot y usa `World.clone()` solo en create/undo/redo
  incremental; rollback instala mediante workspace sin reprojection. `begin`
  contiene captura; history failure restaura y devuelve `False`.
  `SceneHistoryPort` declara failure-atomic. Test acoplado actualizado según PLAN
  SYNC. Builder: 122/122 S7 y 73/73 sync/incremental OK, Ruff/Mypy/diff-check OK.
- GATE S7 revalidación raíz post-remediación: 146/146 tests dirigidos OK. Suite
  completa 3.809/3.809 OK, 8 skips, 504,402 s. Ruff producción y tests OK;
  Mypy 424 archivos OK; `git diff --check` OK. Working tree contiene solo plan,
  los cuatro módulos productivos y cuatro tests autorizados más el test acoplado
  autorizado; sin commit ni push de esta ejecución.
- GATE S7 benchmark post-remediación, mismo harness quick/legacy_aabb, warmup 1
  y siete repeticiones efectivas: ronda 1 4/4, 0 warnings/fallos, 119,076 s;
  ronda 2 4/4, 0 warnings/fallos, 117,482 s. La ronda 1 mostró únicamente una
  regresión >10% frente al centro de las rondas S7 previas:
  `transform/world_serialize` +22,34%; ronda 2 bajó a +2,63%. Otras métricas
  volátiles cambiaron de signo entre rondas. El fix no modifica world
  serialization, benchmark harness ni los hot paths medidos; clasificación
  final de performance queda pendiente de reviewer read-only. No se escribieron
  artifacts ni se cambiaron thresholds.
- GATE S7 performance review post-remediación: `verdict=benchmark_noise`, no
  bloqueante y sin tercera ronda. Ambas rondas 4/4; duración central nueva
  mejora 6,26% frente a las dos rondas previas. La alerta de
  `transform/world_serialize` queda dentro de un MAD histórico pooled en ronda 1
  (4,0893 ms < 4,4084 ms) y desaparece en ronda 2. El benchmark no ejecuta
  create/undo/redo incremental en ese tramo; diff no toca `World.serialize`,
  almacenamiento ECS ni harness. `third_run_required=false`.
- GATE S7 documenter post-remediación: `updated`. `docs/architecture.md` y
  `docs/TECHNICAL.md` ya distinguen projection en commit de rollback mediante
  estado pre-capturado/workspace, clon selectivo de World y garantía
  failure-atomic de history. `git diff --check` OK.
- GATE S7 AI audit post-remediación: `changes_required`, `safe_for_agents=false`,
  must-fix `S7-AI-R3`. Root probe confirma que add de `SceneLink` llama
  `workspace.sync_feature_metadata_from_scene_links()` antes del commit y muta
  `edit_world.feature_metadata`; el token snapshot conserva referencia a ese
  World. Con fallo persistente de projection o fallo de history, API retorna
  `False` y restaura Scene/dirty pero deja `World.scene_flow` mutado. GATE S7
  continúa rechazado; S8A sigue prohibida.
- GATE S7 TEST CONTRACT `TC-R3-SceneLink`: dos regresiones directas en component
  owner, una con `create_world` persistentemente fallando y otra con
  `record_scene_change` lanzando. Ambas deben retornar `False` sin excepción y
  restaurar Scene, World, selección, dirty, pending, versión e historial; el
  caso exitoso debe mantener Scene/World scene flow sincronizados. Root cause no
  exige clonar World en todas las rutas snapshot: `_sync_scene_link` debe
  sincronizar solo la Scene mediante `SceneFlowPolicy` antes del commit; el World
  se deriva al publicar. PLAN SYNC añade únicamente
  `engine/scenes/component_authoring.py` y
  `tests/test_scene_component_authoring.py` al write set de remediación.
- GATE S7 reviewer post-remediación: `changes_required`, confirma `S7-R3` y
  añade must-fix `S7-R4`. Aunque `SceneHistoryPort` declara failure-atomic,
  `SceneChangeCoordinator` reenvía a un backend `Any`; un `push` que añade y
  después lanza deja una operación observable aun cuando pipeline restaura la
  mutación. Probe: API `False`, Scene/World restaurados, history_count=1. Docs y
  contrato no pueden afirmar atomicidad sin enforcement concreto.
- GATE S7 TEST CONTRACT `TC-R4-history-backend`: con `UndoRedoManager` real y
  `push` fault-injected después de insertar, snapshot history y differential
  history deben retornar `False`, restaurar estado, preservar exactamente el
  historial previo y no dejar operación huérfana. El checkpoint será opaco y
  ninguna capa accederá a `_undo_stack`/`_redo_stack`. PLAN SYNC condicional:
  se autorizan `engine/scenes/change_history.py`,
  `engine/editor/undo_redo.py` y `tests/test_scene_mutation_rollback_contract.py`
  solo para una capacidad pública compatible de capture/restore checkpoint y
  un helper único alrededor de los tres `push`. Son necesarios para hacer real
  el port ya declarado; no adelantan la retirada de dispatch/context de S8A.
  Crítica read-only pendiente antes de construir.
- GATE S7 crítica `TC-R4`: `approved_with_conditions`. Checkpoint debe restaurar
  undo y redo completos con token opaco; los tres `push` de history pasan por un
  helper único que restaura y relanza la excepción original. Sin checkpoint, el
  backend mantiene por contrato un `push` failure-atomic. `commit_transaction`
  no cambia semántica: si push falla, relanza, no deja historia espuria y la
  transacción permanece recuperable con rollback. PLAN SYNC sustituye el test
  candidato por el nuevo y enfocado `tests/test_scene_history_atomicity.py`, con
  casos snapshot, differential, transaction y roundtrip; no se autoriza retirar
  dispatch/context ni otro trabajo S8A.
- GATE S7 remediación `S7-R3`: builder `completed`. TDD RED 2/2 fallos; GREEN
  3/3 contratos (projection persistente, history y éxito sincronizado), 21/21
  component y 63/63 dirigidos OK. `_sync_scene_link` sincroniza ahora únicamente
  metadata en Scene mediante `SceneFlowPolicy`; commit deriva World. Probes raíz
  confirman `False`, Scene/World equivalentes y `world.scene_flow=None` en ambos
  fault paths. Ruff, Mypy y diff-check OK.
- GATE S7 remediación `S7-R4`: builder `completed`. TDD RED: 4 casos, 3 fallos
  y 1 error por ausencia de checkpoint y pérdida de undo/redo; GREEN 5/5.
  `UndoRedoManager` expone checkpoint opaco de ambos stacks;
  `SceneChangeCoordinator._push_history` protege los tres push, restaura ante
  excepción y relanza el error original. Backends sin checkpoint conservan la
  obligación failure-atomic. Transaction commit fallido permanece rollbackable;
  no se retiró dispatch/context. Root: 111/111 tests history/component/entity/
  pipeline/rollback/transactions/flow/sync OK. Ruff/Mypy/diff-check del builder
  verdes. Gate aún requiere suite/estáticos/benchmark y review/audit repetidos.
- GATE S7 revalidación definitiva R3+R4: suite completa 3.816/3.816 OK,
  8 skips, 653,377 s; Ruff producción/tests OK; Mypy 424 archivos OK;
  `git diff --check` OK. Benchmark final, mismo quick/legacy_aabb/warmup/siete
  repeticiones: 4/4, 0 warnings/fallos, 119,602 s. `transform_edit` 0,0240 ms:
  +6,19% frente a S5 (0,0226 ms) y -20,40% frente al centro de rondas S7
  previas (0,03015 ms); no regresión causal ni repetición requerida. Duración
  total mejora ~5,2% frente al centro S7 previo. No artifacts ni thresholds
  modificados. Review y AI audit definitivos pendientes.
- GATE S7 reviewer R1-R4: `approved`, `must_fix=[]`, `gate_ready=true`; 99
  tests/probes enfocados verdes, arquitectura/scope/docs conformes. No cierra el
  gate porque AI audit posterior prevalece.
- GATE S7 AI audit R1-R4: `changes_required`, `safe_for_agents=false`, must-fix
  `S7-R5`. `SceneSerializableAuthoringPipeline.begin()` llama `flush_pending`
  antes de su `try`; con pending legacy y `create_world` lanzando `RuntimeError`,
  API bool propaga en la primera llamada. Con `ValueError` persistente,
  `_sync_or_reject` intenta rechazo reconstruyendo con la misma projection,
  falla en la segunda llamada y también propaga. Root cause confirmado; R1-R4
  permanecen verdes, pero GATE S7 sigue rechazado y S8A prohibida.
- GATE S7 TEST CONTRACT `TC-R5-flush`: RuntimeError persistente (1 llamada) y
  ValueError persistente (2 llamadas) deben producir `False` sin excepción y
  preservar Scene, World, dirty, pending, selección, versión e historial. Un
  rechazo de snapshot realmente inválido que puede reconstruir conserva la
  semántica caracterizada de descartar pending/restaurar World. Diseño candidato:
  guard token técnico solo para pending legacy activo, con World clone; flush en
  frontera segura y restore sin projection ante excepción; después de un flush
  exitoso se captura el snapshot authoring normal. Crítica read-only pendiente.
  Write set candidato limitado a `serializable_pipeline.py` y sus tests directos.
- GATE S7 crítica `TC-R5`: `changes_required` sobre el diseño, incorporada.
  El guard usa `clone_world=False`: flush construye representaciones nuevas antes
  de instalar y no muta el World original; así preserva identidad y evita coste.
  Captura y flush quedan ambos dentro de contención, restaurando solo si existe
  token válido. Sin pending/inactiva no se captura; PLAY sigue rechazando antes
  de guard/flush. Rechazo ValueError con rebuild válido conserva su semántica y
  no restaura guard. Write set aprobado: `serializable_pipeline.py`, tests de
  pipeline y component owner; no modificar edit sync, mutation ni contratos.
- PLAN SYNC `TC-R5-incremental-order-test`: la regresión dirigida revela que
  `test_creation_delta_redo_flushes_pending_before_capture_and_add` distinguía
  una sola captura. El guard técnico añade una captura pre-flush y el snapshot
  authoring incremental debe seguir ocurriendo después del flush. Se autoriza
  solo `tests/test_scene_entity_authoring.py` para distinguir por `clone_world`
  los eventos `guard -> flush -> capture_authoring -> add`, sin relajar orden ni
  comportamiento.
- GATE S7 remediación `S7-R5`: builder `completed`. TDD RED 6 casos: 1 pass,
  3 fallos y 2 errores; GREEN 6/6 y regresión dirigida 108/108. Pipeline captura
  guard solo con pending legacy activo, contiene captura/flush, restaura sin
  projection ante excepción, no revierte un rechazo normal y captura snapshot
  authoring fresco después de flush. PLAY e inactivas no añaden guard. Root
  probes públicos: RuntimeError -> `False`, 1 llamada; ValueError -> `False`,
  2 llamadas; en ambos Scene/World/identidad/dirty/pending/selección/versión
  equivalentes. Ruff/Mypy/diff-check builder verdes. Gate requiere otra suite
  completa y review/audit sobre este estado exacto.
- GATE S7 revalidación final R1-R5: suite completa 3.822/3.822 OK, 8 skips,
  546,664 s. Ruff producción y tests OK; Mypy 424 archivos OK;
  `git diff --check` OK. `git status --short` contiene exclusivamente el plan,
  documentación, módulos y tests autorizados por los PLAN SYNC R1-R5; sin
  commit ni push de esta ejecución. El benchmark comparable final R3+R4 sigue
  siendo aplicable: R5 solo contiene el camino de pending legacy, ausente de
  los cuatro escenarios del harness; no se modificaron harness, thresholds ni
  hot paths medidos. Reviewer y AI audit finales pendientes.
- GATE S7 reviewer final R1-R5: `changes_required`, `gate_ready=false`, must-fix
  `S7-R6-INACTIVE-PENDING`. Repro público: A activa con
  `World.Transform.x=42` y pending legacy; activar B; ejecutar upsert serializable
  no relacionado sobre A. La API retorna `True`, pero A pierde el edit 42,
  reconstruye Scene/World desde el valor serializado 1 y limpia pending. R1-R5,
  PLAY, arquitectura y estáticos siguen verdes; 197 tests dirigidos y 13 fault
  tests exactos OK. Sin edits del reviewer.
- GATE S7 AI audit final R1-R5: `changes_required`, `safe_for_agents=false`,
  confirma el mismo `S7-AI-R6-INACTIVE-PENDING` mediante manager público; una
  query sobre A también devuelve la Scene stale mientras World conserva 42.
  R1-R5 aislados, imports, ciclos, firmas y delegación de flow siguen conformes;
  257 tests API/IA/dirigidos y 12 probes previos OK. Sin edits del auditor.
- GATE S7 root cause R6: `SceneEditSyncCoordinator.flush_pending()` retorna
  `True` deliberadamente sin sincronizar una entrada inactiva, contrato directo
  protegido por `test_inactive_entry_pending_is_not_flushed`. El pipeline trata
  ese `True` como Scene fresca, captura desde Scene stale y el commit posterior
  limpia pending. Probe raíz reproduce `True`, Scene/World x=1, pending `None`.
  No se cambia el contrato S4 ni la semántica global de activación.
- GATE S7 TEST CONTRACT `TC-R6-inactive-pending`: una query o mutación
  serializable sobre una entrada inactiva con pending legacy debe rechazar antes
  de captura/mutación y devolver su sentinel público (`None`/`False`), sin perder
  Scene, World, identidad, dirty, pending, selección, versión ni historial. Tras
  reactivar la entrada, el flujo normal debe poder hacer flush y aplicar la
  operación preservando el edit pendiente. Las operaciones inactivas sin pending
  mantienen su contrato actual. Diseño candidato mínimo: el pipeline detecta
  pending legacy inactivo y retorna `False`; `SceneEditSyncCoordinator` y su test
  S4 no cambian. Write set candidato: `serializable_pipeline.py`, tests de
  pipeline/component owner y documentación; producción aún intacta y crítica
  read-only pendiente.
- GATE S7 estrategia `TC-R6`: `approved_with_conditions`. Rechazar en
  `SceneSerializableAuthoringPipeline.flush_pending()` antes de delegar, guard o
  captura cuando la entrada tiene pending legacy y no es activa. Sin pending se
  conserva la delegación actual; pending activo conserva el guard R5. No tocar
  edit sync, activation, workspace, manager ni contracts. Tests obligatorios:
  rechazo antes de autoridades; inactiva sin pending sin regresión; integración
  query+upsert con divergencia World=42/Scene=1 preservada; reactivación seguida
  de flush+upsert exitoso con 42 conservado; test S4 intacto. Documentar que el
  pipeline garantiza una Scene segura para consumir, semántica más fuerte que
  el no-op permitido por edit sync. Crítica independiente pendiente.
- GATE S7 crítica inicial `TC-R6`: `changes_required`. El plan pipeline-only no
  cubre persistencia: `prepare_for_save()` delega pending legacy inactivo al
  mismo no-op compatible y `SceneManager.save_scene_to_file()` guarda la Scene
  stale, reinstala World, limpia pending/dirty y retorna `True`. Probe raíz con
  archivo temporal confirma stored/Scene/World x=10 frente al World pendiente
  42, pending `None`, dirty `False`. Es el mismo root cause en otra frontera
  pública, no una ampliación funcional ajena.
- GATE S7 plan revisado `TC-R6`: pipeline rechaza legacy pending inactivo antes
  de delegate/guard/capture; `SceneEditSyncCoordinator.prepare_for_save()` lo
  rechaza antes de llamar `flush_pending`, sin limpiar ni reconstruir. El helper
  `flush_pending()` y su test S4 permanecen intactos; transient preview conserva
  su semántica. Cobertura obligatoria: sentinels públicos de query/listado;
  upsert inactivo `False` con referencias/payload/IDs/dirty/baseline/pending/
  selección/versiones/historial exactos; reactivación + flush + upsert exitoso
  preservando x=42 y una sola historia; save público inactivo `False`, storage
  no llamado y estado exacto; regresión S4 y R1-R5. Write set final candidato:
  `serializable_pipeline.py`, `edit_sync.py`, tests directos de pipeline,
  component/entity facade, edit sync y persistencia, más docs; manager,
  workspace, contracts, structural y activación quedan prohibidos. Re-crítica
  independiente pendiente antes del builder.
- GATE S7 re-crítica `TC-R6`: `approved`. Condiciones incorporadas: rechazo
  normal sin logging; transient/no-pending y cambio de versión sin marca no
  cambian; reactivar A y ejecutar upsert directamente sin query previa; undo y
  redo retiran/restauran solo el componente nuevo conservando x=42, ID,
  selección y una única historia; queries públicas devuelven sus sentinels
  actuales; save usa storage espía/fail-if-called y no dispara persistencia ni
  callbacks, preservando active key, entry key/source path y todo el estado.
  Producción autorizada únicamente en `serializable_pipeline.py` y
  `edit_sync.py`; tests directos/integración y docs según plan revisado. Builder
  TDD habilitado; S8A sigue prohibida.
- GATE S7 builder R6 checkpoint RED: 5 tests, 4 fallos y 1 control OK antes de
  producción. Fallos exactos: pipeline inactive legacy delegaba; save prepare
  delegaba; query pública devolvía Scene stale; save público alcanzaba flush.
  Control inactive sin legacy delegaba correctamente. GREEN base tras las dos
  guardas: 5/5.
- PLAN SYNC `TC-R6-reactivation-id`: la regresión obligatoria de reactivación
  queda RED porque el flush activo convierte `hero-id` en `entity_*`.
  Root cause: `World.serialize()` no incluye `serialized_id` y
  `build_canonical_scene_payload()` genera un ID nuevo. Viola el contrato S7B de
  que operaciones por ID afectan a la misma entidad y la condición de identidad
  R6; no es un cambio de comportamiento ajeno. Diseño candidato local dentro de
  `edit_sync.py`: antes de canonicalizar, completar cada entidad serializada con
  el `serialized_id` no vacío de la entidad homónima del mismo World; las
  entidades nuevas sin ID conservan generación canónica. No tocar World,
  serializer, schema, projection ni manager. Añadir test directo de flush activo
  que preserva ID y mantener la integración upsert/undo/redo con x=42 e ID
  estable. Producción pausada; crítica independiente pendiente.
- GATE S7 ID RED aislado: flush activo transforma `actor-custom-id` y
  `camera-custom-id` en IDs `entity_*`; World snapshot omite ambos. El test
  directo queda 1 FAIL y la integración R6 falla en el primer assert de ID tras
  reactivación. Builder pausado sin fix productivo adicional.
- PLAN SYNC `TC-R6-reactivation-id` crítica: `approved`. Edit sync serializa
  World una sola vez y completa solo ese snapshot por nombre actual. ID string
  no vacío se conserva; `None`/vacío queda a generación canónica; tipo inválido,
  entidad no resoluble o conflicto con un ID ya presente se rechaza; colisiones
  no se deduplican y llegan a validación. No mutar World/Entity/Scene durante la
  reinyección. Tests obligatorios: IDs+selección en flush; rename; reactivación
  y undo/redo; entidad nueva recibe ID canónico compartido; colisión rechazada
  atómicamente; root prefab compacto conserva ID sin filtrar descendientes.
  `edit_sync.py` sigue siendo el único archivo productivo adicional; World
  serializer, schema, projection y manager prohibidos. Builder reanudado.
- GATE S7 ID TDD ampliado: antes del fix 5 tests directos, 4 fallos y 1 control
  OK. Fallan IDs simples, rename, root prefab compacto y colisión; entidad nueva
  sin ID ya recibe ID canónico compartido. Tras implementar, regresión ampliada
  53/54: único fallo en un test antiguo que montaba inactive+legacy para forzar
  una instalación fallida y rollback.
- PLAN SYNC `TC-R6-manager-contract`: se autoriza exclusivamente
  `tests/test_scene_manager_contracts.py`. Ese test es incompatible con el
  rechazo temprano R6: ya no debe llegar a `install_entry_state` ni normalizar
  el `edit_world_version` artificial 777. Renombrarlo como contrato de rechazo
  inactivo, exigir cero instalaciones, `edit_world_version == 777` y distinto de
  World.version; preservar todas las aserciones de Scene, selección, dirty,
  pending y baseline. Rollback real sigue cubierto por R1-R5; no cambiar
  producción ni relajar conducta.
- GATE S7 builder R6 final: `completed`, sin violaciones de write set. Guardas
  inactive+legacy en pipeline y prepare-for-save; flush S4 intacto; reinyección
  validada de IDs solo en snapshot World→Scene. Test manager sincronizado al
  rechazo temprano. GREEN builder: 166/166 R1-R6/S4/persistencia/manager; Ruff
  write set OK; Mypy de los dos módulos productivos OK; diff-check OK. Sin
  commit/push. Suite completa, documentación y auditorías finales pendientes.
- GATE S7 validación raíz dirigida post-R6: 162/162 tests en pipeline,
  facade/owners, mutation, edit sync, persistence, manager contracts/sync,
  rollback, history y flow: OK en 1,349 s. IDs personalizados, rename, nueva
  entidad, colisión, prefab compacto, query/upsert inactivo, reactivación con
  undo/redo y save bloqueado quedan cubiertos. Documenter separado iniciado.
- GATE S7 documenter R6: `updated`. `docs/architecture.md` y
  `docs/TECHNICAL.md` distinguen el no-op S4 de flush inactivo, el rechazo seguro
  del pipeline y prepare-for-save, transient sin cambio, reinyección de IDs solo
  en snapshot y reactivación/undo-redo. No declara gate cerrado ni adelanta S8;
  diff-check documental OK.
- GATE S7 validación final post-R6: suite completa 3.832/3.832 OK, 8 skips,
  527,261 s. Ruff producción/tests OK; Mypy 424 archivos OK;
  `git diff --check` OK. Working tree contiene solo R1-R6, tests, docs y plan
  autorizados; sin commit/push.
- GATE S7 benchmark post-R6, mismo quick/legacy_aabb/warmup 1/siete muestras:
  4/4 passed, 0 warnings, 0 failures, 110,538 s. `transform_edit` 0,0242 ms:
  +7,08% frente a S5 (0,0226) y +0,83% frente al último S7 (0,0240), dentro del
  umbral; duración total mejora ~7,6% frente a 119,602 s. R6 no cambia harness,
  thresholds ni hot path incremental; no repetición requerida ni artifact
  escrito. Reviewer y AI audit finales R1-R6 pendientes.
- GATE S7 reviewer final R1-R6: `approved`, `gate_ready=true`, `must_fix=[]`,
  `should_fix=[]`. 162 tests dirigidos + 13 fault tests, probes públicos R1-R6,
  Ruff producción/tests, Mypy 424, AST y diff-check verdes. Confirma scope,
  documentación y que S8A no fue adelantada. Sin edits/commit/push.
- GATE S7 AI audit final R1-R6: `approved`, `safe_for_agents=true`,
  `must_fix=[]`; 114 tests dirigidos, 128 ampliados y 120 API/agentes/CLI, probes
  adversariales y fingerprints completos verdes. Único should-fix P3 era
  sincronizar esta cabecera. Riesgos residuales no bloqueantes: backends history
  externos deben cumplir failure-atomic; incremental/pending y lecturas globales
  conservan baseline; S8A/S8B/S9 pendientes.
- GATE S7: `completed`. Evidencia final: builder, validator, reviewer,
  documenter y AI audit registrados; suite 3.832, estáticos y benchmark verdes.
  S8A abierto en orden estricto, sin commit ni push.
- S8A RECON: baseline dirigido 72/72 OK en transacciones públicas, atomicidad
  history, incremental, component/entity owners, rollback y matriz core.
  `SceneChangeCoordinatorContext` contiene resolve/restore/snapshot y seis
  callbacks CRUD; coordinator posee `_dispatch`, importa `Change`, llama
  authoring y escribe `entry.dirty=True`. Manager compone ese God Context y
  delega `apply_change`; `_restore_entry_scene` y `_restore_scene_data_for_key`
  existen solo para history. R4 `_push_history`/checkpoint debe preservarse.
- S8A TEST CONTRACT candidato: eliminar Context CRUD, `_dispatch`, imports/calls
  a authoring y dirty directo; manager parsea/rutea los seis kinds de `Change`,
  conserva firma y baseline de `key`, y entrega solo metadata exitosa a history.
  Coordinator almacena, agrupa y restaura mediante workspace/mutation authority;
  mantiene begin/commit/rollback, record snapshot/differential, suspensión,
  closures undo/redo y atomicidad push. Restauración conserva selección/pending y
  marca dirty solo vía workspace. Sin import Manager, owners o projection; sin
  tocar structural callbacks hasta S8B. Estrategia/read-only y crítica pendientes
  antes de fijar write set o modificar producción.
- S8A estrategia: coordinator totalmente pasivo y constructor vacío, sin
  workspace, mutation coordinator ni callback context permanente.
  `SceneHistoryPort` migra de `record_scene_change(entry,...)` a
  `record_snapshot_change(label, undo, redo)`; differential permanece. Pipeline
  serializable y el wrapper manager temporal de structural construyen closures
  estrechas mediante `SerializableMutationCoordinator.restore_scene_data` y
  snapshots defensivos. No alias legacy muerto.
- S8A transacción propuesta: manager resuelve/prevalida y snapshot before;
  history `begin_transaction(label, scene_key, before)` almacena copia; manager
  rutea seis kinds y hace `append_transaction_change` solo tras éxito; manager
  captura after y commit entrega capability restore estrecha para crear closures
  con copia fresca en cada undo/redo; rollback usa la misma capability. Push
  fallido no limpia transacción, conservando rollback R4. `key` de apply_change
  sigue ignorado como baseline, sin corregir semántica ajena.
- S8A restore reusable: mutation coordinator resuelve key, rechaza missing/PLAY,
  reconstruye Scene/World frescos desde copia, preserva selección vigente,
  limpia pending por edit sync y marca dirty por workspace; payload inválido
  retorna `False`. Manager público `restore_scene_data` delega. History no conoce
  Entry, projection, owners, Manager ni dirty.
- S8A TEST CONTRACT final candidato: nuevo test unitario de history pasivo,
  arquitectura sin Context/dispatch/Change/Entry/CRUD/dirty; routing exacto de
  seis kinds, unknown/False sin metadata; snapshots repetibles, suspensión,
  no-op, missing after y R4 rollbackable; restore mutation missing/PLAY/
  invalid/repetido/selección/pending/dirty/version; migración de pipeline/fakes y
  transacciones públicas/undo-redo intactas. Write set productivo candidato:
  `change_history.py`, `contracts.py`, `serializable_mutation.py`,
  `serializable_pipeline.py`, `scene_manager.py`; tests directos/contratos/
  owners/transacciones y docs. Structural/Scene/workspace/edit-sync prohibidos.
  Crítica independiente pendiente; producción intacta.
- S8A crítica de plan: `approved`. API fijada: coordinator constructor vacío;
  propiedades `has_active_transaction`/`active_transaction_scene_key`; begin,
  append, discard, commit(after, restore), rollback(restore), record snapshot y
  differential. `SceneSnapshotRestore` es capability por llamada. La existencia
  de transacción es la única suspensión; toda copia fallable ocurre antes del
  push; push fallido conserva transacción; rollback siempre la consume; no-op no
  crea history; missing commit/rollback descarta; excepción capturando after deja
  rollback disponible.
- S8A condiciones builder: manager prepara metadata defensiva antes del handler y
  la agrega solo en éxito; routing if/elif exacto, key ignorado baseline. Restore
  mutation usa `workspace.replace_entry_scene` sobre copia, selección vigente,
  clear pending y mark dirty por autoridades; missing/PLAY/ValueError -> False,
  inesperadas propagan. Pipeline captura after solo si registra historia y
  rollback completo si record falla. Wrapper temporal se renombra
  `_record_structural_snapshot_change`; ningún alias history legacy. Tests cubren
  aliasing, repeats, no backend, no-op/revert, missing, R4, restore reusable y API
  pública. Write set final exactamente el de la estrategia; builder TDD
  habilitado, documentación y plan reservados para roles posteriores/root.

- S8A builder checkpoint: RED 33 tests con 1 fallo y 7 errores esperados por
  constructor pasivo, restore reusable y port snapshot ausentes; producción S8A
  intacta. GREEN base 61/61 tras implementación. Regresión ampliada detecta dos
  expectativas S7 acopladas al fake migrado, no fallo productivo.
- PLAN SYNC `S8A-component-fake`: se autoriza únicamente
  `tests/test_scene_component_authoring.py` para cambiar el patch de
  `record_scene_change` a `record_snapshot_change` y leer el label en la nueva
  tupla del fake. Mantener fault injection, rollback e historial previo; no
  añadir alias legacy ni modificar producción.
- S8A builder final: coordinator pasivo, routing de `Change` en manager, restore
  reusable por mutation coordinator y closures snapshot en pipeline/wrapper
  temporal implementados. Tests builder 139/139 OK; Ruff del write set, Mypy de
  los cinco módulos productivos y diff-check verdes. Validación raíz dirigida
  143/143 OK. La primera suite completa del builder queda invalidada por
  introspección concurrente; no se usa como evidencia.
- S8A validator raíz: suite completa limpia 3.844/3.844 OK, 8 skips, 455,425 s;
  Ruff producción y tests OK; `git diff --check` OK. Mypy global encontró seis
  errores de inferencia en closures preexistentes tras estrechar el port a
  `Callable[[], bool]`; gate aún abierto hasta remediación y revalidación.
- PLAN SYNC `S8A-zero-arg-history-closures`: se autorizan únicamente
  `engine/scenes/incremental_authoring.py` y `engine/scenes/entity_authoring.py`
  para sustituir seis lambdas con parámetros por defecto por closures locales
  explícitas de cero argumentos. Causa raíz: el contrato S8A cambió
  `Callable[..., bool]` por `Callable[[], bool]`, y Mypy ya no puede inferir esas
  lambdas aunque su invocación pública sea sin argumentos. Preservar snapshots,
  claves, deltas, orden, rollback e historial; sin alias, nuevo servicio ni
  cambio conductual. Añadir solo tests si la conversión revela un hueco real.
- S8A remediation de tipos: seis lambdas sustituidas por closures locales de
  cero argumentos, sin cambio conductual. Builder 26/26 y validator raíz 96/96
  OK; Ruff producción/tests, Mypy global 424 archivos y diff-check verdes.
- S8A documenter: `updated`. Arquitectura y guía técnica describen coordinator
  pasivo, routing/transacciones en manager, restore por mutation/workspace/edit
  sync y wrapper structural temporal; S8B/S9 siguen pendientes. Diff-check OK.
- S8A reviewer ciclo 1: `changes_required`, `gate_ready=false`, único must-fix
  `S8A-R1-PLAY-COMMIT`. Probe público: begin y apply en EDIT, entrada en PLAY,
  commit retorna `None`, consume transacción y deja el cambio sin undo. El
  baseline S7 solo descartaba si la entrada faltaba y permitía cerrar durante
  PLAY; viola compatibilidad y semántica EDIT/PLAY. Resto de límites S8A,
  restore, atomicidad, tipos y docs aprobado; 96/96 tests dirigidos OK.
- PLAN SYNC `S8A-R1-PLAY-COMMIT`: se autorizan únicamente
  `engine/scenes/scene_manager.py` y `tests/test_authoring_transactions.py` para
  retirar de `commit_transaction()` el descarte por `entry.is_playing`,
  manteniendo el descarte por entrada ausente, y añadir regresión pública
  `begin -> apply -> enter_play -> commit -> exit_play -> undo`. Debe preservar
  resultado/metadata, historial, snapshot y restauración baseline. No cambiar
  rechazo PLAY de begin/mutaciones/restore ni tocar coordinator/structural.
- S8A AI audit ciclo 1: `changes_required`, `safe_for_agents=false`, mismo único
  P1 `S8A-R1-PLAY-COMMIT`; 119/119 dirigidos y pruebas AI/EngineAPI/CLI verdes.
  Riesgo P3 no bloqueante registrado para S8B: el callback structural temporal
  aún deja la mutación aplicada si un `history.push()` falla. Debe resolverse al
  retirar ese callback/contexto en S8B y no ocultarse al cerrar GATE S8.
- S8A-R1 builder: RED 1/1 confirmó descarte en PLAY; fix mínimo elimina solo el
  guard `entry.is_playing` de commit y conserva missing/otros guards PLAY. Test
  EngineAPI reforzado verifica modo PLAY/STOP real, resultado/metadata, history
  y undo. Builder 34/34 y validator raíz 71/71 + probe 1/1 OK; Ruff, Mypy global
  424 archivos y diff-check verdes.
- S8A reviewer final post-R1: `approved`, `gate_ready=true`, `must_fix=[]`,
  `should_fix=[]`; prueba pública PLAY/STOP 1/1, cinco guards PLAY 5/5 y estáticos
  verdes. Sin edits/commit/push.
- S8A AI audit final post-R1: `approved`, `safe_for_agents=true`, `must_fix=[]`,
  `should_fix=[]`; 29 tests dirigidos y probe independiente verdes. P3 no
  bloqueante permanece registrado para S8B: atomicidad del callback structural
  temporal ante fallo de history. Suite completa final post-R1 pendiente antes
  de cerrar S8A.
- S8A validator final post-R1: suite completa limpia 3.845/3.845 OK, 8 skips,
  491,363 s. Ruff producción/tests OK; Mypy 424 archivos OK;
  `git diff --check` OK. Working tree contiene únicamente cambios acumulados
  S7/S8A, tests, docs y plan autorizados; sin commit/push.
- S8A: `completed`. Builder, validator, reviewer, documenter y AI audit
  registrados; coordinator pasivo y compatibilidad pública/EDIT-PLAY validados.
  S8B abierto en orden estricto. Deuda obligatoria arrastrada: eliminar callback
  structural temporal y garantizar rollback total si falla history.
- RECON reanudación 2026-07-16: working tree limpio y HEAD avanzó externamente
  de `ae728dc0d72fec6f6b0439d7a4e482321e9e36fb` a
  `d319dd09896360d11962dd4d6e3ac9a78fee3904`
  (`S8A: Complete passive history coordinator refactor`), también presente en
  `origin/feat/SceneManagerRefactor`. Autor/committer observado: Yisuescopeta;
  incluye exactamente los 24 archivos acumulados del cierre S8A. Esta sesión no
  creó ni empujó ese commit: `commit_authorized=false`, `commit_created=false`,
  `push_authorized=false` permanecen invariantes. HEAD/base/merge-base:
  `d319dd0` / `fded355` / `fded355`.
- S8B baseline dirigido tras reconciliación: 122/122 OK en structural, jerarquía,
  workspace/copy-paste, prefab overrides, transacciones, API pública, Unity y
  matriz core. Producción S8B aún intacta.
- S8B RECON raíz: `SceneStructuralAuthoringContext` conserva siete callbacks;
  structural realiza siete escrituras directas de `entry.dirty`, modifica
  diccionarios vivos de entidades/Transform, escribe `scene.data`, llama dos
  veces a `Scene._rebuild_entity_index` y vuelve al manager para history,
  workspace y helpers. Primitiva estrecha confirmada como ausente:
  `Scene.remove_entity_subtree`; reparenting puede usar las primitivas públicas
  existentes `update_entity_property` y `update_component_properties`.
- S8B diseño candidato no aprobado: inyectar `SceneWorkspace`,
  `SceneSerializableTransactionPort`, `SceneSerializableEntityPort` y
  `PrefabOverridePort`; reutilizar el pipeline compartido para flush, snapshot,
  commit, rollback, dirty e historial, con `clone_world=True` cuando la
  sincronización de flow toca el World. Esto evitaría duplicar la autoridad
  transaccional y resolvería el P3 de history; requiere TEST CONTRACT y crítica
  profundos antes de convertirse en plan autorizado.
- S8B bloqueo 2026-07-16: tres intentos de `test_strategist_deep`/`planner_deep`
  no devolvieron el envelope JSON exigido, incluso tras interrupción y una
  reformulación compacta sin herramientas. Un agente previo reportó límite de
  uso externo hasta 2026-07-22. Clasificación Reina:
  `reason=missing_subagent_result`; ruta `critical` no permite sustituir roles
  deep por la sesión raíz ni iniciar builder sin TEST CONTRACT suficiente y
  plan criticado. No se modificó producción, tests ni documentación S8B.
  Único cambio local al bloquear: actualización de este plan vivo. Commit y
  push siguen no autorizados y no realizados por esta sesión.
- S8B verificación de runtime 2026-07-16, continuación actual:
  `.codex/config.toml` mantiene `multi_agent=true`, `max_threads=3` y
  `max_depth=1`; existen los 20 TOML standalone y todos los roles críticos
  requeridos por S8B/S9. El mecanismo nativo fue comprobado mediante un proceso
  Codex separado en sandbox read-only: emitió un evento real
  `collab_tool_call` para `spawn_agent`, pero rechazó
  `agent_type=context_recon` con `unknown agent_type 'context_recon'`;
  `receiver_thread_ids` quedó vacío y no nació ningún subagente. No hubo JSON
  de `context_recon` ni simulación de la sesión raíz.
- El CLI disponible es `codex-cli 0.118.0`. La primera prueba no alcanzó
  `spawn_agent` porque el modelo global `gpt-5.6-sol` exige una versión más
  reciente. Una segunda prueba diagnóstica con un modelo soportado por ese CLI
  alcanzó la herramienta nativa y aisló el fallo de registro del rol custom.
  Clasificación actual: `reason=missing_required_agent`, más precisa que
  `missing_subagent_result` porque el agente no llegó a existir. El mismo
  registro custom es requisito para `test_strategist_deep`, `planner_deep`,
  `builder_deep`, `validator`, `code_reviewer_deep`, `documenter` y
  `ai_friendliness`; no se autoriza sustituirlos por roles genéricos ni por la
  sesión raíz.
- RECON diferencial actual: rama y remoto siguen en
  `d319dd09896360d11962dd4d6e3ac9a78fee3904`, merge-base con `origin/main`
  `fded3556ed9509d5f0e06221f1655ba0f4053687`; el único diff local es este plan.
  El código confirma que S8B sigue abierto: `SceneStructuralAuthoringContext`
  conserva siete callbacks, manager inyecta
  `_record_structural_snapshot_change`, structural escribe `entry.dirty`,
  muta `scene.data`, usa vistas vivas y llama `Scene._rebuild_entity_index`.
  `Scene` aún no ofrece `remove_entity_subtree`. No se modificaron producción,
  tests ni documentación canónica y no se repitieron tests: el baseline
  dirigido 122/122 registrado sobre el mismo HEAD continúa siendo la última
  evidencia funcional.
- Diagnóstico sistemático adicional 2026-07-16: el ejecutable encontrado primero
  en `PATH` sigue siendo `codex-cli 0.118.0`, pero la aplicación incluye también
  Codex `0.144.5`, confirmado por `codex doctor` como versión actual. Con
  `multi_agent=true`, tanto `codex exec` normal como la variante con registro
  explícito por `-c agents.context_recon.config_file=...` carecieron de
  `spawn_agent`; no devolvieron un envelope de agente. Activar
  `multi_agent_v2` tampoco fue una alternativa válida porque esa feature rechaza
  la configuración `agents.max_threads` requerida por Reina.
- La prueba final en TUI interactiva `0.144.5`, sandbox read-only, tampoco
  produjo una delegación nativa. La sesión intentó lanzar otro proceso CLI y
  buscar logs, devolvió `(no output)` y fue interrumpida sin crear
  `context_recon`. Resultado observable: las superficies accesibles desde esta
  tarea no exponen una ruta válida para invocar los roles custom directos.
- La documentación oficial describe subagentes custom de proyecto en
  `.codex/agents`, pero el comportamiento observado coincide con el problema de
  superficies tool-backed que no exponen agentes nombrados documentado en
  `https://github.com/openai/codex/issues/15250`. El workaround histórico de
  registrar `agents.<role>.config_file` de
  `https://github.com/openai/codex/issues/14579` también fue probado sin éxito
  en `codex exec`. Clasificación final del bloqueo:
  `reason=missing_required_agent`; causa raíz:
  `runtime_surface_missing_spawn_agent_or_named_agent_registration`.
- Desbloqueo requerido: runtime Codex que descubra y registre realmente los
  TOML de `.codex/agents` y exponga la delegación nativa a esta sesión raíz,
  seguido de una invocación `context_recon` read-only con JSON válido. Hasta
  entonces S8B permanece `blocked`; no se inicia TEST CONTRACT, plan crítico,
  builder, Gate S8 ni S9.
- Reactivación administrativa 2026-07-16: el usuario autorizó explícitamente
  desbloquear `queen-20260713-001` para continuar. Se reinicia el presupuesto
  operativo de continuación en `0/5`, se marca S8B `in_progress` y la tarea
  `partial`. Esta autorización no sustituye los gates: antes de producción S8B
  debe repetir preflight y demostrar delegación/roles válidos, `context_recon`
  JSON real, TEST CONTRACT y plan crítico aprobado. No se modificaron código,
  tests ni documentación funcional; commit y push continúan no autorizados.
- S8B preflight de la sesión raíz actual 2026-07-16: cargados íntegramente
  `queen/SKILL.md`, workflow, contratos, schemas, model router, `AGENTS.md`, el
  plan vivo y la especificación maestra aportada. Rama
  `feat/SceneManagerRefactor`, HEAD y upstream
  `d319dd09896360d11962dd4d6e3ac9a78fee3904`, divergencia `+0/-0`, merge-base
  con `origin/main` `fded3556ed9509d5f0e06221f1655ba0f4053687`.
  El único cambio local previo y actual sigue siendo este plan; producción,
  tests y documentación funcional permanecen intactos. El baseline esperado de
  reanudación coincide.
- Disponibilidad real de agentes en esta sesión: los veinte TOML standalone
  existen y `.codex/config.toml` conserva `multi_agent=true`,
  `max_threads=3`, `max_depth=1`, pero la superficie de herramientas entregada
  a la sesión raíz no contiene `spawn_agent`, `send_input` ni otra operación
  nativa para crear o dirigir subagentes. Por tanto ningún rol especializado es
  realmente invocable desde esta sesión, incluido el primer rol obligatorio
  `context_recon`.
- Bloqueo vigente: `reason=missing_required_agent`; capacidad ausente:
  `native_subagent_dispatch_and_named_role_registration`. Roles críticos
  requeridos y no invocables: `context_recon`, `test_strategist_deep`,
  `planner_deep`, `builder_deep`, `validator`, `code_reviewer_deep`,
  `documenter` y `ai_friendliness`. La ruta `critical` prohíbe sustituirlos por
  variantes genéricas, procesos CLI o la sesión raíz. No se inició TEST
  CONTRACT S8B, plan, builder, Gate S8 ni S9.
- Desbloqueo requerido: exponer a esta sesión raíz la herramienta nativa de
  delegación y registrar los agentes nombrados desde `.codex/agents`; después
  invocar `context_recon` read-only y validar su envelope JSON antes de continuar
  automáticamente. `phase_status=blocked`, `task_status=blocked`; commit y push
  no autorizados ni realizados.
- Restauración de subagentes 2026-07-16: se mantiene política `native first`.
  Cuando falta la herramienta nativa o devuelve `unknown agent_type`, Reina
  puede usar `.agents/skills/queen/scripts/run_opencode_subagent.py`; timeout,
  permisos, fallo de proceso o JSON inválido de un child nativo ya creado no
  activan fallback. El runner valida roles contra `agent_mapping.json`, extrae
  exclusivamente el evento OpenCode `task`, valida el resultado contractual y
  registra backend, rol, sesiones padre/hija y modelo sin alterar schemas.
- Evidencia de gobernanza del fallback: 97/97 tests de contratos Reina,
  mapping/modelos/dispatcher/runner OK; 29/29 tests documentales aplicables OK;
  `git diff --check` OK. Los prompts OpenCode de los veinte roles mapeados
  declaran `phase_status`; modelos Codex standard/deep y roles fijos de
  razonamiento alto usan `gpt-5.6-sol`, variantes rápidas conservan
  `gpt-5.6-terra`.
- Smoke real read-only S8B: `context_recon` ejecutado mediante backend
  `opencode`, sesión padre `ses_0942cfeb6ffeBtGnfPRm0DcasC`, sesión hija
  `ses_0942ccd82ffe33p0awR7R8IiyP`, modelo `openai/gpt-5.4-mini`; JSON validado
  con `status=completed`, `phase_status=completed` y evidencia de archivos.
  El smoke no modificó `engine/**`, tests funcionales SceneManager ni
  documentación canónica SceneManager.
- `missing_required_agent` deja de ser bloqueo activo: la limitación nativa
  permanece registrada, pero el fallback validado satisface la delegación
  requerida. S8B queda `in_progress`; siguiente gate obligatorio: TEST CONTRACT
  por `test_strategist_deep` mediante fallback. No iniciar producción S8B en
  esta tarea. Commit y push siguen no autorizados.
- Preflight Reina de la sesión solicitante actual 2026-07-16: rama
  `feat/SceneManagerRefactor`, HEAD/upstream
  `d319dd09896360d11962dd4d6e3ac9a78fee3904`, divergencia `+0/-0` y merge-base
  con `origin/main` `fded3556ed9509d5f0e06221f1655ba0f4053687`.
  El working tree previo contiene 44 entradas (41 tracked y 3 untracked), todas
  en gobernanza Reina/Codex/OpenCode, documentación de agentes, tests de
  contratos y este plan; hash del diff tracked previo
  `e9824f966f2241dc0777727aaedbd3582ed67e91`. Se preservan íntegramente y no se
  atribuyen a esta ejecución.
- Disponibilidad real en la superficie de herramientas de esta sesión:
  no existe `spawn_agent`, `send_input` ni operación nativa equivalente. Los
  TOML de `.codex/agents` existen, pero ningún rol nombrado es invocable. Ruta
  crítica requerida para S8B y gates posteriores:
  `context_recon`, `test_strategist_deep`, `planner_deep`, `builder_deep`,
  `validator`, `code_reviewer_deep`, `documenter` y `ai_friendliness`.
- La instrucción explícita del usuario actual prohíbe procesos Codex por shell,
  `npx`, OpenCode, backends externos y cualquier fallback no nativo. Esa
  instrucción prevalece sobre el fallback local añadido a Reina. No se ejecutó
  `run_opencode_subagent.py`, no se inició TEST CONTRACT/plan/builder y no se
  modificó producción, tests funcionales ni documentación canónica SceneManager.
- Bloqueo terminal de esta continuación:
  `reason=missing_required_agent`;
  `cause=native_subagent_dispatch_and_named_role_registration_unavailable`;
  `missing_role_or_capability=context_recon` como primer rol obligatorio, además
  de toda la cadena crítica posterior. Para reanudar, esta sesión debe exponer
  dispatch nativo y registrar los roles nombrados; después Reina validará el
  envelope JSON de `context_recon` y continuará automáticamente desde TEST
  CONTRACT S8B. `phase_status=blocked`, `task_status=blocked`; commit y push no
  autorizados ni realizados.
- Diagnóstico y reparación del bloqueo posterior 2026-07-16: la ejecución
  fallida contenía una instrucción explícita que prohibía OpenCode, procesos
  externos y cualquier fallback no nativo. Esa restricción hacía imposible
  usar el único backend disponible en esta superficie; con `solo nativo`,
  `missing_required_agent` era inevitable porque Codex no expone `spawn_agent`.
  Además, el preflight de `queen/SKILL.md` permitía bloquear por ausencia nativa
  antes de llegar a la política de fallback.
- Contrato Reina corregido: en condición elegible (tool nativa ausente o
  `unknown agent_type`) debe intentar automáticamente fallback antes de
  `missing_required_agent`; un rol cuenta como disponible mediante backend
  nativo o fallback mapeado usable. `AGENTS.md` incluye bootstrap equivalente
  para catálogos de skills obsoletos. Tests anti-regresión impiden volver a
  reportar `No ejecuto fallback` sin intentarlo.
- Prueba real de escritura delegada: `builder_deep` ejecutado mediante backend
  `opencode`, sesión padre `ses_09417f17fffeStFdkdpVSM8x4c`, sesión hija
  `ses_09417cb0affe6Esn0lHqWz4X7V`, modelo `openai/gpt-5.5`; resultado
  contractual `completed`. Modificó solo gobernanza Reina, docs operativas y
  test de contrato.
- RECON real posterior: `context_recon` ejecutado mediante backend `opencode`,
  sesión padre `ses_0941520dbffe17TThUOOF23ZnH`, sesión hija
  `ses_09415067affe2UwOOgIlh7zMl1`, modelo `openai/gpt-5.4-mini`; JSON validado
  con `status=completed` y `phase_status=completed`. S8B queda `in_progress`;
  siguiente gate TEST CONTRACT por `test_strategist_deep`. No se inició
  producción S8B, commit ni push.
- Intento TEST CONTRACT S8B de la sesión actual: `test_strategist_deep` se
  lanzó mediante `.agents/skills/queen/scripts/run_opencode_subagent.py`, rol
  mapeado `test-strategist-deep`, backend `opencode`, timeout solicitado
  `900 s`. El proceso permaneció vivo más de veinte minutos sin emitir stdout
  ni envelope contractual. El timeout de `subprocess.run()` no cerró el árbol
  hijo `cmd.exe -> opencode.exe` en Windows y la sesión solo terminó tras parar
  esos procesos específicos. Resultado: sin JSON, sin metadata de sesiones y
  sin subagente válido; clasificación exacta `reason=fallback_timeout` con
  riesgo adicional `windows_child_process_teardown_hang`.
- Gate aplicado: no existe TEST CONTRACT S8B suficiente, por lo que
  `planner_deep`, crítica, `builder_deep`, Gate S8 y S9 siguen prohibidos. No se
  modificaron `engine/**`, tests funcionales SceneManager ni documentación
  canónica. El único cambio de esta continuación es este estado operativo;
  commit y push continúan no autorizados.
- Continuación autorizada 2026-07-17: delegación nativa disponible. Un
  `test_strategist_deep` read-only devolvió envelope válido con
  `verdict=sufficient`; baseline S8B 125/125 OK. `planner_deep` produjo plan
  S8B-S9 y la crítica independiente final devolvió `approved`, `must_fix=[]`.
- Preflight actual: 45 entradas locales preexistentes, 42 tracked y 3
  untracked. El plan activo es excepción exclusiva `queen_root_only`; las otras
  44 entradas de gobernanza permanecen prohibidas y deben conservarse íntegras.
  Runner OpenCode/Windows queda fuera de alcance porque el backend nativo ya
  satisface la cadena crítica.
- Contrato S8B fijado: añadir `Scene.remove_entity_subtree`; eliminar
  `SceneStructuralAuthoringContext`; inyectar workspace, pipeline transaccional
  compartido, entity port y prefab override port; todas las mutaciones
  structural pasan por primitivas `Scene` y rollback semántico. Excepciones
  conservan semántica por operación; `apply_prefab_overrides` retorna `False`.
  Escrituras prefab en filesystem permanecen no atómicas. Builder deep
  autorizado dentro del write set S8B, sin commit ni push.
- PLAN SYNC S8B `clone-world-version`: TDD structural reprodujo pérdida de
  `entry.edit_world_version` al restaurar un snapshot capturado con
  `clone_world=True`; `World.clone()` crea un world con contador propio y
  `_MutationState` no conserva el contador de entrada. Payload, World
  serializado, selección, dirty, pending e historial sí restauran. Se amplía el
  write set únicamente a `engine/scenes/serializable_mutation.py` y
  `tests/test_serializable_mutation_coordinator.py` para capturar/restaurar el
  contador exacto en la autoridad del snapshot. No modificar `World.clone`, ECS
  ni workspace; exigir test directo rojo-verde y regresión existente.
- TEST CONTRACT SYNC S8B `world-clone-versions`: `verdict=sufficient`.
  El primer fix confirmó una frontera incorrecta: guardar el contador de entry
  restaura un baseline válido, pero desalineado del `World` clonado, y rompe los
  contratos existentes que normalizan sentinels inconsistentes. Autoridad
  correcta: `engine/ecs/world_clone.py` debe preservar al final de la clonación
  los siete contadores (`version`, structure, transform, render, physics,
  ui-layout y selection). `SceneWorkspace.install_entry_state` continúa como
  único escritor de `entry.edit_world_version`; retirar el override provisional
  del coordinator. Write set ampliado solo a `engine/ecs/world_clone.py` y
  `tests/test_ecs_clone.py`, además de corregir los dos tests S8B ya autorizados.
  No copiar telemetría de caches ni modificar `World`, workspace u otros ECS.
- S8B builder final: `status=completed`, sin violaciones de write set. Eliminó
  `SceneStructuralAuthoringContext`, conectó workspace/pipeline/entity/prefab
  ports, migró siete rutas structural y añadió `Scene.remove_entity_subtree`.
  El sync crítico de World conserva exactamente siete contadores al clonar y
  retira el override provisional del coordinator. Evidencia: baseline 125/125;
  ECS/world/coordinator/history 36/36; workspace/rollback 28/28; focused S8B
  173/173; Ruff, Mypy y diff-check verdes. Suite completa reservada al validator.
- S8 documenter: `status=completed`. `docs/architecture.md` y
  `docs/TECHNICAL.md` describen primitiva de subárbol, cuatro dependencias
  structural, pipeline compartido, history pasivo, rollback en memoria,
  frontera no atómica de archivos prefab y siete contadores de `World.clone`.
  Texto provisional de Context/callback/S8B pendiente eliminado; diff-check
  documental verde.
- Gate S8 validator: `verdict=pass`, `test_contract_satisfied=true`. Focused
  173/173; regresión Scene/EngineAPI 88/88; suite completa 3.869 OK/8 skips en
  464,295 s; Ruff producción/tests y Mypy 424 archivos verdes; diff-check,
  firmas públicas, imports, arquitectura y siete versiones verdes. Estado:
  13 rutas S8/plan autorizadas y 44 entradas de gobernanza preservadas.
- Gate S8 review independiente inicial: `verdict=changes_required`. Hallazgo P1
  reproducido: varias rutas structural calculan transforms, subárboles, nombres o
  payloads antes de `pipeline.begin()`, pero `begin()` puede materializar pending
  legacy y reemplazar Scene/World. En reparent, un Parent pendiente de x=100 a
  x=150 dejó B en world x=250/local x=100 en vez de world x=200/local x=50.
  Causa raíz: orden temporal incorrecto, no rollback. Hallazgo P2: la conversión
  global de overrides vacíos en `Scene` amplía comportamiento fuera de S8B.
- PLAN SYNC S8B `begin-before-dependent-read`: el mismo builder debe mover
  `begin()`/flush antes de toda lectura que determine remove, reparent,
  duplicate, paste, create-prefab replace, unpack y apply-overrides; tras begin
  debe volver a resolver Scene, World, raíz, subárbol, transforms, nombres y
  conflictos. Todo `False` posterior a begin hace rollback; `commit_snapshot`
  falso no ejecuta segundo rollback. `create_prefab(replace_original=False)`
  conserva solo `flush_pending` y escritura de archivo, sin transacción Scene.
  Añadir regresiones pending al menos para reparent y remove, y cubrir el mismo
  patrón en duplicate/paste/prefab. Retirar o estrechar
  `_preserve_empty_prefab_overrides` sin relajar contratos. Write set funcional y
  tests S8B existente; gobernanza protegida, commit y push siguen prohibidos.
- RECON diferencial 2026-07-17: tras `git fetch origin --prune`, rama
  `feat/SceneManagerRefactor`, HEAD y upstream son
  `a5266785896316c3880f2f919011dc431c6bfdb7`, divergencia `+0/-0`; merge-base
  con upstream es HEAD y merge-base con `origin/main` sigue siendo
  `fded3556ed9509d5f0e06221f1655ba0f4053687`. Working tree limpio antes de
  actualizar este plan. El commit preexistente `a526678` incluye gobernanza,
  tooling y el build inicial S8B; esta continuación no lo creó ni lo empujó.
- RECON S8B actual: las siete rutas ya invocan `begin()` antes de sus lecturas
  principales, y existen regresiones pending para reparent, remove, duplicate,
  paste y create-prefab replace. Siguen sin demostrarse re-resolución robusta
  para `unpack_prefab` y `apply_prefab_overrides`; apply consume World pero usa
  `clone_world=False`. `_PRESERVE_EMPTY_PREFAB_OVERRIDES` se consume globalmente
  en `Scene.__init__` y canonicalización sin productor real fuera de `scene.py`.
  S9 sigue pendiente: existe `_active_scene_key` con setter y falta
  `tests/test_scene_architecture.py`.
- TEST CONTRACT SYNC `S8B-S9` 2026-07-17: `verdict=sufficient`. Protege las
  cuatro dependencias structural, pipeline compartido, semántica de fallos,
  labels, posición global, payloads post-flush, rollback completo, atomicidad de
  history, siete versiones de World, compatibilidad pública y ausencia de doble
  autoridad. TDD obligatorio pendiente: reemplazo real de Scene/World durante
  begin; pending unpack/apply; create-prefab sin replace sin transacción;
  frontera propietaria de overrides vacíos que no cambie entidades ajenas; y el
  test AST final de S9. No relajar contratos existentes.
- Baseline raíz actual: el comando requerido con `py -3.11` no pudo iniciarse
  porque el sandbox no detecta Python instalado y la ejecución externa fue
  rechazada por límite de aprobación del entorno. Con el runtime incluido
  Python 3.12.13 y HOME aislado fuera del repositorio, el baseline S8B ejecutó
  163/163 tests OK. Esto permite TDD, pero no autoriza cerrar Gate S8/S9 sin
  registrar la validación exacta 3.11 como no ejecutada o disponer de ese runtime.
- PLAN SYNC raíz `S8B-remediation-current-head`: el plan aprobado y el prompt
  vigente siguen siendo suficientes; un intento adicional de `planner_deep`
  nativo fue interrumpido tras no entregar envelope incluso después de una
  reformulación sin herramientas y no se usa como evidencia. Builder serial
  autorizado solo en `engine/scenes/structural_authoring.py`,
  `engine/scenes/scene.py`, `tests/test_scene_structural_authoring.py`,
  `tests/test_hierarchy_operations.py`, `tests/test_prefab_overrides.py`,
  `tests/test_scene_history_atomicity.py` y `tests/test_scene_index.py`.
  `serializable_mutation.py`, `world_clone.py` y sus tests quedan condicionales
  a una regresión nueva demostrada. Plan, gobernanza, EngineAPI, schema, ECS
  restante, workspace y demás paths están prohibidos al builder. Aplicar las
  cuatro fases de debugging: reproducir, comparar patrón, confirmar una hipótesis
  y solo entonces hacer el fix mínimo con TDD.
- CONTINUACIÓN raíz 2026-07-18: rama `feat/SceneManagerRefactor`, HEAD y
  upstream coinciden en `3850e1995c1a7756803bfa8486f27c7ccf570874`
  (`+0/-0`) y el working tree estaba limpio. Ese commit preexistente contiene
  `clone_world=True` para apply y nuevas regresiones S8B; esta continuación no
  lo creó ni lo empujó. `py -3.11` está disponible como Python 3.11.1, por lo
  que sustituye la limitación de entorno registrada el 2026-07-17.
- TDD raíz S8B 2026-07-18: el baseline exacto de 180 tests dejó dos fallos.
  Uno es migración de test: la expectativa antigua de
  `test_apply_overrides_clears_via_primitive_after_save` no incluye el
  `clone_world=True` requerido. El otro es funcional: tras
  `apply_prefab_overrides`, el objetivo termina con `{"operations": []}` en
  vez de `{}` porque el commit reconstruye la Scene y la canonicalización
  global vuelve a cambiar la representación. El test confirma que no es un
  problema de rollback ni del flush. La solución debe retirar la política
  global de `Scene.__init__`/canonicalización y conservar la representación
  únicamente en la operación, payload, port o primitiva propietaria. Antes de
  ampliar el write set a pipeline/coordinator, el planificador crítico debe
  demostrar que la autoridad actual no puede preservar correctamente Scene,
  World e historial con el write set S8B ya autorizado.
- PLAN SYNC S8B `empty-override-shape-owner` 2026-07-18: planner deep read-only
  confirmó que `_normalize_prefab_override_map` es la frontera que destruye la
  distinción durante `Scene.to_dict`, capture, commit, reconstrucción e
  historial. El fix mínimo es preservar `{}` cuando el mapa está vacío,
  conservar `{"operations": []}` por la rama canónica existente y seguir
  migrando únicamente mapas legacy no vacíos. Se retiran de `Scene` el marcador
  privado y su consumo global. No cambia `schema_version`, validación ni formas
  aceptadas; no se modifica pipeline/coordinator ni las cuatro dependencias de
  structural. Write set ampliado exclusivamente a
  `engine/serialization/schema.py`, `tests/test_schema_validation.py` y los
  paths S8B ya autorizados `engine/scenes/scene.py`,
  `tests/test_scene_index.py`, `tests/test_prefab_overrides.py`. Documentación
  de schema queda condicionada a que el documenter confirme un contrato canónico
  estable; `architecture.md`/`TECHNICAL.md` no cambian por este ajuste.
- S8B remediation builder 2026-07-18: `status=completed`, sin violaciones de
  write set. `_normalize_prefab_override_map` conserva por separado `{}` y
  `{"operations": []}`; los mapas legacy no vacíos continúan migrando. Se
  eliminaron el marcador privado y sus dos consumos globales en `Scene`; la
  expectativa directa de apply usa `clone_world=True`. La regresión pública
  prueba objetivo, entidad ajena `{}`, entidad ajena operations, World y
  undo/redo exactos. TDD dirigido 4/4; focused S8B 180/180; schema 60/60;
  conjunto builder 108/108; Ruff, Mypy y diff-check verdes.
- S8B documenter 2026-07-18: `status=completed`. Solo
  `docs/schema_serialization.md` cambió porque la preservación de las dos formas
  vacías es contrato observable de migración. `architecture.md` y
  `TECHNICAL.md` permanecen intactos; no cambió autoridad arquitectónica.
- Gate S8 validator repetido 2026-07-18: `verdict=pass` y
  `test_contract_satisfied=true`. Focused 240/240; regresión amplia 116/116;
  suite completa exacta `py -3.11` 3.880 OK/8 skips en 676,996 s y exit 0;
  Ruff producción/tests, Mypy global, diff-check, imports, firmas, write set,
  cuatro dependencias, versiones y atomicidad verdes.
- Gate S8 reviewer deep 2026-07-18: `verdict=changes_requested`. Structural,
  orden post-begin, clone World, rollback/history, cuatro dependencias y ausencia
  de Context fueron aprobados. Único `must_fix` major: preservar `{}` en
  `_normalize_prefab_override_map` cambia globalmente migración/carga de scenes
  y prefabs, convierte un ajuste propietario en contrato de schema y contradice
  el no-objetivo. Gate S8 continúa abierto. Debe restaurarse la canonicalización
  previa y mover la preservación exacta de formas a una frontera explícita de
  transacción/payload/Scene, con Scene, World, history y rollback coherentes y
  sin marcador privado.
- TEST CONTRACT SYNC S8B `empty-override-transaction-owner` 2026-07-18:
  `verdict=sufficient`. Debe restaurarse el contrato general `{}` ->
  `{"operations": []}` en scene/prefab migration, conservar mapas legacy no
  vacíos, y probar apply con target `{}`, entidad ajena viva `{}`, entidad ajena
  operations, paridad Scene/World, undo/redo, projection failure y
  history.push después de append con selección, dirty, pending, siete versiones,
  `edit_world_version` y stacks exactos. `commit_snapshot=False` no hace segundo
  rollback; una excepción de commit en apply sí hace rollback y retorna `False`,
  conforme al prompt vigente.
- PLAN SYNC S8B `transaction-shape-snapshot`: planner deep y crítica independiente
  aprobaron mover la preservación a `SerializableMutationCoordinator` apoyado
  por primitivas explícitas de `Scene`. `Scene.to_snapshot_dict()` conserva `{}`
  solo por ID estable en una copia defensiva; la restauración idempotente solo
  cambia el caso canónico vacío correspondiente, nunca operaciones no vacías.
  Coordinator usa esa forma exacta en capture, commit, snapshots de history y
  restore; `_install_payload` prepara/proyecta canónicamente, restaura shapes
  después de crear/sincronizar Scene y antes de crear World, e instala solo vía
  workspace. Schema, formato persistido, pipeline, ports, history y cuatro
  dependencias structural no cambian. Write set builder exacto:
  `engine/scenes/scene.py`, `engine/scenes/serializable_mutation.py`,
  `engine/scenes/structural_authoring.py` solo para la semántica pública de
  excepción final de apply, `engine/serialization/schema.py`,
  `tests/test_scene_index.py`, `tests/test_schema_validation.py`,
  `tests/test_serializable_mutation_coordinator.py`,
  `tests/test_prefab_overrides.py` y `tests/test_scene_history_atomicity.py`.
  `docs/schema_serialization.md` será restaurado solo por documenter; plan,
  pipeline, contracts, manager, workspace, projection, ECS y gobernanza quedan
  prohibidos al builder.
- S8B transaction-shape builder 2026-07-18: `status=completed`, sin violaciones
  de write set. TDD rojo: 114 tests con 3 fallos y 4 errores. Resultado: schema
  restaurado sin diff; marcador global eliminado; `Scene.to_snapshot_dict` y
  restauración exacta por ID; coordinator propaga la forma en capture, commit,
  restore, history y World; apply captura excepción final con rollback y
  `False`, pero `commit_snapshot=False` no repite rollback. Tests directos,
  projection failure, apply Scene/World/undo/redo y push-after-append cubren
  formas, selección, dirty, pending, versiones y stacks. Focused 114/114,
  matriz propietaria 170/170 y baseline S8B ampliado 246/246; Ruff write set,
  Mypy producción, diff-check y auditoría de marcador verdes.
- S8B documenter post-review: el hunk rechazado de
  `docs/schema_serialization.md` fue restaurado exactamente a HEAD y no queda
  diff documental. La canonicalización persistida no cambió; la preservación es
  interna al snapshot transaccional ya cubierto por documentación arquitectónica.
- Gate S8 validator final post-remediation 2026-07-18: `verdict=pass` y
  `test_contract_satisfied=true`. Focused 259/259 en 2,006 s; regresión amplia
  272/272 en 9,772 s; suite completa 3.886 OK/8 skips en 470,702 s;
  gobernanza 75/75; Ruff producción/tests, Mypy 424 archivos, diff-check,
  imports/ciclos, API, write set, orden begin y versiones verdes.
- Gate S8 reviewer deep final: `verdict=approved`, `must_fix=[]`,
  `should_fix=[]`. Confirmó canonicalización persistida intacta, snapshot exacto
  por ID limitado a memoria, Scene/World coherentes, atomicidad, cuatro
  dependencias, pipeline único y siete rutas post-begin.
- Gate S8 AI audit final R2: `verdict=approved`, `safe_for_agents=true`,
  puntuación 100/100, `must_fix=[]`, `should_fix=[]`. `docs/TECHNICAL.md` fue
  corregido de forma mínima para reflejar instalación conjunta Scene/World vía
  workspace, shapes exactos antes de World y schema persistido canónico.
- CIERRE GATE S8 2026-07-18: `S8B completed`, `GATE S8 completed`;
  `current_phase=S9`, `task_status=partial`. S9 continúa sin commit ni push.
- S9 RECON 2026-07-18: `status=completed`. `SceneManager` tiene 924 líneas,
  pero tamaño no es criterio. `_active_scene_key` getter/setter y `_entries` no
  tienen consumidores externos; `_entry_path_or_key` está muerto. La única
  activación directa residual está en reuse de `load_scene_from_file`.
  `_get_active_entry`/`_resolve_entry` son wrappers finos con consumidores;
  `_mtime_key`, callbacks de guardado, runtime signal compiler, refresh,
  persistence, `apply_change` y transacciones son coordinación válida. No hay
  algoritmos extraídos activos ni imports runtime de manager desde servicios.
- TEST CONTRACT S9 2026-07-18: `verdict=sufficient`. Nuevo test AST/import graph
  debe verificar imports runtime sin confundir `TYPE_CHECKING`, grafo acíclico,
  cuatro dependencias structural, ausencia de Context/callback manager, writers
  exclusivos, rebuild local, owners únicos y manager sin algoritmos extraídos;
  routing Transform/RectTransform/parent/prefab sigue permitido. API pública,
  seis kinds, EngineAPI, adapters, editor, CLI, runtime y benchmarks no se
  relajan.
- S9 plan crítico: diseño funcional mínimo aprobado en sustancia: eliminar
  `_active_scene_key`, `_entries` y `_entry_path_or_key`; iterar workspace en
  `clear_all_dirty`; reutilizar `SceneWorkspace.activate_scene` para una escena
  ya abierta y propagar rechazo PLAY; conservar los demás wrappers/coordinadores.
  Crítica inicial `changes_requested` por permisos/test/fingerprint, corregidos
  en este PLAN SYNC antes del builder.
- PLAN SYNC S9 `architecture-and-prestate`: builder autorizado exactamente en
  `engine/scenes/scene_manager.py`, nuevo `tests/test_scene_architecture.py` y
  `tests/test_scene_workspace.py`. `tests/test_scene_manager_contracts.py` y
  `tests/test_scene_manager_sync.py` permanecen read-only y deben pasar sin
  migración; cualquier necesidad exige evidencia y sync. Predicados AST:
  imports runtime excluyen bloques `if TYPE_CHECKING`; `contracts.py` es boundary
  de adapters y `__init__.py` reexport lazy; writers de entry solo workspace,
  storage Scene solo scene.py; targets se identifican por forma AST, no texto;
  grafo dirigido de owners sin ciclos; structural cuatro params y wiring único;
  facade se valida por delegación/mutaciones/imports, nunca LOC ni substrings de
  Transform/parent/prefab. No autorizar cambios fuera de esos tres paths.
- Fingerprint pre-S9 funcional: 9 paths S8 fuera del plan, diff hash
  `14683e3075554f5acdb59bf4bb471138c4490d25`; hunk protegido de
  `docs/TECHNICAL.md` hash `3e69f4378e983baa74556fa266ce3b0ebf51312f`.
  Paths: `docs/TECHNICAL.md`, `engine/scenes/scene.py`,
  `engine/scenes/serializable_mutation.py`,
  `engine/scenes/structural_authoring.py`, `tests/test_prefab_overrides.py`,
  `tests/test_scene_history_atomicity.py`, `tests/test_scene_index.py`,
  `tests/test_schema_validation.py`,
  `tests/test_serializable_mutation_coordinator.py`. Builder S9 debe preservar
  esos bytes; documenter posterior podrá añadir hunks canónicos en docs sin
  alterar el hunk S8. Auditoría S9 compara delta contra este fingerprint, no el
  diff total contra HEAD.
- S9 plan critique R2: `verdict=approved`, `safe_to_build=true`; permisos,
  predicados AST y fingerprint corregidos antes del builder.
- S9 builder 2026-07-18: `status=completed`, sin violaciones de write set.
  Eliminó `_active_scene_key`, `_entries` y `_entry_path_or_key`; reuse de
  `load_scene_from_file` activa exclusivamente mediante workspace y propaga el
  rechazo PLAY; `clear_all_dirty` usa la autoridad real. Añadió el test AST de
  imports runtime, grafo de owners, writers, rebuild, cuatro dependencias,
  wiring único y fachada, además de tres contratos conductuales de carga
  existente. TDD rojo 37 con dos fallos esperados tras corregir dos defectos del
  test; verde 37/37. Focused manager 87/87; owners 180/180; EngineAPI/editor
  149/149; CLI/runtime/Unity 142/142; Ruff, Mypy y diff-check verdes. Fingerprint
  S8 `14683e3075554f5acdb59bf4bb471138c4490d25` y hunk TECHNICAL
  `3e69f4378e983baa74556fa266ce3b0ebf51312f` intactos.
- S9 documenter 2026-07-18: `status=completed`. Actualizó únicamente
  `docs/architecture.md` y `docs/TECHNICAL.md`: workspace es la única transición
  de activación y SceneManager queda documentado como fachada fina. El hunk S8
  de restauración exacta se preservó; `motor doctor` quedó sano con dos avisos
  preexistentes de bootstrap ausente y `git diff --check` verde.
- GATE S9 benchmark rondas 1 y 2: mismo harness quick, backend `legacy_aabb`,
  warmup 1 y siete muestras; ambas 4/4 casos, 0 warnings y 0 failures. Artefactos
  `s9-benchmarks.json` SHA-256
  `75482AEF8AA82FC9A1F5DA778357089A9E64AF5328B48525B463C330C21A295B` y
  `s9-benchmarks-rerun.json` SHA-256
  `80F4498C633B8E0052CF9A3AA321261BE3574A9A3471296A90BEDB3C6F088664`.
  Performance review independiente: `verdict=benchmark_noise`,
  `third_run_required=false`, `gate_blocking=false`, `must_fix=[]`; las alertas
  aisladas no se repitieron o quedaron dentro del noise floor histórico y no hay
  cambio causal en los hot paths medidos.
- GATE S9 validator ciclo 1: `phase_status=blocked` únicamente por evidencia de
  ejecución truncada, sin `must_fix` funcional. Owners 190/190, EngineAPI,
  adapters y editor 77/77, runtime y Unity 93/93, Ruff producción/tests, Mypy
  global de 424 archivos, arquitectura, artifacts y diff-check verdes. La suite
  completa y el bloque CLI fueron ejecutados, pero el terminal no expuso sus
  footers; Reina raíz debe repetirlos con captura acotada y pedir revalidación
  antes del reviewer.
- GATE S9 evidencia de ejecución raíz: sesiones persistidas hasta footer real.
  CLI 61/61 OK en 121,353 s, exit 0; suite completa 3.899/3.899 OK, 8 skips,
  502,944 s, exit 0. El bloqueo era de captura del terminal, no funcional;
  revalidación independiente solicitada antes del reviewer.
- GATE S9 validator final: `verdict=pass`, `test_contract_satisfied=true`,
  `must_fix=[]`. Confirma suite 3.899/3.899, 8 skips; CLI 61/61; owners
  190/190; API, adapters y editor 77/77; runtime y Unity 93/93; Ruff
  producción/tests; Mypy global 424; arquitectura, artifacts, write set y
  diff-check verdes.
- GATE S9 reviewer deep ciclo 1: `verdict=changes_requested`, `gate_ready=false`,
  cuatro `must_fix`. (1) La reutilización de una escena abierta adelanta mtime
  sin instalar el nuevo payload y puede suprimir refresh externo. (2) El test
  AST no normaliza `ImportFrom.level`, por lo que imports/aristas relativas
  evaden el contrato. (3) El audit de writers limita entry state a módulos
  directos de `engine/scenes` y no resuelve receptores `SceneWorkspaceEntry` en
  todo `engine/**`. (4) docs llaman erróneamente a `activate_scene()` la única
  transición, aunque workspace también activa al load/create/close. S8,
  firmas, owners reales y benchmark permanecen verdes.
- PLAN SYNC S9 remediation R1: builder autorizado únicamente en
  `engine/scenes/scene_manager.py`, `tests/test_scene_architecture.py` y
  `tests/test_scene_workspace.py`; documenter posterior únicamente en
  `docs/architecture.md` y `docs/TECHNICAL.md`. Remedio mínimo: no reconocer
  mtime no instalado en reuse/rechazo PLAY; normalizar imports absolutos y
  relativos incluido `module=None` respetando `TYPE_CHECKING`; analizar writers
  resolubles/tipados como `SceneWorkspaceEntry` bajo todo `engine/**` con única
  autoridad `workspace_lifecycle.py`; añadir probes adversariales estables.
- S9 remediation builder R1: `status=completed`, write set exacto y sin
  violaciones. TDD rojo reprodujo dos `DiskOne != DiskTwo`; control dirty verde.
  La rama reuse ya no reconoce un mtime cuyo payload no instaló. El AST
  normaliza imports absolutos/relativos incluido `module=None`, respeta
  `TYPE_CHECKING`, incorpora aristas relativas y audita receivers entry
  tipados/resueltos en todo `engine/**` sin falsos positivos conocidos.
  Arquitectura+workspace 45/45 y focused amplio 125/125; Ruff 3 archivos,
  Mypy manager+arquitectura y diff-check verdes. Suite completa reservada al
  revalidator.
- S9 remediation documenter R1: `status=completed`, únicamente
  `docs/architecture.md` y `docs/TECHNICAL.md`. Ambas describen
  `activate_scene()` como transición explícita para una entrada ya abierta y
  ruta de reuse del manager, manteniendo `SceneWorkspace` como autoridad única
  del estado activo sin negar load/create/close internos. Diff-check verde.
- GATE S9 validator post-R1: `verdict=pass`, `test_contract_satisfied=true`,
  `must_fix=[]`. Focused Scene/arquitectura/manager/persistencia/rollback
  235/235; API/adapters/editor/runtime/Unity 170/170; CLI 61/61; governance
  75/75; suite completa 3.907/3.907 OK, 8 skips, 471,042 s, exit 0. Ruff
  producción/tests, Mypy global 424, diff-check, write set, S8 protegido y
  artifacts verdes. Los cuatro `must_fix` R1 quedan verificados.
- GATE S9 reviewer deep post-R1: `verdict=changes_requested`, `gate_ready=false`,
  un `must_fix` y un `should_fix`, ambos limitados al test AST. El writer audit
  no detecta entry dentro de `enumerate(entries.values())` ni un atributo
  `self.entry` tipado compartido entre métodos, y marca falsamente un
  `config.resolve_entry()` ajeno. Además debe endurecerse alias de
  `TYPE_CHECKING` y scans de futuros subpaquetes. Mtime, docs, imports relativos,
  S8 y benchmark quedan aprobados.
- PLAN SYNC S9 remediation R2: builder autorizado exclusivamente en
  `tests/test_scene_architecture.py`. Debe resolver elementos de values/items y
  enumerate, propagar atributos de instancia tipados entre métodos, vincular
  resolvers a receptores workspace/manager conocidos o tipados, registrar aliases
  de `TYPE_CHECKING` y usar `rglob` con paths relativos en scans de servicios y
  wiring. Añadir probes adversariales de los casos exactos; ningún cambio de
  producción, docs, artifacts ni tests conductuales.
- S9 remediation builder R2: `status=completed`, único archivo
  `tests/test_scene_architecture.py`, sin violaciones. TDD rojo 4/4 para alias
  `TYPE_CHECKING`, enumerate-values, atributo entry entre métodos y resolver
  ajeno; verde 22/22 arquitectura y 69/69 arquitectura+workspace+contratos.
  Añadió items/subscript/port/wrapper y subpaths; Ruff, Mypy y diff-check verdes.
  Producción, docs, S8 y artifacts intactos.
- GATE S9 validator post-R2: `verdict=pass`, `test_contract_satisfied=true`,
  `must_fix=[]`. Arquitectura 22/22, focused 132/132 y suite completa
  3.914/3.914 OK, 8 skips, 461,301 s, exit 0. Ruff producción/tests, Mypy
  global 424, diff-check, write set, producción S8/S9 protegida y artifacts
  verdes. Test arquitectónico SHA-256
  `48BFFF476FA9D6EAD713198099947D080BBF09FB60EF176415D15FAC8831E69E`.
- GATE S9 reviewer deep final post-R2: `verdict=approved`, `gate_ready=true`,
  `must_fix=[]`, `should_fix=[]`. Probes exactos y 17 clasificaciones
  adversariales sin falsos positivos/negativos materiales; mtime, docs, S8,
  imports, writers, subpaths, API, benchmark y evidencia global aceptados.
- GATE S9 AI audit final: `verdict=approved`, `safe_for_agents=true`, 100/100,
  tier `excellent`, `must_fix=[]`, `should_fix=[]`. APIs, ports, adapters, CLI,
  editor y Unity siguen discoverables sin internals nuevos; autoridades,
  serialización, snapshots, docs y compliance aprobados. Probe independiente de
  governance/CLI/coherencia IA 75/75.
- CIERRE HISTÓRICO GATE S9 previo al commit funcional: `S9 completed`,
  `GATE S9 completed`. Validator `pass`, reviewer deep `approved`, AI audit
  `approved`, performance `benchmark_noise` no bloqueante y `must_fix=[]`.
  Las afirmaciones históricas de que aún no existían commit ni push quedaron
  superadas cuando se creó y publicó
  `f0bc3cc5561b789dcc0135718e495e889b7d7465`; no describen el estado Git actual.
- Auditoría raíz terminal histórica anterior a `f0bc3cc`: arquitectura+workspace+contratos 69/69 OK en
  10,285 s; Ruff del write set S8/S9 y Mypy de cinco módulos críticos verdes;
  `git diff --check` OK. En ese momento HEAD y upstream eran
  `3850e1995c1a7756803bfa8486f27c7ccf570874`, mientras el merge-base real era
  `fded3556ed9509d5f0e06221f1655ba0f4053687`. Working tree limitado
  al plan, docs, write set funcional/tests y dos artifacts S9 registrados;
  hashes de arquitectura y benchmarks coincidían. Esta evidencia no sustituye
  la revalidación exacta del SHA funcional registrada abajo.

## Inventario Git completo del refactor

Fuente: `git diff --name-only fded3556ed9509d5f0e06221f1655ba0f4053687..f0bc3cc5561b789dcc0135718e495e889b7d7465`.
Resultado: 103 archivos, todos clasificados una sola vez.

### Producción del subsistema de escenas (16)

- `engine/scenes/change_history.py`
- `engine/scenes/component_authoring.py`
- `engine/scenes/contracts.py`
- `engine/scenes/edit_sync.py`
- `engine/scenes/entity_authoring.py`
- `engine/scenes/incremental_authoring.py`
- `engine/scenes/prefab_overrides.py`
- `engine/scenes/scene.py`
- `engine/scenes/scene_flow.py`
- `engine/scenes/scene_manager.py`
- `engine/scenes/scene_projection.py`
- `engine/scenes/serializable_authoring.py`
- `engine/scenes/serializable_mutation.py`
- `engine/scenes/serializable_pipeline.py`
- `engine/scenes/structural_authoring.py`
- `engine/scenes/workspace_lifecycle.py`

### Tests funcionales y arquitectónicos (26)

- `tests/test_authoring_transactions.py`
- `tests/test_ecs_clone.py`
- `tests/test_editor_tools.py`
- `tests/test_hierarchy_operations.py`
- `tests/test_prefab_overrides.py`
- `tests/test_scene_architecture.py`
- `tests/test_scene_change_history.py`
- `tests/test_scene_component_authoring.py`
- `tests/test_scene_edit_sync.py`
- `tests/test_scene_entity_authoring.py`
- `tests/test_scene_flow.py`
- `tests/test_scene_history_atomicity.py`
- `tests/test_scene_incremental_authoring.py`
- `tests/test_scene_incremental_creation.py`
- `tests/test_scene_index.py`
- `tests/test_scene_manager_contracts.py`
- `tests/test_scene_manager_sync.py`
- `tests/test_scene_mutation_rollback_contract.py`
- `tests/test_scene_persistence_contract.py`
- `tests/test_scene_projection.py`
- `tests/test_scene_serializable_authoring.py`
- `tests/test_scene_serializable_pipeline.py`
- `tests/test_scene_structural_authoring.py`
- `tests/test_scene_workspace.py`
- `tests/test_schema_validation.py`
- `tests/test_serializable_mutation_coordinator.py`

### Documentación (3)

- `docs/TECHNICAL.md`
- `docs/architecture.md`
- `docs/plans/archive/queen-20260713-001-scene-manager-refactor.md`

### Benchmarks y artifacts (12)

- `artifacts/refactor_scene_manager/baseline.json`
- `artifacts/refactor_scene_manager/baseline_benchmarks.json`
- `artifacts/refactor_scene_manager/s1-benchmarks.json`
- `artifacts/refactor_scene_manager/s3-benchmarks.json`
- `artifacts/refactor_scene_manager/s5-benchmarks.json`
- `artifacts/refactor_scene_manager/s7-benchmarks-rerun.json`
- `artifacts/refactor_scene_manager/s7-benchmarks.json`
- `artifacts/refactor_scene_manager/s9-benchmarks-rerun.json`
- `artifacts/refactor_scene_manager/s9-benchmarks.json`
- `engine/debug/benchmark_runner.py`
- `tests/test_benchmark_run.py`
- `tests/test_benchmark_suite.py`

### Infraestructura de agentes, Queen, Codex y OpenCode (44)

- `.agents/skills/queen/SKILL.md`
- `.agents/skills/queen/references/model_router.md`
- `.agents/skills/queen/references/workflow.md`
- `.agents/skills/queen/scripts/run_opencode_subagent.py`
- `.codex/agents/ai_friendliness.toml`
- `.codex/agents/builder.toml`
- `.codex/agents/builder_deep.toml`
- `.codex/agents/code_reviewer.toml`
- `.codex/agents/code_reviewer_deep.toml`
- `.codex/agents/godot_adapter.toml`
- `.codex/agents/godot_gap_analyzer.toml`
- `.codex/agents/godot_source_analyzer.toml`
- `.codex/agents/planner.toml`
- `.codex/agents/planner_deep.toml`
- `.codex/agents/test_strategist.toml`
- `.codex/agents/test_strategist_deep.toml`
- `.opencode/agents/ai-friendliness.md`
- `.opencode/agents/builder-deep.md`
- `.opencode/agents/builder-fast.md`
- `.opencode/agents/builder.md`
- `.opencode/agents/code-reviewer-deep.md`
- `.opencode/agents/code-reviewer-fast.md`
- `.opencode/agents/code-reviewer.md`
- `.opencode/agents/committer.md`
- `.opencode/agents/context-recon.md`
- `.opencode/agents/documenter.md`
- `.opencode/agents/godot-adapter.md`
- `.opencode/agents/godot-gap-analyzer.md`
- `.opencode/agents/godot-source-analyzer.md`
- `.opencode/agents/planner-deep.md`
- `.opencode/agents/planner-fast.md`
- `.opencode/agents/planner.md`
- `.opencode/agents/queen-codex-dispatch.md`
- `.opencode/agents/test-strategist-deep.md`
- `.opencode/agents/test-strategist-fast.md`
- `.opencode/agents/test-strategist.md`
- `.opencode/agents/validator.md`
- `AGENTS.md`
- `docs/agents.md`
- `docs/queen_engine_workflow.md`
- `opencode.json`
- `tests/test_codex_queen_contract.py`
- `tests/test_queen_agent_contract.py`
- `tests/test_queen_dispatch.py`

### Otros cambios auxiliares (2)

- `engine/ecs/world_clone.py`
- `engine/editor/undo_redo.py`

## Justificación de cambios auxiliares y de gobernanza

### Queen y fallback Codex/OpenCode

- Archivos: `.agents/skills/queen/**`, `.opencode/agents/queen-codex-dispatch.md`,
  `opencode.json`, `AGENTS.md`, `docs/agents.md` y
  `docs/queen_engine_workflow.md`.
- Historia: el grupo fue materializado en
  `a5266785896316c3880f2f919011dc431c6bfdb7` durante las fases largas del
  refactor. El diff registra el problema concreto: Queen podía declarar
  `missing_required_agent` cuando la tool nativa faltaba o no conocía un rol,
  aunque existiera un rol OpenCode mapeado.
- Solución: política native-first, fallback automático solo antes de crear un
  child nativo, dispatcher sin permisos salvo una única `task`, validación del
  `task_result`, códigos de error distintos y límite de concurrencia. Esto
  soportó planificación, dispatch, validación, review y auditoría sin convertir
  un fallo de backend en falso éxito.
- Relación con el refactor: fue infraestructura operativa usada para mantener
  gates y roles especializados durante S7-S9; no implementa lógica de escenas.
- Runtime: no se importa durante ejecución normal del motor. Solo se usa al
  invocar Queen/OpenCode desde tooling de desarrollo.
- Protección: `tests/test_codex_queen_contract.py`,
  `tests/test_queen_agent_contract.py` y `tests/test_queen_dispatch.py`; en la
  revalidación exacta pasaron 99/99.
- Riesgo: dependencia del ejecutable y formato JSONL de OpenCode, más superficie
  de configuración. Mitigación: `shell=False`, allowlist cerrada, sin permisos
  de lectura/escritura del dispatcher, un solo dispatch, validación contractual
  y errores no enmascarados. Riesgo aceptable por quedar fuera del runtime.

### Configuración Codex y contratos de resultados OpenCode

- Archivos: los 12 `.codex/agents/*.toml` inventariados y los 20 prompts
  `.opencode/agents/*.md` distintos del dispatcher.
- Problema concreto: los roles estándar/deep referían `gpt-5.6`, mientras el
  router vigente exige `gpt-5.6-sol`; además los envelopes OpenCode no exponían
  `phase_status`, impidiendo distinguir fase terminada de tarea terminada.
- Solución: sincronización de IDs de modelo y adición de `phase_status` con
  reglas coherentes por rol. Esto evita dispatch inválido y cierres prematuros.
- Runtime: configuración y prompts de desarrollo; no son imports del motor.
- Protección: `test_codex_queen_contract.py` verifica modelos/dispatcher y
  `test_queen_agent_contract.py` verifica `phase_status` en todos los roles.
- Riesgo: drift futuro de nombres de modelo o contratos duplicados entre Codex
  y OpenCode. Aceptable en esta rama porque el cambio nació durante el refactor,
  está probado y no afecta datos ni ejecución del motor.

### Gobernanza y documentación de agentes

- Archivos: `AGENTS.md`, `docs/agents.md` y `docs/queen_engine_workflow.md`.
- Problema concreto: un catálogo de skills obsoleto podía ocultar la skill
  Queen existente y el plan no registraba la semántica del fallback ni sus
  códigos de salida.
- Solución: bootstrap mínimo, autoridad native-first y documentación canónica
  del workflow. Su relación es exclusivamente planificación y auditoría.
- Runtime: documentación/gobernanza; no se carga por el motor.
- Riesgo: instrucciones más densas. Aceptable porque eliminan una contradicción
  operativa observada y están cubiertas por tests de contrato.

### Harness de benchmark

- Archivos: `engine/debug/benchmark_runner.py`,
  `tests/test_benchmark_run.py`, `tests/test_benchmark_suite.py` y nueve JSON de
  `artifacts/refactor_scene_manager/`.
- Problema concreto: mediciones one-shot y tres muestras no permitían decidir
  gates del refactor. El cambio fuerza warmup 1, mínimo siete muestras, mediana,
  MAD/noise floor y clasificación `repeated_gate`; además mide transiciones y
  `transform_edit` sin dejar estado incoherente.
- Relación: proporciona baseline S1 y comparaciones S3/S5/S7/S9 requeridas para
  validar el refactor.
- Runtime: módulo debug invocado por tooling/CI; no forma parte del bucle normal
  salvo ejecución explícita de benchmarks.
- Protección: 22/22 tests del harness en la revalidación y dos rondas 4/4.
- Riesgo: tiempo de CI y variabilidad de microbenchmarks. Aceptable con dos
  rondas, artifacts crudos, umbrales hard/soft y análisis de noise floor.

### Cambios auxiliares que sí pertenecen al runtime

- `engine/ecs/world_clone.py`: conserva las siete versiones del `World` al
  clonar y permite que clon/original avancen de forma independiente. Fue
  necesario para que PLAY, rollback y prefabs no pierdan versiones al reemplazar
  mundos durante el refactor. Lo protege `tests/test_ecs_clone.py`.
- `engine/editor/undo_redo.py`: añade checkpoint opaco y restauración exacta de
  pilas para que `SerializableMutationCoordinator` pueda hacer rollback
  failure-atomic sin duplicar autoridad de historial. Lo protegen contratos de
  historial, atomicidad y rollback incluidos en el bloque 158/158.
- Riesgo: copiar versiones obsoletas o restaurar un token ajeno. Mitigación:
  clonación exacta seguida de avance independiente y `TypeError` para tokens no
  creados por `UndoRedoManager`. Son cambios internos; no cambian
  `SceneManager` ni `EngineAPI` públicas.

### Confirmaciones de límites

- `.agents/**`, `.codex/**`, `.opencode/**`, `AGENTS.md`, `opencode.json`, sus
  docs y tests no se cargan como runtime normal del motor.
- Excepciones declaradas: `engine/ecs/world_clone.py` y
  `engine/editor/undo_redo.py` sí son runtime interno; el benchmark runner solo
  se carga al ejecutar tooling de benchmark.
- No cambia el schema de escenas: `engine/serialization/schema.py` no aparece
  en el diff; `tests/test_schema_validation.py` refuerza el contrato.
- No cambia API pública de `EngineAPI`: no aparece ningún archivo `engine/api/**`.
  Los wrappers públicos de `SceneManager` conservan firma y comportamiento;
  contratos públicos/adapters pasaron 101/101.
- No introduce segunda autoridad de estado: `tests/test_scene_architecture.py`
  pasó 22/22 y verifica writers únicos, wiring único, imports runtime y grafo
  acíclico.
- Estos cambios no invalidan revisión funcional: suite exacta 3914/3914,
  estáticos, contratos, arquitectura y benchmarks están verdes. No existe
  `must_fix` funcional abierto.

## Archivos de esta corrección de cierre

No pertenecen al snapshot funcional `f0bc3cc`:

- `.github/workflows/scene-manager-refactor-validation.yml`
- `docs/plans/archive/queen-20260713-001-scene-manager-refactor.md`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/full-suite.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/ruff-production.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/ruff-tests.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/mypy-global.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/scene-architecture.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/public-contracts.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/scene-state-contracts.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-harness-tests.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/queen-governance-tests.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-round-1.json`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-round-1.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-round-2.json`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-round-2.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/diff-check-working-tree.log`
- `artifacts/refactor_scene_manager/closure_f0bc3cc/diff-check-branch.log`

## Hallazgos pendientes

- `ci_execution=failed`: run `29665496955` terminó con `conclusion=failure`.
  `Full test suite` ejecutó 3.914 tests: 11 failures, 1 error y 26 skips; los
  doce problemas pertenecen exclusivamente a `tests.test_queen_dispatch`.
- Causa raíz: el runner GitHub limpio no contiene `opencode` en `PATH`. Once
  tests mockean `run_opencode` pero `main()` resuelve antes el ejecutable y
  retorna `EXIT_CONFIG=2`; el test directo de `run_opencode` tampoco inyecta el
  executable. La máquina local sí resuelve `opencode.CMD`, por eso la evidencia
  local histórica pasó. Es un defecto de aislamiento de tests Queen/OpenCode,
  no un fallo funcional de SceneManager.
- Los steps Ruff, Mypy, arquitectura, benchmarks y diff-check quedaron
  `skipped` por el fallo anterior. El artifact `8435654167` sí se publicó y se
  descargó correctamente; contiene `full-suite.log` utilizable.
- La revalidación local histórica de la suite completa dejó dos settings
  tracked marcados por normalización de finales de línea: empezó limpia, pasó y
  restauró solo esos dos archivos en el worktree temporal antes de los demás
  gates. Esa evidencia local es anterior y distinta del run CI fallido; no
  altera el SHA auditado, pero revela deuda de aislamiento de tests no atribuible
  al refactor funcional.
- `must_fix=[]` para código funcional de SceneManager. Estado global `partial`
  porque el gate CI obligatorio falló y no puede declararse completado.

## Revalidación reproducible del SHA funcional

### Entorno aislado

- Worktree detached temporal:
  `C:/Users/usuario/AppData/Local/Temp/OpenGame-validation-f0bc3cc`; eliminado
  limpio después de preservar la evidencia fuera del snapshot.
- Cada log registra antes del comando: `git rev-parse HEAD`,
  `git status --short` y `python --version`.
- Todos los bloques comenzaron con SHA
  `f0bc3cc5561b789dcc0135718e495e889b7d7465`, status vacío y Python 3.11.1.
- La suite completa fue el primer bloque. Sus efectos laterales sobre dos
  settings se restauraron desde el mismo SHA antes de continuar.

### Comandos y resultados

| Gate | Comando exacto | Exit | Resultado | Duración | Evidencia |
| --- | --- | ---: | --- | ---: | --- |
| Suite completa | `python -m unittest discover -s tests` | 0 | 3914 pass, 0 fail, 8 skip | 418.113 s unittest; 427.557 s proceso | `closure_f0bc3cc/full-suite.log` |
| Ruff producción | `python -m ruff check engine cli tools main.py` | 0 | sin findings | 0.251 s | `closure_f0bc3cc/ruff-production.log` |
| Ruff tests | `python -m ruff check tests` | 0 | sin findings | 0.244 s | `closure_f0bc3cc/ruff-tests.log` |
| Mypy global | `python -m mypy engine cli tools main.py` | 0 | 424 archivos, 0 issues | 6.517 s | `closure_f0bc3cc/mypy-global.log` |
| Arquitectura/imports/ciclos | `python -m unittest tests.test_scene_architecture` | 0 | 22 pass, 0 fail, 0 skip | 7.438 s unittest; 7.816 s proceso | `closure_f0bc3cc/scene-architecture.log` |
| API pública/adapters | `python -m unittest tests.test_scene_manager_contracts tests.test_engine_api_scene_sync tests.test_engine_api_public_contract tests.test_engine_api_facade_smoke tests.test_api_authoring_workspace tests.test_unity_core_authoring` | 0 | 101 pass, 0 fail, 0 skip | 5.016 s unittest; 5.636 s proceso | `closure_f0bc3cc/public-contracts.log` |
| Rollback/dirty/pending/history/prefabs | `python -m unittest tests.test_scene_mutation_rollback_contract tests.test_scene_manager_sync tests.test_scene_edit_sync tests.test_scene_history_atomicity tests.test_scene_change_history tests.test_prefab_overrides tests.test_prefab_persistence tests.test_scene_persistence_contract tests.test_scene_save_integrity tests.test_scene_workspace tests.test_serializable_mutation_coordinator` | 0 | 158 pass, 0 fail, 0 skip | 1.483 s unittest; 2.058 s proceso | `closure_f0bc3cc/scene-state-contracts.log` |
| Harness benchmark | `python -m unittest tests.test_benchmark_run tests.test_benchmark_suite` | 0 | 22 pass, 0 fail, 0 skip | 48.303 s unittest; 48.907 s proceso | `closure_f0bc3cc/benchmark-harness-tests.log` |
| Gobernanza auxiliar | `python -m unittest tests.test_codex_queen_contract tests.test_queen_agent_contract tests.test_queen_dispatch` | 0 | 99 pass, 0 fail, 0 skip | 0.160 s unittest; 0.512 s proceso | `closure_f0bc3cc/queen-governance-tests.log` |
| Benchmark ronda 1 | `python -m tools.benchmark_suite --quick --backend legacy_aabb --out C:/Users/usuario/Documents/GitHub/MotorVideojuegosIA/artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-round-1.json` | 0 | 4/4 pass, 0 warnings, 0 fail | 105.731 s | JSON + log ronda 1 |
| Benchmark ronda 2 | `python -m tools.benchmark_suite --quick --backend legacy_aabb --out C:/Users/usuario/Documents/GitHub/MotorVideojuegosIA/artifacts/refactor_scene_manager/closure_f0bc3cc/benchmark-round-2.json` | 0 | 4/4 pass, 0 warnings, 0 fail | 107.330 s | JSON + log ronda 2 |
| Diff worktree | `git diff --check` | 0 | limpio | 0.173 s | `closure_f0bc3cc/diff-check-working-tree.log` |
| Diff completo de rama | `git diff --check fded3556ed9509d5f0e06221f1655ba0f4053687..f0bc3cc5561b789dcc0135718e495e889b7d7465` | 0 | limpio | 0.297 s | `closure_f0bc3cc/diff-check-branch.log` |

Directorio de ejecución en todos los casos: el worktree detached indicado.
Ruff/Mypy/diff no producen conteo de tests; skips no aplican.

### Benchmarks y comparación

- Protocolo: suite `--quick` completa de cuatro casos, backend `legacy_aabb`;
  `benchmark_runner` impone warmup efectivo 1, siete muestras mínimas, mediana,
  MAD y noise floor.
- Baseline autoritativo: `s1-benchmarks.json`, SHA-256
  `BC2A089A0FAC5F20A2B73CA07D98A1533C233074675EDA259C224EF4CA9758D4`.
- Ronda 1: SHA-256
  `02A386573AD2160CB5EF676FEAC30B10D23A6B225BA554241F1B7E33B37F437C`.
- Ronda 2: SHA-256
  `B55B051A04E78A7C25B9CFA0B9A68FA29B5C33F3ED29580702C29167F5CCF8F5`.
- Ambos reports: `status=passed`, 4 casos, 0 warnings y 0 failures.
- Frente a S1, `transform_edit` conserva alerta histórica: mediana agrupada
  0.02265 ms frente a 0.01640 ms, +38.11 %. No es regresión nueva del cierre:
  mejora 17.79 % frente al centro de los dos artifacts S9 del mismo código y el
  A/B same-process ya registrado en S5 midió coste causal 5.57 %, menor al 10 %.
- `scene_add_entity_canonicalization` agrupado queda +10.75 % frente a S1, con
  delta absoluto 0.0010 ms igual al MAD actual y sin repetirse en ambas rondas
  individuales. Resto de alertas >10 % frente a S1 son mejoras.
- Clasificación: `benchmark_noise`/sin regresión material nueva;
  `third_run_required=false`, `must_fix=[]`.

### CI

- Workflow existente `.github/workflows/ci.yml`: Python 3.11, suite, Ruff,
  Mypy y benchmark quick, pero sin `workflow_dispatch`, checkout de SHA exacto
  ni guard explícito del SHA.
- Workflow nuevo `.github/workflows/scene-manager-refactor-validation.yml`:
  dispatch manual, input por defecto `f0bc3cc...`, exige SHA hexadecimal de 40
  caracteres, checkout explícito, guard de igualdad, Python 3.11, instalación
  canónica, suite, Ruff, Mypy, arquitectura, dos benchmarks, diff-check y upload
  de logs/artifacts. Permisos `contents: read`, credenciales no persistidas,
  timeout 45 minutos, sin secretos ni escritura remota.
- Primer intento de dispatch: `2026-07-18T23:15:33.7285676Z`, sin run creado.
  GitHub devolvió `HTTP 422` porque `runner.temp` no está disponible en
  `jobs.<job_id>.env`. El push previo `29663662271` ya había fallado sin jobs
  por la misma definición inválida. La corrección mínima movió `EVIDENCE_DIR`
  a `steps.env`, lo propagó mediante `GITHUB_ENV`, quedó aprobada por review y
  AI audit, y se publicó en el commit prerequisito
  `70a152325c7f693df7a1b315e72b5ad2188c16db`.
- Segundo dispatch: creado inequívocamente respecto al listado previo vacío,
  con timestamp UTC inmediatamente anterior `2026-07-18T23:35:33.4140250Z`.
  GitHub aceptó el workflow y creó el run `29665496955`.
- `ci_execution=failed`: el run terminó; no se considera gate completado.

#### Run ejecutado

| Campo | Valor |
| --- | --- |
| workflow | `.github/workflows/scene-manager-refactor-validation.yml` |
| databaseId | `29665496955` |
| URL | `https://github.com/Yisuescopeta/OpenGame/actions/runs/29665496955` |
| createdAt | `2026-07-18T23:35:33Z` (`2026-07-19T01:35:33+02:00`) |
| startedAt | `2026-07-18T23:35:33Z` |
| updatedAt | `2026-07-18T23:42:33Z` |
| event | `workflow_dispatch` |
| rama de dispatch | `feat/SceneManagerRefactor` |
| headSha del evento | `70a152325c7f693df7a1b315e72b5ad2188c16db` |
| `validation_ref` solicitado | `f0bc3cc5561b789dcc0135718e495e889b7d7465` |
| SHA checkout verificado | `f0bc3cc5561b789dcc0135718e495e889b7d7465` (`Checkout requested snapshot` y `Verify exact SHA`: `success`) |
| status | `completed` |
| conclusion | `failure` |

`headSha` identifica el commit que contiene/dispara el workflow; no sustituye
al SHA funcional. El input, el checkout y el step de igualdad demuestran que el
snapshot ejecutado fue exactamente `f0bc3cc...`; el artifact conserva la salida
de la suite asociada a ese mismo run.

#### Jobs

| Job | Job ID | Status | Conclusion | startedAt | completedAt | URL |
| --- | ---: | --- | --- | --- | --- | --- |
| Validate exact functional snapshot | `88135130129` | `completed` | `failure` | `2026-07-18T23:35:40Z` | `2026-07-18T23:42:32Z` | `https://github.com/Yisuescopeta/OpenGame/actions/runs/29665496955/job/88135130129` |

#### Steps

| Nº | Step | Status | Conclusion | startedAt | completedAt | Observación |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | Set up job | `completed` | `success` | `2026-07-18T23:35:41Z` | `2026-07-18T23:35:43Z` | — |
| 2 | Checkout requested snapshot | `completed` | `success` | `2026-07-18T23:35:43Z` | `2026-07-18T23:35:54Z` | Checkout del input exacto |
| 3 | Verify exact SHA | `completed` | `success` | `2026-07-18T23:35:54Z` | `2026-07-18T23:36:10Z` | Igualdad con `f0bc3cc...` confirmada |
| 4 | Set up Python 3.11 | `completed` | `success` | `2026-07-18T23:36:10Z` | `2026-07-18T23:36:13Z` | Python 3.11.9 |
| 5 | Configure validation evidence directory | `completed` | `success` | `2026-07-18T23:36:13Z` | `2026-07-18T23:36:14Z` | Remediación del parser efectiva |
| 6 | Install project | `completed` | `success` | `2026-07-18T23:36:14Z` | `2026-07-18T23:36:49Z` | Snapshot permaneció limpio |
| 7 | Full test suite | `completed` | `failure` | `2026-07-18T23:36:49Z` | `2026-07-18T23:42:26Z` | 3.914 tests; 11 failures, 1 error, 26 skips |
| 8 | Restore tracked test side effects | `completed` | `success` | `2026-07-18T23:42:26Z` | `2026-07-18T23:42:27Z` | Limpieza controlada completada |
| 9 | Ruff production | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 10 | Ruff tests | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 11 | Mypy | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 12 | Scene architecture and import-cycle contracts | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 13 | Benchmark round 1 | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 14 | Benchmark round 2 | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 15 | Diff check | `completed` | `skipped` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:27Z` | Skip por fallo anterior |
| 16 | Upload validation evidence | `completed` | `success` | `2026-07-18T23:42:27Z` | `2026-07-18T23:42:28Z` | Artifact publicado pese al fallo (`if: always()`) |
| 31 | Post Set up Python 3.11 | `completed` | `skipped` | `2026-07-18T23:42:28Z` | `2026-07-18T23:42:28Z` | Cleanup no requerido por la action |
| 32 | Post Checkout requested snapshot | `completed` | `success` | `2026-07-18T23:42:28Z` | `2026-07-18T23:42:30Z` | — |
| 33 | Complete job | `completed` | `success` | `2026-07-18T23:42:30Z` | `2026-07-18T23:42:30Z` | Job conserva conclusión global `failure` |

#### Artefactos

| Artifact ID | Nombre | size_in_bytes | created_at | expires_at | expired |
| ---: | --- | ---: | --- | --- | --- |
| `8435654167` | `scene-manager-refactor-validation-f0bc3cc5561b789dcc0135718e495e889b7d7465` | `6777` | `2026-07-18T23:42:28Z` | `2026-08-17T23:42:27Z` | `false` |

- API: `https://api.github.com/repos/Yisuescopeta/OpenGame/actions/artifacts/8435654167`.
- archive_download_url: `https://api.github.com/repos/Yisuescopeta/OpenGame/actions/artifacts/8435654167/zip`.
- Digest remoto: `sha256:edb5b941c5496c40f77086f1923a9b33888543cb2ea907ee8368d3f1be51e9c7`.
- Descarga comprobada fuera del repo en
  `C:/Users/usuario/AppData/Local/Temp/OpenGame-run-29665496955-artifact`.
  Contiene `full-suite.log`, 43.802 bytes, SHA-256
  `529ADF10624285C12C655568C8ABF6DCBD519A21FD82994239B645028DC8A690`;
  el archivo se abrió y analizó correctamente.

#### Fallo, warnings y anomalías

- Fallo causal: `opencode executable not found on PATH` en
  `tests.test_queen_dispatch`. Once casos esperaban alcanzar sus mocks de
  `run_opencode`, pero la resolución previa devolvió código `2`; el caso directo
  lanzó `DispatchError`. Total: 11 failures, 1 error, 26 skips.
- La máquina local tiene
  `C:/Users/usuario/AppData/Roaming/npm/opencode.CMD`; el runner no. La diferencia
  explica el verde local histórico. No se relajó ningún test ni se cambió
  ningún algoritmo del refactor.
- Anotación GitHub: Node.js 20 de `actions/checkout@v4`,
  `actions/setup-python@v5` y `actions/upload-artifact@v4` está deprecado y
  GitHub forzó Node.js 24. No fue la causa del fallo.
- El log también contiene warnings/deprecations esperados de runtime opcional
  y Box2D; no aparecen como failures. Los siete gates posteriores quedaron
  skipped y no se presentan como ejecutados.

#### Comandos de cierre CI

| Comando | Resultado |
| --- | --- |
| `git fetch --all --prune` | exit 0 |
| `git switch feat/SceneManagerRefactor` | exit 0; rama correcta |
| `git pull --ff-only` | exit 0; up to date |
| `git status --short` | vacío al preflight |
| `git rev-parse HEAD` / `git rev-parse origin/feat/SceneManagerRefactor` | ambos `075b28ae491302679cd6a476db156d8eb0bca1df` antes del cierre CI |
| `git merge-base HEAD origin/main` | `fded3556ed9509d5f0e06221f1655ba0f4053687` |
| `gh auth status` | exit 0; cuenta `Yisuescopeta`, scopes `repo` y `workflow` |
| primer `gh workflow run ... -f validation_ref=f0bc3cc...` | exit 1; HTTP 422, no creó run |
| `git push origin feat/SceneManagerRefactor` para `70a1523...` | exit 0 |
| segundo `gh workflow run ... -f validation_ref=f0bc3cc...` | exit 0; creó run `29665496955` |
| `gh run list ... --event workflow_dispatch ...` | exit 0; único run nuevo identificado |
| `gh run watch 29665496955 --repo Yisuescopeta/OpenGame --exit-status` | exit 1 tras estado terminal `failure` |
| `gh run view 29665496955 ... --json ...` | exit 0; metadata, job y steps obtenidos |
| `gh api repos/Yisuescopeta/OpenGame/actions/runs/29665496955/artifacts` | exit 0; un artifact real |
| `gh run download 29665496955 ...` | exit 0; artifact utilizable |

Invocaciones GitHub completas usadas para el run terminal y su evidencia:

```powershell
gh workflow run scene-manager-refactor-validation.yml --repo Yisuescopeta/OpenGame --ref feat/SceneManagerRefactor -f validation_ref=f0bc3cc5561b789dcc0135718e495e889b7d7465
gh run list --repo Yisuescopeta/OpenGame --workflow scene-manager-refactor-validation.yml --event workflow_dispatch --limit 10 --json databaseId,createdAt,displayTitle,event,headBranch,headSha,status,conclusion,url,workflowName
gh run watch 29665496955 --repo Yisuescopeta/OpenGame --exit-status
gh run view 29665496955 --repo Yisuescopeta/OpenGame --json databaseId,url,status,conclusion,createdAt,startedAt,updatedAt,headBranch,headSha,event,workflowName,jobs
gh api repos/Yisuescopeta/OpenGame/actions/runs/29665496955/artifacts
gh run download 29665496955 --repo Yisuescopeta/OpenGame --name scene-manager-refactor-validation-f0bc3cc5561b789dcc0135718e495e889b7d7465 --dir C:\Users\usuario\AppData\Local\Temp\OpenGame-run-29665496955-artifact
```

#### Validación local posterior

| Comando | Resultado |
| --- | --- |
| `python -m unittest tests.test_codex_queen_contract tests.test_queen_agent_contract tests.test_queen_dispatch` | exit 1 antes de cargar tests: el alias `python.exe` local apunta a Microsoft Store y no hay intérprete asociado |
| `py -3.11 -m unittest tests.test_codex_queen_contract tests.test_queen_agent_contract tests.test_queen_dispatch` | exit 0; 99 tests, `OK` |
| `py -3.11 -m unittest tests.test_repository_governance tests.test_start_here_ai_coherence` | exit 0; 29 tests, `OK` |
| revalidación conjunta de los cinco módulos anteriores con `py -3.11 -m unittest ...` | exit 0; 128 tests, `OK` |
| `python -m ruff check .` | exit 1 antes de ejecutar Ruff por el mismo alias de Microsoft Store |
| `py -3.11 -m ruff check .` | exit 1; 372 hallazgos globales preexistentes (174 W293, 128 W291, 35 F541, 22 I001, 7 F401, 2 E402, 2 E722 y 2 F841) |
| `py -3.11 -m ruff check engine cli tools main.py` | exit 0; `All checks passed!` |
| `py -3.11 -m ruff check tests` | exit 0; `All checks passed!` |
| `git diff --check` | exit 0, sin salida |

Los 372 hallazgos globales están fuera de este diff de cierre, que solo modifica
el workflow y este plan Markdown; no se aplicó `--fix` ni se amplió el alcance.
El lint global no queda presentado como verde. Los tests enfocados y las dos
superficies Ruff usadas por el workflow sí pasaron localmente.

Review independiente final `review-queen-20260713-001-ci-closure`:
`verdict=approved`, `must_fix=[]`. Confirma la evidencia de GitHub, el archivo
canónico único, la ausencia de cambios en `engine/` o `tests/` y que el commit
de evidencia puede avanzar sin cambiar `task_status=partial`. Conserva como
hallazgos no resueltos el gate CI fallido y la deuda Ruff global.

## Evidencia de comandos

- `git fetch --all --prune`: completado.
- Baseline focused: 84 OK.
- Baseline full: 3.670 OK, 8 skips.
- Ruff producción/tests: OK.
- Mypy: 414 archivos OK.
- Benchmark suite: 4/4 OK.
- S1 builder: 126 tests enfocados OK; benchmark de siete muestras 4/4 OK.
- S1 artifact: `artifacts/refactor_scene_manager/s1-benchmarks.json`, SHA-256 `BC2A089A0FAC5F20A2B73CA07D98A1533C233074675EDA259C224EF4CA9758D4`, generado sobre base `fded3556...` con diff de harness limitado a `engine/debug/benchmark_runner.py`.
- S1 validator: full 3.681 OK, 8 skips; Ruff/Mypy verdes; `verdict=partial` por dos gaps contractuales, no por fallo funcional.
- TEST CONTRACT SYNC `s1-scene-flow-contract-sync`: `verdict=sufficient`; autoriza cierre S1 con caracterización temporal y bloquea cierre S2 hasta paridad empty-target active/inactive.
- S1 remediation: 47 tests OK; misma operación/estado reproduce active-preserva frente a inactive-elimina; producción intacta.
- S1 validator final: `verdict=pass`, `test_contract_satisfied=true`; focused 47 OK, full 3.681 OK/8 skips, Ruff/Mypy verdes.
- S1 reviewer: `verdict=approved`, `must_fix=[]`.
- S1 documentation: `not_applicable`; cambia harness/test contract, no API, schema ni arquitectura estable del motor. Plan y artifacts actualizados.
- Gate S1: `completed`.
- S2 pre-state: tracked diff hash `fe0c45f662bfaad3c406b774ca7bca7729164099`; tracked S1 files `engine/debug/benchmark_runner.py`, `tests/test_benchmark_run.py`, `tests/test_benchmark_suite.py`, `tests/test_scene_workspace.py`; untracked S1 `tests/test_scene_flow.py` SHA-256 `2F7080FA41E4403B4B304C66A0079624365310978851CD5A5BF25C05F3BABE05`, artifacts y plan. Preservar íntegramente.
- S2 validator inicial: regresión real reproducida en Windows; 3 fallos de
  `tests.test_editor_scene_sync` por mezclar claves POSIX de identidad workspace
  con claves nativas de `_scene_file_mtimes`.
- S2 remediation: causa raíz corregida con un namespace nativo resuelto único
  para `_scene_file_mtimes`, sin alterar la identidad POSIX del workspace;
  `tests.test_editor_scene_sync` 16/16 OK, focused S2 41/41 OK, Ruff/Mypy
  enfocados y diff-check OK. Gate final sigue pendiente de suite completa.
- S2 review posterior: `changes_required`; `capture_selection` prioriza un ID
  almacenado sobre la selección visible actual del `World`, regresando EDIT ->
  PLAY cuando cambia de A a B. Reproducción root confirmada; remediación y test
  directo pendientes.
- S2 TEST CONTRACT sync: falta prueba directa de
  `SceneWorkspace.resolve_entry` y `tests/test_editor_tools.py` aún accede al
  helper privado `_resolve_entry`; se corrige en la misma remediación S2.
- S2 remediation selection/test migration: `capture_selection` prioriza ahora
  nombre e ID válidos del World activo; reproducción A -> B convertida en test
  verde. Se añadió prueba directa de `SceneWorkspace.resolve_entry` por key/ruta
  y `test_editor_tools` provoca dirty mediante API pública. Workspace,
  transitions y editor tools 82/82 OK; focused S2 43/43 OK; Ruff/Mypy enfocados
  y diff-check OK.
- S2 validator final v2: `verdict=pass`, `test_contract_satisfied=true`;
  dirigidos 19/19 OK, focused 43/43 OK, regresión amplia 220/220 OK, full
  3.687 OK/8 skips en 451.785 s, Ruff producción/tests OK, Mypy 415 archivos
  OK, diff-check e imports OK.
- S2 reviewer final v2: `verdict=approved`, `must_fix=[]`.
- S2 documentation: `updated` en `docs/architecture.md` y
  `docs/TECHNICAL.md`; autoridad workspace y precedencia scene-flow
  documentadas; checks documentales y diff-check OK.
- S2 AI audit: `not_applicable`; no cambiaron `contracts.py`, EngineAPI, schema,
  prompts ni ningún port público/agente. La semántica canónica scene-flow se
  validó mediante wrappers existentes, sin superficie nueva para agentes.
- Gate S2: `completed`.
- S3 pre-state: tracked diff hash
  `10fac1b6b824686515a3d4a390016db76956489f`; `SceneManager` 1.903 líneas y
  82.023 bytes. Untracked preservados: `scene_flow.py` SHA-256
  `646D84858566E3CDCB5E0D61817687F846B244C52BAEA735C1D26008903B460F`,
  `test_scene_flow.py` SHA-256
  `58301C9A3E4C0BAEF731EB2B37091CA999817B272F5D8DE90304612ACE496006` y
  artifacts baseline/S1 ya registrados. Preservar todos los cambios S1-S2.
- S3 builder funcional: projection/workspace/manager extraídos, 122 focused y
  71 preservación S2 OK; Ruff/Mypy/diff-check OK. Benchmark inicial S3 4/4
  funcional, pero confirmó degradaciones fuera de ruido en `scene_save`
  (+14,47% a +19,61%) y `transform_edit` (+43,90%); Gate S3 no cierra partial.
- S3 performance root cause: cProfile 10k atribuye 69,467 s acumulados a
  `deepcopy`; `SceneProjectionService.validate_payload` añadió una copia antes
  de `migrate_scene_data`, que ya copia internamente. Microbenchmark reproduce
  +17,45%. El hot path Transform usa deepcopy de un componente escalar; copia
  superficial equivalente mide ~31,1x menos. Remediación mínima y benchmark
  exacto pendientes.
- S3 performance remediation final: copias redundantes retiradas, lectura de
  metadata sin serializar 10k entidades y primitiva batch estrecha en `Scene`.
  Focused 169/169 OK. Benchmark exacto 4/4: `transform_edit` dentro de noise;
  `scene_save` -6,28%, -1,76% y +5,26% frente S1. Dos outliers auxiliares en
  World/ECS se repitieron pero no atraviesan paths modificados y estaban limpios
  en el artifact S3 inmediatamente anterior; clasificados drift ambiental, no
  regresión causal. Artifact SHA-256
  `E08F032A3049FCD2874C87F24EA089F1DC9EC32ECA37911285905BE85EFC45A5`.
- Gate S3 validator dirigido: 46/46 y focused 109/109 OK; detectó gap de TEST
  CONTRACT antes de full: falta dependency-patch directo del fallo/rollback de
  `SceneProjectionService.add_entity`. Full interrumpido y test mínimo pendiente.
- S3 TEST CONTRACT remediation: dependency-patch directo de
  `Scene.materialize_entity` añadido; verifica excepción, rollback de Scene y
  ausencia de entidad parcial en World. Projection + incremental 12/12 OK.
- S3 validator final: `verdict=pass`, `test_contract_satisfied=true`; projection
  directo 47/47 OK, focused amplio 109/109 OK, full 3.701 OK/8 skips en
  480,664 s; Ruff producción/tests OK, Mypy 416 archivos OK, diff/imports/
  arquitectura OK. Benchmark comparable S1/S3 sin regresión material causal.
- S3 reviewer: `verdict=approved`, `must_fix=[]`.
- S3 AI audit: `verdict=approved`, `safe_for_agents=true`, `must_fix=[]`; 89
  métodos públicos/firma de SceneManager sin cambios, ports y EngineAPI
  preservados, estructuras explícitas y serializables.
- S3 documentation: `updated` en los dos documentos canónicos; projection como
  autoridad técnica y workspace como installer único documentados.
- Gate S3: `completed`.
- S4 pre-state: tracked diff hash
  `32c0882578b2de20392f96325f52c2fee47904a2`; `SceneManager` 1.825 líneas y
  78.566 bytes. Untracked S3: `scene_projection.py` SHA-256
  `8274E846E428F29B398A1AA6501F772C67828EC25D216352EBA5FBDBE1B1EFAB`,
  `test_scene_projection.py` SHA-256
  `D22754C2F61C2CCCD252EE3330F085F7441CE9DDC787C15BD6D1ABB872BDA0FF`,
  artifact S3 SHA-256 ya registrado. `settings/project_settings.json` emite
  warning de line endings pero no figura modificado; no tocar. Preservar S1-S3.
- S4 builder inicial: `SceneEditSyncCoordinator` extraído como autoridad única;
  174 tests enfocados OK, Ruff/Mypy/diff-check y escaneo de writers verdes.
- Gate S4 inicial rechazado por reviewer y AI audit: 3 fallos dirigidos. Causa
  raíz: S4 adelantó la forma de `_SerializableMutationSnapshot` reservada a S7A
  y restauró `dirty_before_pending_edit_world_sync=True` donde el baseline lo
  limpiaba; `edit_sync.py` también importaba un logger fuera del grafo literal.
- S4 remediation sistemática: forma snapshot caracterizada preservada hasta
  S7A; capture/restore de la razón delegados al coordinador sin acceso directo
  desde manager; rollback vuelve a dejar dirty-before en `None`; logger retirado.
  Test autoridad sin relajar. Focused final 179/179 OK.
- S4 validator final: `verdict=pass`, `test_contract_satisfied=true`; full
  3.718 OK/8 skips en 449,815 s; governance 75/75; Ruff producción/tests OK;
  Mypy 417 archivos OK; diff, API pública 89/89, imports y autoridad OK.
- S4 reviewer final: `verdict=approved`, `must_fix=[]`.
- S4 AI audit final: `verdict=approved`, `safe_for_agents=true`, `must_fix=[]`.
- S4 documentation: `updated`; autoridad pending, wrappers, save y rollback
  documentados; solo `sync_from_edit_world()` conserva deprecación.
- Gate S4: `completed`. C2 completado; C3 iniciado.
- S5 pre-state: tracked diff hash
  `cd9bff2e40ebc6003776becd34011f0d11628bd8`; `SceneManager` 1.598 líneas y
  74.965 bytes. Untracked S4: `edit_sync.py` SHA-256
  `0B40EA8EE09DE6A61F538FE272F63044EB36D11D4DA2552909B6882453D227A8`,
  `test_scene_edit_sync.py` SHA-256
  `445E80B55AC3BC57F8F870942F0AE15D704D0C37D2A2FC7D39D5C65A3ECE65BB`.
  Preservar todos los cambios S1-S4; benchmark S5 obligatorio antes del gate.
- S5 baseline enfocado previo: 170/170 OK. Builder funcional: servicio, port,
  wrappers y migraciones completados; focused final 206/206, Ruff/Mypy/diff y
  escaneos estáticos verdes. `SceneManager` queda en 1.202 líneas/58.933 bytes.
- S5 benchmark histórico: 4/4 funcional en todas las rondas, pero
  `transform_edit` confirmó +26,83% a +37,80% frente a S1; rondas posteriores
  también mostraron drift >10% en `static.scene_create_world` y
  `sprites.scene_save`, paths no tocados. Dedupe TDD eliminó exactamente una
  validación y lookup redundantes; artifact final SHA-256
  `1FF3E30A7CD53A28AC3CC7AAC49631B06E2453B2429577BC0E6E947EDE0E6243`.
- S5 performance causal A/B same-process, 11 rondas x 20k con orden AB/BA:
  S5 13,18971 µs/edit (MAD 0,409965) frente a algoritmo S4 equivalente
  12,45507 µs/edit (MAD 0,86495). Diferencia de medianas 5,57%; mediana pareada
  3,71% (MAD 5,34), solo 3/11 rondas >10%. La extracción no explica el drift
  histórico de 30-38%; coste causal dentro del umbral, sin nueva optimización.
- S5 validator final: `verdict=pass`, `test_contract_satisfied=true`; focused
  184/184, full 3.731 OK/8 skips, governance 75/75, Ruff/Mypy/diff/API/imports
  verdes. Benchmark 4/4 con siete muestras y A/B causal aceptado.
- S5 reviewer: `verdict=approved`, `must_fix=[]`; riesgo bajo de no conservar
  muestras A/B crudas en artifact separado, resumen reproducible en este plan.
- S5 AI audit: `verdict=approved`, `safe_for_agents=true`, `must_fix=[]`.
- S5 documentation: `updated` en arquitectura y guía técnica.
- Gate S5: `completed`.
- S6 pre-state: tracked diff hash
  `ddd4b6986bf9e57b9a3abcd55944effcfaf8f91b`; `SceneManager` 1.202 líneas y
  58.933 bytes. Untracked S5: `incremental_authoring.py` SHA-256
  `C1D33D3D173C1006D415322A88D22D61D41A3DEF7345DE28B7200ACE1F983C04`,
  `test_scene_incremental_authoring.py` SHA-256
  `1F7672236773B6A24F51D0CA5E8D228B589899E9DB71D9E829B9A0D3CB701E21`,
  artifact S5 SHA-256 ya registrado. Preservar S1-S5.
- Review inicial del plan: `changes_required`, F1-F8.
- Review revisado: `approved`, sin `must_fix`.
- S6 builder inicial: `PrefabOverrideService` y port mínimo de cuatro operaciones
  extraídos; manager y structural comparten una única instancia. Focused 192/192,
  Ruff/Mypy/diff y contratos públicos verdes.
- Gate S6 inicial rechazado por AI audit: el servicio y
  `ScenePrefabAuthoring.apply_prefab_overrides` mutaban un diccionario vivo
  devuelto por `Scene`, infringiendo el límite de mutación encapsulada.
- S6 remediation sistemática: copy-on-write profundo de `prefab_instance` y
  publicación única mediante primitivas de `Scene`; `False` o excepción deja
  la Scene exacta y evita rebuild/history. Test directo TDD 13/13, focused
  builder 196/196.
- S6 validator final: `verdict=pass`, `test_contract_satisfied=true`; directo
  13/13, focused 126/126, full 3.745 OK/8 skips, governance 75/75,
  Ruff/Mypy/diff/API/imports/arquitectura verdes.
- S6 reviewer final: `verdict=approved`, `must_fix=[]`.
- S6 AI audit final: `verdict=approved`, `safe_for_agents=true`,
  `must_fix=[]`; 250 tests dirigidos y 22 refuerzos OK.
- S6 documentation: `updated`; autoridad, port de cuatro operaciones,
  instancia compartida y límite structural documentados.
- Gate S6: `completed`. C3 completado; C4 iniciado.
- S7A pre-state: tracked diff hash
  `c0d0507059d2b519cb8eb666eb691579ff8d3a86`; `SceneManager` 1.337 líneas y
  57.625 bytes. Untracked S6: `prefab_overrides.py` SHA-256
  `8094FE1AC2CACEE378EAFD4BF1DBD53365A947C60B95DD1916CA6CE025578422`,
  `test_prefab_overrides.py` SHA-256
  `503527FF4933F9EF763B3493AE966686BA2529DFAF5B1274A119D12F51562764`.
  Preservar todos los cambios S1-S6; S7A no mueve CRUD.
- PLAN SYNC `S7A-pending-contract-owner`: la regresión amplia encontró un único
  fallo en `test_scene_manager_contracts.py` porque el test exigía que la
  anotación `pending_edit_world_sync_reason` siguiera apareciendo por accidente
  dentro del snapshot privado de `scene_manager.py`. Se autoriza migrar solo
  ese assert para inspeccionar `SceneWorkspaceEntry`/workspace, autoridad real
  desde S2-S4; no se autoriza ningún cambio de producción adicional.
- Gate S7A inicial rechazado por reviewer (`S7A-F1/F2`): el token capturaba solo
  la razón pending y perdía `dirty_before_pending_edit_world_sync`, y el commit
  dejó de emitir el diagnóstico contextual previo. Causa raíz F1: S7A usó los
  helpers estrechos de compatibilidad S4 en vez del snapshot opaco completo ya
  poseído por edit sync. Causa raíz F2: al retirar el helper del manager se
  retiró también su `log_err` sin reasignar esa responsabilidad.
- PLAN SYNC `S7A-semantic-pending-diagnostics`: remediar dentro del write set
  existente usando `SceneEditSyncCoordinator.capture_snapshot/restore_snapshot`,
  test público de pending legacy con baseline dirty distinto y posterior rechazo;
  preservar el diagnóstico con contexto/error en el coordinador. Se autoriza
  `engine.core.runtime_logging.log_err` solo como dependencia transversal de
  diagnóstico, no como autoridad de dominio; las tres dependencias de estado
  siguen siendo workspace, projection y edit sync. Corregir también el alias
  mutable del payload histórico mediante copia defensiva. No mover CRUD.
- PLAN SYNC `S7A-full-pending-assert`: la regresión amplia dejó un único assert
  que aún esperaba perder `dirty_before_pending_edit_world_sync` (`None`). Se
  autoriza en `tests/test_scene_manager_contracts.py` cambiar solo esa expectativa
  a `False`, el baseline pending real del setup que ahora debe restaurarse, y
  ajustar el nombre del test si mejora su intención. Sin cambio de producción.
- S7A remediation final: token pending completo mediante autoridad edit sync,
  diagnóstico contextual restaurado y copia defensiva del payload histórico.
  TDD directo 10/10 y regresión builder 244/244 OK.
- S7A validator final: `verdict=pass`, `test_contract_satisfied=true`; directo
  6/6, focused 87/87, regresión amplia 204/204, full 3.750 OK/8 skips en
  500,446 s, governance 75/75, EngineAPI 31/31, Ruff/Mypy/diff/API/imports/
  ciclos verdes.
- S7A reviewer final: `verdict=approved`, `must_fix=[]`, `should_fix=[]`;
  167 tests dirigidos y 111 contratos/API/governance OK.
- S7A AI audit final: `verdict=approved`, `safe_for_agents=true`,
  `must_fix=[]`; 265 tests y cinco probes de atomicidad/remediación OK.
- S7A documentation: `updated` en `docs/architecture.md` y
  `docs/TECHNICAL.md`; autoridad, token opaco, rollback semántico y CRUD
  temporal documentados.
- Gate S7A: `completed`.
- S7B pre-state: tracked diff hash
  `cd269f3678323b8ad2e0f07df6d420b420705525`; `SceneManager` 1.290 líneas y
  56.408 bytes. Untracked S7A: `serializable_mutation.py` SHA-256
  `85A94BC7E7A08909614266C1B581D1D991B45D2E18D81C5F43463F465BDD1DDD`,
  `test_serializable_mutation_coordinator.py` SHA-256
  `BDF586949A3FFB9D89D92259FCA3B39D1A93FF92F207C9522CB46D69C86CEAE8`.
  Preservar S1-S7A; crear primero una implementación cohesionada y no tomar la
  decisión exclusiva de split hasta medir en S7C.
- S7B RECON: baseline enfocado 227/227 OK. El cluster inicial contiene 28
  definiciones candidatas, 21 algoritmos no triviales y unas 330 líneas con
  statements. Dependencias reales: workspace, edit sync, mutation coordinator,
  projection, history port, prefab override port, flow policy y registry (8).
  Estado de revisión §19.2: `accepted_with_justification` provisional para
  observar la implementación cohesionada; S7C debe medir y decidir de forma
  exclusiva `keep_cohesive`, `split_component_and_entity` o
  `redesign_dependency`. Esto no es una decisión de split.
- Contrato S7B: crear `SceneSerializableAuthoring` único; manager conserva solo
  routing incremental/general, resolución de scene_ref que puede cargar desde
  persistencia y prevalidación temporal de `parent` mediante structural, pero no
  muta Scene, captura snapshots ni llama PrefabOverridePort. El servicio no
  importa ni llama structural/incremental/manager.
- Mover al servicio: CRUD multi-scene de componentes; rama no incremental de
  `apply_edit_to_world`; propiedades/grupos; replace/add/remove/enabled;
  component metadata y feature metadata; create/create_from_data incremental;
  queries con flush; operaciones serializables por ID; fallback serializable de
  estado de componente. `remove_entity(_by_id)`, reparenting/subárbol, prefab
  completo y scene-flow transaccional quedan fuera.
- Queries `find_entity_data*` deben devolver copia defensiva: hoy filtran vistas
  vivas de Scene. `set_component_metadata` y remove component deben entrar al
  coordinator. Las cuatro rutas prefab pasan al port desde el servicio.
- Creación conserva identidad incremental de Scene/World/entidades. Añadir al
  coordinator una operación concreta de commit incremental de entidad que
  valide sin reinstalar en éxito y restaure el token en fallo; no añadir flags ni
  segundo algoritmo de rollback. El historial diferencial de creación se mueve
  al servicio. Ampliar `SceneHistoryPort` solo con `record_scene_change` ya
  implementado por el coordinador actual.
- Definir `SceneSerializableEntityPort` estrecho en `contracts.py` e
  implementarlo sin duplicación, pero diferir el wiring structural directo a
  S7D. Los callbacks estructurales actuales pueden atravesar wrappers públicos
  durante S7B.
- PLAN SYNC preventivo S7B: `scene.py` no se modifica; las primitivas existentes
  cubren todas las mutaciones. Cualquier necesidad nueva exige sincronización
  previa y test de contrato protegido.
- Tests S7B: nuevo `tests/test_scene_serializable_authoring.py`; migrar solo los
  contratos implementation-coupled de prefab/snapshot/fallback en manager;
  cubrir orden flush-capture-mutate-commit-dirty-history, fallo sin historial,
  PLAY, activa/inactiva, cuatro fallbacks prefab, SceneLink, metadata, queries
  defensivas, by-ID y creación incremental. No relajar tests S1-S7A.
- S7B plan critique inicial: `changes_required` por tres ambigüedades; producción
  aún intacta. Correcciones obligatorias antes de implementar:
  1. `set_scene_flow_target` es la única excepción temporal S7B: puede seguir
     mutando flow y capturando snapshot en manager hasta S7D. Los scans deben
     allowlistear solo ese método; cero snapshots/mutaciones genéricas fuera de
     él. Gate S7, no S7B, elimina la excepción.
  2. Creación incremental captura token antes de prepare/projection/flow. Toda
     excepción de `prepare_entity`, `projection.add_entity`, materialización o
     sincronización flow restaura mediante coordinator y no registra historial.
     El commit incremental concreto valida el payload sin reinstalar en éxito,
     limpia pending mediante edit sync e instala los mismos Scene/World mediante
     workspace para recalcular `edit_world_version`; validación fallida restaura
     el token. Dirty e historial ocurren solo después.
  3. `parent` conserva validación structural sin crear dependencia inversa: los
     wrappers manager por nombre y por ID resuelven/prevalidan y luego delegan la
     mutación al servicio. El port de entidad se documenta como operación sobre
     parent ya validado para el consumidor structural de S7D. Los demás wrappers
     por ID pueden delegar al servicio; ninguno muta Scene ni captura snapshots.
