# Queen Execution Plan: ajuste plan especializado ejecucion

Status: active
Authority: operational-plan
Task ID: queen-20260630-001
Created at: 2026-06-30T23:40:39.4184318+02:00
Updated at: 2026-07-01T01:07:29.8210104+02:00
Mode: long-task-plan

## Objective
Ejecutar el refactor incremental con control operativo: baseline reproducible, cambios Python pequeños, tests enfocados y Rust solo tras medición.

## Non-goals
- No iniciar Rust/PyO3 sin baseline, tests de equivalencia y gate de speedup.
- No tocar `EngineAPI`, `Scene`, `SceneManager`, schema, editor, `legacy_aabb` ni contrato de `query_physics_*` en la fase inicial.
- No crear CI nuevo desde cero; el repo ya tiene `.github/workflows/ci.yml`.

## Constraints
- Los planes en `docs/plans/` son artefactos operativos, por debajo de código, tests, `EngineAPI`, CLI `motor` y docs canónicas.
- Cada cambio debe ser pequeño, reversible y validado con tests enfocados.
- Cambios públicos de API, CLI, schema o arquitectura requieren replanificar y actualizar docs canónicas antes de implementar.
- Benchmark local aceptado en `artifacts/benchmarks/`; esos JSON están ignorados por git.

## Current phase
- Name: Phase 3 - SpatialHash2D equivalence gate
- Status: done
- Allowed files: `tests/test_spatial_hash.py`, benchmark/tooling tests first; optional experimental native files only after separate gate approval.
- Forbidden files: `engine/api/**`, `engine/scenes/scene_manager.py`, `engine/scenes/scene.py`, `engine/serialization/**`, `engine/editor/**`, `engine/physics/**`, `motor/**`, `docs/architecture.md`, `docs/TECHNICAL.md`, `docs/api.md`, `docs/cli.md`, `docs/schema_serialization.md`
- Acceptance checks: deterministic query/ray/oversized-entry tests pass; native path remains optional and disabled.
- Docs affected: operational plan and `docs/refactor/` phase result.
- Risks: Rust deferred if Windows install, CI, or FFI overhead becomes costly.

## Phases

### Phase 1 — Baseline + ECS query cache micro-PR
Status: done
Goal: Seal baseline and replace global component-query cache invalidation with selective invalidation.
Allowed files: operational plan, `engine/ecs/world.py`, `tests/test_ecs_indices.py`, benchmark artifact.
Forbidden files: public API, scene/schema/editor/physics/CLI/canonical docs.
Acceptance checks: focused ECS + contract tests pass; doctor passes; quick benchmark baseline written.
Docs affected: operational plan only.
Risks: private cache metrics are internal and must not become public API.

### Phase 2 — World.clone measurement only
Status: done
Goal: Measure `World.clone()` through existing `play_mode_clone_stress`; optimize only if safety invariants stay intact.
Allowed files: benchmark/tooling tests first; `engine/ecs/world.py` only if measurable safe change exists.
Forbidden files: serialization schema and scene manager unless replan approved.
Acceptance checks: before/after benchmark, `tests.test_ecs_clone`, EDIT/PLAY contract tests.
Docs affected: operational plan only unless public behavior changes.
Risks: clone correctness is more important than speed.

### Phase 3 — SpatialHash2D equivalence gate
Status: done
Goal: Strengthen Python equivalence tests before any native experiment.
Allowed files: `tests/test_spatial_hash.py`, optional experimental native files only after gate approval.
Forbidden files: physics public query semantics and `legacy_aabb` fallback.
Acceptance checks: deterministic query/ray/oversized-entry tests pass; native path remains optional.
Docs affected: operational plan first; canonical docs only if public behavior changes.
Risks: Rust deferred if Windows install, CI, or FFI overhead becomes costly.

## Decisions
- 2026-06-30: Fase inicial limitada a baseline y ECS query cache. Reason: plan corregido prioriza medición antes de Rust. Impact: no cambios públicos.
- 2026-06-30: CI existente se conserva. Reason: `.github/workflows/ci.yml` ya ejecuta tests, benchmark suite, ruff, mypy, bandit y pip-audit. Impact: fase no añade workflows.
- 2026-07-01: Fase 2 queda como measurement-only. Reason: `play_mode_clone_stress` mide `World.clone`, pero no hay evidencia suficiente para un cambio seguro. Impact: no se toca `World.clone`.
- 2026-07-01: Se documenta ADR-0001 para invalidacion selectiva del query cache ECS. Reason: `engine/ecs/world.py` es modulo protegido y hubo cambio interno ECS. Impact: decision trazable y rollback claro.

## Progress log
- 2026-06-30: Plan normalizado a formato Queen operativo. Baseline y micro-PR ECS en curso.
- 2026-06-30: Baseline quick benchmark creado en `artifacts/benchmarks/baseline_20260630.json`; status `passed`, 4/4 scenarios, 0 warnings.
- 2026-06-30: ECS query cache micro-PR implementado. `World` conserva caches no afectados por el tipo de componente modificado y mantiene contadores internos de hits/misses/invalidations.
- 2026-06-30: Validación micro-PR: `tests.test_ecs_indices tests.test_ecs_clone` OK (14 tests), `tests.test_ecs_clone tests.test_spatial_hash tests.test_benchmark_suite tests.test_world_versions` OK (29 tests), contract suite OK (91 tests), `ruff` OK, `mypy engine/ecs/world.py` OK, `motor doctor` OK, benchmark post-cambio `artifacts/benchmarks/query_cache_20260630.json` OK (4/4, 0 warnings).
- 2026-06-30: Full suite baseline ejecutada: `py -m unittest discover -s tests` = 3461 tests, 12 failures, 8 skipped. Fallos quedan fuera del cambio ECS: editor interaction selection/gizmo tests, RPG Android animation/lives/render-order tests.
- 2026-07-01: Rama segura creada: `codex/queen-safe-continuation` desde `origin/main` en `b18fb1894552ef50ea3966a88276051054286585`.
- 2026-07-01: Documentacion obligatoria creada en `docs/refactor/`: baseline environment/tests/benchmarks, branch audit, protected modules, phase 1 result, phase 2 result y ADR-0001.
- 2026-07-01: Validacion full suite actual: `py -m pytest` = 3439 passed, 16 failed, 8 skipped; `py -m unittest discover -s tests` = 3463 tests, 16 failures, 8 skipped. Fallos clasificados en `docs/refactor/baseline_tests.md`.
- 2026-07-01: Validacion enfocada ECS/clone/scene/benchmarks: `py -m unittest tests.test_ecs_indices tests.test_ecs_clone tests.test_scene_workspace tests.test_core_regression_matrix tests.test_benchmark_run tests.test_benchmark_suite` = 53 tests OK.
- 2026-07-01: Benchmark dedicado `play_mode_clone_stress` guardado en `artifacts/benchmarks/world_clone_before_20260701.json`: `world_clone.ms=519.396200`, `edit_to_play.ms=507.614900`, `play_to_edit.ms=850.159900`. No se aplica optimizacion de `World.clone`.
- 2026-07-01: Revalidacion final enfocada OK: 53 tests OK, `ruff` OK, `mypy engine/ecs/world.py` OK, `motor doctor` OK.
- 2026-07-01: Phase 3 SpatialHash2D equivalence gate implementado Python-only. Se amplian tests para `reset`, ray candidates horizontales/verticales/diagonales/negativos/distancia cero y oversized entries. No se toca runtime ni Rust.
- 2026-07-01: Benchmark aislado guardado en `artifacts/benchmarks/spatial_hash_python_20260701.json`: `insert.ms=13.934000`, `query.ms=8.396900`, `query_into.ms=9.480800`, `ray_candidates.ms=8.947400`, checksum estable `4089648442599396781`.
- 2026-07-01: Validacion Phase 3 OK: `tests.test_spatial_hash tests.test_physics_system` = 34 tests OK; `tests.test_spatial_hash_benchmark tests.test_benchmark_run tests.test_benchmark_suite` = 23 tests OK; `ruff` OK; `motor doctor` OK.

## Final checks
- Focused tests: pass
- Regression tests: partial; contract/regression targeted pass, full suite has 16 baseline failures
- Lint: pass
- Typecheck: not run for phase 3; no typed runtime files changed
- Motor doctor: pass
- Review: not_requested
- AI audit: not_applicable

## Source Plan

# Plan Tecnico de Refactorizacion Incremental — OpenGame Engine

**Motor 2D experimental en Python: auditoria, plan Python-Rust/PyO3, benchmarks y roadmap por fases**

---

**Proyecto analizado:** [OpenGame](https://github.com/Yisuescopeta/OpenGame.git) — Yisuescopeta/OpenGame
**Fecha:** 2026-06-30
**Metodologia:** Auditoria multi-agente en 12 dimensiones (arquitectura, hotspots, ECS, fisica, render, sistemas auxiliares, PyO3, compatibilidad IA, testing, roadmap, riesgos, recomendacion ejecutiva)
**Equipo de analisis:** 12 subagentes especializados + 8 writers tecnicos

---
> **Versión corregida:** esta edición ajusta el plan para reducir riesgo operativo. El nuevo orden recomendado es: primero tests/benchmarks/CI, después optimizaciones Python seguras, y solo entonces Rust/PyO3 para hotspots medidos. Se pospone Rapier2D, PGS solver, IslandBuilder y cambios profundos de ECS hasta que existan benchmarks y tests suficientes.

---

## Resumen Ejecutivo

**Recomendación corregida:** Refactorización incremental con Rust restringido a hotspots medidos, pero **no iniciar la migración Rust como primera acción**. La primera acción debe ser estabilizar la línea base: tests verdes, benchmarks reproducibles, CI mínimo y documentación del entorno. Después conviene aplicar optimizaciones Python de bajo riesgo —especialmente invalidación selectiva del query cache ECS y reducción de allocaciones por frame— y solo entonces introducir el primer módulo Rust mediante PyO3.

La estrategia corregida es:

```text
Fase 0: estabilizar tests, benchmarks y CI.
Fase 1: optimizaciones Python seguras y reversibles.
Fase 2: primer módulo Rust pequeño con fallback Python.
Fase 3: ECS/física/render según mediciones reales.
```

### Diagnóstico del Motor

OpenGame es un motor ECS 2D escrito en Python que comprende **588 archivos fuente**, **51 componentes**, **28 sistemas** y acumula **512 commits** con **2 contribuyentes activos**. El repositorio contiene **98 branches abiertos**, señal de desarrollo paralelo sin consolidación. El motor soporta dos backends de física: un sistema `legacy_aabb` de **69 KB de código Python puro** y una integración opcional sobre Box2D. Esta dualidad de backends representa una deuda técnica activa: el motor contiene dos implementaciones de física con diferentes semánticas de componentes y rutas de ejecución, lo que complica cualquier migración masiva.

La deuda técnica crítica se concentra en tres áreas interdependientes. Primera: la invalidación del caché de queries en el ECS es global y no granular. Cada operación de escritura en un componente fuerza la reconstrucción completa de todos los cachés de queries, lo que convierte al ECS en un cuello de botella progresivo a medida que crece la cantidad de entidades. Segunda: `World.clone()` se implementa mediante serialización JSON, con tiempos medidos de **200 ms a 2 segundos** para escenarios de 10 000 entidades. Este mecanismo afecta directamente el guardado de estado, el rollback de simulaciones y cualquier operación que requiera copiar el mundo ECS. Tercera: el solver PGS (Projected Gauss-Seidel) de contactos, el constructor de islas (`IslandBuilder` con recorrido BFS), y el `SpatialHash2D` basado en diccionarios Python, son rutas enteramente interpretadas que ejecutan en bucles calientes durante cada frame de simulación.

### Hotspots de Rendimiento

Los cuatro hotspots principales identificados, ordenados por impacto potencial de optimización, son:

| Hotspot | Ubicación estimada | Naturaleza del cuello de botella | Corrección recomendada |
|---|---|---|---|
| `get_entities_with()` caché miss | Sistema de queries ECS | Invalidación global de caché | **Primero en Python**: invalidación selectiva, métricas hit/miss y reducción de listas temporales |
| `World.clone()` | Serialización ECS completa | JSON como mecanismo de deep-copy | **Primero en Python**: benchmark dedicado, fast clone seguro y tests EDIT/PLAY |
| `SpatialHash2D` | Broad-phase de física | Dict/set lookups en Python puro | **Primer candidato Rust** solo tras benchmarks y tests de equivalencia |
| Solver PGS + `IslandBuilder` BFS | Narrow-phase + resolución de contactos | Bucles Python sobre contactos | **No tocar al inicio**; migrar solo si sigue siendo hotspot tras mejorar broadphase/queries |

Estos cuatro puntos concentran gran parte del riesgo de rendimiento, pero no todos exigen Rust. La corrección principal del plan es separar **problemas algorítmicos solucionables en Python** de **bucles numéricos que sí justifican Rust**.

### Estrategia de Migración Corregida

La estrategia propuesta sigue siendo híbrida. Python permanece como lenguaje del framework: editor visual, API pública (`EngineAPI`), serialización de escenas, interfaz de línea de comandos y módulos de IA no requieren migración. Rust se introduce exclusivamente como backend acelerado para hotspots medidos, expuesto al runtime Python vía PyO3 y empaquetado con maturin. Cada módulo migrado incluye un **fallback Python obligatorio**: si el módulo Rust no carga, el motor continúa operando con la implementación Python original.

El orden corregido no empieza migrando `SpatialHash2D` mañana. Empieza creando una base fiable:

1. **Fase 0 — Estabilización:** resolver tests fallando, fijar baseline de benchmarks, documentar comandos reproducibles y configurar CI Python mínimo.
2. **Fase 1 — Optimización Python segura:** invalidación selectiva del query cache, medición de `World.clone()`, reducción de allocaciones por frame y eliminación de reconstrucciones innecesarias.
3. **Fase 2 — Primer módulo Rust:** `SpatialHash2D` con PyO3, fallback Python y tests de equivalencia.
4. **Fase 3 — Módulos nativos posteriores:** física, render prep, partículas, pathfinding o ECS storage solo si el profiling demuestra impacto real.

### Riesgos y Métricas de Éxito

El principal riesgo operativo es la fragilidad del ecosistema de tests. Actualmente el proyecto reporta **3 tests fallando (F)** y **3 tests con errores (E)**, con solo 2 contribuyentes para mantener estabilidad durante el refactor. Migrar código a Rust con tests rotos en la línea base introduce ambigüedad: un test que falla tras la migración puede deberse a la migración misma o a un fallo preexistente.

Por tanto, la métrica de éxito corregida es:

| Fase | Criterio de éxito |
|---|---|
| Fase 0 | tests base verdes o fallos documentados y aislados; benchmarks reproducibles; CI mínimo operativo |
| Fase 1 | mejoras Python medibles sin cambios de API pública; 0 regresiones en escenas/EngineAPI |
| Fase 2 | primer módulo Rust con fallback Python, tests de equivalencia y speedup ≥2x frente a Python optimizado |
| Fase 3 | cada módulo nuevo justificado por profiling y reversible mediante fallback |

La infraestructura técnica de soporte — PyO3 + maturin + fallback Python + CI multiplataforma — sigue siendo válida, pero no debe bloquear la fase inicial. Primero se mide y estabiliza. Después se optimiza en Python. Solo entonces se cruza la frontera Rust.

---

# 1. Diagnostico del Proyecto

El motor OpenGame 2D es un proyecto Python de aproximadamente 181,384 lineas distribuidas en 588 archivos, de los cuales 297 pertenecen al directorio `engine/` que contiene el nucleo del sistema. El repositorio cuenta con 51 componentes registrados, 28 sistemas de runtime organizados por fases, y una arquitectura de Entity-Component-System (ECS, sistema de entidad-componente) que soporta tanto ejecucion grafica como headless. Solo 2 contribuyentes mantienen el codigo, con 98 ramas activas que reflejan un alto grado de experimentacion paralela sin consolidacion. Esta configuracion humana y organizativa condiciona cada decision tecnica: el riesgo de divergencia entre ramas amplifica el costo de cualquier refactor que no este rigurosamente justificado con datos del propio codigo.

Este capitulo establece el diagnostico completo sobre el que se construye el plan de refactorizacion. Se examina la arquitectura actual, se inventarian los modulos por nivel de criticidad, se cuantifica la deuda tecnica con referencias concretas a archivos y lineas, y se identifican los modulos cuya modificacion conlleva riesgo de ruptura total del contrato publico del motor.

## 1.1 Arquitectura Actual

### 1.1.1 Mapa de Arquitectura: Cuatro Capas con Scene como Fuente de Verdad

El motor se organiza en cuatro capas principales, desde la infraestructura inferior hasta los puntos de entrada de usuario. La relacion entre estas capas no es estrictamente jerarquica: existen referencias ascendentes a traves de puertos internos y contratos de wiring que evitan dependencias circulares directas.

```
+------------------------+  +------------------------+
|      CLI / Scripts     |  |   Landing Page (Astro) |
|   py -m motor [...]    |  |   GitHub Pages         |
+------------------------+  +------------------------+
            |                          |
            v                          v
+-----------------------------------------------------+
|           EngineAPI — Fachada publica estable         |
|   engine/api/engine_api.py + 10 submodulos _*_api    |
|   (_agent, _authoring, _assets, _debug, _editor,     |
|    _export, _runtime, _scene_workspace, _ui)         |
+-----------------------------------------------------+
            |                    ^
            v                    |
+-----------------------------------------------------+
|        Controllers / App Layer                        |
|   RuntimeController, SceneManager,                    |
|   SceneWorkflowController, DebugToolsController,      |
|   EditorInteractionCtrl, ProjectWorkspaceCtrl         |
+-----------------------------------------------------+
            |                    ^
            v                    |
+-----------------------------------------------------+
|        Core del Motor (engine/core/)                  |
|   Game (grafico)          HeadlessGame (CLI/tests)    |
|   RuntimeLoopState        EngineState (EDIT/PLAY)     |
|   TimeManager             RuntimeTickPlan             |
|   RuntimeControllerContext (contratos de wiring)      |
+-----------------------------------------------------+
            |                    ^
            v                    |
+-----------------------------------------------------+
|        Sistemas Runtime (engine/systems/)             |
|   28 sistemas organizados en 4 fases:               |
|   FIXED_UPDATE: Physics, Collision, CharacterCtrl,   |
|                 PlayerCtrl, ScriptBehaviour,          |
|                 Gameplay2DSemantic, Area2D, RayCast,  |
|                 Navigation, MovingPlatform, EnemyPatrol|
|   UPDATE:       Animation, Input, MobileControls      |
|   POST_UPDATE:  Timer, Tween, Audio, Particles,       |
|                 VisibleOnScreen, Parallax, UI,        |
|                 ResourcePreloader, SceneTransition    |
|   RENDER:       Render, UIRender, Line2D, Light2D,    |
|                 Selection, UIFocus, GPU Particles     |
+-----------------------------------------------------+
            |                    ^
            v                    |
+-----------------------------------------------------+
|        ECS Base (engine/ecs/)                         |
|   World (contenedor + indices)   Entity (contenedor)  |
|   Component (datos)              GroupRegistry        |
+-----------------------------------------------------+
            |                    ^
            v                    |
+-----------------------------------------------------+
|        Componentes (engine/components/)               |
|   51 componentes registrados en 10 familias:         |
|   Core espacial, Render 2D, Fisica, Gameplay, UI,     |
|   Escena, Animacion, Input/Audio, Navegacion,         |
|   Particulas                                          |
+-----------------------------------------------------+
            |                    ^
            v                    |
+-----------------------------------------------------+
|        Infraestructura Inferior                       |
|   Physics: legacy_aabb (+ box2d opt-in)              |
|   Rendering: Pipeline render, Tilemap renderer        |
|   Audio: NullAudioBackend, AudioRuntime               |
|   Assets: AssetDatabase (SQLite), Prefabs             |
|   Serialization: Schema v2, Migraciones v1->v2        |
|   Events: EventBus, RuleSystem, SignalRuntime         |
|   Editor: EditorShell, UI core, Inspector, Hierarchy  |
|   Export: Content pack, Presets, Multi-plataforma     |
+-----------------------------------------------------+
```

La capa superior esta formada por los puntos de entrada: la interfaz de linea de comandos (`py -m motor`), el lanzador grafico (`main.py`), el runtime headless para tests y automatizacion, y el runtime exportado para juegos empaquetados. Todos estos puntos de entrada convergen en `EngineAPI`, que actua como fachada publica unica para agentes de IA, tests, CLI y scripts de automatizacion. El principio arquitectonico central, documentado en `docs/architecture.md`, establece que el motor no debe ocultar estado funcional en la interfaz grafica: la fuente de verdad persistente vive exclusivamente en datos serializables.

`Scene` es esa fuente de verdad. Conserva el contenido editable y persistible — entidades, componentes serializables, reglas, `feature_metadata` y referencias de prefab — en formato JSON con `schema_version = 2`. `World`, en contraste, es una proyeccion operativa que contiene entidades activas para el editor y el runtime, pero no es un formato de persistencia. `SceneManager` coordina el workspace editable y el ciclo `EDIT -> PLAY -> STOP`, manteniendo `edit_world` como proyeccion de authoring y `runtime_world` como clon temporal para la ejecucion. Esta separacion es una invariante arquitectonica: las mutaciones de runtime no se guardan como authoring, y un ciclo completo de guardado y carga conserva entidades, componentes, jerarquia y `feature_metadata`.

### 1.1.2 Ciclo EDIT-PLAY-STOP: Clonacion de Runtime World Temporal

La transicion entre modos de edicion y ejecucion constituye uno de los mecanismos mas criticos del motor. Cuando el usuario activa el modo PLAY (mediante la tecla ESPACIO o una llamada programatica a `EngineAPI.play()`), `SceneManager` clona el `edit_world` actual en un `runtime_world` temporal mediante `World.clone()`. Este metodo, definido en `engine/ecs/world.py` a partir de la linea 430, replica cada entidad iterando sobre `iter_all_entities()`, clonando componentes via `Component.clone()` (que a su vez usa `to_dict()` y `from_dict()`), y preservando jerarquia, grupos, metadatos serializables y relaciones de prefab. La clonacion usa `clone_json_value()` para valores mutables que pasan al runtime, asegurando que el `World` resultante no comparta contenedores mutables con `Scene.data`.

El flujo de datos es unidireccional desde `Scene` hacia el runtime:

```
Scene (JSON v2, fuente de verdad persistente)
   |
   |-- Scene.create_world() --> [edit_world] proyeccion editable
   |                               |
   |<-- serialize() -------------+ |
   |                             | |
   v                             v v
[SceneManager] --- PLAY ----> [runtime_world] clon temporal
                                 |
                                 +-- FIXED_UPDATE (1/60s)
                                 +-- UPDATE (animacion)
                                 +-- POST_UPDATE (UI/deferred)
                                 +-- RENDER (grafico)
                                 |
                               STOP
                                 |
                                 v
                           [edit_world restaurado]
```

Cuando el usuario detiene la ejecucion (tecla ESC o `EngineAPI.stop()`), el motor limpia el estado transitorio del loop, ejecuta los hooks `on_stop` y restaura `edit_world`. Las mutaciones realizadas durante PLAY — posiciones de entidades, estados de animacion, eventos emitidos — no contaminan el estado editable ni se persisten en `Scene` a menos que el usuario ejecute una operacion de guardado explicita desde el modo EDIT. Este diseno evita que cambios transitorios de runtime corrompan el authoring, pero introduce complejidad en la coordinacion entre cinco objetos de estado dispersos: `Game._state` (EngineState), `RuntimeController._loop_state` (RuntimeLoopState), `SceneManager._workspace` (SceneWorkspace), `RuntimeController._servicios` (RegistroServicios) y `SceneManager._change_history` (SceneChangeCoordinator).

### 1.1.3 Puntos de Entrada y Superficies de Mutacion

El motor expone cinco puntos de entrada principales, cada uno con un perfil de uso diferente y expectativas de estabilidad distintas. El punto grafico canonico es `py main.py` o la construccion programatica de `Game(...)` en `engine/core/game.py:191`, que monta el editor completo con ventana raylib, paneles, jerarquia, inspector y hot-reload. El parametro `editor_enabled=True` controla si se cargan las dependencias del editor via `_load_editor_dependencies()`, una funcion que materializa 20+ factories globales (seccion 1.3.6). El punto de entrada CLI oficial es `py -m motor`, implementado en `motor/__main__.py` y `motor/cli.py`, que soporta comandos como `motor doctor --project .`, `motor capabilities` y `motor export [...]`.

Para tests, automatizacion y agentes de IA, la superficie publica estable es `EngineAPI`, inicializada en `engine/api/engine_api.py:35`. Su constructor ejecuta una secuencia explicita de cinco fases: validacion del directorio de proyecto (`_validate_project_root`), inicializacion del engine (`_initialize_engine`, que crea `HeadlessGame`, `SceneManager`, `ProjectService` y `AssetService`), inicializacion de colaboradores (`_initialize_collaborators`, que instancia 9 sub-APIs delegadas), refresco de contratos (`_refresh_contracts`) y registro opcional del backend Box2D (`_register_optional_box2d_backend`). El runtime exportado para juegos empaquetados usa `SharedGameRuntime` en `engine/runtime/exported_game.py`, que construye internamente un `Game(editor_enabled=False, hot_reload_enabled=False)` y carga escenas mediante `RuntimeController.load_scene_from_data()`. `ExportRuntime` permanece como shim marcado como deprecated.

Las rutas compartidas de authoring autorizadas — las unicas que deben usarse para mutaciones persistentes — son: `SceneManager.apply_edit_to_world()`, `SceneManager.update_entity_property()`, `SceneManager.replace_component_data()`, `SceneManager.add_component_to_entity()`, `SceneManager.remove_component_from_entity()`, y sus equivalentes publicos en `EngineAPI`. Cualquier otra ruta de mutacion directa sobre `World` o `Entity` constituye un riesgo de corrupcion del estado serializable.

## 1.2 Inventario de Modulos

### 1.2.1 Core Obligatorio: El Contrato Minimo del Motor

Los modulos clasificados como `core obligatorio` definen el contrato minimo que hace funcionar al motor como plataforma coherente de desarrollo 2D. Si cualquiera de estos modulos se rompe, la promesa central del motor — que datos serializables mandan y que editor, runtime, API y CLI trabajan sobre el mismo modelo — deja de cumplirse.

El nucleo ECS (`engine/ecs/`) contiene `world.py`, `entity.py`, `component.py` y `group_operations.py`. `World` es el contenedor principal que almacena entidades, indices y caches de queries. Soporta clonacion (`World.clone()`) para la separacion EDIT/PLAY, serializacion con validacion de contratos (`World.serialize()`) y gestion de grupos via `GroupRegistry`. `Entity` actua como contenedor de componentes con notificaciones bidireccionales a `World` (seccion 1.3.3). `Component` define la interfaz base que todos los componentes registrados deben extender, incluyendo los metodos `to_dict()` y `from_dict()` obligatorios para componentes oficiales.

La capa de escenas (`engine/scenes/`) incluye `scene.py` (la fuente de verdad serializable con `schema_version = 2`), `scene_manager.py` (coordinador de workspace, dirty state, transacciones y transiciones EDIT/PLAY/STOP), `contracts.py` (puertos internos `SceneRuntimePort`, `SceneAuthoringPort`, `SceneWorkspacePort`) y el subsistema de serializacion con migraciones de `v1` a `v2`. El `SceneManager` es el unico componente autorizado a gestionar tanto `edit_world` como `runtime_world`, y su metodo `sync_from_edit_world()` esta marcado como deprecated pero sigue siendo usado internamente en ciertos flujos legacy.

El core del motor (`engine/core/`) contiene `game.py` (la clase `Game` de mas de 1000 lineas que coordina inicializacion de sistemas, estado, editor y profiling), `headless_game.py` (adaptador para ejecucion sin graficos), `runtime_loop.py` (definicion de las cuatro fases del frame) y `runtime_contracts.py` (el dataclass `RuntimeControllerContext` con 25+ getters lambdas que cablean el runtime). La fachada publica (`engine/api/engine_api.py` y sus 10 submodulos `_*_api.py`) encapsula todo acceso externo al motor, aislando a consumidores como tests, CLI y agentes de IA de los internals privados.

El sistema fisico base (`engine/physics/`) incluye `backend.py` (la clase abstracta `PhysicsBackend` que define el contrato comun), `legacy_backend.py` (el backend AABB por defecto con PGS solver, islas, CCD y `move_and_slide`), `island_manager.py` (construccion de islas por BFS), `contact_solver.py` (PGS velocity y position solve), `shapes.py` (ShapeFactory con AABB, Circle, Capsule y Polygon) y `swept_collision.py` (barrido continuo con busqueda binaria TOI). El contrato fisico garantiza que `legacy_aabb` siempre este disponible como fallback universal, incluso cuando el backend Box2D opt-in no pueda activarse.

Finalmente, `engine/levels/component_registry.py` define mediante `create_default_registry()` el inventario oficial de 51 componentes soportados, organizados en 10 familias funcionales. Este registro es la fuente de verdad para la validacion de serializacion: un componente no registrado no tiene soporte publico garantizado.

### 1.2.2 Modulos Oficiales Opcionales

Los modulos oficiales opcionales son capacidades soportadas e integradas en el repositorio, pero no necesarias para que el motor conserve su contrato minimo. El motor puede seguir siendo coherente sin que estas capacidades esten presentes o funcionales.

Los 28 sistemas de runtime (`engine/systems/`) constituyen la logica ejecutable del motor, organizados en cuatro fases: `FIXED_UPDATE` (fisica y gameplay con `fixed_dt = 1/60s`), `UPDATE` (animacion e input), `POST_UPDATE` (UI, temporizadores, bookkeeping) y `RENDER` (solo loop grafico). Los 51 componentes (`engine/components/`) definen los datos serializables que estos sistemas consumen. Los pipelines de assets (`engine/assets/`), render (`engine/rendering/`), audio (`engine/audio/`), tilemap (`engine/tilemap/`) y UI serializable (`engine/ui/`) completan las capacidades oficiales. El backend Box2D (`engine/physics/box2d_backend.py`) es opt-in: cuando la dependencia `Box2D` esta disponible, se registra como alternativa al AABB legacy, aunque con capacidades reducidas (no soporta `move_and_slide` ni `move_and_collide`).

### 1.2.3 Experimental y Tooling

Los modulos experimentales tienen libertad de cambio alta porque no forman parte del contrato duro del motor. Incluyen el agente nativo clean-room (`engine/agent/`), reinforcement learning (`engine/rl/`), recetas IA declarativas (`engine/recipes/`), pathfinding experimental (`engine/navigation/`), debug avanzado y benchmarking (`tools/`, `datasets/`, `benchmarks/`), y la landing page de GitHub Pages (`landing/`). Estos modulos pueden ser valiosos, pero su ausencia o modificacion no rompe la promesa central del motor. La regla de promocion establece que antes de elevar cualquier capacidad experimental a `modulos oficiales opcionales` o `core obligatorio`, debe justificarse que afecta al contrato base de datos o authoring, que requiere compatibilidad fuerte, y que su ausencia romperia la definicion minima del motor.

## 1.3 Deuda Tecnica Identificada

La deuda tecnica del proyecto no es uniforme: algunos items son herencia de transiciones arquitectonicas en curso, otros son decisiones de diseno que acumulan costo de mantenimiento, y un tercer grupo son anti-patrones que dificultan el testing y la evolucion del codigo. La tabla siguiente resume los items identificados, cuantificando su ubicacion concreta y su severidad.

| Item | Archivo | Lineas | Severidad | Descripcion |
|------|---------|--------|-----------|-------------|
| Indices duales ECS | `engine/ecs/world.py` | 167-189, 594-599 | Alta | `_entities_by_name` + `_name_index`, `_entities_by_component` + `_component_index` coexisten; cada operacion actualiza ambos sistemas |
| Invalidacion global de query cache | `engine/ecs/world.py` | 580-592 | Media-Alta | `_component_query_cache.clear()` en cada `_index_component` y `_deindex_component` |
| Acoplamiento Entity-World | `engine/ecs/entity.py` | 134-155 | Alta | `Entity.__setattr__` notifica a `World` via `_notify_owner_world()` sincrono sin batching |
| Physics backend dual | `engine/physics/` | Multiple | Media | `box2d` no soporta `move_and_slide` ni `body_test_motion`; fallback automatico a AABB legacy |
| GPUParticlesSystem adaptador CPU | `engine/systems/gpu_particles_system.py` | Multiple | Media | Delega toda la logica en `ParticleSystem` (CPU); nombre conservado por compatibilidad de wiring |
| Game como God Object | `engine/core/game.py` | 1-500+ | Alta | 1000+ lineas, 20+ factories lazy, 25+ sistemas, estado, editor, profiling |
| Carga lazy de editor | `engine/core/game.py` | 105-189 | Media | `_load_editor_dependencies()` con variables globales y 20+ factories |
| RuntimeControllerContext sin tipado | `engine/core/runtime_contracts.py` | 14-50 | Media | 25+ campos `Callable[[], Any]`; errores solo detectables en runtime |
| Serializacion dual | `engine/ecs/component.py` | 35-101 | Media | Fallback legacy `__dict__` coexiste con contratos explicitos `to_dict()`/`from_dict()` |
| Imports inline en ECS base | `engine/ecs/world.py` | 258-279 | Media | `_touch_component_specific()` importa 8 componentes concretos inline para evitar circular imports |
| Logica de prefabs en World | `engine/ecs/world.py` | 688-762 | Media-Alta | `serialize()` contiene ~75 lineas de logica de prefabs acoplada al formato de serializacion |
| Tests con fallos | `tests/` | Multiple | Alta | 3 failures, 3 errors en suite de tests |
| Errores de linting | Codigo completo | Multiple | Media | 277 errores ruff, 196 errores mypy |

La interpretacion de estos datos requiere distinguir entre deuda activa y deuda pasiva. Los indices duales en `World` son deuda activa: cada creacion, eliminacion o modificacion de entidad debe actualizar ambos sistemas de indexacion, y los metodos `_legacy_remove_name`, `_legacy_add_component_entity` y `_legacy_remove_component_entity` existen exclusivamente para mantener la sincronizacion. La funcion `get_entities_with()` (linea 366) primero intenta los indices nuevos y cae a los legacy como fallback, lo que introduce una ruta de codigo adicional que debe mantenerse coherente. La funcion `_load_editor_dependencies()` en `game.py` (lineas 133-189) es otro ejemplo de deuda activa: 57 lineas de importaciones runtime y asignaciones a variables globales que ocultan las dependencias reales del editor y hacen imposible razonar sobre el grafo de dependencias sin ejecutar el codigo.

### 1.3.1 Indices Duales Legacy/Nuevos en World

En `engine/ecs/world.py`, la clase `World` mantiene dos sistemas de indexacion simultaneos desde las lineas 167 hasta 189. El sistema canonico nuevo usa estructuras optimizadas: `_name_index` (dict `str -> int` para nombre a entity_id), `_serialized_id_index` (dict `str -> int`), `_children_index` (dict `str|None -> set[int]`), `_component_index` (dict `type -> set[int]`), `_component_owner_index` (dict `int -> int` para instancia de componente a entity_id) y `_component_query_cache` (dict `tuple -> tuple` para cache de queries). Paralelamente, el sistema legacy mantiene `_entities_by_name` (dict `str -> Entity`) y `_entities_by_component` (dict `type -> list[Entity`]). Cada operacion de entidad en `add_entity()`, `remove_entity()` y `_adopt_entities()` debe actualizar ambos sistemas, duplicando el trabajo de indexacion y duplicando el riesgo de inconsistencia.

### 1.3.2 Invalidacion Global del Cache de Queries

El cache de queries `_component_query_cache` se invalida completamente en cada adicion o remocion de componente. Los metodos `_index_component()` y `_deindex_component()` (lineas 580-592) ejecutan `self._component_query_cache.clear()` incondicionalmente. Esto es correcto funcionalmente — cualquier query que involucre el tipo de componente modificado podria tener resultados desactualizados — pero es suboptimo: una invalidacion selectiva por `query_key`, que solo eliminara las entradas cuyo `query_key` contenga el `component_type` modificado, reduciria el costo de recomputable en escenas con alta frecuencia de cambio de componentes.

### 1.3.3 Acoplamiento Bidireccional Entity-World

En `engine/ecs/entity.py` (lineas 134-155), la clase `Entity` intercepta cambios a campos trackeados via `__setattr__` y notifica al `World` propietario mediante `_notify_owner_world()`. Esto implica que `Entity` conoce la existencia de `World`, que `Entity` llama a un metodo privado de `World` en cada cambio de campo, y que `World._on_entity_changed()` responde reindexando. Este patron sincrono sin batching dificulta el testing aislado de `Entity` (requiere un `World` mock), complica la serializacion (los side effects de notificacion pueden interferir con la reconstruccion de entidades) y hace imposible usar `Entity` fuera del contexto de un `World`.

### 1.3.4 Physics Backend Dual con Capacidades Diferentes

El motor mantiene dos backends de fisica: `legacy_aabb` (disponible siempre) y `box2d` (opt-in, requiere la dependencia `Box2D 2.3.10`). La deteccion de cual backend usar ocurre en `RuntimeController.update_gameplay()` via `PhysicsBackendRegistry.resolve(world)`. El problema es que `box2d` no soporta `move_and_slide()` ni `move_and_collide()`, metodos que si estan implementados en `LegacyAABBPhysicsBackend` con un bucle de deslizamiento multi-iteracion basado en `body_test_motion`. Cuando un juego configura `box2d` como backend pero usa `CharacterController2D` con `move_mode = "move_and_slide"`, el sistema cae automaticamente al fallback AABB legacy. Esto significa que la experiencia de movimiento cinematico es diferente segun el backend activo, sin que el usuario tenga control explicito sobre el fallback.

### 1.3.5 GPUParticlesSystem como Anti-Humo

`GPUParticlesSystem` en `engine/systems/gpu_particles_system.py` delega toda su logica en `ParticleSystem` (CPU). No existe aceleracion GPU real: el computo es puramente CPU fallback. El nombre `GPUParticlesSystem` se conserva por compatibilidad con el wiring existente en `RuntimeControllerContext` y `Renderer`. Este modulo esta clasificado como `experimental/tooling` en la taxonomia del motor, pero aparece en la lista de sistemas del `RuntimeControllerContext`, donde los consumidores podrian asumir que existe una diferencia funcional real entre `ParticleSystem` y `GPUParticlesSystem`.

### 1.3.6 Game como God Object

`engine/core/game.py` supera las 1000 lineas y contiene logica de inicializacion de 25+ sistemas, state management, editor UI (paneles, shell, layout), profiling, scene workflow, signal compilation y fullscreen toggle. Es una clase God Object donde cualquier refactor parcial requiere entender toda la clase. El metodo `__init__` (a partir de linea 196) inicializa 25+ atributos de sistema, monta paneles de editor condicionalmente, crea el `RuntimeController` con un `RuntimeControllerContext` de 25+ lambdas, y configura tres controladores adicionales (`DebugToolsController`, `SceneWorkflowController`, `ProjectWorkspaceController`) cada uno con su propio conjunto de closures.

### 1.3.7 Estado de Calidad del Codigo

La suite de tests del proyecto reporta 3 fallos (failures) y 3 errores (errors) al ejecutarse. Adicionalmente, el analisis estatico con `ruff` detecta 277 violaciones de estilo o posibles bugs, y `mypy` reporta 196 errores de tipado en el codebase. Estas cifras indican que el proyecto carece de una barrera de calidad automatica antes de la integracion: codigo con errores de tipo o violaciones de estilo puede llegar a la rama principal sin obstaculo mecanico. La ausencia de un gestor de dependencias estandar (`pyproject.toml`, `requirements.txt`, `setup.py` o `Pipfile`) en la raiz del proyecto dificulta la reproducibilidad del entorno y la configuracion de integracion continua.

## 1.4 Riesgos Generales de Refactorizacion

### 1.4.1 Modulos Protegidos: Lista de No-Tocar sin Plan de Contingencia

Cualquier plan de refactorizacion debe comenzar por identificar los modulos cuya modificacion conlleva riesgo de ruptura total del contrato publico del motor. La tabla siguiente clasifica estos modulos por nivel de proteccion.

| Modulo | Archivo(s) Clave | Nivel de Proteccion | Razon de Proteccion |
|--------|-----------------|---------------------|---------------------|
| ECS base: World, Entity, Component | `engine/ecs/world.py`, `entity.py`, `component.py` | CRITICO | Todo depende de ellos: 51 componentes, 28 sistemas, serializacion, clonacion EDIT/PLAY |
| Scene (fuente de verdad) | `engine/scenes/scene.py` | CRITICO | Define schema v2; save/load roundtrip debe conservar entidades, componentes, jerarquia y feature_metadata |
| SceneManager | `engine/scenes/scene_manager.py` | CRITICO | Coordina EDIT/PLAY/STOP, workspace multi-escena, dirty state, transacciones y prefabs |
| EngineAPI fachada | `engine/api/engine_api.py` + 10 submodulos | CRITICO | Superficie publica estable para tests, CLI, agentes IA y scripts de automatizacion |
| Schema y migraciones | `engine/serialization/schema.py` | CRITICO | Define v1->v2; sin compatibilidad hacia atras si se rompe el formato |
| ComponentRegistry | `engine/levels/component_registry.py` | ALTO | Fuente de verdad de los 51 componentes oficiales; afecta validacion de serializacion |
| LegacyAABBPhysicsBackend | `engine/physics/legacy_backend.py` | ALTO | Fallback universal; backend default estable con PGS solver, islas y CCD |
| PhysicsBackend ABC | `engine/physics/backend.py` | ALTO | Contrato comun que ambos backends deben implementar; define move_and_slide y move_and_collide |
| RuntimeController | `engine/app/runtime_controller.py` | MEDIO-ALTO | Orquesta los 28 sistemas en las 4 fases del frame; orden de ejecucion afecta determinismo fisico |
| Game / HeadlessGame | `engine/core/game.py`, `cli/headless_game.py` | MEDIO-ALTO | Puntos de entrada principales; wiring de 25+ sistemas y 25+ lambdas de contexto |
| Contratos internos | `engine/scenes/contracts.py`, `engine/core/runtime_contracts.py` | MEDIO | Puertos internos que fijan limites de integracion entre runtime, authoring, workspace y API |

Los modulos marcados como CRITICO deben considerarse inmutables en cualquier refactor de fase 1. Un cambio en `World.serialize()` o en `Scene` podria invalidar todos los archivos de escena existentes, forzando una migracion de formato que el proyecto no tiene capacidad de ejecutar con solo 2 contribuyentes. Los modulos de nivel ALTO pueden modificarse si se dispone de un plan de contingencia que incluya: (a) tests de regresion que ejecuten antes y despues del cambio, (b) un periodo de dualidad donde el sistema nuevo coexista con el legacy, y (c) un rollback definido en caso de fallo. Los de nivel MEDIO-ALTO y MEDIO requieren analisis de impacto caso por caso.

La decision de proteccion se basa en dos criterios: cuantas rutas de codigo dependen del modulo, y que tan dificil es detectar una ruptura. `EngineAPI` tiene proteccion critica no porque su implementacion sea compleja, sino porque es la unica fachada publica estable: tests, CLI, agentes de IA y scripts de automatizacion dependen de sus metodos. Un cambio en la firma de `EngineAPI.load_level()` o `EngineAPI.play()` romperia todos los consumidores externos sin que el compilador de Python lo detecte.

### 1.4.2 Riesgo de Divergencia: 98 Ramas con 2 Contribuyentes

El repositorio mantiene 98 ramas activas con solo 2 contribuyentes. Esta metrica, obtenida del analisis del repositorio Git, sugiere un patron de desarrollo caracterizado por alta experimentacion paralela sin consolidacion. Muchas de estas ramas podrian contener cambios parciales, exploraciones de features o correcciones de bugs que nunca fueron integrados a la rama principal. Antes de iniciar cualquier refactorizacion, es imperativo verificar si hay ramas relevantes con cambios no fusionados que podrian entrar en conflicto con las modificaciones planeadas. El riesgo de divergencia se manifiesta cuando un refactor en la rama principal invalida el trabajo pendiente en ramas paralelas, o cuando una rama larga se fusiona despues del refactor introduciendo regresiones en modulos que ya fueron modificados. La recomendacion operativa es: auditar las 10-15 ramas mas recientes en busca de cambios que afecten los modulos criticos identificados en la tabla anterior, y consolidar o descartar esas ramas antes de comenzar la fase 1 del refactor.

La combinacion de deuda tecnica significativa (indices duales, God Object, acoplamiento bidireccional), estado de calidad deficiente (3 failures, 3 errors, 277 errores ruff, 196 errores mypy) y una estructura de contribucion fragil (2 desarrolladores, 98 ramas) define el contexto de riesgo dentro del cual debe ejecutarse cualquier plan de refactorizacion. El diagnostico no es una invitacion a la paralisis: es un mapa de restricciones que permite priorizar intervenciones segun su relacion costo-beneficio y su probabilidad de exito dado el equipo disponible. El capitulo siguiente traduce este diagnostico en hotspots concretos — ubicaciones medibles en el codigo donde la refactorizacion producira el mayor impacto con el menor riesgo de ruptura.

---


# 2. Hotspots y Profiling

El diagnostico del Capitulo 1 establecio que el motor OpenGame 2D arrastra problemas sistematicos de complejidad algoritmica, invalidacion agresiva de caches y allocaciones por frame. Este capitulo transforma esas observaciones generales en un catalogo cuantificado de 15 hotspots priorizados, acompanado de un analisis de las estructuras recreadas cada frame y un plan de benchmarks para medir el impacto de las futuras optimizaciones. Cada hotspot se vincula a una rutina concreta, un archivo fuente y una metrica observable, eliminando la ambiguedad sobre donde invertir el esfuerzo de refactorizacion.

## 2.1 Hotspots Criticos Identificados

El analisis estatico de ~2.500 lineas de codigo distribuidas en 10 archivos clave revelo ocho categorias de cuello de botella que consumen tiempo de CPU de manera desproporcionada. La tabla siguiente condensa los 15 hotspots mas relevantes, ordenados por una combinacion de severidad, frecuencia de invocacion y dificultad de mitigacion. Los tres primeros concentran la mayor parte del tiempo perdido en escenas medianas a grandes.

| # | Hotspot | Archivo | Funcion / Lineas | Severidad | Complejidad | Metrica Clave |
|---|---------|---------|------------------|-----------|-------------|---------------|
| 1 | Invalidacion global del query cache ECS | `engine/ecs/world.py` | `_index_component()` L.580-583, `_deindex_component()` L.585-592 | Critica | O(1) invalidacion, O(k) reconstruccion | Hit rate del `_component_query_cache` por frame |
| 2 | O(N^2) en busqueda de areas de gravedad/damping | `engine/systems/physics_system.py` | `_get_effective_gravity()` L.798-875, `_get_effective_linear_damp()` L.884-937, `_get_effective_angular_damp()` L.939-992 | Critica | O(N * M) por frame | Tiempo acumulado en area queries vs. num rigidbodies |
| 3 | PGS Solver en Python puro | `engine/systems/physics_system.py`, `contact_solver.py` | `solve()` L.549, `solve_positions()` L.558 | Critica | 8 vel + 5 pos iteraciones * constraints | `solver_iterations * constraint_count * island_count` |
| 4 | `body_test_motion` iterando todas las entidades | `engine/physics/legacy_backend.py` | `_collect_motion_targets()` L.403-461 | Alta | O(P * slides * E) | Tiempo vs. entity_count y character_count |
| 5 | SpatialHash2D con dicts Python | `engine/physics/spatial_hash.py` | `insert()` L.26-35, `query()` L.37-48, `query_ray_candidates()` L.65-94 | Alta | O(celdas) por query sin arrays contiguos | Cell count, reference count, oversized entries |
| 6 | Render spatial index reconstruido por frame | `engine/systems/render_system.py` | `_spatially_filter_render_entities()` L.759-781 | Alta | O(R) rebuild cada frame | Tiempo de `rebuild()` vs. entidades renderizables |
| 7 | `get_entities_with()` crea lista nueva por llamada | `engine/ecs/world.py` | `get_entities_with()` L.366-403 | Alta | O(k) lista + filtrado activo | Llamadas por frame y tamanio de listas retornadas |
| 8 | CollisionSystem iterando todas las entidades con Collider | `engine/systems/collision_system.py` | `update()` L.96-267 | Alta | O(C) + O(E) escaneos | Candidate pairs, narrow phase pairs, colisiones reales |
| 9 | ParticleSystem: scan lineal del pool por emitter | `engine/systems/particle_system.py` | `_update_particles()` L.208-243, `_alloc()` L.194-206 | Media-Alta | O(pool_size * emitter_count) | Tiempo vs. pool_size (max 32768) * emitters |
| 10 | `sync_world` iterando todas las entidades | `engine/physics/legacy_backend.py` | `sync_world()` L.62-86 | Media-Alta | O(E) por step | Tiempo vs. entity_count total |
| 11 | `query_shape_cast` iterando todas las entidades | `engine/physics/legacy_backend.py` | `query_shape_cast()` L.219-314 | Media-Alta | O(E) por cast | Tiempo vs. entity_count |
| 12 | Render graph cache invalidado por debug flags | `engine/systems/render_system.py` | `_build_render_graph()` L.432-684 | Media | O(R log R) por invalidacion | Hit/miss del render graph cache |
| 13 | CharacterController crea backend cada frame | `engine/systems/character_controller_system.py` | `update()` L.30-44 | Media | Instanciacion de ~69KB codigo | Instanciaciones de `LegacyAABBPhysicsBackend` por frame |
| 14 | `swept_shape_toi` import dinamico por colision | `engine/physics/legacy_backend.py` | `_swept_toi()` L.316-339 | Media | O(1) lookup * llamadas | Tiempo de narrow-phase vs. shape pairs |
| 15 | GroupRegistry invalida orden en cada registro | `engine/ecs/world.py` | `register_entity()` L.58-63 | Media | O(g log g) sort | Tiempo vs. tamano de grupo |

La interpretacion de esta tabla es inmediata: los tres hotspots criticos (filas 1-3) explican por que escenas con mas de 5.000 entidades o mas de 50 cuerpos dinamicos sufren degradaciones severas de frame time. El hotspot 1 invalida todo el trabajo de cache del ECS, forzando reconstrucciones de interseccion de sets en cada frame donde se spawnee o destruya una entidad. El hotspot 2 multiplica el coste de la fisica por el tamano total del mundo, no por la cantidad de cuerpos dinamicos. El hotspot 3 ejecuta miles de iteraciones de solver sobre estructuras Python dispersas, un patron que ninguna optimizacion algoritmica dentro del interprete puede resolver satisfactoriamente. Los hotspots de severidad alta (filas 4-8) agravan el problema al escanear colecciones completas donde una busqueda espacial seria suficiente. Los de severidad media (filas 9-15) representan acumulaciones de overhead que, individualmente, no dominan el perfil pero que en conjunto consumen un 15-25% del tiempo de frame en escenas densas.

### 2.1.1 World.clone() para Play Mode: Serializacion JSON Completa

La transicion de modo EDIT a PLAY es uno de los puntos de friccion mas visibles para el usuario. `World.clone()` (invocado en `play_mode_clone_stress`) recorre `self.iter_all_entities()` en su totalidad y, por cada entidad, ejecuta `_clone_component()`, que resuelve la copia via `component.to_dict() -> clone_json_value() -> from_dict()`. Para una escena tipica de 10.000 entidades con 5 componentes cada una, esto implica 50.000 round-trips de serializacion JSON. El analisis del codigo en `engine/ecs/component.py` confirma que `Component.clone()` carece de un contrato de copia rapida; incluso componentes triviales como `Transform` (seis campos numericos) atraviesan el pipeline completo de serializacion. El benchmark `play_mode_clone_stress` con 10.000 entidades reporta tiempos de 200 ms a 2 segundos segun el hardware y la complejidad de los componentes, un rango que convierte la iteracion de desarrollo en una experiencia fragmentada.

### 2.1.2 get_entities_with() con Cache Invalidada Globalmente

El metodo `get_entities_with()` en `engine/ecs/world.py` (lineas 366-403) implementa un cache de dos niveles: `_component_query_cache` almacena tuplas de `entity_id` indexadas por la tupla de tipos de componente consultados. Sin embargo, la invalidacion de este cache ocurre en `_index_component()` y `_deindex_component()` (lineas 580-592), donde se invoca `self._component_query_cache.clear()` sin discriminacion. El resultado es que una sola entidad que anada o elimine un componente destruye todas las queries cacheadas del mundo. En escenas dinamicas donde se spawnean particulas, balas o enemigos, el cache nunca "enfria": el hit rate cae a aproximadamente 0% y cada llamada a `get_entities_with()` reconstruye la interseccion de sets desde cero. Adicionalmente, incluso cuando `candidate_ids` se obtiene del cache, la funcion materializa una `list[Entity]` nueva (lineas 388-392), aplicando filtros de `active` y `has_enabled_component` que requieren lookups adicionales en el dict `_entities`.

### 2.1.3 SpatialHash2D con Dicts Python: Sin Arrays Contiguos

La estructura `SpatialHash2D` en `engine/physics/spatial_hash.py` (130 lineas) utiliza `dict[tuple[int, int], set[int]]` para almacenar las celdas. Cada insercion invoca `setdefault((cx, cy), set())`, que crea un conjunto vacio de Python si la celda no existe. Las consultas `query()` y `query_into()` recorren rangos de celdas con bucles anidados de Python y acumulan resultados en sets mediante `update()`. El metodo `query_ray_candidates()` (lineas 65-94) es especialmente conservador: en lugar de implementar un algoritmo DDA (Digital Differential Analyzer) que recorra exactamente las celdas intersectadas por el rayo, construye un AABB envolvente del segmento de rayo y consulta todas las celdas dentro de ese rectangulo. Esto genera un numero de falsos positivos proporcional al angulo del rayo, penalizando los casts diagonales. La ausencia de arrays contiguos en memoria implica que no hay vectorizacion posible y que cada acceso a celda implica multiples resoluciones de hash.

### 2.1.4 LegacyAABBPhysicsBackend: 69 KB de Python Puro

El archivo `engine/physics/legacy_backend.py` contiene 1.590 lineas de codigo Python que implementan fisica AABB (Axis-Aligned Bounding Box). El metodo `body_test_motion()` (lineas 633-804) es el punto de entrada para `move_and_slide` del character controller. Internamente, `_collect_motion_targets()` (lineas 403-461) itera `world.get_all_entities()` completo para cada llamada. Como `move_and_slide` puede invocar `body_test_motion` hasta `max_slides` (4) veces por personaje por frame, la complejidad total es O(P * slides * E), donde P es el numero de personajes. En una escena con 10 personajes y 1.000 entidades, esto implica hasta 40.000 iteraciones de entidades por frame solo para el movimiento de personajes. El backend ademas crea instancias de shapes en cada consulta y resuelve colisiones swept mediante `_swept_toi()`, que importa dinamicamente `swept_shape_toi` dentro de la funcion (linea 327), anadiendo un `__import__` por colision potencial.

### 2.1.5 PGS Solver en Python Puro: Iteraciones Dict-Intensivas

El solver PGS (Projected Gauss-Seidel) reside en `engine/systems/physics_system.py` y `engine/physics/contact_solver.py`. Por cada isla de contactos, ejecuta `self._solver_iterations` (8 por defecto) pasadas de velocity solve y 3-5 pasadas de position solve. Dentro de cada iteracion, el solver recorre cada `ContactConstraint2D`, accediendo a velocidades, masas y transformadas a traves de dict lookups (`all_bodies[entity_id]`) y resolviendo el sistema lineal de contacto en coordenadas Python puro. Para una escena con 100 cuerpos dinamicos, 10 islas y 200 constraints, esto representa 8 * 200 * 10 = 16.000 iteraciones de velocity solve por frame, cada una con multiples accesos a diccionarios y operaciones aritmeticas encapsuladas. El coste no es solo el numero de operaciones, sino la indireccion continua: el solver nunca trabaja sobre arrays contiguos de velocidades o posiciones.

### 2.1.6 PhysicsSystem O(N^2): _get_effective_gravity y Damping

Los metodos `_get_effective_gravity()` (lineas 798-875), `_get_effective_linear_damp()` (lineas 884-937) y `_get_effective_angular_damp()` (lineas 939-992) de `physics_system.py` comparten una misma estructura defectuosa: cada uno itera `world.iter_entities()` completo para encontrar `Area2D` que solapen el AABB del cuerpo dinamico. Si hay N rigidbodies dinamicos y M entidades totales, esto es O(N * M) por frame. En una escena con 100 rigidbodies y 10.000 entidades, cada funcion escanea 1.000.000 de entidades por frame, y las tres funciones en conjunto escanean 3.000.000. El codigo fuente muestra que la unica optimizacion aplicada es un early-out por `Area2D` deshabilitado o sin override de gravedad, pero no hay indice espacial de areas: cada body dinamico compara su AABB contra todos los demas del mundo.

### 2.1.7 IslandBuilder BFS Cada Frame: Sin Persistencia de Conectividad

`IslandBuilder2D.build_islands()` en `engine/physics/island_manager.py` (lineas 44-123) reconstruye el grafo de conectividad desde cero en cada paso de fisica. El proceso completo incluye: (1) colectar todos los body IDs de constraints y joints en un set, (2) construir una lista de adyacencia como `dict[int, set[int]]`, (3) ejecutar BFS sobre cada componente conectado, y (4) asignar constraints a islas mediante iteracion completa de la lista de constraints. Aunque existe el parametro `body_id_to_island` para persistencia de estado de sueno, la estructura de islas se recalcula integramente. En escenas con muchos cuerpos estaticos que no cambian de configuracion, esta reconstruccion es puramente redundante: la topologia de contactos entre frames consecutivos tipicamente difiere solo en un pequeno porcentaje.

### 2.1.8 Render Pipeline: Reconstruccion del RenderSpatialIndex Cada Frame

El metodo `_spatially_filter_render_entities()` en `engine/systems/render_system.py` (lineas 759-781) invoca `self._render_spatial_index.rebuild(sorted_entities)` en cada frame (linea 773), independientemente de si las entidades renderizables han cambiado de posicion. A diferencia del `_static_grid_cache` del PhysicsSystem, que al menos se preserva cuando la version de estructura no cambia, el indice espacial de render no implementa version tracking. Tras el rebuild, el sistema ejecuta un `query(camera_bounds)` para obtener los IDs visibles y luego filtra `sorted_entities` mediante una list comprehension que verifica membresia en el set de visibles. Este doble paso (rebuild completo + filtrado secuencial) procesa todas las entidades renderizables dos veces por frame, incluso cuando la camara y las entidades son estaticas.

## 2.2 Allocaciones e Invalidaciones por Frame

Los hotspots identificados en la seccion anterior no operan sobre estructuras persistentes; gran parte del tiempo de CPU se consume en crear y destruir objetos temporales que podrian reutilizarse o eliminarse.

### 2.2.1 Estructuras Creadas Cada Frame

El analisis de rutas calientes revela ocho categorias de estructuras que se instancian garantizadamente en cada frame de gameplay:

Las listas de entidades (`list[Entity]`) generadas por `get_entities_with()` representan una de las fuentes mas persistentes de allocacion. En un frame tipico, los sistemas de render, fisica y colision realizan entre 5 y 15 queries distintas; cada una materializa una lista nueva con referencias a objetos Entity. El PhysicsSystem ademas crea un `dict[int, _SolidCandidate]` para los cuerpos estaticos, un `dict[int, Any]` (`all_bodies`) que mapea IDs a instancias de rigidbody, y una `list[ContactConstraint2D]` que acumula todos los constraints del frame. La cantidad de constraints escala cuadraticamente con el numero de cuerpos en proximidad, por lo que en escenas densas esta lista puede contener miles de objetos nuevos. El cache de queries (`_component_query_cache`) se invalida globalmente y se reconstruye como `dict[tuple[type, ...], tuple[int, ...]]`, recreando las tuplas de clave y valor en cada invalidacion. El `SpatialHash2D` para cuerpos dinamicos (`moving_grid`) se instancia de cero en cada paso de fisica (linea 207 de `physics_system.py`), incluyendo su dict interno de celdas. En el sistema de render, cada frame genera listas de `RenderBatch` y `RenderCommand` que se recorren secuencialmente para producir las llamadas de dibujo.

### 2.2.2 Caches Global vs. Selectiva: Un Contraste Revelador

No todas las invalidaciones de cache son igualmente costosas. El `_component_query_cache` del ECS es el peor caso: una invalidacion global que se dispara en cada add o remove de componente, sin importar si el tipo de componente afectado es relevante para las queries cacheadas. Un sistema que spawnea balas (add de componente `Bullet`) invalida el cache de `RenderSystem`, que consulta `(Transform, Sprite)`, aunque `Bullet` no participe en esa query.

Por el contrario, el `VersionedGeometryCache` del PhysicsSystem implementa un esquema de versionado correcto. La cache almacena geometria (AABB y shapes) indexada por una firma que incluye la pose del transform y la definicion del collider. Solo se reconstruye cuando la firma cambia, lo que ocurre tipicamente en el primer frame o cuando un objeto se mueve. Las metricas internas del motor (`aabb_builds`, `aabb_cache_hits`, `shape_builds`, `shape_cache_hits`) permiten observar este comportamiento: en frames calientes, el hit rate de la geometria supera el 95%, mientras que el hit rate del query cache ECS permanece cercano al 0% en escenas dinamicas.

El `_static_grid_cache` del PhysicsSystem representa un caso intermedio. El spatial hash estatico se preserva mientras el `cache_key` (compuesto por `id(world)`, `world.structure_version`, `selected_cell_size` y la tupla de firmas geometricas de todos los estaticos) no cambie. Esto funciona bien para escenas donde los estaticos no se mueven, pero invalida completamente ante cualquier cambio estructural, incluso si ese cambio no afecta a los cuerpos estaticos.

## 2.3 Metricas a Medir y Benchmarks

La refactorizacion sin medicion es especulacion. Esta seccion define las metricas concretas que cada hotspot debe reportar y cataloga los benchmarks existentes y propuestos para capturarlas.

### 2.3.1 Benchmarks Existentes: Infraestructura Disponible

El motor dispone de un sistema de benchmarks headless accesible via `engine.debug.benchmark_runner`. Los cuatro escenarios relevantes para este analisis son:

`many_transform_entities` (10k-100k entidades) mide el rendimiento del ECS en escenas dominadas por transforms. Es el benchmark principal para los hotspots 1, 7 y 15 (query cache, allocaciones de `get_entities_with`, ordenamiento de grupos). `play_mode_clone_stress` (10k entidades) mide el tiempo de transicion EDIT->PLAY y es el benchmark directo para el hotspot de `World.clone()`. `many_sprite_entities` (10k entidades) evalua la preparacion de render, incluyendo el sorting de entidades y la reconstruccion del spatial index (hotspots 6 y 12). Los escenarios de fisica (`many_static_colliders`, `many_dynamic_and_static` con backends `legacy_aabb` y `box2d`) cubren los hotspots 2, 3, 4, 5, 8, 10 y 11, reportando metricas como `candidate_solids`, `island_count`, `aabb_builds`, `shape_builds`, swept checks y estadisticas del spatial hash.

La suite CI (`tools.benchmark_suite --quick`) ejecuta estos escenarios con umbrales suaves para detectar regresiones grandes. Los reportes JSON conservan tres secciones (`summary`, `profiler_report`, `last_sample`) con las mediciones puntuales bajo la clave `operations`, permitiendo extraer datos comparables entre ejecuciones.

### 2.3.2 Benchmarks Nuevos Recomendados

Los benchmarks existentes no cubren algunos patrones de acceso criticos. Se proponen los siguientes escenarios adicionales:

Para el ECS, un benchmark `query_cache_stress` que ejecute 100 operaciones de add/remove de componente en una escena de 1.000 entidades mientras se miden 1.000 queries `get_entities_with(Transform)` permitiria cuantificar directamente el impacto de la invalidacion global. Un benchmark `get_component_throughput` que ejecute 1 millon de llamadas a `entity.get_component(Transform)` sobre 1.000 entidades estableceria una linea base para la ruta de lookup. Para la fisica, un escenario `area_overlap_stress` con 50 rigidbodies dinamicos y 100 areas de gravedad medira el O(N^2) de `_get_effective_gravity`. Para el render, un benchmark `render_prep_10k_sprites` que aísle la fase de preparacion (sorting, spatial index rebuild, batch construction) del dibujo real permitiria medir los hotspots 6, 7 y 12 sin ruido del driver grafico. Para particulas, un escenario `particle_pool_stress` con 10 emitters y 5.000 particulas activas quantificaria el coste del scan lineal del pool (hotspot 9). Finalmente, un benchmark `ecs_clone_by_component_count` con escenas de 1k, 5k, 10k y 50k entidades multiplicado por 1, 3, 5 y 10 componentes caracterizaria la escalabilidad de `World.clone()`.

### 2.3.3 Speedup Minimo Aceptable: El Umbral de 2x

La migracion de un modulo Python a Rust (via PyO3) introduce complejidad de build, dependencias nativas cross-platform y mayor dificultad de depuracion. Por ello, se establece como criterio de decision que la migracion de un modulo completo solo se justifica cuando los benchmarks proyecten una mejora minima de 2x sobre la implementacion Python optimizada. Este umbral no es arbitrario: compensa el coste de mantenimiento adicional y el riesgo de incompatibilidades en el pipeline de distribucion.

Los hotspots que potencialmente superan este umbral con migracion a Rust son el PGS Solver (hotspot 3), donde la literatura de motores de fisica reporta speedups de 10-50x al mover el solver a codigo nativo con arrays contiguos, y el SpatialHash2D (hotspot 5), donde un grid con vec contiguo y DDA para ray casting puede alcanzar 5-20x sobre la implementacion con dicts y sets de Python. Para los hotspots algoritmicos (invalidacion de cache, O(N^2) por falta de indice, allocaciones innecesarias), la optimizacion en Python pura tipicamente alcanza mejoras de 2-10x sin necesidad de salir del interprete, haciendo que Rust sea innecesario para esos casos. Los benchmarks definidos en esta seccion son los que determinara, con datos concretos, que optimizaciones se quedan en Python y cuales requieren la frontera nativa.

---


## 3. Plan Python vs Rust

El analisis de hotspots del Capitulo 2 revelo que OpenGame concentra el tiempo de CPU en un numero reducido de subsistemas: broad-phase espacial, iteracion ECS, preparacion de render y simulacion de particulas. No obstante, aproximadamente el 70 % del codigo fuente no aparece en rutas calientes y no justifica el coste cognitivo y operativo de una migracion a Rust. Este capitulo establece la division de responsabilidades entre ambos lenguajes, documentando que subsistemas permanecen en Python con su arquitectura intacta y cuales se migran a Rust ordenados por la relacion esfuerzo/beneficio.

El criterio fundamental para esta division es el **coste de oportunidad**: un modulo solo migra a Rust si el speedup proyectado supera con creces el coste de mantener una frontera FFI (Foreign Function Interface), generar wheels multiplataforma y garantizar tests de equivalencia permanentes entre ambas implementaciones. Todo lo que no cumple este umbral permanece en Python, donde la velocidad de desarrollo, la capacidad de introspeccion y la compatibilidad con el ecosistema de agentes de IA son insustituibles.

### 3.1 Responsabilidades Python (mantener)

Python sigue siendo el lenguaje anfitrion de OpenGame. Los siguientes subsistemas permanecen en Python de manera permanente, no como decision provisional, sino porque Rust no aporta valor anadido en su dominio o porque la restriccion de compatibilidad hace inviable cualquier alteracion.

#### 3.1.1 EngineAPI: fachada publica estable

La fachada `EngineAPI` (`engine/api/engine_api.py`), con aproximadamente 180 metodos publicos, constituye el contrato de estabilidad del motor. Es la interfaz que consumen los agentes de IA (via `START_HERE_AI.md`), los tests de integracion, los scripts CLI y las herramientas de automatizacion. La restriccion dura del proyecto establece que `EngineAPI` y la serializacion de escenas no pueden romperse bajo ninguna circunstancia. Migrar esta fachada a Rust implicaria rehacer la capa de bindings para cada metodo publico, multiplicando la superficie de FFI por un factor de cien sin beneficio de rendimiento alguno, ya que la fachada es una capa de delegacion que no ejecuta computo intensivo. Nuevas capacidades del motor se exponen exclusivamente a traves de esta interfaz, manteniendo el contrato social con los usuarios y agentes.

#### 3.1.2 Editor completo: EditorShell, UI core, layout, inspector, panels

El editor visual de OpenGame opera sobre un ciclo de interaccion humana donde los cuellos de botella son la latencia de entrada y el renderizado de widgets, no la ejecucion de logica Python. Los sistemas de layout, el inspector de propiedades, los paneles flotantes y el `EditorShell` dependen de introspeccion dinamica de componentes, serializacion inmediata a JSON para el estado del workspace y reflexion sobre clases Python. Rust carece de ventajas significativas en este dominio: la programacion de interfaces de usuario interactivas en Rust (via egui, imgui o toolkits nativos) no mejoraria el rendimiento percibido por el usuario y degradaria la velocidad de iteracion del equipo.

#### 3.1.3 SceneManager: workspace, authoring, transacciones, dirty state

El `SceneManager` gestiona el flujo de vida del ciclo `EDIT -> PLAY -> STOP`, incluyendo la captura de snapshots del mundo para deshacer/rehacer, el tracking de estado modificado (dirty state) y la transicion de contexto entre modo edicion y modo juego. Este subsistema esta profundamente acoplado a la serializacion `World.clone()` y a la semantica de transacciones del editor. Aunque `World.clone()` es un hotspot de rendimiento (Capitulo 2, Seccion 2.4), la optimizacion se aplicara en el storage subyacente, no en el coordinador de escenas, que permanece en Python como orquestador.

#### 3.1.4 Serializacion: Scene v2, Prefab v2, schema, migraciones

El formato de serializacion Scene v2 y Prefab v2 define el contrato de persistencia del motor. Cada cambio en el schema requiere una migracion coordina. Las clases `Component` existentes — mas de 40 en el registro (`component_registry.py`) — mantienen sus metodos `to_dict()` y `from_dict()` como interfaz de serializacion inmutable. Rust puede participar en la serializacion acelerando el escaneo de datos internos (por ejemplo, un `SparseSet` nativo serializa su estado contiguo de forma mas rapida), pero el coordinador del proceso, el manejo de prefabs, la resolucion de referencias cruzadas y las migraciones de schema permanecen 100 % en Python.

#### 3.1.5 CLI motor, IA/agentes y tests

El sistema de comandos CLI (`motor/`) y la infraestructura de agentes de IA (`START_HERE_AI.md`, skills, prompts) dependen del dinamismo de Python para la generacion de codigo, la carga condicional de modulos y la reflexion sobre el estado del motor. Los tests de integracion y equivalencia — incluyendo los golden tests que comparan salidas byte-a-byte entre implementaciones Python y Rust — se ejecutan exclusivamente en Python, ya que su proposito es verificar la correccion de ambos lados de la frontera FFI.

#### Tabla 3.1: Subsistemas que permanecen en Python

| Subsistema | Archivos clave | Razon de permanencia | Riesgo si se migra |
|---|---|---|---|
| EngineAPI (fachada publica) | `engine/api/engine_api.py` (~180 metodos) | Contrato estable para agentes, tests, CLI | Roto = todos los juegos y agentes externos dejan de funcionar |
| Editor UI completo | `editor/`, `engine/ui/` | I/O bound, reflexion Python, tooling | Perdida de iteracion rapida, acople innecesario a FFI |
| SceneManager | `engine/core/scene_manager.py` | Coordinador de ciclo EDIT-PLAY-STOP | Cambios propagan a TODO; estabilizar primero |
| Serializacion v2 (coordinador) | `engine/ecs/world.py:serialize()` | Formato de escena es contrato de persistencia | Escenas existentes no se podrian guardar/cargar |
| Component classes (40+) | `engine/components/*.py` | API `to_dict/from_dict` es inmutable | Serializacion depende de `__dict__` y nombres de clase |
| CLI motor | `motor/` | Scripting, parseo de args, dinamismo | Sin beneficio de rendimiento |
| IA/agentes | `START_HERE_AI.md`, `skills/` | EngineAPI es unica interfaz; reflexion Python | Incompatible con ecosistema de agentes |
| Tests integracion/equivalencia | `tests/` | Deben correr en ambos modos (pure/native) | Perderian proposito si estan en Rust |
| PhysicsBackend ABC + dispatch | `engine/physics/backend.py` | Decide que backend usar; los backends SI pueden ser Rust | Cambios rompen Box2D y legacy simultaneamente |
| Carga de assets | `engine/resources/` | I/O bound (disco/red), no CPU bound | Rust no mejora carga de texturas/sonidos |
| Sistema scripting | `engine/systems/script_behaviour_system.py` | Hot reload, importlib, eval, 100 % Python | Imposible en Rust sin reimplementar CPython |
| AnimationSystem | `engine/systems/animation_system.py` | State machine declarativa, callbacks Python | Logica trivial (~0.1 ms con 1000 animators) |
| TweenSystem | `engine/systems/tween_system.py` | Reflection setattr/getattr por frame | Acople total a objeto Python |
| ParallaxSystem | `engine/systems/parallax_system.py` | Matematica trivial (<20 capas) | Irrelevante para rendimiento |
| Light2DSystem | `engine/systems/light2d_system.py` | Render-bound (draw calls Raylib) | Bottleneck es GPU, no Python |
| TimerSystem | `engine/systems/timer_system.py` | Cuenta regresiva O(1) | Impacto despreciable |

La tabla 3.1 abarca 16 subsistemas que representan aproximadamente el 65-70 % de las lineas de codigo del repositorio. La decision de mantenerlos en Python no es conservadurismo: es una eleccion tecnica fundamentada en el perfil de carga de trabajo de cada subsistema. Los sistemas de animacion, tween, parallax y timer, por ejemplo, consumen colectivamente menos de 0.5 ms por frame incluso en escenas grandes; migrarlos a Rust generaria una complejidad de FFI desproporcionada para un beneficio medido en microsegundos. El sistema de scripting (`ScriptBehaviourSystem`, 417 lineas) es un caso limite de imposibilidad tecnica: utiliza `importlib` para hot reload, `eval` para resolucion de property paths y context passing dinamico a hooks Python, capacidades que no tienen equivalente directo en Rust sin embeber un interprete completo. De manera similar, el `EngineAPI` es la superficie de contacto con el mundo exterior: romperlo implicaria invalidar todos los juegos construidos sobre OpenGame, asi como los flujos de trabajo de los agentes de IA que dependen de `START_HERE_AI.md` como mapa de navegacion.

### 3.2 Responsabilidades Rust (migrar de forma selectiva)

Los subsistemas candidatos a Rust comparten tres características: (1) aparecen en rutas calientes del frame loop, (2) ejecutan cómputo numérico denso sobre datos planos, y (3) tienen una interfaz suficientemente acotada para encapsular la complejidad FFI en un adaptador dual con fallback Python.

La corrección clave es que **Rust no es la primera fase del refactor**. Antes de mover código a Rust hay que estabilizar tests, crear benchmarks base y agotar optimizaciones Python de bajo riesgo cuando el problema sea algorítmico. Rust se reserva para bucles calientes que sigan siendo costosos después de esas optimizaciones.

#### 3.2.1 Orden corregido por esfuerzo/beneficio

El orden recomendado es:

| Orden | Trabajo | Lenguaje recomendado | Motivo |
|---|---|---|---|
| 0 | Tests verdes, benchmarks base, CI mínimo | Python/infraestructura | Sin línea base no se puede atribuir mejora o regresión |
| 1 | Invalidación selectiva del query cache ECS | Python | Problema algorítmico; no necesita FFI |
| 2 | Benchmark y optimización inicial de `World.clone()` | Python | Afecta editor/PLAY; alto valor y alto riesgo de compatibilidad |
| 3 | Reducción de allocaciones/rebuilds por frame | Python | Bajo riesgo, mejora global |
| 4 | `SpatialHash2D` nativo | Rust/PyO3 | Primer candidato Rust por aislamiento e interfaz pequeña |
| 5 | Physics queries / area queries | Rust o Python según profiling | Evitar O(N²); quizá basta con índice espacial Python |
| 6 | Partículas o render prep | Rust/PyO3 | Buen candidato si hay muchos elementos por frame |
| 7 | ECS storage nativo parcial | Rust/PyO3 | Solo cuando la API Python ya esté estable y benchmarkeada |
| 8 | Rapier2D / Box2D avanzado | Rust/C++ binding | Solo con tests sólidos de física |
| 9 | PGS solver / IslandBuilder | Rust/PyO3 | No migrar hasta confirmar que sigue siendo hotspot real |

#### 3.2.2 SpatialHash2D: primer módulo Rust, no primera intervención

El `SpatialHash2D` (`engine/physics/spatial_hash.py`, ~130 líneas) sigue siendo el mejor candidato para validar PyO3 porque su API es pequeña y opera sobre datos numéricos. Sin embargo, ya no debe aparecer como “primera acción del plan”. Antes deben existir:

- benchmarks base de física y spatial queries;
- tests de equivalencia Python/Rust para `insert`, `remove`, `query`, `query_into`, `clear` y ray candidates;
- fallback Python probado;
- CI mínimo capaz de compilar o, como mínimo, saltar Rust sin romper el proyecto.

Solo con esa base se implementa la versión Rust.

#### 3.2.3 ECS queries: primero Python, después Rust si sigue siendo necesario

El sistema de queries del ECS (`World.get_entities_with()`) es un cuello de botella importante, pero la primera intervención debe ser Python-only: invalidar selectivamente las entradas del cache afectadas por el tipo de componente modificado, añadir métricas de hit/miss y reducir listas temporales. Esto es más barato y menos arriesgado que mover inmediatamente el storage a Rust.

Una migración Rust de sparse sets o storage SoA para componentes calientes (`Transform`, `Sprite`, `Collider`, `RigidBody`, `RenderOrder2D`) solo se justifica si, tras las optimizaciones Python, los benchmarks muestran que las queries siguen consumiendo una fracción significativa del frame.

#### 3.2.4 Física: Rapier2D/Box2D no deben entrar demasiado pronto

La integración de Rapier2D o Box2D como backend adicional puede ser valiosa, pero no debe ejecutarse en el primer mes salvo que ya existan tests de física muy sólidos. Antes de añadir un backend nuevo hay que estabilizar:

- contrato `PhysicsBackend`;
- tests de colisiones, raycasts, triggers, `move_and_slide` y determinismo;
- benchmarks de física legacy;
- tolerancias numéricas y fixtures comparables.

La física completa tiene demasiado riesgo para ser una migración temprana. Primero se migran queries o índices espaciales aislados. Después se evalúa backend externo.

#### 3.2.5 Render prep: candidato medio, no urgente

El render backend pyray/raylib no debe tocarse al principio. Si los benchmarks muestran coste real en preparación de render, Rust puede encargarse de culling, batching y generación de draw commands, manteniendo intacta la API de render en Python. Esta fase debe ir después de estabilizar ECS y tener benchmarks de `render_prep_10k_sprites`.

#### 3.2.6 Sistemas auxiliares: partículas, tilemap y pathfinding

Partículas CPU, tilemap culling y pathfinding son candidatos razonables a Rust porque son sistemas con datos planos y bucles repetitivos. Aun así, cada uno debe pasar por el mismo gate:

```text
benchmark base -> tests equivalencia -> implementación aislada -> fallback Python -> speedup ≥2x -> PR pequeño
```

#### Tabla 3.2: Subsistemas candidatos a Rust, corregidos por prioridad real

| Prioridad | Subsistema | Lenguaje/fase inicial | Cuándo mover a Rust |
|---|---|---|---|
| P0 | Tests, benchmarks, CI | Python/infraestructura | No aplica |
| P1 | Query cache ECS | Python | Solo si sigue siendo hotspot tras invalidación selectiva |
| P1 | `World.clone()` | Python | Solo si requiere storage nativo más adelante |
| P2 | `SpatialHash2D` | Rust/PyO3 | Primer módulo Rust tras Fase 0 y Fase 1 |
| P2 | Area queries / physics queries | Python o Rust | Según profiling posterior |
| P3 | Partículas CPU | Rust/PyO3 | Si hay escenas con miles de partículas |
| P3 | Render prep | Rust/PyO3 | Si `render_prep` supera el presupuesto de frame |
| P4 | ECS storage nativo | Rust/PyO3 | Cuando API y benchmarks ECS estén estables |
| P4 | Rapier2D/Box2D avanzado | Rust/C++ binding | Tras tests de física sólidos |
| P5 | PGS solver / IslandBuilder | Rust/PyO3 | Solo si sigue siendo cuello de botella medido |

# 4. Plan de Integración Rust/PyO3

La integración de Rust en OpenGame mediante PyO3 constituye el eje técnico central de esta refactorización. El motor, compuesto en un 97.7% por código Python, requiere acelerar subsistemas críticos sin interrumpir el flujo de desarrollo ni exigir a los usuarios finales la instalación de un toolchain de Rust. Este capítulo define la arquitectura de integración progresiva, el sistema de construcción, el patrón de fallback transparente, las estrategias de FFI eficiente y el plan de testing que garantiza la equivalencia funcional entre las implementaciones nativa y pura.

El principio rector es **opt-in, no opt-out**: el módulo nativo es una mejora opcional que el motor explota cuando está disponible, pero el sistema funciona íntegramente sin él. Esta decisión tiene implicaciones que atraviesan todos los aspectos del diseño, desde la estructura de directorios hasta la matriz de CI.

## 4.1 Estructura del Paquete

### 4.1.1 Layout del Workspace

La integración introduce un segundo raíz dentro del monorepo existente: el directorio `opengame_native/`, que aloja el crate Rust compilado como extensión Python via PyO3. Este directorio convive en el mismo repositorio que el código Python (`engine/`, `motor/`, `tests/`), manteniendo la coherencia de versiones y simplificando la integración en CI.

```
opengame/                          # Root del monorepo
├── pyproject.toml                 # Proyecto principal (setuptools)
├── engine/                        # Código Python existente
│   ├── ecs/                       # World, Entity, Component
│   ├── physics/                   # SpatialHash2D, backends, solvers
│   ├── systems/                   # 26+ sistemas (collision, particles, render)
│   ├── components/                # 40+ componentes serializables
│   ├── core/                      # Runtime loop, game loop
│   ├── api/                       # EngineAPI y sub-APIs
│   └── native/                    # ← NUEVO: Adaptadores Python
│       ├── __init__.py            # Detector NATIVE_AVAILABLE + loader
│       ├── spatial_hash.py        # Adaptador dual SpatialHash2D
│       ├── ecs_storage.py         # Adaptador dual ECS storage
│       ├── collision.py           # Adaptador dual collision system
│       ├── particles.py           # Adaptador dual particle system
│       ├── render_prep.py         # Adaptador dual render prep
│       ├── pathfinding.py         # Adaptador dual pathfinding
│       ├── _spatial_hash.py       # Fallback Python puro
│       ├── _ecs_storage.py        # Fallback Python puro
│       ├── _collision.py          # Fallback Python puro
│       ├── _particles.py          # Fallback Python puro
│       └── _ffi_types.py          # Tipos planos compartidos (structs FFI)
├── opengame_native/               # ← NUEVO: Crate Rust (maturin)
│   ├── Cargo.toml
│   ├── pyproject.toml             # Configuración maturin
│   ├── rust-toolchain.toml
│   └── src/
│       ├── lib.rs                 # Entry point: módulo Python, feature flags
│       ├── types.rs               # AABB, Vec2, Color (structs C-like)
│       ├── ffi.rs                 # Utilidades FFI (buffer conversion)
│       ├── ecs/
│       │   ├── mod.rs
│       │   ├── storage.rs         # SoA storage: arrays paralelos
│       │   ├── query.rs           # Query engine: intersección de máscaras
│       │   └── batch.rs           # Batch operations para FFI
│       ├── spatial/
│       │   ├── mod.rs
│       │   └── spatial_hash.rs    # SpatialHash2D nativo
│       ├── collision/
│       │   ├── mod.rs
│       │   ├── shapes.rs          # Circle, AABB, Capsule, Polygon
│       │   ├── narrow.rs          # SAT narrow-phase
│       │   ├── broad.rs           # AABB overlap + spatial hash
│       │   └── manifold.rs        # ContactManifold2D, ContactPoint2D
│       ├── particles/
│       │   ├── mod.rs
│       │   └── simulator.rs       # Particle pool, update, emit
│       ├── render/
│       │   ├── mod.rs
│       │   ├── culler.rs          # Frustum culling
│       │   └── sorter.rs          # Sort key computation
│       ├── pathfinding/
│       │   ├── mod.rs
│       │   └── grid.rs            # A* sobre grid 2D
│       └── math/
│           ├── mod.rs
│           ├── vec2.rs
│           └── aabb.rs
├── tests/
│   └── native/                    # Tests específicos de integración
│       ├── test_equivalence.py    # Tests Python vs Rust
│       ├── test_ffi.py            # Tests de boundary FFI
│       └── test_numerical.py      # Tests de tolerancia numérica
└── .github/workflows/
    ├── native-wheels.yml          # CI: build de wheels multiplataforma
    └── tests.yml                  # CI: tests dual pure/native
```

El layout preserva la separación de dominios en ambos lados de la frontera. Cada módulo Rust (`ecs/`, `spatial/`, `collision/`, `particles/`, `render/`, `pathfinding/`, `math/`) tiene su contraparte adaptadora en `engine/native/`, que actúa como único punto de contacto entre el código Python del motor y la extensión compilada. Esta simetría reduce la carga cognitiva del desarrollador: para entender qué hace `spatial_hash.rs` en Rust, basta con leer `engine/native/spatial_hash.py` en Python, que documenta la interfaz dual y la lógica de delegación.

### 4.1.2 Módulos Rust por Dominio

La priorización de módulos sigue el análisis de hotspots realizado en el Capítulo 3. `SpatialHash2D` encabeza la lista por su perfil de operaciones puramente numéricas con dict lookups intensivos (el archivo `engine/physics/spatial_hash.py`, de 130 líneas, realiza 3-4 lookups de diccionario por entidad insertada). Los queries ECS representan el segundo hotspot: `World.get_entities_with()` (líneas 366-403 de `engine/ecs/world.py`) ejecuta intersección de sets desde `_component_index` por cada sistema, en cada frame.

El módulo `math/` proporciona los tipos fundamentales (`Vec2`, `AABB`) que el resto de módulos consumen. Se define como crate interno dentro del workspace para que `spatial/`, `collision/` y `particles/` compartan la misma representación de datos sin duplicación. Los tipos se diseñan como structs C-like con layout contiguo en memoria, facilitando la serialización a arrays planos para cruce FFI.

## 4.2 Build System y Packaging

### 4.2.1 Maturin como Build Tool

La elección del sistema de construcción recae sobre **maturin** en lugar de `setuptools-rust`. Maturin implementa PEP 517 nativamente, lo que permite que `pip install` compile automáticamente el crate Rust sin configuración adicional por parte del usuario. En el ciclo de desarrollo, `maturin develop` compila e instala la extensión en el entorno virtual activo en 2-5 segundos (modo debug) o 15-30 segundos (modo release), eliminando la fricción de alternar entre lenguajes durante la iteración.

| Criterio | Maturin | setuptools-rust | Decisión |
|---|---|---|---|
| PEP 517 compliant | Nativo | Requiere pasos extra | maturin |
| Cross-compilación | Excelente (cibuildwheel) | Posible pero manual | maturin |
| Desarrollo iterativo | `maturin develop` (instantáneo) | `pip install -e` + compilación | maturin |
| Wheels multiplataforma | Automatizado via CI | Scripts adicionales requeridos | maturin |
| Wheels Windows/macOS | Automatizado via CI | Requiere configuración manual | maturin |
| Experiencia developer | Instalar Rust, `maturin develop`, listo | Más configuración inherente | maturin |

La decisión por maturin no introduce dependencias adicionales en el runtime del usuario: el wheel generado es una extensión binaria autocontenida que solo requiere la ABI de CPython correspondiente. Para el perfil de release, el `Cargo.toml` del crate configura `lto = "fat"`, `codegen-units = 1`, `panic = "abort"` y `strip = true`, produciendo un binario optimizado para tamaño y velocidad.

El `pyproject.toml` del crate declara `requires-python = ">=3.11"`, alineándose con el requisito mínimo del proyecto principal. La feature `pyo3/extension-module` se activa siempre, mientras que `parallel` (que habilita rayon) y `numpy` (para zero-copy buffers) son features opcionales que el adaptador Python puede consultar en tiempo de ejecución.

### 4.2.2 CI Multiplataforma

El pipeline de GitHub Actions se divide en dos flujos. El primero, `native-wheels.yml`, se dispara en tags con prefijo `native-v*` y construye wheels para Linux (manylinux2014, compatible con la mayoría de distribuciones), macOS (x86_64 y arm64 universal) y Windows (x64). Usa `PyO3/maturin-action@v1` que abstrae la complejidad de los toolchains de cada plataforma. El segundo flujo, `tests.yml`, ejecuta la suite de tests completa en matriz OS × Python × modo (pure/native), asegurando que ni la integración ni el fallback se degradan silenciosamente.

### 4.2.3 Instalación para el Usuario

Tres escenarios de instalación cubren el espectro de usuarios. El usuario común ejecuta `pip install opengame[native]`, que descarga el wheel precompilado para su plataforma y versión de Python sin requerir toolchain Rust. Si no existe wheel compatible, pip intenta compilar desde sdist; si la compilación falla, el motor funciona con el fallback Python automáticamente. El desarrollador clona el repositorio, ejecuta `pip install -e ".[dev,native]"` y luego `maturin develop --release` dentro de `opengame_native/` para tener la extensión nativa en su entorno de trabajo. Esta progresión —wheel, sdist, fallback— garantiza que ningún usuario queda bloqueado por una limitación de plataforma.

## 4.3 Patrón de Fallback

### 4.3.1 Detector Centralizado

El punto neuralgico de la dualidad nativo/puro reside en `engine/native/__init__.py`. Al importarse el módulo, intenta cargar `opengame_native` dentro de un bloque `try/except ImportError`. Si la carga tiene éxito, la variable `NATIVE_AVAILABLE` recibe `True` y se captura la versión del módulo. Si falla —porque el wheel no existe para la plataforma, porque el usuario no tiene Rust instalado, o porque se ha configurado explícitamente `OPENGAME_FORCE_PURE=1`— la variable permanece en `False` y todas las importaciones subsiguientes del motor siguen rutas Python puras. Este mecanismo opera en tiempo de importación, antes de que cualquier sistema del motor solicite funcionalidad acelerada, eliminando cualquier latencia de detección en el game loop.

El adaptador también implementa un contrato de versiones: exporta `NATIVE_API_VERSION` como constante entera. Cuando el módulo nativo se carga con éxito, el adaptador verifica que `opengame_native.API_VERSION` coincida con el valor esperado. Si difieren —por ejemplo, tras una actualización parcial del motor sin actualizar el crate— el adaptador emite un `RuntimeWarning` y trata la discrepancia como si el módulo no estuviera disponible, forzando el fallback. Esta verificación previene crashes difíciles de diagnosticar que surgirían si Python y Rust interpretan los buffers de FFI con layouts incompatibles.

### 4.3.2 Adaptador por Módulo

Cada subsistema acelerado expone una única clase Python que encapsula la decisión nativo/puro. Tomando `SpatialHash2D` como referencia (el primer módulo migrado según el roadmap), el adaptador en `engine/native/spatial_hash.py` define una clase cuyo `__init__` consulta `get_native()` del detector central. Si el módulo nativo está disponible, instancia `native.SpatialHash2D(...)` como backend; de lo contrario, importa `_SpatialHash2DPython` desde `engine/native/_spatial_hash.py`. Todos los métodos públicos (`insert`, `query`, `query_ray_candidates`, `clear`, `reset`) delegan directamente a `self._backend`, sin bifurcación lógica adicional.

Esta encapsulación garantiza que el resto del motor —`CollisionSystem`, `RenderSystem`, `RuntimeAPI`— no contiene referencias explícitas a `opengame_native`. Los sistemas interactúan con `engine.native.spatial_hash.SpatialHash2D` exactamente como interactuaban con `engine.physics.spatial_hash.SpatialHash2D` antes de la refactorización. La única diferencia observable es el rendimiento: el conjunto de IDs retornado por `query()` es idéntico independientemente del backend activo.

### 4.3.3 Snapshot-Compute-Publish

El patrón que gobierna toda interacción a través de la frontera FFI se denomina **Snapshot-Compute-Publish**. Python nunca pasa objetos vivos (`Entity`, `Component`, `RigidBody`) a Rust. En su lugar, el adaptador extrae datos planos —posiciones, AABBs, flags de activación— en arrays de structs C-like. Este es el paso **Snapshot**. Los arrays cruzan la frontera FFI en una única llamada, Rust procesa el cómputo (spatial hash, queries de colisión, sorting) y retorna resultados como arrays de IDs o structs planos. Este es el paso **Compute**. Finalmente, Python interpreta los IDs retornados, mapeándolos de vuelta a objetos `Entity` mediante `world.get_entity(entity_id)`, y aplica los resultados (contactos, eventos, comandos de render). Este es el paso **Publish**.

Este diseño evita el estado compartido mutable cruzado, que es fuente de race conditions y complicaciones con el GIL. Rust no mantiene referencias a objetos Python entre llamadas; cada frame comienza con un snapshot limpio y termina con resultados descartables. La invariante clave es: **datos planos entran, resultados planos salen; Rust no conserva estado Python**.

## 4.4 Estrategia FFI Eficiente

### 4.4.1 Minimizar Cruces FFI

Cada cruce Python → Rust via PyO3 introduce un overhead de aproximadamente 50-200 nanosegundos más el costo de conversión de argumentos. En un frame con 60 sistemas, si cada sistema realiza 1000 llamadas individuales, el overhead acumulado alcanza 3-12 milisegundos, una cifra peligrosa para mantener 60 FPS (16.67 ms por frame). La estrategia correcta reduce esto a 60 llamadas batch por frame, totalizando 3-12 microsegundos, cantidad insignificante.

La regla práctica es: **un cruce FFI por sistema por frame**. En lugar de llamar `spatial_hash.insert(entity_id, aabb)` 1000 veces, el adaptador acumula todas las inserciones en un array plano (`[id0, l0, t0, r0, b0, id1, l1, t1, r1, b1, ...]`) y ejecuta `insert_batch(flat_array)` una sola vez. Los sistemas del motor se refactorizan para operar en este modo: preparan datos, invocan una operación batch, reciben resultados batch.

### 4.4.2 Tipos de Datos y Buffers

Los datos cruzan la frontera como listas de tuplas Python convertidas a structs Rust, o como arrays NumPy cuando se activa la feature `numpy`. Para buffers grandes —posiciones de 10,000 entidades, estados de 100,000 partículas— el uso de `numpy::PyReadonlyArray2<f32>` en Rust permite acceso zero-copy sin copia intermedia. El fallback Python ignora completamente NumPy y opera con listas normales, manteniendo la compatibilidad para entornos sin SciPy instalado.

Los structs planos compartidos se definen en `engine/native/_ffi_types.py` como `NamedTuple` (ej: `AABB = NamedTuple('AABB', [('left', float), ('top', float), ('right', float), ('bottom', float)])`). Rust define los equivalentes como structs `#[repr(C)]`. Ambos lados acuerdan el layout en memoria por convención, no por serialización explícita en cada llamada, eliminando overhead de marshalling.

### 4.4.3 Paralelismo Controlado

Rust utiliza **rayon** para data parallelism dentro de los computos batch (intersección de AABBs, sorting de entidades, actualización de partículas). Críticamente, esto ocurre sin involucrar threads de Python: el GIL se libera durante la llamada FFI y rayon distribuye el trabajo sobre los cores disponibles desde Rust. La feature `parallel` se incluye por defecto pero puede desactivarse compilando sin ella, lo que fuerza ejecución secuencial en Rust. Esto es útil para debugging o para plataformas donde el threading de rayon presente problemas. El adaptador Python puede detectar si la feature está disponible consultando `hasattr(opengame_native, 'PARALLEL_ENABLED')`.

## 4.5 Testing de la Integración

### 4.5.1 Tests de Equivalencia

La premisa innegociable de la integración es que el mismo input produce el mismo output en ambas implementaciones. La suite `tests/native/test_equivalence.py` verifica esta invariante para cada módulo migrado. Para `SpatialHash2D`, el test genera 100 AABBs aleatorias con semilla fija, las inserta tanto en la instancia nativa como en la pura, ejecuta 20 queries AABB aleatorios, y verifica que los sets de IDs retornados sean idénticos (diferencia simétrica vacía). Para el sistema de colisiones, se construye una escena con entidades en posiciones conocidas, se ejecuta el broad-phase nativo y el puro, y se comparan los pares `(entity_a_id, entity_b_id)` detectados.

Los tests de equivalencia usan **hypothesis** para generación property-based cuando el dominio lo permite, y semillas fijas (`random.Random(42)`) para reproducibilidad en casos deterministas. Cada test anota el backend activo en el reporte de pytest, facilitando la identificación de divergencias.

### 4.5.2 CI Dual

El pipeline de integración continua ejecuta la suite completa dos veces: una con `pytest --pure` (forzando `OPENGAME_FORCE_PURE=1`) y otra con `pytest --native` (permitiendo carga del módulo nativo si está disponible). Los tests Python puros son obligatorios y deben reportar 0 fallas en todas las plataformas. Los tests nativos se marcan como opcionales en plataformas donde el wheel no se ha generado aún, pero se vuelven obligatorios en Linux x64 una vez que el pipeline de wheels produce el artefacto correspondiente.

Esta configuración garantiza que el fallback Python nunca se rompe como consecuencia de un cambio en el crate Rust. Si un desarrollador modifica la interfaz FFI sin actualizar el fallback, los tests `--pure` fallan inmediatamente, bloqueando el merge.

### 4.5.3 Tolerancias Numéricas

No todas las divergencias entre Python y Rust constituyen errores. Las operaciones de punto flotante pueden producir resultados ligeramente diferentes debido al orden de evaluación, optimizaciones del compilador Rust, o el uso de instrucciones SIMD. El plan de testing define tolerancias explícitas por categoría de dato.

| Categoría | Tolerancia | Aplica a |
|---|---|---|
| Enteros / IDs | Exacto (0) | entity_id, conteos de entidades, draw_calls, batches |
| Posiciones y velocidades | `abs_diff < 0.001` | Transform.x/y post-integración, hit points de raycast |
| Velocity solve PGS | `abs_diff < 0.001` | Velocidades post-solve, impulses de joints |
| Position solve PGS | `abs_diff < 0.01` | Posiciones post-position-solve (3 iteraciones acumulan error) |
| Transform puro | `abs_diff < 1e-9` | Coordenadas tras operaciones algebraicas sin física |
| Render metrics | Exacto (0) | Número de render_entities, draw_calls, sprite_batches |

La categoría de tolerancia relajada para position solve (0.01 en lugar de 0.001) reconoce que el solver PGS (Projected Gauss-Seidel) acumula error numérico a través de sus iteraciones, y pequeñas diferencias en el orden de procesamiento de contactos entre Python y Rust se amplifican ligeramente. Estas tolerancias se codifican como constantes en `tests/native/test_numerical.py` y se usan en todos los assertions de punto flotante cruzados.

El test `test_numerical.py` proporciona helpers estandarizados: `assert_float_equal(a, b, rel_tol, abs_tol)` y `assert_aabb_equal(a, b, rel_tol)`. Cuando un test de equivalencia falla con una diferencia dentro de la tolerancia permitida, el desarrollador ajusta el assertion al helper correspondiente en lugar de intentar forzar la coincidencia bit-exact, que sería una batalla contra las propiedades de la aritmética de punto flotante.

---

La integración Rust/PyO3, tal como se describe en este capítulo, constituye una refactorización de riesgo controlado. Cada decisión arquitectónica —desde el layout de directorios hasta las tolerancias numéricas de testing— está diseñada para preservar el comportamiento observable del motor mientras se introducen ganancias de rendimiento progresivas. El patrón de fallback transparente asegura que ningún usuario queda excluido; la estrategia de batching mínimo garantiza que el overhead de la frontera de lenguajes nunca consume las ganancias que Rust proporciona; y la suite de testing dual impide la divergencia silenciosa entre implementaciones. El resultado es un motor que funciona íntegramente en Python puro, pero que se acelera automáticamente cuando las condiciones lo permiten.

---


# 5. Plan ECS

## 5.1 Diagnostico del ECS Actual

### 5.1.1 Storage Entity-Centric sin Centralizacion

El ECS de OpenGame emplea un modelo de almacenamiento **entity-centric** en el que cada instancia de `Entity` mantiene sus componentes en un diccionario privado `_components: dict[type, Component]`, localizado en `engine/ecs/entity.py` (lineas 1-323). Este diseño implica que los componentes viven dispersos en el heap de Python, cada uno como un objeto independiente accesible unicamente a traves de su entidad contenedora. No existe un `ComponentStorage` centralizado que agrupe componentes del mismo tipo en memoria contigua. La clase `World`, definida en `engine/ecs/world.py` (763 lineas), actua como contenedor de entidades pero no como gestor de componentes: su indice `_entities: dict[int, Entity]` (linea 168) mapea identificadores a objetos `Entity`, y la indireccion para acceder a un componente requiere siempre `World -> Entity -> dict[type, Component] -> Component`, lo que constituye tres niveles de indireccion obligatorios en la ruta caliente de cada sistema.

La ausencia de storage centralizado tiene una consecuencia directa sobre la localidad de cache: al iterar, por ejemplo, los 500 componentes `Transform` de una escena mediana, el motor accede a 500 objetos Python distribuidos arbitrariamente en memoria. Un ECS arquetipico o basado en SparseSets evitaria esta dispersion agrupando los componentes por tipo en arrays densos, permitiendo que la CPU precargue datos adyacentes en las lineas de cache L1/L2. En el estado actual, cada `get_component()` genera potencialmente un cache miss, cuyo coste no es medible directamente desde Python pero cuyo efecto acumulado se manifiesta en la latencia de iteracion de sistemas como `RenderSystem` y `PhysicsSystem`.

### 5.1.2 Indices del World y Query Cache

`World` mantiene cinco estructuras de indice que duplican parcialmente la informacion ya presente en las entidades. El indice primario es `_component_index: dict[type, set[int]]` (linea 172 de `world.py`), que mapea un tipo de componente al conjunto de identificadores de entidades que lo poseen. Este indice soporta la operacion `get_entities_with()` mediante interseccion de sets. El indice secundario `_component_owner_index: dict[int, int]` (linea 173) permite hallar la entidad propietaria de una instancia de componente dada su identidad de objeto Python (`id(component)`), usado principalmente en `get_entity_by_component_instance()`.

El query cache `_component_query_cache: dict[tuple[type, ...], tuple[int, ...]]` (linea 174) almacena el resultado materializado de queries previas como una tupla ordenada de identificadores de entidad. Sin embargo, este cache presenta un defecto de diseno critico: las funciones `_index_component()` y `_deindex_component()` (lineas 580-592) invocan `self._component_query_cache.clear()` en cada operacion de adicion o remocion de componente, independientemente del tipo afectado. Esto significa que si un spawner anade cinco entidades con el componente `Bullet` en un frame, todas las queries cacheadas —incluidas aquellas que solo involucran `Transform` y `Sprite`— se invalidan simultaneamente. En escenas con entidades temporales, particulas o spawners activos, la tasa de aciertos del cache cae a niveles cercanos al 0%, convirtiendo cada `get_entities_with()` en una reconstruccion de interseccion de sets.

Adicionalmente, `World` mantiene `_entities_by_component: dict[type, list[Entity]]` (linea 178), un indice LEGACY que almacena listas de referencias a objetos `Entity` por tipo. Las funciones `_legacy_add_component_entity()` y `_legacy_remove_component_entity()` (lineas 598-610) actualizan este indice sincronicamente con `_component_index`, duplicando el trabajo de indexacion en cada operacion. Este doble indice existe "por compatibilidad" con codigo de tests y sistemas antiguos que acceden directamente al campo.

### 5.1.3 Costes Operativos Cuantificados

Las operaciones del ECS presentan costes bien definidos que determinan los cuellos de botella del motor. El `get_component(exact_type)` resuelve en O(1) mediante `Entity._components.get(component_type)`, pero la ruta de acceso completa atraviesa tres niveles de indireccion (`World._entities[entity_id]` -> `Entity._components[component_type]` -> objeto Component). Cuando el tipo solicitado no coincide exactamente con la clave registrada, `Entity.get_component()` cae en una busqueda lineal O(n) sobre todos los componentes de la entidad, verificando `issubclass(registered_type, component_type)` para cada tipo registrado. En una entidad con ocho componentes, este fallback implica hasta ocho llamadas a `issubclass()`.

La operacion `clone()` para la transicion EDIT->PLAY es el cuello de botella principal. `World.clone()` (lineas 430-462) itera todas las entidades, y para cada componente invoca `_clone_component()` (lineas 477-495), que primero intenta `component.clone()` —el cual ejecuta `to_dict() -> clone_json_value() -> from_dict()`— y luego `copy.deepcopy()` como fallback. Una escena de 10.000 entidades con cinco componentes cada una genera 50.000 serializaciones a diccionario seguidas de 50.000 deserializaciones. El benchmark interno `play_mode_clone_stress` mide este coste en rangos de 200 ms a 2 segundos segun el hardware y la complejidad de los componentes. A titulo comparativo, un `Transform` con seis campos float se clona via JSON en lugar de una simple copia de estructura, incurriendo un coste 10x a 50x superior al necesario.

En un frame tipico de una escena de 1.000 entidades con 500 visibles y 100 dinamicas, el motor ejecuta aproximadamente 4.000 a 8.000 llamadas a `get_component()`: ~2.000 desde `RenderSystem` (500 entidades x 4 componentes), ~1.000 desde `PhysicsSystem` (100 dinamicas x 10 accesos por iteracion del solver), y ~1.000 desde `CollisionSystem`. Ninguno de estos accesos aprovecha la localidad de cache ni arrays contiguos.

## 5.2 Fase A: Optimizacion Python Segura (después de Fase 0)

### 5.2.1 Invalidacion Selectiva del Query Cache

La primera optimizacion ataca el defecto de invalidacion global del cache. En lugar de `_component_query_cache.clear()` en cada `_index_component()` y `_deindex_component()`, se implementa un indice inverso `dict[type, set[tuple[type, ...]]]` que registra, para cada tipo de componente, que queries (identificadas por su tupla de tipos) lo incluyen. Cuando se indexa un componente de tipo T, solo se invalidan las entradas del cache cuya key contiene T. Un spawner de balas que anade entidades con el componente `Bullet` ya no invalidara la query `(Transform, Sprite)` que usa `RenderSystem`, permitiendo que esta ultima mantenga su cache activo entre frames.

La implementacion requiere modificar exclusivamente las lineas 580-592 de `world.py`. Se mantiene intacta la estructura `_component_query_cache` y su semantica de acceso en `get_entities_with()`. El cambio solo afecta el momento en que las entradas se marcan como obsoletas. El riesgo es bajo porque no se modifica el mecanismo de caching, unicamente la granularidad de su invalidacion.

### 5.2.2 Validacion por Version

Complementariamente a la invalidacion selectiva, se introduce un sistema de versionado por tipo: `_component_type_versions: dict[type, int]` almacena un contador monotonico para cada tipo. El query cache almacena pares `(resultado, version_tuple)` donde `version_tuple` contiene las versiones de cada tipo en la query. La validacion de cache se reduce a una comparacion de tuplas de enteros en O(1), sin necesidad de invalidacion explicita. Cuando `get_entities_with(T1, T2)` consulta el cache, verifica que las versiones actuales de T1 y T2 coincidan con las almacenadas; si no, reconstruye el resultado y actualiza la entrada.

Este mecanismo elimina por completo la necesidad de `_component_query_cache.clear()` e incluso del indice inverso de invalidacion selectiva, aunque ambos pueden coexistir. La version del world ya existe como `_version`, `_structure_version` y versiones especificas por dominio (`_transform_version`, `_render_version`, `_physics_version`); la extension a versiones por tipo de componente es un refinamiento natural del mecanismo ya presente.

### 5.2.3 Fast Clone via copy.copy()

La optimizacion de clonado introduce un contrato de copia rapida para componentes simples. En `_clone_component()` (linea 477), antes de invocar `component.clone()` —que siempre pasa por serializacion JSON— se intenta `copy.copy(component)` para aquellos componentes que implementan el metodo `__copy__()` o que son identificados como "seguros para copia superficial". Los componentes `Transform` (seis campos float) y `Sprite` (referencias a textura, tinta, dimensiones) son candidatos inmediatos: carecen de estado mutable compartido y pueden clonarse correctamente mediante una copia de miembros.

Esta optimizacion se habilita mediante una whitelist de componentes safe-for-fast-clone. El fallback a `component.clone()` via JSON permanece como garantia para componentes con grafos de referencias complejas. El impacto esperado es una reduccion del tiempo de `clone()` en un factor de 2x a 5x para escenas donde la mayoria de componentes son simples (el caso tipico).

### 5.2.4 Batching de Notificaciones

Cada operacion sobre un componente genera una notificacion sincronica a `World` via `_notify_owner_world()`. Durante un spawn de prefab con 10 entidades y 5 componentes cada una, se generan 50 notificaciones individuales, cada una actualizando indices e invalidando cache. `Entity` ya posee el campo `_notifications_suspended` (usado durante `__init__`), pero no existe API publica para controlarlo.

Se expone `entity.suspend_notifications()` / `entity.resume_notifications()` como metodos publicos, junto con un context manager `world.batch_operation()` que suspende notificaciones durante su bloque y emite una unica notificacion de consolidacion al salir. El `PrefabSpawner` y el cargador de escenas usan este mecanismo, reduciendo 50 notificaciones a una sola sincronizacion final. Esta optimizacion es opt-in y no afecta el comportamiento de sistemas existentes.

## 5.3 Fase B: Storage Mejorado Python (solo tras benchmarks ECS)

### 5.3.1 ComponentStorage Centralizado

La fase B introduce la abstraccion `ComponentStorage`, una clase que extrae el almacenamiento de componentes desde las entidades individuales hacia una estructura centralizada en `World`. `ComponentStorage` mantiene `dict[type, dict[int, Component]]` —por tipo de componente, un mapa de entity_id a instancia. Los componentes del mismo tipo dejan de dispersarse en el heap y se agrupan logicamente en el mismo diccionario interno, facilitando la iteracion por tipo sin pasar por entidades intermedias.

`Entity._components` se convierte en una vista o proxy sobre `ComponentStorage`. Los metodos publicos `Entity.add_component()`, `Entity.get_component()` y `Entity.remove_component()` conservan sus firmas y comportamiento, pero internamente delegan a `world._storage.get_component(entity_id, component_type)`. La migracion de componentes existentes al nuevo storage ocurre transparentemente la primera vez que una entidad registrada en un `World` accede a sus componentes. Los 26+ sistemas del motor no requieren modificacion porque la API publica no cambia.

El riesgo principal es que `Entity` requiere referencia a `World` para resolver operaciones de componentes. `Entity` ya mantiene `_owner_world` (linea 295 de `world.py`); la dependencia existe pero se intensifica. Para entidades sin world asignado, `Entity._components` opera en modo cache local que se sincroniza con el storage cuando la entidad es adoptada por un `World`.

### 5.3.2 Indice de Arquetipos

Un arquetipo (archetype) se define como el conjunto de tipos de componentes que posee una entidad. Se introduce `ArchetypeRegistry`, que mantiene un mapa `frozenset[type] -> Archetype`, donde cada `Archetype` almacena el conjunto de identificadores de entidades que comparten exactamente los mismos componentes. Cuando una entidad anade o remueve un componente, se recalcula su firma de tipos (`frozenset(entity._components.keys())`) y se traslada al arquetipo correspondiente.

Para `get_entities_with(T1, T2, T3)`, el sistema localiza los arquetipos cuyo conjunto de tipos es superconjunto de `{T1, T2, T3}` y devuelve la union de sus entidades. Los 26 sistemas del motor usan queries fijas: `RenderSystem` siempre consulta `(Transform, Sprite, RenderOrder2D)`, `PhysicsSystem` consulta `(Transform, RigidBody)` y `(Transform, Collider)`. Con arquetipos, estas queries pasan de calcular intersecciones de sets en cada frame a realizar una union de arquetipos previamente identificados, reduciendo el coste de O(min(s1, s2, s3)) a O(1) para queries estables.

### 5.3.3 Iteracion Directa por Tipo

Se anade el metodo `world.iter_components(component_type) -> Iterable[Component]` que itera directamente sobre `self._storage[component_type].values()`, sin materializar la lista de entidades intermedias. Un sistema de particulas puede recorrer todos los `ParticleEmitter2D` accediendo a los componentes directamente, sin ejecutar `get_entities_with()` ni `entity.get_component()`. Este metodo es aditivo: no modifica ningun sistema existente, pero proporciona una ruta optima para sistemas nuevos o refactorizados que beneficien la iteracion directa.

La siguiente tabla resume las tres fases del plan ECS, sus alcances temporales, riesgos y objetivos de rendimiento.

| Fase | Alcance | Duracion | Riesgo | Objetivo Principal | Metrica de Exito |
|------|---------|----------|--------|-------------------|-----------------|
| A | Optimizaciones Python sin cambiar storage | Tras Fase 0 | Bajo | Invalidacion selectiva de cache, fast clone, batching | Cache hit rate > 85%, clone 10k < 400 ms |
| B | Storage mejorado en Python puro | Tras benchmarks ECS | Medio | ComponentStorage centralizado, arquetipos, iteracion directa | Query O(1) para sistemas estables, clone 10k < 200 ms |
| C | Storage nativo via PyO3/Rust | Mes 2+ si se justifica | Alto | SparseSet para componentes calientes, SoA para numericos | 10-50x en iteracion de Transform y RigidBody |

La eleccion de una estructura de tres fases responde al principio de que cada fase debe demostrar mejora medible antes de iniciar la siguiente. La fase A es puramente local: modifica logica de invalidacion y rutas de clonado sin alterar donde viven los datos. La fase B reestructura el almacenamiento pero permanece dentro de Python, manteniendo la compatibilidad de build y debugging. La fase C introduce dependencias nativas y solo se justifica si los benchmarks de la fase B no alcanzan los umbrales de rendimiento requeridos para escenas mayores a 50.000 entidades. Este enfoque incremental asegura que, en el peor caso de una fase C fallida, las fases A y B ya habran producido mejoras sustanciales con codigo reversible.

## 5.4 Fase C: Storage Nativo Componentes Calientes (mes 2+ si el profiling lo justifica)

### 5.4.1 SparseSet en Rust/PyO3 para Componentes Numericos

La fase C migra los tipos de componentes mas accedidos a un `SparseSet` implementado en Rust con bindings PyO3. Un SparseSet es una estructura que combina un array denso (contiguo en memoria) con un array esparso (sparse) de indices, permitiendo acceso O(1) por entity_id e iteracion secuencial cache-friendly. Para cada tipo migrado, el SparseSet almacena: `dense: Vec<Component>` con los componentes ordenados secuencialmente, `sparse: Vec<u32>` donde `sparse[entity_id]` indica el indice en `dense` o `u32::MAX` si la entidad no tiene ese componente, y `entity_ids: Vec<u32>` con los identificadores correspondientes a cada posicion de `dense`.

Los tipos objetivo se seleccionan por frecuencia de acceso medida en el analisis estatico de los sistemas criticos. `Transform` lidera con ~3.000 a 6.000 accesos por frame, seguido de `Sprite` (~1.000-3.000), `Collider` (~500-1.500), `RigidBody` (~300-800) y `RenderOrder2D` (~1.000-2.000). Cada uno de estos componentes se beneficia de la localidad de cache que proporciona un array denso: iterar 1.000 `Transform` en un SparseSet Rust implica un recorrido lineal de memoria contigua, mientras que la iteracion actual requiere 1.000 lookups en diccionarios Python.

El modulo PyO3 expone operaciones basicas: `insert(entity_id, component)`, `get(entity_id) -> component`, `remove(entity_id)` e `iter() -> iterator`. Los componentes Python se serializan a una representacion de bytes plana al insertar y se reconstruyen al extraer, usando el contrato `to_dict()`/`from_dict()` ya existente para la conversion.

### 5.4.2 SoA Nativo para Campos Numericos

Para `Transform` y `RigidBody`, la migracion va un paso mas alla: en lugar de almacenar objetos componente completos, se descompone en arrays paralelos de tipos primitivos. Un `NativeTransformSoA` mantiene `pos_x: Vec<f32>`, `pos_y: Vec<f32>`, `rotation: Vec<f32>`, `scale_x: Vec<f32>`, `scale_y: Vec<f32>`, indexados por `entity_id`. De forma similar, `NativeRigidBodySoA` almacena `velocity_x`, `velocity_y`, `angular_velocity`, `mass` y `inv_mass`. Los sistemas de fisica y render pueden actualizar lotes de entidades con una sola llamada FFI que procesa los arrays en Rust, vectorizando operaciones que en Python requieren un loop por entidad.

### 5.4.3 Orden de Migracion de Componentes

El orden de migracion se determina por la relacion entre frecuencia de acceso, impacto en sistemas y complejidad de implementacion. No todos los componentes justifican la inversion de migracion a Rust; algunos permaneceran en storage Python incluso tras completar la fase C.

| Prioridad | Componente | Est. get_component()/frame | Sistemas afectados | Complejidad de migracion | Justificacion |
|-----------|-----------|---------------------------|-------------------|------------------------|---------------|
| 1 | Transform | 3.000-6.000 | Render, Physics, Collision, UI, Camera | Media | Accedido por toda entidad visible y dinamica. Impacto transversal. SoA posible. |
| 2 | Sprite + RenderOrder2D + RenderStyle2D | 2.000-5.000 (conjunto) | RenderSystem | Media | Familia render. Migracion conjunta permite iteracion batchada del RenderSystem sin lookups intermedios. |
| 3 | Collider + RigidBody | 800-2.300 | PhysicsSystem, CollisionSystem | Alta | Requieren sincronizacion con SpatialHash2D y PGS solver. Los campos numericos (velocidad, masa) son candidatos a SoA. |
| 4 | Animator | 500-1.000 | AnimatorSystem | Baja | Frecuencia media pero beneficioso para batching de actualizacion de frames de animacion. |
| 5 | Camera2D | 1-5 | RenderSystem | Baja | Una o pocas entidades, pero accedido en ruta critica de render. |
| 6-10 | Resto (Polygon2D, StaticBody2D, etc.) | <500 cada uno | Sistemas especificos | Variable | No se migran salvo que los benchmarks lo justifiquen. Permanecen en storage Python de la fase B. |

La tabla anterior prioriza `Transform` en primer lugar porque casi todos los sistemas lo utilizan: `RenderSystem` lo lee para posicionar sprites, `PhysicsSystem` lo modifica para integrar movimiento, `CollisionSystem` lo consulta para construir AABBs, y `Camera2D` depende de el para el view transform. Migrar `Transform` a SparseSet nativo beneficia simultaneamente a los tres sistemas criticos del motor. La familia render (`Sprite`, `RenderOrder2D`, `RenderStyle2D`) se agrupa en segundo lugar porque el `RenderSystem` itera los tres componentes secuencialmente para cada entidad visible; tenerlos en un arquetipo nativo permite que el sistema de renderizado recorra un unico array denso de "entidades renderizables" sin interseccion de sets. `Collider` y `RigidBody` ocupan el tercer lugar por su alta complejidad de sincronizacion: el PGS solver en `contact_solver.py` accede directamente a campos de `RigidBody` (`velocity_x`, `velocity_y`, `angular_velocity`, `mass`) durante las 8 iteraciones de velocidad por frame, y el `PhysicsSystem` actualiza `Transform` tras la integracion.

## 5.5 Riesgos y Compatibilidad

### 5.5.1 API Publica Estable

El contrato publico del ECS no cambia en ninguna de las tres fases. Los metodos `World.create_entity()`, `World.add_entity()`, `World.get_entity()`, `World.get_entities_with()`, `Entity.add_component()`, `Entity.get_component()`, `Entity.has_component()` y `Entity.remove_component()` mantienen sus firmas exactas y semantica de retorno. Los 26+ sistemas que dependen del ECS —incluyendo `RenderSystem`, `PhysicsSystem`, `CollisionSystem`, `AnimatorSystem`, `AudioSystem`, `UISystem`, `CharacterControllerSystem`, `ScriptBehaviourSystem`, `GPUParticlesSystem` y `NavigationAgent2DSystem`— operan sin modificacion.

### 5.5.2 Serializacion Scene v2

El formato de serializacion de escenas (Schema v2) permanece inmutable. `World.serialize()` recorre todas las entidades llamando `component.to_dict()` y `World.deserialize()` invoca `component.from_dict()`. Ni la estructura de almacenamiento subyacente ni la presencia de SparseSets nativos modifican este contrato: la serializacion siempre parte de la representacion Python de los componentes, independientemente de si estan almacenados en un dict de `Entity`, un `ComponentStorage`, o un SparseSet Rust. Las escenas existentes se cargan y guardan sin cambios.

### 5.5.3 Sistemas Dependientes

El impacto sobre los 26 sistemas se mitiga mediante una estrategia de compatibilidad dual: cada cambio al ECS se implementa como una nueva ruta de ejecucion con fallback a la ruta legacy. Por ejemplo, `get_entities_with()` primero consulta el indice de arquetipos (fase B) y, si este no esta disponible o no tiene resultado, cae al mecanismo actual de interseccion de sets. Los metodos `_legacy_add_component_entity()` y `_legacy_remove_component_entity()` se mantienen activos durante toda la fase B para asegurar que codigo que accede directamente a `_entities_by_component` continue funcionando. Cada optimizacion se habilita mediante un feature flag (por ejemplo, `world._enable_feature("selective_cache_invalidation")`) que permite rollback inmediato si un sistema presenta regresiones.

---

# 6. Plan de Fisica

## 6.1 Estado Actual

### 6.1.1 LegacyAABBPhysicsBackend: Motor Completo en Python

El sistema de fisica de OpenGame opera sobre una arquitectura de backend dual con contrato ABC (`PhysicsBackend` en `engine/physics/backend.py`). El backend `legacy_aabb`, implementado en `engine/physics/legacy_backend.py` (~1.500 lineas), no es un motor de fisica monolitico sino un adaptador que orquesta dos sistemas independientes: `PhysicsSystem` (`engine/systems/physics_system.py`, 1.913 lineas) para resolucion de cuerpos rigidos y `CollisionSystem` (`engine/systems/collision_system.py`, 864 lineas) para deteccion de colisiones. Ambos sistemas se ejecutan enteramente en Python puro.

El stack de fisica legacy implementa caracteristicas comparables a motores comerciales: broad-phase mediante `SpatialHash2D` con cell size adaptativo (32 a 256 pixeles) y cache de grid estatico; narrow-phase SAT (Separating Axis Theorem) completo para poligonos con manifolds y clipping de aristas, definido en `engine/physics/shapes.py` (909 lineas); PGS (Projected Gauss-Seidel) solver con 8 iteraciones de velocidad y 3 de posicion, warm-starting por contacto y friccion Coulomb, implementado en `engine/physics/contact_solver.py` (395 lineas); island building via BFS sobre el grafo de contactos y joints con sleeping a nivel de isla, en `engine/physics/island_manager.py` (145 lineas); CCD (Continuous Collision Detection) con tres modos (`disabled`, `continuous`, `cast_shape`) usando swept collision binario con hasta 64 iteraciones, en `engine/physics/swept_collision.py` (235 lineas); y joints de tipo `fixed`, `distance`, `pin`, `groove` y `damped_spring`.

El backend legacy expone ademas las queries `query_ray` (DDA via swept AABB), `query_aabb` (spatial hash) y `query_shape_cast` (TOI binario), junto con `body_test_motion` (sweep no-mutante con broad-phase AABB + swept_shape_toi por shape) y `move_and_slide` (bucle de slide estilo Godot con floor snap y clasificacion floor/wall/ceiling). Los materiales fisicos son serializables via `PhysicsMaterial` y el sistema soporta overrides de `Area2D` para gravedad y damping con modos replace/combine.

### 6.1.2 Box2D Backend: Experimental e Incompleto

El segundo backend, `Box2DPhysicsBackend` en `engine/physics/box2d_backend.py`, es una integracion experimental sobre pyBox2D (bindings Python de Box2D 2.3.10). Aunque delega la simulacion a `b2World` nativo en C++, presenta carencias criticas que lo hacen no viable para uso en produccion: no implementa `move_and_slide` ni `body_test_motion`, metodos esenciales para el `CharacterControllerSystem`; no soporta `query_shape_cast`; aproxima las capsulas como cajas; no implementa `AnimatableBody2D`; y sus bindings estan en mantenimiento minimo. Cuando se selecciona Box2D como backend, el `CharacterControllerSystem` detecta `supports_kinematic_move() == False` y recae en un fallback del backend legacy que itera sobre todas las entidades sin usar el spatial hash, incurriendo en O(n) por iteracion de slide.

### 6.1.3 SpatialHash2D Compartido

La estructura `SpatialHash2D` en `engine/physics/spatial_hash.py` (130 lineas) es un spatial hash basico que usa `dict[tuple[int, int], set[int]]` para mapear celdas de grid a conjuntos de identificadores de entidad. Soporta insercion, query AABB, query de candidatos para rayos, y deteccion de entidades "oversized" (aquellas cuyo AABB cubre mas celdas que el limite configurado). Tanto `PhysicsSystem` como `CollisionSystem` y el propio `LegacyAABBPhysicsBackend` comparten instancias de `SpatialHash2D` para la broad-phase. El grid se reconstruye cada frame, aunque el cache de grid estatico reduce parcialmente este coste.

## 6.2 Estrategia de Backends

### 6.2.1 Decision: Integrar Rapier2D, Deprecar Box2D

El analisis comparativo de los tres candidatos de backend determina que Rapier2D, bindings Python oficiales del motor de fisica Rust con SIMD, es la unica opcion que justifica la inversion de integracion. Rapier2D supera a legacy_aabb en velocidad raw por un factor estimado de 30x a 60x gracias a su implementacion en Rust con paralelizacion; soporta todas las shapes nativas incluyendo capsulas y convex hulls; proporciona queries nativas de raycast, AABB y shape-cast; incluye CCD nativo; y ofrece soporte WASM para export web via `wasm-bindgen`. La instalacion via `pip install rapier2d-py` proporciona binarios precompilados, eliminando la necesidad de toolchain C++.

Box2D se depreca gradualmente porque completar las funcionalidades faltantes (`move_and_slide`, `body_test_motion`, `query_shape_cast`, capsulas nativas, `AnimatableBody2D`) requiere una inversion mayor que crear el backend Rapier desde cero, y pyBox2D carece de path de mejora (sin SIMD, sin paralelo, sin WASM, bindings estancados). El backend legacy_aabb se mantiene como fallback permanente, siempre disponible, siempre funcional, y referencia de comportamiento correcto.

La siguiente tabla compara las tres estrategias de backend en los ejes relevantes para OpenGame.

| Dimension | Legacy AABB (Python) | Box2D (C++/bindings) | Rapier2D (Rust/SIMD) |
|-----------|---------------------|---------------------|---------------------|
| Velocidad raw | 1x (baseline) | 15-25x | 30-60x |
| move_and_slide | Completo, Python | No implementado | Nativo via shape-cast |
| body_test_motion | Completo, Python | No implementado | Nativo via cast_shape |
| query_shape_cast | Completo (TOI binario) | No implementado | Nativo |
| Capsula | Nativa | Aproximada como caja | Nativa |
| Joints completos | 5 tipos | 2 tipos | 5+ tipos |
| WASM/Web | No | No | Si |
| Paralelismo | No (GIL) | No (single-thread) | Si (parallel solver) |
| Determinismo | Python float | Plataforma-dependiente | Cross-platform |
| Instalacion | Siempre disponible | Compila C++ | Binario precompilado |
| Mantenimiento | Completo (propio) | Estancado | Activo (100+ contribuidores) |

La eleccion de Rapier2D sobre la alternativa de reescribir el PGS solver o el SpatialHash2D en Rust/PyO3 responde a una evaluacion coste-beneficio. Reimplementar el solver PGS de `contact_solver.py` (395 lineas de algoritmo numerico) en Rust podria ofrecer una mejora de 5x a 10x sobre la version Python, pero mantenerlo, depurarlo y extenderlo recae integramente en el equipo de OpenGame. Rapier2D, por otro lado, es un motor de fisica completo con test suite exhaustiva, soporte de comunidad y desarrollo activo. El valor no esta en reimplementar fisica propia, sino en integrar un motor existente via el contrato `PhysicsBackend` ABC que ya define la interfaz pluggable del motor.

### 6.2.2 Legacy AABB como Fallback Permanente

El backend `legacy_aabb` nunca se elimina. Su presencia garantiza que OpenGame funcione en entornos donde `rapier2d-py` no este disponible (plataformas exoticas, entornos de desarrollo sin acceso a PyPI, o versiones de Python no soportadas por los bindings). La resolucion de backend en `engine/physics/registry.py` sigue la prioridad: si el usuario solicita `rapier2d` y esta disponible, se usa Rapier; si no, se cae automaticamente a `legacy_aabb`. Este fallback es transparente para todos los sistemas porque la seleccion ocurre en el registro de backends, no en los sistemas consumidores.

### 6.2.3 PhysicsBackend ABC Inalterado

El contrato `PhysicsBackend` en `engine/physics/backend.py` no requiere modificaciones. Los metodos que `Rapier2DPhysicsBackend` debe implementar ya estan definidos: `create_body()`, `destroy_body()`, `create_shape()`, `step(world, dt)`, `query_ray()`, `query_aabb()`, `query_shape_cast()`, `collect_contacts()`, `body_test_motion()`, `move_and_slide()`, `move_and_collide()` y `supports_kinematic_move()`. Los dataclass `MoveResult2D` y `MotionResult2D` permanecen como estructuras canonicas de retorno; Rapier2D popula los mismos campos que legacy_aabb. Esta estabilidad del ABC es la garantia de que los 26+ sistemas no necesitan adaptacion.

## 6.3 Migracion Incremental

### 6.3.1 Fase 1: Queries a Rust

La primera fase de migracion de la fisica no toca el motor de simulacion. En lugar de ello, migra las operaciones de query —`query_ray`, `query_aabb`, `query_shape_cast`— a implementaciones en Rust via PyO3, exponiendolas como metodos del `PhysicsBackend`. Estas queries son rutas calientes independientes del solver: `query_ray` se usa para armas, deteccion de linea de vision y laseres; `query_aabb` para triggers de area y seleccion; `query_shape_cast` para prediccion de colisiones. Una implementacion en Rust de estas operaciones, usando el mismo SpatialHash2D pero con estructuras de datos contiguas y sin el GIL de Python, puede ofrecer mejoras de 5x a 10x sobre las versiones Python que iteran entidades candidatas con loops interpretados.

### 6.3.2 Fase 2: SpatialHash2D a Rust

El `SpatialHash2D` actual, implementado en `engine/physics/spatial_hash.py` con diccionarios y sets Python, se reimplementa en Rust como modulo PyO3. La API se preserva exactamente: `insert(entity_id, aabb)`, `query(aabb) -> set[int]`, `query_ray_candidates(ox, oy, dx, dy, max_distance) -> set[int]`, `clear()` y `reset()`. El SpatialHash2D Rust se comparte entre todos los backends: `PhysicsSystem`, `CollisionSystem` y `LegacyAABBPhysicsBackend` lo usan para broad-phase, independientemente de si el backend principal es Rapier o legacy. Esta migracion beneficia inmediatamente al backend existente sin requerir la integracion de Rapier.

### 6.3.3 Fase 3: Rapier2D como Backend Alternativo

Con las queries y el spatial hash ya migradas a Rust, la fase 3 integra `Rapier2DPhysicsBackend` como backend completo. El proceso se descompone en seis sub-fases:

**Phase 0 — Scaffold (1 semana):** Crear `Rapier2DPhysicsBackend` heredando de `PhysicsBackend`, con deteccion de disponibilidad via `try/except ImportError` de `rapier2d`. Implementar metodos stub que lancen `NotImplementedError` para funcionalidades no cubiertas, con fallback automatico a legacy_aabb.

**Phase 1 — Core Fisica (2 semanas):** Implementar `create_body` y `create_shape` mapeando `Transform` + `RigidBody` + `Collider` de OpenGame a `rapier.RigidBody` y `rapier.Collider`. Implementar `sync_world` con sincronizacion bidireccional (Python -> Rapier antes de `step()`, Rapier -> Python despues). Implementar `step()` integrando con `PhysicsPipeline.step()`. Implementar `query_ray` y `query_aabb` nativos via `QueryPipeline`.

**Phase 2 — Character Controller (2 semanas):** Implementar `body_test_motion` via `QueryPipeline.cast_shape()`, y `move_and_slide` reutilizando el bucle de slide existente del backend legacy pero delegando cada sweep a Rapier. Integrar con `PhysicsKinematicMoveService` sin modificar `CharacterControllerSystem`. Verificar que `supports_kinematic_move()` retorna `True`.

**Phase 3 — Joints y Filtering (1 semana):** Mapear `Joint2D` variants a `FixedJoint`, `PrismaticJoint` y `RevoluteJoint` de Rapier. Mapear `CollisionFilter2D.layer/mask` a `rapier.CollisionGroups`.

**Phase 4 — Features Avanzadas (1 semana):** Implementar `Area2D` gravity/damping overrides, `PhysicsMaterial`, CCD mode mapping, y `AnimatableBody2D`.

**Phase 5 — Paridad y Deprecacion (1 semana):** Implementar sleeping sync, `ContactMonitor` via eventos de colision de Rapier, deprecation warnings en Box2D, y documentacion de migracion.

La sincronizacion bidireccional Python <-> Rapier utiliza un mapeo de handles: `_entity_to_body: dict[int, rapier.RigidBodyHandle]` y `_body_to_entity: dict[rapier.RigidBodyHandle, int]`. Cada frame, antes de `step()`, se actualizan las posiciones y velocidades de los bodies Rapier desde los `Transform` y `RigidBody` de Python. Tras `step()`, se copian los resultados de vuelta a los componentes Python. Este overhead de sincronizacion es el coste fijo de usar un motor externo; se minimiza batchando las actualizaciones y evitando sync de entidades inactivas o sleeping.

### 6.3.4 CharacterControllerSystem Sin Cambios

El `CharacterControllerSystem` en `engine/systems/character_controller_system.py` ya esta diseñado para inyeccion de backend: su metodo `update()` acepta un parametro `backend=None` y, si no se proporciona, crea `LegacyAABBPhysicsBackend(None, None)`. El `PhysicsKinematicMoveService` detecta `supports_kinematic_move()`: si el backend lo soporta, usa `backend.move_and_slide()` y `backend.body_test_motion()`; si no, usa el fallback legacy. Esta arquitectura significa que `Rapier2DPhysicsBackend` solo necesita implementar `supports_kinematic_move() -> True` y los metodos `move_and_slide`/`body_test_motion` con las mismas firmas y estructuras de retorno que el backend legacy. El `CharacterControllerSystem` no requiere ni una linea de cambio.

## 6.4 Benchmarks

### 6.4.1 Escenarios de Medicion

La evaluacion del plan de fisica requiere un suite de benchmarks automatizado que compare los tres backends (legacy_aabb, Box2D y Rapier2D) bajo seis escenarios representativos de uso real:

**Stacking Tower** mide estabilidad estatica con 50 cajas apiladas en torre de 10x5, durante 300 frames. Captura jitter (desviacion de posicion) y sleeping ratio. El PGS Python tiene dificultades para estabilizar pilas grandes debido al coste de las 8 iteraciones de velocidad sobre N contactos; Rapier deberia estabilizar en menos de 1 ms.

**Scattering** mide dinamica pura con 100 cuerpos dinamicos con velocidad aleatoria en una caja cerrada, durante 300 frames. Este escenario estresa el solver de velocidad con multiples colisiones simultaneas, donde la ventaja de Rust sobre Python es mas pronunciada.

**Raycast Stress** coloca 200 entidades estaticas distribuidas en grid y ejecuta 100 raycasts aleatorios por frame. Evalua la eficiencia del broad-phase y la query de rayos. El legacy usa DDA via swept AABB con iteracion de candidatos en Python; Rapier usa su query pipeline nativa.

**Shape Cast / body_test_motion** situa 100 estaticos y un cuerpo en movimiento, ejecutando 50 shape_casts por frame. Este escenario replica la carga de trabajo del character controller y de sistemas de prediccion de IA.

**Character Controller** simula un personaje con `move_and_slide` sobre 50 plataformas estaticas y 10 one-way platforms, con movimiento izquierda/derecha/salto. Mide tiempo de CC por frame y precision de flags `on_floor`/`on_wall`.

**Mixed Realistic** combina 20 dinamicos, 100 estaticos, 5 joints, 1 character controller y 10 raycasts en un escenario tipo plataformas 2D. Este es el benchmark de aceptacion: la fisica debe ocupar menos del budget de 16.67 ms para 60 fps.

### 6.4.2 Objetivo de Mejora

Los criterios de aceptacion establecen umbrales de rendimiento para cada escenario. La meta minima es una mejora de 5x a 16x sobre el backend legacy en escenarios con mas de 100 cuerpos.

| Escenario | Carga | Legacy Budget | Rapier Objetivo | Mejora Minima |
|-----------|-------|-------------|-----------------|---------------|
| Stacking | 50 cajas estaticas apiladas | < 16 ms | < 1 ms | **16x** |
| Scattering | 100 dinamicos | < 16 ms | < 2 ms | **8x** |
| Raycast Stress | 200 estaticos + 100 raycasts | < 4 ms | < 0.5 ms | **8x** |
| Shape Cast | 100 estaticos + 50 shape casts | < 4 ms | < 0.5 ms | **8x** |
| Character Controller | 1 CC + 50 plataformas + 10 one-way | < 4 ms | < 1 ms | **4x** |
| Mixed Realistic | 20 dyn + 100 est + 5 joints + 1 CC + 10 rays | < 16 ms | < 3 ms | **5x** |

La mejora de 16x en el escenario de stacking es el objetivo mas agresivo porque es donde el PGS Python muestra su mayor debilidad: cada frame, el solver ejecuta 8 iteraciones sobre todos los contactos activos de la pila. Con 50 cajas apiladas, el numero de contactos puede superar los 100, lo que genera 800 iteraciones de solver en Python puro. Rapier ejecuta el mismo algoritmo PGS pero en Rust con SIMD y paralelismo, reduciendo el tiempo de solver de ~15 ms a menos de 1 ms. El escenario de character controller tiene el objetivo mas modesto (4x) porque incluye el overhead de sincronizacion bidireccional Python <-> Rapier y la logica de `move_and_slide` que, aunque delegada a Rapier para los sweeps, mantiene el bucle de slide en Python. La mejora en CC depende criticamente de que `body_test_motion` via Rapier sea suficientemente mas rapido que el sweep binario Python para compensar el coste de sync.

Los benchmarks se implementan en la infraestructura existente (`engine.debug.benchmark_runner`) y se ejecutan en CI para cada pull request que modifique el sistema de fisica. Las metricas capturadas incluyen: `physics_total_ms` (tiempo total de fisica por frame), `physics_step_ms` (tiempo dentro de `step()` sin sync), `physics_sync_ms` (tiempo de sincronizacion Python<->Rapier), `btm_ms` (body_test_motion), `move_slide_ms` (move_and_slide), `query_ray_ms`, `query_aabb_ms`, y contadores de bodies, contactos e islas. Una regresion de mas del 10% respecto al baseline falla la CI, forzando revison antes del merge.

---


# 7. Plan de Render

El sistema de renderizado de OpenGame constituye uno de los tres pilares críticos de la arquitectura junto con el ECS (Entity Component System) y la física. A diferencia de los sistemas analizados en capítulos anteriores, el pipeline de render opera bajo una restricción temporal severa: cada frame completo debe ejecutarse en 16.67 milisegundos o menos para mantener 60 fotogramas por segundo. El análisis detallado del código en `engine/systems/render_system.py` (1.200+ líneas), `engine/rendering/render_spatial_index.py` (186 líneas) y `engine/rendering/pipeline_executor.py` (162 líneas) revela que la fase de preparación (prep) consume una proporción significativa de ese presupuesto, llegando a ~3.15 milisegundos de mediana para 10.000 sprites según las mediciones documentadas en `docs/performance.md`. Este capítulo identifica los cuellos de botella específicos del pipeline y propone un plan de mejora incremental en tres fases que mantiene el backend gráfico intacto mientras optimiza la preparación de frames.

## 7.1 Pipeline Actual

### 7.1.1 Flujo de Preparación de Frame

El pipeline de renderizado sigue una arquitectura de tres capas: el `RenderSystem` actúa como orquestador, el `RenderPipelinePlanner2D` construye el plan del frame, y el `RenderPipelineExecutor2D` ejecuta los comandos contra la API de pyray/raylib. El flujo completo de un frame comienza en `RenderSystem.render()`, que invoca `_build_frame_plan()` para construir un `FramePlan2D` completo. Esta fase de preparación incluye: (1) ordenamiento de entidades mediante `_sorted_render_entities()`, que implementa una caché versionada con clave compuesta por `id(world)`, `render_version`, `transform_version`, `structure_version` y la tupla de sorting layers; (2) filtrado espacial a través de `_spatially_filter_render_entities()`, que reconstruye el índice espacial completo cada frame mediante `RenderSpatialIndex.rebuild()` seguido de `query()` con los bounds de la cámara; (3) generación del grafo de render en `_build_render_graph()`, que itera cada entidad visible realizando múltiples lookups de componentes y construyendo instancias de `RenderCommand`; y (4) agrupamiento en batches con `_build_batches()`, que escanea secuencialmente los comandos agrupando consecutivos que compartan el mismo `RenderBatchKey`, compuesto por `atlas_id`, `material_id`, `shader_id`, `blend_mode` y `layer`.

Una vez construido el plan, la ejecución delega en `RenderPipelineExecutor2D`, que itera los passes (World, Overlay, Debug) y para cada batch invoca `_execute_render_commands()`. Dentro de esta última función, los sprites simples consecutivos que comparten textura y batch key se agrupan en quads rlgl mediante `_draw_sprite_batch()`, con un límite conservador de `MAX_SPRITES_PER_BATCH = 1024` sprites por draw call, definido en `render_system.py:192`.

### 7.1.2 Batching: Criterios de Agrupamiento

El sistema implementa batching en dos niveles. El primer nivel, en `_build_batches()` (`render_system.py:847-858`), agrupa comandos consecutivos que comparten el mismo `RenderBatchKey` instanciado desde el payload del comando. El segundo nivel, en `_execute_render_commands()`, identifica sprites batchables mediante `_simple_sprite_components()`, que excluye explícitamente sprites rotados, sprites con componente `Animator` activo, sprites con `Polygon2D`, y entidades con textura inválida. Los sprites que cumplen los criterios se acumulan en un buffer de quads rlgl que se emite como un único draw call cuando se alcanza el límite de 1024 sprites o cuando cambia la textura o el estado de render.

Los elementos que no pueden batcharse siguen el camino de fallback individual: cada sprite rotado, animado o con polígono genera su propia llamada a `rl.draw_texture_pro()` o `rl.rl_begin(RL_TRIANGLES)`. Los tilemaps se renderizan mediante render targets cacheados (texturas offscreen) o fallback individual por tile. La geometría de debug genera un draw call por primitiva. Según las métricas de `docs/performance.md`, con 10.000 sprites idénticos el sistema emite entre 1 y 10 draw calls y batcha la totalidad de los sprites, confirmando que el mecanismo de batching funciona correctamente bajo condiciones óptimas.

### 7.1.3 Métricas Actuales del Pipeline

Los datos de referencia extraídos de `docs/performance.md` proporcionan los siguientes puntos de medición para la fase de preparación: con 1.000 sprites el sistema consume aproximadamente 0,5 milisegundos de mediana en preparación y emite un único draw call que agrupa la totalidad de los sprites. Al escalar a 5.000 sprites el tiempo sube a ~2,0 milisegundos con 1 a 5 draw calls. El punto de referencia crítico de 10.000 sprites consume ~3,15 milisegundos de mediana en la fase de preparación, emitiendo entre 1 y 10 draw calls y logrando batchar todos los sprites bajo condiciones óptimas (todos con la misma textura, sin rotación, sin animación). Con 50.000 sprites el tiempo supera los 15 milisegundos. Una escena mixta de 5.000 entidades (con tilemaps, animaciones y colliders de debug activos) consume ~2,5 milisegundos con más de 50 draw calls debido a las caídas del camino batchable al camino de fallback individual. Estas métricas constituyen el baseline inmutable contra el que se medirán todas las mejoras. El objetivo de la fase 3 es reducir el tiempo de preparación de 10.000 sprites de ~3,15 ms a menos de 0,5 ms, liberando ~2,65 ms del presupuesto de 16,67 ms por frame para otros sistemas o para escalar a escenas más grandes.

## 7.2 Cuellos de Botella Identificados

El análisis del código fuente identifica tres cuellos de botella principales en la fase de preparación, cada uno con un impacto medible y una solución viable.

### 7.2.1 Reconstrucción Completa del RenderSpatialIndex cada Frame

La función `_spatially_filter_render_entities()` en `render_system.py:773` invoca `self._render_spatial_index.rebuild(sorted_entities)` en cada frame con culling activado. La implementación de `rebuild()` en `render_spatial_index.py:29-36` ejecuta `self.clear()` seguido de un bucle `for` que recalcula los bounds AABB de cada entidad mediante `bounds_for_entity()` y reinserta en el `SpatialHash2D`. Para una escena con 10.000 entidades, esto implica 10.000 cálculos de bounds (cada uno con 2 lookups de componentes), 10.000 inserciones en el spatial hash (cada una calculando cell bounds e iterando celdas afectadas), y un query del viewport. El problema crítico: **esta reconstrucción completa ocurre aunque ninguna entidad se haya movido**.

En contraste, el sistema de ordenamiento `_sorted_render_entities()` ya implementa una caché versionada que evita re-sortar cuando no hay cambios relevantes, logrando una tasa de acierto (hit rate) de aproximadamente 85%. El spatial index carece de esta optimización: su tasa de acierto es 0%.

### 7.2.2 Doble Escaneo de Comandos

El pipeline realiza dos pasadas completas e independientes sobre la lista de comandos de render. La primera, `_build_batches()` (`render_system.py:847-858`), itera todos los comandos para agruparlos por `RenderBatchKey`. La segunda, `_sprite_batch_plan_stats()` (`render_system.py:696-754`), vuelve a iterar todos los comandos para calcular estadísticas de batching, realizando además 3 lookups de componentes adicionales por comando mediante `_simple_sprite_components()` y normalizando referencias de textura. Para 10.000 entidades, esto duplica el trabajo de escaneo lineal a costa de información que podría calcularse durante la primera pasada.

### 7.2.3 Sorting O(n log n) Invalidado por Cualquier Cambio

Cuando ocurre un cache miss en `_sorted_render_entities()`, el sistema ejecuta `sorted(entities, key=sort_key)` con una función de clave que realiza 2 lookups de componentes por entidad (`RenderOrder2D` y `Transform`), resuelve índices de layer y pass, y construye una tupla de ordenamiento `(pass_index, layer_index, order_in_layer, depth, entity_id)`. El cache miss se dispara cuando cambia cualquier entidad en términos de versión de render, transform o estructura. En una escena con 10.000 entidades donde solo 10 entidades (0,1%) cambian de posición, todo el conjunto se reordena en O(n log n) en vez de reutilizar el ordenamiento anterior con ajustes incrementales.

La siguiente tabla resume los tres cuellos de botella principales con sus ubicaciones exactas, complejidades e impacto estimado.

| Cuello de Botella | Ubicación (archivo:línea) | Complejidad | Impacto en 10K sprites | Condición de Disparo |
|---|---|---|---|---|
| Reconstrucción spatial index | `render_spatial_index.py:29-36` | O(n) inserciones | ~1,0-1,5 ms | Cada frame con culling activo |
| Doble escaneo de comandos | `render_system.py:696-754` + `847-858` | 2x O(commands) | ~0,5-1,0 ms | Siempre (pasadas consecutivas) |
| Sorting completo en cache miss | `render_system.py:400-430` | O(n log n) | ~2,0 ms | Cualquier cambio de posición/render |
| Generación de commands | `render_system.py:481-529` | O(v) con 3+ lookups/entidad | ~1,0 ms | Cache miss del grafo |
| Signature de chunks tilemap | `render_system.py:1218-1251` | O(tiles log tiles) por chunk | Spikes puntuales | Cache miss de chunk dirty |

La suma de estos cuellos de botella explica los ~3,15 ms de mediana observados para 10.000 sprites. La reconstrucción del spatial index representa aproximadamente el 30-47% del tiempo total de preparación, el sorting en cache miss el 40-60%, y el doble escaneo de comandos el 15-30%.

## 7.3 Plan de Mejora Incremental

La estrategia se divide en tres fases con incrementos crecientes de complejidad y speedup esperado. Cada fase mantiene compatibilidad con el backend gráfico pyray/raylib y no altera la API pública del `RenderSystem`.

### 7.3.1 Fase 1: Optimizaciones en Python (Speedup 2-5x)

La primera fase no introduce Rust; se enfoca en eliminar trabajo redundante mediante optimizaciones algorítmicas dentro del código Python existente.

**Caché versionada del spatial index.** Aplicar el mismo patrón que `_sorted_render_entities()`: una clave de caché compuesta por `transform_version` y `structure_version` del world. Si la clave coincide con la ejecución anterior, se reutiliza el índice espacial existente y solo se ejecuta `query()` con los nuevos bounds de cámara. En escenas estáticas donde solo la cámara se mueve, esto reduce el culling de O(n) a O(celdas visibles). Para escenas con entidades en movimiento, el impacto es neutro. La mejora esperada en escenas típicas es de 30-60% del tiempo de culling.

**Fusión de `_build_batches()` y `_sprite_batch_plan_stats()`.** Calcular las estadísticas de batching durante la pasada única de construcción de batches, eliminando la segunda iteración y sus lookups de componentes adicionales. Esto reduce el trabajo de escaneo a la mitad en la ruta de sprites.

**Lazy batch key resolution.** En `_build_batch_key()` (`render_system.py:1030-1067`), introducir una caché por entidad que almacene la clave de batch y se invalide solo cuando cambien `RenderStyle2D`, `Sprite` o `Animator`. Dado que la mayoría de las entidades mantienen sus estilos estables entre frames, esto evita lookups repetidos de componentes y resoluciones de atlas.

**Precálculo de componentes.** Durante `_sorted_render_entities()`, extraer una estructura plana con los componentes relevantes pre-resueltos (transform, sprite, render_order) para evitar los 3-5 lookups de componentes por entidad en la fase de generación de comandos.

Las métricas proyectadas para esta fase son: escena de 10.000 sprites estáticos con cámara moviéndose se reduce de ~3,15 ms a ~1,5-2,0 ms; escena de 10.000 sprites con 1% en movimiento se reduce de ~3,15 ms a ~2,5-3,0 ms; escena de 50.000 sprites estáticos se reduce de ~15+ ms a ~6-8 ms.

### 7.3.2 Fase 2: Render Prep en Rust (Speedup 10-50x)

La segunda fase migra la lógica de preparación a un crate Rust `opengame-render-prep` accesible via PyO3/maturin. El backend gráfico permanece en Python; Rust solo reemplaza las operaciones de cálculo.

**Sorting en Rust (subfase posterior, solo si `render_prep` sigue siendo hotspot).** La función `_sorted_render_entities()` se reemplaza por una llamada a `RenderSorter.sort_entities()`, que recibe un array plano de `EntitySortInput` (structs con campos numéricos) y devuelve un `Vec<u32>` con los IDs ordenados. La ordenación utiliza el introsort de la biblioteca estándar de Rust, significativamente más rápido que el Timsort de Python para datos numéricos. El speedup proyectado debe tratarse como hipótesis hasta medirlo contra `render_prep_10k_sprites`.

**Culling en Rust (subfase posterior, tras benchmark de culling).** El `RenderSpatialIndex` se reimplementa en Rust como `RenderCullingEngine` con un `SpatialHash2D` que mantiene grids de enteros (`HashMap<(i32, i32), Vec<u32>>`). Las funciones `rebuild()` y `query_visible()` operan sobre arrays planos sin overhead de objetos Python. El speedup proyectado debe validarse con cámaras estáticas y móviles, y no asumirse antes del benchmark.

**Generación de draw commands en Rust (subfase posterior, tras estabilizar sorting/culling).** La función `_build_render_graph()` se reemplaza por `generate_draw_commands()`, que recibe las entidades ordenadas y filtradas, calcula las claves de batch, agrupa por batch key consecutivo, y marca sprites batchables. El resultado es un vector plano de `DrawCommand` que Python itera para emitir las llamadas gráficas. El speedup proyectado debe validarse contra la implementación Python optimizada.

La suma de estas tres operaciones no debe presentarse como resultado esperado garantizado. El criterio real es que el módulo Rust aporte al menos 2x frente a Python optimizado, manteniendo fallback y sin romper el backend pyray/raylib.

### 7.3.3 Fase 3: Batching Completo con SIMD (Speedup 50-100x)

La tercera fase expande el crate Rust para cubrir toda la preparación de sprites, incluyendo el cálculo de coordenadas UV, bounds y decisiones de batchability. Esta fase aprovecha SIMD para operaciones de AABB masivas y paralelización con rayon para el procesamiento de chunks de tilemaps independientes. La interfaz híbrida final consiste en: Python maneja el backend gráfico, la API pública, el render de debug y el UI; Rust maneja todo el `prep` del frame (culling, sorting, commands, batching). El speedup end-to-end proyectado para la preparación total de 10.000 sprites es de 50-100x, reduciendo el tiempo de ~4,5 ms a ~0,10 ms.

## 7.4 Qué NO Mover a Rust

La decisión de qué componentes permanecen en Python es tan importante como la de qué se migra. Los siguientes sistemas se mantienen intencionalmente en Python por razones técnicas sólidas:

**Backend gráfico pyray/raylib.** Toda la API de pyray (`rl.draw_texture_pro()`, `rl.rl_begin()`, `rl.rl_vertex2f()`, `rl.end_mode_2d()`) permanece en Python porque el cuello de botella aquí es el driver GPU, no el código Python. La latencia de llamada a la API gráfica nativa amortiza cualquier overhead del intérprete.

**Debug geometry, UI rendering, tilemap chunk render targets.** El renderizado de debug opera por diseño sin optimización: cada línea, círculo o rectángulo es un draw call individual, y esta pasada solo se activa en desarrollo. El UI rendering (`UIRenderSystem`) típicamente maneja menos de 100 elementos y está acoplado a estados de botones del `UISystem`. Los render targets de chunks de tilemap requieren compleja lógica de invalidación y composición que no justifica el esfuerzo de interoperabilidad Rust-Python.

**Asset loading y `TextureManager`.** La carga de assets es una operación I/O bound (discos, red, filesystem) donde Rust no proporciona ventaja significativa. El `TextureResolutionCache` ya está optimizado para evitar llamadas repetidas a `Path.resolve()` y mantiene un índice por referencia de asset.

---

# 8. Plan de Tests, Benchmarks y CI

La refactorización del motor de render y los sistemas core exige una estrategia de testing que garantice que cada optimización preserve el comportamiento funcional. Este capítulo describe el estado actual de la suite de pruebas, define los tests que deben existir antes de modificar código de producción, propone una infraestructura de CI/CD con tres workflows diferenciados, y establece criterios cuantificables de éxito.

## 8.1 Estado Actual

### 8.1.1 Inventario de Tests

La ejecución de `py -m unittest discover -s tests` sobre la rama `Fix/optimizacion5.5` procesa 1.565 tests, reportando 3 fallos y 3 errores. La distribución por criticidad, extraída del análisis del inventario de test files, muestra que los tests críticos (save/load, EngineAPI, workspace multi-escena) pasan correctamente, mientras que los fallos se concentran en: `test_performance_infra.py` (caché de layout no se invalida como espera el test), `test_inspector_core.py` (el test esperaba que cambiara `entity.id` tras rebuild pero el ID no cambia), `test_agent_service.py` (dependencia de credenciales de entorno local que reporta `opencode-go` como `configured` en vez de `missing`), y `engine/app/debug_tools_controller.py` (la clase `_FakePerfWorld` carece del método `iter_all_entities`). Estos 3 fallos y 3 errores son preexistentes y no bloquean el inicio de la refactorización, aunque deben documentarse como baseline.

### 8.1.2 Benchmarks Existentes

El sistema de benchmarks dispone de 8 escenarios definidos accesibles via `tools.benchmark_run`, de los cuales 4 forman parte de la suite quick ejecutada por `tools.benchmark_suite --quick`. La suite quick pasa 4/4 sin warnings ni fallos en aproximadamente 29 segundos. Los escenarios incluyen: `many_transform_entities` (1K-100K entidades, métricas de ms/frame), `many_sprite_entities` (2K-10K entidades, métricas de draw_calls y batching), `transform_edit_stress` (10K entidades, métrica de edición serializable), `play_mode_clone_stress` (10K entidades, métrica de transición EDIT/PLAY), `many_static_colliders` (1K-2K colliders, métricas de caché de física), y `many_dynamic_and_static` (10K+100 entidades, comparativa de backends legacy_aabb vs box2d). Los reportes en formato JSON preservan métricas en `operations.load_level`, `operations.transform_edit`, `operations.edit_to_play`, `operations.render_preparation`, y `operations.physics_cache_metrics`.

### 8.1.3 Análisis Estático

El análisis de código estático reporta 277 errores de ruff (principalmente whitespace, imports sin ordenar, imports no usados y nombres indefinidos) y 196 errores de mypy (concentrados en ECS/world, render, editor y scene manager). Estos valores constituyen deuda técnica informativa: no bloquean la refactorización pero deben configurarse con `continue-on-error` en CI para evitar falsos negativos mientras se abordan progresivamente.

## 8.2 Tests antes de Tocar Código

La regla fundamental de esta refactorización es: **no se modifica código de producción sin un test de equivalencia que verifique la semántica preservada**. Los tests se dividen en tres categorías.

### 8.2.1 Tests de Equivalencia Python/Rust

Se definen más de 50 tests de equivalencia distribuidos en cinco dominios. Para ECS, 8 tests (ECS-EQ-01 a ECS-EQ-08) verifican que `World.create_entity`, `Entity.add_component`, `Entity.remove_component`, `World.get_entity_by_name`, `World.get_children`, `World.iter_all_entities`, el incremento de `structure_version`, y la clonación de mundo producen resultados idénticos entre implementaciones. Para transforms, 5 tests (TRF-EQ-01 a TRF-EQ-05) validan coordenadas globales con herencia de jerarquía, rotación compuesta, escalado compuesto, invalidación de caché, y contadores de revisión, con tolerancia `abs_diff < 1e-9`.

Para física, 10 tests (PHY-EQ-01 a PHY-EQ-10) cubren `sync_world` del backend legacy, insert/query del `SpatialHash2D`, raycasts con hit points y distancias, AABB queries, `body_test_motion` (swept collision), PGS velocity solve con 8 iteraciones, PGS position solve con 3 iteraciones, agrupamiento de islas, métricas de caché cold/hot frame, y joints (fixed, distance, pin). Las tolerancias varían entre `abs_diff < 0.001` para posiciones y velocidades post-solve, y `abs_diff < 0.01` para position solve acumulado.

Para render, 5 tests (RND-EQ-01 a RND-EQ-05) verifican que `render_entities` coincida, que `draw_calls` sea igual con batching, que `sprite_batches` coincida, que el sorting por layer y orden sea idéntico, y que el culling espacial incluya/excluya las mismas entidades. Para serialización, 5 tests (SER-EQ-01 a SER-EQ-05) validan roundtrips de escenas, prefabs, save/load v2, y feature metadata.

### 8.2.2 Tests de Regresión

Los golden benchmarks constituyen la línea base inmutable de la refactorización. El proceso de establecimiento requiere ejecutar la suite completa pre-refactor sobre un entorno de hardware estandarizado (preferiblemente el runner de CI) y almacenar el resultado como `benchmarks/golden_v1.json` bajo control de versiones. Este archivo nunca se modifica salvo que se produzca una mejora confirmada y medible, momento en el que se promueve a `golden_v2.json` con documentación de los cambios que justifican la nueva baseline. Cada ejecución posterior de CI compara las métricas obtenidas contra esta línea base con tolerancias estrictas: para tiempos por operación se permite un máximo de `max(+20%, +10ms)` respecto al golden; para conteos de `render_entities`, `draw_calls` y `sprite_batches` se exige exactitud numérica sin tolerancia; y para métricas de caché de física como `aabb_build_reduction` se exige que el valor no caiga más de 5 puntos porcentuales por debajo del golden. Adicionalmente, todos los archivos `.json` del directorio `levels/` deben cargar sin excepción mediante `EngineAPI.load_level()`, todos los prefabs en `prefabs/` deben instanciar sin error, y la totalidad de los tests de contrato API (signatures de `EngineAPI`, CLI del motor, roundtrip de serialización) deben reportar 0 fallos.

### 8.2.3 Tests de Contrato API

El contrato público de `EngineAPI` se verifica mediante `test_engine_api_public_contract.py`, que valida que todos los métodos públicos existan, sean invocables, mantengan sus signatures, y devuelvan los tipos esperados. La CLI del motor se verifica con tests que ejecutan `motor --help`, `motor doctor`, `motor export`, `motor benchmark` y `motor test`, comprobando códigos de salida y contenido de salida. La serialización roundtrip se prueba escena por escena con la secuencia `load -> to_dict -> from_dict -> to_dict`, comparando el resultado contra el payload original.

## 8.3 CI/CD Propuesto

La infraestructura de CI/CD se implementa mediante tres workflows de GitHub Actions, cada uno con un propósito diferenciado. El principio rector es que los tests Python puros son obligatorios (bloquean merge si fallan), mientras que los tests que requieren el toolchain de Rust son informativos.

### 8.3.1 Workflow `ci.yml` (Pipeline Principal)

El workflow de integración continua se dispara en push a `main`, `Fix/optimizacion5.5` y ramas `refactor/*`, y en pull request a `main`. Contiene cinco jobs secuenciales:

| Job | Descripción | Obligatorio | Requiere Rust |
|---|---|---|---|
| `static-analysis` | Ruff check + ruff format check + mypy typecheck | NO (info) | NO |
| `tests-python-puro` | Suite completa unittest discover -s tests | **SI** | NO |
| `tests-rust` | Tests de equivalencia ECS/física/render con módulo Rust | NO | **SI** |
| `benchmarks` | Suite quick + comparación contra golden baseline | **SI** | NO |
| `coverage` | Cobertura mínima del 65% | NO (info) | NO |

El job `static-analysis` ejecuta siempre pero está configurado con `continue-on-error: true` debido a los 277 errores de ruff y 196 de mypy preexistentes. El job `tests-python-puro` es la puerta crítica: si grep detecta "FAIL:" o "ERROR:" en el reporte, el pipeline falla con exit code 1. El job `tests-rust` detecta automáticamente la presencia del directorio `opengame_rust/` con `Cargo.toml`; si existe, compila con `cargo build --release`, instala via `maturin develop`, y ejecuta el subset de tests de equivalencia. Este job usa `continue-on-error: true` porque el toolchain Rust puede no estar disponible en todos los entornos de CI durante las primeras fases. El job `benchmarks` ejecuta `tools.benchmark_suite --quick` y, si existe `benchmarks/golden_v1.json`, compara resultados con `tools.benchmark_compare`.

### 8.3.2 Workflow `pr.yml` (Validación de Pull Request)

Este workflow se ejecuta exclusivamente en pull requests a `main` y `Fix/optimizacion5.5`. Es más estricto que `ci.yml` en validaciones específicas del cambio: ejecuta tests unitarios obligatorios, detecta si el PR incluye cambios en `opengame_rust/` (mediante `git diff --name-only HEAD~1 | grep "opengame_rust"`) y en ese caso fuerza la ejecución de tests de equivalencia, ejecuta benchmarks quick con `--fail-on-warning`, y verifica que no haya regresión contra el golden baseline. La detección condicional de cambios Rust permite que PRs que solo modifican Python no paguen el costo de compilación del toolchain Rust.

### 8.3.3 Workflow `nightly.yml` (Suite Completa)

Programado diariamente a las 03:00 UTC, este workflow ejecuta la suite completa de benchmarks sin el flag `--quick` (usando cargas reales de escenarios), y adicionalmente corre benchmarks individuales para ECS iteration (10K entidades), render prep (5K sprites), physics queries (1K static + 1K queries), tilemap culling (256x256), y partículas (10K update). Los resultados se almacenan con timestamp en `artifacts/benchmarks/nightly_YYYYMMDD.json` para análisis de tendencias históricas.

## 8.4 Criterios de Éxito

### 8.4.1 Rendimiento

El criterio primario de éxito de la refactorización es la mejora medible en benchmarks. Los umbrales establecidos definen tanto objetivos como mínimos aceptables:

| Benchmark | Baseline Python (ms) | Objetivo Rust (ms) | Mejora Mínima | Criterio de Éxito |
|---|---|---|---|---|
| Iteración ECS 10K | ~500 | ~50 | 90% | `operations.ecs_iteration.ms < 50` |
| Query ECS 10K filter | ~200 | ~20 | 90% | `operations.ecs_query.ms < 20` |
| Render prep 5K | ~25 | ~10 | 60% | `operations.render_preparation.ms < 10` |
| Render prep 10K | ~60 | ~25 | 58% | `operations.render_preparation.ms < 25` |
| Spatial hash query 1K | ~20 | ~5 | 75% | `operations.spatial_hash_query.ms < 5` |
| Raycast 1000 dense | ~100 | ~15 | 85% | `operations.raycast_batch.ms < 15` |
| Partículas 10K update | ~50 | ~5 | 90% | `operations.particles_update.ms < 5` |
| Carga escena 10K | ~15.000 | ~5.000 | 67% | `operations.load_level.ms < 5.000` |
| Clone play/edit 10K | ~10.000 | ~3.000 | 70% | `operations.edit_to_play.ms < 3.000` |

El objetivo agregado de iteración ECS con 10.000 entidades (~500 ms a ~50 ms, 90% de mejora) representa el caso más representativo del motor, ya que la iteración de componentes es la operación fundamental sobre la que se construyen todos los demás sistemas.

### 8.4.2 Compatibilidad

El segundo pilar de éxito es la preservación del comportamiento observable. Los criterios cuantificables son: 100% de escenas en `levels/` deben cargar sin excepción (criterio COMP_01); 100% de tests de API pública deben pasar (criterio COMP_03); 0 breaking changes en la interfaz `EngineAPI` (verificado por `test_engine_api_public_contract.py`); 100% de prefabs en `prefabs/` deben instanciar sin error (criterio COMP_02); y serialización roundtrip debe preservar todos los campos para escenas complejas (criterio COMP_05). El backend de física debe mantener el fallback automático: si Box2D no está disponible, el sistema usa `legacy_aabb` silenciosamente sin lanzar excepciones (criterio COMP_06).

### 8.4.3 Tolerancia Numérica

Dado que Python y Rust manejan aritmética de punto flotante con diferencias en orden de evaluación y optimizaciones del compilador, se establecen categorías de tolerancia explícitas. Los conteos de entidades, componentes, draw_calls y batches deben coincidir exactamente (Categoría A). Las coordenadas de `Transform` tras operaciones puras deben coincidir con `abs_diff < 1e-9` (Categoría B). Las posiciones post-integración, velocidades post-solve PGS, hit points de raycasts, distancias de colisión e impulses de joints bilaterales deben coincidir con `abs_diff < 0.001` (Categoría C). El position solve con 3 iteraciones, que acumula error iterativo, permite una tolerancia relajada de `abs_diff < 0.01` (Categoría D). Estas tolerancias se codifican en el test `test_numeric_tolerance.py` y se aplican en todos los tests de equivalencia Python/Rust.

---


# 9. Roadmap

Este roadmap corrige el orden original para reducir riesgo. La idea central es simple: **no se introduce Rust antes de tener tests, benchmarks y CI mínimos**. La refactorización debe avanzar mediante PRs pequeños, medibles y reversibles. Cada fase tiene un gate de aceptación; si no se cumple, no se avanza.

El orden corregido es:

```text
Fase 0: estabilización y medición.
Fase 1: optimizaciones Python seguras.
Fase 2: primer módulo Rust aislado.
Fase 3: ECS/física/render según profiling.
Fase 4: consolidación, documentación y benchmarks continuos.
```

## 9.1 Roadmap 30 Días (Mes 1)

El primer mes ya no debe intentar meter `SpatialHash2D`, `IslandBuilder`, Rapier2D y PGS solver a la vez. Eso sería demasiado riesgo para un proyecto con tests fallando y pocos contribuyentes. El objetivo corregido del primer mes es tener una base sólida y validar solo un módulo Rust pequeño si los datos lo justifican.

### 9.1.1 Semana 1: Fase 0 — Tests, benchmarks y CI mínimo

La semana 1 es no negociable. No se migra código a Rust todavía.

Objetivos:

1. Ejecutar la suite completa de tests.
2. Resolver los failures/errors existentes o documentarlos como fallos preexistentes aislados.
3. Crear un baseline reproducible de benchmarks.
4. Documentar el entorno de instalación y ejecución.
5. Configurar CI mínimo Python.
6. Auditar las ramas activas más recientes si afectan a módulos críticos.

Entregables:

| Entregable | Criterio de aceptación |
|---|---|
| `docs/profiling/baseline_report.md` | incluye comandos, hardware, commit, fecha y resultados |
| `benchmarks/baseline_results.json` | contiene ECS, clone, physics, render prep, partículas y tilemap |
| suite de tests base | verde o con fallos preexistentes documentados |
| CI Python mínimo | ejecuta tests críticos y no bloquea por Rust |
| lista de APIs protegidas | `EngineAPI`, `Scene`, `SceneManager`, serialización y componentes |

Criterio de salida: no se empieza ningún módulo Rust si no existe baseline reproducible.

### 9.1.2 Semana 2: Fase 1 — Optimización Python segura

La semana 2 se centra en cambios Python-only, de bajo riesgo y alto impacto.

Prioridades:

1. Invalidación selectiva de `_component_query_cache`.
2. Métricas de hit/miss para queries ECS.
3. Reducción de listas temporales en `get_entities_with()`.
4. Benchmark específico de `World.clone()`.
5. Identificar reconstrucciones por frame en física/render.
6. Añadir tests de regresión para EDIT/PLAY/STOP.

No se debe cambiar todavía el storage ECS ni la serialización Scene v2. El objetivo es mejorar sin tocar contratos públicos.

Entregables:

| Entregable | Criterio de aceptación |
|---|---|
| query cache selectivo | no invalida queries no relacionadas con el componente modificado |
| benchmark `query_cache_stress` | muestra hit rate y tiempo antes/después |
| benchmark `play_mode_clone_stress` | cuantifica coste real de `World.clone()` |
| tests EDIT/PLAY/STOP | verifican que runtime no contamina authoring |
| PR pequeño | no toca `EngineAPI`, `Scene`, schema ni editor |

Criterio de salida: las mejoras Python deben ser medibles y no romper tests.

### 9.1.3 Semana 3: Fase 2 — Primer módulo Rust pequeño

Solo en la semana 3, si las dos primeras semanas están estables, se introduce el primer módulo Rust.

Candidato recomendado: `SpatialHash2D`.

Motivo:

- API pequeña;
- datos numéricos;
- bajo acoplamiento;
- buen candidato para tests de equivalencia;
- útil para física y queries espaciales;
- fallback Python sencillo.

Tareas:

1. Crear `opengame_native/` con PyO3 + maturin.
2. Implementar `SpatialHash2D` nativo.
3. Crear bridge Python con fallback.
4. Añadir tests de equivalencia Python/Rust.
5. Ejecutar benchmark antes/después.
6. Verificar instalación en Windows/Linux/macOS cuando sea posible.

Criterios de aceptación:

| Criterio | Valor mínimo |
|---|---|
| equivalencia funcional | mismos resultados que Python para fixtures deterministas |
| speedup | ≥2x frente a Python optimizado |
| fallback | si falla import Rust, usa Python sin romper |
| PR | pequeño, reversible y documentado |
| tests | 0 regresiones nuevas |

Si `SpatialHash2D` no alcanza 2x o complica demasiado la instalación, se deja como experimental y no se migra otro módulo Rust.

### 9.1.4 Semana 4: Consolidación y decisión

La semana 4 no debe introducir Rapier2D ni PGS solver. Debe consolidar lo hecho y decidir si merece la pena continuar con Rust.

Tareas:

1. Comparar baseline vs estado actual.
2. Documentar resultados reales.
3. Revisar overhead PyO3.
4. Medir si el primer módulo Rust compensa.
5. Decidir el siguiente candidato: particles, render prep, area queries o ECS storage parcial.
6. Preparar roadmap de 90 días con datos reales, no estimaciones.

Criterio de salida del mes 1:

| Pregunta | Respuesta exigida |
|---|---|
| ¿Los tests están controlados? | Sí |
| ¿Hay baseline reproducible? | Sí |
| ¿Hay al menos una mejora Python medible? | Sí |
| ¿El primer Rust compensa? | Sí, solo si ≥2x y sin romper instalación |
| ¿Se tocó EngineAPI/Scene/Editor? | No |
| ¿Rapier2D/PGS entraron? | No, quedan para fases posteriores |

## 9.2 Roadmap 90 Días (Meses 1-3)

El horizonte de 90 días queda dividido en tres fases prudentes.

### 9.2.1 Mes 1: Estabilización, Python quick wins y primer Rust aislado

Objetivos:

- tests y CI mínimos;
- benchmarks base;
- query cache ECS optimizado en Python;
- `World.clone()` medido y parcialmente optimizado si es seguro;
- `SpatialHash2D` Rust solo si pasa el gate.

No se integra Rapier2D. No se migra PGS solver. No se cambia el storage ECS de forma profunda.

### 9.2.2 Mes 2: ECS y queries físicas

El segundo mes debe abordar el cuello de botella que los benchmarks indiquen como más importante después del mes 1.

Candidatos:

| Candidato | Primera solución | Migración Rust |
|---|---|---|
| ECS queries | mejorar cache, versiones y retorno por IDs | solo si sigue siendo hotspot |
| Area queries O(N²) | índice espacial y filtrado por tipo | Rust si el índice Python no basta |
| `World.clone()` | fast clone seguro por componente | Rust solo si storage nativo existe |
| Partículas | optimizar pool y update | Rust si hay muchos elementos |
| Render prep | evitar rebuilds por frame | Rust si el sorting/culling sigue costando |

El objetivo del mes 2 es quitar coste estructural antes de tocar física profunda.

### 9.2.3 Mes 3: Física externa o render prep, según datos

Rapier2D, Box2D avanzado, PGS solver o render prep nativo solo deben entrar en el mes 3 si los benchmarks del mes 1-2 demuestran necesidad.

Orden recomendado:

1. Si física sigue dominando: mejorar `PhysicsBackend` y queries antes de Rapier2D.
2. Si render prep domina: culling/batching/draw command generation en Rust.
3. Si partículas dominan: update CPU en Rust con batch único por frame.
4. Si ECS domina: storage nativo parcial para componentes calientes.

Tabla corregida de milestones:

| Horizonte | Entregable principal | KPI de aceptación | Si falla |
|---|---|---|---|
| 30 días | tests+benchmarks+query cache+primer Rust opcional | 0 regresiones; baseline; primer Rust ≥2x si existe | mantener Python y posponer Rust |
| 90 días | 1-2 hotspots reales optimizados | mejora medible en frame time; PRs pequeños | reducir scope |
| 180 días | consolidación de módulos útiles | CI con benchmarks y documentación | congelar migraciones nativas |

## 9.3 Roadmap 6 Meses (Meses 1-6)

El horizonte de seis meses no debe asumirse como una migración completa a Rust. Debe ser una consolidación de las optimizaciones que hayan demostrado valor.

### 9.3.1 Meses 1-2: Base fiable + optimizaciones estructurales

- tests y CI;
- benchmarks continuos;
- query cache;
- `World.clone()`;
- reconstrucciones por frame;
- primer módulo Rust si compensa;
- documentación del patrón Python/Rust.

### 9.3.2 Meses 3-4: Módulos nativos justificados

Solo se migran módulos con evidencia:

- `SpatialHash2D` si todavía no está consolidado;
- partículas si el benchmark lo justifica;
- render prep si domina frame time;
- area queries si siguen siendo O(N²);
- ECS storage parcial si las queries optimizadas siguen siendo insuficientes.

Rapier2D se evalúa aquí, no antes, y solo si existen tests de física comparables.

### 9.3.3 Mes 5: Integración avanzada

- render prep más completo;
- tilemap chunk culling;
- pathfinding;
- jobs paralelos con llamadas batch;
- evitar cruces FFI pequeños;
- revisar packaging multiplataforma.

### 9.3.4 Mes 6: Limpieza, documentación y deuda técnica

El mes 6 no debe introducir nuevos módulos Rust. Debe consolidar:

- documentación;
- eliminación de código duplicado;
- benchmarks automáticos;
- tests de regresión;
- guía de contribución;
- matriz de fallback;
- decisión sobre qué módulos nativos se mantienen y cuáles se descartan.

Timeline corregido:

```text
Mes 1          Mes 2          Mes 3          Mes 4          Mes 5          Mes 6
[===========]  [===========]  [===========]  [===========]  [===========]  [===========]
Tests/bench    ECS/clone      Física/render  Nativo just.   Integración    Limpieza
CI mínimo      Python wins    según datos     según datos    avanzada       docs/CI
Spatial opc.   queries        Rapier eval     particles      jobs           deuda
```

## 9.4 Dependencias y Criterios de Abandono

### 9.4.1 Cadena de Dependencias Secuencial Corregida

| Orden | Fase | Depende de | Justificación |
|---|---|---|---|
| 1 | Tests base y baseline de benchmarks | Ninguna | Sin medición no hay refactor fiable |
| 2 | Optimización Python segura | Baseline | Permite mejoras sin FFI ni packaging |
| 3 | PyO3 + primer módulo Rust | Tests y benchmarks | Valida integración nativa de bajo riesgo |
| 4 | Módulos nativos adicionales | Primer Rust exitoso | Evita repetir errores de FFI/build |
| 5 | Física externa / ECS storage | Evidencia de profiling | Alto riesgo; solo tras datos reales |
| 6 | Limpieza | Reemplazos estables | No eliminar legacy hasta tener confianza |

### 9.4.2 Criterio de Abandono Principal

El criterio de abandono corregido es:

```text
Si una migración Rust no aporta ≥2x frente a Python optimizado
o rompe instalación/tests,
se abandona ese módulo y se mantiene Python.
```

A nivel global:

```text
Si tras el primer módulo Rust el coste de mantenimiento, CI o packaging supera el beneficio medido,
se detiene la línea Rust y se continúa con optimizaciones Python + librerías externas puntuales.
```

### 9.4.3 Recursos y Restricciones de Equipo

El plan debe asumir pocos contribuyentes y evitar ramas largas. Las reglas operativas son:

- PRs de máximo 3-5 días de trabajo;
- ningún módulo crítico se toca sin tests previos;
- cada cambio debe tener rollback claro;
- ningún módulo Rust sin fallback Python;
- ninguna fase empieza si la anterior no pasó el gate;
- la documentación se actualiza junto al código, no al final.

---

# 10. Riesgos Técnicos

El análisis de riesgos identifica 35 riesgos distribuidos en cinco categorías: técnicos (12), arquitectura (7), proceso (6), compatibilidad (6) e infraestructura (4). De estos, 14 se clasifican como P0 críticos, 19 como P1 importantes y 2 como P2 de monitoreo. Este capítulo no enumera los 35 riesgos en su totalidad —esa lista exhaustiva reside en el documento de análisis de riesgos— sino que construye una matriz de los riesgos más relevantes para la toma de decisiones, detalla sus mitigaciones específicas, y define escenarios de fallo con planes de contingencia ejecutables.

## 10.1 Matriz de Riesgos

### 10.1.1 Clasificación por Severidad

Los 14 riesgos P0 críticos comparten una característica común: su materialización bloquea el progreso de al menos una fase del roadmap o corrompe datos del motor. Los cinco más graves, ordenados por proximidad temporal al inicio del proyecto, son: (1) los 3 failures y 3 errors en tests preexistentes (T01), que impiden usar la suite de regresión como red de seguridad; (2) el overhead de FFI superior al beneficio de Rust (T06), que invalida la premisa económica de toda la refactorización; (3) el bus factor de 1 con solo 2 contribuyentes (P01), donde la pérdida de cualquier persona paraliza el proyecto; (4) la imposibilidad de build en Windows (I02), que excluye a la mayoría de usuarios del ecosistema Python; y (5) el ECS bifurcado entre Python y Rust (A01), que crea dos fuentes de verdad para los datos del motor.

Los 19 riesgos P1 importantes representan retrabajo, degradación de performance o aumento de complejidad que no bloquean inmediatamente pero que, si se ignoran, escalan a P0. Los dos riesgos P2 (version pinning de PyO3 y pérdida de momentum de comunidad) se monitorean sin acción preventiva directa, con revisiones trimestrales.

### 10.1.2 Matriz Top 15: Probabilidad × Impacto

La siguiente tabla presenta los 15 riesgos con mayor producto de probabilidad por impacto, ordenados de mayor a menor prioridad de atención. La escala de probabilidad utiliza tres niveles: alta (>60%), media (30-60%) y baja (<30%). La escala de impacto utiliza tres niveles: alto (bloqueo o corrupción de datos), medio (retrabajo significativo o degradación medible) y bajo (inconveniente operativo).

| ID | Riesgo | Categoría | Prob. | Impacto | Prio. | Estrategia | Costo de Mitigación |
|---|---|---|---|---|---|---|---|
| T01 | Tests fallan pre-refactor (3F/3E) | Técnico | Alta | Alto | P0 | Congelar trabajo hasta 0 failures; root cause por cada test | 1-2 semanas |
| T06 | Overhead FFI > beneficio de Rust | Técnico | Alta | Alto | P0 | Benchmark antes de migrar cada módulo; gate de 2× speedup | 2 días por módulo |
| A01 | ECS bifurcado Python/Rust | Arquitectura | Alta | Alto | P0 | Decisión binaria: migrar todo o nada; gate en fase 2 | 1 semana de análisis |
| P01 | Bus factor 1 (2 contribuyentes) | Proceso | Media | Alto | P0 | Pair programming, ADRs, max 20h/semana en refactor | Continuo |
| I02 | Build imposible en Windows | Infraestructura | Alta | Alto | P0 | cibuildwheel desde día 1; wheels precompilados obligatorios | 3-5 días setup |
| T02 | Regresiones silenciosas en ECS | Técnico | Alta | Alto | P0 | Tests de propiedad, snapshots de comportamiento, fuzzing | 1 semana |
| C01 | Escenas existentes no cargan | Compatibilidad | Alta | Alto | P0 | Formatos language-agnostic; migrador automático; tests de carga | 3-4 días |
| A04 | EngineAPI para IA inconsistente | Compatibilidad | Media | Alto | P0 | Tests de contrato; golden masters; CI separado | 2-3 días |
| I01 | CI/CD rotos por Rust toolchain | Infraestructura | Alta | Medio | P0 | CI paralelo Python primero/Rust después; cache agresivo | 2-3 días |
| T04 | Deadlocks GIL Python/Rust | Técnico | Media | Alto | P0 | Diseño single-threaded para v1; timeouts en tests | Diseño (0 días extra) |
| T05 | Panics en Rust crashean Python | Técnico | Media | Alto | P1 | Cero unwrap en producción; Result<T,E> siempre; panic handler | Continuo |
| A02 | Deuda técnica dual Python+Rust | Arquitectura | Alta | Medio | P1 | Resolver deuda Python antes: 0 errores ruff/mypy como gate | 1-2 semanas |
| P02 | Tiempo estimado subestimado 3-5× | Proceso | Alta | Medio | P0 | Estimar con buffer 4×; fases con entregables demostrables | Planificación |
| C05 | Comportamiento física diferente | Compatibilidad | Alta | Medio | P1 | Tests con tolerancias; comparación frame-a-frame; documentar | 1 semana |
| T09 | Build times de Rust lentos | Técnico | Alta | Medio | P1 | sccache; cargo check para dev; release solo en CI | 1 día setup |

La matriz revela un patrón concentrado: 8 de los 15 riesgos de mayor prioridad son P0, y 6 de esos 8 tienen probabilidad alta. Esto significa que el proyecto enfrenta al menos seis riesgos con más de 60% de probabilidad de materialización y impacto alto si ocurren. La mitigación de estos seis riesgos no es opcional; es requisito de entrada para la fase 0 del roadmap.

La interpretación de cada estrategia de mitigación varía según su naturaleza. Las mitigaciones de "diseño" como el single-threaded para v1 (T04) no consumen tiempo adicional del calendario porque son decisiones arquitectónicas tomadas antes de escribir código. Las mitigaciones "continuas" como el pair programming (P01) y la política de cero unwrap (T05) son prácticas de equipo que se mantienen durante toda la duración del proyecto. Las mitigaciones con costo fijo deben planificarse como tareas explícitas en el roadmap.

### 10.1.3 Correlación entre Riesgos

Algunos riesgos no son independientes; su materialización aumenta la probabilidad de otros. El T06 (overhead FFI) y el T09 (build times lentos) se refuerzan mutuamente: si el build es lento, se hacen menos iteraciones de benchmark, lo que reduce la detección temprana de overhead. El P01 (bus factor) y el P04 (burnout) están directamente correlacionados: un contribuyente que trabaja el doble por ausencia del otro tiene mayor probabilidad de burnout. El A01 (ECS bifurcado) activa el T02 (regresiones silenciosas) porque una query que cruza el boundary Python/Rust puede devolver resultados inconsistentes sin generar una excepción.

## 10.2 Mitigaciones

### 10.2.1 Fase 0 No Negociable

Antes de que cualquier línea de código Rust se escriba, la fase 0 impone ocho gates de entrada que deben pasar simultáneamente. Estos gates se derivan directamente de los riesgos P0 identificados en la matriz.

El gate 0.1 exige que `pytest` pase con 0 failures y 0 errors. Los 3 failures y 3 errors actuales deben resolverse mediante root cause analysis documentada para cada caso; si un test es imposible de arreglar por ser flaky o depender de estado global, se marca con `@pytest.mark.skip` con explicación y ticket de seguimiento. El gate 0.2 exige 0 errores de ruff (o justificados y documentados); los 277 errores reportados deben eliminarse. El gate 0.3 exige 0 errores de mypy en interfaces públicas; los 196 errores reportados deben resolverse. El gate 0.4 exige benchmarks base ejecutados y archivados en `.benchmarks/baseline.json`. El gate 0.5 exige CI con Rust toolchain funcional en Linux, macOS y Windows. El gate 0.6 exige wheels precompilados generándose correctamente. El gate 0.7 recomienda (no exige) reducir branches activos de 98 a máximo 5. El gate 0.8 recomienda documentar la decisión de usar Rust y PyO3 mediante un ADR. El gate 0.9 exige que el prototype PyO3 "hola mundo" funcione en las tres plataformas. El gate 0.10 exige un backup completo del repositorio con el tag `pre-rust-refactor`.

Estos 10 gates son la aplicación operativa de la mitigación de seis riesgos P0 simultáneos: T01 (tests fallando), A02 (deuda técnica), T06 (benchmarks base), I01 (CI roto), I02 (instalación imposible) y A07 (fragmentación de branches). Cumplirlos consume aproximadamente 1-2 semanas de trabajo de ambos desarrolladores, pero reduce drásticamente la superficie de riesgo de las fases posteriores.

### 10.2.2 Tests de Equivalencia Obligatorios

Para cada módulo migrado a Rust, los tests de equivalencia no son opcionales: son el mecanismo de detección del riesgo T02 (regresiones silenciosas). El procedimiento es estándar: (1) escribir tests en Python puro que ejerciten el módulo Python actual con datos deterministas, (2) migrar el módulo a Rust manteniendo la API idéntica, (3) ejecutar los mismos tests contra el bridge Rust verificando que los outputs son idénticos byte por byte para tipos numéricos o con tolerancia estricta para floats.

Los tests de equivalencia para `SpatialHash2D` verifican secuencias de operaciones deterministas: insertar 100 entidades en posiciones aleatorias con semilla fija, consultar un AABB específico, eliminar 50 entidades, volver a consultar. Los resultados de la implementación Python y la implementación Rust deben coincidir exactamente en el conjunto de IDs retornado. Para el PGS solver, los tests verifican que, para la misma configuración de contactos y velocidades iniciales, las velocidades finales después de N iteraciones difieran en menos de 1e-6.

### 10.2.3 Ritmo de Cambios y Rollback

La regla de máximo un cambio grande por semana con plan de rollback se deriva de la correlación entre riesgos de proceso y técnicos. Un "cambio grande" se define como cualquier PR que modifique más de 500 líneas, toque más de un subsistema, o introduzca una nueva dependencia Rust. El plan de rollback para cada cambio grande debe documentarse en el PR y consistir en: (1) feature flag que deshabilite el cambio sin revertir el código, o (2) instrucciones de revert explícitas con estimación de tiempo, o (3) ambos.

Para el SpatialHash2D Rust, el rollback es el feature flag `USE_RUST_SPATIAL_HASH` que defaultea a `False` si se detecta cualquier problema. Para el ECS storage Rust, el rollback es revertir el PR completo porque es un "big bang controlado"; el tiempo estimado es horas, no días. Para cambios de CI, el rollback es deshacer el commit de configuración.

### 10.2.4 Documentación Continua

La documentación no es una fase final; es una mitigación continua del riesgo P01 (bus factor). Cada módulo Rust debe incluir un README que explique: propósito, API pública, cómo testear, y trampas conocidas. Cada decisión arquitectónica relevante se documenta como ADR en `docs/adr/`. El archivo `START_HERE_AI.md` se mantiene actualizado como contrato para agentes de IA que interactúan con `EngineAPI`. La documentación de API se genera automáticamente desde docstrings y rustdoc en CI.

## 10.3 Escenarios de Fallo

### 10.3.1 Escenario 1: Overhead FFI Consume la Ganancia

Este es el escenario de fallo existencial. Los síntomas son: benchmarks muestran que el módulo Rust es igual o más lento que Python, el profiling con `py-spy` + `perf` revela que la conversión de datos entre Python y Rust ocupa más del 50% del tiempo de frame, y la frecuencia de llamadas FFI es mayor de una por entidad por frame.

El plan de contingencia tiene tres niveles. El nivel 1, inmediato (0-4 horas): no mergear el PR. Mantener el módulo en branch experimental. El nivel 2, análisis (1-3 días): identificar el bottleneck exacto mediante perf. Si el overhead está en conversión de listas, reemplazar por buffers compartidos (arrays numpy) o memoria compartida. Si el overhead está en GIL acquire/release, rediseñar operaciones batch que procesen múltiples entidades en una sola llamada FFI. El nivel 3, decisión: si después de 3 días de optimización el speedup no alcanza 1,5×, se abandona el módulo. No hay vergüenza en esta decisión; es preferible un motor funcional en Python que un híbrido roto.

La señal de alarma temprana es un speedup inferior a 2× en la fase 2 (SpatialHash2D). Si el módulo más simple y aislado no alcanza 2×, los módulos más complejos —que requieren más conversiones de datos— tampoco lo harán.

### 10.3.2 Escenario 2: Tests de EngineAPI Fallan

Los tests de `EngineAPI` son sagrados. Si un cambio de refactorización rompe la API pública —cambia signatures, tipos de retorno, o comportamiento observable— la acción inmediata es revertir el cambio sin análisis previo. La regla de oro es: `EngineAPI` puede volverse más rápida internamente, pero su comportamiento externo es inmutable.

El plan de contingencia especifica: (1) revertir inmediatamente el commit que causó la falla, (2) identificar si el cambio era necesario para la integración Rust, (3) si lo era, rediseñar la integración para no tocar la API pública —adaptar Rust a la API existente, nunca al revés, (4) si no es posible adaptar Rust sin cambiar la API, congelar ese módulo y documentar la limitación. Los golden masters de respuestas de `EngineAPI` se almacenan en CI y se comparan en cada build.

### 10.3.3 Escenario 3: Build Rust Falla Repetidamente

Si el build de Rust falla más de dos veces en CI por causas no relacionadas con el código (toolchain, dependencias, configuración de runners), el plan de contingencia es: (1) primera falla: reintentar el job, documentar el error. (2) segunda falla: crear un ticket de infraestructura con logs completos. (3) tercera falla: evaluar alternativas. Si la causa es Windows específicamente y no se resuelve en una semana, la decisión drástica pero válida es posponer soporte Windows para la parte Rust, manteniendo fallback Python puro en Windows. Esta decisión se documenta explícitamente: "OpenGame con Rust requiere Linux/macOS. Windows usa Python puro (más lento pero funcional)". Es preferible entregar valor en dos plataformas que no entregar nada en tres.

Si la causa es general (no específica de una plataforma), se evalúa el uso de wheels precompilados generados manualmente en lugar de compilación en destino. El pipeline de `maturin` + `cibuildwheel` se configura para generar wheels en CI y almacenarlos como artifacts; si la compilación en destino falla, el usuario instala el wheel precompilado.

### 10.3.4 Escenario 4: Un Contribuyente Se Vuelve No Disponible

Si uno de los dos contribuyentes no está disponible por más de dos semanas (enfermedad, abandono, fuerza mayor), el scope de la refactorización se reduce automáticamente al 50%. El contribuyente restante trabaja en un único módulo a la vez, en secuencia, sin paralelización. La prioridad se reajusta: optimizaciones Python primero (no requieren Rust), luego SpatialHash2D si el contribuyente restante conoce Rust, o se pospone toda migración Rust hasta que el equipo se complete. Esta mitigación opera en tiempo real y no requiere decisión formal; es una regla de operación preestablecida.

---

El análisis de riesgos y el roadmap comparten una premisa común: cada decisión se toma sobre datos, no sobre intuición. El roadmap proporciona el calendario; la matriz de riesgos proporciona las condiciones bajo las cuales ese calendario debe ajustarse o abandonarse. La combinación de ambos —hitos medibles con umbrales de aborto explícitos— es lo que distingue esta refactorización de un esfuerzo ad-hoc sin dirección clara.

---


# 11. Recomendacion Final

Este capítulo sustituye la recomendación original por una versión más prudente y ejecutable. El plan sigue defendiendo una refactorización híbrida Python/Rust, pero cambia el orden: **primero estabilidad y medición; después optimización Python; finalmente Rust selectivo**.

## 11.1 Decisión Ejecutiva

### 11.1.1 Refactorización sí, pero no empezar por Rust

**Decisión:** Refactorizar sí, pero no con una migración inmediata. El motor debe estabilizarse primero.

Orden recomendado:

```text
1. Tests verdes o fallos base documentados.
2. Benchmarks reproducibles.
3. CI mínimo.
4. Optimizaciones Python seguras.
5. Primer módulo Rust aislado.
6. Fases nativas posteriores solo si el profiling lo justifica.
```

Python se mantiene como lenguaje principal para editor, `EngineAPI`, escenas, serialización, CLI, herramientas de IA y tests de integración. Rust se usa solo como acelerador de hotspots numéricos.

### 11.1.2 Primer trabajo real: Fase 0

**Primer trabajo recomendado:** no es `SpatialHash2D` en Rust. Es preparar una línea base fiable.

Tareas iniciales:

1. Ejecutar toda la suite de tests.
2. Resolver o aislar los tests fallando.
3. Crear `benchmarks/baseline_results.json`.
4. Crear `docs/profiling/baseline_report.md`.
5. Configurar CI Python mínimo.
6. Documentar comandos de instalación y ejecución.
7. Identificar APIs protegidas.

Sin esto, cualquier refactor posterior tendrá resultados ambiguos.

### 11.1.3 Primer módulo Rust: `SpatialHash2D`, pero solo después

`SpatialHash2D` sigue siendo el primer candidato Rust, pero solo después de Fase 0 y Fase 1.

Condiciones para empezar:

- tests de equivalencia escritos;
- benchmark específico antes/después;
- fallback Python diseñado;
- CI capaz de no romper si Rust no está disponible;
- query cache y problemas Python evidentes ya tratados o medidos.

Si no alcanza 2x frente a Python optimizado, se descarta como migración prioritaria.

### 11.1.4 Perímetro protegido

No se debe tocar al inicio:

- `EngineAPI`;
- `Scene`;
- `SceneManager`;
- schema Scene v2;
- serialización/prefabs;
- editor gráfico;
- clases `Component` existentes;
- `PhysicsBackend` público;
- integración raylib/pyray.

Estos módulos solo se modifican con tests de contrato y plan de rollback.

## 11.2 Plan de 30 Días Detallado Corregido

### Semana 1 — Estabilización

| Día | Tarea | Entregable |
|---|---|---|
| 1 | Ejecutar suite completa | reporte de tests actual |
| 2 | Resolver/aislar failures y errors | lista de fallos base documentados |
| 3 | Ejecutar benchmarks existentes | `benchmarks/baseline_results.json` |
| 4 | Añadir benchmarks faltantes mínimos | ECS, clone, physics, render prep, partículas |
| 5 | Configurar CI Python mínimo | workflow ejecutando tests críticos |
| 6-7 | Documentar entorno y comandos | `docs/profiling/baseline_report.md` |

Criterio de salida: baseline reproducible y estado de tests controlado.

### Semana 2 — Python quick wins

| Día | Tarea | Entregable |
|---|---|---|
| 8 | Medir `_component_query_cache` | métricas hit/miss |
| 9 | Implementar invalidación selectiva | PR Python-only |
| 10 | Benchmark `query_cache_stress` | antes/después |
| 11 | Medir `World.clone()` | benchmark dedicado |
| 12 | Optimizar clone si es seguro | sin romper EDIT/PLAY |
| 13-14 | Revisar rebuilds por frame | lista de cambios seguros |

Criterio de salida: al menos una mejora Python medible sin cambios de API.

### Semana 3 — Primer Rust opcional

| Día | Tarea | Entregable |
|---|---|---|
| 15 | Crear `opengame_native/` | crate PyO3/maturin mínimo |
| 16 | Tests equivalencia `SpatialHash2D` | fixtures deterministas |
| 17-18 | Implementar `SpatialHash2D` Rust | `cargo test` verde |
| 19 | Bridge Python + fallback | import seguro |
| 20 | Benchmark antes/después | speedup medido |
| 21 | Decisión: continuar o abandonar | informe breve |

Criterio de salida: `SpatialHash2D` ≥2x frente a Python optimizado, sin regresiones.

### Semana 4 — Consolidación

| Día | Tarea | Entregable |
|---|---|---|
| 22-24 | Corregir integración y docs | PR pequeño y reversible |
| 25 | Revisar overhead PyO3 | informe de coste FFI |
| 26 | Elegir siguiente candidato con datos | decisión documentada |
| 27-28 | Actualizar roadmap 90 días | plan basado en benchmarks reales |
| 29-30 | Cerrar deuda de la fase | tests/CI/documentación |

Criterio de salida: no empezar Rapier2D, PGS ni ECS storage profundo sin datos.

## 11.3 Plan de 90 Días Corregido

| Mes | Objetivo | Qué entra | Qué no entra todavía |
|---|---|---|---|
| Mes 1 | baseline + Python quick wins + primer Rust aislado | query cache, clone benchmark, SpatialHash opcional | Rapier2D, PGS, ECS storage profundo |
| Mes 2 | optimizar el hotspot real siguiente | area queries, partículas, render prep o ECS parcial | física completa si no hay tests |
| Mes 3 | consolidar 1-2 módulos nativos útiles | render prep o backend física si procede | reescritura global |

## 11.4 Plan de 6 Meses Corregido

| Mes | Objetivo |
|---|---|
| 1 | tests, benchmarks, CI, Python quick wins, primer Rust opcional |
| 2 | ECS/clone/queries físicas según datos |
| 3 | render prep, partículas o física según profiling |
| 4 | backend externo de física solo si hay tests sólidos |
| 5 | integración avanzada y packaging multiplataforma |
| 6 | limpieza, documentación, benchmarks continuos y eliminación de código muerto solo si reemplazos son estables |

## 11.5 Métricas y Criterios

### Criterios de éxito

| Área | Criterio |
|---|---|
| Tests | 0 regresiones nuevas |
| API | `EngineAPI`, `Scene`, `SceneManager` y serialización intactos |
| Benchmarks | antes/después documentado |
| Rust | cada módulo ≥2x frente a Python optimizado |
| Fallback | Python sigue funcionando si Rust no carga |
| Mantenibilidad | PRs pequeños, reversibles y documentados |

### Criterios para parar

Se debe parar o replanificar si:

- los tests de `EngineAPI` fallan;
- un benchmark empeora >10%;
- PyO3 complica instalación en Windows;
- un módulo Rust no alcanza 1.5x tras una semana;
- el overhead FFI consume >50% de la mejora;
- dos semanas seguidas no producen PR mergeable;
- se intenta tocar `Scene`, `EngineAPI` o editor sin tests de contrato.

## 11.6 Recomendación Final

La refactorización debe seguir esta prioridad:

```text
1. Tests verdes.
2. Benchmarks base.
3. Query cache ECS en Python.
4. World.clone medido y optimizado si es seguro.
5. SpatialHash2D Rust con fallback.
6. Area queries / physics queries.
7. Render prep o partículas.
8. Rapier2D solo con tests de física sólidos.
9. PGS solver solo si sigue siendo hotspot real.
```

La versión corregida del plan no descarta Rust. Lo coloca en su sitio: **Rust es una herramienta para acelerar hotspots demostrados, no el punto de partida del refactor**.

---
