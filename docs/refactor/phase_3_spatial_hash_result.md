# Resultado de fase

## Objetivo

Cerrar el gate de equivalencia Python de `SpatialHash2D` antes de cualquier experimento Rust/PyO3.

## Estado inicial

- Base commit: `b18fb1894552ef50ea3966a88276051054286585`
- Branch: `codex/queen-safe-continuation`
- Remote main: `origin/main`
- `git fetch --all --prune`: ejecutado antes de tocar codigo.
- `git remote show origin`: `HEAD branch: main`.
- Full suite baseline sigue roja con 16 fallos ya documentados en `docs/refactor/baseline_tests.md`.
- Validacion previa de fase: `tests.test_spatial_hash tests.test_physics_system` pasaba con 30 tests OK.

## Archivos inspeccionados

- `docs/plans/active/queen-20260630-001-ajuste-plan-especializado-ejecucion.md`
- `docs/refactor/phase_2_world_clone_result.md`
- `docs/refactor/baseline_environment.md`
- `tests/test_spatial_hash.py`
- `tests/test_physics_system.py`
- `tools/benchmark_run.py`
- `tools/benchmark_suite.py`
- `engine/debug/benchmark_runner.py`
- `engine/debug/benchmark_scenarios.py`

## Cambios realizados

- `tests/test_spatial_hash.py` ahora cubre:
  - `reset()` cambia `cell_size` y limpia celdas, referencias y oversized entries.
  - `query_ray_candidates()` para rayos horizontales, verticales, diagonales, negativos y distancia cero.
  - oversized entries como candidatos obligatorios en ray queries.
- `tools/spatial_hash_benchmark.py` anade un microbenchmark aislado de Python para `insert`, `query`, `query_into` y `ray_candidates`.
- `tests/test_spatial_hash_benchmark.py` valida schema minimo, checksums deterministas y escritura CLI JSON.
- Artefacto generado: `artifacts/benchmarks/spatial_hash_python_20260701.json`.

## Cambios descartados

- No se implemento Rust/PyO3.
- No se modifico `engine/physics/spatial_hash.py`.
- No se modifico `engine/physics/**`, `engine/api/**`, escenas, serializacion, editor, `motor/**` ni docs canonicas.
- No se cambio semantica publica de `query_physics_*` ni `legacy_aabb`.

Reason: esta fase solo debia cerrar el gate Python y producir benchmark reproducible.

## Tests ejecutados

- `py -m unittest tests.test_spatial_hash tests.test_physics_system`
  - Result: passed.
  - Summary: 34 tests OK.
- `py -m unittest tests.test_spatial_hash_benchmark tests.test_benchmark_run tests.test_benchmark_suite`
  - Result: passed.
  - Summary: 23 tests OK.
- `py -m ruff check tests/test_spatial_hash.py tools/spatial_hash_benchmark.py tests/test_spatial_hash_benchmark.py`
  - Result: passed.
- `py -m motor doctor --project . --json`
  - Result: passed, project healthy, 0 warnings.

Full suite no se reejecuto en esta fase porque el baseline completo ya esta rojo y clasificado; los tests relevantes de `SpatialHash2D`, fisica y benchmark pasaron.

## Benchmarks ejecutados

Command:

```bash
py -m tools.spatial_hash_benchmark --entity-count 10000 --query-count 1000 --ray-count 500 --cell-size 64 --out artifacts/benchmarks/spatial_hash_python_20260701.json
```

Result:

- `insert.ms`: 13.934000
- `insert.p95_ms`: 22.666800
- `query.ms`: 8.396900
- `query.p95_ms`: 8.800800
- `query_into.ms`: 9.480800
- `query_into.p95_ms`: 9.728200
- `ray_candidates.ms`: 8.947400
- `ray_candidates.p95_ms`: 9.678700
- `counts.total_entries`: 10000
- `counts.cell_count`: 1444
- `counts.reference_count`: 14920
- `counts.oversized_entry_count`: 0
- `checksum`: 4089648442599396781

All operation checksums were stable.

## Riesgos detectados

- Full-suite baseline sigue rojo por fallos ajenos a esta fase.
- `query_ray_candidates()` conserva contrato broadphase conservador por swept AABB; un futuro backend nativo debe comparar sets de candidatos, no orden.
- Benchmark mide `SpatialHash2D` aislado; no demuestra todavia mejora de fisica end-to-end.

## Rollback

Rollback de fase:

- Revertir cambios en `tests/test_spatial_hash.py`.
- Eliminar `tools/spatial_hash_benchmark.py`.
- Eliminar `tests/test_spatial_hash_benchmark.py`.
- Eliminar `docs/refactor/phase_3_spatial_hash_result.md`.
- Quitar las entradas Phase 3 del progress log del plan activo.
- Opcional: borrar `artifacts/benchmarks/spatial_hash_python_20260701.json`.

No hay cambio runtime que desactivar.

## Decision

Mantener Phase 3. Gate de equivalencia Python cerrado. Native path sigue no implementado y desactivado.

## Siguiente recomendacion

Antes de cualquier Rust/PyO3, abrir plan separado de Phase 4 con ADR propuesto, fallback Python explicito, equivalencia Python/Rust y comparacion contra este benchmark Python. No activar Rust por defecto sin speedup >= 2x y sin instalar limpio sin Rust.
