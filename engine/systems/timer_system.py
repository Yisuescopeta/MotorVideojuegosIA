"""
engine/systems/timer_system.py - Sistema de actualizacion de temporizadores.

Actualiza todos los Timer del mundo, emite señales via SignalRuntime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.components.timer import Timer
from engine.ecs.entity import Entity
from engine.ecs.world import World

if TYPE_CHECKING:
    from engine.events.signals import SignalRuntime


class TimerSystem:
    """Sistema que actualiza temporizadores y emite señales."""

    def __init__(self, signal_runtime: Optional["SignalRuntime"] = None) -> None:
        self._signal_runtime: Optional["SignalRuntime"] = signal_runtime

    def set_signal_runtime(self, signal_runtime: "SignalRuntime") -> None:
        """Asigna el runtime de señales para emitir eventos."""
        self._signal_runtime = signal_runtime

    def update(self, world: World, dt: float, time_scale: float = 1.0) -> None:
        """Actualiza todos los timers activos del mundo."""
        for entity in world.get_entities_with(Timer):
            timer = entity.get_component(Timer)
            if timer is None or not timer.enabled:
                continue
            self._update_timer(entity, timer, dt, time_scale)

    def _update_timer(
        self,
        entity: Entity,
        timer: Timer,
        dt: float,
        time_scale: float,
    ) -> None:
        # Autostart en primer frame si está detenido
        if timer.autostart and timer.is_stopped:
            timer.start()
            self._emit(entity, "started")

        if not timer.is_running:
            return

        effective_dt = dt
        if not timer.ignore_time_scale:
            effective_dt *= time_scale

        timer._time_left -= effective_dt

        if timer._time_left <= 0:
            self._emit(entity, "timeout")
            if timer.one_shot:
                timer.stop()
                self._emit(entity, "stopped")
            else:
                excess = -timer._time_left
                timer.start()
                timer._time_left -= excess

    def _emit(self, entity: Entity, signal_name: str) -> None:
        if self._signal_runtime is None:
            return
        self._signal_runtime.emit(entity.name, signal_name)
