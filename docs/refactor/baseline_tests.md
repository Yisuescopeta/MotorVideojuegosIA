# Baseline tests

Date: 2026-07-01

## Commands executed

- `py -m pytest`
  - Result: failed.
  - Summary: 3439 passed, 16 failed, 8 skipped, 34 warnings.
  - Duration: 419.36 s.

- `py -m unittest discover -s tests`
  - Result: failed.
  - Summary: 3463 tests, 16 failures, 8 skipped.
  - Duration: 449.524 s.

- `py -m unittest tests.test_ecs_indices tests.test_ecs_clone tests.test_scene_workspace tests.test_core_regression_matrix tests.test_benchmark_run tests.test_benchmark_suite`
  - Result: passed.
  - Summary: 53 tests OK.
  - Duration: 37.182 s.

- `py -m unittest tests.test_ecs_indices tests.test_ecs_clone tests.test_scene_workspace tests.test_core_regression_matrix tests.test_benchmark_run tests.test_benchmark_suite`
  - Result after docs update: passed.
  - Summary: 53 tests OK.
  - Duration: 24.320 s.

- `py -m ruff check engine/ecs/world.py tests/test_ecs_indices.py`
  - Result: passed.

- `py -m mypy engine/ecs/world.py`
  - Result: passed.

- `py -m motor doctor --project . --json`
  - Result: passed, project healthy, 0 warnings.

## Failure classification

- `tests/test_editor_interaction_controller.py`: 4 failures.
  - Classification: baseline functional/test expectation failures outside ECS query cache and `World.clone`.

- `tests/test_export_runtime_playability.py::TestRPGAndroidRuntimeParity::test_rpg_shared_runtime_advances_idle_and_mobile_walk_animation`: 1 failure.
  - Classification: baseline functional regression in RPG/export runtime path, outside ECS query cache and `World.clone`.

- `tests/test_queen_agent_contract.py`: 4 failures.
  - Classification: governance/documentation contract failures. These are affected by existing `AGENTS.md` working-tree changes and are outside ECS query cache and `World.clone`.

- `tests/test_rpg_android_animation_regression.py`: 3 failures.
  - Classification: baseline functional regression in RPG Android animation path.

- `tests/test_rpg_lives_system.py`: 3 failures.
  - Classification: baseline functional regression in RPG lives/combat path.

- `tests/test_rpg_render_order.py`: 1 failure.
  - Classification: baseline functional regression in RPG render order path.

## Phase relevance

Focused ECS, clone, scene workspace, core regression, and benchmark tests passed. Full-suite failures are not introduced by the phase 1 ECS query cache change or phase 2 `World.clone` measurement, but they remain open baseline risk.

## Runtime input/picking phase update - 2026-07-02

- Directed baseline before implementation: `py -3 -m pytest tests/test_script_behaviour_system.py tests/test_render_graph.py tests/test_solitario_espanol.py -q`
  - Result: passed.
  - Summary: 83 passed.
- Full-suite baseline before implementation: `py -3 -m pytest -q`
  - Result: failed.
  - Summary: 16 failed, 3468 passed, 8 skipped, 34 warnings, 1198 subtests passed.
  - Duration: 501 s.
  - Classification: same known baseline areas as above: editor interaction, RPG Android/export/runtime paths, RPG lives/render order, and queen agent contract.
- Directed validation after implementation: `py -3 -m pytest tests/test_script_behaviour_system.py tests/test_viewport.py tests/test_render_graph.py tests/test_solitario_espanol.py -q`
  - Result: passed.
  - Summary: 100 passed, 5 subtests passed.
- Directed validation plus export smoke after updating the runtime pointer payload test: `py -3 -m pytest tests/test_script_behaviour_system.py tests/test_viewport.py tests/test_render_graph.py tests/test_solitario_espanol.py tests/test_export_windows_smoke.py::TestExportedGameWindowed::test_windowed_pyray_updates_and_renders_once_per_frame -q`
  - Result: passed.
  - Summary: 101 passed, 5 subtests passed.
- Full-suite validation after implementation: `py -3 -m pytest -q`
  - Result: failed with known baseline failures only.
  - Summary: 16 failed, 3475 passed, 8 skipped, 34 warnings, 1198 subtests passed.
  - Duration: 415.09 s.

## Codex Queen migration baseline - 2026-07-10

- Pre-change suite from active plan: 3582 pass, 12 known functional failures,
  8 skipped.
- Authority: `tests/test_queen_agent_contract.py` plus repository governance.
- New focused command and final result live in
  `docs/refactor/phase_codex_queen_migration_result.md`.
