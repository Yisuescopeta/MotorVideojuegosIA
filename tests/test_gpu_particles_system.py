"""Tests para GPUParticlesSystem — placeholder no-op.

Verifica que el placeholder expone update/reset/render como no-ops seguros
para mantener compatibilidad con los call-sites de Game.render().
"""

from __future__ import annotations

import unittest

try:
    from engine.systems.gpu_particles_system import GPUParticlesSystem
except ImportError:
    GPUParticlesSystem = None


@unittest.skipIf(GPUParticlesSystem is None, "GPUParticlesSystem not importable")
class TestGPUParticlesSystemNoOp(unittest.TestCase):
    """GPUParticlesSystem placeholder debe exponer update/reset/render seguros."""

    def setUp(self) -> None:
        self.system = GPUParticlesSystem()

    def test_update_is_noop(self) -> None:
        """update(world, dt) no lanza excepción."""
        # Usamos None como world — el placeholder no lo usa.
        self.system.update(None, 0.016)  # type: ignore[arg-type]

    def test_render_is_noop(self) -> None:
        """render(world) no lanza excepción."""
        self.system.render(None)  # type: ignore[arg-type]

    def test_reset_is_noop(self) -> None:
        """reset() no lanza excepción."""
        self.system.reset()

    def test_multiple_calls_safe(self) -> None:
        """Múltiples llamadas consecutivas no fallan ni acumulan estado."""
        for _ in range(5):
            self.system.update(None, 0.016)  # type: ignore[arg-type]
            self.system.render(None)  # type: ignore[arg-type]
            self.system.reset()

    def test_has_required_methods(self) -> None:
        """Verifica que la clase expone los tres métodos esperados."""
        self.assertTrue(hasattr(self.system, "update"))
        self.assertTrue(hasattr(self.system, "render"))
        self.assertTrue(hasattr(self.system, "reset"))
        self.assertTrue(callable(self.system.update))
        self.assertTrue(callable(self.system.render))
        self.assertTrue(callable(self.system.reset))


if __name__ == "__main__":
    unittest.main()
