"""engine/events/input_events.py — InputEvent types (Godot parity).
Typed input events for keyboard, mouse, joypad, and action-based input.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InputEvent:
    device: int = 0


@dataclass
class InputEventKey(InputEvent):
    keycode: int = 0
    pressed: bool = False
    echo: bool = False


@dataclass
class InputEventMouseButton(InputEvent):
    button_index: int = 0
    pressed: bool = False
    x: float = 0.0
    y: float = 0.0


@dataclass
class InputEventMouseMotion(InputEvent):
    x: float = 0.0
    y: float = 0.0
    relative_x: float = 0.0
    relative_y: float = 0.0


@dataclass
class InputEventJoypadButton(InputEvent):
    button_index: int = 0
    pressed: bool = False


@dataclass
class InputEventJoypadMotion(InputEvent):
    axis: int = 0
    axis_value: float = 0.0


@dataclass
class InputEventAction(InputEvent):
    action: str = ""
    strength: float = 0.0
    pressed: bool = False
