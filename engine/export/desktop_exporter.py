"""Common desktop export logic.

DesktopExporter is abstract and cannot be instantiated directly.
Use WindowsExporter, LinuxExporter, or MacOSExporter instead.
"""

from __future__ import annotations

from typing import Any

from engine.export.platform_exporter import PlatformExporter


class DesktopExporter(PlatformExporter):
    platform = "desktop"

    def validate_environment(self) -> dict[str, Any]:
        raise NotImplementedError(
            "DesktopExporter is abstract. Use WindowsExporter, "
            "LinuxExporter, or MacOSExporter."
        )

    def export(self, ctx) -> bool:  # type: ignore[no-untyped-def]
        raise NotImplementedError(
            "DesktopExporter is abstract. Use WindowsExporter, "
            "LinuxExporter, or MacOSExporter."
        )
