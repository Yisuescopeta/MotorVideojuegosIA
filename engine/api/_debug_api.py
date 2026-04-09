from __future__ import annotations

from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult


class DebugAPI(EngineAPIComponent):
    """Debug and profiler endpoints exposed by EngineAPI."""

    def reset_profiler(self, run_label: str = "default") -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        self.game.reset_profiler(run_label=run_label)
        return self.ok("Profiler reset", {"run_label": run_label})

    def get_profiler_report(self) -> Dict[str, Any]:
        if self.game is None:
            return {}
        return self.game.get_profiler_report()

    def get_runtime_debug_snapshot(self) -> Dict[str, Any]:
        if self.game is None:
            return {}
        return self.game.get_runtime_debug_snapshot()

    def configure_debug_overlay(
        self,
        *,
        draw_colliders: Optional[bool] = None,
        draw_labels: Optional[bool] = None,
        draw_tile_chunks: Optional[bool] = None,
        draw_camera: Optional[bool] = None,
        primitives: Optional[list[Dict[str, Any]]] = None,
    ) -> ActionResult:
        if self.game is None or self.game.render_system is None:
            return self.fail("Render system not ready")
        self.game.debug_draw_colliders = self.game.debug_draw_colliders if draw_colliders is None else bool(draw_colliders)
        self.game.debug_draw_labels = self.game.debug_draw_labels if draw_labels is None else bool(draw_labels)
        self.game.render_system.set_debug_options(
            draw_colliders=draw_colliders,
            draw_labels=draw_labels,
            draw_tile_chunks=draw_tile_chunks,
            draw_camera=draw_camera,
        )
        if primitives is not None:
            self.game.render_system.set_debug_primitives(primitives)
        return self.ok("Debug overlay configured", self.game.render_system.get_debug_state())

    def clear_debug_primitives(self) -> ActionResult:
        if self.game is None or self.game.render_system is None:
            return self.fail("Render system not ready")
        self.game.render_system.clear_debug_primitives()
        return self.ok("Debug primitives cleared")

    def get_debug_geometry_dump(
        self,
        viewport_width: int = 800,
        viewport_height: int = 600,
    ) -> Dict[str, Any]:
        if self.game is None or self.game.render_system is None or self.game.world is None:
            return {}
        return self.game.render_system.get_debug_geometry_dump(
            self.game.world,
            viewport_size=(float(viewport_width), float(viewport_height)),
        )
