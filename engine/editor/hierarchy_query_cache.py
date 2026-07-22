"""Explicit cache for immutable hierarchy read models."""

from __future__ import annotations

from engine.editor.hierarchy_queries import HierarchyQueries, HierarchySnapshot
from engine.scenes.post_commit import DomainEvent, ScenePostCommitEventPublisher
from engine.scenes.refs import OpenDocumentId


class HierarchyQueryCache:
    """Caches hierarchy snapshots and invalidates them after scene commits."""

    def __init__(self, publisher: ScenePostCommitEventPublisher) -> None:
        self._snapshots: dict[tuple[OpenDocumentId, str], HierarchySnapshot] = {}
        self._invalidations = 0
        self._unsubscribe = publisher.subscribe(self._on_post_commit)

    @property
    def invalidation_count(self) -> int:
        return self._invalidations

    def snapshot(self, queries: HierarchyQueries, search: str = "") -> HierarchySnapshot:
        normalized_search = str(search or "").strip().casefold()
        key = (queries.scene_ref.document_id, normalized_search)
        cached = self._snapshots.get(key)
        if cached is not None:
            return cached
        result = queries.snapshot(normalized_search)
        self._snapshots[key] = result
        return result

    def invalidate_scene(self, document_id: OpenDocumentId) -> int:
        stale_keys = [key for key in self._snapshots if key[0] == document_id]
        for key in stale_keys:
            self._snapshots.pop(key, None)
        if stale_keys:
            self._invalidations += 1
        return len(stale_keys)

    def close(self) -> None:
        self._unsubscribe()

    def _on_post_commit(self, event: DomainEvent) -> None:
        self.invalidate_scene(event.scene.document_id)


__all__ = ["HierarchyQueryCache"]
