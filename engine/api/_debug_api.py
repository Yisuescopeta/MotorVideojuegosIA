from __future__ import annotations

from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult


class DebugAPI(EngineAPIComponent):
    """Debug and profiler endpoints exposed by EngineAPI."""

    def reset_profiler(self, run_label: str = "default") -> ActionResult:
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        runtime.reset_profiler(run_label=run_label)
        return self.ok("Profiler reset", {"run_label": run_label})

    def get_profiler_report(self) -> Dict[str, Any]:
        runtime = self.runtime
        if runtime is None:
            return {}
        return runtime.get_profiler_report()

    def configure_debug_overlay(
        self,
        *,
        draw_colliders: Optional[bool] = None,
        draw_labels: Optional[bool] = None,
        draw_tile_chunks: Optional[bool] = None,
        draw_camera: Optional[bool] = None,
        primitives: Optional[list[Dict[str, Any]]] = None,
    ) -> ActionResult:
        runtime = self.runtime
        if runtime is None or runtime.render_system is None:
            return self.fail("Render system not ready")
        runtime.debug_draw_colliders = runtime.debug_draw_colliders if draw_colliders is None else bool(draw_colliders)
        runtime.debug_draw_labels = runtime.debug_draw_labels if draw_labels is None else bool(draw_labels)
        runtime.render_system.set_debug_options(
            draw_colliders=draw_colliders,
            draw_labels=draw_labels,
            draw_tile_chunks=draw_tile_chunks,
            draw_camera=draw_camera,
        )
        if primitives is not None:
            runtime.render_system.set_debug_primitives(primitives)
        return self.ok("Debug overlay configured", runtime.render_system.get_debug_state())

    def clear_debug_primitives(self) -> ActionResult:
        runtime = self.runtime
        if runtime is None or runtime.render_system is None:
            return self.fail("Render system not ready")
        runtime.render_system.clear_debug_primitives()
        return self.ok("Debug primitives cleared")

    def get_debug_geometry_dump(
        self,
        viewport_width: int = 800,
        viewport_height: int = 600,
    ) -> Dict[str, Any]:
        runtime = self.runtime
        if runtime is None or runtime.render_system is None or runtime.world is None:
            return {}
        return runtime.render_system.get_debug_geometry_dump(
            runtime.world,
            viewport_size=(float(viewport_width), float(viewport_height)),
        )
