"""
tools/engine_cli.py - BACKEND INTERNAL / COMPATIBILITY MODULE

ARCHITECTURE NOTE:
    ╔══════════════════════════════════════════════════════════════════╗
    ║  DEPRECATED: DO NOT USE FOR NEW CODE                             ║
    ╚══════════════════════════════════════════════════════════════════╝

    This module exists ONLY for:
    1. Backward compatibility with existing scripts/workflows
    2. Internal backend functionality shared with motor.cli_core

    ROLE DEFINITION:
        ┌─────────────────┐      ┌──────────────────┐
        │  OFFICIAL CLI   │─────▶│   motor.cli      │
        └─────────────────┘      └──────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │    motor.cli_core    │
                              │  (implementations)   │
                              └──────────────────────┘
                                          ▲
                                          │
        ┌─────────────────┐      ┌──────────────────┐
        │    LEGACY USE   │─────▶│ tools.engine_cli │
        └─────────────────┘      │  (deprecated)    │
                                 └──────────────────┘

    Official CLI (USE THIS):
        motor [command] [options]
        python -m motor [command] [options]

        Python API:
            from motor.cli import run_motor_command
            from motor.cli import create_motor_parser

    Legacy compatibility (DEPRECATED):
        python -m tools.engine_cli [command] [options]
        
        Shows deprecation warning and delegates to motor.cli

MIGRATION GUIDE:
    Old (deprecated):
        from tools.engine_cli import cmd_doctor
        # or
        python -m tools.engine_cli doctor --project .

    New (official):
        from motor.cli_core import cmd_doctor
        # or
        python -m motor doctor --project .
        # or
        from motor.cli import run_motor_command
        run_motor_command(["doctor", "--project", "."])

INTERNAL USE ONLY:
    This module re-exports from motor.cli_core for backward compatibility.
    Internal engine code should import directly from motor.cli_core.
"""

from __future__ import annotations

import warnings
import sys
from typing import List, Optional

# Re-export command handlers from motor.cli_core for backward compatibility
# New code should import directly from motor.cli_core
from motor.cli_core import (
    # Commands
    cmd_capabilities,
    cmd_doctor,
    cmd_project_info,
    cmd_scene_list,
    cmd_scene_create,
    cmd_entity_create,
    cmd_component_add,
    cmd_assets_list,
    cmd_slices_list,
    cmd_slices_grid,
    cmd_slices_auto,
    cmd_slices_manual,
    cmd_animator_info,
    cmd_animator_set_sheet,
    cmd_animator_upsert_state,
    cmd_animator_remove_state,
    # Utilities
    _output,
    _ensure_project,
    _init_engine,
    _make_response,
    _print_json,
    # Exceptions
    EngineCLIError,
    ProjectNotFoundError,
    EngineInitError,
)

# Re-export official CLI for transition support
# This allows gradual migration from tools.engine_cli to motor.cli
from motor.cli import run_motor_command, cli_main, main, create_motor_parser

# Legacy compatibility alias
parse_args = create_motor_parser

__all__ = [
    # Commands (deprecated path - use motor.cli_core directly)
    "cmd_capabilities",
    "cmd_doctor",
    "cmd_project_info",
    "cmd_scene_list",
    "cmd_scene_create",
    "cmd_entity_create",
    "cmd_component_add",
    "cmd_assets_list",
    "cmd_slices_list",
    "cmd_slices_grid",
    "cmd_slices_auto",
    "cmd_slices_manual",
    "cmd_animator_info",
    "cmd_animator_set_sheet",
    "cmd_animator_upsert_state",
    "cmd_animator_remove_state",
    # Utilities (internal - not for CLI use)
    "_output",
    "_ensure_project",
    "_init_engine",
    "_make_response",
    "_print_json",
    # Exceptions
    "EngineCLIError",
    "ProjectNotFoundError",
    "EngineInitError",
    # Official CLI (transition support)
    "run_motor_command",
    "cli_main",
    "main",
    "create_motor_parser",
    "parse_args",  # Legacy alias
]


def _emit_deprecation_warning() -> None:
    """Emit warning about deprecated CLI path."""
    warnings.warn(
        "python -m tools.engine_cli is deprecated. Use 'motor' or 'python -m motor' instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def deprecated_main() -> int:
    """
    DEPRECATED entry point for backward compatibility.
    
    Emits deprecation warning and delegates to the official motor CLI.
    
    Returns:
        Exit code from cli_main()
    """
    _emit_deprecation_warning()
    print(
        "[DEPRECATED] Using python -m tools.engine_cli is deprecated.\n"
        "[DEPRECATED] Please use: motor {}\n".format(" ".join(sys.argv[1:])),
        file=sys.stderr,
    )
    return cli_main()


if __name__ == "__main__":
    # When run directly, show deprecation and delegate to official CLI
    raise SystemExit(deprecated_main())
