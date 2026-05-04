"""Resource UID system — stable IDs for resource references."""

from __future__ import annotations

import json
import os
import uuid
from typing import Dict, Optional


class ResourceUIDCache:
    """Maps resource paths to stable UIDs."""

    def __init__(self, cache_path: str = ".motor/resource_uid_cache.json") -> None:
        self._cache_path = cache_path
        self._path_to_uid: Dict[str, str] = {}
        self._uid_to_path: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, "r") as f:
                    data = json.load(f)
                self._path_to_uid = data.get("path_to_uid", {})
                self._uid_to_path = data.get("uid_to_path", {})
            except (json.JSONDecodeError, IOError):
                pass

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        with open(self._cache_path, "w") as f:
            json.dump(
                {
                    "path_to_uid": self._path_to_uid,
                    "uid_to_path": self._uid_to_path,
                },
                f,
                indent=2,
            )

    def get_or_create_uid(self, path: str) -> str:
        """Get existing UID or create a new one for this path."""
        if path in self._path_to_uid:
            return self._path_to_uid[path]
        uid = f"uid://{uuid.uuid4().hex[:12]}"
        self._path_to_uid[path] = uid
        self._uid_to_path[uid] = path
        self.save()
        return uid

    def resolve_uid(self, uid: str) -> Optional[str]:
        """Resolve a UID to its file path."""
        return self._uid_to_path.get(uid)

    def has_uid(self, uid: str) -> bool:
        return uid in self._uid_to_path

    def get_path(self, uid: str) -> Optional[str]:
        return self._uid_to_path.get(uid)

    def remove_path(self, path: str) -> None:
        uid = self._path_to_uid.pop(path, None)
        if uid:
            self._uid_to_path.pop(uid, None)
        self.save()

    def clear(self) -> None:
        self._path_to_uid.clear()
        self._uid_to_path.clear()
