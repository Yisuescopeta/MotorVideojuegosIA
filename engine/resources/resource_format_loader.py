"""Resource format loaders for .tres (text) and .res (binary) formats."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from engine.resources.resource_uid import ResourceUIDCache


class ResourceFormatLoader:
    """Base class for resource format loaders."""

    def get_recognized_extensions(self) -> list:
        """Return list of file extensions this loader handles."""
        return []

    def load(self, path: str) -> Optional[Any]:
        """Load a resource from path."""
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        """Check if resource exists at path."""
        return os.path.exists(path)


class JSONResourceLoader(ResourceFormatLoader):
    """Loads .json resource files."""

    def get_recognized_extensions(self) -> list:
        return ["json", "motor_scene", "motor_prefab"]

    def load(self, path: str) -> Optional[dict]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None


class BinaryResourceLoader(ResourceFormatLoader):
    """Loads .res binary resource files."""

    def get_recognized_extensions(self) -> list:
        return ["res"]

    def load(self, path: str) -> Optional[Any]:
        try:
            import pickle

            with open(path, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, IOError):
            return None
