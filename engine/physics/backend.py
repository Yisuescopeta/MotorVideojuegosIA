from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PhysicsContact:
    entity_a: str
    entity_b: str
    entity_a_id: int
    entity_b_id: int
    is_trigger: bool


class PhysicsBackend(ABC):
    """Contrato estable para backends de fisica 2D."""

    backend_name: str = "unknown"

    @abstractmethod
    def create_body(self, entity: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def destroy_body(self, entity_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_shape(self, entity: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def step(self, world: Any, dt: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def query_ray(self, world: Any, origin: tuple[float, float], direction: tuple[float, float], max_distance: float) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def query_aabb(self, world: Any, bounds: tuple[float, float, float, float]) -> list[dict[str, Any]]:
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
