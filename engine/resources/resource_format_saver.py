"""Resource format savers for .tres (text) and .res (binary) formats."""

from __future__ import annotations

from typing import Any


class ResourceFormatSaver:
    """Base class for resource format savers."""

    def get_recognized_extensions(self, resource: Any) -> list:
        return []

    def save(self, resource: Any, path: str) -> bool:
        raise NotImplementedError


class JSONResourceSaver(ResourceFormatSaver):
    """Saves resources as JSON."""

    def get_recognized_extensions(self, resource: Any) -> list:
        return ["json"]

    def save(self, resource: Any, path: str) -> bool:
        try:
            import json

            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    resource if isinstance(resource, dict) else resource.to_dict(),
                    f,
                    indent=2,
                )
            return True
        except (IOError, TypeError):
            return False


class BinaryResourceSaver(ResourceFormatSaver):
    """Saves resources as binary pickle format (.res)."""

    def get_recognized_extensions(self, resource: Any) -> list:
        return ["res"]

    def save(self, resource: Any, path: str) -> bool:
        try:
            import pickle

            with open(path, "wb") as f:
                pickle.dump(
                    resource if isinstance(resource, dict) else resource.to_dict(),
                    f,
                )
            return True
        except (IOError, TypeError):
            return False
