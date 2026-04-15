# AGENTS.md

## Purpose

This repository uses a shared serializable engine model and supports parallel
feature work through isolated branches/worktrees.

This file is the default operating contract for coding agents working in this
repo.

Read this file together with:

- `docs/README.md`
- `docs/architecture.md`
- `docs/TECHNICAL.md`
- `docs/schema_serialization.md`
- `docs/module_taxonomy.md`
- `docs/agents.md`

Historical roadmaps, prompt packs, research notes, and old orchestration
material are archived under `docs/archive/`. They are useful background, not the
current product contract.

## Core repository invariants

These rules are not optional.

### 1. Persistent source of truth

- `Scene` is the persistent source of truth.
- `World` is an operational projection.
- runtime mutations must not become accidental authoring state.

### 2. Authoring path

- serializable authoring changes must go through `SceneManager` or `EngineAPI`
- do not introduce new direct-edit paths around shared authoring flows
- direct mutation of `edit_world` is legacy compatibility only, not the preferred route for new work

### 3. Public API

- `EngineAPI` is the stable public facade for agents, tests, CLI and automation
- do not bypass it for public-facing workflows unless the task explicitly requires internal wiring work

### 4. Physics contract

- preserve the common backend contract
- preserve `legacy_aabb` fallback behavior
- do not change the public meaning of `query_physics_ray` or `query_physics_aabb` outside dedicated physics work

### 5. Component registration

- if you add a new public component, register it in `engine/levels/component_registry.py`
- do not assume public support for unregistered components

## Critical files

Treat these files as frozen unless the task explicitly authorizes them.

- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/tilemap.py`
- `engine/levels/component_registry.py`

If you think one of these files must be changed:

1. stop
2. explain exactly why
3. state the minimal required change
4. do not change it silently

## Documentation boundaries

- Canonical docs live at the root of `docs/` and are indexed by `docs/README.md`.
- Archived docs live under `docs/archive/` and must not be treated as current source of truth.
- New public behavior should update canonical docs, not only an archived note or prompt.
- Do not promote a capability as current unless it is backed by code, tests, the public API, or the official `motor` CLI.

## Branch-aware perimeter rules

When working in a parallel feature branch, stay strictly inside that branch scope.

### Branch: `feature/w1-audio2d-runtime`

Allowed:

- `engine/components/audiosource.py`
- `engine/systems/audio_system.py`
- `engine/api/_runtime_api.py`
- audio tests
- audio docs

Forbidden:

- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/scenes/scene_manager.py`
- `engine/api/_authoring_api.py`

### Branch: `feature/w1-navigation-core`

Allowed:

- `engine/navigation/*`
- navigation tests
- navigation docs
- minimal API additions in `engine/api/_runtime_api.py` or `engine/api/_authoring_api.py`
- `engine/levels/component_registry.py` only if a public component is introduced

Forbidden:

- `engine/tilemap/*`
- `engine/components/tilemap.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/core/game.py`

### Branch: `feature/w1-animator-authoring`

Allowed:

- `engine/components/animator.py`
- `engine/systems/animation_system.py`
- `engine/editor/animator_panel.py`
- animator-specific parts of `engine/api/_authoring_api.py`
- animator tests
- animator docs

Forbidden:

- `engine/systems/render_system.py`
- `engine/tilemap/*`
- `engine/app/runtime_controller.py`
- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/inspector/inspector_system.py`

### Branch: `feature/w1-tilemap-authoring`

Allowed:

- `engine/components/tilemap.py`
- tilemap-specific parts of `engine/api/_authoring_api.py`
- tilemap editor/inspector files
- tilemap API tests
- tilemap serialization tests
- tilemap docs

Forbidden:

- `engine/systems/render_system.py`
- `engine/tilemap/collision_builder.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`

### Branch: `feature/w2-tilemap-render`

Allowed:

- `engine/systems/render_system.py`
- `tests/test_render_graph.py`
- tilemap render docs

Forbidden:

- `engine/components/tilemap.py`
- `engine/api/_authoring_api.py`
- `engine/tilemap/collision_builder.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/core/game.py`
- `engine/editor/*`

### Branch: `feature/w3-tilemap-collision`

Allowed:

- `engine/tilemap/collision_builder.py`
- `tests/test_tilemap_collision.py`
- minimal, justified changes in `engine/app/runtime_controller.py`
- tilemap collision docs

Forbidden:

- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/systems/render_system.py`
- `engine/components/tilemap.py`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`

### Branch: `feature/w4-physics-core`

Allowed:

- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/rigidbody.py`
- `engine/physics/*`
- `engine/app/runtime_controller.py`
- physics/runtime tests
- physics docs

Forbidden:

- `engine/components/tilemap.py`
- `engine/tilemap/collision_builder.py`
- `engine/systems/render_system.py`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`
- `engine/editor/*`
- `engine/api/_authoring_api.py`

## Testing expectations

Before reporting completion:

- run focused tests for the touched subsystem
- run additional regression tests when the change touches shared contracts
- do not disable tests to get green output
- do not claim lint/typecheck/bandit success unless you actually ran them

Minimum commands commonly useful in this repo:

```bash
py -m unittest discover -s tests
py -m ruff check engine cli tools main.py
py -m mypy engine cli tools main.py
```

Use narrower test selection when appropriate, but state exactly what you ran.

## Parallel merge discipline

Every final delivery should include:

1. a short technical summary
2. exact files changed
3. exact tests added or modified
4. exact tests run
5. remaining risks or limitations
6. confirmation that no forbidden files were touched

## Stop conditions

Stop and ask for review instead of continuing if:

- the task requires a forbidden file
- the task requires widening the branch perimeter
- the task would change a core invariant
- the task would create a new public contract without explicit approval

## Practical rule

Prefer a smaller correct change over a broader risky one.
Do not optimize for local completion if it harms merge safety.
