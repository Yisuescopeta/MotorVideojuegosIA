"""Abstract platform exporter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from engine.export.build_context import BuildContext


class PlatformExporter(ABC):
    platform: str = ""

    @abstractmethod
    def validate_environment(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def export(self, ctx: BuildContext) -> bool:
        ...
