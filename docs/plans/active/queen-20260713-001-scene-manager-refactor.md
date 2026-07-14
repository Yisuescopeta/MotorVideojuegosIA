# Queen plan — SceneManager refactor

## Estado

- `task_id`: `queen-20260713-001`
- `model_route`: `critical`
- `max_cycles`: `5`
- `cycle`: `4/5`
- `current_phase`: `S7B`
- `phase_status`: `S0 completed; S1 completed; S2 completed; S3 completed; S4 completed; S5 completed; S6 completed; S7A completed; S7B in_progress`
- `task_status`: `partial`
- `next_action`: extraer SceneSerializableAuthoring cohesivo en S7B sin separar componentes/entidades antes de S7C
- `commit_authorized`: `false`
- `commit_created`: `false`
- `push_authorized`: `false`
- `base_sha`: `fded3556ed9509d5f0e06221f1655ba0f4053687`
- `final_sha`: pendiente

## Autoridades

- Especificación maestra: `C:/Users/usuario/.codex/attachments/dc349715-f71f-4972-bbc5-509f99d814b3/pasted-text.txt`
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
- tests manager/sync.
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
- S7C: pendiente.
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

## Archivos modificados

- `artifacts/refactor_scene_manager/baseline.json`
- `artifacts/refactor_scene_manager/baseline_benchmarks.json`
- `artifacts/refactor_scene_manager/s1-benchmarks.json`
- `artifacts/refactor_scene_manager/s3-benchmarks.json`
- `artifacts/refactor_scene_manager/s5-benchmarks.json`
- `docs/TECHNICAL.md`
- `docs/architecture.md`
- `docs/plans/active/queen-20260713-001-scene-manager-refactor.md`
- `engine/debug/benchmark_runner.py`
- `engine/scenes/edit_sync.py`
- `engine/scenes/scene_flow.py`
- `engine/scenes/incremental_authoring.py`
- `engine/scenes/prefab_overrides.py`
- `engine/scenes/scene_projection.py`
- `engine/scenes/scene.py`
- `engine/scenes/scene_manager.py`
- `engine/scenes/workspace_lifecycle.py`
- `tests/test_benchmark_run.py`
- `tests/test_benchmark_suite.py`
- `tests/test_editor_tools.py`
- `tests/test_scene_edit_sync.py`
- `tests/test_scene_incremental_authoring.py`
- `tests/test_prefab_overrides.py`
- `tests/test_scene_flow.py`
- `tests/test_scene_incremental_creation.py`
- `tests/test_scene_index.py`
- `tests/test_scene_manager_contracts.py`
- `tests/test_scene_mutation_rollback_contract.py`
- `tests/test_scene_persistence_contract.py`
- `tests/test_scene_projection.py`
- `tests/test_scene_workspace.py`

## Hallazgos pendientes

- Ejecutar S3-S9 sin trasladar God Object ni introducir doble autoridad.
- Retirar en S9 las asignaciones directas residuales a
  `workspace.active_scene_key` observadas por el validator, conservando wrappers
  compatibles.

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
