"""Tests para GPUParticlesSystem — adaptador CPU real.

Verifica que el adaptador delega correctamente al ParticleSystem subyacente
y expone conteo de partículas real.
"""

from __future__ import annotations

import unittest

from engine.components.particle_emitter2d import ParticleEmitter2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.systems.gpu_particles_system import GPUParticlesSystem


class TestGPUParticlesSystemReal(unittest.TestCase):
    """GPUParticlesSystem debe emitir partículas reales vía CPU fallback."""

    def setUp(self) -> None:
        self.world = World()
        self.system = GPUParticlesSystem()

    def _create_emitter_entity(
        self,
        name: str = "Emitter",
        amount: int = 32,
        one_shot: bool = True,
        lifetime: float = 1.0,
        x: float = 0.0,
        y: float = 0.0,
    ) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        emitter = ParticleEmitter2D(
            amount=amount,
            one_shot=one_shot,
            lifetime=lifetime,
            emitting=True,
        )
        entity.add_component(emitter)

    def test_one_shot_emits_particles(self) -> None:
        """Entidad one_shot produce partículas activas tras update."""
        self._create_emitter_entity(amount=64, one_shot=True)
        self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)

    def test_reset_clears_particles(self) -> None:
        """reset() deja active_particle_count en 0."""
        self._create_emitter_entity(amount=64, one_shot=True)
        self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)
        self.system.reset()
        self.assertEqual(self.system.active_particle_count, 0)
        self.assertEqual(self.system.total_particle_count, 0)

    def test_active_particle_count_zero_before_update(self) -> None:
        """Sin update no hay partículas activas."""
        self._create_emitter_entity(amount=32, one_shot=True)
        self.assertEqual(self.system.active_particle_count, 0)

    def test_update_no_world_is_safe(self) -> None:
        """update con None no lanza excepción y no altera estado."""
        self.system.update(None, 0.016)  # type: ignore[arg-type]
        self.assertEqual(self.system.active_particle_count, 0)

    def test_render_no_world_is_safe(self) -> None:
        """render con None no lanza excepción."""
        self.system.render(None)  # type: ignore[arg-type]

    def test_total_matches_or_exceeds_active(self) -> None:
        """total_particle_count >= active_particle_count siempre."""
        self._create_emitter_entity(amount=64, one_shot=True)
        self.system.update(self.world, 0.016)
        self.assertGreaterEqual(
            self.system.total_particle_count,
            self.system.active_particle_count,
        )

    def test_multiple_updates_continuous_emission(self) -> None:
        """Emisor continuo acumula partículas con múltiples updates."""
        self._create_emitter_entity(
            name="Continuous",
            amount=10,
            one_shot=False,
            lifetime=0.5,
        )
        for _ in range(10):
            self.system.update(self.world, 0.016)
        self.assertGreater(self.system.active_particle_count, 0)

    def test_has_required_methods(self) -> None:
        """Verifica que la clase expone los métodos y propiedades esperados."""
        self.assertTrue(hasattr(self.system, "update"))
        self.assertTrue(hasattr(self.system, "render"))
        self.assertTrue(hasattr(self.system, "reset"))
        self.assertTrue(callable(self.system.update))
        self.assertTrue(callable(self.system.render))
        self.assertTrue(callable(self.system.reset))
        self.assertTrue(hasattr(type(self.system), "active_particle_count"))
        self.assertTrue(hasattr(type(self.system), "total_particle_count"))

    def test_update_docstring_not_empty(self) -> None:
        """Docstring de update explica CPU fallback y safe no-op."""
        doc = GPUParticlesSystem.update.__doc__
        self.assertIsNotNone(doc, "update must have a docstring")
        assert doc is not None
        self.assertGreater(len(doc.strip()), 0, "update docstring must not be empty")

    def test_render_docstring_not_empty(self) -> None:
        """Docstring de render explica CPU fallback y safe no-op."""
        doc = GPUParticlesSystem.render.__doc__
        self.assertIsNotNone(doc, "render must have a docstring")
        assert doc is not None
        self.assertGreater(len(doc.strip()), 0, "render docstring must not be empty")

    def test_reset_docstring_not_empty(self) -> None:
        """Docstring de reset explica clear and no-op behavior."""
        doc = GPUParticlesSystem.reset.__doc__
        self.assertIsNotNone(doc, "reset must have a docstring")
        assert doc is not None
        self.assertGreater(len(doc.strip()), 0, "reset docstring must not be empty")


if __name__ == "__main__":
    unittest.main()
