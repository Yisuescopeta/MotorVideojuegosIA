"""Registry of platform exporters."""

from __future__ import annotations

from typing import Optional

from engine.export.platform_exporter import PlatformExporter


class ExporterRegistry:
    _exporters: dict[str, PlatformExporter] = {}

    @classmethod
    def register(cls, exporter: PlatformExporter) -> None:
        cls._exporters[exporter.platform] = exporter

    @classmethod
    def get(cls, platform: str) -> Optional[PlatformExporter]:
        return cls._exporters.get(platform)

    @classmethod
    def list_platforms(cls) -> list[str]:
        return sorted(cls._exporters.keys())

    @classmethod
    def list_all(cls) -> list[PlatformExporter]:
        return list(cls._exporters.values())
