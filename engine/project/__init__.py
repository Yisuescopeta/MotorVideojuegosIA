"""
engine/project - Servicios de proyecto y estado del editor.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from engine.project.build_settings import BuildManifest, BuildSettings, BuildTargetPlatform
from engine.project.project_service import ProjectManifest, ProjectService

if TYPE_CHECKING:
    from engine.project.build_player import (
        BuildPlayerOptions,
        BuildPlayerService,
        BuildReport,
        BuildReportDiagnostic,
    )
    from engine.project.build_prebuild import (
        BuildPrebuildService,
        PrebuildDependencyGraphSummary,
        PrebuildDiagnostic,
        PrebuildReport,
        PrebuildSelectedContent,
    )

_BUILD_PLAYER_SYMBOLS = frozenset({
    "BuildPlayerOptions",
    "BuildPlayerService",
    "BuildReport",
    "BuildReportDiagnostic",
})
_BUILD_PREBUILD_SYMBOLS = frozenset({
    "BuildPrebuildService",
    "PrebuildDependencyGraphSummary",
    "PrebuildDiagnostic",
    "PrebuildReport",
    "PrebuildSelectedContent",
})


def __getattr__(name: str) -> object:
    if name in _BUILD_PLAYER_SYMBOLS:
        from engine.project import build_player as _m
        return getattr(_m, name)
    if name in _BUILD_PREBUILD_SYMBOLS:
        from engine.project import build_prebuild as _m
        return getattr(_m, name)
    raise AttributeError(f"module 'engine.project' has no attribute {name!r}")


__all__ = [
    "BuildManifest",
    "BuildPlayerOptions",
    "BuildPlayerService",
    "BuildPrebuildService",
    "BuildReport",
    "BuildReportDiagnostic",
    "BuildSettings",
    "BuildTargetPlatform",
    "PrebuildDependencyGraphSummary",
    "PrebuildDiagnostic",
    "PrebuildReport",
    "PrebuildSelectedContent",
    "ProjectManifest",
    "ProjectService",
]
