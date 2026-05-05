"""engine/systems/gpu_particles_system.py — GPUParticlesSystem: CPU-fallback adapter.

Este sistema no ejecuta partículas en GPU real. Delega al ParticleSystem de CPU
para mantener compatibilidad con el wiring existente en RuntimeController y Game,
mientras expone una interfaz estable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.systems.particle_system import ParticleSystem

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.events.event_bus import EventBus


class GPUParticlesSystem:
    """Adaptador de partículas respaldado por ParticleSystem (CPU fallback).

    Expone update(world, dt), render(world), reset(), active_particle_count
    y total_particle_count delegando en la implementación CPU.
    """

    def __init__(self, event_bus: "EventBus | None" = None) -> None:
        self._particle_system: ParticleSystem = ParticleSystem(event_bus=event_bus)

    def update(self, world: "World", dt: float) -> None:
        if world is not None:
            self._particle_system.update(world, dt)

    def render(self, world: "World") -> None:
        if world is not None:
            self._particle_system.render(world)

    def reset(self) -> None:
        self._particle_system.clear()

    @property
    def active_particle_count(self) -> int:
        return self._particle_system.active_particle_count

    @property
    def total_particle_count(self) -> int:
        return self._particle_system.total_particle_count
