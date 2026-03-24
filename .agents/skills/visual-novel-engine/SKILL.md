---
name: visual-novel-engine
description: Build or extend visual novel systems in this IA-first engine. Use when the request involves dialogue flow, branching choices, scene transitions, character states, scripted events, relationship flags, save-friendly story progression, or a complete visual novel loop.
metadata:
  audience: narrative-authoring
  genre: visual-novel
  compatibility: motor-videojuegos-ia
license: Proprietary-Project
---

# Visual Novel Engine

Build visual novel features against the engine that exists today: scene JSON, `feature_metadata`, serializable components, `ScriptBehaviour`, declarative UI, and headless validation. Do not assume a hidden VN runtime, save system, or UI-owned branching state.

## When To Use Me

- Use this skill for dialogue flow, branching, flags, scene replay, save-slot design, portraits, choice menus, and audio-cued narrative scenes.
- Use this skill when the implementation must cite and use real engine surfaces such as `engine/systems/ui_system.py`, `engine/systems/ui_render_system.py`, `engine/components/uitext.py`, `engine/components/uibutton.py`, `engine/components/scriptbehaviour.py`, `engine/events/rule_system.py`, `engine/components/audiosource.py`, `engine/serialization/schema.py`, and `tools/engine_cli.py`.
- Use this skill when the narrative loop must remain serializable and runnable headless.

## When NOT To Use Me

- Do not use this skill for platformer movement, combat loops, or UI polish unrelated to narrative state.
- Do not use this skill to imply that the repo already has a dedicated `DialogueGraph`, `FlagStore`, or `SaveSlot` engine primitive. If you need a reusable core runtime beyond data plus scripts, open a separate engine task.
- Do not couple route progression, branching, or flags to button widgets, overlay state, or editor-only memory.

## Real Engine Surface

- `engine/serialization/schema.py`
  Scene JSON is versioned with `schema_version`, `name`, `entities`, `rules`, and `feature_metadata`. Reuse this format first.
- `engine/systems/ui_system.py`, `engine/systems/ui_render_system.py`, `engine/components/canvas.py`, `engine/components/recttransform.py`, `engine/components/uitext.py`, `engine/components/uibutton.py`
  Declarative overlay UI. Use it only to render dialogue text, portraits, and choice buttons, then emit explicit actions or events.
- `engine/components/scriptbehaviour.py` and `engine/systems/script_behaviour_system.py`
  Serializable Python hook point with `public_data` for runtime-local state and access to the world, scene manager, and scene-flow loader.
- `engine/events/event_bus.py` and `engine/events/rule_system.py`
  Event-driven branching, scene transitions, logs, and lightweight reactions without hiding authority in UI.
- `engine/components/audiosource.py` and `engine/systems/audio_system.py`
  Serializable audio cues through `AudioSource`. There is no audio-bus system in the current repo.
- `engine/debug/timeline.py`, `engine/debug/golden_run.py`, and `tests/test_headless_harness.py`
  Deterministic replay/debug building blocks for transcript-like validation and branch regression checks.
- `engine/project/project_service.py`
  Persists project/editor data such as `project.json`, `.motor/editor_state.json`, and project settings. This is not a player-facing save-slot runtime.

## VN Runtime Design

1. Model the VN runtime as data inside scene JSON, usually under `feature_metadata.vn_runtime`.
2. Keep the data versioned and explicit:
   - `dialogue_graph` or `dialogue_script`
   - `nodes`
   - `choices`
   - `conditions`
   - `flag_store`
   - `save_slots`
3. Keep authority in data and logic:
   - `UIText` renders the active line.
   - `UIButton` renders available choices.
   - `ScriptBehaviour` or explicit event handlers decide the next node and update flags.
4. Treat `SaveSlot` as a serializable JSON model, not as an already-built engine service.
5. If the request needs a reusable global save/load runtime, create a separate engine task instead of faking one in UI code.

## Data, Logic, And UI Separation

- DATA:
  Put narrative graphs, flags, current node ids, portrait ids, and replay metadata in scene JSON or other serializable JSON files referenced from the scene.
- LOGIC:
  Use `ScriptBehaviour.public_data`, `RuleSystem`, and emitted events to evaluate conditions, mutate flags, and request scene transitions.
- UI:
  Use `Canvas`, `UIText`, and `UIButton` only to display the current line, portraits, and valid choices. UI should never be the source of truth for route state.

## Feature Guidance

- Typewriter:
  If the request only needs presentation, implement it as display state in a dedicated script or UI presenter. Keep the full line text in narrative data.
- Choice menus and branching:
  Choices should reference explicit `next_node` ids and optional conditions. Branch selection must update flags in data, not infer state from UI clicks.
- Flags and conditions:
  Use a JSON `flag_store` object with stable keys and simple values. If conditions grow beyond simple equality and presence checks, define them explicitly in JSON and evaluate them in one place.
- Save/load and replay:
  There is no generic save system today. Store the proposed save payload as JSON and validate the serialization contract. If a real save service is needed, separate that engine task from content authoring.
- Audio cues:
  Use `AudioSource` entities for BGM, SFX, and voice triggers. If later the engine gains buses or mixers, migrate to them explicitly; do not assume they exist now.
- Scene transitions:
  Use scene JSON plus `scene_flow` metadata or explicit scene loads from script context. Do not bury transitions inside UI-only code paths.

## Tooling And Validation

- Validate scene payloads with the real CLI:
  - `py -3 tools/engine_cli.py validate --target scene --path levels/<vn_scene>.json`
- Run deterministic smoke headlessly:
  - `py -3 tools/engine_cli.py smoke --scene levels/<vn_scene>.json --frames 5 --seed 123 --out-dir artifacts/vn_smoke`
  - `py -3 tools/engine_cli.py run-headless levels/<vn_scene>.json --frames 30 --seed 123 --debug-dump artifacts/vn_headless/debug_dump.json`
- Reuse `tests/test_schema_validation.py` and `tests/test_headless_harness.py` patterns for offline validation.
- There is no dedicated dialogue-dataset CLI in the current repo. If a request needs dialogue dataset generation, treat it as a separate workflow and do not pretend an existing dataset pipeline already covers VN scripts.

## Implementation Guidance

- Prefer one scene-level runtime owner entity with `ScriptBehaviour` that reads `feature_metadata.vn_runtime`.
- Keep portraits, speaker nameplates, and choices declarative as entities under a `Canvas`.
- If you need route-specific side effects, emit events or mutate a dedicated narrative state object; do not spread flag writes across unrelated scripts.
- If a requested feature depends on missing engine primitives such as persistent save slots, voice mixing buses, or a dedicated timeline authoring system, say so and split it into a follow-up task.

## Checklist De Aceptacion

- The VN loop is data-driven and serializable under the current scene schema.
- Branching authority lives in data plus logic, not in UI state.
- `feature_metadata`, `ScriptBehaviour.public_data`, or explicit JSON files hold flags and current-node state.
- UI entities only render text, portraits, and valid choices.
- Audio cues use real `AudioSource` paths instead of invented bus APIs.
- The proposal distinguishes existing engine systems from follow-up engine work.
- Validation includes schema checks plus at least one headless or unit path that proves branch progression and flag mutation.
- Outputs and transcripts, when generated, go to `artifacts/`.

## Read Next

Read [references/VN_DATA_MODEL.md](references/VN_DATA_MODEL.md) for the concrete JSON shape, example conditions, and a minimal branching template.
