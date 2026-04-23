"""
engine/components/tween.py - Componente de interpolacion de propiedades (Tween).

Soporta paths simples: "Transform.x", "Transform.y", "Camera2D.zoom",
"Sprite.tint_0", "Sprite.tint_1", "Sprite.tint_2", "Sprite.tint_3" (alpha).
"""

from __future__ import annotations

from typing import Any, Optional

from engine.ecs.component import Component


class Tween(Component):
    """Interpolacion declarativa de una propiedad numerica."""

    VALID_TRANSITIONS: frozenset[str] = frozenset(
        [
            "linear",
            "sine_in",
            "sine_out",
            "sine_in_out",
            "quad_in",
            "quad_out",
            "quad_in_out",
            "cubic_in",
            "cubic_out",
            "cubic_in_out",
            "expo_in",
            "expo_out",
            "expo_in_out",
        ]
    )

    def __init__(
        self,
        property_path: str = "",
        from_value: float = 0.0,
        to_value: float = 1.0,
        duration: float = 1.0,
        autostart: bool = False,
        one_shot: bool = True,
        transition: str = "linear",
    ) -> None:
        self.enabled: bool = True
        self.property_path: str = str(property_path or "").strip()
        self.from_value: float = float(from_value)
        self.to_value: float = float(to_value)
        self.duration: float = max(0.001, float(duration))
        self.autostart: bool = bool(autostart)
        self.one_shot: bool = bool(one_shot)
        self.transition: str = self._coerce_transition(transition)

        # Estado de runtime (no serializable)
        self._elapsed: float = 0.0
        self._is_running: bool = False
        self._is_finished: bool = False
        self._has_autostarted: bool = False

    def _coerce_transition(self, value: Any) -> str:
        normalized = str(value or "linear").strip().lower()
        return normalized if normalized in self.VALID_TRANSITIONS else "linear"

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    @property
    def progress(self) -> float:
        """Progreso normalizado entre 0.0 y 1.0."""
        if self.duration <= 0:
            return 1.0
        return min(1.0, self._elapsed / self.duration)

    def start(self) -> None:
        """Inicia manualmente la interpolacion."""
        self._elapsed = 0.0
        self._is_running = True
        self._is_finished = False

    def stop(self) -> None:
        """Detiene la interpolacion."""
        self._is_running = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "property_path": self.property_path,
            "from_value": self.from_value,
            "to_value": self.to_value,
            "duration": self.duration,
            "autostart": self.autostart,
            "one_shot": self.one_shot,
            "transition": self.transition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tween":
        component = cls(
            property_path=data.get("property_path", ""),
            from_value=data.get("from_value", 0.0),
            to_value=data.get("to_value", 1.0),
            duration=data.get("duration", 1.0),
            autostart=data.get("autostart", False),
            one_shot=data.get("one_shot", True),
            transition=data.get("transition", "linear"),
        )
        component.enabled = data.get("enabled", True)
        return component
