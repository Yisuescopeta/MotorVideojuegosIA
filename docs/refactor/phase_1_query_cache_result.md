# Resultado de fase

## Objetivo

Close phase 1 by documenting the Python-only ECS query cache change: replace global component-query cache invalidation with selective invalidation and keep internal hit/miss/invalidation counters.

## Estado inicial

- Base commit: `b18fb1894552ef50ea3966a88276051054286585`
- Branch: `codex/queen-safe-continuation`
- Remote main: `origin/main`
- Existing full-suite baseline is not green.
- Existing benchmark artifacts: `baseline_20260630.json`, `query_cache_20260630.json`.

## Archivos inspeccionados

- `engine/ecs/world.py`
- `tests/test_ecs_indices.py`
- `tests/test_ecs_clone.py`
- `tools/benchmark_suite.py`
- `tools/benchmark_run.py`
- `engine/debug/benchmark_runner.py`
- `engine/debug/benchmark_scenarios.py`

## Cambios realizados

- `World` now tracks internal component-query cache hits, misses, and invalidations.
- Component membership changes invalidate only cached queries containing the changed component type.
- Full cache clear remains available for full index rebuild paths.
- Tests cover unrelated component changes preserving existing query cache entries.

## Cambios descartados

- No Rust/PyO3.
- No public API.
- No scene, schema, editor, physics, or CLI changes.
- No `World.clone` changes in phase 1.

## Tests ejecutados

- `py -m pytest`: failed, 3439 passed, 16 failed, 8 skipped.
- `py -m unittest discover -s tests`: failed, 3463 tests, 16 failures, 8 skipped.
- `py -m unittest tests.test_ecs_indices tests.test_ecs_clone tests.test_scene_workspace tests.test_core_regression_matrix tests.test_benchmark_run tests.test_benchmark_suite`: passed, 53 tests OK; rerun after docs also passed in 24.320 s.
- `py -m ruff check engine/ecs/world.py tests/test_ecs_indices.py`: passed.
- `py -m mypy engine/ecs/world.py`: passed.
- `py -m motor doctor --project . --json`: passed, project healthy.

Relevant focused result: ECS/query/clone/scene benchmark contract tests passed.

## Benchmarks ejecutados

- `artifacts/benchmarks/query_cache_20260630.json`: passed, 4/4 scenarios, 0 warnings.

Key `play_mode_clone_stress_10k` values in that artifact:

- `world_clone.ms`: 692.0669999963138
- `edit_to_play.ms`: 815.5941000004532
- `play_to_edit.ms`: 977.9819000032148

## Riesgos detectados

- Full suite remains red with 16 failures.
- `AGENTS.md` working-tree changes trigger Queen governance contract failures.
- Cache counters are internal and must not become public API.

## Rollback

Revert the changes in:

- `engine/ecs/world.py`
- `tests/test_ecs_indices.py`

This restores global component-query cache invalidation.

## Decision

Continue. Phase 1 is acceptable as a small Python-only ECS internal change with focused tests passing and benchmark artifact present.

## Siguiente recomendacion

Proceed to phase 2 as measurement-only. Do not optimize `World.clone` without stronger before/after evidence and unchanged clone invariants.
