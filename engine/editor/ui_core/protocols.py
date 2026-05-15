"""Pure structural protocols for editor UI core models."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeAlias, runtime_checkable

PropertyValue: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | list["PropertyValue"]
    | tuple["PropertyValue", ...]
    | dict[str, "PropertyValue"]
)


@runtime_checkable
class EntityLike(Protocol):
    """Minimal entity shape consumed by pure tree view helpers."""

    id: int
    name: str


@runtime_checkable
class WorldLike(Protocol):
    """Minimal world shape for hierarchy snapshots."""

    def iter_all_entities(self) -> Iterable[EntityLike]: ...
