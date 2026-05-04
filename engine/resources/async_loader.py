"""Async resource loading using threading."""

from __future__ import annotations

import threading
from enum import Enum
from typing import Any, Callable, Optional


class LoadStatus(Enum):
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class AsyncLoadRequest:
    """Tracks an async resource load."""

    def __init__(self, path: str, loader_func: Callable[[str], Any]) -> None:
        self.path = path
        self.loader_func = loader_func
        self.status = LoadStatus.IN_PROGRESS
        self.resource: Any = None
        self.error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._load, daemon=True)
        self._thread.start()

    def _load(self) -> None:
        try:
            self.resource = self.loader_func(self.path)
            if self.resource is not None:
                self.status = LoadStatus.DONE
            else:
                self.status = LoadStatus.FAILED
                self.error = "Loader returned None"
        except Exception as e:
            self.error = str(e)
            self.status = LoadStatus.FAILED


class AsyncResourceLoader:
    """Manages async resource loading operations."""

    def __init__(self) -> None:
        self._pending: dict[str, AsyncLoadRequest] = {}

    def load_async(self, path: str, loader_func: Callable[[str], Any]) -> AsyncLoadRequest:
        """Start async resource load."""
        request = AsyncLoadRequest(path, loader_func)
        self._pending[path] = request
        request.start()
        return request

    def get_status(self, path: str) -> Optional[LoadStatus]:
        request = self._pending.get(path)
        return request.status if request else None

    def get_resource(self, path: str) -> Optional[Any]:
        """Get loaded resource if done."""
        request = self._pending.get(path)
        if request and request.status == LoadStatus.DONE:
            return request.resource
        return None

    def poll(self) -> list[AsyncLoadRequest]:
        """Get list of completed requests, removing them."""
        completed = []
        for path, request in list(self._pending.items()):
            if request.status in (LoadStatus.DONE, LoadStatus.FAILED):
                completed.append(request)
                del self._pending[path]
        return completed

    def pending_count(self) -> int:
        return len(self._pending)

    def clear(self) -> None:
        self._pending.clear()
