"""engine/components/path_follower_2d.py — PathFollower2D component (Godot PathFollow2D)."""

from __future__ import annotations

from typing import Any, Optional

from engine.ecs.component import Component
from engine.resources.curve_2d import Curve2D


class PathFollower2D(Component):
    """Component that makes an entity follow a Curve2D path.

    Godot mapping: PathFollow2D node.
    Requires Transform component on the same entity.
    """

    def __init__(
        self,
        curve: Optional[Curve2D] = None,
        speed: float = 80.0,
        loop: bool = True,
        cubic_interp: bool = True,
        rotates: bool = True,
        h_offset: float = 0.0,
        v_offset: float = 0.0,
        start_active: bool = True,
    ) -> None:
        self.enabled: bool = True
        self.curve: Optional[Curve2D] = curve
        self.progress: float = 0.0
        self.speed: float = float(speed)
        self.loop: bool = bool(loop)
        self.cubic_interp: bool = bool(cubic_interp)
        self.rotates: bool = bool(rotates)
        self.h_offset: float = float(h_offset)
        self.v_offset: float = float(v_offset)
        self.start_active: bool = bool(start_active)

    @property
    def progress_ratio(self) -> float:
        if self.curve is None:
            return 0.0
        length = self.curve.get_baked_length()
        if length <= 1e-9:
            return 0.0
        return self.progress / length

    @progress_ratio.setter
    def progress_ratio(self, value: float) -> None:
        if self.curve is None:
            return
        length = self.curve.get_baked_length()
        self.progress = max(0.0, min(1.0, float(value))) * length

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "curve": self.curve.to_dict() if self.curve is not None else None,
            "progress": self.progress,
            "speed": self.speed,
            "loop": self.loop,
            "cubic_interp": self.cubic_interp,
            "rotates": self.rotates,
            "h_offset": self.h_offset,
            "v_offset": self.v_offset,
            "start_active": self.start_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathFollower2D":
        curve = None
        curve_data = data.get("curve")
        if curve_data is not None and isinstance(curve_data, dict):
            curve = Curve2D.from_dict(curve_data)

        component = cls(
            curve=curve,
            speed=data.get("speed", 80.0),
            loop=data.get("loop", True),
            cubic_interp=data.get("cubic_interp", True),
            rotates=data.get("rotates", True),
            h_offset=data.get("h_offset", 0.0),
            v_offset=data.get("v_offset", 0.0),
            start_active=data.get("start_active", True),
        )
        component.enabled = bool(data.get("enabled", True))
        component.progress = float(data.get("progress", 0.0))
        return component
