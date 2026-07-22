"""Composition root for constructing the runtime/editor graph.

The root owns construction-time wiring. Hosts expose only the capability
objects needed by their application surface; the root itself is not a runtime
dependency and is never used as a service locator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.app.runtime_system_factory import RuntimeSystemBundle, create_runtime_system_bundle
from engine.levels.component_registry import ComponentRegistry, create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager


@dataclass(frozen=True, slots=True)
class RuntimeHost:
    """Runtime construction products handed to the application entrypoint."""

    scene_manager: SceneManager
    project_service: ProjectService
    runtime_systems: RuntimeSystemBundle


@dataclass(frozen=True, slots=True)
class EditorHost:
    """Editor application products supplied by the GUI entrypoint."""

    application: Any
    shell: Any
    platform: Any


@dataclass(frozen=True, slots=True)
class EngineCompositionRoot:
    """Immutable construction result; never pass this object into systems."""

    runtime_host: RuntimeHost | None = None
    editor_host: EditorHost | None = None

    @classmethod
    def compose_runtime(
        cls,
        project_root: str | Path,
        *,
        global_state_dir: str | None = None,
        gravity: float = 600.0,
        auto_ensure_project: bool = False,
        read_only: bool = False,
        registry: ComponentRegistry | None = None,
    ) -> "EngineCompositionRoot":
        """Build the shared runtime graph in one explicit construction boundary."""
        component_registry = registry or create_default_registry()
        project_service = ProjectService(
            str(project_root),
            global_state_dir=global_state_dir,
            auto_ensure=auto_ensure_project,
            read_only=read_only,
        )
        runtime_host = RuntimeHost(
            scene_manager=SceneManager(component_registry),
            project_service=project_service,
            runtime_systems=create_runtime_system_bundle(gravity=gravity),
        )
        return cls(runtime_host=runtime_host)

    @classmethod
    def compose_editor(
        cls,
        *,
        application: Any,
        shell: Any,
        platform: Any,
        runtime_host: RuntimeHost | None = None,
    ) -> "EngineCompositionRoot":
        """Attach an editor host without making it a runtime service registry."""
        return cls(
            runtime_host=runtime_host,
            editor_host=EditorHost(
                application=application,
                shell=shell,
                platform=platform,
            ),
        )


__all__ = ["EditorHost", "EngineCompositionRoot", "RuntimeHost"]
