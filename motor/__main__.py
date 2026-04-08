"""
motor/__main__.py - Entrypoint for `python -m motor`

ARCHITECTURE NOTE:
    This is the OFFICIAL CLI entrypoint for MotorVideojuegosIA.
    
    Execution flow:
        python -m motor [args]
            ↓
        motor/__main__.py (this file)
            ↓
        motor.cli:main()
            ↓
        motor.cli:cli_main()
            ↓
        motor.cli:run_motor_command()

    This module intentionally contains minimal logic. Its sole purpose is to
    delegate to the official CLI implementation in motor.cli.

    For programmatic use:
        from motor.cli import run_motor_command
        exit_code = run_motor_command(["doctor", "--project", "."])

    For backwards compatibility only:
        python -m tools.engine_cli  (deprecated, shows warning)

Official CLI:
    motor [command] [options]
    python -m motor [command] [options]

Examples:
    python -m motor --help
    python -m motor doctor --project . --json
    python -m motor capabilities
"""

from __future__ import annotations

import sys

# Official CLI entrypoint - delegates to motor.cli
from motor.cli import main

if __name__ == "__main__":
    # Delegate to official CLI implementation
    main()
