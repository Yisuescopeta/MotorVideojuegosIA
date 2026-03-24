---
name: turn-based-combat-rpg
description: Build or extend turn-based combat RPG systems in this IA-first engine. Use when the request involves initiative order, actions, abilities, status effects, party state, enemy AI turns, encounter flow, loot, battle resolution, or a complete turn-based combat loop.
metadata:
  audience: combat-authoring
  genre: turn-based-rpg
  compatibility: motor-videojuegos-ia
license: Proprietary-Project
---

# Turn Based Combat RPG

Build turn-based combat against the engine that exists today: ECS entities, scene JSON, `feature_metadata`, `ScriptBehaviour`, `EventBus`, `RuleSystem`, deterministic seeds, snapshots, and headless validation. Do not assume there is already a built-in combat system, action queue, or status-effect framework.

## When To Use Me

- Use this skill for initiative order, party state, abilities, targeting, buffs/debuffs, combat logs, deterministic battle replay, and encounter-resolution loops.
- Use this skill when the implementation must cite real engine surfaces such as `engine/serialization/schema.py`, `engine/components/scriptbehaviour.py`, `engine/systems/script_behaviour_system.py`, `engine/events/event_bus.py`, `engine/events/rule_system.py`, `engine/core/game.py`, `engine/debug/timeline.py`, `engine/debug/golden_run.py`, `engine/systems/ui_system.py`, `engine/systems/ui_render_system.py`, and `engine/components/audiosource.py`.
- Use this skill when combat must stay serializable, replayable, and headless-friendly.

## When NOT To Use Me

- Do not use this skill for platformer loops, visual novel flow, or UI-only menu work.
- Do not claim the repo already has native `Combatant`, `Ability`, `StatusEffect`, or battle-state components. Those do not exist in `engine/components/` today.
- Do not put turn state, targeting state, or resolution rules inside overlay widgets. UI only renders combat state.

## Real Engine Surface

- `engine/serialization/schema.py`
  Scene JSON is versioned with `schema_version`, `name`, `entities`, `rules`, and `feature_metadata`. Reuse that envelope for battle data.
- `engine/components/scriptbehaviour.py` and `engine/systems/script_behaviour_system.py`
  Serializable hook point for encounter logic, state transitions, and battle resolution.
- `engine/events/event_bus.py` and `engine/events/rule_system.py`
  Event-driven triggers for combat logs, aftermath, animation/audio cues, and simple reactions.
- `engine/core/game.py`
  Global RNG is controlled through `set_seed()`, which seeds Python `random`. Use this for deterministic battle replay.
- `engine/debug/timeline.py` and `engine/debug/golden_run.py`
  Replay and snapshot infrastructure for deterministic headless validation.
- `engine/systems/ui_system.py`, `engine/systems/ui_render_system.py`, `engine/components/uitext.py`, `engine/components/uibutton.py`
  Overlay UI for action menus and combat log rendering only.
- `engine/components/audiosource.py` and `engine/systems/audio_system.py`
  Serializable BGM/SFX playback. There is no audio-bus or mixer system in the current repo.

## Combat Data Model

1. Put encounter authority in JSON, usually under `feature_metadata.turn_based_battle`.
2. Model explicit data objects:
   - `combatants`
   - `parties`
   - `moves` or `abilities`
   - `targeting`
   - `status_effects`
   - `battle_context`
3. Use stable ids and explicit stats. Keep HP, speed, buffs, durations, and selected actions in data.
4. If you need reusable engine primitives later, split that into a separate engine task instead of hiding it in content scripts.

## Turn Loop

Implement combat as an explicit state machine. Recommended states:

- `StartTurn`
- `SelectActions`
- `OrderActions`
- `Resolve`
- `EndTurn`

State ownership belongs in the battle model or a dedicated `ScriptBehaviour.public_data` runtime cache, not in UI buttons.

## Ordering Policy

- Sort actions by:
  1. higher `priority`
  2. higher actor `speed`
  3. deterministic tie-break using the seeded RNG
- Always control randomness through the engine seed or an explicitly seeded `random.Random`.
- Never introduce unseeded randomness in damage rolls, crits, or initiative.

## Effects And Triggers

- Represent `StatusEffect` as explicit data with:
  - id
  - stacks or magnitude
  - remaining duration
  - trigger timing such as `on_apply`, `on_turn_start`, `on_before_action`, `on_after_action`, `on_turn_end`
- Resolve damage, healing, buffs, debuffs, and persistent states in one pipeline.
- Use `EventBus` and `RuleSystem` for emitted combat events, logs, animation hooks, and audio cues, but keep the authoritative math in battle logic.

## Data, Logic, And UI Separation

- DATA:
  Battle context, combatants, parties, abilities, order, and status effects live in JSON or other serializable data.
- LOGIC:
  `ScriptBehaviour` and deterministic helpers compute targeting, order, damage, and status updates.
- UI:
  `Canvas`, `UIText`, and `UIButton` render menus and logs only. They should dispatch explicit action ids, never own battle truth.

## Validation

- Use unit tests for the damage pipeline, status application, and action order.
- Use the real CLI for schema and smoke validation:
  - `py -3 tools/engine_cli.py validate --target scene --path levels/<battle_scene>.json`
  - `py -3 tools/engine_cli.py smoke --scene levels/<battle_scene>.json --frames 5 --seed 123 --out-dir artifacts/battle_smoke`
  - `py -3 tools/engine_cli.py run-headless levels/<battle_scene>.json --frames 30 --seed 123 --debug-dump artifacts/battle_headless/debug_dump.json`
- For replay evidence, save transcripts or state captures under `artifacts/`.
- There is no dedicated battle dataset pipeline in the current repo. Do not imply one exists.

## Implementation Guidance

- Prefer one encounter-owner entity with `ScriptBehaviour` that reads `feature_metadata.turn_based_battle`.
- Keep combat logs as serializable arrays of events and write them to `artifacts/` during tests or smoke runs.
- If the request needs reusable status-effect components, item systems, aggro, or meta-progression, call those out as follow-up engine tasks.
- Audio and UI hooks should subscribe to combat events, not embed combat rules.

## Checklist De Aceptacion

- Combat state is data-driven under the current scene schema.
- Turn flow is an explicit state machine and not inferred from UI interaction.
- Action order uses priority, speed, and a seeded deterministic tie-break.
- Damage, buffs, debuffs, and persistent effects are resolved in one explicit pipeline.
- Logs, replay evidence, or snapshots are produced without relying on visual inspection.
- UI only renders action choices and combat state.
- Any missing engine primitive is called out as separate work instead of being implied as already available.

## Read Next

Read [references/TURN_BASED_PIPELINE.md](references/TURN_BASED_PIPELINE.md) for the data shape, text diagrams, and pseudocode for a minimal deterministic encounter.
