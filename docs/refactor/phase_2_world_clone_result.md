# Resultado de fase

## Objetivo

Measure `World.clone()` through `play_mode_clone_stress` and decide whether a safe optimization is justified now.

## Estado inicial

- Base commit: `b18fb1894552ef50ea3966a88276051054286585`
- Branch: `codex/queen-safe-continuation`
- Remote main: `origin/main`
- Phase 1 query cache change already present in the working tree.
- Full suite baseline remains red with unrelated failures.

## Archivos inspeccionados

- `engine/ecs/world.py`
- `tests/test_ecs_clone.py`
- `tests/test_scene_workspace.py`
- `tests/test_core_regression_matrix.py`
- `tests/test_benchmark_run.py`
- `tests/test_benchmark_suite.py`
- `tools/benchmark_run.py`
- `engine/debug/benchmark_runner.py`
- `engine/debug/benchmark_scenarios.py`

## Cambios realizados

- Created dedicated benchmark artifact: `artifacts/benchmarks/world_clone_before_20260701.json`.
- No `World.clone` implementation change was made.
- No runtime, scene, serialization, editor, physics, or Rust code was touched.

## Cambios descartados

- No fast clone path.
- No component-specific clone special casing.
- No schema or SceneManager change.
- No Rust/PyO3 experiment.

Reason: current measurement shows `World.clone` is still significant, but does not provide enough evidence for a safe, clearly valuable implementation change. Correctness has priority.

## Tests ejecutados

- `py -m pytest`: failed, 3439 passed, 16 failed, 8 skipped.
- `py -m unittest discover -s tests`: failed, 3463 tests, 16 failures, 8 skipped.
- `py -m unittest tests.test_ecs_indices tests.test_ecs_clone tests.test_scene_workspace tests.test_core_regression_matrix tests.test_benchmark_run tests.test_benchmark_suite`: passed, 53 tests OK; rerun after docs also passed in 24.320 s.
- `py -m ruff check engine/ecs/world.py tests/test_ecs_indices.py`: passed.
- `py -m mypy engine/ecs/world.py`: passed.
- `py -m motor doctor --project . --json`: passed, project healthy.

Focused clone and EDIT/PLAY contract coverage passed.

## Benchmarks ejecutados

Command:

```bash
py -m tools.benchmark_run --scenario play_mode_clone_stress --backend legacy_aabb --mode play --frames 1 --entity-count 10000 --columns 100 --operation-repeats 5 --out artifacts/benchmarks/world_clone_before_20260701.json
```

Result:

- `world_clone.ms`: 519.396200
- `world_clone.median_ms`: 519.396200
- `world_clone.p95_ms`: 565.221600
- `world_clone.samples_ms`: 519.396200, 467.704300, 524.242400, 565.221600, 517.306100
- `edit_to_play.ms`: 507.614900
- `play_to_edit.ms`: 850.159900
- `ecs_queries.ms`: 5.573500
- `load_level.ms`: 3413.605200
- `render_preparation.ms`: 74.002400
- `summary.frame_max_ms`: 0.098800

## Riesgos detectados

- Full-suite baseline remains red.
- Optimizing `World.clone` risks mutable aliasing, prefab hierarchy regressions, and EDIT/PLAY contamination.
- Existing benchmark variance is high enough that a small optimization would be hard to trust.

## Rollback

No code rollback needed for phase 2 because no `World.clone` implementation was changed.

If the benchmark artifact is not desired, delete:

- `artifacts/benchmarks/world_clone_before_20260701.json`

## Decision

Maintain current implementation and do not optimize `World.clone` in this phase.

## Siguiente recomendacion

Before any `World.clone` optimization, add a more isolated clone scaling benchmark by entity/component mix and keep the existing aliasing tests mandatory. Next safe work can proceed to the SpatialHash2D equivalence gate, without Rust implementation yet.
