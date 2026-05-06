"""Backends y abstracciones de fisica."""

from engine.physics.backend import MotionResult2D, MoveResult2D
from engine.physics.contact_solver import ContactConstraint2D, ImpulseSolver2D
from engine.physics.registry import LEGACY_PHYSICS_BACKEND, PhysicsBackendRegistry, ResolvedPhysicsBackend

__all__ = [
    "ContactConstraint2D",
    "ImpulseSolver2D",
    "LEGACY_PHYSICS_BACKEND",
    "MotionResult2D",
    "MoveResult2D",
    "PhysicsBackendRegistry",
    "ResolvedPhysicsBackend",
]
