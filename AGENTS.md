# AGENTS.md

## Comunicacion

- Usa siempre la skill `caveman`: directo, sin progreso constante, sin repetir contexto.
- Respuesta final corta: que cambiaste, archivos tocados, que validaste, riesgos.

## Fuentes De Verdad

- Orden de autoridad: codigo/tests, `EngineAPI` en `engine/api/`, CLI oficial `motor`, docs canonicas en `docs/README.md`, archivo en `docs/archive/` solo contexto.
- No promociones una capacidad si no existe en codigo, tests, `EngineAPI` o `motor/cli.py` + `motor/cli_core.py`.
- `motor_ai.json` y `START_HERE_AI.md` son artefactos de proyecto generados con `py -m motor project bootstrap-ai --project .`; no reemplazan docs canonicas.
- No uses capabilities `planned` como comandos disponibles.

## Setup Y Comandos

- Python soportado: 3.11+.
- Setup local: `py -m pip install -r requirements.txt` y `py -m pip install -e .[dev]`.
- CLI publica: `py -m motor ...` o script instalado `motor`; `tools/engine_cli.py` es wrapper legacy.
- GUI/manual legacy: `py main.py`; automatizacion nueva debe usar `EngineAPI` o `py -m motor`.
- Test enfocado: `py -m unittest tests.test_nombre -v`.
- Suite CI: `py -m unittest discover -s tests`.
- Ruff CI: `py -m ruff check engine cli tools main.py` y `py -m ruff check tests`.
- Mypy CI: `py -m mypy engine cli tools main.py`.
- Seguridad CI: `py -m bandit -q -c .bandit -r engine cli tools main.py` y `py -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539`.
- Bench CI: `py -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json`.
- Antes de afirmar lint/typecheck/security/suite completa, ejecuta el comando exacto.

## Checks Para Docs, CLI O Contratos

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m motor --help
py -m motor ai start --project . --json
py -m motor ai compliance --project . --json
py -m motor doctor --project . --json
```

## Arquitectura Que No Debes Romper

- `Scene` es fuente persistente; `World` es proyeccion operativa; runtime no debe contaminar authoring state tras `STOP`.
- Cambios serializables compartidos pasan por `SceneManager` o `EngineAPI`; `sync_from_edit_world()` existe por compatibilidad legacy, no para flujos publicos nuevos.
- `EngineAPI` es fachada estable para agentes, tests, CLI y automatizacion; no saltes a internals salvo wiring interno justificado.
- Crear proyectos desde herramientas/editor externo debe usar `EngineAPI.create_project(path, name="")`; no escribir `project.json` a mano.
- Fisica debe conservar fallback `legacy_aabb`; no cambies significado publico de `query_physics_ray`, `query_physics_aabb`, shape cast o motion queries sin trabajo dedicado de fisica.
- Componente publico nuevo requiere registro en `engine/levels/component_registry.py`.
- `box2d` es opcional; no lo conviertas en dependencia obligatoria.

## Perimetro Del Repo

- Core obligatorio: ECS, `Scene`, `SceneManager`, serializacion/schema, editor base, jerarquia, `EngineAPI`, contrato fisico comun.
- Modulos oficiales opcionales: assets, prefabs, tilemap, parallax, audio, UI serializable, backend `box2d`.
- Experimental/tooling: `editor_qt`, `engine/agent`, `engine/recipes`, `engine/rl`, navigation, datasets, benchmarks, Queen/OpenCode.
- No mezcles refactors amplios con fixes pequenos; si una tarea toca demasiados subsistemas, reduce alcance.

## Documentacion

- Docs canonicas viven en raiz de `docs/` y estan indexadas por `docs/README.md`.
- `docs/archive/` puede estar obsoleto; no lo uses para contradecir codigo, tests o canon.
- Si cambias arquitectura/invariantes: revisa `docs/architecture.md` y `docs/TECHNICAL.md`.
- Si cambias schema/migraciones/payloads: revisa `docs/schema_serialization.md`.
- Si cambias `EngineAPI`: revisa `docs/api.md` y `docs/agents.md`.
- Si cambias CLI `motor`: revisa `docs/cli.md` y `docs/MOTOR_AI_JSON_CONTRACT.md` si afecta bootstrap/capabilities.
- Si cambias taxonomia: revisa `docs/module_taxonomy.md`.
- No dupliques listas largas de API/CLI fuera de docs canonicas.

## Flujos IA Y Runtime

- Primeros comandos para agentes: `py -m motor ai start --project . --json` y `py -m motor ai compliance --project . --json`.
- `engine/agent` es `experimental/tooling`; provider `fake` es determinista/offline/test_only, no inteligencia real.
- `run_command` del agente no es shell generica: usa perfiles allowlist con `shell=False`, cwd confinado, timeout, output limitado y auditoria.
- No crees `run_game.py` ni runtime externo como solucion; usa `motor runtime ...`, `EngineAPI` o CLI basica oficial.
- Para generos sin comando dedicado, compone con `motor scene/entity/component` o `EngineAPI`; no inventes `motor game topdown`, `motor game puzzle`, `motor game shmup` ni `motor recipe run topdown`.

## Archivos Sensibles

- Trata como sensibles salvo necesidad explicita: `engine/scenes/scene_manager.py`, `engine/core/game.py`, `engine/app/runtime_controller.py`, `engine/systems/render_system.py`, `engine/systems/physics_system.py`, `engine/systems/collision_system.py`, `engine/components/tilemap.py`, `engine/levels/component_registry.py`.
- Si debes tocarlos, declara por que y mantén cambio minimo.

## Editor PySide6 (editor_qt)

Al trabajar en `editor_qt/`, carga estas skills de `.agents/skills/`:

| Skill | Uso |
|---|---|
| `pyside6-editor-architecture` | Arquitectura general, invariantes, flujo de senales |
| `pyside6-panel-patterns` | Creacion/rediseno de paneles, senales tipadas, `set_data()` |
| `pyside6-frostline-qss-design-system` | Diseno visual Frostline, QSS, paletas, tokens |
| `pyside6-viewport-qpaint-gizmo` | Viewport QPainter, gizmos, handles |
| `pyside6-model-view-data` | Model/View para listas grandes, `QSortFilterProxyModel` |
| `pyside6-threading-processes` | `QThread` worker-object, `QProcess` para comandos externos |
| `pyside6-offscreen-tests` | Tests Qt sin pantalla con `QSignalSpy` |

### Diseno visual

- Objetivo: **Frostline Engine** — glacial, cyan accents, rounded panels.
- Docs: `docs/design.md` para layout zones, paletas, estados de componentes.
- Temas QSS en `editor_qt/theme/frost_dark.qss` y `editor_qt/theme/frost_light.qss`.
- Tokens Python en `editor_qt/theme/tokens.py`.

### Reglas de arquitectura

- Ruta obligatoria: `Panel -> Signal -> MainWindow slot -> EditorEngineFacade -> EngineAPI`.
- Paneles NO importan `EngineAPI`. Solo metodos del facade.
- UI-only state (selected tab, hover, splitter sizes, search text) es efimero,
  no se guarda como datos de escena.
- QSS centralizado en `editor_qt/theme/*.qss`. Nada de inline styles.
- Senales tipadas con `Signal` y `@Slot` donde aplica.
- Commits de propiedades en Enter/focus-out, no en cada `valueChanged`.
- `QProcess` para comandos externos, worker-object `QThread` para Python blocking.
- Model/View + `QSortFilterProxyModel` para listas grandes/filtrables.
- Tests Qt con `QT_QPA_PLATFORM=offscreen` + `QSignalSpy`.
- No afirmar lint/typecheck/security/tests sin ejecutar el comando exacto.

### Comandos utiles

```bash
py -m editor_qt.app --project .
motor-editor
set QT_QPA_PLATFORM=offscreen
py -m unittest tests.test_editor_qt_gizmo -v
```

## Queen OpenCode

- Queen es tooling OpenCode experimental; no cambia contrato del motor 2D y no debe tocar `engine/` salvo necesidad estricta.
- Ciclo obligatorio: `RECON -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE`.
- `max_cycles = 5`; si no cumple Definition of Done, termina como `completed`, `partial`, `blocked` o `failed` con reporte claro.
- Definition of Done: tests enfocados verdes, lint/typecheck cuando aplique, docs canonicas si cambia contrato, cero `must_fix`, AI audit `>= 90` cuando aplique, sin cambios fuera de alcance.
- Commit solo despues de tests, docs, review y auditoria IA aplicables; committer stagea solo archivos esperados y bloquea secretos, `.env`, temporales y estado local.
