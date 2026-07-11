# Baseline benchmarks

Date: 2026-07-01

## Existing benchmark tooling

- `tools/benchmark_run.py`
- `tools/benchmark_suite.py`
- `engine/debug/benchmark_runner.py`
- `engine/debug/benchmark_scenarios.py`
- `tools/physics_benchmark_cli.py`
- `tools/render_benchmark_cli.py`
- `tools/tilemap_collision_benchmark_cli.py`

## Existing benchmark scenarios verified

- `transform_edit_stress`
- `play_mode_clone_stress`
- `many_static_colliders`
- `many_sprite_entities`
- `many_transform_entities`
- `many_ui_buttons`
- `huge_tilemap`
- `one_dynamic_many_static`
- `many_dynamic_and_static`

## Existing artifacts

- `artifacts/benchmarks/baseline_20260630.json`
- `artifacts/benchmarks/query_cache_20260630.json`
- `artifacts/benchmarks/world_clone_before_20260701.json`

## Phase 1 quick suite

`artifacts/benchmarks/query_cache_20260630.json`:

- Status: passed.
- Total: 4 scenarios.
- Warnings: 0.
- Failed: 0.
- `play_mode_clone_stress_10k.world_clone.ms`: 692.0669999963138.
- `play_mode_clone_stress_10k.edit_to_play.ms`: 815.5941000004532.
- `play_mode_clone_stress_10k.play_to_edit.ms`: 977.9819000032148.

## Phase 2 dedicated measurement

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

## Conclusion

`World.clone()` remains measurable, but the current dedicated run does not justify a safe implementation change by itself. No `World.clone` optimization was applied.

## Runtime input/picking phase update - 2026-07-02

This phase adds runtime API wiring, coordinate conversion, visual bounds, and 2D picking. It is not a performance optimization phase, so no before/after benchmark was required to justify the change.

Benchmark tooling checked in the repository:

- `tools/benchmark_run.py`
- `tools/benchmark_suite.py`
- `engine/debug/benchmark_runner.py`
- `engine/debug/benchmark_scenarios.py`
- `tools/physics_benchmark_cli.py`
- `tools/render_benchmark_cli.py`
- `tools/tilemap_collision_benchmark_cli.py`
- `tools/spatial_hash_benchmark.py`

No Rust/PyO3 benchmark or native module was added.

## Codex Queen migration - 2026-07-10

No benchmark applies: migration changes only agent tooling, tests and docs.
Existing benchmark inventory remains unchanged.
