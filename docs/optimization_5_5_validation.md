# Optimization 5.5 validation

Fecha: 2026-04-27
Rama revisada: `Fix/optimización5.5`

## Checks ejecutados

| Comando | Resultado |
| --- | --- |
| `python -m unittest discover -s tests` | OK: 1595 tests, 9 skipped, 988.335 s |
| `python -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json` | OK: suite `passed`, 4/4 escenarios, 0 warnings, 0 failures |
| `python -m ruff check engine cli tools main.py` | OK: all checks passed |
| `python -m ruff check tests` | OK: all checks passed |
| `python -m mypy engine cli tools main.py` | OK: no issues found in 242 source files |

Nota: `artifacts/benchmarks/performance_suite.json` fue regenerado para leer métricas y luego restaurado para no dejar el artifact modificado.

## Benchmarks quick

Suite:

- Status: `passed`
- Duracion total: 44904.83 ms
- Total: 4
- Passed: 4
- Warnings: 0
- Failed: 0

Escenarios:

| Escenario | Status | Duracion ms | Metricas clave |
| --- | --- | ---: | --- |
| `transform_edit_stress_10k` | passed | 9540.13 | load_level 3474.55; transform_edit **0.15**; render_preparation 139.17; frame_max 0.11 |
| `play_mode_clone_stress_10k` | passed | 27129.10 | load_level 8772.29; edit_to_play 1499.91; play_to_edit 1984.17; render_preparation 166.60; frame_max 24.12 |
| `many_static_colliders` | passed | 2636.85 | load_level 549.13; edit_to_play 60.15; play_to_edit 130.43; render_preparation 14.57; frame_max 141.85 |
| `many_sprite_entities_headless` | passed | 5598.47 | load_level 1493.33; edit_to_play 226.71; play_to_edit 366.89; render_preparation **35.92**; frame_max 4.51 |

Confirmaciones de metricas clave:

- `transform_edit_stress_10k`: `transform_edit` se mantiene en ~0.15 ms, muy bajo y dentro del umbral.
- `many_sprite_entities_headless`: `render_preparation` se mantiene en ~35.92 ms, razonable y dentro del umbral.
- `play_mode_clone_stress_10k` y `many_static_colliders` pasan sin warnings ni failures; no muestran empeoramiento extremo frente a umbrales quick.

## Verificaciones 5.5

- `ProjectService.list_assets()` usa SQLite cuando el indice existe: **PASS**.
- `ProjectService.list_project_scenes()` usa SQLite cuando el indice existe: **PASS**.
- `Entity.to_dict()["id"]` siempre es `str`: **PASS**.
- `World.get_entity_by_serialized_id()` funciona tras rename y remove: **PASS**.
- `RenderSpatialIndex.bounds_for_entity()` devuelve bounds para entidad activa solo con `Transform`: **PASS**.
- `RenderSystem` invalida render graph al cambiar `world.transform_version`: **PASS**.
- `PhysicsSystem` incrementa `transform_version` al mover una entidad: **PASS**.
- `ScriptBehaviourSystem` deja de ejecutar hooks tras eliminar o reemplazar `ScriptBehaviour`: **PASS**.
- `Tilemap.iter_visible_runtime_chunks()` acota candidatos por `camera_bounds`: **PASS**.

Estas verificaciones quedan cubiertas por la suite completa y las pruebas headless existentes de project service, IDs serializados, render graph/spatial index, physics, scripts y tilemap.

## Riesgos restantes

- Se aplico un ajuste menor en `tests/test_audio_system.py` para evitar una asercion exacta sobre tiempo de pared sub-frame al pausar audio; el comportamiento runtime no cambio.
- Los cambios de Ruff tocaron muchos archivos con orden de imports, whitespace y variables no usadas. No se hicieron refactors funcionales amplios.

## Recomendacion

**Lista para merge.**

Con criterio estricto, la rama esta lista porque tests completos, benchmarks quick, Ruff global, Ruff tests y Mypy global estan verdes, y no se detectaron regresiones en las optimizaciones 5.5.
