"""engine/systems/gpu_particles_system.py — GPUParticlesSystem placeholder.

Este sistema es un marcador de posición experimental. No realiza cómputo real de
partículas en GPU. Existe para satisfacer el contrato de RuntimeControllerContext
sin romper el wiring existente ni importar archivos inexistentes.

Si se implementa una feature real de partículas GPU en el futuro, este archivo
será reemplazado por la implementación completa.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.ecs.world import World


class GPUParticlesSystem:
    """Placeholder no-op para sustituto futuro de partículas GPU.

    Expone update(world, dt) y reset() para mantener compatibilidad con
    los call-sites existentes en RuntimeController y Game.
    """

    def update(self, world: "World", dt: float) -> None:
        """No-op: no hay implementación real de partículas GPU todavía."""
        pass

    def render(self, world: "World") -> None:
        """No-op: placeholder sin cómputo real de partículas GPU."""
        pass

    def reset(self) -> None:
        """No-op."""
        pass
