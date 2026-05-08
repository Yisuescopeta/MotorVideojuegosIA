"""Typed value parsing for Inspector edits."""

from __future__ import annotations

import json
from typing import Any


def encode_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_value(text: str, original_value: Any) -> Any:
    value = str(text).strip()
    if isinstance(original_value, bool):
        lowered = value.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        raise ValueError("Expected boolean value")
    if isinstance(original_value, int) and not isinstance(original_value, bool):
        return int(value)
    if isinstance(original_value, float):
        return float(value)
    if isinstance(original_value, str):
        return text
    if isinstance(original_value, list):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError("Expected JSON list")
        return parsed
    if isinstance(original_value, dict):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object")
        return parsed
    if original_value is None:
        if value.lower() in {"", "none", "null"}:
            return None
        raise ValueError("Expected null value")
    raise ValueError(f"Unsupported value type: {type(original_value).__name__}")
