"""Typed post-commit notifications for editor authoring changes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from engine.core.runtime_logging import log_err
from engine.scenes.refs import EntityRef, OpenSceneRef


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Fact describing one committed persistent scene change."""

    scene: OpenSceneRef
    scene_revision: int
    label: str
    changed_entities: tuple[EntityRef, ...] = ()
    history_entry_id: str | None = None

    @property
    def kind(self) -> str:
        return "scene_committed"


ScenePostCommitEvent: TypeAlias = DomainEvent


class PostCommitEventPublisher(Protocol):
    """Minimal output port for facts published after a commit."""

    def publish(self, event: DomainEvent) -> None: ...


class ScenePostCommitEventPublisher:
    """In-process editor publisher; subscribers are observers, not commands."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._subscribers: list[Callable[[DomainEvent], None]] = []

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)

    def subscribe(self, handler: Callable[[DomainEvent], None]) -> Callable[[], None]:
        if not callable(handler):
            raise TypeError("post-commit handler must be callable")
        self._subscribers.append(handler)

        def unsubscribe() -> None:
            try:
                self._subscribers.remove(handler)
            except ValueError:
                pass

        return unsubscribe

    def publish(self, event: DomainEvent) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError("post-commit publisher accepts DomainEvent instances")
        self._events.append(event)
        for handler in tuple(self._subscribers):
            try:
                handler(event)
            except Exception as exc:  # pragma: no cover - defensive boundary
                log_err(f"ScenePostCommitEventPublisher: handler failed: {exc}")


def changed_entity_refs(
    scene: OpenSceneRef,
    before: dict[str, object],
    after: dict[str, object],
) -> tuple[EntityRef, ...]:
    """Return stable refs for entities whose persisted payload changed."""

    def by_id(snapshot: dict[str, object]) -> dict[str, object]:
        entities = snapshot.get("entities", [])
        if not isinstance(entities, list):
            return {}
        result: dict[str, object] = {}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_id = entity.get("id")
            if isinstance(entity_id, str) and entity_id:
                result[entity_id] = entity
        return result

    before_entities = by_id(before)
    after_entities = by_id(after)
    changed_ids = sorted(
        entity_id
        for entity_id in set(before_entities) | set(after_entities)
        if before_entities.get(entity_id) != after_entities.get(entity_id)
    )
    return tuple(EntityRef(scene, entity_id) for entity_id in changed_ids)


__all__ = [
    "DomainEvent",
    "PostCommitEventPublisher",
    "ScenePostCommitEvent",
    "ScenePostCommitEventPublisher",
    "changed_entity_refs",
]
