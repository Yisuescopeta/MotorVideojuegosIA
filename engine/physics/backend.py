from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from engine.physics.types import (
    PhysicsAABBHit,
    PhysicsBackendInfo,
    PhysicsBackendSelection,
    PhysicsContact,
    PhysicsPoint,
    PhysicsRayHit,
)


class PhysicsBackend(ABC):
    """
    Contrato estable para backends de fisica 2D.

    Las capas superiores del motor solo deben depender de:
    - `step()`
    - `query_ray()`
    - `query_aabb()`
    - `collect_contacts()`
    - `set_event_bus()`
    - `get_step_metrics()`
    """

    backend_name: str = "unknown"

    @abstractmethod
    def step(self, world: Any, dt: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def query_ray(
        self,
        world: Any,
        origin: tuple[float, float],
        direction: tuple[float, float],
        max_distance: float,
    ) -> list[PhysicsRayHit]:
        raise NotImplementedError

    @abstractmethod
    def query_aabb(self, world: Any, bounds: tuple[float, float, float, float]) -> list[PhysicsAABBHit]:
        raise NotImplementedError

    def query_shape(self, world: Any, shape: dict[str, Any]) -> list[dict[str, Any]]:
        del world, shape
        return []

    @abstractmethod
    def collect_contacts(self, world: Any) -> list[PhysicsContact]:
        raise NotImplementedError

    @abstractmethod
    def sync_world(self, world: Any) -> None:
        raise NotImplementedError

    def set_event_bus(self, event_bus: Optional[Any]) -> None:
        del event_bus

    def get_step_metrics(self) -> dict[str, float]:
        return {}


__all__ = [
    "PhysicsAABBHit",
    "PhysicsBackend",
    "PhysicsBackendInfo",
    "PhysicsBackendSelection",
    "PhysicsContact",
    "PhysicsPoint",
    "PhysicsRayHit",
]
