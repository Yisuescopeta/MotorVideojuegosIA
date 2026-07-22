"""Immutable read models for the persistent :class:`Scene` domain object."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeAlias

JsonViewValue: TypeAlias = None | bool | int | float | str | tuple[Any, ...] | Mapping[str, Any]


def freeze_json(value: Any) -> JsonViewValue:
    """Recursively convert JSON-shaped data into immutable containers."""
    if isinstance(value, dict):
        return MappingProxyType(
            {str(key): freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze_json(item) for item in value)
    return value


def thaw_json(value: Any) -> Any:
    """Return a detached mutable JSON-shaped copy for explicit boundaries."""
    if isinstance(value, Mapping):
        return {str(key): thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    if isinstance(value, frozenset):
        return [thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class EntityView:
    """Immutable view of one serialized entity."""

    entity_id: str
    name: str
    data: Mapping[str, Any]

    @property
    def id(self) -> str:
        return self.entity_id

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return thaw_json(self.data)


@dataclass(frozen=True, slots=True)
class RuleView:
    """Immutable view of one persisted rule."""

    data: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return thaw_json(self.data)


@dataclass(frozen=True, slots=True)
class FeatureMetadataView:
    """Immutable view of scene feature metadata."""

    data: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return thaw_json(self.data)


@dataclass(frozen=True, slots=True)
class SceneSnapshot:
    """Immutable canonical snapshot captured from a scene."""

    name: str
    revision: int
    data: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return thaw_json(self.data)


def entity_view(entity_data: Mapping[str, Any]) -> EntityView:
    frozen = freeze_json(dict(entity_data))
    if not isinstance(frozen, Mapping):
        raise TypeError("entity_data must be JSON-shaped mapping")
    entity_id = entity_data.get("id")
    name = entity_data.get("name")
    return EntityView(
        entity_id=str(entity_id) if entity_id is not None else "",
        name=str(name) if name is not None else "",
        data=frozen,
    )


__all__ = [
    "EntityView",
    "FeatureMetadataView",
    "JsonViewValue",
    "RuleView",
    "SceneSnapshot",
    "entity_view",
    "freeze_json",
    "thaw_json",
]
