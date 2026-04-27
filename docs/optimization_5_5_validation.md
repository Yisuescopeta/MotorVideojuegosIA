# Optimization 5.5 validation

Fecha de ejecucion: 2026-04-27
Rama revisada: `Fix/optimizacion5.5`

## Checks finales ejecutados

| Comando | Resultado |
| --- | --- |
| `python -m unittest discover -s tests` | OK: 1595 tests, 9 skipped, 1383.794 s |
| `python -m tools.benchmark_suite --quick --out artifacts/benchmarks/performance_suite.json` | OK: suite `passed`, 4/4 escenarios, 0 warnings, 0 failures |
| `python -m ruff check engine cli tools main.py` | OK: all checks passed |
| `python -m ruff check tests` | OK: all checks passed |
| `python -m mypy engine cli tools main.py` | OK: no issues found in 242 source files |

## Benchmark quick

Suite:

- Status: `passed`
- Duracion total: 42998.06 ms
- Total: 4
- Passed: 4
- Warnings: 0
- Failed: 0

Escenarios:

| Escenario | Status | Duracion ms | Metricas clave |
| --- | --- | ---: | --- |
| `transform_edit_stress_10k` | passed | 9793.83 | load_level 3474.41; transform_edit **0.13**; render_preparation 144.77; frame_max 0.11 |
| `play_mode_clone_stress_10k` | passed | 25946.59 | load_level 8203.19; edit_to_play 1106.85; play_to_edit 2180.61; render_preparation 172.06; frame_max 28.55 |
| `many_static_colliders` | passed | 2383.07 | load_level 517.20; edit_to_play 68.07; play_to_edit 141.56; render_preparation 14.25; frame_max 92.90 |
| `many_sprite_entities_headless` | passed | 4874.33 | load_level 1457.45; edit_to_play 219.11; play_to_edit 365.36; render_preparation **37.57**; frame_max 4.54 |

Confirmaciones:

- Tests completos pasan.
- Benchmark quick pasa con 4/4 escenarios, 0 warnings y 0 failures.
- Ruff global sobre `engine cli tools main.py` pasa.
- Ruff sobre `tests` pasa.
- Mypy global sobre `engine cli tools main.py` pasa.
- `.github/workflows/ci.yml` contiene los checks estrictos:
  - `python -m ruff check engine cli tools main.py`
  - `python -m ruff check tests`
  - `python -m mypy engine cli tools main.py`

## Artifact de benchmark

`artifacts/benchmarks/performance_suite.json` es un artifact local generado por el benchmark quick. No queda versionado ni staged:

- `git ls-files -- artifacts/benchmarks/performance_suite.json` no devuelve entradas.
- `.gitignore` mantiene `artifacts/benchmarks/*.json`.
- `git check-ignore -v artifacts/benchmarks/performance_suite.json` confirma que el archivo queda ignorado por esa regla.

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

- No se detectan riesgos bloqueantes en la validacion final.
- `artifacts/benchmarks/performance_suite.json` se conserva solo como artifact local ignorado tras ejecutar el benchmark.

## Recomendacion

**Lista para merge.**

Con criterio estricto, la rama esta lista porque tests completos, benchmark quick, Ruff global, Ruff tests y Mypy global estan verdes; CI protege los checks globales estrictos; y el artifact local de benchmark no queda versionado.
