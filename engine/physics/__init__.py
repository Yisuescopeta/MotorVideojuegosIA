"""Backends y abstracciones de fisica."""

from engine.physics.registry import LEGACY_PHYSICS_BACKEND, PhysicsBackendRegistry, ResolvedPhysicsBackend

__all__ = [
    "LEGACY_PHYSICS_BACKEND",
    "PhysicsBackendRegistry",
    "ResolvedPhysicsBackend",
]
