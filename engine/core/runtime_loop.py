from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RuntimePhase(str, Enum):
    """Explicit runtime phases used by the shared frame sequencer."""

    FIXED_UPDATE = "fixed_update"
    UPDATE = "update"
    POST_UPDATE = "post_update"
    RENDER = "render"


@dataclass(frozen=True)
class RuntimeTickPlan:
    """Resolved work for a single runtime frame."""

    frame_dt: float
    fixed_dt: float
    fixed_steps: int
    is_stepping: bool
    should_render_like: bool


@dataclass
class RuntimeLoopState:
    """Mutable fixed-step state shared across runtime sessions."""

    accumulator: float = 0.0
    fixed_dt: float = 1.0 / 60.0
    max_fixed_steps_per_frame: int = 4

    def reset(self) -> None:
        self.accumulator = 0.0
