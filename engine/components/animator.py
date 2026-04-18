"""
engine/components/animator.py - Componente de animaciones por sprite sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


PARAMETER_TYPES = {"bool", "int", "float", "trigger"}
CONDITION_OPERATORS = {"==", "!=", ">", ">=", "<", "<="}


def _coerce_parameter_type(parameter_type: Any) -> str:
    normalized = str(parameter_type or "bool").strip().lower()
    if normalized in PARAMETER_TYPES:
        return normalized
    return "bool"


def _coerce_parameter_value(value: Any, parameter_type: str) -> bool | int | float:
    normalized_type = _coerce_parameter_type(parameter_type)
    if normalized_type in {"bool", "trigger"}:
        return bool(value)
    if normalized_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_operator(operator: Any) -> str:
    normalized = str(operator or "==").strip()
    if normalized in CONDITION_OPERATORS:
        return normalized
    return "=="


@dataclass
class AnimationData:
    """Datos de una animacion individual."""

    frames: List[int] = field(default_factory=lambda: [0])
    slice_names: List[str] = field(default_factory=list)
    fps: float = 8.0
    loop: bool = True
    on_complete: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "frames": self.frames,
            "slice_names": self.slice_names,
            "fps": self.fps,
            "loop": self.loop,
        }
        if self.on_complete is not None:
            result["on_complete"] = self.on_complete
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationData":
        return cls(
            frames=data.get("frames", [0]),
            slice_names=data.get("slice_names", []),
            fps=data.get("fps", 8.0),
            loop=data.get("loop", True),
            on_complete=data.get("on_complete"),
        )

    def get_frame_count(self) -> int:
        if self.slice_names:
            return len(self.slice_names)
        return len(self.frames)


@dataclass
class AnimationParameterDefinition:
    """Define un parametro serializable de la state machine."""

    type: str = "bool"
    default: bool | int | float = False

    def __post_init__(self) -> None:
        self.type = _coerce_parameter_type(self.type)
        self.default = _coerce_parameter_value(self.default, self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "default": self.default,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AnimationParameterDefinition":
        if not isinstance(data, dict):
            return cls()
        return cls(
            type=data.get("type", "bool"),
            default=data.get("default", False),
        )


@dataclass
class AnimationCondition:
    """Condicion declarativa para una transicion."""

    parameter: str = ""
    operator: str = "=="
    value: Any = True

    def __post_init__(self) -> None:
        self.operator = _coerce_operator(self.operator)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AnimationCondition":
        if not isinstance(data, dict):
            return cls()
        return cls(
            parameter=str(data.get("parameter", "") or ""),
            operator=data.get("operator", "=="),
            value=data.get("value", True),
        )


@dataclass
class AnimationTransition:
    """Transicion entre estados de animacion."""

    to: str = ""
    conditions: List[AnimationCondition] = field(default_factory=list)
    has_exit_time: bool = False
    exit_time: float = 0.0
    force_restart: bool = False
    name: Optional[str] = None

    def __post_init__(self) -> None:
        self.has_exit_time = bool(self.has_exit_time)
        self.force_restart = bool(self.force_restart)
        try:
            self.exit_time = float(self.exit_time)
        except (TypeError, ValueError):
            self.exit_time = 0.0
        self.exit_time = max(0.0, min(1.0, self.exit_time))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "to": self.to,
            "conditions": [condition.to_dict() for condition in self.conditions],
            "has_exit_time": self.has_exit_time,
            "exit_time": self.exit_time,
            "force_restart": self.force_restart,
        }
        if self.name is not None:
            result["name"] = self.name
        return result

    @classmethod
    def from_dict(cls, data: Any) -> "AnimationTransition":
        if not isinstance(data, dict):
            return cls()
        return cls(
            to=str(data.get("to", "") or ""),
            conditions=[
                AnimationCondition.from_dict(condition_data)
                for condition_data in data.get("conditions", [])
            ],
            has_exit_time=data.get("has_exit_time", False),
            exit_time=data.get("exit_time", 0.0),
            force_restart=data.get("force_restart", False),
            name=data.get("name"),
        )


@dataclass
class AnimationStateDefinition:
    """Nodo de la state machine de animacion."""

    transitions: List[AnimationTransition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transitions": [transition.to_dict() for transition in self.transitions],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AnimationStateDefinition":
        if not isinstance(data, dict):
            return cls()
        return cls(
            transitions=[
                AnimationTransition.from_dict(transition_data)
                for transition_data in data.get("transitions", [])
            ],
        )


@dataclass
class AnimationStateMachine:
    """State machine serializable de una sola capa."""

    entry_state: str = ""
    states: Dict[str, AnimationStateDefinition] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_state": self.entry_state,
            "states": {name: state.to_dict() for name, state in self.states.items()},
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AnimationStateMachine":
        if not isinstance(data, dict):
            return cls()
        return cls(
            entry_state=str(data.get("entry_state", "") or ""),
            states={
                state_name: AnimationStateDefinition.from_dict(state_data)
                for state_name, state_data in data.get("states", {}).items()
            },
        )


class Animator(Component):
    """Gestiona animaciones basadas en sprite sheets."""

    def __init__(
        self,
        sprite_sheet: str = "",
        sprite_sheet_ref: Any = None,
        frame_width: int = 32,
        frame_height: int = 32,
        animations: Optional[Dict[str, AnimationData]] = None,
        default_state: str = "idle",
        flip_x: bool = False,
        flip_y: bool = False,
        speed: float = 1.0,
        parameters: Optional[Dict[str, AnimationParameterDefinition]] = None,
        state_machine: Optional[AnimationStateMachine] = None,
    ) -> None:
        self.enabled: bool = True
        self.sprite_sheet_ref = normalize_asset_reference(sprite_sheet_ref if sprite_sheet_ref is not None else sprite_sheet)
        self.sprite_sheet: str = self.sprite_sheet_ref.get("path", "")
        self.frame_width: int = frame_width
        self.frame_height: int = frame_height
        self.animations: Dict[str, AnimationData] = animations or {}
        self.default_state: str = default_state
        self.flip_x: bool = flip_x
        self.flip_y: bool = flip_y
        self.speed: float = max(0.01, float(speed))
        self.parameters: Dict[str, AnimationParameterDefinition] = parameters or {}
        self.state_machine: Optional[AnimationStateMachine] = state_machine
        self._parameter_values: Dict[str, bool | int | float] = self._build_runtime_parameter_store()

        self.current_state: str = default_state
        self.current_frame: int = 0
        self.elapsed_time: float = 0.0
        self.is_finished: bool = False

        if self.current_state not in self.animations:
            self.current_state = self.resolve_entry_state()

    def _build_runtime_parameter_store(self) -> Dict[str, bool | int | float]:
        return {
            name: definition.default
            for name, definition in self.parameters.items()
        }

    def get_sprite_sheet_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.sprite_sheet_ref)

    def sync_sprite_sheet_reference(self, reference: Any) -> None:
        self.sprite_sheet_ref = normalize_asset_reference(reference)
        self.sprite_sheet = self.sprite_sheet_ref.get("path", "")

    def resolve_entry_state(self) -> str:
        state_machine_entry = self.state_machine.entry_state if self.state_machine is not None else ""
        if state_machine_entry in self.animations:
            return state_machine_entry
        if self.default_state in self.animations:
            return self.default_state
        return next(iter(self.animations.keys()), self.default_state)

    def get_parameter_definition(self, name: str) -> Optional[AnimationParameterDefinition]:
        return self.parameters.get(name)

    def set_parameter(self, name: str, value: Any) -> bool:
        definition = self.get_parameter_definition(name)
        if definition is None:
            return False
        self._parameter_values[name] = _coerce_parameter_value(value, definition.type)
        return True

    def get_parameter(self, name: str) -> Optional[bool | int | float]:
        if name not in self.parameters:
            return None
        return self._parameter_values.get(name, self.parameters[name].default)

    def set_trigger(self, name: str) -> bool:
        definition = self.get_parameter_definition(name)
        if definition is None or definition.type != "trigger":
            return False
        self._parameter_values[name] = True
        return True

    def reset_trigger(self, name: str) -> bool:
        definition = self.get_parameter_definition(name)
        if definition is None or definition.type != "trigger":
            return False
        self._parameter_values[name] = False
        return True

    def consume_trigger(self, name: str) -> bool:
        value = bool(self.get_parameter(name))
        if not self.reset_trigger(name):
            return False
        return value

    def get_state_definition(self, state_name: Optional[str] = None) -> Optional[AnimationStateDefinition]:
        if self.state_machine is None:
            return None
        target_state = state_name if state_name is not None else self.current_state
        return self.state_machine.states.get(target_state)

    def get_state_transitions(self, state_name: Optional[str] = None) -> List[AnimationTransition]:
        state = self.get_state_definition(state_name)
        if state is None:
            return []
        return list(state.transitions)

    def evaluate_condition(self, condition: AnimationCondition) -> bool:
        definition = self.get_parameter_definition(condition.parameter)
        if definition is None:
            return False
        left_value = self.get_parameter(condition.parameter)
        right_value = _coerce_parameter_value(condition.value, definition.type)
        operator = condition.operator
        if operator == "==":
            return left_value == right_value
        if operator == "!=":
            return left_value != right_value
        if operator == ">":
            return bool(left_value is not None and left_value > right_value)
        if operator == ">=":
            return bool(left_value is not None and left_value >= right_value)
        if operator == "<":
            return bool(left_value is not None and left_value < right_value)
        if operator == "<=":
            return bool(left_value is not None and left_value <= right_value)
        return False

    def transition_conditions_match(self, transition: AnimationTransition) -> bool:
        return all(self.evaluate_condition(condition) for condition in transition.conditions)

    def consume_transition_triggers(self, transition: AnimationTransition) -> None:
        for condition in transition.conditions:
            definition = self.get_parameter_definition(condition.parameter)
            if definition is not None and definition.type == "trigger":
                self.consume_trigger(condition.parameter)

    def play(self, state: str, force_restart: bool = False) -> str:
        if state not in self.animations:
            print(f"[WARNING] Animator: estado '{state}' no existe")
            return self.current_state
        previous_state = self.current_state
        if state == self.current_state and not force_restart:
            return previous_state
        self.current_state = state
        self.current_frame = 0
        self.elapsed_time = 0.0
        self.is_finished = False
        return previous_state

    def stop(self) -> None:
        self.is_finished = True

    def resume(self) -> None:
        if self.is_finished and self.current_state in self.animations:
            anim = self.animations[self.current_state]
            if not anim.loop:
                self.is_finished = False

    @property
    def is_playing(self) -> bool:
        if self.current_state not in self.animations:
            return False
        if self.is_finished:
            return False
        return True

    @property
    def normalized_time(self) -> float:
        anim = self.get_current_animation()
        if anim is None or anim.get_frame_count() <= 0:
            return 0.0
        return self.current_frame / max(1, anim.get_frame_count() - 1)

    def get_current_animation(self) -> Optional[AnimationData]:
        return self.animations.get(self.current_state)

    def get_current_sprite_frame(self) -> int:
        anim = self.get_current_animation()
        if anim is None or not anim.frames:
            return 0
        frame_index = min(self.current_frame, len(anim.frames) - 1)
        return anim.frames[frame_index]

    def get_current_slice_name(self) -> Optional[str]:
        anim = self.get_current_animation()
        if anim is None or not anim.slice_names:
            return None
        frame_index = min(self.current_frame, len(anim.slice_names) - 1)
        return anim.slice_names[frame_index]

    def get_source_rect(self, sheet_columns: int) -> tuple[int, int, int, int]:
        frame_index = self.get_current_sprite_frame()
        col = frame_index % sheet_columns
        row = frame_index // sheet_columns
        return (
            col * self.frame_width,
            row * self.frame_height,
            self.frame_width,
            self.frame_height,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "enabled": self.enabled,
            "sprite_sheet": self.get_sprite_sheet_reference(),
            "sprite_sheet_path": self.sprite_sheet,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "speed": self.speed,
            "animations": {name: anim.to_dict() for name, anim in self.animations.items()},
            "default_state": self.default_state,
            "current_state": self.current_state,
            "current_frame": self.current_frame,
            "is_finished": self.is_finished,
        }
        if self.parameters:
            result["parameters"] = {
                name: definition.to_dict()
                for name, definition in self.parameters.items()
            }
        if self.state_machine is not None:
            result["state_machine"] = self.state_machine.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Animator":
        animations = {
            name: AnimationData.from_dict(anim_data)
            for name, anim_data in data.get("animations", {}).items()
        }
        parameters = {
            name: AnimationParameterDefinition.from_dict(parameter_data)
            for name, parameter_data in data.get("parameters", {}).items()
        }
        state_machine_data = data.get("state_machine")
        state_machine = (
            AnimationStateMachine.from_dict(state_machine_data)
            if isinstance(state_machine_data, dict)
            else None
        )
        sprite_sheet_ref = normalize_asset_reference(data.get("sprite_sheet"))
        sprite_sheet_path = data.get("sprite_sheet_path", data.get("sprite_sheet", ""))
        if isinstance(sprite_sheet_path, str) and sprite_sheet_path and sprite_sheet_ref.get("path") != sprite_sheet_path:
            sprite_sheet_ref = build_asset_reference(sprite_sheet_path, sprite_sheet_ref.get("guid", ""))

        animator = cls(
            sprite_sheet=sprite_sheet_path,
            sprite_sheet_ref=sprite_sheet_ref,
            frame_width=data.get("frame_width", 32),
            frame_height=data.get("frame_height", 32),
            animations=animations,
            default_state=data.get("default_state", data.get("current_state", "idle")),
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", False),
            speed=data.get("speed", 1.0),
            parameters=parameters,
            state_machine=state_machine,
        )
        animator.enabled = data.get("enabled", True)
        requested_state = data.get("current_state", animator.default_state)
        animator.current_state = requested_state if requested_state in animator.animations else animator.resolve_entry_state()
        animator.current_frame = data.get("current_frame", 0)
        animator.is_finished = data.get("is_finished", False)
        return animator
