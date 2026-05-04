"""
engine/components/audio_listener_2d.py - AudioListener2D component for spatial audio.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class AudioListener2D(Component):
    """Listener 2D for spatial audio. Determines where the scene is "heard" from.

    Only one listener should be active at a time. AudioSources with spatial_blend > 0
    will have their volume attenuated and panned based on distance/angle to this listener.
    """

    def __init__(
        self,
        enabled: bool = True,
        is_active: bool = True,
        max_distance: float = 1000.0,
        attenuation_mode: str = "inverse",
        pan_strength: float = 1.0,
    ) -> None:
        self.enabled: bool = enabled
        self.is_active: bool = is_active
        self.max_distance: float = max_distance
        self.attenuation_mode: str = attenuation_mode  # 'linear', 'inverse', 'exponential'
        self.pan_strength: float = pan_strength

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "is_active": self.is_active,
            "max_distance": self.max_distance,
            "attenuation_mode": self.attenuation_mode,
            "pan_strength": self.pan_strength,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudioListener2D:
        component = cls(
            enabled=data.get("enabled", True),
            is_active=data.get("is_active", True),
            max_distance=data.get("max_distance", 1000.0),
            attenuation_mode=data.get("attenuation_mode", "inverse"),
            pan_strength=data.get("pan_strength", 1.0),
        )
        return component
