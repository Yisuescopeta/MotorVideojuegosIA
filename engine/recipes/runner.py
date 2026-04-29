from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from engine.recipes.registry import RecipeValidationError, get_recipe

AllowedCommand = Tuple[str, ...]

ALLOWED_RECIPE_COMMANDS: frozenset[AllowedCommand] = frozenset(
    {
        ("game", "platformer", "create"),
        ("game", "platformer", "add-coin"),
        ("game", "platformer", "add-hazard"),
        ("game", "platformer", "add-respawn"),
        ("game", "platformer", "validate"),
        ("ai", "compliance"),
        ("runtime", "step"),
        ("runtime", "events"),
    }
)


def _command_path(command: Sequence[str]) -> AllowedCommand:
    if len(command) >= 3 and tuple(command[:2]) == ("game", "platformer"):
        return tuple(command[:3])
    if len(command) >= 2:
        return tuple(command[:2])
    return tuple(command)


def _validate_allowed(command: Sequence[str]) -> None:
    path = _command_path(command)
    if path not in ALLOWED_RECIPE_COMMANDS:
        raise RecipeValidationError(f"Recipe command is not allowlisted: {' '.join(command)}")


def _validate_recipe_commands(recipe: Dict[str, Any]) -> None:
    for step in recipe.get("steps", []):
        _validate_allowed(step["command"])
    for command in recipe.get("validation_commands", []):
        _validate_allowed(command)


def _parse_json_output(text: str) -> Dict[str, Any]:
    start = text.find("{")
    if start < 0:
        return {}
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        return {}


def _run_motor_argv(argv: List[str]) -> tuple[int, str, Dict[str, Any]]:
    from motor.cli import run_motor_command

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            exit_code = run_motor_command(argv)
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 1
    output = stdout_buffer.getvalue()
    if stderr_buffer.getvalue():
        output = output + stderr_buffer.getvalue()
    return exit_code, output, _parse_json_output(output)


def _argv_for_project(command: Iterable[str], project_path: Path) -> List[str]:
    return [*list(command), "--project", str(project_path), "--json"]


def run_recipe(recipe_id: str, project_path: Path) -> Dict[str, Any]:
    recipe = get_recipe(recipe_id)
    _validate_recipe_commands(recipe)

    executed_steps: List[Dict[str, Any]] = []
    first_failure: Dict[str, Any] | None = None

    for step in recipe["steps"]:
        command = list(step["command"])
        argv = _argv_for_project(command, project_path)
        exit_code, raw_output, payload = _run_motor_argv(argv)
        success = exit_code == 0 and bool(payload.get("success", exit_code == 0))
        result = {
            "id": step["id"],
            "description": step["description"],
            "command": command,
            "argv": argv,
            "success": success,
            "exit_code": exit_code,
            "message": str(payload.get("message", "") or ""),
            "data": payload.get("data", {}),
        }
        if not payload:
            result["raw_output"] = raw_output
        executed_steps.append(result)
        if not success:
            first_failure = result
            break

    return {
        "recipe": recipe["id"],
        "version": recipe["version"],
        "description": recipe["description"],
        "success": first_failure is None,
        "steps": executed_steps,
        "first_failure": first_failure,
        "expected_capabilities": list(recipe["expected_capabilities"]),
        "validation_commands": list(recipe["validation_commands"]),
    }


class RecipeRunner:
    """Canonical API-method facade for recipe execution."""

    @staticmethod
    def run_recipe(recipe_id: str, project_path: Path) -> Dict[str, Any]:
        return run_recipe(recipe_id, project_path)
