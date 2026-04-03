---
name: platformer-2d-builder
description: Build or extend 2D side-scrolling platformer gameplay in this engine. Use when Codex needs to design, scaffold, tune, validate, or verify platformer scenes, player movement, jump feel, traversal, hazards, enemies, collectibles, checkpoints, camera framing, respawn flow, or scene and menu transitions using the repo's EngineAPI, AI workflow CLI, and headless verification surfaces.
---

# Platformer 2D Builder

Build platformer gameplay in small, verifiable slices that fit this engine's serializable scene model, public EngineAPI boundary, and AI-assisted workflow surfaces.

Prioritize feel, readability, and progression over feature count. Prefer native components and explicit scene data first, then add small engine extensions only when the current public surfaces cannot express the requested mechanic.

## Skill Identity

### Purpose

- Build or extend a 2D side-scrolling platformer using the engine's existing scene, component, workflow, validation, and headless verification contracts.
- Help agents turn vague platformer requests into small implementation slices with explicit validation and verification after each slice.

### Use When

- Build a new platformer room, route, menu flow, or checkpoint loop.
- Tune movement, jump feel, camera framing, hazards, scene flow, or respawn behavior.
- Add platformer-adjacent systems such as pickups, patrol hazards, or goal transitions in a staged way.
- Prepare `ai-context`, `ai-validate`, `ai-verify`, or split authoring requests for platformer work.

### Do Not Use When

- Build a genre that is not centered on grounded traversal, jumps, hazards, and checkpointed progression.
- Invent unsupported systems in one pass without checking the current component registry, schema, and workflow services.
- Perform broad engine architecture work that is not specifically in service of platformer gameplay.

## Genre Mental Model

A strong platformer in this engine is readable first, expressive second, and broad only after the basics are stable.

- Make the player controller predictable before adding more content.
- Make collisions and hazard shapes easy to read before tuning difficulty.
- Teach one mechanic at a time, then combine mechanics after the base route is fair.
- Keep the camera useful for upcoming jumps and recovery spaces.
- Prefer a short, polished route with reliable respawn and transition flow over a large scene with unstable feel.

## Engine-Aligned Workflow

Treat `EngineAPI` as the mutation boundary. Do not bypass it with direct runtime internals, ad hoc scene mutation paths, or raw scene-file edits when a public workflow already exists.

Follow this sequence:

1. Inspect context first.
   - Run `py -3 -m tools.engine_cli ai-context --project-root .`
   - Inspect the active scene, registered components, existing scene flow, and examples such as `levels/platformer_test_scene.json` and `levels/main_menu_scene.json`.
2. Propose one small implementation slice.
   - Name the slice, target scene, expected entities/components, and verification goal before editing.
3. Run workspace-only authoring if scene lifecycle changes are needed.
   - Use a separate execution request for `create_scene`, `open_scene`, `activate_scene`, or `save_scene`.
4. Run transactional scene edits separately.
   - Use a separate execution request for `create_entity`, `add_component`, `edit_component_field`, `instantiate_prefab`, or `set_scene_flow_connection`.
5. Validate after structural changes.
   - Use `py -3 -m tools.engine_cli ai-validate --target active-scene`
   - Use `scene-file`, `scene-transitions`, or `project` validation targets when the saved artifact or project graph matters.
6. Save before persisted verification.
   - Verification reads saved project content. If headless verification must observe the latest scene edits, save first in a workspace-only step.
7. Verify headlessly with explicit assertions.
   - Use `py -3 -m tools.engine_cli ai-verify --scenario <path>`
   - Prefer machine-checkable assertions over prose claims.
8. Iterate only after a passing or explainable failing report.
   - Fix one slice at a time.
   - Do not start enemies, collectibles, or scene flow polish while movement or collision is still unstable.

Never mix workspace lifecycle operations and transactional scene edits in one execution request. The repo intentionally rejects that combination to preserve rollback behavior, active-scene targeting, and predictable persistence.

Automation-owned and headless runs should remain deterministic and project-local. Assume `.motor/ai_assist_state` is the state root for isolated workflow and verification runs.

## Platformer Design Heuristics

### Player Controller Feel

- Start with native controller surfaces.
  - Use `PlayerController2D` for the lightest slice.
  - Use `CharacterController2D` when you need explicit gravity, max fall speed, or floor snap controls.
- Tune baseline feel with existing fields before proposing new engine work.
  - `move_speed`
  - `jump_velocity`
  - `air_control`
  - `gravity`
  - `max_fall_speed`
  - `floor_snap_distance`
- Keep grounded and airborne control intentionally different. Full air control should be a choice, not a default.
- Treat acceleration and deceleration as a design goal, not as an assumed built-in feature. Add them only as an explicit follow-up extension if native controller behavior is not enough.

### Jump Tuning

- Tune jump arc with native data first.
  - `PlayerController2D.jump_velocity`
  - `CharacterController2D.jump_velocity`
  - `CharacterController2D.gravity`
  - `CharacterController2D.max_fall_speed`
- Frame coyote time, jump buffering, and variable jump height as explicit follow-up extensions. They are not native controller features in the current repo.
- Validate baseline jump reliability before extending feel logic. A stable simple jump is better than a half-implemented advanced jump stack.

### Traversal Building Blocks

- Start with static floors, platforms, and gaps.
- Use slopes, stairs, moving platforms, one-way platforms, ladders, and spring or launch interactions only after confirming engine support or explicitly adding the missing support.
- Keep platform widths, collision shapes, and landing spaces readable. Avoid narrow collision margins until the controller is already proven stable.
- Use `Camera2D.follow_entity`, `framing_mode`, dead zones, and clamp fields to keep upcoming jumps visible.

### Level Structure

- Begin with a safe onboarding area that proves movement, jump, and landing.
- Introduce one traversal or hazard idea at a time.
- Escalate with combinations only after each standalone mechanic is fair.
- Insert short recovery windows after harder sections.
- Place checkpoints before materially harder sequences, not after them.
- Place rewards where they reinforce intended movement, not where they create blind detours.

### Hazards, Enemies, Collectibles, and Checkpoints

- Use trigger-based hazards first.
  - `Collider.is_trigger = true`
  - rules on `on_trigger_enter`
  - explicit respawn or transition behavior
- Add enemies only after movement, landing, and hazard reset flow are stable.
- Use collectibles only if they can be represented cleanly with existing components, rules, or a small explicit extension. Do not invent a fake collectible system in scene JSON.
- Prefer scene-data checkpoint flow over hidden state. A practical native pattern is:
  - `SceneEntryPoint` on the respawn target
  - `SceneTransitionOnPlayerDeath`
  - `SceneTransitionAction` targeting the current scene and entry id
  - hazard rules that emit `player_death`

### Readability and Fairness

- Avoid blind jumps.
- Avoid collision silhouettes that disagree with the visible geometry.
- Avoid hazards without a clear reset or recovery path.
- Avoid failure loops that immediately re-trigger damage on respawn.
- Keep goal placement visible or clearly foreshadowed.

## Current Support Boundaries

Treat these as supported now:

- horizontal movement speed
- airborne control through `air_control`
- jump impulse through `jump_velocity`
- gravity and terminal fall through `CharacterController2D.gravity` and `max_fall_speed`
- floor snap through `floor_snap_distance`
- trigger-based hazards
- camera follow and platformer framing
- scene flow and headless assertion checks

Treat these as explicit follow-up extensions, not native assumptions:

- coyote time
- jump buffering
- variable jump height
- dedicated checkpoint component
- dedicated collectible component
- dedicated enemy patrol component
- moving platform primitives
- one-way platform primitives
- ladder or climb systems

If you need one of the follow-up features, state that it is not native, implement the smallest explicit extension, and add matching validation and tests instead of inventing silent scene fields.

## Recommended Implementation Slices

1. Slice 1: scene, floor, spawn, camera.
   - Create or open the target scene, establish the player start, add a walkable floor, and wire a primary `Camera2D`.
   - Verify `Player`, `MainCamera`, and floor entities exist, the camera follows the player, and the scene loads headlessly.
2. Slice 2: movement, jump, and landing sanity.
   - Add `InputMap` plus either `PlayerController2D` or `CharacterController2D`, then tune only the native movement and jump fields needed for a reliable first jump.
   - Verify controller component presence, key field values, `PLAY` state health, and basic frame progression.
3. Slice 3: hazards and death/reset loop.
   - Add one readable hazard volume and a deterministic reset path.
   - Verify the hazard entity exists, uses a trigger collider, and the reset or death transition entities and fields are present.
4. Slice 4: collectibles or pickups if the project has a supported representation.
   - Keep the first pickup loop minimal and inspectable.
   - Verify pickup entities, trigger shapes, and any saved feedback wiring that already exists.
5. Slice 5: checkpoints.
   - Represent checkpoints with explicit scene data, entry points, rules, and transitions before considering a dedicated system.
   - Verify `SceneEntryPoint`, death transition wiring, and target scene or entry ids.
6. Slice 6: enemies or patrol hazards.
   - Add only one enemy behavior pattern after movement and collision are already trusted.
   - Prefer a prefab or one explicit reusable pattern over bespoke one-off hazards.
7. Slice 7: goal object plus scene transition.
   - Add a clear goal volume, door, or flag and wire the next scene flow or transition target.
   - Verify the goal entity, flow key or transition target, and that the next scene can load.
8. Slice 8: menu, pause, and restart flow.
   - Connect the gameplay scene to menu UI and restart or return flow using supported UI and scene-flow surfaces.
   - Verify menu buttons, scene flow keys, and transition targets with saved-scene verification.

Read `references/verification-recipes.md` before writing platformer verification scenarios.

## Agent Behavior Rules

- Use the engine's public API and workflow surfaces instead of private internals.
- Keep workspace operations separate from transactional scene-edit operations.
- Validate after structural changes.
- Save before verification when verification depends on persisted scene content.
- Use headless verification for smoke tests.
- Work incrementally in small, testable slices.
- Avoid overbuilding.
- Avoid inventing unsupported engine systems or scene fields.
- Avoid editing raw scene files directly when public workflows already exist.
- Avoid giant one-shot game generation.
- Prefer deterministic, inspectable changes.
- Prefer reusable prefabs or component patterns once a pattern stabilizes.
- Keep names, paths, scene refs, flow keys, and entry ids consistent.
- Check `engine/levels/component_registry.py` before adding components.
- If you add a new engine feature for advanced platformer feel, also update schema or validation coverage and add tests.

## Verification Guidance

Use `ai-verify` to check saved project facts that matter to a platformer slice. Good baseline assertions include:

- `entity_exists` for `Player`, `MainCamera`, floor, hazards, checkpoints, and goal objects
- `component_exists` for controller, collider, camera, transition, and scene-link components
- `component_field_equals` for movement values, camera follow target, trigger flags, entry ids, and transition targets
- `selected_scene_is` for active-scene sanity
- `scene_flow_target_can_be_loaded` for next-scene or menu flow keys
- `recent_event_exists` when the engine emits stable events that your slice depends on
- `engine_status_sanity` for state, frame count, and entity-count smoke checks

For runtime behavior that depends on deterministic input, combine saved-scene verification with focused `EngineAPI` probes in a follow-up check. Do not pretend that a static assertion proves dynamic feel.

## Anti-Patterns

- Mixing workspace and transactional authoring in one request
- Verifying unsaved scene changes via a saved-scene verification path
- Building a full multi-level platformer in one pass
- Adding enemies before movement and collision are solid
- Creating unfair jumps without readable setup
- Creating hazards without a safe reset flow
- Treating advanced jump-feel features as if they already exist natively
- Inventing unsupported components, fields, or link modes
- Hiding checkpoint or collectible state in ad hoc runtime-only data when scene data should express it

## Output Examples

Use prompts like these when applying the skill:

- `Use $platformer-2d-builder to create a beginner platformer room with a player spawn, one floor, one jumpable platform, and a platformer camera. Keep it to one slice and include validation plus headless verification.`
- `Use $platformer-2d-builder to add a hazard pit and a respawn checkpoint to the active scene. Use explicit scene data, save before verification, and verify the reset wiring.`
- `Use $platformer-2d-builder to add a goal door that transitions to the next scene. Keep scene flow references consistent and verify that the target scene can load.`
- `Use $platformer-2d-builder to tune jump feel for a more responsive controller without inventing unsupported features. Start with native fields, explain tradeoffs, and verify the saved tuning values plus a headless play smoke test.`

## Reference

Read `references/verification-recipes.md` when you need:

- `ai-verify` scenario templates
- split workflow reminders for saved-scene verification
- platformer-focused assertion recipes for room bootstrap, hazards, checkpoints, goals, and jump tuning
