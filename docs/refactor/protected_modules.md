# Protected modules

Date: 2026-07-01

## Protected files

- `engine/api/engine_api.py`
- `engine/api/_*_api.py`
- `engine/scenes/scene.py`
- `engine/scenes/scene_manager.py`
- `engine/serialization/schema.py`
- `engine/ecs/component.py`
- `engine/ecs/world.py`
- `engine/ecs/entity.py`
- `engine/levels/component_registry.py`
- `engine/physics/backend.py`
- `engine/physics/legacy_backend.py`
- `engine/core/game.py`
- `engine/core/runtime_contracts.py`

## Protected contracts

- Scene v2.
- Prefabs.
- Public `EngineAPI`.
- `EDIT -> PLAY -> STOP`.
- `legacy_aabb` fallback.
- Existing scene compatibility.
- AI agent compatibility.
- Graphical editor.
- Existing serialization and migrations.

## Current phase handling

`engine/ecs/world.py` is protected, but phase 1 touched it only for internal query cache invalidation and added focused tests. Phase 2 did not modify it.

No protected public API, scene manager, schema, editor, physics backend, or serialization file was modified in phase 2.

## Runtime input/picking phase handling - 2026-07-02

- `engine/core/game.py` is protected and was modified because runtime input must be updated by the engine before `ScriptBehaviourSystem.update()`. The change is limited to service creation, service injection, and input snapshots for PLAY/runtime.
- `engine/core/runtime_contracts.py`, scene serialization, physics backends, Scene v2, prefabs, and public `EngineAPI` were not modified.
- `engine/systems/render_system.py` was modified to expose visual bounds and picking from the render source of truth. This keeps hit testing aligned with render order instead of duplicating card bounds in scripts.
- Rollback path: restore `Game` service wiring, remove runtime input/picking services from script contexts, and restore the previous solitaire controller. If `EDIT -> PLAY -> STOP` regresses, keep null services in `ScriptBehaviourContext` and stop using the API from solitaire until replanned.
