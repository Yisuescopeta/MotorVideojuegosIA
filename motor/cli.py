"""
motor/cli.py - Official CLI implementation for MotorVideojuegosIA

ARCHITECTURE:
    This module implements the OFFICIAL CLI interface. It is the ONLY public
    interface for command-line operations. No other module should be used
    directly for CLI purposes.

    Layer structure:
        1. Entrypoints:
           - motor/__main__.py      : Enables `python -m motor`
           - motor/cli.py (this)    : Argument parsing and dispatch
           - motor/cli_core.py      : Command implementations

        2. Public API (stable):
           - create_motor_parser()   : Create ArgumentParser for introspection
           - run_motor_command()     : Execute with args list, returns exit code
           - cli_main()              : Entry point using sys.argv
           - main()                  : Entry point calling sys.exit()

        3. Internal (private):
           - dispatch_command()      : Route parsed args to handlers
           - Individual command handlers (imported from cli_core)

    Backwards compatibility (deprecated):
        tools/engine_cli.py         : Compatibility wrapper, shows deprecation warning

Usage:
    motor [command] [options]
    python -m motor [command] [options]

Examples:
    motor doctor --project . --json
    motor capabilities
    motor scene create "Level 1" --project .
    motor entity create Player --components '{"Transform":{"x":100}}'

Programmatic use:
    from motor.cli import run_motor_command
    exit_code = run_motor_command(["doctor", "--project", ".", "--json"])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from motor.cli_core import (
    # Commands
    cmd_ai_compliance,
    cmd_ai_start,
    cmd_capabilities,
    cmd_doctor,
    cmd_project_info,
    cmd_project_bootstrap_ai,
    cmd_recipe_list,
    cmd_recipe_show,
    cmd_recipe_run,
    cmd_game_platformer_add_checkpoint,
    cmd_game_platformer_add_coin,
    cmd_game_platformer_create,
    cmd_game_platformer_add_enemy_patrol,
    cmd_game_platformer_add_goal,
    cmd_game_platformer_add_ground,
    cmd_game_platformer_add_hazard,
    cmd_game_platformer_add_killzone,
    cmd_game_platformer_add_moving_platform,
    cmd_game_platformer_add_platform,
    cmd_game_platformer_add_player,
    cmd_game_platformer_add_respawn,
    cmd_game_platformer_set_bounds,
    cmd_game_platformer_set_camera_follow,
    cmd_game_platformer_validate,
    cmd_scene_list,
    cmd_scene_create,
    cmd_scene_load,
    cmd_scene_save,
    cmd_runtime_play,
    cmd_runtime_step,
    cmd_runtime_stop,
    cmd_runtime_status,
    cmd_runtime_entities,
    cmd_runtime_inspect,
    cmd_runtime_events,
    cmd_entity_create,
    cmd_component_add,
    cmd_prefab_create,
    cmd_prefab_instantiate,
    cmd_prefab_unpack,
    cmd_prefab_apply,
    cmd_prefab_list,
    cmd_assets_list,
    cmd_slices_list,
    cmd_slices_grid,
    cmd_slices_auto,
    cmd_slices_manual,
    cmd_agent_session_create,
    cmd_agent_message_send,
    cmd_agent_action_approve,
    cmd_agent_providers_list,
    cmd_agent_providers_login,
    cmd_agent_providers_logout,
    cmd_agent_providers_status,
    cmd_agent_session_compact,
    cmd_agent_session_inspect,
    cmd_agent_usage,
    cmd_animator_info,
    cmd_animator_set_sheet,
    cmd_animator_upsert_state,
    cmd_animator_remove_state,
    cmd_animator_ensure,
    # Exceptions
    EngineCLIError,
    ProjectNotFoundError,
    EngineInitError,
)

__all__ = ["main", "cli_main", "run_motor_command", "create_motor_parser"]


def create_motor_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the motor CLI."""
    parser = argparse.ArgumentParser(
        prog="motor",
        description="Official CLI for MotorVideojuegosIA - AI-facing game engine operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
GRAMMAR: motor <noun> [<subnoun>] <verb> [<args>] [options]

AI-Facing Commands:
  ai start                  Compact AI entrypoint contract
  ai compliance             Validate AI-native project compliance
  capabilities              Discover engine capabilities
  doctor                    Validate project health
  
  project info              Show project information
  project bootstrap-ai      Generate AI bootstrap files
  recipe list/show/run      Declarative AI recipes for common workflows
  game platformer create    Create minimal native 2D platformer scene
  game platformer add-*     Add/update native platformer entities and semantics
  game platformer validate  Validate native platformer scene
  
  scene list                List all scenes
  scene create <name>       Create new scene
  scene load <path>         Load a scene
  scene save                Save active scene

  runtime play              Start a stateless headless runtime check
  runtime step              Run PLAY -> STEP -> STOP headlessly
  runtime stop              Stop runtime in the current stateless process
  
  entity create <name>      Create entity in active scene
  
  component add <e> <c>     Add component to entity

  prefab create <e> <p>     Save entity subtree as prefab
  prefab instantiate <p>    Instantiate prefab in active scene
  prefab unpack <e>         Convert prefab instance to explicit entities
  prefab apply <e>          Apply instance overrides to source prefab
  prefab list               List project prefabs
  
  animator info <e>         Show animator configuration
  animator set-sheet <e> <a>  Set sprite sheet
  animator ensure <e>       Ensure Animator exists (creates if missing)
  animator state create <e> <s>  Create/update animation state
  animator state remove <e> <s>  Remove animation state
  
  asset list                List project assets
  asset slice list <a>      List slices for asset
  asset slice grid <a>      Create grid-based slices
  asset slice auto <a>      Auto-detect slices
  asset slice manual <a>    Save manual slices

  agent session create      Create an experimental agent session
  agent session compact     Compact an agent session transcript
  agent session inspect     Inspect an agent session without mutating it
  agent message send        Send a message to an agent session
  agent action approve      Approve or reject a pending agent action
  agent providers list      List configured agent providers
  agent providers login     Store provider credentials or delegate managed Codex login
  agent providers status    Show provider auth status
  agent providers logout    Remove provider credentials
  agent usage               Show token/cost usage for a session

Examples:
  motor ai start --project . --json
  motor ai compliance --project . --strict --json
  motor doctor --project . --json
  motor recipe list --project . --json
  motor recipe show platformer-basic --project . --json
  motor recipe run platformer-basic --project . --json
  motor capabilities
  motor runtime step --project . --frames 300 --input "right,jump" --json
  motor game platformer create "Level 1" --project . --json
  motor game platformer add-player --x 100 --y 300 --project . --json
  motor game platformer add-ground --from-x 0 --to-x 20 --y 8 --project . --json
  motor game platformer add-coin --x 320 --y 200 --points 1 --project . --json
  motor game platformer add-hazard --x 640 --y 300 --damage 1 --project . --json
  motor game platformer add-goal --x 1100 --y 200 --project . --json
  motor game platformer add-respawn --x 100 --y 300 --id default --project . --json
  motor game platformer add-moving-platform --name Lift_A --x 320 --y 300 --width 96 --height 24 --to-x 640 --to-y 300 --speed 80 --project . --json
  motor game platformer add-enemy-patrol --name Slime_A --x 500 --y 480 --point 500,480 --point 700,480 --damage 1 --speed 60 --project . --json
  motor game platformer add-checkpoint --name Checkpoint_A --x 200 --y 420 --id cp_a --project . --json
  motor game platformer add-killzone --name Pit_A --x 640 --y 620 --width 1280 --height 64 --damage 1 --project . --json
  motor game platformer set-camera-follow --name MainCamera --target Player --project . --json
  motor game platformer set-bounds --name LevelBounds --left 0 --right 1600 --top 0 --bottom 720 --camera MainCamera --project . --json
  motor game platformer validate --project . --json
  motor scene create "Level 1"
  motor entity create Player --components '{"Transform":{"x":100}}'
  motor prefab create Player prefabs/player.prefab --project .
  motor animator ensure Player --sheet assets/player.png
  motor animator state create Player idle --slices idle_0,idle_1,idle_2 --fps 8 --loop
  motor animator state create Player attack --slices atk_0,atk_1 --fps 12 --no-loop --set-default
  motor asset slice grid assets/tiles.png --cell-width 32 --cell-height 32 --project .

Documentation:
  - See START_HERE_AI.md in your project root
  - See motor_ai.json for full capability registry
  - See docs/cli.md for the official CLI reference
        """,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2026.03 (MotorVideojuegosIA)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === ai ===
    ai_parser = subparsers.add_parser(
        "ai",
        help="AI assistant entrypoints",
    )
    ai_subparsers = ai_parser.add_subparsers(dest="ai_subcommand", required=True)

    ai_start_parser = ai_subparsers.add_parser(
        "start",
        help="Show compact AI entrypoint contract",
        description="Return a read-only compact project contract for AI assistants.",
    )
    ai_start_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory (default: current directory)"
    )
    ai_start_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    ai_compliance_parser = ai_subparsers.add_parser(
        "compliance",
        help="Run read-only AI-native project compliance diagnostics",
        description="Validate whether a project follows the MotorVideojuegosIA AI-native contract.",
    )
    ai_compliance_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory (default: current directory)"
    )
    ai_compliance_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when suspicious external runtime signals or no native scene are found",
    )
    ai_compliance_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === capabilities ===
    cap_parser = subparsers.add_parser(
        "capabilities",
        help="List all engine capabilities",
        description="Display the full capability registry for AI assistants.",
    )
    cap_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === doctor ===
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose project health",
        description="Validate project structure, bootstrap files, and engine availability.",
    )
    doctor_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory (default: current directory)"
    )
    doctor_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === project ===
    project_parser = subparsers.add_parser(
        "project",
        help="Project operations",
    )
    project_subparsers = project_parser.add_subparsers(dest="project_subcommand", required=True)
    
    proj_info_parser = project_subparsers.add_parser(
        "info",
        help="Get project information",
    )
    proj_info_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    proj_info_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    proj_bootstrap_parser = project_subparsers.add_parser(
        "bootstrap-ai",
        help="Generate AI bootstrap files (motor_ai.json and START_HERE_AI.md)",
        description="Generate or regenerate AI-facing bootstrap files for the project.",
    )
    proj_bootstrap_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    proj_bootstrap_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === recipe ===
    recipe_parser = subparsers.add_parser(
        "recipe",
        help="Declarative AI recipe operations",
    )
    recipe_subparsers = recipe_parser.add_subparsers(dest="recipe_subcommand", required=True)

    recipe_list_parser = recipe_subparsers.add_parser(
        "list",
        help="List bundled declarative AI recipes",
        description="List bundled declarative AI recipes without mutating the project.",
    )
    recipe_list_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    recipe_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    recipe_show_parser = recipe_subparsers.add_parser(
        "show",
        help="Show a bundled declarative AI recipe",
        description="Show a bundled declarative AI recipe without mutating the project.",
    )
    recipe_show_parser.add_argument("recipe_id", help="Recipe id")
    recipe_show_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    recipe_show_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    recipe_run_parser = recipe_subparsers.add_parser(
        "run",
        help="Run a bundled declarative AI recipe",
        description="Run a bundled recipe through allowlisted official motor commands.",
    )
    recipe_run_parser.add_argument("recipe_id", help="Recipe id")
    recipe_run_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    recipe_run_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === game ===
    game_parser = subparsers.add_parser(
        "game",
        help="Game scaffolding operations",
    )
    game_subparsers = game_parser.add_subparsers(dest="game_subcommand", required=True)

    game_platformer_parser = game_subparsers.add_parser(
        "platformer",
        help="2D platformer scaffolding",
    )
    game_platformer_subparsers = game_platformer_parser.add_subparsers(dest="game_platformer_subcommand", required=True)

    game_platformer_create_parser = game_platformer_subparsers.add_parser(
        "create",
        help="Create a minimal native 2D platformer scene",
        description="Create a minimal native 2D platformer scene",
    )
    game_platformer_create_parser.add_argument("name", help="Scene name")
    game_platformer_create_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_player_parser = game_platformer_subparsers.add_parser(
        "add-player",
        help="Ensure a platformer Player in the selected scene",
        description="Create or update Player using native components; saves the selected serialized scene.",
    )
    game_platformer_add_player_parser.add_argument("--x", type=float, required=True, help="Player X position in pixels")
    game_platformer_add_player_parser.add_argument("--y", type=float, required=True, help="Player Y position in pixels")
    game_platformer_add_player_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_player_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_ground_parser = game_platformer_subparsers.add_parser(
        "add-ground",
        help="Ensure platformer ground in the selected scene",
        description="Create or update Ground from half-open grid cell range [from-x,to-x); grid size is 64 px.",
    )
    game_platformer_add_ground_parser.add_argument("--from-x", type=float, required=True, help="Start grid cell, inclusive")
    game_platformer_add_ground_parser.add_argument("--to-x", type=float, required=True, help="End grid cell, exclusive")
    game_platformer_add_ground_parser.add_argument("--y", type=float, required=True, help="Ground Y grid cell")
    game_platformer_add_ground_parser.add_argument("--name", default=None, help="Ground entity name; omitted creates Ground_###")
    game_platformer_add_ground_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_ground_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_platform_parser = game_platformer_subparsers.add_parser(
        "add-platform",
        help="Ensure a platformer platform in the selected scene",
        description="Create or update Platform from grid cell origin and width; grid size is 64 px.",
    )
    game_platformer_add_platform_parser.add_argument("--x", type=float, required=True, help="Platform start X grid cell")
    game_platformer_add_platform_parser.add_argument("--y", type=float, required=True, help="Platform Y grid cell")
    game_platformer_add_platform_parser.add_argument("--width", type=float, required=True, help="Platform width in grid cells")
    game_platformer_add_platform_parser.add_argument("--name", default=None, help="Platform entity name; omitted creates Platform_###")
    game_platformer_add_platform_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_platform_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_goal_parser = game_platformer_subparsers.add_parser(
        "add-goal",
        help="Ensure a platformer Goal in the selected scene",
        description="Create or update Goal using Transform, trigger Collider and Goal2D; no assets required.",
    )
    game_platformer_add_goal_parser.add_argument("--x", type=float, required=True, help="Goal X position in pixels")
    game_platformer_add_goal_parser.add_argument("--y", type=float, required=True, help="Goal Y position in pixels")
    game_platformer_add_goal_parser.add_argument("--name", default=None, help="Goal entity name; omitted creates Goal or Goal_###")
    game_platformer_add_goal_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_goal_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_coin_parser = game_platformer_subparsers.add_parser(
        "add-coin",
        help="Ensure a platformer Coin in the selected scene",
        description="Create or update Coin using Transform, trigger Collider and Collectible2D.",
    )
    game_platformer_add_coin_parser.add_argument("--x", type=float, required=True, help="Coin X position in pixels")
    game_platformer_add_coin_parser.add_argument("--y", type=float, required=True, help="Coin Y position in pixels")
    game_platformer_add_coin_parser.add_argument("--points", type=int, required=True, help="Points awarded when collected")
    game_platformer_add_coin_parser.add_argument("--name", default=None, help="Coin entity name; omitted creates Coin_###")
    game_platformer_add_coin_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_coin_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_hazard_parser = game_platformer_subparsers.add_parser(
        "add-hazard",
        help="Ensure a platformer Hazard in the selected scene",
        description="Create or update Hazard using Transform, trigger Collider and Hazard2D.",
    )
    game_platformer_add_hazard_parser.add_argument("--x", type=float, required=True, help="Hazard X position in pixels")
    game_platformer_add_hazard_parser.add_argument("--y", type=float, required=True, help="Hazard Y position in pixels")
    game_platformer_add_hazard_parser.add_argument("--damage", type=int, required=True, help="Damage applied on touch")
    game_platformer_add_hazard_parser.add_argument("--name", default=None, help="Hazard entity name; omitted creates Hazard_###")
    game_platformer_add_hazard_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_hazard_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_respawn_parser = game_platformer_subparsers.add_parser(
        "add-respawn",
        help="Ensure a platformer RespawnPoint in the selected scene",
        description="Create or update RespawnPoint using Transform and RespawnPoint2D.",
    )
    game_platformer_add_respawn_parser.add_argument("--x", type=float, required=True, help="Respawn X position in pixels")
    game_platformer_add_respawn_parser.add_argument("--y", type=float, required=True, help="Respawn Y position in pixels")
    game_platformer_add_respawn_parser.add_argument("--id", dest="spawn_id", required=True, help="Respawn point id")
    game_platformer_add_respawn_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_respawn_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_moving_platform_parser = game_platformer_subparsers.add_parser(
        "add-moving-platform",
        help="Ensure a named platformer moving platform in the selected scene",
        description="Create or update a named moving platform using Transform, Collider and MovingPlatform2D.",
    )
    game_platformer_add_moving_platform_parser.add_argument("--name", required=True, help="Moving platform entity name")
    game_platformer_add_moving_platform_parser.add_argument("--x", type=float, required=True, help="Start X position in pixels")
    game_platformer_add_moving_platform_parser.add_argument("--y", type=float, required=True, help="Start Y position in pixels")
    game_platformer_add_moving_platform_parser.add_argument("--width", type=float, required=True, help="Collider width in pixels")
    game_platformer_add_moving_platform_parser.add_argument("--height", type=float, required=True, help="Collider height in pixels")
    game_platformer_add_moving_platform_parser.add_argument("--to-x", type=float, required=True, help="Destination X position in pixels")
    game_platformer_add_moving_platform_parser.add_argument("--to-y", type=float, required=True, help="Destination Y position in pixels")
    game_platformer_add_moving_platform_parser.add_argument("--speed", type=float, required=True, help="Movement speed in pixels per second")
    game_platformer_add_moving_platform_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_moving_platform_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_enemy_patrol_parser = game_platformer_subparsers.add_parser(
        "add-enemy-patrol",
        help="Ensure a named platformer enemy patrol in the selected scene",
        description="Create or update a named enemy patrol using Transform, trigger Collider and EnemyPatrol2D.",
    )
    game_platformer_add_enemy_patrol_parser.add_argument("--name", required=True, help="Enemy entity name")
    game_platformer_add_enemy_patrol_parser.add_argument("--x", type=float, required=True, help="Enemy X position in pixels")
    game_platformer_add_enemy_patrol_parser.add_argument("--y", type=float, required=True, help="Enemy Y position in pixels")
    game_platformer_add_enemy_patrol_parser.add_argument("--point", action="append", required=True, help="Patrol point as x,y; repeat for multiple points")
    game_platformer_add_enemy_patrol_parser.add_argument("--damage", type=int, required=True, help="Damage on touch")
    game_platformer_add_enemy_patrol_parser.add_argument("--speed", type=float, required=True, help="Patrol speed in pixels per second")
    game_platformer_add_enemy_patrol_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_enemy_patrol_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_checkpoint_parser = game_platformer_subparsers.add_parser(
        "add-checkpoint",
        help="Ensure a named platformer checkpoint in the selected scene",
        description="Create or update a named checkpoint using Transform, trigger Collider, Checkpoint2D and RespawnPoint2D.",
    )
    game_platformer_add_checkpoint_parser.add_argument("--name", required=True, help="Checkpoint entity name")
    game_platformer_add_checkpoint_parser.add_argument("--x", type=float, required=True, help="Checkpoint X position in pixels")
    game_platformer_add_checkpoint_parser.add_argument("--y", type=float, required=True, help="Checkpoint Y position in pixels")
    game_platformer_add_checkpoint_parser.add_argument("--id", dest="checkpoint_id", required=True, help="Checkpoint id")
    game_platformer_add_checkpoint_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_checkpoint_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_add_killzone_parser = game_platformer_subparsers.add_parser(
        "add-killzone",
        help="Ensure a named platformer killzone in the selected scene",
        description="Create or update a named killzone using Transform, trigger Collider and KillZone2D.",
    )
    game_platformer_add_killzone_parser.add_argument("--name", required=True, help="Killzone entity name")
    game_platformer_add_killzone_parser.add_argument("--x", type=float, required=True, help="Killzone X position in pixels")
    game_platformer_add_killzone_parser.add_argument("--y", type=float, required=True, help="Killzone Y position in pixels")
    game_platformer_add_killzone_parser.add_argument("--width", type=float, required=True, help="Collider width in pixels")
    game_platformer_add_killzone_parser.add_argument("--height", type=float, required=True, help="Collider height in pixels")
    game_platformer_add_killzone_parser.add_argument("--damage", type=int, required=True, help="Damage on touch")
    game_platformer_add_killzone_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_add_killzone_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_set_camera_follow_parser = game_platformer_subparsers.add_parser(
        "set-camera-follow",
        help="Configure named Camera2D follow settings in the selected scene",
        description="Create or update a named Camera2D using existing native camera follow fields.",
    )
    game_platformer_set_camera_follow_parser.add_argument("--name", required=True, help="Camera entity name")
    game_platformer_set_camera_follow_parser.add_argument("--target", required=True, help="Target entity name to follow")
    game_platformer_set_camera_follow_parser.add_argument("--offset-x", type=float, default=0.0, help="Camera offset X")
    game_platformer_set_camera_follow_parser.add_argument("--offset-y", type=float, default=0.0, help="Camera offset Y")
    game_platformer_set_camera_follow_parser.add_argument("--dead-zone-width", type=float, default=0.0, help="Dead zone width")
    game_platformer_set_camera_follow_parser.add_argument("--dead-zone-height", type=float, default=0.0, help="Dead zone height")
    game_platformer_set_camera_follow_parser.add_argument("--zoom", type=float, default=1.0, help="Camera zoom")
    game_platformer_set_camera_follow_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_set_camera_follow_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_set_bounds_parser = game_platformer_subparsers.add_parser(
        "set-bounds",
        help="Configure platformer LevelBounds2D in the selected scene",
        description="Create or update named LevelBounds2D data and optionally sync Camera2D clamps.",
    )
    game_platformer_set_bounds_parser.add_argument("--name", required=True, help="Bounds entity name")
    game_platformer_set_bounds_parser.add_argument("--left", type=float, required=True, help="Left level bound")
    game_platformer_set_bounds_parser.add_argument("--right", type=float, required=True, help="Right level bound")
    game_platformer_set_bounds_parser.add_argument("--top", type=float, required=True, help="Top level bound")
    game_platformer_set_bounds_parser.add_argument("--bottom", type=float, required=True, help="Bottom level bound")
    game_platformer_set_bounds_parser.add_argument("--camera", default=None, help="Optional Camera2D entity to receive clamp values")
    game_platformer_set_bounds_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_set_bounds_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    game_platformer_validate_parser = game_platformer_subparsers.add_parser(
        "validate",
        help="Validate selected platformer scene",
        description="Validate selected scene has Player, terrain, Goal, loadability and strict AI compliance.",
    )
    game_platformer_validate_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    game_platformer_validate_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === scene ===
    scene_parser = subparsers.add_parser(
        "scene",
        help="Scene operations",
    )
    scene_subparsers = scene_parser.add_subparsers(dest="scene_subcommand", required=True)
    
    scene_list_parser = scene_subparsers.add_parser(
        "list",
        help="List all scenes",
    )
    scene_list_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    scene_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    scene_create_parser = scene_subparsers.add_parser(
        "create",
        help="Create a new scene",
    )
    scene_create_parser.add_argument("name", help="Scene name")
    scene_create_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    scene_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    scene_load_parser = scene_subparsers.add_parser(
        "load",
        help="Load a scene",
    )
    scene_load_parser.add_argument("path", help="Scene path")
    scene_load_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    scene_load_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    scene_save_parser = scene_subparsers.add_parser(
        "save",
        help="Save the active scene",
    )
    scene_save_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    scene_save_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === runtime ===
    runtime_parser = subparsers.add_parser(
        "runtime",
        help="Stateless headless runtime controls",
        description="Run official EngineAPI runtime controls in a stateless headless CLI process.",
    )
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_subcommand", required=True)

    runtime_play_parser = runtime_subparsers.add_parser(
        "play",
        help="Start play mode for a stateless headless runtime check",
    )
    runtime_play_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_play_parser.add_argument(
        "--headless",
        action="store_true",
        help="Explicitly request the headless runtime path",
    )
    runtime_play_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    runtime_step_parser = runtime_subparsers.add_parser(
        "step",
        help="Run PLAY -> STEP -> STOP in a stateless headless process",
    )
    runtime_step_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_step_parser.add_argument(
        "--frames",
        type=int,
        default=1,
        help="Number of frames to step (default: 1)",
    )
    runtime_step_parser.add_argument(
        "--input",
        dest="input_spec",
        default=None,
        help="Comma-separated InputMap actions to hold while stepping (left,right,up,down,jump,action_1,action_2)",
    )
    runtime_step_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    runtime_stop_parser = runtime_subparsers.add_parser(
        "stop",
        help="Stop runtime in the current stateless process",
    )
    runtime_stop_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_stop_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    runtime_status_parser = runtime_subparsers.add_parser(
        "status",
        help="Read-only runtime status and active scene info",
    )
    runtime_status_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_status_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    runtime_entities_parser = runtime_subparsers.add_parser(
        "entities",
        help="List entities in the active scene (read-only)",
    )
    runtime_entities_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_entities_parser.add_argument("--tag", default=None, help="Filter by tag")
    runtime_entities_parser.add_argument("--layer", default=None, help="Filter by layer")
    runtime_entities_parser.add_argument("--active-only", action="store_true", help="Only active entities")
    runtime_entities_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    runtime_inspect_parser = runtime_subparsers.add_parser(
        "inspect",
        help="Inspect a specific entity (read-only)",
    )
    runtime_inspect_parser.add_argument("entity", help="Entity name")
    runtime_inspect_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_inspect_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    runtime_events_parser = runtime_subparsers.add_parser(
        "events",
        help="Return recent runtime events (read-only)",
    )
    runtime_events_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    runtime_events_parser.add_argument(
        "--count", type=int, default=50,
        help="Number of recent events to retrieve (default: 50)"
    )
    runtime_events_parser.add_argument(
        "--step-frames", type=int, default=0,
        help="Run PLAY -> STEP(N) before reading events in this stateless process"
    )
    runtime_events_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === entity ===
    entity_parser = subparsers.add_parser(
        "entity",
        help="Entity operations",
    )
    entity_subparsers = entity_parser.add_subparsers(dest="entity_subcommand", required=True)
    
    entity_create_parser = entity_subparsers.add_parser(
        "create",
        help="Create a new entity in the active scene",
    )
    entity_create_parser.add_argument("name", help="Entity name")
    entity_create_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    entity_create_parser.add_argument(
        "--components", default=None,
        help='Components JSON (e.g., "{Transform:{x:100}}")'
    )
    entity_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === component ===
    component_parser = subparsers.add_parser(
        "component",
        help="Component operations",
    )
    component_subparsers = component_parser.add_subparsers(dest="component_subcommand", required=True)
    
    component_add_parser = component_subparsers.add_parser(
        "add",
        help="Add a component to an entity",
    )
    component_add_parser.add_argument("entity", help="Entity name")
    component_add_parser.add_argument("component", help="Component name")
    component_add_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    component_add_parser.add_argument(
        "--data", default=None,
        help='Component data JSON'
    )
    component_add_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === prefab ===
    prefab_parser = subparsers.add_parser(
        "prefab",
        help="Prefab operations",
    )
    prefab_subparsers = prefab_parser.add_subparsers(dest="prefab_subcommand", required=True)

    prefab_create_parser = prefab_subparsers.add_parser(
        "create",
        help="Create a prefab from an entity",
    )
    prefab_create_parser.add_argument("entity", help="Root entity name")
    prefab_create_parser.add_argument("path", help="Prefab output path")
    prefab_create_parser.add_argument(
        "--replace-original",
        action="store_true",
        help="Replace the original subtree with a linked prefab instance",
    )
    prefab_create_parser.add_argument(
        "--instance-name",
        default=None,
        help="Instance name to use when replacing the original subtree",
    )
    prefab_create_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    prefab_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    prefab_instantiate_parser = prefab_subparsers.add_parser(
        "instantiate",
        help="Instantiate a prefab in the active scene",
    )
    prefab_instantiate_parser.add_argument("path", help="Prefab path")
    prefab_instantiate_parser.add_argument("--name", default=None, help="Root entity name override")
    prefab_instantiate_parser.add_argument("--parent", default=None, help="Optional parent entity name")
    prefab_instantiate_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    prefab_instantiate_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    prefab_unpack_parser = prefab_subparsers.add_parser(
        "unpack",
        help="Unpack a prefab instance into explicit scene entities",
    )
    prefab_unpack_parser.add_argument("entity", help="Prefab instance root entity")
    prefab_unpack_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    prefab_unpack_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    prefab_apply_parser = prefab_subparsers.add_parser(
        "apply",
        help="Apply prefab instance overrides back to the source prefab",
    )
    prefab_apply_parser.add_argument("entity", help="Prefab instance root entity")
    prefab_apply_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    prefab_apply_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    prefab_list_parser = prefab_subparsers.add_parser(
        "list",
        help="List project prefabs",
    )
    prefab_list_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    prefab_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === animator ===
    animator_parser = subparsers.add_parser(
        "animator",
        help="Animator operations",
    )
    animator_subparsers = animator_parser.add_subparsers(dest="animator_subcommand", required=True)
    
    animator_info_parser = animator_subparsers.add_parser(
        "info",
        help="Get animator info for an entity",
    )
    animator_info_parser.add_argument("entity", help="Entity name")
    animator_info_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    animator_info_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    animator_sheet_parser = animator_subparsers.add_parser(
        "set-sheet",
        help="Set sprite sheet for animator",
    )
    animator_sheet_parser.add_argument("entity", help="Entity name")
    animator_sheet_parser.add_argument("asset", help="Asset path")
    animator_sheet_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    animator_sheet_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    animator_ensure_parser = animator_subparsers.add_parser(
        "ensure",
        help="Ensure Animator exists with optional sheet (creates or updates)",
    )
    animator_ensure_parser.add_argument("entity", help="Entity name")
    animator_ensure_parser.add_argument(
        "--sheet", dest="sprite_sheet", default="",
        help="Sprite sheet asset path. If Animator exists, updates the sheet."
    )
    animator_ensure_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    animator_ensure_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # animator state subcommand (nueva gramática jerárquica)
    animator_state_parser = animator_subparsers.add_parser(
        "state",
        help="Animator state operations",
    )
    animator_state_subparsers = animator_state_parser.add_subparsers(dest="animator_state_subcommand", required=True)
    
    # state create (antes upsert-state)
    animator_state_create_parser = animator_state_subparsers.add_parser(
        "create",
        help="Create or update an animation state",
    )
    animator_state_create_parser.add_argument("entity", help="Entity name")
    animator_state_create_parser.add_argument("state", help="State name")
    animator_state_create_parser.add_argument(
        "--slices", required=True,
        help="Comma-separated slice names"
    )
    animator_state_create_parser.add_argument(
        "--fps", type=float, default=8.0,
        help="Frames per second"
    )
    animator_state_create_parser.add_argument(
        "--loop", dest="loop", action="store_true", default=None,
        help="Enable animation looping (default: true)"
    )
    animator_state_create_parser.add_argument(
        "--no-loop", dest="loop", action="store_false", default=None,
        help="Disable animation looping"
    )
    animator_state_create_parser.add_argument(
        "--set-default", action="store_true",
        help="Set as default state"
    )
    animator_state_create_parser.add_argument(
        "--auto-create", action="store_true",
        help="Auto-create Animator component if missing"
    )
    animator_state_create_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    animator_state_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # state remove (antes remove-state)
    animator_state_remove_parser = animator_state_subparsers.add_parser(
        "remove",
        help="Remove an animation state",
    )
    animator_state_remove_parser.add_argument("entity", help="Entity name")
    animator_state_remove_parser.add_argument("state", help="State name")
    animator_state_remove_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    animator_state_remove_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # === LEGACY COMMANDS (compatibilidad temporal, no documentados) ===
    # upsert-state legacy alias
    animator_upsert_parser = animator_subparsers.add_parser(
        "upsert-state",
        help=argparse.SUPPRESS,  # No mostrar en help
    )
    animator_upsert_parser.add_argument("entity", help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("state", help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--slices", required=True, help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--fps", type=float, default=8.0, help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--loop", dest="loop", action="store_true", default=None, help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--no-loop", dest="loop", action="store_false", default=None, help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--set-default", action="store_true", help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--auto-create", action="store_true", help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--project", dest="project_root", default=".", help=argparse.SUPPRESS)
    animator_upsert_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    
    # remove-state legacy alias
    animator_remove_parser = animator_subparsers.add_parser(
        "remove-state",
        help=argparse.SUPPRESS,  # No mostrar en help
    )
    animator_remove_parser.add_argument("entity", help=argparse.SUPPRESS)
    animator_remove_parser.add_argument("state", help=argparse.SUPPRESS)
    animator_remove_parser.add_argument("--project", dest="project_root", default=".", help=argparse.SUPPRESS)
    animator_remove_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    # === asset ===
    asset_parser = subparsers.add_parser(
        "asset",
        help="Asset operations",
    )
    asset_subparsers = asset_parser.add_subparsers(dest="asset_subcommand", required=True)
    
    # asset list
    asset_list_parser = asset_subparsers.add_parser(
        "list",
        help="List assets",
    )
    asset_list_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    asset_list_parser.add_argument(
        "--search", default="",
        help="Search filter for asset names"
    )
    asset_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # asset slice
    asset_slice_parser = asset_subparsers.add_parser(
        "slice",
        help="Slice operations",
    )
    asset_slice_subparsers = asset_slice_parser.add_subparsers(dest="slice_subcommand", required=True)
    
    # slice list
    slice_list_parser = asset_slice_subparsers.add_parser(
        "list",
        help="List slices for an asset",
    )
    slice_list_parser.add_argument("asset", help="Asset path")
    slice_list_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    slice_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # slice grid
    slice_grid_parser = asset_slice_subparsers.add_parser(
        "grid",
        help="Create grid-based slices",
    )
    slice_grid_parser.add_argument("asset", help="Asset path")
    slice_grid_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    slice_grid_parser.add_argument(
        "--cell-width", type=int, required=True,
        help="Cell width in pixels"
    )
    slice_grid_parser.add_argument(
        "--cell-height", type=int, required=True,
        help="Cell height in pixels"
    )
    slice_grid_parser.add_argument(
        "--margin", type=int, default=0,
        help="Margin in pixels"
    )
    slice_grid_parser.add_argument(
        "--spacing", type=int, default=0,
        help="Spacing between cells"
    )
    slice_grid_parser.add_argument(
        "--pivot-x", type=float, default=0.5,
        help="Pivot X (0-1)"
    )
    slice_grid_parser.add_argument(
        "--pivot-y", type=float, default=0.5,
        help="Pivot Y (0-1)"
    )
    slice_grid_parser.add_argument(
        "--naming-prefix", default=None,
        help="Naming prefix for slices"
    )
    slice_grid_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # slice auto
    slice_auto_parser = asset_slice_subparsers.add_parser(
        "auto",
        help="Auto-detect and create slices",
    )
    slice_auto_parser.add_argument("asset", help="Asset path")
    slice_auto_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    slice_auto_parser.add_argument(
        "--pivot-x", type=float, default=0.5,
        help="Pivot X (0-1)"
    )
    slice_auto_parser.add_argument(
        "--pivot-y", type=float, default=0.5,
        help="Pivot Y (0-1)"
    )
    slice_auto_parser.add_argument(
        "--naming-prefix", default=None,
        help="Naming prefix for slices"
    )
    slice_auto_parser.add_argument(
        "--alpha-threshold", type=int, default=1,
        help="Alpha threshold (0-255)"
    )
    slice_auto_parser.add_argument(
        "--preview", action="store_true",
        help="Preview only, don't save"
    )
    slice_auto_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    # slice manual
    slice_manual_parser = asset_slice_subparsers.add_parser(
        "manual",
        help="Save manual slices",
    )
    slice_manual_parser.add_argument("asset", help="Asset path")
    slice_manual_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    slice_manual_parser.add_argument(
        "--slices", required=True,
        help="Slices JSON string or path to JSON file"
    )
    slice_manual_parser.add_argument(
        "--pivot-x", type=float, default=0.5,
        help="Pivot X (0-1)"
    )
    slice_manual_parser.add_argument(
        "--pivot-y", type=float, default=0.5,
        help="Pivot Y (0-1)"
    )
    slice_manual_parser.add_argument(
        "--naming-prefix", default=None,
        help="Naming prefix for slices"
    )
    slice_manual_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # === agent ===
    agent_parser = subparsers.add_parser(
        "agent",
        help="Experimental engine-native agent operations",
    )
    agent_subparsers = agent_parser.add_subparsers(dest="agent_subcommand", required=True)

    agent_session_parser = agent_subparsers.add_parser(
        "session",
        help="Agent session operations",
    )
    agent_session_subparsers = agent_session_parser.add_subparsers(dest="agent_session_subcommand", required=True)

    agent_session_create_parser = agent_session_subparsers.add_parser(
        "create",
        help="Create an experimental agent session",
    )
    agent_session_create_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    agent_session_create_parser.add_argument(
        "--permission-mode",
        choices=["confirm_actions", "full_access"],
        default="confirm_actions",
        help="Permission mode for mutating agent actions"
    )
    agent_session_create_parser.add_argument("--title", default="", help="Optional session title")
    agent_session_create_parser.add_argument("--provider-id", default="fake", help="Provider id for the session")
    agent_session_create_parser.add_argument("--model", default="", help="Optional provider model")
    agent_session_create_parser.add_argument("--temperature", type=float, default=None, help="Optional provider temperature")
    agent_session_create_parser.add_argument("--max-tokens", type=int, default=None, help="Optional max output tokens")
    agent_session_create_parser.add_argument("--stream", action="store_true", help="Enable provider streaming when supported")
    agent_session_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_session_compact_parser = agent_session_subparsers.add_parser(
        "compact",
        help="Compact an experimental agent session transcript",
    )
    agent_session_compact_parser.add_argument("session_id", help="Agent session id")
    agent_session_compact_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_session_compact_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_session_inspect_parser = agent_session_subparsers.add_parser(
        "inspect",
        help="Inspect an experimental agent session",
    )
    agent_session_inspect_parser.add_argument("session_id", help="Agent session id")
    agent_session_inspect_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_session_inspect_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_message_parser = agent_subparsers.add_parser(
        "message",
        help="Agent message operations",
    )
    agent_message_subparsers = agent_message_parser.add_subparsers(dest="agent_message_subcommand", required=True)

    agent_message_send_parser = agent_message_subparsers.add_parser(
        "send",
        help="Send a message to an experimental agent session",
    )
    agent_message_send_parser.add_argument("session_id", help="Agent session id")
    agent_message_send_parser.add_argument("message", help="Message text")
    agent_message_send_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    agent_message_send_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_action_parser = agent_subparsers.add_parser(
        "action",
        help="Agent action operations",
    )
    agent_action_subparsers = agent_action_parser.add_subparsers(dest="agent_action_subcommand", required=True)

    agent_action_approve_parser = agent_action_subparsers.add_parser(
        "approve",
        help="Approve or reject a pending agent action",
    )
    agent_action_approve_parser.add_argument("session_id", help="Agent session id")
    agent_action_approve_parser.add_argument("action_id", help="Agent action id")
    agent_action_approve_parser.add_argument(
        "--reject",
        action="store_true",
        help="Reject instead of approve"
    )
    agent_action_approve_parser.add_argument(
        "--project", dest="project_root", default=".",
        help="Path to project directory"
    )
    agent_action_approve_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_providers_parser = agent_subparsers.add_parser(
        "providers",
        help="Agent provider operations",
    )
    agent_providers_subparsers = agent_providers_parser.add_subparsers(dest="agent_providers_subcommand", required=True)
    agent_providers_list_parser = agent_providers_subparsers.add_parser(
        "list",
        help="List configured agent providers",
    )
    agent_providers_list_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_providers_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_providers_login_parser = agent_providers_subparsers.add_parser(
        "login",
        help="Store provider credentials or delegate managed Codex login",
    )
    agent_providers_login_parser.add_argument("provider", help="Provider id, e.g. opencode-go or openai")
    agent_providers_login_parser.add_argument("--api-key-stdin", action="store_true", help="Read API key from stdin")
    agent_providers_login_parser.add_argument("--codex-chatgpt", action="store_true", help="Delegate OpenAI login to the official Codex ChatGPT flow")
    agent_providers_login_parser.add_argument("--device-auth", action="store_true", help="Use the official Codex device-code login flow")
    agent_providers_login_parser.add_argument("--base-url", default="", help="Optional provider base URL")
    agent_providers_login_parser.add_argument("--model", default="", help="Optional default model")
    agent_providers_login_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_providers_login_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_providers_logout_parser = agent_providers_subparsers.add_parser(
        "logout",
        help="Remove provider credentials",
    )
    agent_providers_logout_parser.add_argument("provider", help="Provider id")
    agent_providers_logout_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_providers_logout_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_providers_status_parser = agent_providers_subparsers.add_parser(
        "status",
        help="Show provider auth status",
    )
    agent_providers_status_parser.add_argument("provider", nargs="?", default="", help="Optional provider id")
    agent_providers_status_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_providers_status_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    agent_usage_parser = agent_subparsers.add_parser(
        "usage",
        help="Show token/cost usage for an agent session",
    )
    agent_usage_parser.add_argument("session_id", help="Agent session id")
    agent_usage_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    agent_usage_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    return parser


def dispatch_command(parsed: argparse.Namespace) -> int:
    """Dispatch to appropriate command handler based on parsed args."""
    from pathlib import Path
    
    if not parsed.command:
        return 0  # Help was already printed
    
    # === capabilities ===
    if parsed.command == "ai":
        if parsed.ai_subcommand == "start":
            return cmd_ai_start(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        if parsed.ai_subcommand == "compliance":
            return cmd_ai_compliance(
                project_path=Path(parsed.project_root).resolve(),
                strict=parsed.strict,
                json_output=parsed.json,
            )

    # === capabilities ===
    if parsed.command == "capabilities":
        return cmd_capabilities(json_output=parsed.json)
    
    # === doctor ===
    elif parsed.command == "doctor":
        return cmd_doctor(
            project_path=Path(parsed.project_root).resolve(),
            json_output=parsed.json,
        )
    
    # === project ===
    elif parsed.command == "project":
        if parsed.project_subcommand == "info":
            return cmd_project_info(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        elif parsed.project_subcommand == "bootstrap-ai":
            return cmd_project_bootstrap_ai(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )

    # === recipe ===
    elif parsed.command == "recipe":
        if parsed.recipe_subcommand == "list":
            return cmd_recipe_list(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        if parsed.recipe_subcommand == "show":
            return cmd_recipe_show(
                project_path=Path(parsed.project_root).resolve(),
                recipe_id=parsed.recipe_id,
                json_output=parsed.json,
            )
        if parsed.recipe_subcommand == "run":
            return cmd_recipe_run(
                project_path=Path(parsed.project_root).resolve(),
                recipe_id=parsed.recipe_id,
                json_output=parsed.json,
            )

    # === game ===
    elif parsed.command == "game":
        if parsed.game_subcommand == "platformer":
            if parsed.game_platformer_subcommand == "create":
                return cmd_game_platformer_create(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-player":
                return cmd_game_platformer_add_player(
                    project_path=Path(parsed.project_root).resolve(),
                    x=parsed.x,
                    y=parsed.y,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-ground":
                return cmd_game_platformer_add_ground(
                    project_path=Path(parsed.project_root).resolve(),
                    from_x=parsed.from_x,
                    to_x=parsed.to_x,
                    y=parsed.y,
                    name=parsed.name,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-platform":
                return cmd_game_platformer_add_platform(
                    project_path=Path(parsed.project_root).resolve(),
                    x=parsed.x,
                    y=parsed.y,
                    width=parsed.width,
                    name=parsed.name,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-goal":
                return cmd_game_platformer_add_goal(
                    project_path=Path(parsed.project_root).resolve(),
                    x=parsed.x,
                    y=parsed.y,
                    name=parsed.name,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-coin":
                return cmd_game_platformer_add_coin(
                    project_path=Path(parsed.project_root).resolve(),
                    x=parsed.x,
                    y=parsed.y,
                    points=parsed.points,
                    name=parsed.name,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-hazard":
                return cmd_game_platformer_add_hazard(
                    project_path=Path(parsed.project_root).resolve(),
                    x=parsed.x,
                    y=parsed.y,
                    damage=parsed.damage,
                    name=parsed.name,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-respawn":
                return cmd_game_platformer_add_respawn(
                    project_path=Path(parsed.project_root).resolve(),
                    x=parsed.x,
                    y=parsed.y,
                    spawn_id=parsed.spawn_id,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-moving-platform":
                return cmd_game_platformer_add_moving_platform(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    x=parsed.x,
                    y=parsed.y,
                    width=parsed.width,
                    height=parsed.height,
                    to_x=parsed.to_x,
                    to_y=parsed.to_y,
                    speed=parsed.speed,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-enemy-patrol":
                return cmd_game_platformer_add_enemy_patrol(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    x=parsed.x,
                    y=parsed.y,
                    points=parsed.point,
                    damage=parsed.damage,
                    speed=parsed.speed,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-checkpoint":
                return cmd_game_platformer_add_checkpoint(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    x=parsed.x,
                    y=parsed.y,
                    checkpoint_id=parsed.checkpoint_id,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "add-killzone":
                return cmd_game_platformer_add_killzone(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    x=parsed.x,
                    y=parsed.y,
                    width=parsed.width,
                    height=parsed.height,
                    damage=parsed.damage,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "set-camera-follow":
                return cmd_game_platformer_set_camera_follow(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    target=parsed.target,
                    offset_x=parsed.offset_x,
                    offset_y=parsed.offset_y,
                    dead_zone_width=parsed.dead_zone_width,
                    dead_zone_height=parsed.dead_zone_height,
                    zoom=parsed.zoom,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "set-bounds":
                return cmd_game_platformer_set_bounds(
                    project_path=Path(parsed.project_root).resolve(),
                    name=parsed.name,
                    left=parsed.left,
                    right=parsed.right,
                    top=parsed.top,
                    bottom=parsed.bottom,
                    camera=parsed.camera,
                    json_output=parsed.json,
                )
            if parsed.game_platformer_subcommand == "validate":
                return cmd_game_platformer_validate(
                    project_path=Path(parsed.project_root).resolve(),
                    json_output=parsed.json,
                )
    
    # === scene ===
    elif parsed.command == "scene":
        if parsed.scene_subcommand == "list":
            return cmd_scene_list(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        elif parsed.scene_subcommand == "create":
            return cmd_scene_create(
                project_path=Path(parsed.project_root).resolve(),
                name=parsed.name,
                json_output=parsed.json,
            )
        elif parsed.scene_subcommand == "load":
            return cmd_scene_load(
                project_path=Path(parsed.project_root).resolve(),
                path=parsed.path,
                json_output=parsed.json,
            )
        elif parsed.scene_subcommand == "save":
            return cmd_scene_save(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )

    # === runtime ===
    elif parsed.command == "runtime":
        if parsed.runtime_subcommand == "play":
            return cmd_runtime_play(
                project_path=Path(parsed.project_root).resolve(),
                headless=parsed.headless,
                json_output=parsed.json,
            )
        elif parsed.runtime_subcommand == "step":
            return cmd_runtime_step(
                project_path=Path(parsed.project_root).resolve(),
                frames=parsed.frames,
                input_spec=parsed.input_spec,
                json_output=parsed.json,
            )
        elif parsed.runtime_subcommand == "stop":
            return cmd_runtime_stop(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        elif parsed.runtime_subcommand == "status":
            return cmd_runtime_status(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        elif parsed.runtime_subcommand == "entities":
            return cmd_runtime_entities(
                project_path=Path(parsed.project_root).resolve(),
                tag=parsed.tag,
                layer=parsed.layer,
                active_only=parsed.active_only,
                json_output=parsed.json,
            )
        elif parsed.runtime_subcommand == "inspect":
            return cmd_runtime_inspect(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                json_output=parsed.json,
            )
        elif parsed.runtime_subcommand == "events":
            return cmd_runtime_events(
                project_path=Path(parsed.project_root).resolve(),
                count=parsed.count,
                step_frames=parsed.step_frames,
                json_output=parsed.json,
            )

    # === entity ===
    elif parsed.command == "entity":
        if parsed.entity_subcommand == "create":
            components = None
            if parsed.components:
                components = json.loads(parsed.components)
            return cmd_entity_create(
                project_path=Path(parsed.project_root).resolve(),
                name=parsed.name,
                components=components,
                json_output=parsed.json,
            )
    
    # === component ===
    elif parsed.command == "component":
        if parsed.component_subcommand == "add":
            data = None
            if parsed.data:
                data = json.loads(parsed.data)
            return cmd_component_add(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                component_name=parsed.component,
                data=data,
                json_output=parsed.json,
            )

    # === prefab ===
    elif parsed.command == "prefab":
        if parsed.prefab_subcommand == "create":
            return cmd_prefab_create(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                prefab_path=parsed.path,
                replace_original=parsed.replace_original,
                instance_name=parsed.instance_name,
                json_output=parsed.json,
            )
        elif parsed.prefab_subcommand == "instantiate":
            return cmd_prefab_instantiate(
                project_path=Path(parsed.project_root).resolve(),
                prefab_path=parsed.path,
                name=parsed.name,
                parent=parsed.parent,
                json_output=parsed.json,
            )
        elif parsed.prefab_subcommand == "unpack":
            return cmd_prefab_unpack(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                json_output=parsed.json,
            )
        elif parsed.prefab_subcommand == "apply":
            return cmd_prefab_apply(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                json_output=parsed.json,
            )
        elif parsed.prefab_subcommand == "list":
            return cmd_prefab_list(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )

    # === animator ===
    elif parsed.command == "animator":
        if parsed.animator_subcommand == "info":
            return cmd_animator_info(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                json_output=parsed.json,
            )
        elif parsed.animator_subcommand == "set-sheet":
            return cmd_animator_set_sheet(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                asset_path=parsed.asset,
                json_output=parsed.json,
            )
        elif parsed.animator_subcommand == "ensure":
            return cmd_animator_ensure(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                sprite_sheet=parsed.sprite_sheet,
                json_output=parsed.json,
            )
        elif parsed.animator_subcommand == "state":
            # Nueva gramática jerárquica: animator state <action>
            if parsed.animator_state_subcommand == "create":
                slice_names = [s.strip() for s in parsed.slices.split(",") if s.strip()]
                # Determine loop value: explicit --no-loop or --loop, default to True
                loop = True if parsed.loop is None else parsed.loop
                return cmd_animator_upsert_state(
                    project_path=Path(parsed.project_root).resolve(),
                    entity_name=parsed.entity,
                    state_name=parsed.state,
                    slice_names=slice_names,
                    fps=parsed.fps,
                    loop=loop,
                    set_default=parsed.set_default,
                    auto_create=parsed.auto_create,
                    json_output=parsed.json,
                )
            elif parsed.animator_state_subcommand == "remove":
                return cmd_animator_remove_state(
                    project_path=Path(parsed.project_root).resolve(),
                    entity_name=parsed.entity,
                    state_name=parsed.state,
                    json_output=parsed.json,
                )
        # LEGACY COMMANDS (compatibilidad temporal)
        elif parsed.animator_subcommand == "upsert-state":
            # Legacy alias para 'animator state create'
            slice_names = [s.strip() for s in parsed.slices.split(",") if s.strip()]
            loop = True if parsed.loop is None else parsed.loop
            import warnings
            warnings.warn(
                "'animator upsert-state' is deprecated. Use 'animator state create' instead.",
                DeprecationWarning,
                stacklevel=1
            )
            return cmd_animator_upsert_state(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                state_name=parsed.state,
                slice_names=slice_names,
                fps=parsed.fps,
                loop=loop,
                set_default=parsed.set_default,
                auto_create=parsed.auto_create,
                json_output=parsed.json,
            )
        elif parsed.animator_subcommand == "remove-state":
            # Legacy alias para 'animator state remove'
            import warnings
            warnings.warn(
                "'animator remove-state' is deprecated. Use 'animator state remove' instead.",
                DeprecationWarning,
                stacklevel=1
            )
            return cmd_animator_remove_state(
                project_path=Path(parsed.project_root).resolve(),
                entity_name=parsed.entity,
                state_name=parsed.state,
                json_output=parsed.json,
            )
    
    # === asset ===
    elif parsed.command == "asset":
        if parsed.asset_subcommand == "list":
            return cmd_assets_list(
                project_path=Path(parsed.project_root).resolve(),
                search=parsed.search,
                json_output=parsed.json,
            )
        elif parsed.asset_subcommand == "slice":
            if parsed.slice_subcommand == "list":
                return cmd_slices_list(
                    project_path=Path(parsed.project_root).resolve(),
                    asset_path=parsed.asset,
                    json_output=parsed.json,
                )
            elif parsed.slice_subcommand == "grid":
                return cmd_slices_grid(
                    project_path=Path(parsed.project_root).resolve(),
                    asset_path=parsed.asset,
                    cell_width=parsed.cell_width,
                    cell_height=parsed.cell_height,
                    margin=parsed.margin,
                    spacing=parsed.spacing,
                    pivot_x=parsed.pivot_x,
                    pivot_y=parsed.pivot_y,
                    naming_prefix=parsed.naming_prefix,
                    json_output=parsed.json,
                )
            elif parsed.slice_subcommand == "auto":
                return cmd_slices_auto(
                    project_path=Path(parsed.project_root).resolve(),
                    asset_path=parsed.asset,
                    pivot_x=parsed.pivot_x,
                    pivot_y=parsed.pivot_y,
                    naming_prefix=parsed.naming_prefix,
                    alpha_threshold=parsed.alpha_threshold,
                    preview_only=parsed.preview,
                    json_output=parsed.json,
                )
            elif parsed.slice_subcommand == "manual":
                # Parse slices from JSON string or file
                slices_input = parsed.slices
                if slices_input.startswith("[") or slices_input.startswith("{"):
                    slices_data = json.loads(slices_input)
                else:
                    slices_file = Path(slices_input)
                    if not slices_file.exists():
                        slices_file = Path(parsed.project_root) / slices_input
                    slices_data = json.loads(slices_file.read_text(encoding="utf-8"))
                
                if isinstance(slices_data, dict) and "slices" in slices_data:
                    slices_data = slices_data["slices"]
                
                return cmd_slices_manual(
                    project_path=Path(parsed.project_root).resolve(),
                    asset_path=parsed.asset,
                    slices_data=slices_data,
                    pivot_x=parsed.pivot_x,
                    pivot_y=parsed.pivot_y,
                    naming_prefix=parsed.naming_prefix,
                    json_output=parsed.json,
                )

    # === agent ===
    elif parsed.command == "agent":
        if parsed.agent_subcommand == "session" and parsed.agent_session_subcommand == "create":
            return cmd_agent_session_create(
                project_path=Path(parsed.project_root).resolve(),
                permission_mode=parsed.permission_mode,
                title=parsed.title,
                provider_id=parsed.provider_id,
                model=parsed.model,
                temperature=parsed.temperature,
                max_tokens=parsed.max_tokens,
                stream=parsed.stream,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "session" and parsed.agent_session_subcommand == "compact":
            return cmd_agent_session_compact(
                project_path=Path(parsed.project_root).resolve(),
                session_id=parsed.session_id,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "session" and parsed.agent_session_subcommand == "inspect":
            return cmd_agent_session_inspect(
                project_path=Path(parsed.project_root).resolve(),
                session_id=parsed.session_id,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "message" and parsed.agent_message_subcommand == "send":
            return cmd_agent_message_send(
                project_path=Path(parsed.project_root).resolve(),
                session_id=parsed.session_id,
                message=parsed.message,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "action" and parsed.agent_action_subcommand == "approve":
            return cmd_agent_action_approve(
                project_path=Path(parsed.project_root).resolve(),
                session_id=parsed.session_id,
                action_id=parsed.action_id,
                approved=not parsed.reject,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "providers" and parsed.agent_providers_subcommand == "list":
            return cmd_agent_providers_list(
                project_path=Path(parsed.project_root).resolve(),
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "providers" and parsed.agent_providers_subcommand == "login":
            return cmd_agent_providers_login(
                project_path=Path(parsed.project_root).resolve(),
                provider_id=parsed.provider,
                api_key_stdin=parsed.api_key_stdin,
                codex_chatgpt=parsed.codex_chatgpt,
                device_auth=parsed.device_auth,
                base_url=parsed.base_url,
                model=parsed.model,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "providers" and parsed.agent_providers_subcommand == "logout":
            return cmd_agent_providers_logout(
                project_path=Path(parsed.project_root).resolve(),
                provider_id=parsed.provider,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "providers" and parsed.agent_providers_subcommand == "status":
            return cmd_agent_providers_status(
                project_path=Path(parsed.project_root).resolve(),
                provider_id=parsed.provider,
                json_output=parsed.json,
            )
        elif parsed.agent_subcommand == "usage":
            return cmd_agent_usage(
                project_path=Path(parsed.project_root).resolve(),
                session_id=parsed.session_id,
                json_output=parsed.json,
            )
    
    return 1  # Unknown command


def run_motor_command(args: Optional[List[str]] = None) -> int:
    """
    Execute motor CLI command with given arguments.
    
    Args:
        args: Command line arguments. If None, uses sys.argv[1:].
        
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = create_motor_parser()
    parsed = parser.parse_args(args)
    
    if not parsed.command:
        parser.print_help()
        return 0
    
    try:
        return dispatch_command(parsed)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({
            "success": False,
            "message": f"Unexpected error: {exc}",
            "data": {}
        }, indent=2))
        return 1


def cli_main() -> int:
    """Main entry point for the motor CLI."""
    return run_motor_command(sys.argv[1:])


def main() -> None:
    """Execute motor CLI and exit."""
    raise SystemExit(cli_main())
