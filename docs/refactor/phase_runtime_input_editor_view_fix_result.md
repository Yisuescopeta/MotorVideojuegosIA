# Resultado de fase

## Objetivo

Corregir el click de cartas en la vista GAME del editor cuando el viewport esta escalado o letterboxed.

## Estado inicial

- Rama: `codex/runtime-input-picking`
- Base detectada: `origin/main`
- Fallo observado: headless funcionaba; la ruta editor GAME podia desalinear el mouse real con el viewport del juego.

## Archivos inspeccionados

- `engine/core/game.py`
- `engine/runtime/runtime_input.py`
- `engine/runtime/runtime_picking.py`
- `engine/utils/viewport.py`
- `engine/systems/render_system.py`
- `tests/test_solitario_espanol.py`
- `tests/test_viewport.py`
- `tests/test_export_windows_smoke.py`

## Cambios realizados

- `Game._update_runtime_input_from_editor()` usa `map_game_view_screen_point_to_texture()` cuando el tab activo es GAME.
- La entrada runtime recibe `viewport_x/viewport_y` directos en lugar de recalcularlos con otra ruta.
- Se agrego un test de regresion que valida mouse world y picking sobre una carta con viewport escalado.

## Cambios descartados

- No se toco la logica del solitario.
- No se cambio `context.input` ni `context.picking`.
- No se duplico la logica de picking en scripts.

## Tests ejecutados

- `py -3 -m pytest tests/test_runtime_input_editor_mapping.py tests/test_viewport.py tests/test_solitario_espanol.py -q`
  - Resultado: `34 passed`
- `py -3 -m pytest tests/test_export_windows_smoke.py -k windowed_pyray_updates_and_renders_once_per_frame -q`
  - Resultado: `1 passed`

## Benchmarks ejecutados

No aplica. Cambio funcional, no de rendimiento.

## Riesgos detectados

- La correccion depende de que `EditorLayout.map_game_view_screen_point_to_texture()` siga siendo la fuente de verdad del Game View.

## Rollback

Revertir el ajuste en `engine/core/game.py` y eliminar `tests/test_runtime_input_editor_mapping.py`.

## Decision

Mantener.

## Siguiente recomendacion

Si vuelve a aparecer desajuste, probar la misma ruta en la vista SCENE con el editor camera y comparar con `screen_to_viewport()`.
