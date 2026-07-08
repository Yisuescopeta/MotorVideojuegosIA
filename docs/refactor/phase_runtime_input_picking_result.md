# Resultado de fase

## Objetivo

Crear una API oficial minima para input runtime, conversion de coordenadas, bounds visuales y picking 2D, y refactorizar el solitario espanol para dejar de leer `pyray` directamente.

## Estado inicial

- Base: `b18fb1894552ef50ea3966a88276051054286585`.
- Rama: `codex/runtime-input-picking`.
- Rama principal remota detectada: `origin/main`.
- Tests dirigidos antes del cambio: 83 passed.
- Suite completa antes del cambio: 16 failed, 3468 passed, 8 skipped, 34 warnings, 1198 subtests passed.

## Archivos inspeccionados

- `engine/systems/script_behaviour_system.py`
- `engine/core/game.py`
- `engine/runtime/shared_game_runtime.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/utils/viewport.py`
- `engine/runtime/exported_game.py`
- `projects/Opengame cartas/scripts/solitario_espanol/controller.py`
- `tests/test_script_behaviour_system.py`
- `tests/test_viewport.py`
- `tests/test_render_graph.py`
- `tests/test_solitario_espanol.py`

## Cambios realizados

- Nuevo `RuntimeInputService` con mouse screen/viewport/world, estados del boton izquierdo y `key_pressed(name)`.
- Nuevas conversiones publicas en `engine.utils.viewport`: screen -> viewport, viewport -> world, screen -> world.
- Nuevo servicio de queries runtime para bounds visuales y picking.
- `ScriptBehaviourContext` ahora expone `input`, `render` y `picking` con null services compatibles.
- `Game`, runtime exportado y shared runtime actualizan input antes de ejecutar scripts.
- `RenderSystem` expone bounds visuales y picking sobre el orden visual existente.
- El solitario espanol usa `context.input` y `context.picking` para hover/click, sin `pyray` directo.
- Documentacion y ADR de la API runtime agregados.

## Cambios descartados

- No se parchearon hitboxes manuales dentro del solitario.
- No se duplico logica de camara o viewport en scripts.
- No se introdujo picking exacto por rotacion de sprite; v1 usa AABB.
- No se introdujeron dependencias nuevas.

## Tests ejecutados

- `py -3 -m pytest tests/test_script_behaviour_system.py tests/test_viewport.py tests/test_render_graph.py tests/test_solitario_espanol.py -q`
  - Resultado: passed.
  - Resumen: 100 passed, 5 subtests passed.
- `py -3 -m pytest tests/test_script_behaviour_system.py tests/test_viewport.py tests/test_render_graph.py tests/test_solitario_espanol.py tests/test_export_windows_smoke.py::TestExportedGameWindowed::test_windowed_pyray_updates_and_renders_once_per_frame -q`
  - Resultado: passed.
  - Resumen: 101 passed, 5 subtests passed.
- `py -3 -m pytest -q`
  - Resultado: failed con los 16 fallos baseline conocidos.
  - Resumen: 16 failed, 3475 passed, 8 skipped, 34 warnings, 1198 subtests passed.
- `py -3 -m pytest tests/test_render_graph.py tests/test_solitario_espanol.py -q`
  - Resultado: passed tras ajuste de formato en bounds de poligono.
  - Resumen: 74 passed, 5 subtests passed.

## Benchmarks ejecutados

No aplica. La fase no optimiza rendimiento; agrega contrato runtime y tests funcionales.

## Riesgos detectados

- Bounds de sprites rotados son AABB conservadores, no picking exacto por forma rotada.
- Sprites sin tamano visual real no participan en picking.
- La suite completa conserva fallos baseline no relacionados.

## Rollback

Revertir `engine/runtime/runtime_input.py`, `engine/runtime/runtime_picking.py`, el wiring en `Game`/runtime exportado/shared runtime, los cambios de contexto en `ScriptBehaviourSystem`, los metodos nuevos de picking/bounds en `RenderSystem`, las conversiones nuevas de viewport y el controlador del solitario. Si `EDIT -> PLAY -> STOP` falla, dejar `context.input`, `context.render` y `context.picking` como null services y no usar la API desde solitario hasta replanificar.

## Decision

Mantener. Los tests dirigidos cubren contexto runtime, conversiones, picking y solitario.

## Siguiente recomendacion

Anadir overlay debug opcional para bounds visuales, colliders y mouse screen/viewport/world si el editor necesita inspeccion visual.
