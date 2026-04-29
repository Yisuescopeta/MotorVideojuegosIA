from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

RECIPE_SCHEMA_VERSION = 1
_RECIPES_DIR = Path(__file__).resolve().parent


class RecipeError(Exception):
    """Base recipe error."""


class RecipeNotFoundError(RecipeError):
    """Raised when a bundled recipe id is unknown."""


class RecipeValidationError(RecipeError):
    """Raised when a bundled recipe payload is invalid."""


def _recipe_files() -> List[Path]:
    return sorted(path for path in _RECIPES_DIR.glob("*.json") if path.is_file())


def _load_payload(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecipeValidationError(f"Invalid recipe JSON in {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RecipeValidationError(f"Recipe {path.name} must be a JSON object")
    _validate_recipe_payload(payload, source=path.name)
    return payload


def _validate_string_list(payload: Dict[str, Any], field: str, source: str) -> None:
    value = payload.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise RecipeValidationError(f"Recipe {source} field '{field}' must be a non-empty string list")


def _validate_command(command: Any, source: str, field: str) -> None:
    if not isinstance(command, list) or not command:
        raise RecipeValidationError(f"Recipe {source} {field} command must be a non-empty argv list")
    if not all(isinstance(token, str) and token.strip() for token in command):
        raise RecipeValidationError(f"Recipe {source} {field} command tokens must be non-empty strings")
    forbidden = {"--project", "--json"}
    if any(token in forbidden for token in command):
        raise RecipeValidationError(f"Recipe {source} {field} command cannot include --project or --json")


def _validate_recipe_payload(payload: Dict[str, Any], source: str) -> None:
    for field in ("id", "version", "description"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise RecipeValidationError(f"Recipe {source} field '{field}' must be a non-empty string")
    _validate_string_list(payload, "expected_capabilities", source)

    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RecipeValidationError(f"Recipe {source} field 'steps' must be a non-empty list")
    seen_step_ids: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise RecipeValidationError(f"Recipe {source} step {index} must be an object")
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise RecipeValidationError(f"Recipe {source} step {index} field 'id' must be non-empty")
        if step_id in seen_step_ids:
            raise RecipeValidationError(f"Recipe {source} duplicate step id: {step_id}")
        seen_step_ids.add(step_id)
        if not isinstance(step.get("description"), str) or not step["description"].strip():
            raise RecipeValidationError(f"Recipe {source} step {step_id} description must be non-empty")
        _validate_command(step.get("command"), source, f"step {step_id}")

    validations = payload.get("validation_commands")
    if not isinstance(validations, list) or not validations:
        raise RecipeValidationError(f"Recipe {source} field 'validation_commands' must be a non-empty list")
    for index, command in enumerate(validations):
        _validate_command(command, source, f"validation_commands[{index}]")


def list_recipes() -> List[Dict[str, Any]]:
    recipes = []
    for path in _recipe_files():
        payload = _load_payload(path)
        recipes.append(
            {
                "id": payload["id"],
                "version": payload["version"],
                "description": payload["description"],
                "expected_capabilities": list(payload["expected_capabilities"]),
                "step_count": len(payload["steps"]),
                "validation_command_count": len(payload["validation_commands"]),
            }
        )
    return sorted(recipes, key=lambda item: item["id"])


def get_recipe(recipe_id: str) -> Dict[str, Any]:
    normalized = str(recipe_id or "").strip()
    if not normalized:
        raise RecipeNotFoundError("Recipe id is required")
    for path in _recipe_files():
        payload = _load_payload(path)
        if payload["id"] == normalized:
            return payload
    raise RecipeNotFoundError(f"Unknown recipe: {normalized}")


class RecipeRegistry:
    """Canonical API-method facade for bundled recipes."""

    @staticmethod
    def list_recipes() -> List[Dict[str, Any]]:
        return list_recipes()

    @staticmethod
    def get_recipe(recipe_id: str) -> Dict[str, Any]:
        return get_recipe(recipe_id)
