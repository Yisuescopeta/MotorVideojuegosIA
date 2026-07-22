"""Stable identity and reference value objects for scene authoring."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


def _required(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class OpenDocumentId:
    """Session-only identity for one open document."""

    value: str

    def __post_init__(self) -> None:
        normalized = _required(self.value, field_name="OpenDocumentId.value")
        try:
            normalized = str(UUID(normalized))
        except ValueError as exc:
            raise ValueError("OpenDocumentId.value must be a UUID") from exc
        object.__setattr__(self, "value", normalized)

    @classmethod
    def new(cls) -> "OpenDocumentId":
        return cls(str(uuid4()))


@dataclass(frozen=True, slots=True)
class OpenSceneRef:
    document_id: OpenDocumentId


@dataclass(frozen=True, slots=True)
class SceneAssetRef:
    """Persistent scene identity; path is only a relocatable hint."""

    guid: str
    canonical_path_hint: str = ""

    def __post_init__(self) -> None:
        normalized = _required(self.guid, field_name="SceneAssetRef.guid")
        object.__setattr__(self, "guid", normalized)
        object.__setattr__(self, "canonical_path_hint", str(self.canonical_path_hint or "").strip())


@dataclass(frozen=True, slots=True)
class ResolvedSceneReference:
    """Project-owned resolution of a persistent scene asset reference."""

    scene: SceneAssetRef
    target_entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class EntityRef:
    scene: OpenSceneRef
    entity_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_id", _required(self.entity_id, field_name="EntityRef.entity_id"))


@dataclass(frozen=True, slots=True)
class ComponentRef:
    entity: EntityRef
    component_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_type", _required(self.component_type, field_name="ComponentRef.component_type"))


__all__ = [
    "ComponentRef",
    "EntityRef",
    "OpenDocumentId",
    "OpenSceneRef",
    "ResolvedSceneReference",
    "SceneAssetRef",
]
