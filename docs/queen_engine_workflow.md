# Queen Engine Workflow

Authority: operational-workflow

Documento operativo para Queen/OpenCode. No es documentacion canonica del
producto ni cambia el contrato del motor.

Queen existe para programar, refactorizar, endurecer y mantener el motor
OpenGame. No crea juegos como objetivo final. Las escenas o juegos generados
solo valen como fixture, demo minima, smoke test o validacion del motor.

## Ciclo

```text
RECON -> TEST CONTRACT -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE
```

`TEST CONTRACT` ocurre antes de implementar. `validator` hace la validacion
final despues de documentar.

## Smoke tests de permisos Queen/OpenCode

Para smoke tests verificables por Git, no usar `.motor/queen_state` como
sandbox. Ese arbol puede estar ignorado por Git y no sirve como evidencia de
diff versionable.

Si un subagente devuelve `<task_result></task_result>` vacio, no asumir fallo de
permisos. Revisar primero si el proveedor/modelo del subagente fallo. Si el
harness no propaga el error real, Queen debe bloquear con
`missing_subagent_result`. Para smoke tests de permisos, usar un proveedor/modelo
con saldo y salida visible confirmada.

Durante smoke tests de permisos, todos los agentes del flujo Queen principal
deben usar un proveedor operativo. Si `opencode.json` y el frontmatter del
agente difieren, hay riesgo de drift de modelo efectivo. Mantener el `model:`
del frontmatter sincronizado con `opencode.json`. Si aparece
`<task_result></task_result>`, revisar primero proveedor/modelo efectivo y drift
de frontmatter antes de diagnosticar permisos.

Para validar permisos de escritura de subagentes, usar este fixture trackeado:

```text
tests/fixtures/queen_permission_smoke/permission_sandbox.md
```

La smoke test debe registrar:

- lectura antes y despues del archivo;
- `git diff --name-only -- tests/fixtures/queen_permission_smoke/permission_sandbox.md`;
- `git diff -- tests/fixtures/queen_permission_smoke/permission_sandbox.md`;
- `git status --short -- tests/fixtures/queen_permission_smoke/permission_sandbox.md`.

No usar solo `git diff --name-only` para detectar archivos nuevos sin trackear.
Si la prueba valida creacion de archivos nuevos, usar tambien:

```bash
git status --short --untracked-files=all -- <ruta>
```

## Matriz de validacion

Si un test recomendado no existe, Queen debe localizar el equivalente real con
`rg`, docs o config. Si no hay equivalente, debe proponer un test minimo antes
de implementar.

| Subsistema | Tests minimos recomendados | Regresiones recomendadas | Docs afectadas | Smoke/manual |
|---|---|---|---|---|
| docs-only | `tests.test_repository_governance` | `tests.test_start_here_ai_coherence` | Doc editado, `docs/agents.md`, `AGENTS.md` si cambia flujo | Revisar enlaces y autoridad del doc |
| CLI | `tests.test_motor_cli_contract` | `tests.test_parser_registry_alignment`, `tests.test_motor_registry_consistency` | `docs/cli.md`, `docs/agents.md` | `py -m motor --help`, comando nuevo con `--json` |
| EngineAPI | `tests.test_engine_api_public_contract` | `tests.test_motor_interface_coherence`, `tests.test_official_contract_regression` | `docs/api.md`, `docs/agents.md` | Script minimo con `EngineAPI` y `shutdown()` |
| Scene/SceneManager/authoring | `tests.test_scene_manager_contracts`, `tests.test_scene_workspace` | `tests.test_scene_save_integrity`, `tests.test_api_authoring_workspace` | `docs/architecture.md`, `docs/TECHNICAL.md` | `EDIT -> PLAY -> STOP` headless |
| schema/serialization/migrations | `tests.test_schema_validation`, `tests.test_component_serialization_contracts` | `tests.test_official_contract_regression`, `tests.test_scene_storage` | `docs/schema_serialization.md`, `docs/TECHNICAL.md` | Load/save/load fixture legacy y v2 |
| physics/collision | `tests.test_physics_backend`, `tests.test_collision_system` | `tests.test_physics_backend_contract`, `tests.test_physics_body_test_motion`, `tests.test_physics_move_and_slide` | `docs/architecture.md`, `docs/TECHNICAL.md` | Headless runtime step con collider |
| render | `tests.test_render_graph`, `tests.test_render_pipeline_foundation` | `tests.test_render_safety`, `tests.test_render_sprite_animator` | `docs/TECHNICAL.md` | Captura o smoke visual si cambia orden visual |
| editor/runtime | `tests.test_runtime_controller`, `tests.test_runtime_loop_foundation` | `tests.test_editor_scene_sync`, `tests.test_runtime_step_script_behaviour` | `docs/architecture.md`, `docs/TECHNICAL.md`, `docs/agents.md` | Abrir editor si cambia UI visual |
| export pipeline | `tests.test_export_cli_contract`, `tests.test_export_content_pack` | `tests.test_export_runtime_playability`, `tests.test_export_presets` | `docs/export_pipeline.md`, `docs/build_artifacts.md`, `docs/agents.md` | `py -m motor export ... --json` cuando aplique |
| components/component registry | `tests.test_docs_component_registry_sync`, `tests.test_component_serialization_contracts` | `tests.test_official_contract_regression`, `tests.test_motor_interface_coherence` | `docs/TECHNICAL.md`, `docs/schema_serialization.md` | Crear entidad con componente via API/CLI |
| experimental/tooling | `tests.test_queen_agent_contract`, tests especificos del tooling | `tests.test_repository_governance`, `tests.test_start_here_ai_coherence` | Doc operativo del tooling, `docs/module_taxonomy.md` si cambia clasificacion | Smoke del comando o workflow sin tocar core |

## TEST CONTRACT minimo

Queen debe exigir a `test-strategist`:

- comportamiento actual protegido;
- comportamiento nuevo esperado;
- tests existentes que son autoridad;
- tests nuevos o modificados necesarios;
- tests que no deben relajarse;
- comandos minimos enfocados;
- regresiones recomendadas;
- criterios de aceptacion verificables;
- que hacer si no se pueden ejecutar tests.

Si el contrato es `insufficient`, no se implementa. Si es `not_applicable`, debe
ser docs-only trivial y declarar razon.
