"""Deprecated compatibility shim for exported games.

Exported runtime now uses the shared Game + RuntimeController path.
"""

from __future__ import annotations

import warnings
from typing import Any

from engine.levels.component_registry import ComponentRegistry
from engine.runtime.content_loader import ContentLoader
from engine.runtime.shared_game_runtime import SharedGameRuntime
from engine.systems.render_system import RenderSystem


class ExportRuntime(SharedGameRuntime):
    """Deprecated alias for the shared exported Game runtime."""

    def __init__(
        self,
        loader: ContentLoader,
        registry: ComponentRegistry,
        *,
        window_config: dict[str, Any] | None = None,
        gravity: float = 600.0,
        render_system: RenderSystem | None = None,
    ) -> None:
        warnings.warn(
            "ExportRuntime is deprecated; use SharedGameRuntime backed by Game + RuntimeController.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(
            loader=loader,
            registry=registry,
            window_config=window_config,
            gravity=gravity,
            render_system=render_system,
        )
