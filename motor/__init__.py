"""
motor - Official CLI package for MotorVideojuegosIA

ARCHITECTURE:
    This package provides the OFFICIAL command-line interface for AI-facing
    operations and project management.

    Public API (stable):
        motor.cli.create_motor_parser()  -> ArgumentParser
        motor.cli.run_motor_command()    -> int (exit code)
        motor.cli.cli_main()             -> int (entry point)
        motor.cli.main()                 -> None (calls sys.exit)

    Implementation modules (internal):
        motor.cli_core  - Command handlers and business logic
        motor.cli       - Argument parsing and dispatch

    Entrypoints:
        motor [command]               (when installed as script)
        python -m motor [command]     (module execution)

    Backward compatibility (deprecated):
        python -m tools.engine_cli    (shows deprecation warning)

EXAMPLES:
    # As module
    python -m motor doctor --project . --json
    python -m motor capabilities
    python -m motor scene create "Level 1"

    # Programmatic use
    from motor.cli import run_motor_command
    exit_code = run_motor_command(["doctor", "--project", ".", "--json"])

    # Parser introspection
    from motor.cli import create_motor_parser
    parser = create_motor_parser()

DOCUMENTATION:
    - See START_HERE_AI.md in project root
    - See motor_ai.json for capability registry
"""

from __future__ import annotations

# Public API exports
from motor.cli import (
    create_motor_parser,
    run_motor_command,
    cli_main,
    main,
)

__version__ = "2026.03"

__all__ = [
    # Official public API
    "create_motor_parser",  # Create argument parser for introspection
    "run_motor_command",    # Execute command with args list
    "cli_main",             # Entry point returning exit code
    "main",                 # Entry point calling sys.exit
]
