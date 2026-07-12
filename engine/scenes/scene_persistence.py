from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from engine.scenes.storage import JsonSceneStorage, SceneStorage
from engine.serialization.schema import migrate_scene_data, validate_scene_data

COMPACT_SCENE_SAVE_ENTITY_THRESHOLD = 1000
COMPACT_SCENE_SAVE_SEPARATORS = (",", ":")


@dataclass(frozen=True)
class LoadedScenePayload:
    payload: dict[str, Any]
    resolved_path: str
    mtime: float | None


@dataclass(frozen=True)
class SavedSceneResult:
    resolved_path: str
    payload: dict[str, Any]
    entity_count: int
    mtime: float | None


class SceneStorageReadError(RuntimeError):
    """A storage backend failed while reading a scene payload."""


class ScenePersistenceService:
    """Owns technical scene file loading, saving, and verification."""

    def resolve_path(self, path: str | Path) -> Path:
        return Path(path).resolve()

    def get_mtime(self, path: str | Path) -> float | None:
        try:
            return os.path.getmtime(self.resolve_path(path))
        except OSError:
            return None

    def load(
        self,
        path: str | Path,
        *,
        storage: Optional[SceneStorage] = None,
    ) -> LoadedScenePayload:
        resolved = self.resolve_path(path)
        active_storage = storage or JsonSceneStorage()
        try:
            payload = active_storage.load(resolved)
        except Exception as exc:
            raise SceneStorageReadError(f"Failed to read scene storage {resolved}: {exc}") from exc
        verified = self._verified_payload(payload, error_prefix="Invalid scene payload")
        return LoadedScenePayload(
            payload=verified,
            resolved_path=str(resolved),
            mtime=self._read_mtime(resolved),
        )

    def save(
        self,
        path: str | Path,
        payload: dict[str, Any],
        *,
        compact_save: bool | None = None,
        storage: Optional[SceneStorage] = None,
    ) -> SavedSceneResult:
        target = Path(path)
        temp_path: Path | None = None
        stored_payload = payload
        entity_count = self._entity_count(stored_payload)
        try:
            if storage is None:
                temp_path = target.with_name(f"{target.name}.tmp")
                use_compact_save = (
                    compact_save if compact_save is not None else entity_count > COMPACT_SCENE_SAVE_ENTITY_THRESHOLD
                )
                active_storage: SceneStorage = JsonSceneStorage(
                    compact=use_compact_save,
                    separators=COMPACT_SCENE_SAVE_SEPARATORS,
                )
                active_storage.save(temp_path, stored_payload)
                temp_path.replace(target)
            else:
                active_storage = storage
                active_storage.save(target, stored_payload)

            verified = self._verified_payload(
                active_storage.load(target),
                error_prefix="Post-write validation failed",
            )
            readback_entity_count = self._entity_count(verified)
            if readback_entity_count != entity_count:
                raise ValueError(
                    f"Post-write entity count mismatch: written={readback_entity_count}, expected={entity_count}"
                )

            resolved = self.resolve_path(target)
            return SavedSceneResult(
                resolved_path=str(resolved),
                payload=stored_payload,
                entity_count=entity_count,
                mtime=self._read_mtime(resolved),
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def _entity_count(payload: dict[str, Any]) -> int:
        entities = payload.get("entities")
        return len(entities) if isinstance(entities, list) else 0

    def _read_mtime(self, path: str | Path) -> float | None:
        try:
            return self.get_mtime(path)
        except OSError:
            return None

    @staticmethod
    def _verified_payload(payload: dict[str, Any], *, error_prefix: str) -> dict[str, Any]:
        verified = migrate_scene_data(payload)
        validation_errors = validate_scene_data(verified)
        if validation_errors:
            raise ValueError(f"{error_prefix}: {'; '.join(validation_errors)}")
        return verified
