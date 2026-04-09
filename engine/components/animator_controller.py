"""
engine/components/animator_controller.py - Controlador serializable para Animator.
"""

from __future__ import annotations

import copy
from typing import Any

from engine.ecs.component import Component


class AnimatorController(Component):
    """Maquina de estados simple que selecciona clips del Animator."""

    VALID_PARAMETER_TYPES = {"bool", "int", "float", "trigger"}
    VALID_BOOL_OPS = {"is_true", "is_false"}
    VALID_NUMERIC_OPS = {"equals", "not_equals", "greater", "greater_or_equal", "less", "less_or_equal"}
    VALID_TRIGGER_OPS = {"is_set"}

    def __init__(
        self,
        *,
        enabled: bool = True,
        entry_state: str = "",
        parameters: dict[str, dict[str, Any]] | None = None,
        states: dict[str, dict[str, Any]] | None = None,
        transitions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.enabled: bool = bool(enabled)
        self.entry_state: str = str(entry_state or "")
        self.parameters: dict[str, dict[str, Any]] = copy.deepcopy(parameters or {})
        self.states: dict[str, dict[str, Any]] = copy.deepcopy(states or {})
        self.transitions: list[dict[str, Any]] = copy.deepcopy(transitions or [])

        self.runtime_parameters: dict[str, Any] = {}
        self.pending_triggers: set[str] = set()
        self.active_state: str = ""
        self.previous_state: str = ""
        self.time_in_state: float = 0.0
        self.last_transition_id: str = ""
        self.ensure_runtime_parameters()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "entry_state": self.entry_state,
            "parameters": copy.deepcopy(self.parameters),
            "states": copy.deepcopy(self.states),
            "transitions": copy.deepcopy(self.transitions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimatorController":
        return cls(
            enabled=bool(data.get("enabled", True)),
            entry_state=str(data.get("entry_state", "") or ""),
            parameters=copy.deepcopy(data.get("parameters", {})),
            states=copy.deepcopy(data.get("states", {})),
            transitions=copy.deepcopy(data.get("transitions", [])),
        )

    def reset_runtime_state(self) -> None:
        self.active_state = ""
        self.previous_state = ""
        self.time_in_state = 0.0
        self.last_transition_id = ""
        self.pending_triggers.clear()
        self.ensure_runtime_parameters(reset_missing=True)

    def ensure_runtime_parameters(self, *, reset_missing: bool = False) -> None:
        if not isinstance(self.runtime_parameters, dict):
            self.runtime_parameters = {}
        valid_names = set()
        for parameter_name, definition in self.parameters.items():
            if not isinstance(parameter_name, str) or not parameter_name.strip():
                continue
            normalized_name = parameter_name.strip()
            valid_names.add(normalized_name)
            if reset_missing or normalized_name not in self.runtime_parameters:
                self.runtime_parameters[normalized_name] = self._default_runtime_value(definition)
        for runtime_name in list(self.runtime_parameters.keys()):
            if runtime_name not in valid_names:
                del self.runtime_parameters[runtime_name]
        self.pending_triggers.intersection_update(valid_names)

    def has_parameter(self, parameter_name: str) -> bool:
        return str(parameter_name or "").strip() in self.parameters

    def get_parameter_definition(self, parameter_name: str) -> dict[str, Any] | None:
        normalized = str(parameter_name or "").strip()
        definition = self.parameters.get(normalized)
        return definition if isinstance(definition, dict) else None

    def get_parameter_type(self, parameter_name: str) -> str:
        definition = self.get_parameter_definition(parameter_name) or {}
        raw_type = str(definition.get("type", "float") or "float").strip().lower()
        return raw_type if raw_type in self.VALID_PARAMETER_TYPES else "float"

    def get_parameter_value(self, parameter_name: str) -> Any:
        self.ensure_runtime_parameters()
        normalized = str(parameter_name or "").strip()
        if self.get_parameter_type(normalized) == "trigger":
            return normalized in self.pending_triggers
        return self.runtime_parameters.get(normalized, self._default_runtime_value(self.get_parameter_definition(normalized) or {}))

    def set_parameter(self, parameter_name: str, value: Any) -> bool:
        self.ensure_runtime_parameters()
        normalized = str(parameter_name or "").strip()
        if normalized not in self.parameters:
            return False
        parameter_type = self.get_parameter_type(normalized)
        if parameter_type == "trigger":
            if bool(value):
                return self.set_trigger(normalized)
            return self.reset_trigger(normalized)
        self.runtime_parameters[normalized] = self._coerce_runtime_value(parameter_type, value)
        return True

    def set_trigger(self, parameter_name: str) -> bool:
        self.ensure_runtime_parameters()
        normalized = str(parameter_name or "").strip()
        if normalized not in self.parameters or self.get_parameter_type(normalized) != "trigger":
            return False
        self.pending_triggers.add(normalized)
        self.runtime_parameters[normalized] = True
        return True

    def reset_trigger(self, parameter_name: str) -> bool:
        self.ensure_runtime_parameters()
        normalized = str(parameter_name or "").strip()
        if normalized not in self.parameters or self.get_parameter_type(normalized) != "trigger":
            return False
        self.pending_triggers.discard(normalized)
        self.runtime_parameters[normalized] = False
        return True

    def consume_triggers(self, parameter_names: list[str] | set[str]) -> None:
        for parameter_name in parameter_names:
            normalized = str(parameter_name or "").strip()
            if normalized:
                self.reset_trigger(normalized)

    def get_state_payload(self, state_name: str) -> dict[str, Any] | None:
        payload = self.states.get(str(state_name or "").strip())
        return payload if isinstance(payload, dict) else None

    def get_state_animation(self, state_name: str) -> str:
        payload = self.get_state_payload(state_name) or {}
        return str(payload.get("animation_state", "") or "").strip()

    def set_active_state(self, state_name: str, *, last_transition_id: str = "manual") -> bool:
        normalized = str(state_name or "").strip()
        if normalized not in self.states:
            return False
        previous_state = self.active_state
        self.previous_state = previous_state
        self.active_state = normalized
        self.time_in_state = 0.0
        self.last_transition_id = str(last_transition_id or "")
        return True

    def get_runtime_snapshot(self) -> dict[str, Any]:
        self.ensure_runtime_parameters()
        parameter_values: dict[str, Any] = {}
        for parameter_name in self.parameters:
            parameter_values[parameter_name] = self.get_parameter_value(parameter_name)
        return {
            "enabled": bool(self.enabled),
            "entry_state": str(self.entry_state),
            "active_state": str(self.active_state),
            "previous_state": str(self.previous_state),
            "time_in_state": float(self.time_in_state),
            "last_transition_id": str(self.last_transition_id),
            "parameters": parameter_values,
            "pending_triggers": sorted(self.pending_triggers),
        }

    def _default_runtime_value(self, definition: dict[str, Any]) -> Any:
        parameter_type = self.get_parameter_type_from_definition(definition)
        if parameter_type == "bool":
            return bool(definition.get("default", False))
        if parameter_type == "int":
            return int(definition.get("default", 0))
        if parameter_type == "float":
            return float(definition.get("default", 0.0))
        return False

    def _coerce_runtime_value(self, parameter_type: str, value: Any) -> Any:
        if parameter_type == "bool":
            return bool(value)
        if parameter_type == "int":
            return int(value)
        if parameter_type == "float":
            return float(value)
        return bool(value)

    def get_parameter_type_from_definition(self, definition: dict[str, Any]) -> str:
        raw_type = str(definition.get("type", "float") or "float").strip().lower()
        return raw_type if raw_type in self.VALID_PARAMETER_TYPES else "float"
