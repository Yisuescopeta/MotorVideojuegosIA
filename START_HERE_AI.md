# MotorVideojuegosIA - AI Quick Start

**Project**: MotorVideojuegosIA
**Engine Version**: 2026.03

## Overview
This project uses MotorVideojuegosIA, a 2D game engine designed for AI-assisted development.

## Implemented Capabilities

The entries below are available now and are safe to use from the CLI.

### Most Common Operations

- **ai:start**: Show the compact AI entrypoint contract for this project
  - API: `CapabilityRegistry.cmd_ai_start`
  - CLI: `motor ai start [--project <path>] [--json]`

- **ai:compliance**: Validate whether a project follows the AI-native engine contract
  - API: `AssetsProjectAPI.run_ai_compliance`
  - CLI: `motor ai compliance [--project <path>] [--strict] [--json]`

- **scene:load**: Load a scene from a JSON file path
  - API: `SceneWorkspaceAPI.load_level`
  - CLI: `motor scene load <path>`

- **scene:save**: Save the active scene to its source file
  - API: `SceneWorkspaceAPI.save_scene`
  - CLI: `motor scene save [--project <path>]`

- **scene:create**: Create a new scene with a unique file path
  - API: `SceneWorkspaceAPI.create_scene`
  - CLI: `motor scene create <name>`

- **entity:create**: Create a new entity with optional components
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor entity create <name> [--components <json>]`

- **component:add**: Add a component to an existing entity
  - API: `AuthoringAPI.add_component`
  - CLI: `motor component add <entity> <component> [--data <json>]`

- **asset:list**: List all assets in the project catalog
  - API: `AssetsProjectAPI.list_project_assets`
  - CLI: `motor asset list [--search <query>]`

- **asset:slice:grid**: Create grid-based slices from a sprite sheet asset
  - API: `AssetsProjectAPI.create_grid_slices`
  - CLI: `motor asset slice grid <asset> --cell-width <w> --cell-height <h>`

- **asset:slice:list**: List all slices defined for an asset
  - API: `AssetsProjectAPI.list_asset_slices`
  - CLI: `motor asset slice list <asset>`

- **animator:set_sheet**: Set the sprite sheet asset for an Animator
  - API: `AuthoringAPI.set_animator_sprite_sheet`
  - CLI: `motor animator set-sheet <entity> <asset>`

- **animator:state:create**: Create or update an animation state
  - API: `AuthoringAPI.upsert_animator_state`
  - CLI: `motor animator state create <entity> <state> --slices <slices...> [--fps <n>] [--loop|--no-loop] [--set-default] [--auto-create]`

- **animator:info**: Get detailed information about an entity's Animator
  - API: `AuthoringAPI.get_animator_info`
  - CLI: `motor animator info <entity>`

- **runtime:play**: Start play mode for a stateless headless runtime check
  - API: `RuntimeAPI.play`
  - CLI: `motor runtime play [--project <path>] [--headless]`

- **runtime:step**: Run PLAY -> STEP -> STOP headlessly for N frames, optionally with simulated InputMap actions
  - API: `RuntimeAPI.step`
  - CLI: `motor runtime step [--project <path>] [--frames <n>] [--input <actions>]`

- **runtime:stop**: Stop runtime in the current stateless headless process
  - API: `RuntimeAPI.stop`
  - CLI: `motor runtime stop [--project <path>]`

- **runtime:status**: Read-only runtime status and active scene info
  - API: `RuntimeAPI.get_status`
  - CLI: `motor runtime status [--project <path>]`

- **runtime:entities**: List entities in the active scene (read-only)
  - API: `RuntimeAPI.list_entities`
  - CLI: `motor runtime entities [--project <path>] [--tag <tag>] [--layer <layer>] [--active-only]`

- **runtime:inspect**: Inspect a specific entity (read-only)
  - API: `RuntimeAPI.get_entity`
  - CLI: `motor runtime inspect <entity> [--project <path>]`

- **runtime:events**: Return recent runtime events, optionally after a headless step
  - API: `RuntimeAPI.get_recent_events`
  - CLI: `motor runtime events [--project <path>] [--count <n>] [--step-frames <n>]`

- **game:platformer:create**: Create a minimal native 2D platformer scene scaffold
  - API: `SceneWorkspaceAPI.create_scene`
  - CLI: `motor game platformer create <name> [--project <path>]`

- **game:platformer:add-coin**: Create or update native platformer Coin in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-coin [--x <px>] [--y <px>] [--points <int>] [--name <entity>] [--project <path>]`

- **game:platformer:add-hazard**: Create or update native platformer Hazard in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-hazard [--x <px>] [--y <px>] [--damage <int>] [--name <entity>] [--project <path>]`

- **game:platformer:add-goal**: Create or update native platformer Goal in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-goal [--x <px>] [--y <px>] [--name <entity>] [--project <path>]`

- **game:platformer:add-respawn**: Create or update native platformer RespawnPoint in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-respawn [--x <px>] [--y <px>] [--id <id>] [--project <path>]`

- **game:platformer:add-moving-platform**: Create or update a named native moving platform in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-moving-platform --name <entity> --x <px> --y <px> --width <px> --height <px> --to-x <px> --to-y <px> --speed <px_per_sec> [--project <path>]`

- **game:platformer:add-enemy-patrol**: Create or update a named native enemy patrol in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-enemy-patrol --name <entity> --x <px> --y <px> --point <x,y> [--point <x,y> ...] --damage <int> --speed <px_per_sec> [--project <path>]`

- **game:platformer:add-checkpoint**: Create or update a named native checkpoint in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-checkpoint --name <entity> --x <px> --y <px> --id <id> [--project <path>]`

- **game:platformer:add-killzone**: Create or update a named native killzone in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer add-killzone --name <entity> --x <px> --y <px> --width <px> --height <px> --damage <int> [--project <path>]`

- **game:platformer:set-camera-follow**: Create or update Camera2D follow settings in the selected platformer scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer set-camera-follow --name <camera> --target <entity> [--offset-x <px>] [--offset-y <px>] [--dead-zone-width <px>] [--dead-zone-height <px>] [--zoom <float>] [--project <path>]`

- **game:platformer:set-bounds**: Create or update native platformer level bounds in the selected scene
  - API: `AuthoringAPI.create_entity`
  - CLI: `motor game platformer set-bounds --name <entity> --left <px> --right <px> --top <px> --bottom <px> [--camera <camera>] [--project <path>]`

- **game:platformer:validate**: Validate selected native platformer scene contract
  - API: `SceneWorkspaceAPI.load_scene_for_runtime_inspection`
  - CLI: `motor game platformer validate [--project <path>]`

- **recipe:list**: List bundled declarative AI recipes
  - API: `RecipeRegistry.list_recipes`
  - CLI: `motor recipe list [--project <path>]`

- **recipe:show**: Show a bundled declarative AI recipe
  - API: `RecipeRegistry.get_recipe`
  - CLI: `motor recipe show <id> [--project <path>]`

- **recipe:run**: Run a bundled declarative AI recipe through allowlisted motor commands
  - API: `RecipeRunner.run_recipe`
  - CLI: `motor recipe run <id> [--project <path>]`

- **introspect:capabilities**: Query this capability registry itself
  - API: `CapabilityRegistry.cmd_capabilities`
  - CLI: `motor capabilities [--json]`

## Capabilities by Category

### AI

- `ai:compliance`: Validate whether a project follows the AI-native engine contract
- `ai:self-test`: Run a controlled AI self-test workflow in a temporary project by default
- `ai:start`: Show the compact AI entrypoint contract for this project

### Scene Management

- `scene:create`: Create a new scene with a unique file path
- `scene:list`: List all available scenes in the project
- `scene:load`: Load a scene from a JSON file path
- `scene:save`: Save the active scene to its source file

### Entity Operations

- `entity:create`: Create a new entity with optional components
- `entity:delete`: Remove an entity from the active scene, reparenting children to grandparent
- `entity:list`: List all entities in the active scene, optionally filtered

### Component Operations

- `component:add`: Add a component to an existing entity
- `component:edit`: Edit a property of an existing component
- `component:remove`: Remove a component from an entity

### Asset Management

- `asset:list`: List all assets in the project catalog
- `asset:slice:auto`: Auto-detect slices from a sprite sheet asset
- `asset:slice:grid`: Create grid-based slices from a sprite sheet asset
- `asset:slice:list`: List all slices defined for an asset
- `asset:slice:manual`: Save manually defined slices for an asset

### Animation

- `animator:ensure`: Ensure Animator exists on entity with optional sheet (creates or updates)
- `animator:info`: Get detailed information about an entity's Animator
- `animator:set_sheet`: Set the sprite sheet asset for an Animator
- `animator:state:create`: Create or update an animation state
- `animator:state:remove`: Remove an animation state from an Animator

### Prefabs

- `prefab:apply`: Apply instance overrides back to the source prefab
- `prefab:create`: Create a prefab asset from an existing entity subtree
- `prefab:instantiate`: Create an entity instance from a prefab file
- `prefab:list`: List all prefabs available in the project
- `prefab:unpack`: Convert a prefab instance to a regular entity

### Project

- `project:bootstrap-ai`: Generate AI bootstrap files (motor_ai.json and START_HERE_AI.md)
- `project:manifest`: Get the current project's manifest summary

### Recipes

- `recipe:list`: List bundled declarative AI recipes
- `recipe:run`: Run a bundled declarative AI recipe through allowlisted motor commands
- `recipe:show`: Show a bundled declarative AI recipe

### Agent

- `agent:action:approve`: Approve or reject a pending agent action
- `agent:editor_panel`: Use the Agent panel next to Terminal with a live engine port
- `agent:message:send`: Send a message to an engine-native agent session
- `agent:permissions`: Suspend mutating agent tools for approval and resume the same logical turn
- `agent:providers:list`: List configured agent providers and metadata
- `agent:providers:login`: Store provider credentials or delegate managed Codex/OpenAI login
- `agent:providers:logout`: Remove user-local provider credentials
- `agent:providers:status`: Show provider authentication status without revealing secrets
- `agent:runtime`: Run the v3 clean-room agent turn loop with provider/tool-result continuation
- `agent:session:compact`: Compact an agent session transcript into local memory
- `agent:session:create`: Create an experimental clean-room agent session inside the engine
- `agent:session:inspect`: Inspect an agent session without mutating it
- `agent:tools`: List and execute safe engine-native agent tools through the v2 tool pipeline
- `agent:usage`: Show token and cost usage recorded for an agent session

### Game

- `game:platformer:add-checkpoint`: Create or update a named native checkpoint in the selected scene
- `game:platformer:add-coin`: Create or update native platformer Coin in the selected scene
- `game:platformer:add-enemy-patrol`: Create or update a named native enemy patrol in the selected scene
- `game:platformer:add-goal`: Create or update native platformer Goal in the selected scene
- `game:platformer:add-ground`: Create or update native platformer Ground in the selected scene
- `game:platformer:add-hazard`: Create or update native platformer Hazard in the selected scene
- `game:platformer:add-killzone`: Create or update a named native killzone in the selected scene
- `game:platformer:add-moving-platform`: Create or update a named native moving platform in the selected scene
- `game:platformer:add-platform`: Create or update native platformer Platform in the selected scene
- `game:platformer:add-player`: Create or update the native platformer Player in the selected scene
- `game:platformer:add-respawn`: Create or update native platformer RespawnPoint in the selected scene
- `game:platformer:create`: Create a minimal native 2D platformer scene scaffold
- `game:platformer:set-bounds`: Create or update native platformer level bounds in the selected scene
- `game:platformer:set-camera-follow`: Create or update Camera2D follow settings in the selected platformer scene
- `game:platformer:validate`: Validate selected native platformer scene contract

### Runtime

- `runtime:entities`: List entities in the active scene (read-only)
- `runtime:events`: Return recent runtime events, optionally after a headless step
- `runtime:inspect`: Inspect a specific entity (read-only)
- `runtime:play`: Start play mode for a stateless headless runtime check
- `runtime:status`: Read-only runtime status and active scene info
- `runtime:step`: Run PLAY -> STEP -> STOP headlessly for N frames, optionally with simulated InputMap actions
- `runtime:stop`: Stop runtime in the current stateless headless process

### Physics

- `physics:query:aabb`: Query physics entities within an axis-aligned bounding box

### Introspection

- `introspect:capabilities`: Query this capability registry itself
- `introspect:doctor`: Diagnose project health and detect issues

## Coming Soon

These capabilities are planned but **not yet available** via the CLI.
Do not attempt to use them — the `motor` CLI does not expose them.
They are listed here so an AI knows they exist in the engine
and should not be attempted until they are marked as `implemented`.

| Capability | Summary |
|-----------|---------|
| `asset:find` | Find assets by kind, importer, or extension |
| `asset:metadata:get` | Get metadata for a specific asset |
| `asset:refresh` | Refresh the asset catalog and detect changes |
| `entity:parent` | Set or change an entity's parent for hierarchical transforms |
| `introspect:entity` | Get full data for a specific entity |
| `introspect:status` | Get engine status including FPS, entity count, time |
| `physics:backend:list` | List available physics backends and their status |
| `physics:query:ray` | Cast a ray and find intersecting physics bodies |
| `project:editor_state` | Get or set editor state including recent assets and last scene |
| `project:open` | Open a different project and load its startup scene |
| `runtime:redo` | Redo a previously undone operation |
| `runtime:undo` | Undo the last edit operation |
| `scene:flow:load_next` | Load the configured next scene in the scene flow |
| `scene:flow:set_next` | Set the next scene connection for scene flow navigation |

> **Note**: Use `motor capabilities --json` to check which are now available.

## Full Capability Registry

See `motor_ai.json` for the complete machine-readable registry including:
- All capability IDs and summaries
- Required API methods with signatures
- CLI command templates
- Working examples for each capability
- Mode restrictions (edit/play/both)
- Explicit separation of `implemented` vs `planned` capabilities

## Getting Started

Start here before making changes:
```bash
motor ai start --project . --json
```

Rules for AI agents:
- Use MotorVideojuegosIA through `motor`, `EngineAPI` and serialized scenes/components.
- Do not create an external runtime for this project.
- Do not deliver `run_game.py` or an alternate main loop as the main game.
- Treat `MovingPlatform2D` as runtime-supported by `Gameplay2DSemanticSystem`: it moves the platform entity along its path and emits movement events during PLAY, but does not yet carry riders or persist runtime progress.
- Treat `EnemyPatrol2D` as runtime-supported by `Gameplay2DSemanticSystem`: it moves the entity cyclically between patrol points, emits `enemy_patrol_started` and `enemy_patrol_reached_point`, and on Player contact emits `enemy_touched` with damage and respawn (or `enemy_respawn_missing`). If coexisting with `Hazard2D` on the same entity, it absorbs the interaction to avoid duplicate events.
- Treat `Checkpoint2D`, `KillZone2D` and `LevelBounds2D` as runtime-supported semantic gameplay components: `Checkpoint2D` can activate session respawn compatibility via `RespawnPoint2D`, `KillZone2D` can respawn the player from the active checkpoint or first active `RespawnPoint2D`, and `LevelBounds2D` can emit `level_bounds_exited`, clamp horizontal exits and emit `level_bounds_respawn_missing` when bottom exit has no respawn.
- Treat `motor runtime play/step/stop/events` as stateless per invocation; runtime mutations are inspection-only and are not persisted as authoring state.
- Treat `motor recipe run` as allowlisted and shell-safe, but mutating for the target `--project`; bundled platformer recipes include `platformer-basic` and `platformer-advanced`.
- Treat `motor ai self-test` as temporary by default under `.motor/tmp`; use `--in-place` only when real project mutation is intended.

### Quick Workflow

1. **Load the AI contract**:
   ```bash
   motor ai start --project . --json
   ```

2. **Check project health**:
   ```bash
   motor doctor --project . --json
   ```

3. **Check AI-native compliance**:
   ```bash
   motor ai compliance --project . --strict --json
   ```

4. **Create a scene**:
   ```bash
   motor scene create "Level 1" --project .
   ```

5. **Create an entity**:
   ```bash
   motor entity create Player --project . --json
   ```

6. **Add a component**:
   ```bash
   motor component add Player Transform --data '{"x": 100, "y": 200}' --project .
   ```

7. **Slice a sprite sheet**:
   ```bash
   motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .
   ```

8. **Configure animator**:
   ```bash
   motor animator ensure Player --project .
   motor animator set-sheet Player assets/player.png --project .
   motor animator state create Player idle --slices idle_0,idle_1,idle_2,idle_3 --fps 8 --loop --project .
   ```

### Regenerate AI Bootstrap Files

If these files are missing or outdated, regenerate them with:
```bash
motor project bootstrap-ai --project .
```

### Discover Capabilities

List all available capabilities:
```bash
motor capabilities --json
```

## Naming Conventions

- **Capability IDs**: `scope:action` (e.g., `scene:load`, `entity:create`)
- **CLI Commands**: `motor <scope> <action>` (e.g., `motor scene load`)
- **API Methods**: `ScopeAPI.method_name` (e.g., `SceneWorkspaceAPI.load_level`)

## Official CLI

This project uses the official `motor` CLI:
- Entrypoint: `motor [command] [options]`
- Alternative: `python -m motor [command] [options]`
- Legacy: `python -m tools.engine_cli` (deprecated, for compatibility only)
