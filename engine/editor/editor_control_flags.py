"""Feature flags for gradual retained EditorControl migration."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any, Mapping

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True, slots=True)
class EditorControlFeatureFlags:
    console_panel: bool = False


@dataclass(slots=True)
class EditorControlFeatureFlagManager:
    flags: EditorControlFeatureFlags = field(default_factory=lambda: editor_control_feature_flags_from_preferences({}))

    @classmethod
    def from_preferences(cls, preferences: Mapping[str, Any] | None) -> "EditorControlFeatureFlagManager":
        return cls(editor_control_feature_flags_from_preferences(preferences))

    def apply_preferences(self, preferences: Mapping[str, Any] | None) -> EditorControlFeatureFlags:
        self.flags = editor_control_feature_flags_from_preferences(preferences)
        return self.flags

    def update(self, values: Mapping[str, Any]) -> EditorControlFeatureFlags:
        stored = editor_control_feature_flags_to_dict(self.flags)
        for name in editor_control_feature_flag_names():
            if name in values:
                stored[name] = _coerce_bool(values[name], stored[name])
        return self.apply_preferences({"editor_feature_flags": stored})


FLAG_ENV_VARS = {
    "console_panel": "MOTOR_EDITOR_CONTROL_CONSOLE",
}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return default


def default_editor_control_feature_flags() -> EditorControlFeatureFlags:
    return editor_control_feature_flags_from_preferences({})


def editor_control_feature_flag_names() -> tuple[str, ...]:
    return tuple(field.name for field in fields(EditorControlFeatureFlags))


def editor_control_feature_flags_to_dict(flags: EditorControlFeatureFlags) -> dict[str, bool]:
    return {name: bool(value) for name, value in asdict(flags).items()}


def editor_control_feature_flags_from_preferences(
    preferences: Mapping[str, Any] | None,
) -> EditorControlFeatureFlags:
    raw_flags = preferences.get("editor_feature_flags", {}) if preferences else {}
    stored = raw_flags if isinstance(raw_flags, Mapping) else {}
    values = {name: _coerce_bool(stored.get(name, False), False) for name in editor_control_feature_flag_names()}
    flags = EditorControlFeatureFlags(**values)
    for name, env_name in FLAG_ENV_VARS.items():
        if os.environ.get(env_name) is not None:
            flags = replace(flags, **{name: _env_bool(env_name, False)})
    return flags


def editor_control_feature_env_overrides() -> dict[str, str]:
    return {name: env_name for name, env_name in FLAG_ENV_VARS.items() if os.environ.get(env_name) is not None}
