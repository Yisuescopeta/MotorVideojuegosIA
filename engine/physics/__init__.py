"""Backends y abstracciones de fisica."""

from engine.physics.backend import MoveResult2D
from engine.physics.registry import LEGACY_PHYSICS_BACKEND, PhysicsBackendRegistry, ResolvedPhysicsBackend

__all__ = [
    "LEGACY_PHYSICS_BACKEND",
    "MoveResult2D",
    "PhysicsBackendRegistry",
    "ResolvedPhysicsBackend",
]
