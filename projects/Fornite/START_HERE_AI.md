# MotorVideojuegosIA - AI Quick Start

**Project**: Fornite
**Engine Version**: 2026.03

## Overview
This project uses MotorVideojuegosIA, a 2D game engine designed for AI-assisted development.

## Implemented Capabilities

The entries below are available now and are safe to use from the CLI.

### Most Common Operations

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

- **introspect:capabilities**: Query this capability registry itself
  - API: `CapabilityRegistry.cmd_capabilities`
  - CLI: `motor capabilities [--json]`

## Capabilities by Category

### Scene Management

- `scene:create`: Create a new scene with a unique file path
- `scene:list`: List all available scenes in the project
- `scene:load`: Load a scene from a JSON file path
- `scene:save`: Save the active scene to its source file

### Entity Operations

- `entity:create`: Create a new entity with optional components

### Component Operations

- `component:add`: Add a component to an existing entity

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

### Project

- `project:bootstrap-ai`: Generate AI bootstrap files (motor_ai.json and START_HERE_AI.md)
- `project:manifest`: Get the current project's manifest summary

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
| `component:edit` | Edit a property of an existing component |
| `component:remove` | Remove a component from an entity |
| `entity:delete` | Remove an entity from the active scene, reparenting children to grandparent |
| `entity:list` | List all entities in the active scene, optionally filtered |
| `entity:parent` | Set or change an entity's parent for hierarchical transforms |
| `introspect:entity` | Get full data for a specific entity |
| `introspect:status` | Get engine status including FPS, entity count, time |
| `physics:backend:list` | List available physics backends and their status |
| `physics:query:aabb` | Query physics entities within an axis-aligned bounding box |
| `physics:query:ray` | Cast a ray and find intersecting physics bodies |
| `prefab:apply` | Apply instance overrides back to the source prefab |
| `prefab:instantiate` | Create an entity instance from a prefab file |
| `prefab:list` | List all prefabs available in the project |
| `prefab:unpack` | Convert a prefab instance to a regular entity |
| `project:editor_state` | Get or set editor state including recent assets and last scene |
| `project:open` | Open a different project and load its startup scene |
| `runtime:play` | Start play mode to test game logic |
| `runtime:redo` | Redo a previously undone operation |
| `runtime:step` | Advance the simulation by N frames |
| `runtime:stop` | Stop play mode and return to edit mode |
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

### Quick Workflow

1. **Check project health**:
   ```bash
   motor doctor --project . --json
   ```

2. **Create a scene**:
   ```bash
   motor scene create "Level 1" --project .
   ```

3. **Create an entity**:
   ```bash
   motor entity create Player --project . --json
   ```

4. **Add a component**:
   ```bash
   motor component add Player Transform --data '{"x": 100, "y": 200}' --project .
   ```

5. **Slice a sprite sheet**:
   ```bash
   motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .
   ```

6. **Configure animator**:
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

