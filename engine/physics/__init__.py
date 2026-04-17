"""Backends y abstracciones de fisica."""

from engine.physics.backend import (
    PhysicsAABBHit,
    PhysicsBackend,
    PhysicsBackendInfo,
    PhysicsBackendSelection,
    PhysicsContact,
    PhysicsPoint,
    PhysicsRayHit,
)
from engine.physics.registry import LEGACY_PHYSICS_BACKEND, PhysicsBackendRegistry, ResolvedPhysicsBackend

__all__ = [
    "LEGACY_PHYSICS_BACKEND",
    "PhysicsAABBHit",
    "PhysicsBackend",
    "PhysicsBackendInfo",
    "PhysicsBackendSelection",
    "PhysicsBackendRegistry",
    "PhysicsContact",
    "PhysicsPoint",
    "PhysicsRayHit",
    "ResolvedPhysicsBackend",
]
