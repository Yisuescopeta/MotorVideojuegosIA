---
name: platformer-2d
description: Build or extend a 2D platformer vertical slice in this IA-first engine. Use when the request involves CharacterController2D or PlayerController2D movement, jumps, tilemap collision, hazards, checkpoints, respawn, camera follow, animation states, trigger rules, deterministic headless validation, or a complete serializable platformer loop.
metadata:
  audience: gameplay-authoring
  genre: platformer
  compatibility: motor-videojuegos-ia
license: Proprietary-Project
---

# Platformer 2D

Build platformer features against the real engine surface, not against assumed APIs. Prefer serializable scene data, registered components, `ScriptBehaviour`, event rules, and deterministic CLI validation.

## When To Use Me

- Use this skill for platformer movement, jump tuning, camera follow, checkpoints, hazards, respawn, collectibles, tile collisions, and a vertical slice that must run headless.
- Use this skill when the implementation should be anchored to real classes such as `engine/components/charactercontroller2d.py`, `engine/components/playercontroller2d.py`, `engine/components/camera2d.py`, `engine/components/tilemap.py`, `engine/components/animator.py`, `engine/events/rule_system.py`, and `engine/systems/physics_system.py`.
- Use this skill when the output must remain serializable in `levels/`, `prefabs/`, `scripts/`, and `feature_metadata`, not hidden in UI or editor-only state.

## When NOT To Use Me

- Do not use this skill for UI-first menu work, visual novel flow, or turn-based combat.
- Do not use this skill to invent engine primitives that are not present. If the feature needs a new core component or system and no existing path fits, create a separate engine task instead of smuggling it into gameplay content.
- Do not use this skill when the request is purely cosmetic and unrelated to platformer behavior.

## Real Engine Surface

- `engine/components/charactercontroller2d.py`
  Data-driven kinematic platformer controller with `move_speed`, `jump_velocity`, `gravity`, `max_fall_speed`, `air_control`, `floor_snap_distance`, `move_mode`, `on_floor`, and collision normals.
- `engine/systems/character_controller_system.py`
  Applies `InputMap`, slide/collide sweeps, floor snap, and emits `on_collision`.
- `engine/components/playercontroller2d.py` plus `engine/systems/player_controller_system.py`
  Simpler `RigidBody`-based movement path. Use it only when the request does not need controller-specific slide semantics.
- `engine/components/inputmap.py` and `engine/systems/input_system.py`
  Declarative input bindings and `last_state` values. Keep gameplay authority out of UI.
- `engine/components/tilemap.py` plus `engine/tilemap/collision_builder.py`
  Serializable tile layers and runtime baking of solid tile colliders from `flags`, `tags`, or `custom.collision`.
- `engine/components/camera2d.py` plus `engine/systems/render_system.py`
  Platformer camera follow via `follow_entity`, `framing_mode`, `dead_zone_width`, `dead_zone_height`, clamps, and `recenter_on_play`.
- `engine/components/animator.py` plus `engine/systems/animation_system.py`
  Serializable animation states with `idle`, `run`, `jump`, and `on_animation_end` support.
- `engine/events/event_bus.py` and `engine/events/rule_system.py`
  Declarative reactions for hazards, goals, and lightweight respawn flows.
- `cli/runner.py`, `cli/headless_game.py`, `tools/engine_cli.py`, and `tests/test_headless_harness.py`
  Deterministic headless harness and smoke path.

## Vertical Slice Workflow

1. Start from a minimal playable loop, not a full game.
2. Build the slice in serializable data:
   - a player entity
   - solid ground or baked tilemap collision
   - one hazard or death path
   - one checkpoint or respawn point
   - one goal trigger
   - one primary `Camera2D`
3. Choose one movement path:
   - Prefer `CharacterController2D` when the request needs controller feel, floor snap, slide/collide semantics, or later game-feel extensions.
   - Use `PlayerController2D` only for simpler `RigidBody`-driven movement.
4. Use `Animator` states named `idle`, `run`, and `jump` when sprite animation is required because `engine/systems/player_controller_system.py` already targets those names.
5. Implement checkpoint, death, and respawn as serializable behavior:
   - If `RuleSystem` is enough, use `on_trigger_enter`, `set_position`, `emit_event`, and `log_message`.
   - If stateful checkpoint memory is needed, use `ScriptBehaviour.public_data` and `engine/components/scriptbehaviour.py`.
   - There is no built-in `Checkpoint` or `Respawn` component today. If the request needs a reusable engine primitive, create a separate task.

## Game Feel Guidance

- For coyote time, jump buffering, variable jump, halved gravity, corner correction, or momentum transfer:
  - If the current request can be expressed by extending `CharacterController2D` data and `engine/systems/character_controller_system.py`, do that.
  - If those fields do not exist yet, add them only when the task explicitly includes engine work and validate them with dedicated tests.
  - Otherwise, state clearly that the requested feel feature requires a separate engine task.
- Do not fake these mechanics in UI code.
- Do not add hidden non-serializable state as the source of truth. If runtime scratch state is needed, mirror the tunables in component data and keep the runtime-only bits minimal.

## ECS And Data Rules

- Keep authoritative state in components, scene JSON, `feature_metadata`, or `ScriptBehaviour.public_data`.
- Prefer one responsibility per script. Separate locomotion, checkpoint memory, hazard handling, and goal handling when possible.
- Use `SceneLink` only for explicit scene transitions, not for local respawn.
- Prefer baked tilemap colliders for authored level geometry and direct `Collider` entities for simple blockout.
- Use `EngineAPI` helpers such as `create_entity`, `create_camera2d`, `create_input_map`, `create_tilemap`, `set_tilemap_tile`, `set_feature_metadata`, and `set_physics_layer_collision` when generating or editing scenes programmatically.
- Do not make HUD, editor inspector state, or camera state the source of truth for checkpoint progression or death logic.

## Validation

- Canonical examples already in the repo:
  - `tests/visual_basic_platformer.json`
  - `levels/platformer_test_scene.json`
  - `tests/test_character_controller.py`
  - `tests/test_tilemap_collision.py`
  - `tests/test_headless_harness.py`
- When you add or revise a vertical slice, prefer:
  - `py -3 -m unittest tests.test_character_controller tests.test_tilemap_collision tests.test_headless_harness`
  - `py -3 tools/engine_cli.py smoke --scene levels/platformer_test_scene.json --frames 5 --seed 123 --out-dir artifacts/platformer_smoke`
- If you add a new canonical scene, keep it headless-friendly and validate it through the unified CLI, not through editor-only interaction.
- Always write evidence to `artifacts/`.

## Checklist De Aceptacion

- The slice has movement, jump, collision, camera follow, death path, and respawn or checkpoint behavior.
- Gameplay authority is serializable and does not depend on UI state.
- The implementation cites and uses the real engine surface instead of invented APIs.
- `CharacterController2D` or `PlayerController2D` choice is justified.
- Tile collision is backed by `Collider` entities or `Tilemap` plus `engine/tilemap/collision_builder.py`.
- Hazard and goal logic is expressed with rules or serializable scripts.
- Camera uses `Camera2D` follow and clamp fields instead of ad hoc render hacks.
- Validation runs through real repo commands and writes outputs to `artifacts/`.
- Any missing engine primitive is called out as a separate task instead of being implied as already available.

## Read Next

Read [references/PLATFORMER_PATTERNS.md](references/PLATFORMER_PATTERNS.md) for implementation notes, pseudocode, and decision rules that should not live in the main skill body.
