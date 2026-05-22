# Queen Execution Plan: Runtime exportado jugable

Status: active
Authority: operational-plan
Task ID: queen-20260522-001
Created at: 2026-05-22T12:00:00
Updated at: 2026-05-22T18:00:00
Mode: long-task-plan
Related plans: export_build_pipeline.md (padre — cubre pipeline completo; este plan llena el gap de runtime windowed jugable)

## Objective

Que `py -m motor export build "Windows Desktop"` genere un `.exe` realmente jugable:
- Menú UI con Canvas / UIButton funcional que cargue otra escena al hacer click.
- Input de teclado real que mueva un PlayerController2D.
- Render real de sprites/texturas.
- ScriptBehaviour ejecutándose.
- Animaciones, física y colisiones funcionales.
- Smoke test que verifique realmente jugabilidad (no solo carga headless).

El runtime exportado hoy solo ejecuta física + colisiones + dibujo manual de rectángulos. No usa InputSystem, RenderSystem, UISystem, UIRenderSystem, ScriptBehaviourSystem, AnimationSystem, PlayerControllerSystem ni CharacterControllerSystem.

## Non-goals

- No tocar editor, inspector, ni tooling IA.
- No modificar EngineAPI pública.
- No añadir nuevas plataformas de export.
- No cambiar schema de escenas ni componentes.
- No hacer que el runtime exportado tenga paridad total con el editor (no lleva gizmos, inspector, debug tools, consola, ni paneles).
- No implementar carga dinámica de assets por script (solo referencias estáticas en JSON de escena).
- No soportar hot-reload en runtime exportado.
- No tocar `main.py`.

## Constraints

- `engine/runtime/exported_game.py` no debe importar `engine.editor`, `engine.inspector`, `tools`, `tests`, `docs`, `motor`, `main`.
- Tests de pureza existentes (`test_export_windows_smoke.TestExportedRuntimePurity`) deben seguir pasando.
- `engine/core/game.py` y `engine/app/runtime_controller.py` son archivos críticos: cambios mínimos, solo si necesario para desacoplar.
- `ComponentRegistry` debe seguir registrando componentes igual.
- `Scene` sigue siendo fuente de verdad; `World` proyección operativa. Runtime exportado no persiste mutaciones.
- Commit solo tras tests, lint, typecheck, review y AI audit pasados.

## Current phase

- Name: completed
- Status: done

## Phases

### Phase 1 — Fix PyInstaller args en exportadores desktop

Status: done
Goal: Quitar `--specpath` (y `--windowed` condicional) cuando PyInstaller recibe `.spec`. Aplicar a los 3 exportadores desktop. Añadir tests.
Allowed files:
  - `engine/export/windows_exporter.py`
  - `engine/export/linux_exporter.py`
  - `engine/export/macos_exporter.py`
  - `tests/test_export_spec_generation.py`
Forbidden files: todo lo demás
Acceptance checks:
  - `--specpath` no aparece en argv de PyInstaller para Windows.
  - `--specpath` no aparece en argv de PyInstaller para Linux.
  - `--specpath` no aparece en argv de PyInstaller para macOS.
  - `--windowed` solo aparece en macOS si el spec no incluye BUNDLE (o se decide consistencia).
  - Tests mockean `subprocess.run` y verifican lista de args exacta.
  - `py -m unittest tests.test_export_spec_generation -v` pasa.
  - Ruff/mypy limpio en archivos tocados.
Docs affected: `docs/troubleshooting_export.md` si cambia algún mensaje de error
Risks: bajo

### Phase 2 — Desacoplar imports de editor en sistemas runtime

Status: done
Goal: Sistemas usados por runtime (`UISystem`, `ScriptBehaviourSystem`, `RenderSystem`, `AnimationSystem`) no deben importar `engine.editor` ni `engine.inspector` a nivel de módulo. Mover dependencias editoriales a callbacks inyectables o módulos separados.
Allowed files:
  - `engine/systems/ui_system.py` (quitar `from engine.editor.cursor_manager import CursorVisualState`)
  - `engine/systems/script_behaviour_system.py` (quitar `from engine.editor.console_panel import log_err, log_info`)
  - `engine/systems/render_system.py` (auditar imports de editor)
  - `engine/systems/animation_system.py` (auditar imports de editor)
  - `engine/core/runtime_logging.py` (nuevo: logging sin dependencia de editor)
  - `engine/core/game.py` (re-cablear callbacks)
Forbidden files: `engine/runtime/*`, `engine/editor/*`, `engine/inspector/*`
Acceptance checks:
  - `from engine.runtime.exported_game import main` no carga `engine.editor` ni `engine.inspector`.
  - `from engine.systems.ui_system import UISystem` no carga `engine.editor` ni `engine.inspector`.
  - `from engine.systems.script_behaviour_system import ScriptBehaviourSystem` no carga `engine.editor` ni `engine.inspector`.
  - Tests de pureza (`test_export_windows_smoke.TestExportedRuntimePurity`) extendidos para cubrir sistemas individuales.
  - Ruff/mypy limpio.
Docs affected: `docs/architecture.md`, `docs/TECHNICAL.md` (logging module nuevo)
Risks: medio. `CursorVisualState` es un enum usado por `UISystem`; debe moverse a `engine/core` o convertirse en callback. `log_err`/`log_info` son usados en muchos sitios; hay que crear versión runtime-safe.

### Phase 3 — Módulo de runtime exportable (export_runtime.py)

Status: done
Goal: Crear `engine/runtime/export_runtime.py` con clase `ExportRuntime` que encapsule todo el loop de juego exportado: cargar escena, crear World, mantener EventBus, ejecutar sistemas en orden, cambiar escena en runtime. Separar lógica de `exported_game.py`.
Allowed files:
  - `engine/runtime/export_runtime.py` (nuevo)
  - `engine/runtime/exported_game.py` (refactor para delegar en ExportRuntime)
  - `engine/runtime/scene_loader.py` (nuevo: loader de escenas runtime sin SceneManager)
Forbidden files: `engine/editor/*`, `engine/inspector/*`, `engine/api/*`, `engine/core/game.py`
Acceptance checks:
  - `ExportRuntime` no importa `engine.editor` ni `engine.inspector`.
  - `ExportRuntime` puede cargar una escena desde JSON, crear World, ejecutar N frames y devolver eventos.
  - `ExportRuntime` puede cambiar de escena en runtime (`load_scene(path)`).
  - `ExportRuntime` no usa `EngineAPI`.
  - `ExportRuntime` no persiste mutaciones runtime como authoring state.
  - Tests unitarios de `ExportRuntime` con escena mínima.
  - Tests de pureza extendidos.
  - Ruff/mypy limpio.
Docs affected: `docs/runtime_templates.md`, `docs/architecture.md`
Risks: medio. Hay que decidir qué sistemas wirear en cada modo (headless vs windowed). `Scene.create_world()` ya funciona sin editor.

### Phase 4 — Integrar gameplay mínimo (input + player + física)

Status: done
Goal: `ExportRuntime` ejecuta `InputSystem`, `PlayerControllerSystem`, `CharacterControllerSystem`, `PhysicsSystem`, `CollisionSystem`, `AnimationSystem` en orden correcto. Input de teclado mueve PlayerController2D real.
Allowed files:
  - `engine/runtime/export_runtime.py`
  - `engine/runtime/exported_game.py`
  - `engine/export/windows_exporter.py` (hiddenimports si hace falta)
  - `engine/export/linux_exporter.py`
  - `engine/export/macos_exporter.py`
Forbidden files: `engine/editor/*`, `engine/inspector/*`, `engine/api/*`, `engine/core/game.py`
Acceptance checks:
  - Ventana captura teclado real (WASD, Space) y mueve entidad con `PlayerController2D` + `InputMap` + `RigidBody`.
  - Salto funciona.
  - Colisiones con suelo funcionan (player no cae infinito).
  - Animaciones de idle/run/jump cambian con `Animator`.
  - Smoke test headless también ejecuta input inyectado y verifica movimiento.
  - `py -m unittest tests.test_export_windows_smoke -v` sigue pasando.
  - Ruff/mypy limpio.
Docs affected: `docs/runtime_templates.md`
Risks: bajo-medio. `InputSystem` ya usa `pyray` directamente, compatible con runtime. `PlayerControllerSystem` no tiene dependencias de editor. `AnimationSystem` necesita `EventBus` pero no editor.

### Phase 5 — Integrar render real (sprites, texturas, tilemaps)

Status: done
Goal: Reemplazar dibujo manual de rectángulos en `_run_windowed_pyray` por `RenderSystem.render()`. Cargar texturas desde content pack (directory o game.pak).
Allowed files:
  - `engine/runtime/export_runtime.py`
  - `engine/runtime/exported_game.py`
  - `engine/runtime/content_loader.py` (extender para assets binarios desde game.pak)
  - `engine/systems/render_system.py` (posible adaptación para asset resolver runtime)
  - `engine/runtime/asset_resolver.py` (nuevo: resolver assets desde content/ o game.pak sin ProjectService)
Forbidden files: `engine/editor/*`, `engine/inspector/*`, `engine/api/*`
Acceptance checks:
  - Entidades con `Sprite` se renderizan con su textura real, no rectángulo gris.
  - Entidades con `Sprite` + `Animator` renderizan frame correcto de spritesheet.
  - Tilemaps se renderizan (si hay tilemap en escena).
  - Fallback a rectángulo de color SOLO si no hay textura.
  - Directory mode: texturas cargadas desde `content/assets/`.
  - Packed mode: texturas extraídas de `game.pak` a tempdir o cargadas desde zip en memoria.
  - Ruff/mypy limpio.
Docs affected: `docs/runtime_templates.md`, `docs/TECHNICAL.md` (asset resolver runtime)
Risks: alto. `RenderSystem` depende de `ProjectService` y `AssetService` para resolver texturas. Hay que crear un `RuntimeAssetResolver` que lea del content pack sin proyecto. `TextureManager` ya carga texturas de archivos individuales; el reto es darle rutas válidas en frozen build.

### Phase 6 — Integrar UI real (Canvas, UIButton, UIText, UIImage)

Status: done
Goal: `UISystem.update()` procesa mouse real. `UIRenderSystem.render()` dibuja UI encima del render del mundo. `UIButton.on_click` con `type: load_scene` carga escena en runtime.
Allowed files:
  - `engine/runtime/export_runtime.py`
  - `engine/runtime/exported_game.py`
  - `engine/systems/ui_system.py` (si requiere ajustes post-desacople)
  - `engine/systems/ui_render_system.py` (si requiere ajustes post-desacople)
Forbidden files: `engine/editor/*`, `engine/inspector/*`
Acceptance checks:
  - Menú principal con Canvas + UIButton "Play" se renderiza correctamente.
  - Hacer click en "Play" ejecuta `on_click` tipo `load_scene`.
  - Escena destino se carga y reemplaza la actual.
  - UIText e UIImage se renderizan correctamente.
  - UIButton con hover/pressed/disabled cambia color visual.
  - Ruff/mypy limpio.
Docs affected: `docs/runtime_templates.md`
Risks: medio. `UIRenderSystem` usa `AssetService` para sprites de botones; necesita camino alternativo para runtime. `UISystem._resolve_pointer_state` ya usa `pyray.get_mouse_position()` — compatible con ventana exportada.

### Phase 7 — Integrar scripts exportados (ScriptBehaviour)

Status: done
Goal: `ScriptBehaviourSystem` ejecuta `on_play`, `on_update`, `on_stop` en runtime exportado sin `HotReloadManager`. Módulos de script se importan desde `scripts/` (directory mode) o desde `game.pak` extraído.
Allowed files:
  - `engine/runtime/export_runtime.py`
  - `engine/runtime/exported_game.py`
  - `engine/systems/script_behaviour_system.py` (ajustes para modo sin hot-reload)
  - `engine/runtime/script_loader.py` (nuevo: importar módulos desde content pack)
Forbidden files: `engine/editor/*`, `engine/inspector/*`
Acceptance checks:
  - Entidad con `ScriptBehaviour` ejecuta `on_play` al iniciar runtime.
  - `on_update(dt)` se llama cada frame.
  - `on_stop` se llama al cambiar de escena.
  - Script puede leer/escribir `public_data`.
  - Script puede llamar `context.load_scene_flow_target(key)`.
  - Scripts en `scripts/` del content pack son importables.
  - Ruff/mypy limpio.
Docs affected: `docs/runtime_templates.md`
Risks: alto. `ScriptBehaviourSystem` depende de `HotReloadManager` para cargar módulos. Hay que hacer que `_load_module` funcione con importlib estándar cuando no hay hot-reload. También necesita `AssetService` para resolver rutas de script; requiere adaptación similar a Phase 5.

### Phase 8 — Tests de jugabilidad real

Status: done
Goal: Crear `tests/test_export_runtime_playability.py` con tests que verifican que un `.exe` exportado es jugable (no solo smoke test headless).
Allowed files:
  - `tests/test_export_runtime_playability.py` (nuevo)
  - `tests/fixtures/` (escenas mínimas de test)
Forbidden files: `engine/*`, `motor/*`
Acceptance checks:
  - Test: build Windows Desktop con escena UI startup + escena platformer mínima.
  - Test: `ExportRuntime` ejecuta UI, click en botón carga escena platformer.
  - Test: input teclado inyectado mueve Player en escena platformer.
  - Test: verificar que `RenderSystem.render()` y `UIRenderSystem.render()` fueron llamados.
  - Tests no requieren PyInstaller real (mock o usar `ExportRuntime` directamente).
  - `py -m unittest tests.test_export_runtime_playability -v` falla hoy, pasa al terminar Phase 7.
  - Ruff/mypy limpio.
Docs affected: `docs/runtime_templates.md`
Risks: medio. Tests de integración pueden ser lentos si usan PyInstaller real. Usar `ExportRuntime` directamente sin build completo.

### Phase 9 — Actualizar documentación

Status: done
Goal: `docs/runtime_templates.md` describe capacidades reales. `docs/export_pipeline.md` aclara que smoke test ≠ jugable. Si el runtime queda jugable, docs pueden volver a prometer UI/input/scripts con respaldo de tests.
Allowed files:
  - `docs/runtime_templates.md`
  - `docs/export_pipeline.md`
  - `docs/troubleshooting_export.md`
  - `docs/plans/active/export_build_pipeline.md` (actualizar sección 7 si aplica)
Forbidden files: `engine/*`, `tests/*`
Acceptance checks:
  - `docs/runtime_templates.md` línea 143-145 describe capacidades verificadas por tests.
  - `docs/export_pipeline.md` sección "Limitaciones reales" aclara diferencia smoke vs jugable.
  - No se promete nada que no esté respaldado por tests que pasan.
  - `py -m unittest tests.test_repository_governance -v` pasa.
Risks: bajo. Solo docs.

## Decisions

- 2026-05-22: Plan creado tras revisión de `exported_game.py`. Reason: runtime windowed solo dibuja rectángulos, no usa sistemas reales. Impact: 9 fases, ~2-3 semanas de trabajo.
- 2026-05-22: ExportRuntime como clase nueva en vez de modificar `Game`. Reason: `Game` tiene dependencias fuertes de editor. Impact: código más limpio, menos riesgo de regresión en editor.
- 2026-05-22: Orden de fases: fix build → desacoplar → runtime module → gameplay → render → UI → scripts → tests → docs. Reason: cada fase desbloquea la siguiente. Impact: no se puede paralelizar mucho; secuencial.
- 2026-05-22: Desacople de editor (Phase 2) antes de integrar sistemas (Phases 4-7). Reason: si no desacoplamos primero, los imports de editor contaminan el runtime. Impact: Phase 2 es prerequisito crítico.

## Progress log

- 2026-05-22: Plan creado. Status: active. Fase 1 pendiente.
- 2026-05-22: Phase 1 done — fix PyInstaller args (--specpath, --windowed). Tests pasan.
- 2026-05-22: Phase 2 done — desacople imports de editor en sistemas runtime. Pureza verificada.
- 2026-05-22: Phase 3 done — ExportRuntime creado. Scene loading, World, game loop, event bus.
- 2026-05-22: Phase 4 done — InputSystem, PlayerControllerSystem, CharacterControllerSystem, PhysicsSystem, CollisionSystem, AnimationSystem integrados.
- 2026-05-22: Phase 5 done — RenderSystem con RuntimeProjectService para texturas desde content/.
- 2026-05-22: Phase 6 done — UISystem + UIRenderSystem con mouse real y load_scene.
- 2026-05-22: Phase 7 done — ScriptBehaviourSystem con importlib fallback (sin hot-reload).
- 2026-05-22: Phase 8 done — 16 tests en 5 clases (scene loading, frames, gameplay movement, UI click, systems integration).
- 2026-05-22: Phase 9 done — runtime_templates.md, export_pipeline.md y este plan actualizados.
- 2026-05-22: Plan completado. Todas las fases done. ExportRuntime jugable con todos los sistemas canónicos.

## Final checks

- Focused tests: done (16 tests en test_export_runtime_playability.py pasan)
- Regression tests: done (test_export_windows_smoke, test_export_spec_generation pasan)
- Lint: done
- Typecheck: done
- Motor doctor: done
- Review: done
- AI audit: done (no afecta flujos IA de export — ExportRuntime no usa EngineAPI)
