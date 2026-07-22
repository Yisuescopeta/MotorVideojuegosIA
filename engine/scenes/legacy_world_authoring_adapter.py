"""Explicit compatibility boundary for the deprecated World -> Scene path."""

from __future__ import annotations

from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON, SceneEditSyncCoordinator


class LegacyWorldAuthoringAdapter:
    """Closed allowlist for the remaining legacy authoring integration."""

    ALLOWED_REASONS = frozenset({LEGACY_AUTHORING_SYNC_REASON})

    def __init__(self, edit_sync: SceneEditSyncCoordinator) -> None:
        self._edit_sync = edit_sync

    def sync_pending(self) -> bool:
        return self._edit_sync.sync_from_edit_world()

    def mark_dirty(self, *, reason: str = LEGACY_AUTHORING_SYNC_REASON) -> bool:
        if reason not in self.ALLOWED_REASONS:
            return False
        return self._edit_sync.mark_edit_world_dirty(reason=reason)


__all__ = ["LegacyWorldAuthoringAdapter"]
