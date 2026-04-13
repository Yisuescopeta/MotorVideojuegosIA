from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, TypedDict


class PhysicsPoint(TypedDict):
    x: float
    y: float


class PhysicsRayHit(TypedDict, total=False):
    entity: str
    entity_id: int
    distance: float
    point: PhysicsPoint
    normal: PhysicsPoint
    is_trigger: bool


class PhysicsAABBHit(TypedDict):
    entity: str
    entity_id: int
    is_trigger: bool


class PhysicsBackendInfo(TypedDict):
    name: str
    available: bool
    unavailable_reason: Optional[str]


class PhysicsBackendSelection(TypedDict):
    requested_backend: str
    effective_backend: Optional[str]
    used_fallback: bool
    fallback_reason: Optional[str]
    unavailable_reason: Optional[str]


@dataclass
class PhysicsContact:
    entity_a: str
    entity_b: str
    entity_a_id: int
    entity_b_id: int
    is_trigger: bool
    normal_x: float | None = None
    normal_y: float | None = None
    penetration: float = 0.0
    contact_type: str = "overlap"
    source: str = "overlap"
    separation: float = 0.0


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

    Hooks como `create_body()` o `sync_world()` siguen existiendo para los
    adaptadores concretos, pero no deben ser usados como API publica.
    """

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
