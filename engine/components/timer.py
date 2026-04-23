"""
engine/components/timer.py - Componente de temporizador al estilo Godot.

Emite señales: timeout, started, stopped.
Soporta: one_shot, autostart, paused, time_scale ignore.
"""

from __future__ import annotations

from typing import Any, Optional

from engine.ecs.component import Component


class Timer(Component):
    """Temporizador declarativo para entidades del ECS."""

    def __init__(
        self,
        wait_time: float = 1.0,
        one_shot: bool = False,
        autostart: bool = False,
        paused: bool = False,
        ignore_time_scale: bool = False,
    ) -> None:
        self.enabled: bool = True
        self.wait_time: float = max(0.001, float(wait_time))
        self.one_shot: bool = bool(one_shot)
        self.autostart: bool = bool(autostart)
        self.paused: bool = bool(paused)
        self.ignore_time_scale: bool = bool(ignore_time_scale)

        # Estado de runtime (no serializable directamente)
        self._time_left: float = 0.0
        self._is_stopped: bool = True
        self._is_running: bool = False

    @property
    def time_left(self) -> float:
        """Tiempo restante en segundos."""
        return self._time_left

    @property
    def is_stopped(self) -> bool:
        """Indica si el timer está detenido."""
        return self._is_stopped

    @property
    def is_running(self) -> bool:
        """Indica si el timer está corriendo."""
        return self._is_running and not self.paused

    def start(self, wait_time: Optional[float] = None) -> None:
        """Inicia o reinicia el temporizador."""
        if wait_time is not None:
            self.wait_time = max(0.001, float(wait_time))
        self._time_left = self.wait_time
        self._is_stopped = False
        self._is_running = True

    def stop(self) -> None:
        """Detiene el temporizador sin completar."""
        self._is_stopped = True
        self._is_running = False
        self._time_left = 0.0

    def pause(self) -> None:
        """Pausa el temporizador."""
        self.paused = True

    def resume(self) -> None:
        """Reanuda el temporizador pausado."""
        self.paused = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "wait_time": self.wait_time,
            "one_shot": self.one_shot,
            "autostart": self.autostart,
            "paused": self.paused,
            "ignore_time_scale": self.ignore_time_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Timer":
        component = cls(
            wait_time=data.get("wait_time", 1.0),
            one_shot=data.get("one_shot", False),
            autostart=data.get("autostart", False),
            paused=data.get("paused", False),
            ignore_time_scale=data.get("ignore_time_scale", False),
        )
        component.enabled = data.get("enabled", True)
        return component
